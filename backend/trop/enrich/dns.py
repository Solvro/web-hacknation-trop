"""DNS (public recursive resolvers) + IP->ASN (Team Cymru DNS; IPinfo Lite when a token is set).

Only resolvers / registries are contacted, never the scam host. Cached as dns/all:<name> and dns/asn:<ip>.
"""
from __future__ import annotations

import dns.exception
import dns.resolver
import dns.reversename

from trop.config import settings

from . import cache
from .util import etld1

CF_DEAD = {"ns1.dyna-ns.net", "ns2.dyna-ns.net", "ns1.dns-expired.com", "ns2.dns-expired.com"}   # parked: not operator evidence


def _resolver() -> dns.resolver.Resolver:
    r = dns.resolver.Resolver(configure=False)
    r.nameservers = ["1.1.1.1", "8.8.8.8"]
    r.lifetime, r.timeout = 6.0, 3.0
    return r


def _q(name: str, rtype: str) -> tuple[str, list[str]]:
    try:
        return "ok", sorted(a.to_text().rstrip(".").lower() if rtype in ("NS", "CNAME") else a.to_text()
                            for a in _resolver().resolve(name, rtype))
    except dns.resolver.NXDOMAIN:
        return "nxdomain", []
    except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return "noanswer", []
    except dns.exception.DNSException:
        return "timeout", []


def records(name: str) -> dict:
    """{A, AAAA, NS, MX, TXT, nxdomain?}. NS is looked up on the registrable domain."""
    name = name.lower().strip(".")
    hit = cache.get("dns", f"all:{name}")
    if hit is not None and hit.data is not None:
        return hit.data
    if cache.is_offline():
        return {"offline": True}
    out: dict = {"name": name}
    for rtype in ("A", "AAAA", "NS", "MX", "TXT"):
        st, vals = _q(name, rtype)
        out[rtype] = vals[:5] if rtype == "TXT" else vals
        if st == "nxdomain":
            out["nxdomain"] = True
            break
    cache.put("dns", f"all:{name}", cache.Result("ok", out))
    return out


def ns_of(domain: str) -> list[str]:
    ns = records(etld1(domain)).get("NS", [])
    return [] if set(ns) & CF_DEAD else ns


def asn_of(ip: str) -> dict:
    hit = cache.get("dns", f"asn:{ip}")
    if hit is not None:
        return hit.data or {}
    if cache.is_offline() or ":" in ip:
        return {}
    data: dict = {}
    try:
        rev = ".".join(reversed(ip.split(".")))
        _, txt = _q(f"{rev}.origin.asn.cymru.com", "TXT")
        if txt:
            parts = [p.strip().strip('"') for p in txt[0].strip('"').split("|")]
            asn = parts[0].split()[0]
            _, t2 = _q(f"AS{asn}.asn.cymru.com", "TXT")
            data = {"asn": asn, "prefix": parts[1], "cc": parts[2],
                    "name": t2[0].strip('"').split("|")[-1].strip() if t2 else None}
    except (IndexError, ValueError):
        data = {}
    cache.put("dns", f"asn:{ip}", cache.Result("ok" if data else "not_found", data))
    return data


def ipinfo(ip: str) -> dict:
    """IPinfo Lite (free with token; attribution CC BY-SA 4.0)."""
    if not settings.ipinfo_token:
        return asn_of(ip) | {"source": "cymru"}
    res = cache.fetch_json("ipinfo", f"lite:{ip}", f"https://api.ipinfo.io/lite/{ip}", params={"token": settings.ipinfo_token})
    if res.status != "ok":
        return {"error": res.error or res.status}
    d = res.data
    return {"asn": str(d.get("asn", "")).upper().replace("AS", ""), "name": d.get("as_name"), "as_domain": d.get("as_domain"),
            "cc": d.get("country_code"), "source": "ipinfo"}
