"""Optional layers merged into an extracted Incident: infra enrichment, ad-screenshot fields (VLM), creative pHash,
face identities, embeddings. Merge rules are experiments/merge_enrich.py's, unchanged.

Sources are pluggable (`trop.extract.cache`): content-addressed caches first (sha256 of the screenshot / eTLD+1),
then the experiments' precomputed files, then — only when `settings.trop_mode == 'live'` and WS4's
`trop.media.gateway` is importable — the live model gateway.
"""
from __future__ import annotations

import re

from .rules import etld1

CF_DEAD = {"ns1.dyna-ns.net", "ns2.dyna-ns.net", "ns1.dns-expired.com", "ns2.dns-expired.com"}  # parked: not operator evidence
AD_FIELDS = ("advertiser", "text", "overlay", "library_id", "display_link", "cta", "is_decoy", "narrative")
FACE_COS, FACE_LEAD = 0.45, 0.10   # RESULTS §2c: name a person only if cos >= 0.45 and top1 - top2 >= 0.10


def enrich_record(e: dict) -> dict:
    """infra_enrich.json record (DNS/RDAP/crt.sh/ASN) -> DomainInfo.enrich."""
    ns = sorted(x.rstrip(".").lower() for x in e.get("NS", []) if not str(x).startswith("ERR"))
    r = e.get("rdap") or {}
    return {"ns": [] if set(ns) & CF_DEAD else ns, "registrar": r.get("registrar"), "created": r.get("created"),
            "asn": sorted({x.get("asn") for x in (e.get("asn") or {}).values() if x.get("asn")}),
            "certs": [{"issuer": c.get("issuer"), "not_before": c.get("not_before")}
                      for c in e.get("crtsh", []) if c.get("not_before")]}


def apply_infra(inc: dict, lookup) -> int:
    """lookup(etld1) -> raw enrichment record or None. Returns #domains enriched."""
    n = 0
    for d in inc["infra"]["domains"]:
        e = lookup(etld1(d["fqdn"]))
        if not e:
            continue
        d["enrich"] = enrich_record(e)
        n += 1
    return n


def apply_ad_fields(inc: dict, p: dict | None, creative_phash: str | None = None) -> bool:
    """VLM fields of the ad screenshot -> ad.*. Persons from the VLM are NEVER copied (identity = face gallery)."""
    if not p or not inc["ad"].get("screenshot_path"):
        return False
    inc["ad"].update({k: p.get(k) for k in AD_FIELDS if p.get(k)})
    inc["ad"]["kind"] = p.get("screenshot_kind") or p.get("kind")
    if not p.get("is_decoy"):
        inc["ad"]["creative_phash"] = creative_phash
    return True


def face_hits_to_faces(hits: list, source: str = "ad_screenshot") -> list[dict]:
    """Gallery hits [[name, cos, runner_up_cos], ...] -> media.faces with identity only when the rule holds."""
    out = []
    for h in hits or []:
        name, cos, second = h[0], float(h[1]), float(h[2]) if len(h) > 2 and h[2] is not None else 0.0
        lead = cos - second
        if cos >= FACE_COS and lead >= FACE_LEAD:
            out.append({"identity": name, "score": round(cos, 3), "lead": round(lead, 3), "source": source})
    return out


# ------------------------------------------------------------------------------------- creative pHash (rp/media.py)
def creative_bbox(img) -> tuple[int, int, int, int]:
    """Largest 'busy' block = the creative. Row/col gradient projection (experiments/rp/media.py, unchanged)."""
    import numpy as np
    g = np.asarray(img.convert("L"), dtype=np.float32)
    h, w = g.shape
    grad = np.abs(np.diff(g, axis=1))
    row_busy = (grad > 12).mean(axis=1)
    rows = row_busy > 0.25
    best, cur, start, bstart = 0, 0, 0, 0
    for i, r in enumerate(rows):
        if r:
            if cur == 0:
                start = i
            cur += 1
            if cur > best:
                best, bstart = cur, start
        else:
            cur = 0
    if best < h * 0.15:
        return (0, 0, w, h)
    y0, y1 = bstart, bstart + best
    col_busy = (np.abs(np.diff(g[y0:y1], axis=0)) > 12).mean(axis=0)
    cols = np.where(col_busy > 0.2)[0]
    x0, x1 = (int(cols.min()), int(cols.max())) if len(cols) else (0, w)
    return (x0, y0, x1, y1)


def screenshot_phashes(path: str, kind: str | None = None) -> dict:
    """{screenshot_kind, creative_bbox, creative_phash, screenshot_phash} without OCR. kind: 'adlibrary'|'feed'|None
    (None -> aspect-ratio rule of rp/media.py: w > 1.8 h = Ad Library modal)."""
    import imagehash
    from PIL import Image
    img = Image.open(path).convert("RGB")
    w, h = img.size
    kind = kind if kind in ("adlibrary", "feed") else ("adlibrary" if w > 1.8 * h else "feed")
    base = img if kind == "feed" else img.crop((0, 0, int(w * 0.36), h))
    x0, y0, x1, y1 = creative_bbox(base)
    crop = base.crop((x0, y0, x1, y1))
    return {"screenshot_kind": kind, "creative_bbox": [x0, y0, x1, y1],
            "creative_phash": str(imagehash.phash(crop, hash_size=8)), "screenshot_phash": str(imagehash.phash(img, hash_size=8))}


def normalise_vlm(raw: dict) -> dict:
    """Live gateway / vlm_*.jsonl field names -> ad_fields_*.json names."""
    p = dict(raw)
    if "caption" in p and "text" not in p:
        p["text"] = p.pop("caption")
    if "overlay_text" in p and "overlay" not in p:
        p["overlay"] = p.pop("overlay_text")
    if "kind" in p and "screenshot_kind" not in p:
        p["screenshot_kind"] = p["kind"]
    if p.get("library_id"):
        p["library_id"] = re.sub(r"\D", "", str(p["library_id"])) or None
    return p
