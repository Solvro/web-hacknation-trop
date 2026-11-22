"""arq WorkerSettings (`trop worker` -> arq.run_worker)."""
import asyncio

from arq.connections import RedisSettings

from trop.config import settings
from arq.worker import func

from trop.worker import diag, tasks


async def startup(ctx: dict) -> None:
    """Load the corpus once per worker (first analysis would otherwise pay for it)."""
    from trop.api.engine_adapter import worker_corpus
    await asyncio.get_running_loop().run_in_executor(None, diag.write_info)       # uid, writable dirs, mode: read by GET /debug/worker
    try:
        await asyncio.get_running_loop().run_in_executor(None, worker_corpus)
    except Exception:  # noqa: BLE001 - stub mode without engine
        pass
    try:
        from trop.agent import service as svc
        await asyncio.get_running_loop().run_in_executor(None, svc.reap_stale)     # B8: investigations orphaned by the previous worker
    except Exception:  # noqa: BLE001
        pass
    try:
        from trop.worker import hooks
        ctx["scheduler"] = hooks.install()
    except Exception:  # noqa: BLE001
        pass


async def shutdown(ctx: dict) -> None:
    if ctx.get("scheduler"):
        ctx["scheduler"].shutdown(wait=False)


class WorkerSettings:
    on_startup = startup
    on_shutdown = shutdown
    functions = [func(diag.recorded(f), name=f.__name__, timeout=(900 if f.__name__ == "agent" else None))
                 for f in (tasks.analyze, tasks.batch, tasks.capture, tasks.enrich, tasks.hunt, tasks.oracle, tasks.agent, tasks.act)]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 4                 # an investigation is light (own thread pool); 4 keeps a long batch from blocking it
    job_timeout = 600
    keep_result = 3600
    health_check_interval = 30   # heartbeat key arq:queue:health-check (read by GET /debug/worker)
