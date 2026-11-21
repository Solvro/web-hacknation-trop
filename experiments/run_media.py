"""Screenshot layer on CPU: kind, creative crop, pHash, EasyOCR -> ad fields. Scores OCR extraction vs ad_truth.yaml.
Usage: uv run python run_media.py [incidents.json] [ad_truth.yaml]
Writes <dir>/media_ocr.json  {id: ad-dict}."""
import json
import os
import sys
import time

import yaml
from rapidfuzz import fuzz

from rp.media import analyze_screenshot

INC = sys.argv[1] if len(sys.argv) > 1 else "../data/experiments/sample_v1/incidents.json"
TRUTH = sys.argv[2] if len(sys.argv) > 2 else "ad_truth.yaml"
OUT = os.path.join(os.path.dirname(INC), "media_ocr.json")
incs = json.load(open(INC, encoding="utf-8"))
truth = yaml.safe_load(open(TRUTH, encoding="utf-8")) if os.path.exists(TRUTH) else {}
res, times = {}, []
for inc in incs:
    p = inc["ad"].get("screenshot_path")
    if not p:
        continue
    t0 = time.time()
    res[inc["id"]] = analyze_screenshot(p, do_ocr=True)
    times.append(time.time() - t0)
    print(inc["id"], f"{times[-1]:.1f}s", res[inc["id"]].get("screenshot_kind"), "|", res[inc["id"]].get("advertiser"), "|", (res[inc["id"]].get("text") or "")[:80], flush=True)
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def score(pred: dict, truth: dict) -> dict:
    """Field accuracy: kind exact, advertiser fuzzy>=85, library_id exact, caption token_set>=70."""
    rows = {"kind": [], "advertiser": [], "library_id": [], "caption": []}
    for k, t in truth.items():
        p = pred.get(k)
        if not p:
            continue
        rows["kind"].append(p.get("screenshot_kind") == t["kind"])
        rows["advertiser"].append(fuzz.ratio((p.get("advertiser") or "").lower(), t["advertiser"].lower()) >= 85)
        if t.get("library_id"):
            rows["library_id"].append(p.get("library_id") == str(t["library_id"]))
        if t.get("caption"):
            rows["caption"].append(fuzz.token_set_ratio((p.get("text") or "").lower(), t["caption"].lower()) >= 70)
    return {k: f"{sum(v)}/{len(v)}" for k, v in rows.items()}


print("OCR field accuracy:", score(res, truth), f"| mean {sum(times)/len(times):.1f}s/screenshot on CPU")
