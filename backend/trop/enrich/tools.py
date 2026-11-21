"""Plain functions for the White Rabbit agent tools (WS6) and the API: JSON-serialisable results, cached, offline-safe.

    crtsh(domain) · rdap(domain) · dns_ns(domain) · urlscan_search(query) · certpl_check(domain) · wayback(url)
    adlib_search(terms, ...) · capture(url, ...)

Never contact the scam host directly except `capture`, which is budgeted, headless, sandboxed and never submits forms.
"""
from __future__ import annotations

from typing import Any

from . import certpl as _certpl
from . import crtsh as _crtsh
from . import dns as _dns
from . import rdap as _rdap
from . import urlscan as _urlscan
from . import wayback as _wayback
from .enrich import enrich_domain  # noqa: F401  (re-exported)


def crtsh(domain: str, subdomains: bool = False) -> dict[str, Any]:
    """Certificates (crt.sh, Cert Spotter fallback) for a domain."""
    cs = _crtsh.certs(domain, subdomains)
    return {"domain": domain, "count": len(cs), "certs": cs[:40],
            "first_not_before": cs[0]["not_before"] if cs else None,
            "issuers": sorted({c["issuer"] for c in cs})}


def rdap(domain: str) -> dict[str, Any]:
    """RDAP registration data: registrar, created/expires, nameservers."""
    return _rdap.lookup(domain)


def dns_ns(domain: str) -> dict[str, Any]:
    """DNS from public resolvers: NS pair, A records, ASN of the A records."""
    rec = _dns.records(_etld1(domain))
    ips = [x for x in rec.get("A", [])]
    return {"domain": _etld1(domain), "ns": _dns.ns_of(domain), "a": ips, "aaaa": rec.get("AAAA", []),
            "mx": rec.get("MX", []), "asn": {ip: _dns.asn_of(ip) for ip in ips[:5]}, "nxdomain": bool(rec.get("nxdomain"))}


def urlscan_search(query: str, size: int = 50) -> dict[str, Any]:
    """urlscan.io search (search only; e.g. 'page.domain:x', 'hash:<sha256>', 'page.ip:"1.2.3.4"')."""
    d = _urlscan.search(query, size)
    return {"query": query, "total": d.get("total"), "results": d.get("results", [])[:size], "error": d.get("error")}


def certpl_check(domain: str) -> dict[str, Any]:
    """Is the domain on the CERT Polska warning list (hole.cert.pl)?"""
    return {"domain": domain, **_certpl.check(domain)}


def wayback(url: str, limit: int = 10) -> dict[str, Any]:
    """Internet Archive snapshots of a URL/domain."""
    return _wayback.snapshots(url, limit)


def adlib_search(terms: str, countries: str = "PL", limit: int = 25, active: str = "ACTIVE",
                 page_ids: str | None = None) -> dict[str, Any]:
    """Meta Ad Library (ads_archive) search. Returns compact ad rows (no tokens)."""
    from trop.hunter import meta
    return meta.adlib_search(terms, countries=countries, limit=limit, active=active, page_ids=page_ids)


def capture(url: str, profile: str = "fb_inapp_android_pl", docker: bool = True) -> dict[str, Any]:
    """Budgeted headless capture of a landing page in the sandbox; returns the bundle path + summary."""
    from trop.capture import cli as _cap
    return _cap.capture_url(url, profile=profile, docker=docker)


def _etld1(x: str) -> str:
    from .util import etld1
    return etld1(x)


TOOLS = {f.__name__: f for f in (crtsh, rdap, dns_ns, urlscan_search, certpl_check, wayback, adlib_search, capture)}
