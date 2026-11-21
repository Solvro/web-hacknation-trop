"""Internet Archive Wayback lookups (availability + CDX). Third-party; the scam host is not contacted."""
from __future__ import annotations

from . import cache
from .util import host_of


def snapshots(url_or_domain: str, limit: int = 10) -> dict:
    h = host_of(url_or_domain) or url_or_domain
    key = f"cdx:{url_or_domain}:{limit}"

    def parse(rows):
        if not rows or len(rows) < 2:
            return []
        head = rows[0]
        return [dict(zip(head, r)) for r in rows[1:]]

    res = cache.fetch_json("wayback", key, "https://web.archive.org/cdx/search/cdx",
                           params={"url": url_or_domain if "/" in url_or_domain else h, "output": "json", "limit": limit,
                                   "fl": "timestamp,original,statuscode,mimetype,digest", "collapse": "digest"},
                           parse=parse)
    snaps = res.data if res.status == "ok" else []
    return {"query": url_or_domain, "count": len(snaps), "snapshots": snaps,
            "first": snaps[0]["timestamp"] if snaps else None,
            "urls": [f"https://web.archive.org/web/{s['timestamp']}/{s['original']}" for s in snaps[:5]],
            "error": None if res.status in ("ok", "not_found") else (res.error or res.status)}
