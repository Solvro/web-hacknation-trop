"""arq WorkerSettings (`trop worker` -> arq.run_worker)."""
from arq.connections import RedisSettings

from trop.config import settings
from trop.worker import tasks


async def startup(ctx: dict) -> None:
    """Load the corpus once per worker (first analysis would otherwise pay for it)."""
    import asyncio
    from trop.api.engine_adapter import worker_corpus
    try:
        await asyncio.get_running_loop().run_in_executor(None, worker_corpus)
    except Exception:  # noqa: BLE001 - stub mode without engine
        pass


class WorkerSettings:
    on_startup = startup
    functions = [tasks.analyze, tasks.batch, tasks.capture, tasks.enrich, tasks.hunt, tasks.oracle, tasks.agent, tasks.act]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 2                 # memory budget: worker container 1.5 GiB
    job_timeout = 600
    keep_result = 3600
