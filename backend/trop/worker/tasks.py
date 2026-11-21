"""arq task functions. `analyze` runs the engine adapter and publishes SSE events through Redis pub/sub."""
from __future__ import annotations

import asyncio
import importlib
import logging
from datetime import datetime, timezone
from typing import Any

from trop.api.engine_adapter import Material, get_adapter
from trop.schema import Event
from trop.worker import bus

log = logging.getLogger("trop.worker")


def _ev(typ: str, data: dict) -> Event:
    return Event(type=typ, at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"), data=data)


async def run_analysis(r, adapter, job_id: str, material: dict) -> dict:
    """Core of the `analyze` task (testable with a stub adapter and any redis client)."""
    loop = asyncio.get_running_loop()
    mat = Material(job_id=job_id, **{k: v for k, v in material.items() if k in ("kind", "name", "paths")})
    kind = mat.kind if mat.kind in ("url", "file", "zip", "folder", "batch") else "file"
    state = {"id": job_id, "status": "running", "input": {"kind": kind, "name": mat.name}}
    await bus.set_state(r, job_id, state)

    def emit(typ: str, data: dict) -> None:
        asyncio.run_coroutine_threadsafe(bus.publish(r, f"job:{job_id}", _ev(typ, data)), loop).result(timeout=10)
        if typ == "job.done":
            d = data["decision"]
            state.update(status="done", incident_id=data["incident_id"], decision=d["decision"],
                         campaign_id=d.get("campaign_id") or d.get("candidate_campaign_id"))
            asyncio.run_coroutine_threadsafe(bus.set_state(r, job_id, state), loop).result(timeout=10)

    try:
        dec = await loop.run_in_executor(None, adapter.analyze, mat, emit)
        return {"job_id": job_id, "incident_id": dec.incident_id, "decision": dec.decision}
    except Exception as e:  # board 13: still emit what was established
        log.exception("analyze failed")
        state.update(status="error", error=str(e))
        await bus.set_state(r, job_id, state)
        await bus.publish(r, f"job:{job_id}", _ev("job.error", {"job_id": job_id, "step": "capture", "message": str(e)}))
        return {"job_id": job_id, "error": str(e)}


async def analyze(ctx: dict, job_id: str, material: dict) -> dict:
    return await run_analysis(ctx.get("redis_bus") or bus.client(), ctx.get("adapter") or get_adapter(), job_id, material)


async def batch(ctx: dict, job_id: str, items: list[dict]) -> dict:
    """Placeholder: per item adapter.analyze -> BatchRow (wired at G2 with trop.ingest + engine.service)."""
    r = ctx.get("redis_bus") or bus.client()
    await bus.set_state(r, job_id, {"id": job_id, "status": "done", "n_items": len(items), "rows": [], "note": "engine not wired"})
    return {"job_id": job_id, "n": len(items)}


def _placeholder(name: str, module: str, func: str):
    async def task(ctx: dict, *args: Any, **kwargs: Any) -> dict:
        try:
            fn = getattr(importlib.import_module(module), func)
        except (ModuleNotFoundError, AttributeError):
            log.warning("task %s: %s.%s not available yet", name, module, func)
            return {"task": name, "status": "unavailable", "detail": f"{module}.{func} not installed"}
        res = fn(*args, **kwargs)
        return {"task": name, "status": "ok", "result": await res if asyncio.iscoroutine(res) else res}
    task.__name__ = name
    return task


capture = _placeholder("capture", "trop.capture.service", "capture")
enrich = _placeholder("enrich", "trop.enrich.service", "enrich")
hunt = _placeholder("hunt", "trop.hunter.service", "run_source")
oracle = _placeholder("oracle", "trop.oracle.service", "run")
agent = _placeholder("agent", "trop.agent.service", "run_investigation")
act = _placeholder("act", "trop.act.service", "build_package")
