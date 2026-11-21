"""Redis event bus shared by the API (SSE) and the worker (publisher).

Per stream name: list `trop:<name>:events` (history for late subscribers) + pub/sub channel `trop:<name>`.
Names: `job:<id>`, `inv:<id>`, `events`, `oracle`. Job state: JSON in `trop:job:<id>:state`.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncIterator

import redis.asyncio as aioredis

from trop.config import settings
from trop.schema import Event

TTL = 24 * 3600
TERMINAL = {"job.done", "job.error", "investigation.done"}


def client() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


def ekey(name: str) -> str:
    return f"trop:{name}:events"


async def publish(r: aioredis.Redis, name: str, ev: Event) -> None:
    payload = ev.model_dump_json()
    n = await r.rpush(ekey(name), payload)
    await r.expire(ekey(name), TTL)
    await r.publish(f"trop:{name}", json.dumps({"i": n - 1, "e": payload}))


async def subscribe(r: aioredis.Redis, name: str, history: bool = True, stop_on_terminal: bool = True) -> AsyncIterator[Event]:
    """History first (list), then live messages with index >= len(history); ends after a terminal event if requested."""
    ps = r.pubsub()
    await ps.subscribe(f"trop:{name}")
    try:
        nxt = 0
        if history:
            for raw in await r.lrange(ekey(name), 0, -1):
                ev = Event.model_validate_json(raw)
                nxt += 1
                yield ev
                if stop_on_terminal and ev.type in TERMINAL:
                    return
        else:
            nxt = await r.llen(ekey(name))
        while True:
            msg = await ps.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg is None:
                await asyncio.sleep(0.05)
                continue
            m = json.loads(msg["data"])
            if m["i"] < nxt:
                continue
            nxt = m["i"] + 1
            ev = Event.model_validate_json(m["e"])
            yield ev
            if stop_on_terminal and ev.type in TERMINAL:
                return
    finally:
        await ps.unsubscribe()
        await ps.aclose()


async def set_state(r: aioredis.Redis, job_id: str, state: dict) -> None:
    await r.set(f"trop:job:{job_id}:state", json.dumps(state, ensure_ascii=False), ex=TTL)
    await r.zadd("trop:jobs", {job_id: time.time()})


async def get_state(r: aioredis.Redis, job_id: str) -> dict | None:
    raw = await r.get(f"trop:job:{job_id}:state")
    return json.loads(raw) if raw else None
