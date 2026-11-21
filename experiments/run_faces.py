"""Approach (e): face detection + recognition against a small gallery of commonly impersonated public figures.

Gallery: Wikipedia lead images (public, fetched once into data/experiments/face_gallery/).
Models: OpenCV Zoo YuNet (detector) + SFace (recognizer), ONNX, CPU (~40 ms/face). Open-set threshold on cosine.
Scores vs ad_truth.yaml persons. Writes <dir>/faces.json  {id: [{identity, score, bbox}]}.
Usage: uv run python run_faces.py [incidents.json]"""
import json
import os
import sys
import time

import cv2
import httpx
import numpy as np
import yaml

INC = sys.argv[1] if len(sys.argv) > 1 else "../data/experiments/sample_v1/incidents.json"
D = os.path.dirname(INC)
GAL = "../data/experiments/face_gallery"
MODELS = "../data/experiments/models"
os.makedirs(GAL, exist_ok=True)
os.makedirs(MODELS, exist_ok=True)
H = httpx.Client(timeout=60, headers={"User-Agent": "research-client/0.1 (face gallery, public figures)"}, follow_redirects=True)

PEOPLE = {  # canonical -> pl.wikipedia title
    "mateusz morawiecki": "Mateusz_Morawiecki", "rafał brzoska": "Rafał_Brzoska", "krzysztof stanowski": "Krzysztof_Stanowski",
    "tomasz sekielski": "Tomasz_Sekielski", "adam glapiński": "Adam_Glapiński", "monika olejnik": "Monika_Olejnik",
    "karol nawrocki": "Karol_Nawrocki", "radosław sikorski": "Radosław_Sikorski", "wołodymyr zełenski": "Wołodymyr_Zełenski",
    "ursula von der leyen": "Ursula_von_der_Leyen", "donald tusk": "Donald_Tusk", "jarosław kaczyński": "Jarosław_Kaczyński",
    "andrzej domański": "Andrzej_Domański", "andrzej duda": "Andrzej_Duda", "robert lewandowski": "Robert_Lewandowski",
    "szymon hołownia": "Szymon_Hołownia", "rafał trzaskowski": "Rafał_Trzaskowski", "sławomir mentzen": "Sławomir_Mentzen",
    "krzysztof bosak": "Krzysztof_Bosak", "kuba wojewódzki": "Kuba_Wojewódzki", "małgorzata rozenek": "Małgorzata_Rozenek-Majdan",
    "przemysław czarnek": "Przemysław_Czarnek", "elon musk": "Elon_Musk", "zygmunt solorz": "Zygmunt_Solorz",
    "dawid kubacki": "Dawid_Kubacki",
}
ZOO = {"yunet": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
       "sface": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"}


def fetch(url, path):
    if not os.path.exists(path):
        r = H.get(url)
        r.raise_for_status()
        open(path, "wb").write(r.content)
    return path


yunet_p = fetch(ZOO["yunet"], os.path.join(MODELS, "yunet.onnx"))
sface_p = fetch(ZOO["sface"], os.path.join(MODELS, "sface.onnx"))
det = cv2.FaceDetectorYN.create(yunet_p, "", (320, 320), score_threshold=0.75)
rec = cv2.FaceRecognizerSF.create(sface_p, "")


def faces(img):
    h, w = img.shape[:2]
    scale = 1.0 if max(h, w) <= 1600 else 1600 / max(h, w)
    im = cv2.resize(img, (int(w * scale), int(h * scale))) if scale != 1 else img
    det.setInputSize((im.shape[1], im.shape[0]))
    _, f = det.detect(im)
    out = []
    for row in (f if f is not None else []):
        feat = rec.feature(rec.alignCrop(im, row))
        feat = feat / np.linalg.norm(feat)
        out.append((row[:4] / scale, float(row[-1]), feat[0]))
    return out


# --- gallery
gal = {}
for name, title in PEOPLE.items():
    p = os.path.join(GAL, title + ".jpg")
    if not os.path.exists(p):
        try:
            j = H.get(f"https://pl.wikipedia.org/api/rest_v1/page/summary/{title}").json()
            src = (j.get("thumbnail") or {}).get("source") or (j.get("originalimage") or {}).get("source")
            src = src.replace("/320px-", "/640px-") if src else None
            if src:
                fetch(src, p)
            time.sleep(0.5)
        except Exception as e:  # noqa: BLE001
            print("gallery miss", name, e)
            continue
    if os.path.exists(p):
        img = cv2.imread(p)
        fs = faces(img) if img is not None else []
        if fs:
            gal[name] = max(fs, key=lambda x: x[1])[2]
print(f"gallery: {len(gal)}/{len(PEOPLE)} identities with a detected face")
GN = list(gal)
G = np.stack(list(gal.values())) if gal else np.zeros((0, 128), dtype=np.float32)

# --- probes
incs = json.load(open(INC, encoding="utf-8"))
truth = yaml.safe_load(open("ad_truth.yaml", encoding="utf-8"))
res, t_all = {}, []
for inc in incs:
    p = inc["ad"].get("screenshot_path")
    if not p:
        continue
    t0 = time.time()
    img = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
    out = []
    for box, conf, feat in faces(img):
        if len(GN):
            sims = G @ feat
            k = int(np.argmax(sims))
            top, cos = GN[k], round(float(sims[k]), 3)
        else:
            top, cos = None, 0.0
        out.append({"identity_top": top, "cos": cos, "det": round(conf, 2), "bbox": [round(float(x)) for x in box], "feat": feat.tolist()})
    res[inc["id"]] = out
    t_all.append(time.time() - t0)

# --- cross-ad face re-identification (no gallery): same real face reused across ads
SAME_FACE = {("p1", "p2"), ("p1", "p7"), ("p1", "p15"), ("p2", "p7"), ("p2", "p15"), ("p7", "p15")}   # Morawiecki inset
ids_ = [k for k in res if res[k]]
print("faces per screenshot:", {k: len(v) for k, v in res.items()})
pair_rows = []
for i, a in enumerate(ids_):
    for b in ids_[i + 1:]:
        best = max(float(np.dot(fa["feat"], fb["feat"])) for fa in res[a] for fb in res[b])
        key = tuple(sorted((a, b), key=lambda x: int(x[1:])))
        pair_rows.append((key, best, key in SAME_FACE))
pair_rows.sort(key=lambda r: -r[1])
for (a, b), sim, same in pair_rows[:12]:
    print(f"  {a}-{b} face cos={sim:.3f} truth_same_person={same}")
for thr in (0.363, 0.45, 0.55):
    tp = sum(1 for _, s_, t in pair_rows if s_ >= thr and t); fp = sum(1 for _, s_, t in pair_rows if s_ >= thr and not t)
    fn = sum(1 for _, s_, t in pair_rows if s_ < thr and t)
    print(f"  reid thr {thr}: TP {tp} FP {fp} FN {fn} (pairs with faces on both sides: {len(pair_rows)})")
# face-cluster ids as identity proxy for the evidence engine
import itertools
clusters, cid = {}, 0
allf = [(k, j, f["feat"]) for k, v in res.items() for j, f in enumerate(v)]
lab = list(range(len(allf)))
for x, y in itertools.combinations(range(len(allf)), 2):
    if allf[x][0] != allf[y][0] and float(np.dot(allf[x][2], allf[y][2])) >= 0.45:
        lx, ly = lab[x], lab[y]
        lab = [lx if l == ly else l for l in lab]
for (k, j, _), l in zip(allf, lab):
    res[k][j]["face_cluster"] = f"face{l}"

# --- open-set evaluation over thresholds (SFace paper: cosine 0.363 for same identity)
print("\nthr | TP FP FN | precision recall | non-gallery faces wrongly named")
best = None
for thr in (0.30, 0.363, 0.40, 0.45, 0.50):
    tp = fp = fn = 0
    for k, t in truth.items():
        got = {f["identity_top"] for f in res.get(k, []) if f["cos"] >= thr}
        want = set(t.get("persons") or []) & set(GN)
        tp += len(got & want)
        fp += len(got - want)
        fn += len(want - got)
    P = tp / (tp + fp) if tp + fp else 1.0
    R = tp / (tp + fn) if tp + fn else 1.0
    print(f"{thr:.3f} | {tp} {fp} {fn} | {P:.2f} {R:.2f}")
    if best is None or (P >= 0.99 and R > best[2]):
        best = (thr, P, R)
for k, v in res.items():
    print(k, [(f["identity_top"], f["cos"], f.get("face_cluster")) for f in v], "| truth", truth.get(k, {}).get("persons"))
THR = 0.40
for v in res.values():
    for f in v:
        f.pop("feat", None)
json.dump({"faces": res, "thr": THR, "ms_per_image": 1000 * float(np.mean(t_all))}, open(os.path.join(D, "faces.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"mean {1000*np.mean(t_all):.0f} ms/screenshot (CPU)")
