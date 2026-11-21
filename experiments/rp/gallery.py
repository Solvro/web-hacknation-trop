"""Face gallery of public figures for impersonation detection.

Two sources (both Wikimedia, both need a contact address in the User-Agent, which is NOT stored in the repo —
set it in your own shell:  $env:WIKIMEDIA_UA = "RedPill-research/0.1 (contact: <your address>)"):
  * wikidata : every notable Polish citizen with a portrait (Wikidata P27=Poland, P18 image, sitelinks >= MIN_SITELINKS,
               alive or died after 2000) + a curated list of international figures abused in Polish scam ads
  * curated  : the 25 hand-picked Wikipedia lead images (PEOPLE) — kept for the original small-gallery experiment

Commands (run from experiments/):
  uv run python -m rp.gallery fetch [--min-sitelinks 12] [--workers 4]   # network, needs WIKIMEDIA_UA
  uv run python -m rp.gallery fetch-extra [--top 500] [--workers 4]       # network: Commons photos for top people
  uv run python -m rp.gallery build [--per 3]                            # offline: detect + SFace-embed -> index
Outputs: data/experiments/face_gallery/wd/<QID>.jpg, meta.jsonl, index_sface.npz
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, unquote

import httpx

GAL = "../data/experiments/face_gallery"
WD = os.path.join(GAL, "wd")
MODELS = "../data/experiments/models"
PEOPLE = {  # canonical -> pl.wikipedia title (original 25-person curated gallery)
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
# international figures commonly faked in Polish investment/health scam ads — resolved by English Wikipedia title
INTERNATIONAL = ["Elon Musk", "Bill Gates", "Mark Zuckerberg", "Jeff Bezos", "Warren Buffett", "Ursula von der Leyen",
                 "Volodymyr Zelenskyy", "Christine Lagarde", "Donald Trump", "Angela Merkel", "Emmanuel Macron",
                 "Vladimir Putin", "Changpeng Zhao", "Vitalik Buterin", "David Beckham", "Lionel Messi",
                 "Cristiano Ronaldo", "Jensen Huang", "Bernard Arnault", "Pope Leo XIV", "Pope Francis", "Sam Altman",
                 "Kristalina Georgieva", "Friedrich Merz", "Keir Starmer"]
ZOO = {"yunet.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
       "sface.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"}
SPARQL = """
SELECT ?p ?img ?sl ?label WHERE {
  ?p wdt:P27 wd:Q36; wdt:P31 wd:Q5; wikibase:sitelinks ?sl.
  FILTER(?sl >= %(min_sl)d)
  ?p wdt:P18 ?img.
  OPTIONAL { ?p wdt:P570 ?d }
  FILTER(!BOUND(?d) || YEAR(?d) >= 2000)
  OPTIONAL { ?p rdfs:label ?label FILTER(LANG(?label) = "pl") }
}"""


def _client() -> httpx.Client:
    ua = os.environ.get("WIKIMEDIA_UA")
    if not ua:
        raise SystemExit("Set WIKIMEDIA_UA in your shell first (a User-Agent with a contact address).")
    return httpx.Client(timeout=90, headers={"User-Agent": ua}, follow_redirects=True)


def _intl_rows(h: httpx.Client) -> list[dict]:
    titles = " ".join('"' + t + '"@en' for t in INTERNATIONAL)
    q = f"""SELECT ?p ?title ?img ?sl ?label WHERE {{ VALUES ?title {{ {titles} }}
            ?article schema:about ?p; schema:isPartOf <https://en.wikipedia.org/>; schema:name ?title.
            ?p wdt:P18 ?img; wikibase:sitelinks ?sl.
            OPTIONAL {{ ?p rdfs:label ?label FILTER(LANG(?label)="pl") }} }}"""
    r = h.get("https://query.wikidata.org/sparql", params={"query": q, "format": "json"})
    r.raise_for_status()
    seen, out = set(), []
    for b in r.json()["results"]["bindings"]:
        qid = b["p"]["value"].rsplit("/", 1)[-1]
        if qid in seen:
            continue
        seen.add(qid)
        out.append({"qid": qid, "label": b.get("label", {}).get("value") or b["title"]["value"], "img": b["img"]["value"],
                    "sitelinks": int(b["sl"]["value"]), "source": "intl"})
    missing = set(INTERNATIONAL) - {b["title"]["value"] for b in r.json()["results"]["bindings"]}
    if missing:
        print("international titles not resolved:", sorted(missing))
    return out


def fetch(min_sitelinks: int = 12, workers: int = 4) -> None:
    os.makedirs(WD, exist_ok=True)
    h = _client()
    t0 = time.time()
    r = h.get("https://query.wikidata.org/sparql", params={"query": SPARQL % {"min_sl": min_sitelinks}, "format": "json"})
    r.raise_for_status()
    rows, seen = [], set()
    for b in r.json()["results"]["bindings"]:
        qid = b["p"]["value"].rsplit("/", 1)[-1]
        if qid in seen:            # several P18 images -> keep the first
            continue
        seen.add(qid)
        rows.append({"qid": qid, "label": b.get("label", {}).get("value"), "img": b["img"]["value"],
                     "sitelinks": int(b["sl"]["value"]), "source": "pl"})
    rows += [x for x in _intl_rows(h) if x["qid"] not in {y["qid"] for y in rows}]
    print(f"wikidata: {len(rows)} people with a portrait ({time.time()-t0:.0f}s); downloading thumbnails...", flush=True)
    with open(os.path.join(GAL, "meta.jsonl"), "w", encoding="utf-8") as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")

    def one(x):
        p = os.path.join(WD, x["qid"] + ".jpg")
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            return "cached"
        # P18 values are already percent-encoded Special:FilePath URLs -> use as-is (re-quoting gives 404)
        fname = unquote(x["img"].rsplit("/", 1)[-1])
        url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(fname)}?width=400"
        for attempt in range(4):
            try:
                rr = h.get(url)
            except httpx.HTTPError:
                time.sleep(2 ** attempt)
                continue
            if rr.status_code == 200 and rr.headers.get("content-type", "").startswith("image/"):
                open(p, "wb").write(rr.content)
                time.sleep(0.2)
                return "ok"
            if rr.status_code in (429, 503):
                time.sleep(int(rr.headers.get("retry-after", 5)) + 2 ** attempt)
                continue
            return f"http{rr.status_code}"
        return "fail"

    stats: dict = {}
    with ThreadPoolExecutor(workers) as ex:
        for i, s in enumerate(ex.map(one, rows), 1):
            stats[s] = stats.get(s, 0) + 1
            if i % 250 == 0:
                print(f"  {i}/{len(rows)} {stats} ({time.time()-t0:.0f}s)", flush=True)
    print(f"done: {stats} in {time.time()-t0:.0f}s -> {WD}")


# occupations whose holders are typically faked in PL scam ads (politicians, media, business, medicine, church, stars)
IMPERSONATED_OCC = ["Q82955", "Q1930187", "Q947873", "Q43845", "Q131524", "Q188094", "Q806798", "Q39631", "Q250867",
                    "Q33999", "Q177220", "Q937857"]
EXTRA = os.path.join(GAL, "extra")
BAD_FILE = ("signature", "podpis", "autograf", "logo", "herb", "coat_of_arms", "grave", "grób", "grob", "map", "flag",
            "flaga", "tablica", "plaque", ".svg", ".pdf", ".tif", ".webm", ".ogg", ".ogv", ".gif")


def fetch_extra(top: int = 500, per: int = 3, candidates: int = 6, workers: int = 4) -> None:
    """Extra photos from each person's Wikimedia Commons category for the ~`top` most-impersonated people
    (living, IMPERSONATED_OCC, ranked by sitelinks) + all international + curated people. Downloads up to
    `candidates` images per person; build() keeps at most `per` whose face matches the main portrait."""
    os.makedirs(EXTRA, exist_ok=True)
    h = _client()
    t0 = time.time()
    meta = {}
    for line in open(os.path.join(GAL, "meta.jsonl"), encoding="utf-8"):
        m = json.loads(line)
        meta[m["qid"]] = m
    # resume: reuse the people list (qid -> Commons category) of an earlier run instead of re-querying Wikidata
    for prev_list in ("extra.jsonl", "extra.run1.jsonl"):
        pl = os.path.join(GAL, prev_list)
        if os.path.exists(pl):
            chosen, missing = {}, []
            for line in open(pl, encoding="utf-8"):
                x = json.loads(line)
                if x.get("category"):
                    chosen[x["qid"]] = (meta.get(x["qid"], {}).get("sitelinks", 0), x["category"])
                else:
                    missing.append(x["qid"])
            for i in range(0, len(missing), 150):          # direct ID lookups: fast, far below the 60 s limit
                vals = " ".join("wd:" + q for q in missing[i:i + 150])
                rq = h.get("https://query.wikidata.org/sparql", params={
                    "query": "SELECT ?p ?cat WHERE { VALUES ?p { " + vals + " } ?p wdt:P373 ?cat }", "format": "json"})
                rq.raise_for_status()
                for b in json.loads(rq.text, strict=False)["results"]["bindings"]:
                    q = b["p"]["value"].rsplit("/", 1)[-1]
                    chosen[q] = (meta.get(q, {}).get("sitelinks", 0), b["cat"]["value"])
                time.sleep(1)
            if len(chosen) >= 50:
                print(f"reusing people list from {prev_list}: {len(chosen)} people", flush=True)
                return _download_extra(h, chosen, meta, candidates, workers, t0)
    occ = " ".join("wd:" + q for q in IMPERSONATED_OCC)
    q = ("SELECT ?p ?sl ?cat WHERE { VALUES ?occ { " + occ + " } "
         "?p wdt:P27 wd:Q36; wdt:P31 wd:Q5; wdt:P106 ?occ; wdt:P373 ?cat; wikibase:sitelinks ?sl. "
         "FILTER(?sl >= 5) FILTER NOT EXISTS { ?p wdt:P570 ?d } }")
    r = h.get("https://query.wikidata.org/sparql", params={"query": q, "format": "json"})
    r.raise_for_status()
    best = {}
    for b in json.loads(r.text, strict=False)["results"]["bindings"]:
        best[b["p"]["value"].rsplit("/", 1)[-1]] = (int(b["sl"]["value"]), b["cat"]["value"])
    chosen = dict(sorted(best.items(), key=lambda kv: -kv[1][0])[:top])
    meta = {}
    for line in open(os.path.join(GAL, "meta.jsonl"), encoding="utf-8"):
        m = json.loads(line)
        meta[m["qid"]] = m
    by_label = {(m["label"] or "").lower(): qid for qid, m in meta.items()}
    must = [qid for qid, m in meta.items() if m.get("source") == "intl"] + [by_label[n] for n in PEOPLE if n in by_label]
    must = [x for x in must if x not in chosen]
    if must:
        vals = " ".join("wd:" + x for x in must)
        r2 = h.get("https://query.wikidata.org/sparql",
                   params={"query": "SELECT ?p ?cat WHERE { VALUES ?p { " + vals + " } ?p wdt:P373 ?cat }", "format": "json"})
        r2.raise_for_status()
        for b in json.loads(r2.text, strict=False)["results"]["bindings"]:
            qid = b["p"]["value"].rsplit("/", 1)[-1]
            chosen[qid] = (meta.get(qid, {}).get("sitelinks", 0), b["cat"]["value"])
    print(f"extra photos: {len(chosen)} people with a Commons category ({time.time()-t0:.0f}s)", flush=True)
    return _download_extra(h, chosen, meta, candidates, workers, t0)


def _download_extra(h, chosen, meta, candidates, workers, t0):
    import threading
    api_lock = threading.Lock()          # the MediaWiki action API asks clients for serial requests

    def list_files(cat):
        for attempt in range(6):
            with api_lock:
                try:
                    rr = h.get("https://commons.wikimedia.org/w/api.php", params={
                        "action": "query", "list": "categorymembers", "cmtitle": "Category:" + cat, "cmtype": "file",
                        "cmlimit": 40, "format": "json", "maxlag": 5})
                    if rr.status_code == 200:
                        j = rr.json()
                        if "error" not in j:
                            time.sleep(0.3)
                            return [m["title"][5:] for m in j.get("query", {}).get("categorymembers", [])], "ok"
                    wait = int(rr.headers.get("retry-after", 0) or 0)
                except Exception:  # noqa: BLE001
                    wait = 0
                time.sleep(max(wait, 2 ** attempt))
        return [], "api_error"

    prev = {}
    if os.path.exists(os.path.join(GAL, "extra.jsonl")):
        for line in open(os.path.join(GAL, "extra.jsonl"), encoding="utf-8"):
            x = json.loads(line)
            if x.get("status") == "ok":
                prev[x["qid"]] = x

    def one(item):
        qid, (sl, cat) = item
        if qid in prev:
            return prev[qid]
        files, status = list_files(cat)
        if status != "ok":
            return {"qid": qid, "label": meta.get(qid, {}).get("label"), "files": [], "status": status}
        main = unquote(meta.get(qid, {}).get("img", "").rsplit("/", 1)[-1])
        files = [f for f in files if f != main and not any(b in f.lower() for b in BAD_FILE)][:candidates]
        saved = []
        for k, f in enumerate(files):
            dst = os.path.join(EXTRA, f"{qid}__{k}.jpg")
            if os.path.exists(dst) and os.path.getsize(dst) > 1000:
                saved.append(os.path.basename(dst))
                continue
            for attempt in range(3):
                try:
                    im = h.get(f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(f)}?width=400")
                except httpx.HTTPError:
                    time.sleep(2 ** attempt)
                    continue
                if im.status_code == 200 and im.headers.get("content-type", "").startswith("image/"):
                    open(dst, "wb").write(im.content)
                    saved.append(os.path.basename(dst))
                    break
                if im.status_code in (429, 503):
                    time.sleep(int(im.headers.get("retry-after", 5)) + 2 ** attempt)
                    continue
                break
            time.sleep(0.2)
        return {"qid": qid, "label": meta.get(qid, {}).get("label"), "category": cat, "files": saved, "status": "ok"}

    out, n_img = [], 0
    with ThreadPoolExecutor(workers) as ex:
        for i, res in enumerate(ex.map(one, chosen.items()), 1):
            out.append(res)
            n_img += len(res["files"])
            if i % 50 == 0:
                errs = sum(1 for o in out if o.get("status") != "ok")
                print(f"  {i}/{len(chosen)} people, {n_img} candidate photos, {errs} lookup errors ({time.time()-t0:.0f}s)", flush=True)
    with open(os.path.join(GAL, "extra.jsonl"), "w", encoding="utf-8") as f:
        for x in out:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print(f"done: {len(out)} people, {n_img} candidate photos in {time.time()-t0:.0f}s -> {EXTRA}")


def build(per: int = 3) -> None:
    """Offline: download the two ONNX face models if missing, detect the main face per portrait, SFace-embed."""
    import cv2
    import numpy as np
    os.makedirs(MODELS, exist_ok=True)
    for f, u in ZOO.items():
        if not os.path.exists(os.path.join(MODELS, f)):
            open(os.path.join(MODELS, f), "wb").write(httpx.get(u, follow_redirects=True, timeout=120).content)
    det = cv2.FaceDetectorYN.create(os.path.join(MODELS, "yunet.onnx"), "", (320, 320), score_threshold=0.8)
    rec = cv2.FaceRecognizerSF.create(os.path.join(MODELS, "sface.onnx"), "")
    meta = [json.loads(x) for x in open(os.path.join(GAL, "meta.jsonl"), encoding="utf-8")]
    for x in meta:
        x["path"] = os.path.join(WD, x["qid"] + ".jpg")
    # curated, commonly impersonated figures below the Wikidata notability cut (e.g. TV journalists, CEOs)
    # kept even when the person is already in the Wikidata list: several photos per person = better recall
    for name, title in PEOPLE.items():
        cp = os.path.join(GAL, title + ".jpg")
        if os.path.exists(cp):
            meta.append({"qid": "cur:" + title, "label": name.title(), "sitelinks": 0, "source": "curated", "path": cp})
    embs, keep, t0, nofc = [], [], time.time(), 0
    for x in meta:
        p = x["path"]
        if not os.path.exists(p):
            continue
        img = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            continue
        det.setInputSize((img.shape[1], img.shape[0]))
        _, f = det.detect(img)
        if f is None or not len(f):
            nofc += 1
            continue
        row = max(f, key=lambda r: r[2] * r[3])          # largest face = the subject of the portrait
        v = rec.feature(rec.alignCrop(img, row))[0]
        embs.append(v / np.linalg.norm(v))
        keep.append(x)
    # extra Commons photos: keep a photo only if one of its faces matches the person's main portrait(s)
    n_extra = n_rej = 0
    ex_path = os.path.join(GAL, "extra.jsonl")
    if os.path.exists(ex_path):
        E = np.asarray(embs, dtype=np.float32)
        qids = [x["qid"] for x in keep]
        labels = [(x["label"] or "").lower() for x in keep]
        for line in open(ex_path, encoding="utf-8"):
            x = json.loads(line)
            lab = (x.get("label") or "").lower()
            rows = [i for i, (q, l) in enumerate(zip(qids, labels)) if q == x["qid"] or (lab and l == lab)]
            if not rows:
                continue
            ref = E[rows]
            added = 0
            for fn in x["files"]:
                if added >= per:
                    break
                img = cv2.imdecode(np.fromfile(os.path.join(EXTRA, fn), dtype=np.uint8), cv2.IMREAD_COLOR)
                if img is None:
                    continue
                det.setInputSize((img.shape[1], img.shape[0]))
                _, f = det.detect(img)
                if f is None or not len(f):
                    continue
                cand = []
                for row in f:
                    v = rec.feature(rec.alignCrop(img, row))[0]
                    v = v / np.linalg.norm(v)
                    cand.append((float((ref @ v).max()), v))
                sim, v = max(cand, key=lambda c: c[0])
                if 0.45 <= sim <= 0.97:                      # same person, not a duplicate of the main portrait
                    embs.append(v)
                    keep.append({"qid": x["qid"], "label": keep[rows[0]]["label"],
                                 "sitelinks": keep[rows[0]]["sitelinks"], "source": "extra"})
                    added += 1
                    n_extra += 1
                else:
                    n_rej += 1
        print(f"extra photos: kept {n_extra}, rejected {n_rej} (face did not match the main portrait)")
    np.savez_compressed(os.path.join(GAL, "index_sface.npz"), emb=np.asarray(embs, dtype=np.float32),
                        qid=np.array([x["qid"] for x in keep]), label=np.array([x["label"] or x["qid"] for x in keep]),
                        sitelinks=np.array([x["sitelinks"] for x in keep]))
    print(f"index: {len(keep)} faces (no face found in {nofc} portraits) in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "fetch-extra", "build"])
    ap.add_argument("--min-sitelinks", type=int, default=12)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--top", type=int, default=500)
    ap.add_argument("--per", type=int, default=3)
    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch(a.min_sitelinks, a.workers)
    elif a.cmd == "fetch-extra":
        fetch_extra(a.top, a.per, workers=a.workers)
    else:
        build(a.per)
