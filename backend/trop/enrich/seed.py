"""Pre-seed the enrichment cache from the experiment runs (data/experiments/*/infra_enrich.json) so a judge machine
without network replays the same DNS / RDAP / crt.sh / ASN answers."""
from __future__ import annotations

from pathlib import Path

import json

from trop.config import settings

from . import cache


def _ok(v) -> bool:
    return isinstance(v, str) and not v.startswith("ERR")


def seed_from_file(p: Path) -> dict:
    data = json.loads(p.read_text(encoding="utf-8"))
    n = {"domains": 0, "dns": 0, "rdap": 0, "crtsh": 0, "asn": 0}
    for d, e in data.items():
        n["domains"] += 1
        rec = {"name": d}
        for t in ("A", "AAAA", "NS", "MX", "TXT"):
            rec[t] = [x.rstrip(".").lower() if t == "NS" else x for x in e.get(t, []) if _ok(x)]
        if not any(rec[t] for t in ("A", "AAAA", "NS")) and all(x.startswith("ERR:NXDOMAIN") for x in e.get("A", [])):
            rec["nxdomain"] = True
        cache.put("dns", f"all:{d}", cache.Result("ok", rec), seeded=True, seeded_from=p.parent.name)
        n["dns"] += 1
        for ip, a in (e.get("asn") or {}).items():
            if a.get("asn"):
                cache.put("dns", f"asn:{ip}", cache.Result("ok", a), seeded=True)
                n["asn"] += 1
        r = e.get("rdap") or {}
        if r.get("status_code") == 200:
            cache.put("rdap", f"domain:{d}", cache.Result("ok", {
                "registrar": r.get("registrar"), "registrar_iana_id": None, "created": r.get("created"),
                "expires": r.get("expires"), "updated": r.get("updated"), "ns": r.get("ns", []),
                "status": r.get("status", [])}), seeded=True)
            n["rdap"] += 1
        cr = e.get("crtsh")
        if isinstance(cr, list) and not (cr and "err" in cr[0]):
            certs = [{"issuer": c.get("issuer"), "issuer_name": c.get("issuer"), "not_before": c.get("not_before"),
                      "names": c.get("names", []), "id": c.get("id"), "entry_ts": None} for c in cr if c.get("not_before")]
            cache.put("crtsh", f"q:{d}", cache.Result("ok", certs), seeded=True)
            n["crtsh"] += 1
    return n


def seed_all(root: Path | None = None) -> dict:
    root = Path(root or Path(settings.data_dir) / "experiments")
    tot: dict = {"files": 0}
    for p in sorted(root.glob("*/infra_enrich.json")):
        r = seed_from_file(p)
        tot["files"] += 1
        for k, v in r.items():
            tot[k] = tot.get(k, 0) + v
    return tot


def seed_from_db() -> dict:
    """Seed the FS cache from the dev DB's enrichment_cache (read-only): dns / rdap / crt.sh rows of the Hunter prototype."""
    import psycopg

    from .crtsh import _norm_crtsh
    from .rdap import _norm as _norm_rdap
    n = {"dns": 0, "rdap": 0, "crtsh": 0}
    with psycopg.connect(settings.database_url, connect_timeout=5) as c:
        c.read_only = True
        for prov, key, resp in c.execute("SELECT provider, key, response FROM enrichment_cache WHERE status = 'ok' AND provider IN ('dns','rdap','crtsh')"):
            if prov == "dns" and key.startswith("all:") and isinstance(resp, dict):
                rec = {t: [x.rstrip(".") if t == "NS" else x for x in resp.get(t, [])] for t in ("A", "AAAA", "NS", "MX", "TXT")}
                cache.put("dns", key, cache.Result("ok", {"name": key[4:], **rec}), seeded=True)
            elif prov == "rdap" and key.startswith("domain:") and isinstance(resp, dict) and "events" in resp:
                cache.put("rdap", key, cache.Result("ok", _norm_rdap(resp)), seeded=True)
            elif prov == "crtsh" and key.startswith("q:") and isinstance(resp, list):
                cache.put("crtsh", key.replace("q:%.", "q:"), cache.Result("ok", _norm_crtsh(resp)), seeded=True)
            else:
                continue
            n[prov] += 1
    return n
