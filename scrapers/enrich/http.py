"""Cached, rate-limited HTTP for enrichment providers.

Every call goes through enrichment_cache (provider, key): fresh hit → no network; miss → token bucket
→ request → cache (ok / not_found / error / rate_limited, each with its own TTL from enrichment_providers).
REDPILL_OFFLINE=1 serves from cache only (demo / judge machine without network).
"""
from __future__ import annotations

import json
import os
import random
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx
import psycopg
from psycopg.types.json import Jsonb

USER_AGENT = os.environ.get("REDPILL_UA", "RedPill-OSINT/0.1 (scam-campaign research; HackNation 2026)")


@dataclass
class Result:
    status: str              # ok | not_found | error | rate_limited | offline
    data: Any = None
    http_status: int | None = None
    cached: bool = False
    error: str | None = None


class TokenBucket:
    def __init__(self, rate_per_min: float, burst: int):
        self.rate = max(rate_per_min, 0.1) / 60.0
        self.capacity = max(burst, 1)
        self.tokens = float(self.capacity)
        self.t = time.monotonic()
        self.lock = threading.Lock()

    def take(self) -> None:
        with self.lock:
            while True:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.t) * self.rate)
                self.t = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                time.sleep((1 - self.tokens) / self.rate)


class CachedClient:
    _buckets: dict[str, TokenBucket] = {}

    def __init__(self, conn: psycopg.Connection, provider: str, timeout: float = 30.0):
        self.conn = conn
        self.provider = provider
        row = conn.execute(
            "SELECT ttl_ok, ttl_not_found, ttl_error, coalesce(rate_per_min, 60), coalesce(burst, 1) "
            "FROM enrichment_providers WHERE provider = %s", (provider,)).fetchone()
        if not row:
            raise KeyError(f"unknown provider {provider}")
        self.ttl = {"ok": row[0], "not_found": row[1], "error": row[2], "rate_limited": row[2]}
        if provider not in self._buckets:
            self._buckets[provider] = TokenBucket(row[3], row[4])
        self.bucket = self._buckets[provider]
        self.http = httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
        self.offline = os.environ.get("REDPILL_OFFLINE") == "1"

    def cached(self, key: str) -> Result | None:
        row = self.conn.execute(
            "SELECT status, response, http_status, error FROM enrichment_cache "
            "WHERE provider = %s AND key = %s AND (expires_at > now() OR %s)",
            (self.provider, key, self.offline)).fetchone()
        if row:
            return Result(row[0], row[1], row[2], cached=True, error=row[3])
        return None

    def store(self, key: str, res: Result) -> None:
        self.conn.execute(
            """INSERT INTO enrichment_cache (provider, key, fetched_at, expires_at, status, http_status, response, error)
               VALUES (%s, %s, now(), now() + %s, %s, %s, %s, %s)
               ON CONFLICT (provider, key) DO UPDATE SET fetched_at = now(), expires_at = EXCLUDED.expires_at,
                 status = EXCLUDED.status, http_status = EXCLUDED.http_status, response = EXCLUDED.response,
                 error = EXCLUDED.error, attempts = enrichment_cache.attempts + 1""",
            (self.provider, key, self.ttl[res.status], res.status, res.http_status,
             # jsonb cannot hold \u0000 (scanned pages sometimes contain NUL bytes in strings)
             Jsonb(res.data, dumps=lambda o: json.dumps(o, default=str).replace("\\u0000", ""))
             if res.data is not None else None, res.error))
        self.conn.commit()

    def get_json(self, key: str, url: str, *, params: dict | None = None, headers: dict | None = None,
                 not_found_codes: tuple[int, ...] = (404,), retries: int = 2, parse=None) -> Result:
        hit = self.cached(key)
        if hit:
            return hit
        if self.offline:
            return Result("offline")
        last: Result = Result("error", error="no attempt")
        for attempt in range(retries + 1):
            self.bucket.take()
            try:
                r = self.http.get(url, params=params, headers=headers)
            except httpx.HTTPError as e:
                last = Result("error", error=f"{type(e).__name__}: {e}")
                time.sleep(2 ** attempt + random.random())
                continue
            if r.status_code in not_found_codes:
                last = Result("not_found", http_status=r.status_code)
                break
            if r.status_code == 429:
                wait = float(r.headers.get("retry-after", 2 ** (attempt + 2)))
                last = Result("rate_limited", http_status=429, error="429")
                time.sleep(min(wait, 60))
                continue
            if r.status_code >= 500:
                last = Result("error", http_status=r.status_code, error=f"HTTP {r.status_code}")
                time.sleep(2 ** attempt + random.random())
                continue
            if r.status_code >= 400:
                last = Result("error", http_status=r.status_code, error=r.text[:300])
                break
            try:
                data = parse(r) if parse else r.json()
            except (ValueError, json.JSONDecodeError) as e:
                last = Result("error", http_status=r.status_code, error=f"bad JSON: {e}")
                break
            last = Result("ok", data, r.status_code)
            break
        self.store(key, last)
        return last
