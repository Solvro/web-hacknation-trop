"""Déjà Vu evidence engine — ported UNCHANGED from experiments/rp/evidence.py (RESULTS §0/§4; regression gate
G-ENGINE). Only addition: evidence items carry `raw` (the shared values) for explanations; scoring is identical.

Typed, rarity-weighted pair evidence (approach a) + the pair feature vector used by the learned model (approach c).

weight(evidence) = strength(type) x rarity(value)
  * identifier-type values (pixel, tenant, lander, gateway, AW/GA4, domain) -> rarity 1 unless blocklisted
  * shape-type values (param schema, endpoints, third parties, assets, persons, brands) -> IDF-normalised rarity
Missing field on either side contributes 0 and lowers `coverage`. Negative evidence only for a high-strength
field present on both sides and conflicting (kit tenant).
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from itertools import combinations

from datasketch import MinHash

# ---------------------------------------------------------------------------------------- strengths
# Priors (log-likelihood-ratio-like). Calibrated later by the GBM (approach c) and grid search.
STRENGTH = {
    # tracking / operator identifiers (H)
    "fb_pixel": 6.0, "capi_gateway": 6.0, "google_ads": 6.0, "ga4": 6.0, "gtm": 6.0, "tiktok_pixel": 6.0,
    "kit_tenant": 6.0, "lander_id": 7.0, "landing_type_id": 4.0, "video_host": 5.0, "etld1": 6.0, "fqdn": 6.0,
    # kit (H/M)
    "asset_hash": 5.0, "kit_endpoints": 1.0, "url_param_schema": 1.5, "entry_path_template": 1.5, "third_party": 2.0,
    "dom_minhash": 3.0, "favicon": 1.0,
    # infra (M)
    "origin_ip": 3.0, "cert_batch": 2.0, "domain_dna": 0.5,
    # content (H/M/L)
    "headline_template": 4.0, "h1_template": 3.0, "text_minhash": 5.0, "persons": 1.5, "brands": 1.0,
    "products": 3.0, "vertical": 0.5, "ad_name_grammar": 1.0, "comment_names": 2.0, "brand_asset": 0.5,
    "ns_pair": 4.0, "registrar_batch": 3.0, "entry_url": 8.0, "path_shape": 3.0, "chain_etld1": 4.0,
    # ad layer (filled by OCR/VLM modules)
    "advertiser": 2.0, "ad_text": 3.5, "creative_phash": 3.0, "ad_persons": 1.5,
    # embeddings (filled by emb module)
    "text_emb": 3.0, "shot_emb": 2.0, "face_identity": 2.5,
}
# TROP addition (video / ASR layer, WS4 output). Only present when an incident has media.video.gemini / asr_text, so the
# RESULTS §2a/§2b numbers are unaffected. media_text = text MinHash over transcript + on-screen text (same strength as
# text_minhash, campaign-level content); voice_id = speaker-embedding cluster (operator-ish: a voice-over artist / TTS
# voice is reused across an operator's products) -> operator-only, counts for the campaign only via the conjunction.
STRENGTH.update({"media_text": 5.0, "voice_id": 4.0})
NEG = {"kit_tenant_conflict": -5.0, "vertical_conflict": -1.0, "lang_conflict": -2.0}
LAYER = {
    "fb_pixel": "tracking", "capi_gateway": "tracking", "google_ads": "tracking", "ga4": "tracking", "gtm": "tracking",
    "tiktok_pixel": "tracking", "kit_tenant": "kit", "lander_id": "kit", "landing_type_id": "kit", "video_host": "kit",
    "asset_hash": "kit", "kit_endpoints": "kit", "url_param_schema": "kit", "entry_path_template": "kit",
    "third_party": "kit", "dom_minhash": "kit", "favicon": "kit", "etld1": "infra", "fqdn": "infra",
    "origin_ip": "infra", "cert_batch": "infra", "domain_dna": "infra", "headline_template": "content",
    "h1_template": "content", "text_minhash": "content", "persons": "content", "brands": "content",
    "products": "content", "vertical": "content", "ad_name_grammar": "kit", "advertiser": "ad", "ad_text": "ad",
    "creative_phash": "visual", "ad_persons": "ad", "text_emb": "content", "shot_emb": "visual",
    "face_identity": "persons", "comment_names": "content", "brand_asset": "kit", "ns_pair": "infra", "registrar_batch": "infra", "entry_url": "infra", "path_shape": "kit", "chain_etld1": "infra",
    "media_text": "content", "voice_id": "media",
}
HIGH = {"fb_pixel", "capi_gateway", "google_ads", "ga4", "gtm", "kit_tenant", "lander_id", "etld1", "asset_hash",
        "headline_template", "text_minhash", "video_host", "products"}
IDENTIFIER_TYPES = {"chain_etld1", "entry_url", "ns_pair", "ad_text", "advertiser", "face_identity", "fb_pixel", "capi_gateway", "google_ads", "ga4", "gtm", "tiktok_pixel", "kit_tenant", "lander_id",
                    "landing_type_id", "video_host", "etld1", "fqdn"}
GENERIC_TEMPLATES = {"", "{PER}", "home", "index", "strona główna"}

# Evidence that identifies the OPERATOR ACCOUNT (hosting/kit/registrar) but not a specific campaign: an operator runs
# several campaigns from one Cloudflare account / kit tenant / domain batch. Campaign-level score excludes these.
OPERATOR_ONLY = {"chain_etld1", "path_shape", "kit_tenant", "ns_pair", "registrar_batch", "third_party", "landing_type_id", "origin_ip", "cert_batch",
                 "domain_dna", "kit_endpoints", "url_param_schema", "entry_path_template", "brand_asset", "vertical",
                 "voice_id"}
CONJUNCTION = True   # same operator AND same narrative => same campaign (operator evidence capped at +4)
LEVEL = "campaign"   # 'campaign' | 'operator' — which score the harness scorer uses

# Per-type feature disabling for ablations / robustness
DISABLED: set[str] = set()


def _shingles(tokens, k):
    return {" ".join(tokens[i:i + k]) for i in range(max(0, len(tokens) - k + 1))}


_MH_CACHE: dict = {}


def minhash_of(items, num_perm=128) -> MinHash | None:
    if not items:
        return None
    key = hash(frozenset(items))
    if key in _MH_CACHE:
        return _MH_CACHE[key]
    m = MinHash(num_perm=num_perm, seed=7)
    m.update_batch([s.encode("utf-8") for s in items])
    _MH_CACHE[key] = m
    return m


def prepare(incs: list[dict]) -> None:
    """Precompute set-valued views + MinHashes on each incident (in place, under '_v')."""
    for inc in incs:
        t, la, c, inf, ad = inc["tracking"], inc["landing"], inc["content"], inc["infra"], inc.get("ad", {})
        v = {}
        v["fb_pixel"] = set(t.get("fb_pixels", []))
        v["capi_gateway"] = set(t.get("capi_gateways", []))
        v["google_ads"] = set(t.get("google_ads", []))
        v["ga4"] = set(t.get("ga4", []))
        v["gtm"] = set(t.get("gtm", []))
        v["tiktok_pixel"] = set(t.get("tiktok_pixels", []))
        v["kit_tenant"] = set(t.get("kit_tenants", []))
        v["lander_id"] = set(t.get("lander_ids", []))
        v["landing_type_id"] = set(t.get("landing_type_ids", []))
        v["video_host"] = set(t.get("video_hosts", []))
        v["asset_hash"] = set(t.get("asset_hashes", []))
        v["kit_endpoints"] = set(t.get("kit_endpoints", []))
        v["url_param_schema"] = {t["url_param_schema"]} if t.get("url_param_schema") else set()
        v["path_shape"] = set(t.get("path_shapes", []))
        v["entry_path_template"] = {t["entry_path_template"]} if t.get("entry_path_template") not in (None, "", "/") else set()
        v["third_party"] = set(t.get("third_party", []))
        doms_all = inf.get("domains", [])
        lh = la.get("host")
        land_d = [d for d in doms_all if d.get("fqdn") == lh] or doms_all[:1]
        doms = land_d + [d for d in doms_all if d not in land_d]          # landing domain first
        v["etld1"] = {d["etld1"] for d in land_d if d.get("etld1")}         # campaign-level: the entry landing domain
        v["chain_etld1"] = {d["etld1"] for d in doms[len(land_d):] if d.get("etld1")} | v["etld1"]   # funnel/tracker hosts: operator-level
        v["fqdn"] = {d["fqdn"] for d in doms if d.get("fqdn")}
        v["origin_ip"] = set(inf.get("origin_ips", []))
        v["cert"] = [d["cert"] for d in doms if d.get("cert")]
        enr = [d.get("enrich") or {} for d in doms[:1]]       # landing domain only
        v["ns_pair"] = {"|".join(e["ns"]) for e in enr if e.get("ns")}
        v["reg"] = [(e.get("registrar"), e.get("created")) for e in enr if e.get("registrar") and e.get("created")]
        v["ct_certs"] = [(c.get("issuer"), c.get("not_before")) for e in enr for c in (e.get("certs") or [])]
        land = doms[0] if doms else None
        v["domain_dna"] = _domain_dna(land["fqdn"]) if land else None
        content_ok = la.get("page_role") != "error"
        ht = (c.get("headline_template") or "").strip()
        v["headline_template"] = {ht.lower()} if content_ok and ht.lower() not in GENERIC_TEMPLATES and len(ht) > 12 else set()
        h1 = (c.get("h1_template") or "").strip()
        v["h1_template"] = {h1.lower()} if content_ok and len(h1) > 12 else set()
        v["persons"] = set(c.get("persons", []))
        v["comment_names"] = set(c.get("comment_names", []))
        v["brand_asset"] = set(t.get("brand_asset_hashes", []))
        v["brands"] = set(c.get("brands", []))
        v["products"] = set(c.get("products", []))
        v["vertical"] = c.get("vertical") if content_ok and c.get("vertical") not in (None, "other") else None
        v["lang"] = c.get("lang") if content_ok and c.get("lang") not in (None, "unk") else None
        # L0: identical full entry URL with a high-entropy visit/click id = the same visit captured twice
        eu = la.get("entry_url") or ""
        v["entry_url"] = {eu} if eu and re.search(r"(utm_visit|clickid|fbclid|gclid|key|token)=[^&]{12,}", eu) else set()
        an = c.get("ad_name")
        v["ad_name_grammar"] = {re.sub(r"[^/|()\[\]+ ]+", "x", an)} if an else set()
        text = (la.get("text") or "") if content_ok else ""
        toks = re.findall(r"\w+", text.lower())
        v["text_mh"] = minhash_of(_shingles(toks, 5)) if len(toks) >= 30 else None
        dom = la.get("dom_paths") or []
        v["dom_mh"] = minhash_of(set(dom) | {f"cls:{x}" for x in la.get("css_classes", [])}) if len(dom) >= 30 else None
        # ad layer (optional, from OCR/VLM)
        v["advertiser"] = {ad["advertiser"].strip().lower()} if ad.get("advertiser") else set()
        adt = re.sub(r"^(pl|en|de)\s+|\bsponsorowane\b|\bwięcej\b|\.\.\.", " ", (ad.get("text") or "").strip().lower()).strip()
        v["ad_text"] = {re.sub(r"\W+", " ", adt)[:80].strip()} if len(adt) > 25 else set()
        v["creative_phash"] = ad.get("creative_phash")
        v["ad_persons"] = set(ad.get("persons", []))
        v["face_identity"] = {f["identity"] for f in (inc.get("media", {}).get("faces") or []) if f.get("identity")}
        # video / ASR layer (TROP): spoken + on-screen text, voice cluster, domains named in the video
        med = inc.get("media") or {}
        gem = ((med.get("video") or {}).get("gemini") or {})
        mtext = " ".join([med.get("asr_text") or gem.get("transcript") or ""] + [str(x) for x in (gem.get("on_screen_text") or [])])
        mtoks = re.findall(r"\w+", mtext.lower())
        v["media_mh"] = minhash_of(_shingles(mtoks, 5)) if len(mtoks) >= 30 else None
        v["voice_id"] = {med["voice_id"]} if med.get("voice_id") else set()
        v["video_domains"] = set((inc.get("content") or {}).get("video_domains") or [])
        inc["_v"] = v


def _domain_dna(fqdn: str):
    lab = fqdn.split(".")[0] if fqdn.count(".") <= 1 else fqdn.split(".")[-2]
    tld = fqdn.rsplit(".", 1)[-1]
    shape = ("dash" if "-" in lab else "nodash", "digit" if re.search(r"\d", lab) else "nodigit", len(lab) // 3)
    return (tld, shape)


def doc_freq(incs: list[dict]) -> dict:
    df = defaultdict(Counter)
    for inc in incs:
        for k, val in inc["_v"].items():
            if isinstance(val, set):
                for x in val:
                    df[k][x] += 1
    return df


def rarity(ftype: str, value, df: dict, n: int) -> float:
    d = df[ftype].get(value, 2)
    if ftype in IDENTIFIER_TYPES:
        return 1.0
    if n <= 2:
        return 1.0
    return max(0.0, min(1.0, math.log((n + 1) / d) / math.log((n + 1) / 2)))


def pair_evidence(a: dict, b: dict, df: dict, n: int) -> tuple[list[dict], dict]:
    """Return (evidence list, summary). Evidence item: {type, layer, value, weight}."""
    va, vb = a["_v"], b["_v"]
    ev = []

    def add(ftype, value, w, raw=None):
        if ftype in DISABLED or w == 0:
            return
        item = {"type": ftype, "layer": LAYER.get(ftype, "neg"), "value": value, "weight": round(w, 3)}
        if raw is not None:      # TROP port: provenance for explanations (never used in scoring)
            item["raw"] = raw
        ev.append(item)

    # exact set-overlap types
    for ftype in ("fb_pixel", "capi_gateway", "google_ads", "ga4", "gtm", "tiktok_pixel", "kit_tenant", "lander_id",
                  "landing_type_id", "video_host", "etld1", "ns_pair", "entry_url", "headline_template", "h1_template", "products",
                  "url_param_schema", "entry_path_template", "ad_name_grammar", "advertiser", "ad_text", "face_identity", "path_shape"):
        shared = va[ftype] & vb[ftype]
        if shared:
            best = max(shared, key=lambda x: rarity(ftype, x, df, n))
            add(ftype, str(best)[:120], STRENGTH[ftype] * rarity(ftype, best, df, n), raw=[best])
    if not (va["etld1"] & vb["etld1"]) and (va["chain_etld1"] & vb["chain_etld1"]):
        shared = va["chain_etld1"] & vb["chain_etld1"]
        add("chain_etld1", sorted(shared)[0], STRENGTH["chain_etld1"], raw=sorted(shared))
    # weighted-overlap types (sum of rarities, capped)
    for ftype, cap in (("asset_hash", 2.0), ("third_party", 1.5), ("kit_endpoints", 1.0), ("persons", 1.5),
                       ("brands", 1.0), ("origin_ip", 1.0), ("ad_persons", 1.0),
                       ("comment_names", 1.5), ("brand_asset", 1.0)):
        shared = va[ftype] & vb[ftype]
        if shared:
            r = sum(rarity(ftype, x, df, n) for x in shared)
            denom = max(1, min(len(va[ftype]), len(vb[ftype])))
            frac = len(shared) / denom
            w = STRENGTH[ftype] * min(cap, r) * (0.5 + 0.5 * frac) / cap
            add(ftype, f"{len(shared)} shared (e.g. {sorted(shared)[0][:40]})", w, raw=sorted(shared))
    # similarity types
    if va["text_mh"] is not None and vb["text_mh"] is not None:
        j = va["text_mh"].jaccard(vb["text_mh"])
        if j >= 0.15:
            add("text_minhash", f"jaccard={j:.2f}", STRENGTH["text_minhash"] * min(1.0, (j - 0.15) / 0.55))
    if va["dom_mh"] is not None and vb["dom_mh"] is not None:
        j = va["dom_mh"].jaccard(vb["dom_mh"])
        if j >= 0.5:
            add("dom_minhash", f"jaccard={j:.2f}", STRENGTH["dom_minhash"] * min(1.0, (j - 0.5) / 0.4))
    if va.get("creative_phash") and vb.get("creative_phash"):
        hd = _hamming(va["creative_phash"], vb["creative_phash"])
        if hd <= 14:
            add("creative_phash", f"hamming={hd}", STRENGTH["creative_phash"] * (1 - hd / 15))
    # certificate batch
    for ca in va["cert"]:
        for cb in vb["cert"]:
            if ca.get("issuer") == cb.get("issuer") and _hours_apart(ca.get("not_before"), cb.get("not_before")) <= 2:
                add("cert_batch", f"{ca.get('issuer')} within 2h", STRENGTH["cert_batch"])
    for (ra, ca_) in va["reg"]:
        for (rb, cb_) in vb["reg"]:
            if _norm_reg(ra) == _norm_reg(rb) and _iso_hours(ca_, cb_) <= 2:
                add("registrar_batch", f"{_norm_reg(ra)} created {_iso_hours(ca_, cb_)*60:.0f} min apart", STRENGTH["registrar_batch"])
    ct_hit = None
    for (ia, ta) in va["ct_certs"]:
        for (ib, tb) in vb["ct_certs"]:
            if ia == ib and "let's encrypt" in (ia or "").lower() and _iso_hours(ta, tb) <= 1:
                ct_hit = f"{(ia or '')[-12:]} issued {_iso_hours(ta, tb)*60:.0f} min apart"
    if ct_hit and not any(e["type"] == "cert_batch" for e in ev):
        add("cert_batch", ct_hit, STRENGTH["cert_batch"])
    if va["domain_dna"] and vb["domain_dna"] and va["domain_dna"] == vb["domain_dna"]:
        add("domain_dna", str(va["domain_dna"]), STRENGTH["domain_dna"])
    if va["vertical"] and vb["vertical"] and va["vertical"] == vb["vertical"]:
        add("vertical", va["vertical"], STRENGTH["vertical"])
    # video / ASR (TROP): transcript MinHash vs the other side's transcript or landing text; voice; named domains
    if va.get("media_mh") is not None or vb.get("media_mh") is not None:
        best_j = 0.0
        for x, y in ((va.get("media_mh"), vb.get("media_mh")), (va.get("media_mh"), vb["text_mh"]), (va["text_mh"], vb.get("media_mh"))):
            if x is not None and y is not None:
                best_j = max(best_j, x.jaccard(y))
        if best_j >= 0.15:
            add("media_text", f"jaccard={best_j:.2f}", STRENGTH["media_text"] * min(1.0, (best_j - 0.15) / 0.55))
    shared_v = va.get("voice_id", set()) & vb.get("voice_id", set())
    if shared_v:
        best = max(shared_v, key=lambda x: rarity("voice_id", x, df, n))
        add("voice_id", best, STRENGTH["voice_id"] * rarity("voice_id", best, df, n), raw=[best])
    vd = (va.get("video_domains", set()) & (vb["chain_etld1"] | vb.get("video_domains", set()))) | \
         (vb.get("video_domains", set()) & va["chain_etld1"])
    if vd and not (va["etld1"] & vb["etld1"]) and not any(e["type"] == "chain_etld1" for e in ev):
        add("chain_etld1", sorted(vd)[0], STRENGTH["chain_etld1"], raw=sorted(vd))
    # embeddings (cosine), if present
    for ftype, key, lo in (("text_emb", "text_emb", 0.80), ("shot_emb", "shot_emb", 0.85)):
        ea, eb = a.get("emb", {}).get(key), b.get("emb", {}).get(key)
        if ea is not None and eb is not None:
            cos = float(sum(x * y for x, y in zip(ea, eb)))
            if cos >= lo:
                add(ftype, f"cos={cos:.2f}", STRENGTH[ftype] * min(1.0, (cos - lo) / (1 - lo) * 1.5))
    # negative evidence (only high-strength, both present, conflicting)
    if "neg" not in DISABLED:
        if va["kit_tenant"] and vb["kit_tenant"] and not (va["kit_tenant"] & vb["kit_tenant"]):
            add("kit_tenant_conflict", f"{sorted(va['kit_tenant'])[0][:8]} != {sorted(vb['kit_tenant'])[0][:8]}", NEG["kit_tenant_conflict"])
        if va["lang"] and vb["lang"] and va["lang"] != vb["lang"]:
            add("lang_conflict", f"{va['lang']} != {vb['lang']}", NEG["lang_conflict"])
        if va["vertical"] and vb["vertical"] and va["vertical"] != vb["vertical"]:
            add("vertical_conflict", f"{va['vertical']} != {vb['vertical']}", NEG["vertical_conflict"])

    pos = [e for e in ev if e["weight"] > 0]
    layers = {e["layer"] for e in pos if e["weight"] >= 0.5}
    both_high = [f for f in HIGH if (va.get(f) if not isinstance(va.get(f), set) else len(va[f])) and (vb.get(f) if not isinstance(vb.get(f), set) else len(vb[f]))]
    s_op = sum(e["weight"] for e in ev)
    s_camp = sum(e["weight"] for e in ev if e["type"] not in OPERATOR_ONLY)
    content_agree = sum(e["weight"] for e in ev if e["weight"] > 0 and e["layer"] in ("content", "ad", "persons", "visual")
                        and e["type"] not in ("vertical",))
    op_only = sum(e["weight"] for e in ev if e["type"] in OPERATOR_ONLY and e["weight"] > 0)
    if CONJUNCTION and content_agree >= 2.5:
        s_camp += min(op_only, 4.0)
    summary = {
        "score": round(s_camp if LEVEL == "campaign" else s_op, 3),
        "score_campaign": round(s_camp, 3), "score_operator": round(s_op, 3),
        "pos": round(sum(e["weight"] for e in pos), 3),
        "max_item": max((e["weight"] for e in pos), default=0.0),
        "n_layers": len(layers),
        "coverage": round(len(both_high) / len(HIGH), 3),
        "has_high": any(e["type"] in HIGH and e["weight"] >= 4.0 for e in pos),
    }
    return ev, summary


def _norm_reg(r: str | None) -> str:
    return re.sub(r"[^a-z]", "", (r or "").lower().replace("inc", "").replace("llc", "").replace("limited", ""))[:10]


def _iso_hours(a, b) -> float:
    from datetime import datetime
    try:
        fa = datetime.fromisoformat(str(a).replace("Z", "+00:00")[:19])
        fb = datetime.fromisoformat(str(b).replace("Z", "+00:00")[:19])
        return abs((fa - fb).total_seconds()) / 3600
    except Exception:  # noqa: BLE001
        return 1e9


def _hamming(h1: str, h2: str) -> int:
    return bin(int(h1, 16) ^ int(h2, 16)).count("1")


def _hours_apart(a, b) -> float:
    from datetime import datetime
    try:
        fa = datetime.strptime(re.sub(r"\s+", " ", a), "%b %d %H:%M:%S %Y GMT")
        fb = datetime.strptime(re.sub(r"\s+", " ", b), "%b %d %H:%M:%S %Y GMT")
        return abs((fa - fb).total_seconds()) / 3600
    except Exception:  # noqa: BLE001
        return 1e9


def all_pairs(incs: list[dict]) -> dict:
    prepare(incs)
    df = doc_freq(incs)
    n = len(incs)
    out = {}
    for i, j in combinations(range(n), 2):
        out[(i, j)] = pair_evidence(incs[i], incs[j], df, n)
    return out


FEATURE_ORDER = sorted(set(STRENGTH) | set(NEG))


def pair_vector(ev: list[dict], summary: dict) -> list[float]:
    d = defaultdict(float)
    for e in ev:
        d[e["type"]] += e["weight"]
    return [d[f] for f in FEATURE_ORDER] + [summary["n_layers"], summary["coverage"]]


VECTOR_NAMES = FEATURE_ORDER + ["n_layers", "coverage"]
