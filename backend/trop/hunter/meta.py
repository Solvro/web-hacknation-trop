"""Meta Ad Library (`ads_archive`, DSA coverage of all EU-delivered ads) -> IncidentDraft (source.type='hunter').

Token: settings.meta_access_token (never persisted: `ad_snapshot_url` is stored redacted). The API returns no landing
URL: `snapshot.render_snapshots` opens the ad's own render page to read the CTA link, then the landing is captured.
Responses are cached on the FS (source "meta", 1 h) and replay offline.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Iterator

import httpx

from trop.config import settings
from trop.enrich import cache
from trop.schema import AdLayer, Content, IncidentDraft, IncidentSource

from . import gazetteer

cache.SHORT_TTL["meta"] = 3600
GRAPH = "https://graph.facebook.com/v27.0/ads_archive"
FIELDS = ["id", "ad_creation_time", "ad_creative_bodies", "ad_creative_link_captions", "ad_creative_link_descriptions",
          "ad_creative_link_titles", "ad_delivery_start_time", "ad_delivery_stop_time", "ad_snapshot_url", "page_id",
          "page_name", "publisher_platforms", "languages", "eu_total_reach", "target_ages", "target_gender",
          "target_locations", "beneficiary_payers"]


class MetaError(RuntimeError):
    pass


def redact(s):
    return re.sub(r"access_token=[^&\"\s]*", "access_token=REDACTED", s) if isinstance(s, str) else s


def build_params(terms: str | None, countries: list[str], active: str = "ACTIVE", search_type: str = "KEYWORD_UNORDERED",
                 date_min: str | None = None, limit: int = 50, page_ids: list[str] | None = None) -> dict:
    p = {"ad_reached_countries": json.dumps(countries), "ad_active_status": active, "ad_type": "ALL",
         "fields": ",".join(FIELDS), "limit": str(limit)}
    if terms:
        p["search_terms"] = terms[:100]
        p["search_type"] = search_type
    if page_ids:
        p["search_page_ids"] = ",".join(page_ids[:10])
    if date_min:
        p["ad_delivery_date_min"] = date_min
    return p


def _err(r: httpx.Response) -> MetaError:
    try:
        e = r.json().get("error", {})
    except ValueError:
        e = {}
    hint = ""
    if e.get("code") == 190:
        hint = " (token expired/invalid: regenerate META_ACCESS_TOKEN)"
    elif e.get("error_subcode") in (2332002, 2332004) or e.get("code") == 10:
        hint = " (token has no Ad Library API access: identity confirmation / user token needed)"
    elif e.get("code") in (4, 17, 32, 613):
        hint = " (rate limited)"
    return MetaError(f"Graph {r.status_code} code={e.get('code')} sub={e.get('error_subcode')} {e.get('message', r.text[:150])}{hint}")


def fetch(params: dict, max_pages: int = 2, use_cache: bool = True) -> list[dict]:
    """Paged GET; ads returned with a REDACTED snapshot url. Cached by (params, max_pages)."""
    key = hashlib.sha256(json.dumps([params, max_pages], sort_keys=True).encode()).hexdigest()[:24]
    if use_cache:
        hit = cache.get("meta", key)
        if hit is not None and hit.status == "ok":
            return hit.data
    if cache.is_offline():
        return []
    token = settings.meta_access_token
    if not token:
        raise MetaError("META_ACCESS_TOKEN not set")
    ads: list[dict] = []
    url, p = GRAPH, {**params, "access_token": token}
    with httpx.Client(timeout=60) as c:
        for _ in range(max_pages):
            cache.bucket("meta").take()
            r = c.get(url, params=p)
            if r.status_code != 200:
                raise _err(r)
            d = r.json()
            for a in d.get("data", []):
                a["ad_snapshot_url"] = redact(a.get("ad_snapshot_url"))
                ads.append(a)
            nxt = (d.get("paging") or {}).get("next")
            if not nxt:
                break
            url, p = nxt, None
    cache.put("meta", key, cache.Result("ok", ads))
    return ads


cache.RATES["meta"] = 20


def search(terms: str | None, countries: list[str] | None = None, active: str = "ACTIVE", limit: int = 50, max_pages: int = 2,
           date_min: str | None = None, page_ids: list[str] | None = None, search_type: str = "KEYWORD_UNORDERED") -> list[dict]:
    return fetch(build_params(terms, countries or ["PL"], active, search_type, date_min, limit, page_ids), max_pages)


def adlib_search(terms: str, countries: str = "PL", limit: int = 25, active: str = "ACTIVE", page_ids: str | None = None) -> dict[str, Any]:
    """Agent-tool form: compact JSON rows."""
    try:
        ads = search(terms or None, [c.strip() for c in countries.split(",")], active, limit=min(limit, 50), max_pages=1,
                     page_ids=[p.strip() for p in page_ids.split(",")] if page_ids else None)
    except MetaError as e:
        return {"terms": terms, "count": 0, "ads": [], "error": str(e)}
    rows = [{"id": a["id"], "page_id": a.get("page_id"), "page_name": a.get("page_name"),
             "body": ((a.get("ad_creative_bodies") or [""])[0] or "")[:300],
             "title": (a.get("ad_creative_link_titles") or [None])[0], "caption": (a.get("ad_creative_link_captions") or [None])[0],
             "start": a.get("ad_delivery_start_time"), "stop": a.get("ad_delivery_stop_time"),
             "reach": a.get("eu_total_reach"), "platforms": a.get("publisher_platforms")} for a in ads[:limit]]
    return {"terms": terms, "count": len(rows), "ads": rows}


def to_draft(ad: dict, run_id: str | None = None) -> IncidentDraft:
    body = (ad.get("ad_creative_bodies") or [None])[0]
    title = (ad.get("ad_creative_link_titles") or [None])[0]
    caption = (ad.get("ad_creative_link_captions") or [None])[0]
    desc = (ad.get("ad_creative_link_descriptions") or [None])[0]
    text = " ".join(x for x in (body, title, desc) if x)
    persons = gazetteer.find_persons(text)
    d = IncidentDraft(
        source=IncidentSource(type="hunter", ref=f"meta:{ad['id']}", captured_at=datetime.now(timezone.utc).isoformat()),
        ad=AdLayer(platform="meta", kind="adlibrary_api", library_id=str(ad["id"]), advertiser=ad.get("page_name"),
                   page_id=str(ad.get("page_id") or "") or None, text=body, display_link=caption, cta=title,
                   persons=[], delivery={k: ad.get(k) for k in ("ad_delivery_start_time", "ad_delivery_stop_time", "eu_total_reach",
                                                              "publisher_platforms", "languages", "target_ages", "target_gender",
                                                              "target_locations") if ad.get(k) is not None},
                   ),
        content=Content(persons=persons, brands=gazetteer.find_brands(text), lang=(ad.get("languages") or [None])[0],
                        keywords=[p for p in gazetteer.LURE_PHRASES if p.lower() in text.lower()]),
    )
    d.ad.snapshot_url = redact(ad.get("ad_snapshot_url"))      # extra key (AdLayer allows extras)
    d.source.hunter_run = run_id
    d.source.lure_score = gazetteer.lure_score(text)
    d.quality.available = ["ad_api"]
    d.quality.missing = ["landing_url", "creative_media"]
    return d


def iter_queries(extra_terms: list[str] | None = None, persons: bool = True, max_persons: int = 6) -> Iterator[str]:
    """Lure phrases first, then celebrity names from the gazetteer (impersonation lures), then extras."""
    yield from gazetteer.LURE_PHRASES[:5]
    if persons:
        yield from list(gazetteer.PERSONS)[:max_persons]
    yield from (extra_terms or [])
