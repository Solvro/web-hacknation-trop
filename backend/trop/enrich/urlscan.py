"""urlscan.io SEARCH ONLY (never submits scans: that would make urlscan visit/publish the URL) + public result fetch.

Quotas: anon search 30/min and 30 days; with URLSCAN_API_KEY more history. /result needs a key.
"""
from __future__ import annotations

from trop.config import settings

from . import cache
from .util import etld1

API = "https://urlscan.io/api/v1/search/"


def _headers() -> dict:
    return {"API-Key": settings.urlscan_api_key} if settings.urlscan_api_key else {}


def summarise(r: dict) -> dict:
    t, p = r.get("task", {}), r.get("page", {})
    return {"uuid": t.get("uuid") or r.get("_id"), "time": t.get("time"), "task_url": t.get("url"),
            "task_domain": t.get("domain"), "url": p.get("url"), "domain": (p.get("domain") or "").lower(),
            "apex": (p.get("apexDomain") or "").lower(), "ip": p.get("ip"), "asn": p.get("asn"),
            "asnname": p.get("asnname"), "country": p.get("country"), "server": p.get("server"),
            "title": p.get("title"), "status": p.get("status"), "tls_issuer": p.get("tlsIssuer"),
            "tls_valid_from": p.get("tlsValidFrom"), "domain_age_days": p.get("apexDomainAgeDays") or p.get("domainAgeDays"),
            "umbrella_rank": p.get("umbrellaRank")}


def search(q: str, size: int = 100) -> dict:
    """-> {"results": [summary...], "total", "error"?}. Cached 24 h."""
    res = cache.fetch_json("urlscan", f"search:{size}:{q}", API, params={"q": q, "size": size}, headers=_headers(),
                           parse=lambda d: {"total": d.get("total"), "has_more": d.get("has_more"),
                                            "results": [summarise(r) for r in d.get("results", [])]})
    if res.status != "ok":
        return {"results": [], "total": 0, "error": res.error or res.status}
    return res.data


def classify_pivot(scans: list[dict]) -> tuple[str, dict]:
    """shared_service (many old domains, diverse titles: hosted gateway / SaaS) vs campaign infrastructure."""
    by_apex: dict[str, dict] = {}
    for s in scans:
        d = s.get("apex") or etld1(s.get("domain") or "")
        if d:
            by_apex.setdefault(d, s)
    n = len(by_apex)
    if n == 0:
        return "empty", {"domains": 0}
    ages = [s["domain_age_days"] for s in by_apex.values() if isinstance(s.get("domain_age_days"), int)]
    old_share = sum(a > 365 for a in ages) / len(ages) if ages else 0.0
    titles = [(s.get("title") or "").strip().lower()[:60] for s in by_apex.values() if s.get("title")]
    diversity = len(set(titles)) / len(titles) if titles else 1.0
    stats = {"domains": n, "old_share": round(old_share, 2), "title_diversity": round(diversity, 2)}
    return ("shared_service" if n >= 20 and old_share > 0.5 and diversity > 0.6 else "campaign"), stats


def domain_history(domain: str) -> dict:
    d = etld1(domain)
    data = search(f"domain:{d}")
    sc = data.get("results", [])
    times = sorted(s["time"] for s in sc if s.get("time"))
    return {"domain": d, "scans": len(sc), "total": data.get("total"), "first": times[0] if times else None,
            "last": times[-1] if times else None, "ips": sorted({s["ip"] for s in sc if s.get("ip")})[:10],
            "titles": sorted({(s["title"] or "")[:60] for s in sc if s.get("title")})[:5],
            "tls_issuers": sorted({s["tls_issuer"] for s in sc if s.get("tls_issuer")})[:5],
            "tls_valid_from": sorted({s["tls_valid_from"] for s in sc if s.get("tls_valid_from")})[:5],
            "error": data.get("error")}


def result(uuid: str) -> dict | None:
    """Full public scan result JSON (needs URLSCAN_API_KEY since 2026-05). Cached."""
    res = cache.fetch_json("urlscan", f"result:{uuid}", f"https://urlscan.io/api/v1/result/{uuid}/", headers=_headers())
    return res.data if res.status == "ok" else None
