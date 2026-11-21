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


capture = _placeholder("capture", "trop.capture.capture", "capture_url")
enrich = _placeholder("enrich", "trop.enrich.service", "enrich")

act = _placeholder("act", "trop.act.service", "build_package")


AGENT_DEADLINE_S = 840          # arq job_timeout of `agent` is 900: we always finish (and tell the analyst) before arq cancels us
_AGENT_POOL = None


def _agent_pool():
    global _AGENT_POOL
    if _AGENT_POOL is None:
        from concurrent.futures import ThreadPoolExecutor
        _AGENT_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="white-rabbit")     # own pool: other tasks can never starve an investigation
    return _AGENT_POOL


def _agent_fail(inv_id: str, why: str, exc: BaseException | None = None) -> None:
    """Never hang silently: mark the investigation as error and emit investigation.done with a Polish message."""
    msg = f"Śledztwo przerwane: {why}"
    if exc is not None:
        msg += f" ({type(exc).__name__}: {str(exc)[:160]})"
    try:
        from trop.agent import service as svc
        inv = svc.get_investigation(inv_id)
        inv.status = "error"
        svc._save(inv)
    except Exception:  # noqa: BLE001
        log.warning("could not persist error state of %s", inv_id)
    try:
        bus.publish_sync(f"inv:{inv_id}", "investigation.done", {"investigation_id": inv_id, "status": "error", "summary": {"error": msg, "steps": 0}})
    except Exception:  # noqa: BLE001
        log.exception("could not publish investigation.done for %s", inv_id)


async def agent(ctx: dict, inv_id: str, body: dict, hints: list[str] | None = None) -> dict:
    """White Rabbit run (blocking trop.agent.service.run_investigation in a thread). Events are published on `inv:<id>`.
    Any internal error ends with investigation.done (status error, Polish message)."""
    try:
        from trop.agent import service as svc
        from trop.agent.loop import Control

        def emit(typ: str, data: dict) -> None:
            bus.publish_sync(f"inv:{inv_id}", typ, {"investigation_id": inv_id, **data})

        emit("casefile.delta", {"step_n": 0, "text_delta": "_Robotnik przyjął śledztwo, zaczynam od bazy…_\n\n"})
        control = Control(svc._dir(inv_id) / "control.jsonl")
        for h in hints or []:                           # pivots of the incident the investigation was started from (analyst notes, budget cap unchanged)
            control.put({"type": "steer", "message": h})
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(_agent_pool(), lambda: svc.run_investigation(body, emit, investigation_id=inv_id, control=control))
        try:
            res = await asyncio.wait_for(asyncio.shield(fut), AGENT_DEADLINE_S)
        except asyncio.TimeoutError:
            try:
                svc.stop(inv_id)
            except Exception:  # noqa: BLE001
                pass
            _agent_fail(inv_id, f"przekroczono limit czasu {AGENT_DEADLINE_S // 60} min")
            return {"investigation_id": inv_id, "error": "deadline exceeded"}
        return {"investigation_id": inv_id, "status": res.get("status")}
    except asyncio.CancelledError:
        _agent_fail(inv_id, "zadanie zostało anulowane przez robotnika (limit czasu)")
        raise
    except Exception as e:  # noqa: BLE001
        log.exception("agent failed")
        _agent_fail(inv_id, "błąd wewnętrzny", e)
        return {"investigation_id": inv_id, "error": f"{type(e).__name__}: {str(e)[:200]}"}


HUNT_RUNNERS = {"meta_adlibrary": "run_meta", "certpl": "run_certpl", "urlscan": "run_urlscan", "google_ads_transparency": "run_google"}


async def hunt(ctx: dict, source_id: str) -> dict:
    """Run one Hunter source (trop.hunter.runner); drafts are attributed through the sink publisher (worker hooks)."""
    from trop.hunter import runner
    fn = getattr(runner, HUNT_RUNNERS.get(source_id, ""), None)
    if fn is None:
        return {"source_id": source_id, "status": "unknown source"}
    loop = asyncio.get_running_loop()
    run = await loop.run_in_executor(None, lambda: fn(progress=lambda m: log.info("hunter %s: %s", source_id, m)))
    return {"source_id": source_id, "run_id": run.id, "status": run.status, "found": run.found, "attributed": run.attributed}


async def oracle(ctx: dict, certstream_s: float = 20.0) -> dict:
    """One Oracle poll (CT stream + urlscan); new predictions are published as oracle.match by the worker notifier."""
    from trop.oracle import service
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: service.poll_once(certstream_s=certstream_s))
