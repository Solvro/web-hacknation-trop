"""Merge optional layers into incidents.json -> <out>.json
  infra   : infra_enrich.json (DNS/RDAP/crt.sh)                      [always]
  --ad M  : ad_fields_<M>.json (M = easyocr-cpu | qwen38-27b-fp8 | ...)  -> ad.* (advertiser, text, creative_phash, ...)
  --faces : faces.json face clusters -> media.faces[].identity = faceN
  --emb K : out/emb_<corpus>/emb_<K>_text.npy -> emb.text_emb ; emb_siglip_crop.npy -> emb.shot_emb
Usage: uv run python merge_enrich.py <dir> <out_name> [--ad M] [--faces] [--emb mmlw]"""
import argparse
import json
import os

import numpy as np

from rp.extract import etld1

ap = argparse.ArgumentParser()
ap.add_argument("dir")
ap.add_argument("out")
ap.add_argument("--ad")
ap.add_argument("--faces", action="store_true")
ap.add_argument("--emb")
a = ap.parse_args()
D = a.dir
incs = json.load(open(os.path.join(D, "incidents.json"), encoding="utf-8"))
enr = json.load(open(os.path.join(D, "infra_enrich.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "infra_enrich.json")) else {}
CF_DEAD = {"ns1.dyna-ns.net", "ns2.dyna-ns.net", "ns1.dns-expired.com", "ns2.dns-expired.com"}   # parked/suspended: not operator evidence
for inc in incs:
    for d in inc["infra"]["domains"]:
        e = enr.get(etld1(d["fqdn"]))
        if not e:
            continue
        ns = sorted(x.rstrip(".").lower() for x in e.get("NS", []) if not x.startswith("ERR"))
        r = e.get("rdap") or {}
        d["enrich"] = {"ns": [] if set(ns) & CF_DEAD else ns, "registrar": r.get("registrar"), "created": r.get("created"),
                       "asn": sorted({x.get("asn") for x in e.get("asn", {}).values() if x.get("asn")}),
                       "certs": [{"issuer": c.get("issuer"), "not_before": c.get("not_before")} for c in e.get("crtsh", []) if c.get("not_before")]}
media = json.load(open(os.path.join(D, "media_ocr.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "media_ocr.json")) else {}
if a.ad:
    ad = json.load(open(os.path.join(D, f"ad_fields_{a.ad}.json"), encoding="utf-8"))
    for inc in incs:
        p = ad.get(inc["id"])
        if p and inc["ad"].get("screenshot_path"):
            inc["ad"].update({k: p.get(k) for k in ("advertiser", "text", "overlay", "library_id", "display_link", "cta", "is_decoy", "narrative") if p.get(k)})
            inc["ad"]["kind"] = p.get("screenshot_kind")
            m = media.get(inc["id"], {})
            if not p.get("is_decoy"):
                inc["ad"]["creative_phash"] = m.get("creative_phash")
if a.faces:
    fz = json.load(open(os.path.join(D, "faces.json"), encoding="utf-8"))["faces"]
    for inc in incs:
        inc.setdefault("media", {})["faces"] = [{"identity": f["face_cluster"], "score": f["det"]} for f in fz.get(inc["id"], []) if f.get("face_cluster")]
if a.emb:
    E = os.path.join(D, "emb")
    ids = json.load(open(os.path.join(E, "ids.json")))
    T = np.load(os.path.join(E, f"emb_{a.emb}_text.npy"))
    S = np.load(os.path.join(E, "emb_siglip_crop.npy")) if os.path.exists(os.path.join(E, "emb_siglip_crop.npy")) else None
    for inc in incs:
        k = ids.index(inc["id"])
        inc.setdefault("emb", {})["text_emb"] = T[k].tolist()
        if S is not None and not np.isnan(S[k]).any() and inc["ad"].get("screenshot_path") and not inc["ad"].get("is_decoy"):
            inc["emb"]["shot_emb"] = S[k].tolist()
json.dump(incs, open(os.path.join(D, a.out), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("wrote", os.path.join(D, a.out), "| enriched domains:", sum(1 for i in incs for d in i["infra"]["domains"] if d.get("enrich")))
