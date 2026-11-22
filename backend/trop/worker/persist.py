"""Durable copies of what Redis only caches (Redis runs without snapshots; a redeploy used to wipe it).

  data/jobs/<job_id>/state.json + events.jsonl      job records and their event lists
  data/incidents/<incident_id>.json                 {"incident": ..., "decision": ...} of fresh analyses (any decision, incl. `new`)
Writers: worker + API (shared volume). Readers hydrate Redis on demand (`hydrate_job`) or read the file directly (`load_incident`).
All functions are best effort: a failing disk never breaks an analysis, but failures are logged.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from trop.config import settings

log = logging.getLogger("trop.persist")
_SAFE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.")


def _safe(x: str) -> str:
    return "".join(c if c in _SAFE else "_" for c in str(x))[:100]


def jobs_dir() -> Path:
    return Path(settings.data_dir) / "jobs"


def incidents_dir() -> Path:
    return Path(settings.data_dir) / "incidents"


def _atomic(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + f".{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(p)


# -- incidents
def save_incident(iid: str, doc: dict) -> bool:
    try:
        _atomic(incidents_dir() / f"{_safe(iid)}.json", json.dumps(doc, ensure_ascii=False, default=str))
        return True
    except Exception:  # noqa: BLE001
        log.exception("cannot persist incident %s", iid)
        return False


def load_incident(iid: str) -> dict | None:
    f = incidents_dir() / f"{_safe(iid)}.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
    except (OSError, ValueError):
        return None


def incident_ids() -> list[str]:
    d = incidents_dir()
    return [p.stem for p in d.glob("*.json")] if d.is_dir() else []


# -- jobs
def save_state(jid: str, state: dict) -> None:
    try:
        _atomic(jobs_dir() / _safe(jid) / "state.json", json.dumps({**state, "_saved": time.time()}, ensure_ascii=False, default=str))
    except Exception:  # noqa: BLE001
        log.exception("cannot persist job state %s", jid)


def load_state(jid: str) -> dict | None:
    f = jobs_dir() / _safe(jid) / "state.json"
    try:
        if not f.is_file():
            return None
        d = json.loads(f.read_text(encoding="utf-8"))
        d.pop("_saved", None)
        return d
    except (OSError, ValueError):
        return None


def append_event(name: str, payload: str) -> None:
    """name = 'job:<id>'; payload = the serialized Event."""
    if not name.startswith("job:"):
        return
    try:
        p = jobs_dir() / _safe(name[4:]) / "events.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(payload.replace("\n", " ") + "\n")
    except Exception:  # noqa: BLE001
        log.exception("cannot persist event of %s", name)


def load_events(jid: str) -> list[str]:
    f = jobs_dir() / _safe(jid) / "events.jsonl"
    try:
        return [ln for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()] if f.is_file() else []
    except OSError:
        return []


def job_ids(limit: int = 200) -> list[tuple[str, float]]:
    """-> [(job_id, saved_at)] newest first."""
    d, out = jobs_dir(), []
    if d.is_dir():
        for p in d.iterdir():
            s = p / "state.json"
            try:
                out.append((p.name, s.stat().st_mtime))
            except OSError:
                pass
    return sorted(out, key=lambda x: -x[1])[:limit]


async def hydrate_job(r: Any, jid: str) -> bool:
    """Put a persisted job (state + event list) back into Redis. True if something was restored."""
    from trop.worker import bus
    st = load_state(jid)
    if not st:
        return False
    await r.set(f"trop:job:{jid}:state", json.dumps(st, ensure_ascii=False), ex=bus.TTL)
    await r.zadd("trop:jobs", {jid: (jobs_dir() / _safe(jid) / "state.json").stat().st_mtime})
    evs = load_events(jid)
    if evs and not await r.llen(bus.ekey(f"job:{jid}")):
        await r.rpush(bus.ekey(f"job:{jid}"), *evs)
        await r.expire(bus.ekey(f"job:{jid}"), bus.TTL)
    return True
