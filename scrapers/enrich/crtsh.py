"""crt.sh Certificate Transparency lookup → obs_certs, cert / cert_batch observables, cert_covers relations.

    python -m scrapers.enrich.crtsh example.com [--subdomains]

crt.sh JSON: [{id, issuer_name, common_name, name_value (SANs, \n-separated), serial_number, not_before,
not_after, entry_timestamp}]. Precert + final cert share (issuer, serial) → one 'cert' observable.
Limits: ~5 req/min/IP and frequent 502/timeouts → 60 s timeout, negative caching, Cert Spotter fallback.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

from ..ingest.model import ObsHit, RelationDraft
from ..store import artifacts
from ..store.db import Loader, connect
from .http import CachedClient

CN_RE = re.compile(r"CN=([^,]+)")
O_RE = re.compile(r"O=\"?([^,\"]+)")


def _t(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def lookup(conn, domain: str, subdomains: bool = True) -> list[dict]:
    """-> certificates grouped by (issuer_cn, serial), newest first."""
    q = f"%.{domain}" if subdomains else domain
    res = CachedClient(conn, "crtsh", timeout=60).get_json(f"q:{q}", "https://crt.sh/", params={"q": q, "output": "json"})
    if res.status == "error" or res.status == "rate_limited":
        alt = certspotter(conn, domain, subdomains)
        if alt is not None:
            return alt
    if res.status != "ok" or not isinstance(res.data, list):
        return []
    groups: dict[tuple[str, str], dict] = {}
    for e in res.data:
        icn = (CN_RE.search(e.get("issuer_name", "")) or [None, "?"])[1]
        serial = (e.get("serial_number") or "").lstrip("0").lower()
        if not serial:
            continue
        g = groups.setdefault((icn, serial), {
            "issuer_cn": icn, "issuer_org": (O_RE.search(e.get("issuer_name", "")) or [None, None])[1],
            "serial": serial, "sans": set(), "not_before": _t(e.get("not_before")),
            "not_after": _t(e.get("not_after")), "entry_ts": _t(e.get("entry_timestamp")), "crtsh_ids": []})
        g["sans"].update(x.strip().lower() for x in (e.get("name_value") or "").split("\n") if x.strip())
        if e.get("common_name"):
            g["sans"].add(e["common_name"].strip().lower())
        g["crtsh_ids"].append(e.get("id"))
        ts = _t(e.get("entry_timestamp"))
        if ts and (g["entry_ts"] is None or ts < g["entry_ts"]):
            g["entry_ts"] = ts
    out = sorted(groups.values(), key=lambda g: g["not_before"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    for g in out:
        g["sans"] = sorted(g["sans"])
    return out


def certspotter(conn, domain: str, subdomains: bool) -> list[dict] | None:
    """Fallback: SSLMate Cert Spotter (keyless 100 hostname queries/hour)."""
    params = {"domain": domain, "expand": ["dns_names", "issuer"], "include_subdomains": str(subdomains).lower()}
    res = CachedClient(conn, "certspotter").get_json(f"d:{domain}:{subdomains}", "https://api.certspotter.com/v1/issuances", params=params)
    if res.status != "ok" or not isinstance(res.data, list):
        return None
    out = []
    for e in res.data:
        iss = e.get("issuer") or {}
        icn = (CN_RE.search(iss.get("name", "")) or [None, iss.get("friendly_name") or "?"])[1]
        out.append({"issuer_cn": icn, "issuer_org": None, "serial": None, "sans": sorted(e.get("dns_names") or []),
                    "not_before": _t(e.get("not_before")), "not_after": _t(e.get("not_after")),
                    "entry_ts": None, "crtsh_ids": [], "certspotter_id": e.get("id")})
    return out


def enrich_domain(loader: Loader, domain: str, subdomains: bool = True) -> dict:
    certs = lookup(loader.conn, domain, subdomains)
    n_new_names = set()
    first = None
    for c in certs:
        if not c.get("serial"):
            continue
        cid = f"{c['issuer_cn'].lower()}/{c['serial']}"
        attrs = {"issuer_cn": c["issuer_cn"], "issuer_org": c["issuer_org"], "serial": c["serial"], "sans": c["sans"],
                 "not_before": c["not_before"].strftime("%Y-%m-%dT%H:%M:%S") if c["not_before"] else None,
                 "not_after": c["not_after"].strftime("%Y-%m-%dT%H:%M:%S") if c["not_after"] else None}
        oid = loader.observable_id("cert", cid, attrs=attrs)
        loader.conn.execute("UPDATE obs_certs SET crtsh_id = %s, ct_entry = %s WHERE observable_id = %s",
                            (min(i for i in c["crtsh_ids"] if i) if c["crtsh_ids"] else None,
                             __import__("psycopg").types.json.Jsonb({"entry_ts": str(c["entry_ts"])}), oid))
        win = {"valid_from": c["not_before"], "valid_to": c["not_after"]}
        loader.propagate(domain, "cert", cid, "enrich.crtsh", "crtsh@1", context={"crtsh_ids": c["crtsh_ids"][:5]}, **win)
        if c["not_before"]:
            loader.propagate(domain, "cert_batch", f"{c['issuer_cn'].lower()}|{c['not_before']:%Y-%m-%dT%H}",
                             "enrich.crtsh", "crtsh@1", **win)
            first = min(first, c["not_before"]) if first else c["not_before"]
        for san in c["sans"]:
            name = san.lstrip("*.")
            loader.relate(RelationDraft(("cert", cid), "cert_covers", ("fqdn", name), "crtsh"))
            n_new_names.add(name)
    if first:
        loader.conn.execute(
            "UPDATE obs_domains SET first_cert_at = least(coalesce(first_cert_at, %s), %s) WHERE fqdn = %s OR etld1 = %s",
            (first, first, domain, domain))
    loader.conn.commit()
    return {"domain": domain, "certs": len(certs), "names": len(n_new_names),
            "first_cert": first.isoformat() if first else None,
            "issuers": sorted({c["issuer_cn"] for c in certs})}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("domain")
    ap.add_argument("--exact", action="store_true", help="no subdomains")
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    with connect(args.db) as conn:
        loader = Loader(conn, artifacts.from_env(), sensitivity="public")
        print(enrich_domain(loader, args.domain.lower(), not args.exact))
    return 0


if __name__ == "__main__":
    sys.exit(main())
