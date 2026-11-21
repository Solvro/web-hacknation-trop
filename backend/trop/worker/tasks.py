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
            for t, dd in (("incident.created", {"incident_id": data["incident_id"], "source": "upload"}),
                          ("incident.attributed", {"incident_id": data["incident_id"], "decision": d["decision"], "campaign_id": state["campaign_id"], "p": d.get("p")})):
                asyncio.run_coroutine_threadsafe(bus.publish(r, "events", _ev(t, dd)), loop).result(timeout=10)
        elif typ == "job.error":
            state.update(status="error", error=data.get("message"))
            asyncio.run_coroutine_threadsafe(bus.set_state(r, job_id, state), loop).result(timeout=10)

    try:
        dec = await loop.run_in_executor(None, adapter.analyze, mat, emit)
        return {"job_id": job_id, "incident_id": dec.incident_id, "decision": dec.decision}
    except Exception as e:  # board 13: still emit what was established
        log.exception("analyze failed")
        if type(e).__name__ != "CaptureUnavailable":
            state.update(status="error", error=str(e))
        await bus.set_state(r, job_id, state)
        if type(e).__name__ != "CaptureUnavailable":   # that one already emitted its own job.error
            await bus.publish(r, f"job:{job_id}", _ev("job.error", {"job_id": job_id, "step": "capture", "message": str(e)}))
        return {"job_id": job_id, "error": str(e)}


async def analyze(ctx: dict, job_id: str, material: dict) -> dict:
    return await run_analysis(ctx.get("redis_bus") or bus.client(), ctx.get("adapter") or get_adapter(), job_id, material)


async def batch(ctx: dict, job_id: str, path: str) -> dict:
    """POST /batch: trop.ingest.cli.run_batch over an uploaded zip/folder; BatchResult rows stored in Redis."""
    r = ctx.get("redis_bus") or bus.client()
    loop = asyncio.get_running_loop()
    await bus.set_state(r, job_id, {"id": job_id, "status": "running"})
    try:
        from trop.api.engine_adapter import worker_corpus
        from trop.ingest.cli import run_batch
        res = await loop.run_in_executor(None, lambda: run_batch(path, worker_corpus()))
        rows = [x.model_dump(mode="json") for x in res["rows"]]
        await bus.set_state(r, job_id, {"id": job_id, "status": "done", "n_items": len(rows), "rows": rows, "meta": res["meta"]})
        return {"job_id": job_id, "n": len(rows)}
    except Exception as e:  # noqa: BLE001
        log.exception("batch failed")
        await bus.set_state(r, job_id, {"id": job_id, "status": "error", "error": str(e)})
        return {"job_id": job_id, "error": str(e)}


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
_agent_impl = _placeholder("agent", "trop.agent.service", "run_investigation")


async def agent(ctx: dict, inv_id: str, seed: str, campaign_id: str | None = None, budget_steps: int = 20) -> dict:
    """White Rabbit run: WS6 `run_investigation(inv_id, seed, publish=...)` publishes agent.step/graph.* to Redis `inv:<id>`.
    Without WS6 the stream is closed with investigation.done so the UI never hangs."""
    r = ctx.get("redis_bus") or bus.client()
    out = await _agent_impl(ctx, inv_id, seed, campaign_id=campaign_id, budget_steps=budget_steps)
    if out.get("status") == "unavailable":
        await bus.publish(r, f"inv:{inv_id}", _ev("investigation.done", {"investigation_id": inv_id, "summary": {"error": "agent module not installed"}}))
    return out
act = _placeholder("act", "trop.act.service", "build_package")
