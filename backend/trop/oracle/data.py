"""Oracle training data: known campaign domains (kit A) from the DB (read-only) + data/experiments incidents, with timing.

Record: {"domain", "tld", "sld", "source", "created", "registrar", "ns": [...], "issuer", "cert_time", "first_seen", "ips"}
Cached to <data_dir>/oracle/training.json so the Oracle (and its tests/demo) work without the DB.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trop.config import settings
from trop.enrich import cache, crtsh, urlscan
from trop.enrich.util import etld1, parse_ts, tld

KIT_A_TENANT = "f141c307"          # RESULTS §0.7: tenant f141c307… = operator account A


def oracle_dir() -> Path:
    p = Path(settings.data_dir) / "oracle"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _split(d: str) -> tuple[str, str]:
    e = etld1(d)
    t = tld(d)
    return (e[: -(len(t) + 1)] if t and e.endswith("." + t) else e), t


def _from_db() -> list[dict]:
    import psycopg
    out: dict[str, dict] = {}
    with psycopg.connect(settings.database_url, connect_timeout=5) as c:
        c.read_only = True
        rows = c.execute("""
            SELECT DISTINCT ON (oc.etld1) oc.etld1, oc.seen_at, oc.features, d.registrar, d.created_at, d.nameservers
            FROM oracle_candidates oc LEFT JOIN obs_domains d ON d.etld1 = oc.etld1
            WHERE oc.source = 'urlscan' ORDER BY oc.etld1, oc.seen_at""").fetchall()
        for dom, seen, feats, reg, created, ns in rows:
            sld, t = _split(dom)
            out[dom] = {"domain": dom, "tld": t, "sld": sld, "source": "urlscan_pivot", "created": created.isoformat() if created else None,
                        "registrar": reg, "ns": sorted(ns or []), "issuer": (feats or {}).get("tls_issuer"),
                        "first_seen": seen.isoformat(), "ips": (feats or {}).get("ips", []), "cert_time": None}
    return list(out.values())


def _from_experiments() -> list[dict]:
    out = []
    for p in sorted((Path(settings.data_dir) / "experiments").glob("*/incidents.json")):
        try:
            incs = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for i in incs:
            tenants = (i.get("tracking") or {}).get("kit_tenants", [])
            if not any(KIT_A_TENANT in t for t in tenants):
                continue
            dom = (i.get("landing") or {}).get("etld1")
            if not dom:
                continue
            sld, t = _split(dom)
            en = ((i.get("infra") or {}).get("domains") or [{}])[0].get("enrich") or {}
            certs = sorted(c["not_before"] for c in en.get("certs", []) if c.get("not_before"))
            out.append({"domain": dom, "tld": t, "sld": sld, "source": "organizer_kit_a", "created": en.get("created"),
                        "registrar": en.get("registrar"), "ns": en.get("ns", []), "issuer": (en.get("certs") or [{}])[0].get("issuer"),
                        "cert_time": certs[0] if certs else None,
                        "first_seen": (i.get("source") or {}).get("captured_at"), "first_activity_source": "ad_screenshot", "ips": []})
    return out


def load_training(refresh: bool = False) -> list[dict]:
    p = oracle_dir() / "training.json"
    if p.is_file() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    recs: dict[str, dict] = {}
    try:
        for r in _from_db():
            recs[r["domain"]] = r
    except Exception as e:      # DB down: use what is cached or the experiments only
        print(f"oracle: DB unavailable ({type(e).__name__}); using experiments only")
    for r in _from_experiments():
        cur = recs.get(r["domain"])
        if cur is None:
            recs[r["domain"]] = r
        else:                                   # organizer record is richer (ad time, certs): prefer its values
            cur.update({k: v for k, v in r.items() if v})
            cur["source"] = "organizer_kit_a"
    out = sorted(recs.values(), key=lambda r: r["domain"])
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def add_timing(recs: list[dict], progress=None) -> list[dict]:
    """Fill `cert_time` (earliest cert notBefore <= first activity) and `first_seen` (first urlscan sighting) using urlscan
    history (cached; third-party only) and crt.sh/RDAP caches. Records without any evidence keep None."""
    n = 0
    for r in recs:
        n += 1
        h = urlscan.domain_history(r["domain"])
        times = sorted(x for x in [h.get("first")] if x)
        if r.get("source") == "urlscan_pivot" and times:
            r["first_seen"] = times[0]
            r["first_activity_source"] = "urlscan_first_scan"
        valid = sorted(v for v in h.get("tls_valid_from", []) if v)
        if valid and not r.get("cert_time"):
            fs = parse_ts(r.get("first_seen"))
            ok = [v for v in valid if not fs or (parse_ts(v) and parse_ts(v) <= fs)]
            r["cert_time"] = (ok or valid)[0]
        if not r.get("cert_time"):
            cs = crtsh.certs(r["domain"])
            if cs:
                r["cert_time"] = cs[0]["not_before"]
        if progress and n % 20 == 0:
            progress(f"  timing {n}/{len(recs)}")
    return recs


def save_training(recs: list[dict]) -> None:
    (oracle_dir() / "training.json").write_text(json.dumps(recs, ensure_ascii=False, indent=1), encoding="utf-8")


def load_negatives(n_certpl: int = 3000, seed: int = 7) -> list[dict]:
    """Negative pool: (a) other scams = CERT PL warning list (PL-targeted phishing, different grammar), (b) benign popular
    domains (urlscan umbrellaRank). Cached; offline-safe (empty when no sources are cached)."""
    import random
    p = oracle_dir() / "negatives.json"
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    from trop.enrich import certpl
    out: list[dict] = []
    lst = certpl.load()
    doms = sorted(k for k, v in lst.items() if not v[1])
    random.Random(seed).shuffle(doms)
    for d in doms[:n_certpl]:
        sld, t = _split(d)
        out.append({"domain": etld1(d), "sld": sld, "tld": t, "kind": "other_scam"})
    for q in ("page.umbrellaRank:[1 TO 100000] AND page.country:PL", "page.umbrellaRank:[1 TO 50000]", "page.umbrellaRank:[1 TO 20000] AND page.tld:com"):
        for s in urlscan.search(q, 100).get("results", []):
            d = s.get("apex") or etld1(s.get("domain") or "")
            if d:
                sld, t = _split(d)
                out.append({"domain": d, "sld": sld, "tld": t, "kind": "benign"})
    seen, uniq = set(), []
    for r in out:
        if r["domain"] not in seen:
            seen.add(r["domain"])
            uniq.append(r)
    p.write_text(json.dumps(uniq, ensure_ascii=False), encoding="utf-8")
    return uniq
