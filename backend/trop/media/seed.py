"""Pre-seed the gateway cache from the experiment VLM outputs (Qwen3.6-35B-A3B on WCSS), keyed exactly as
`gateway.ad_fields(<same screenshot>)` keys them, so a judge build without API keys still has the VLM fields."""
from __future__ import annotations

import json
from pathlib import Path

from trop.config import settings
from trop.media.gateway import gateway, norm_ad, parse_json

MODEL = "qwen36-35b-a3b"


def _resolve(p: str) -> Path | None:
    """Incident JSON stores Windows-style paths relative to experiments/ ('../data/raw/...')."""
    s = p.replace("\\", "/")
    s = s.removeprefix("../data/")
    q = Path(settings.data_dir) / s
    return q if q.exists() else None


def seed(data_dir: Path | None = None) -> dict:
    root = Path(data_dir or settings.data_dir) / "experiments"
    stats = {"seeded": 0, "existing": 0, "no_image": 0, "no_fields": 0}
    for corpus in ("sample_v1", "dane"):
        inc_f = root / corpus / "incidents.json"
        fields_f = root / corpus / f"ad_fields_{MODEL}.json"
        if not (inc_f.exists() and fields_f.exists()):
            continue
        incs = {i["id"]: i for i in json.loads(inc_f.read_text(encoding="utf-8"))}
        fields = json.loads(fields_f.read_text(encoding="utf-8"))
        shots: dict[str, list[str]] = {}
        for iid, inc in incs.items():
            ad = inc.get("ad", {})
            shots[iid] = list(ad.get("screenshots") or ([ad["screenshot_path"]] if ad.get("screenshot_path") else []))
        work: list[tuple[str, dict]] = [(iid, f) for iid, f in fields.items()]
        # per-screenshot raw answers (d10_0, d10_1, ...) from the jsonl, when present
        for jl in (root / corpus).glob("vlm_*.jsonl"):
            for line in jl.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                if r.get("model") == MODEL and "_" in r["id"] and "ERROR" not in r.get("raw", "")[:8]:
                    j = parse_json(r["raw"])
                    if j:
                        work.append((r["id"], j))
        for rid, f in work:
            iid, _, idx = rid.partition("_")
            lst = shots.get(iid) or []
            i = int(idx) if idx.isdigit() else 0
            img = _resolve(lst[i]) if i < len(lst) else None
            if img is None:
                stats["no_image"] += 1
                continue
            key = gateway.ad_key(str(img))
            if gateway.cache_get(key):
                stats["existing"] += 1
                continue
            res = norm_ad(f, "qwen/qwen3.6-35b-a3b")
            res["_seeded_from"] = f"experiments/{corpus}"
            gateway.cache_put(key, "ad_fields", gateway.ad_chain, res, seeded=True)
            stats["seeded"] += 1
    return stats
