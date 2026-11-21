"""SSE plumbing: sequence playback, `?replay=` recordings, recorder, ping comments."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from pathlib import Path
from typing import AsyncIterator

from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from trop.api.sequences import Seq, canned_recordings, record_to
from trop.config import settings
from trop.schema import Event

PKG_REPLAY = Path(__file__).parent / "replay"
PING_S = 15


def speed() -> float:
    """Playback speed multiplier (tests set TROP_MOCK_SPEED=100)."""
    return float(os.environ.get("TROP_MOCK_SPEED", "1") or 1)


def replay_dir() -> Path:
    return Path(os.environ.get("REPLAY_DIR") or settings.replay_dir)


def ensure_replay_files() -> None:
    """Copy the canned (fictional) demo recordings from the package to data/replay if missing."""
    d = replay_dir()
    d.mkdir(parents=True, exist_ok=True)
    for f in PKG_REPLAY.glob("*.jsonl"):
        if not (d / f.name).exists():
            shutil.copy(f, d / f.name)


def generate_canned(out: Path = PKG_REPLAY) -> list[Path]:
    paths = []
    for name, seq in canned_recordings().items():
        p = out / f"{name}.jsonl"
        record_to(p, seq)
        paths.append(p)
    return paths


def find_recording(name: str, kind: str) -> Path | None:
    for d in (replay_dir(), PKG_REPLAY):
        for cand in (f"{name}-{kind}.jsonl", f"{name}.jsonl"):
            if (d / cand).exists():
                return d / cand
    return None


def load_recording(path: Path) -> Seq:
    seq: Seq = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            seq.append((float(r["t"]), Event.model_validate(r["event"])))
    return seq


def _sse(ev: Event, rewrite: dict[str, str] | None = None) -> ServerSentEvent:
    d = ev.model_dump(mode="json")
    if rewrite:
        for k, v in rewrite.items():
            if k in d["data"]:
                d["data"][k] = v
    return ServerSentEvent(data=json.dumps(d, ensure_ascii=False), event=ev.type)


async def play(seq: Seq, start_at: float = 0.0, rewrite: dict[str, str] | None = None, loop_forever: bool = False) -> AsyncIterator[ServerSentEvent]:
    """Yield events at their offsets (seconds from t0); events with offset < start_at are sent immediately (late subscriber)."""
    sp = speed()
    t0 = time.monotonic() - start_at / sp
    for off, ev in seq:
        wait = off / sp - (time.monotonic() - t0)
        if wait > 0:
            await asyncio.sleep(wait)
        yield _sse(ev, rewrite)


def response(gen: AsyncIterator[ServerSentEvent]) -> EventSourceResponse:
    return EventSourceResponse(gen, ping=PING_S, headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def hold_then_ping(gen: AsyncIterator[ServerSentEvent], hold: bool) -> AsyncIterator[ServerSentEvent]:
    async for x in gen:
        yield x
    while hold:  # keep the connection open (EventSourceResponse sends `: ping` every 15 s)
        await asyncio.sleep(3600)


# ------------------------------------------------------------------------------------------------- recorder
async def record_stream(url: str, out: Path, max_seconds: float = 120.0) -> int:
    """Record a live SSE endpoint to JSONL with original timing (`trop demo record --url ...`)."""
    import httpx
    n, t0 = 0, time.monotonic()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        async with httpx.AsyncClient(timeout=None) as c:
            async with c.stream("GET", url, headers={"Accept": "text/event-stream"}) as r:
                async for line in r.aiter_lines():
                    if time.monotonic() - t0 > max_seconds:
                        break
                    if line.startswith("data:"):
                        ev = json.loads(line[5:].strip())
                        f.write(json.dumps({"t": round(time.monotonic() - t0, 3), "type": ev["type"], "event": ev}, ensure_ascii=False) + "\n")
                        f.flush()
                        n += 1
                        if ev["type"] in ("job.done", "job.error", "investigation.done"):
                            break
    return n
