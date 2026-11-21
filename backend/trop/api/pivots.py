"""Pivots of an analysed incident for White Rabbit: `POST /investigations {seed: "incident:<id>"}`.

White Rabbit (trop.agent) is seeded with ONE domain; everything else we know about the material is handed over as analyst notes
(the same channel as POST /investigations/{id}/steer), so the planner/LLM pivots on all of it within the normal budget cap.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

_DOMAIN_RE = re.compile(r"(?<![\w@.-])((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24})(?![\w-])", re.I)


def _s(x) -> list[str]:
    if x is None or x == "":
        return []
    return [str(i) for i in x if i not in (None, "")] if isinstance(x, (list, tuple, set)) else [str(x)]


def _host(u: str | None) -> str:
    if not u:
        return ""
    u = u.strip()
    try:
        return (urlsplit(u if "//" in u else "//" + u).hostname or "").lower()
    except ValueError:
        return ""


def _usable(d: str) -> bool:
    from trop.agent.tools import _ignored  # same filter the agent applies to candidates (platforms, CDNs, non-domains)
    return bool(d) and not _ignored(d)


def derive(inc: dict) -> dict:
    """-> {domains: [{domain, via}], advertiser, page_id, library_id, kit: {...}, seed, seed_kind}."""
    from trop.agent.tools import _apex
    lan, ad, trk = inc.get("landing") or {}, inc.get("ad") or {}, inc.get("tracking") or {}
    med, con = inc.get("media") or {}, inc.get("content") or {}
    cand: list[tuple[str, str]] = []
    cand.append((_apex(lan.get("etld1") or lan.get("host") or ""), "strona docelowa"))
    for u in _s(lan.get("chain_urls")) + _s(lan.get("redirect_chain")):
        cand.append((_apex(_host(u)), "łańcuch przekierowań"))
    dl = str(ad.get("display_link") or "")
    m = _DOMAIN_RE.search(dl)
    cand.append((_apex(_host(dl) or (m.group(1) if m else "")), "link w reklamie"))
    cta = str(ad.get("cta") or "")
    for m in _DOMAIN_RE.findall(cta):
        cand.append((_apex(m), "CTA reklamy"))
    for d in _s(con.get("video_domains")):
        cand.append((_apex(d), "z nagrania"))
    gem = ((med.get("video") or {}).get("gemini")) or {}
    if gem:
        for m in _DOMAIN_RE.findall(json.dumps(gem, ensure_ascii=False)):
            cand.append((_apex(m), "z nagrania"))
    seen, domains = set(), []
    for d, via in cand:
        if d and d not in seen and _usable(d):
            seen.add(d)
            domains.append({"domain": d, "via": via})
    kit = {"kit_tenants": _s(trk.get("kit_tenants")), "fb_pixels": _s(trk.get("fb_pixels")), "capi_gateways": _s(trk.get("capi_gateways")),
           "google_ads": _s(trk.get("google_ads")), "lander_ids": _s(trk.get("lander_ids"))}
    adv = (ad.get("advertiser") or "").strip() or None
    out = {"domains": domains, "advertiser": adv, "page_id": ad.get("page_id"), "library_id": ad.get("library_id"),
           "kit": {k: v for k, v in kit.items() if v}}
    if domains:
        out["seed"], out["seed_kind"] = domains[0]["domain"], "domain"
    elif adv or out["page_id"]:
        out["seed"], out["seed_kind"] = adv or f"page:{out['page_id']}", "advertiser"
    else:
        out["seed"], out["seed_kind"] = None, "none"
    return out


def hints(p: dict, incident_id: str) -> list[str]:
    """Analyst notes (<= 300 chars each, Polish) passed to White Rabbit as the first steering messages."""
    out: list[str] = []
    rest = [d for d in p["domains"][1:]] if p["seed_kind"] == "domain" else p["domains"]
    if rest:
        out.append(f"Kontekst z materiału {incident_id}: sprawdź też domeny: " + ", ".join(f"{d['domain']} ({d['via']})" for d in rest[:6]) + ".")
    ids = [f"{k}={v[0]}" for k, v in p["kit"].items() if v]
    if ids:
        out.append("Ślady operatora z materiału (użyj db_search / urlscan po rzadkich wartościach): " + "; ".join(ids)[:230] + ".")
    if p["advertiser"] or p["page_id"] or p["library_id"]:
        bits = [f"reklamodawca «{p['advertiser']}»" if p["advertiser"] else None, f"page_id {p['page_id']}" if p["page_id"] else None,
                f"library_id {p['library_id']}" if p["library_id"] else None]
        out.append("Reklama: " + ", ".join(b for b in bits if b) + ". Użyj adlib_search (page_ids / nazwa) i db_search po tej nazwie.")
    if p["seed_kind"] != "domain":
        out.insert(0, "W materiale nie ma żadnej domeny — zacznij od adlib_search po reklamodawcy / page_id oraz db_search; domeny wyciągaj z reklam.")
    return [h[:300] for h in out]
