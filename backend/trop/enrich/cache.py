"""Filesystem cache + polite HTTP for enrichment providers.

Layout: <settings.cache_dir>/enrich/<source>/<key>.json  ->  {"_meta": {...}, "data": <normalised result>}
* fresh hit -> no network; miss -> token bucket -> request -> write.
* TROP_MODE=offline (or TROP_OFFLINE=1): cache-only replay, expired entries are still served, a miss returns
  status "offline" and NEVER touches the network.
* Only third-party services are contacted (crt.sh, RDAP, resolvers, urlscan, ...), never the scam host.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx

from trop.config import settings

USER_AGENT = os.environ.get("TROP_UA", "TROP-OSINT/0.1 (scam-campaign research; HackNation 2026)")
TTL = {"ok": 7 * 86400, "not_found": 86400, "error": 600, "rate_limited": 300}
SHORT_TTL = {"certpl": 3600, "urlscan": 86400, "wayback": 14 * 86400}   # per-source overrides for "ok"


@dataclass
class Result:
    status: str                  # ok | not_found | error | rate_limited | offline
    data: Any = None
    cached: bool = False
    error: str | None = None
    http_status: int | None = None


def is_offline() -> bool:
    return settings.trop_mode == "offline" or os.environ.get("TROP_OFFLINE") == "1"


def cache_root() -> Path:
    return Path(settings.cache_dir) / "enrich"


def key_to_name(key: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", key)
    if len(safe) > 80 or safe != key:
        return safe[:60] + "~" + hashlib.sha256(key.encode()).hexdigest()[:12]
    return safe


def _path(source: str, key: str) -> Path:
    return cache_root() / source / (key_to_name(key) + ".json")


def get(source: str, key: str, *, ignore_ttl: bool = False) -> Result | None:
    p = _path(source, key)
    if not p.is_file():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    m = d.get("_meta", {})
    status = m.get("status", "ok")
    ttl = SHORT_TTL.get(source, TTL["ok"]) if status == "ok" else TTL.get(status, 600)
    if m.get("seeded"):
        ttl = 10 * 365 * 86400
    fresh = time.time() - m.get("fetched_at", 0) < ttl
    if fresh or is_offline() or ignore_ttl:
        return Result(status, d.get("data"), cached=True, error=m.get("error"), http_status=m.get("http_status"))
    return None


def put(source: str, key: str, res: Result, **meta: Any) -> None:
    p = _path(source, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = {"_meta": {"key": key, "status": res.status, "fetched_at": time.time(), "error": res.error,
                      "http_status": res.http_status, **meta}, "data": res.data}
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(p)


class TokenBucket:
    def __init__(self, rate_per_min: float, burst: int = 1):
        self.rate, self.cap = max(rate_per_min, 0.1) / 60.0, max(burst, 1)
        self.tokens, self.t = float(self.cap), time.monotonic()
        self.lock = threading.Lock()

    def take(self) -> None:
        with self.lock:
            while True:
                now = time.monotonic()
                self.tokens = min(self.cap, self.tokens + (now - self.t) * self.rate)
                self.t = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                time.sleep((1 - self.tokens) / self.rate)


# polite per-provider limits (requests/min): crt.sh ~5/min, urlscan anon 30/min, certspotter 100/h
RATES = {"crtsh": 4, "certspotter": 1.5, "rdap": 30, "urlscan": 20, "ipinfo": 60, "wayback": 20, "certpl": 5}
_buckets: dict[str, TokenBucket] = {}


def bucket(source: str) -> TokenBucket:
    return _buckets.setdefault(source, TokenBucket(RATES.get(source, 30), 1))


_client: httpx.Client | None = None


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=40, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    return _client


def fetch_json(source: str, key: str, url: str, *, params: dict | None = None, headers: dict | None = None,
               timeout: float | None = None, not_found: tuple[int, ...] = (404,), retries: int = 1,
               parse: Callable[[Any], Any] | None = None, use_cache: bool = True) -> Result:
    """Cached GET returning JSON (optionally post-processed by `parse`, which is what gets cached)."""
    if use_cache:
        hit = get(source, key)
        if hit is not None:
            return hit
    if is_offline():
        return Result("offline", error="offline mode: no cached entry")
    last = Result("error", error="no attempt")
    for attempt in range(retries + 1):
        bucket(source).take()
        try:
            r = client().get(url, params=params, headers=headers, timeout=timeout or 40)
        except httpx.HTTPError as e:
            last = Result("error", error=f"{type(e).__name__}: {e}")
            time.sleep(1 + attempt)
            continue
        if r.status_code in not_found:
            last = Result("not_found", http_status=r.status_code)
            break
        if r.status_code == 429:
            last = Result("rate_limited", http_status=429, error="429")
            time.sleep(min(float(r.headers.get("retry-after", 5)), 30))
            continue
        if r.status_code >= 500:
            last = Result("error", http_status=r.status_code, error=f"HTTP {r.status_code}")
            time.sleep(1 + attempt)
            continue
        if r.status_code >= 400:
            last = Result("error", http_status=r.status_code, error=r.text[:200])
            break
        try:
            data = r.json()
            last = Result("ok", parse(data) if parse else data, http_status=r.status_code)
        except ValueError as e:
            last = Result("error", http_status=r.status_code, error=f"bad JSON: {e}")
        break
    if use_cache:
        put(source, key, last)
    return last
