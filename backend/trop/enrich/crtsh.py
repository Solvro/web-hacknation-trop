"""Certificate Transparency lookups: crt.sh (primary) with Cert Spotter fallback. Third-party services only.

Normalised cert: {"issuer": issuer_name[-60:] (the form the evidence engine compares), "issuer_name", "not_before",
"names": [...], "id", "entry_ts"}. Sorted by not_before.
Limits: crt.sh ~5 req/min/IP with frequent 502/timeouts (negative-cached); Cert Spotter keyless 100 queries/h.
"""
from __future__ import annotations

from trop.config import settings

from . import cache
from .util import parse_ts


def _norm_crtsh(rows: list[dict]) -> list[dict]:
    out = []
    for c in rows or []:
        if not c.get("not_before"):
            continue
        iss = c.get("issuer_name", "") or ""
        out.append({"issuer": iss[-60:], "issuer_name": iss, "not_before": c.get("not_before"),
                    "names": sorted(set((c.get("name_value") or "").lower().split("\n")))[:10],
                    "id": c.get("id"), "entry_ts": c.get("entry_timestamp")})
    return sorted(out, key=lambda c: c["not_before"] or "")[:60]


def _norm_spotter(rows: list[dict]) -> list[dict]:
    out = []
    for e in rows or []:
        if not e.get("not_before"):
            continue
        iss = (e.get("issuer") or {}).get("name") or (e.get("issuer") or {}).get("friendly_name") or ""
        out.append({"issuer": iss[-60:], "issuer_name": iss, "not_before": e["not_before"].replace("Z", "").split("+")[0],
                    "names": sorted(e.get("dns_names") or [])[:10], "id": e.get("id"), "entry_ts": None,
                    "via": "certspotter"})
    return sorted(out, key=lambda c: c["not_before"])[:60]


def certspotter(domain: str, subdomains: bool = False) -> cache.Result:
    headers = {"Authorization": f"Bearer {settings.certspotter_api_key}"} if settings.certspotter_api_key else None
    return cache.fetch_json(
        "certspotter", f"d:{domain}:{subdomains}", "https://api.certspotter.com/v1/issuances", headers=headers,
        params={"domain": domain, "include_subdomains": str(subdomains).lower(), "expand": ["dns_names", "issuer"]},
        parse=_norm_spotter)


def certs(domain: str, subdomains: bool = False) -> list[dict]:
    """Certificates for `domain` (cached). crt.sh first; Cert Spotter when crt.sh fails / is rate limited."""
    q = f"%.{domain}" if subdomains else domain
    res = cache.fetch_json("crtsh", f"q:{q}", "https://crt.sh/", params={"q": q, "output": "json"}, timeout=60,
                           parse=_norm_crtsh)
    if res.status == "ok" and isinstance(res.data, list):
        return res.data
    if res.status in ("error", "rate_limited"):
        alt = certspotter(domain, subdomains)
        if alt.status == "ok" and isinstance(alt.data, list):
            return alt.data
    return []


def first_cert_time(domain: str):
    cs = certs(domain)
    return parse_ts(cs[0]["not_before"]) if cs else None


def recent_by_pattern(pattern: str, limit: int = 200) -> list[dict]:
    """Newest cert entries whose identity matches a crt.sh pattern (e.g. '%.click'); used by the Oracle poller.
    crt.sh does not cache-hit for such queries well: uncached, time-limited, best effort."""
    res = cache.fetch_json("crtsh", f"recent:{pattern}", "https://crt.sh/",
                           params={"q": pattern, "output": "json", "exclude": "expired", "deduplicate": "Y"},
                           timeout=90, parse=lambda rows: _norm_crtsh(rows)[-limit:])
    return res.data if res.status == "ok" and res.data else []
