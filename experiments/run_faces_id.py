"""Approach (e), gallery mode (Wikidata-scale index built by `python -m rp.gallery build`): identify impersonated public figures in ad screenshots (sample_v1 + DANE) with
YuNet + SFace against the Wikipedia-photo gallery (fetched by `python -m rp.gallery`, needs WIKIMEDIA_UA).
Scores against hand truth (ad_truth.yaml + DANE_TRUTH below) over cosine thresholds; compares with VLM-named persons.
Usage: uv run python run_faces_id.py"""
import json
import os

import cv2
import numpy as np
import yaml
from tabulate import tabulate

from rp.gallery import GAL, MODELS

DANE_TRUTH = {"d1": ["rafał brzoska"], "d3": ["monika olejnik", "adam glapiński"]}   # d48 deepfake studio: identities unclear -> excluded
det = cv2.FaceDetectorYN.create(os.path.join(MODELS, "yunet.onnx"), "", (320, 320), score_threshold=0.75)
rec = cv2.FaceRecognizerSF.create(os.path.join(MODELS, "sface.onnx"), "")


def faces(path):
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return []
    h, w = img.shape[:2]
    sc = 1.0 if max(h, w) <= 1600 else 1600 / max(h, w)
    im = cv2.resize(img, (int(w * sc), int(h * sc))) if sc != 1 else img
    det.setInputSize((im.shape[1], im.shape[0]))
    _, f = det.detect(im)
    out = []
    for row in (f if f is not None else []):
        v = rec.feature(rec.alignCrop(im, row))[0]
        out.append((float(row[-1]), v / np.linalg.norm(v)))
    return out


idx = np.load(os.path.join(GAL, "index_sface.npz"))
G = idx["emb"]
tmpl_names = np.array([str(x).lower() for x in idx["label"]])
names, inv = np.unique(tmpl_names, return_inverse=True)      # several templates (photos) per person
names = list(names)


def person_scores(v):
    """cosine of face v to every PERSON = max over that person's photos"""
    s = G @ v
    out = np.full(len(names), -1.0)
    np.maximum.at(out, inv, s)
    return out
print(f"gallery index: {len(names)} people, {len(tmpl_names)} photos")
truth = {k: v.get("persons") or [] for k, v in yaml.safe_load(open("ad_truth.yaml", encoding="utf-8")).items()}
truth.update(DANE_TRUTH)
shots = {}
for corpus in ("sample_v1", "dane"):
    for inc in json.load(open(f"../data/experiments/{corpus}/incidents.json", encoding="utf-8")):
        p = (inc["ad"].get("screenshots") or [inc["ad"].get("screenshot_path")])[0] if (inc["ad"].get("screenshots") or inc["ad"].get("screenshot_path")) else None
        if p and inc["id"] in truth:
            shots[inc["id"]] = p
hits = {}
for k, p in shots.items():
    hits[k] = []
    for _, v in faces(p):
        s = person_scores(v)
        o = np.argsort(-s)
        hits[k].append((names[o[0]], float(s[o[0]]), float(s[o[1]])))

rows = []
for thr, mg in [(t, 0.0) for t in (0.363, 0.40, 0.45, 0.50, 0.55)] + [(t, 0.10) for t in (0.40, 0.45, 0.50)]:
    tp = fp = fn = 0
    for k, want in truth.items():
        if k not in hits:
            continue
        got = {n for n, s, s2 in hits[k] if s >= thr and s - s2 >= mg}
        want = set(want) & set(names)
        tp += len(got & want)
        fp += len(got - want)
        fn += len(want - got)
    rows.append([thr, mg, tp, fp, fn, round(tp / (tp + fp), 2) if tp + fp else 1.0, round(tp / (tp + fn), 2) if tp + fn else 1.0])
print(tabulate(rows, headers=["cos thr", "min lead", "TP", "FP", "FN", "precision", "recall"], tablefmt="github"))
for k in sorted(hits, key=lambda x: (x[0], int(x[1:]))):
    print(k, [(n, round(s, 3), round(s2, 3)) for n, s, s2 in hits[k]], "| truth", truth.get(k))
json.dump({"hits": hits, "table": rows}, open("../data/experiments/joint/faces_gallery_id.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
