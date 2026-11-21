"""arq WorkerSettings (`trop worker` -> arq.run_worker)."""
from arq.connections import RedisSettings

from trop.config import settings
from trop.worker import tasks


class WorkerSettings:
    functions = [tasks.analyze, tasks.batch, tasks.capture, tasks.enrich, tasks.hunt, tasks.oracle, tasks.agent, tasks.act]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 2                 # memory budget: worker container 1.5 GiB
    job_timeout = 600
    keep_result = 3600
