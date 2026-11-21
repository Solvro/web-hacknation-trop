"""RDAP domain lookup (IANA bootstrap; rdap.org as fallback). No WHOIS port 43."""
from __future__ import annotations

from . import cache
from .util import etld1


def _bootstrap() -> dict[str, str]:
    res = cache.fetch_json("rdap", "bootstrap:dns", "https://data.iana.org/rdap/dns.json")
    table: dict[str, str] = {}
    if res.status == "ok" and isinstance(res.data, dict):
        for tlds, urls in res.data.get("services", []):
            base = next((u for u in urls if u.startswith("https://")), urls[0])
            for t in tlds:
                table[t.lower()] = base if base.endswith("/") else base + "/"
    return table


def _norm(d: dict) -> dict:
    ev = {e.get("eventAction"): e.get("eventDate") for e in d.get("events", [])}
    reg = next((e for e in d.get("entities", []) if "registrar" in (e.get("roles") or [])), {})
    name = next((v[3] for v in (reg.get("vcardArray") or [None, []])[1] if v and v[0] == "fn"), None) if reg else None
    iana = None
    for pid in (reg.get("publicIds") or []):
        if "IANA" in pid.get("type", "") and str(pid.get("identifier", "")).isdigit():
            iana = int(pid["identifier"])
    return {"registrar": name or reg.get("handle"), "registrar_iana_id": iana, "created": ev.get("registration"),
            "expires": ev.get("expiration"), "updated": ev.get("last changed"),
            "ns": sorted({(n.get("ldhName") or "").lower().rstrip(".") for n in d.get("nameservers", []) if n.get("ldhName")}),
            "status": d.get("status", [])}


def lookup(domain: str) -> dict:
    d = etld1(domain)
    last = d.rsplit(".", 1)[-1]
    hit = cache.get("rdap", f"domain:{d}")
    if hit is None and not cache.is_offline():
        base = _bootstrap().get(last)
        url = f"{base}domain/{d}" if base else f"https://rdap.org/domain/{d}"
        res = cache.fetch_json("rdap", f"domain:{d}", url, headers={"Accept": "application/rdap+json"}, parse=_norm)
    else:
        res = hit or cache.Result("offline")
    if res.status != "ok":
        return {"domain": d, "status": res.status, "error": res.error}
    return {"domain": d, "status": "ok", **res.data}
