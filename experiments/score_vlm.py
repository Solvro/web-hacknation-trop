"""Approach (d): score ad-screenshot extraction — EasyOCR (CPU) vs OCR-VLMs vs general VLMs (WCSS) — against ad_truth.yaml.
Writes <dir>/ad_fields_<model>.json  {id: ad-dict} for merging into incidents.
Usage: uv run python score_vlm.py [dir]"""
import json
import os
import re
import sys
from collections import defaultdict

import yaml
from rapidfuzz import fuzz
from tabulate import tabulate

from rp.media import parse_ocr

D = sys.argv[1] if len(sys.argv) > 1 else "../data/experiments/sample_v1"
truth = yaml.safe_load(open("ad_truth.yaml", encoding="utf-8"))
rows = [json.loads(x) for x in open(os.path.join(D, "vlm_sample_v1.jsonl"), encoding="utf-8")]
ocr_local = json.load(open(os.path.join(D, "media_ocr.json"), encoding="utf-8"))


def parse_json(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        try:
            return json.loads(re.sub(r",\s*}", "}", m.group(0)))
        except Exception:  # noqa: BLE001
            return {}


preds = defaultdict(dict)
secs = defaultdict(list)
for r in rows:
    secs[r["model"]].append(r["secs"])
    if "ocr" in r["model"]:
        lines = [(None, l, 1.0) for l in r["raw"].splitlines() if l.strip()]
        blob = r["raw"].lower()
        kind = "adlibrary" if ("szczegóły reklamy" in blob or "identyfikator biblioteki" in blob) else "feed"
        p = parse_ocr(lines, kind)
        p["screenshot_kind"] = kind
        p["persons"] = []
        preds[r["model"]][r["id"]] = p
    else:
        j = parse_json(r["raw"])
        preds[r["model"]][r["id"]] = {
            "screenshot_kind": j.get("kind"), "advertiser": j.get("advertiser"), "library_id": str(j.get("library_id") or "") or None,
            "text": " ".join(x for x in [j.get("caption") or ""] if x), "overlay": j.get("overlay_text"), "cta": j.get("cta"),
            "display_link": j.get("display_link"), "persons": [p.lower() for p in (j.get("persons") or []) if isinstance(p, str)],
            "is_decoy": j.get("is_decoy"), "vertical": j.get("vertical"), "brands": j.get("brands"), "narrative": j.get("narrative"),
            "_parsed": bool(j)}
for k, v in ocr_local.items():
    preds["easyocr-cpu"][k] = {**v, "persons": []}
secs["easyocr-cpu"] = [10.0]


def score(model):
    P = preds[model]
    c = defaultdict(list)
    for k, t in truth.items():
        p = P.get(k)
        if not p:
            continue
        c["kind"].append(p.get("screenshot_kind") == t["kind"])
        c["advertiser"].append(fuzz.ratio((p.get("advertiser") or "").lower(), t["advertiser"].lower()) >= 85)
        if t.get("library_id"):
            c["library_id"].append(str(p.get("library_id") or "") == str(t["library_id"]))
        if t.get("caption"):
            cap = ((p.get("text") or "") + " " + (p.get("overlay") or "")).lower()
            c["caption"].append(fuzz.token_set_ratio(cap, t["caption"].lower()) >= 70)
        want = set(t.get("persons") or [])
        got = {x for x in (p.get("persons") or []) if any(fuzz.partial_ratio(x, w) >= 85 for w in want) or not re.search(r"nieznan|unknown|anonim|lekar|kobiet|mężczy|prezenter|ai|osoba", x)}
        hit = {w for w in want if any(fuzz.partial_ratio(w, x) >= 85 for x in got)}
        c["persons_tp"].append(len(hit))
        c["persons_fn"].append(len(want - hit))
        c["persons_fp"].append(len([x for x in got if not any(fuzz.partial_ratio(x, w) >= 85 for w in want)]))
        if "decoy" in t and p.get("is_decoy") is not None:
            c["decoy"].append(bool(p.get("is_decoy")) == t["decoy"])
    tp, fn, fp = sum(c.pop("persons_tp")), sum(c.pop("persons_fn")), sum(c.pop("persons_fp"))
    out = {k: f"{sum(v)}/{len(v)}" for k, v in c.items()}
    out["persons P/R"] = f"{tp/(tp+fp) if tp+fp else 0:.2f}/{tp/(tp+fn) if tp+fn else 0:.2f}" if model != "easyocr-cpu" and "ocr" not in model else "n/a"
    out["s/img"] = round(sum(secs[model]) / len(secs[model]), 1)
    return out


tab = []
for m in ["easyocr-cpu", "paddleocr-vl", "glm-ocr", "qwen35-9b", "qwen38-27b-fp8", "qwen36-35b-a3b"]:
    if m in preds:
        s = score(m)
        tab.append([m] + [s.get(k, "") for k in ("kind", "advertiser", "library_id", "caption", "persons P/R", "decoy", "s/img")])
        json.dump(preds[m], open(os.path.join(D, f"ad_fields_{m}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(tabulate(tab, headers=["extractor", "kind", "advertiser", "library_id", "caption", "persons P/R", "decoy", "s/img"], tablefmt="github"))
for m in ("qwen36-35b-a3b",):
    print(f"\n{m} persons / vertical / narrative:")
    for k in sorted(preds[m], key=lambda x: int(x[1:])):
        p = preds[m][k]
        print(f"  {k}: {p.get('persons')} | {p.get('vertical')} | decoy={p.get('is_decoy')} | {str(p.get('narrative'))[:90]}")
