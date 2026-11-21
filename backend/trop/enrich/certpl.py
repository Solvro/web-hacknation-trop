"""CERT Polska warning list (hole.cert.pl v2): sync to the FS cache, membership check, snapshot diff.

State under <cache>/enrich/certpl/: list.json {domain: [insert, delete]}, state.json {etag, last_modified, synced_at},
prev.json (list before the last change, for diffs), diff.json (last diff). Offline: serves what is cached.
Licence: any use incl. commercial; attribution optional and must not imply endorsement.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from . import cache
from .util import etld1, host_of

JSON_URL = "https://hole.cert.pl/domains/v2/domains.json"
TXT_URL = "https://hole.cert.pl/domains/v2/domains.txt"
_MEM: dict = {}


def _dir() -> Path:
    d = cache.cache_root() / "certpl"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _parse(body: bytes, url: str) -> dict[str, list]:
    out: dict[str, list] = {}
    if url.endswith(".json"):
        data = json.loads(body)
        rows = data if isinstance(data, list) else data.get("domains") or data.get("data") or []
        for r in rows:
            d = str(r.get("DomainAddress", "")).strip().lower().rstrip(".")
            if d:
                out[d] = [r.get("InsertDate"), r.get("DeleteDate")]
    else:
        for ln in body.decode("utf-8", "ignore").splitlines():
            if ln.strip() and not ln.startswith("#"):
                out[ln.strip().lower()] = [None, None]
    return out


def load() -> dict[str, list]:
    p = _dir() / "list.json"
    if "list" not in _MEM or _MEM.get("mtime") != (p.stat().st_mtime if p.exists() else 0):
        _MEM["list"] = json.loads(p.read_text()) if p.exists() else {}
        _MEM["mtime"] = p.stat().st_mtime if p.exists() else 0
    return _MEM["list"]


def sync(force: bool = False) -> dict:
    """Conditional GET of the list; on change writes list.json (+ prev.json, diff.json). -> stats."""
    d = _dir()
    if cache.is_offline():
        return {"offline": True, "domains": len(load())}
    st_p = d / "state.json"
    state = json.loads(st_p.read_text()) if st_p.exists() and not force else {}
    headers = {"User-Agent": cache.USER_AGENT}
    if state.get("etag"):
        headers["If-None-Match"] = state["etag"]
    if state.get("last_modified"):
        headers["If-Modified-Since"] = state["last_modified"]
    body, url, r = None, None, None
    with httpx.Client(timeout=120, follow_redirects=True) as c:
        for url in (JSON_URL, TXT_URL):
            try:
                r = c.get(url, headers=headers)
            except httpx.HTTPError:
                continue
            if r.status_code == 304:
                return {"not_modified": True, "domains": len(load())}
            if r.status_code == 200:
                body = r.content
                break
    if body is None:
        return {"error": "CERT PL list unreachable", "domains": len(load())}
    new = _parse(body, url)
    old = load()
    added = sorted(k for k, v in new.items() if k not in old and not v[1])
    removed = sorted(k for k, v in old.items() if not v[1] and (k not in new or new[k][1]))
    if old:
        (d / "prev.json").write_text(json.dumps(old))
    (d / "list.json").write_text(json.dumps(new))
    diff = {"at": time.time(), "added": added, "removed": removed, "first_sync": not old}
    (d / "diff.json").write_text(json.dumps(diff))
    st_p.write_text(json.dumps({"etag": r.headers.get("etag"), "last_modified": r.headers.get("last-modified"),
                                "url": url, "synced_at": time.time()}))
    _MEM.clear()
    return {"url": url, "domains": len(new), "added": len(added), "removed": len(removed), "first_sync": not old}


def last_diff() -> dict:
    p = _dir() / "diff.json"
    return json.loads(p.read_text()) if p.exists() else {"added": [], "removed": []}


def check(domain: str, refresh: bool = False) -> dict:
    """-> {listed: bool|None, first_seen, removed_at, matched}. listed=None when no list is cached."""
    lst = load()
    if not lst:
        if refresh or not cache.is_offline():
            sync()
            lst = load()
        if not lst:
            return {"listed": None, "reason": "certpl list not cached"}
    h = host_of(domain)
    for cand in dict.fromkeys([h, etld1(h)]):
        rec = lst.get(cand)
        if rec:
            return {"listed": not rec[1], "first_seen": rec[0], "removed_at": rec[1], "matched": cand}
    return {"listed": False}
