"""APScheduler job definitions that WS2's worker hosts.

    from trop.hunter.scheduler import build_scheduler
    sch = build_scheduler(background=False)   # AsyncIOScheduler for the worker's event loop; background=True -> thread
    sch.start()

Jobs (all offline-safe, each returns a HunterRun that is also persisted under data/hunter/<run_id>/):
  hunter:certpl   hourly   CERT PL list diff
  hunter:meta     every 6 h Meta Ad Library lure phrases -> snapshots -> sandboxed captures (disabled without META_ACCESS_TOKEN)
  hunter:urlscan  daily    urlscan pivots from campaign assets -> oracle candidates
  hunter:google   daily    Google Ads Transparency advertiser enrichment (disabled without ADC)
  oracle:poll     every 15 min  Oracle CT polling for campaign TLDs
"""
from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger("trop.hunter")


def job_certpl() -> Any:
    from .runner import run_certpl
    return run_certpl(progress=log.info)


def job_meta() -> Any:
    from trop.config import settings
    if not settings.meta_access_token:
        log.warning("hunter:meta skipped: META_ACCESS_TOKEN missing")
        return None
    from .runner import run_meta
    return run_meta(progress=log.info)


def job_urlscan() -> Any:
    from .runner import run_urlscan
    return run_urlscan(progress=log.info)


def job_google() -> Any:
    from . import google_atc
    if google_atc.credentials_status() != "set":
        return None
    from .runner import run_google
    return run_google(progress=log.info)


def job_oracle() -> Any:
    from trop.oracle import service
    return service.poll_once()


JOBS = [
    ("hunter:certpl", job_certpl, IntervalTrigger(hours=1)),
    ("hunter:meta", job_meta, IntervalTrigger(hours=6)),
    ("hunter:urlscan", job_urlscan, CronTrigger(hour=4, minute=15)),
    ("hunter:google", job_google, CronTrigger(hour=4, minute=45)),
    ("oracle:poll", job_oracle, IntervalTrigger(minutes=15)),
]


def build_scheduler(background: bool = False, only: list[str] | None = None):
    """Blocking-job scheduler (jobs run in the scheduler's thread pool). Not started."""
    sch = BackgroundScheduler(timezone="UTC") if background else AsyncIOScheduler(timezone="UTC")
    for jid, fn, trig in JOBS:
        if only and jid not in only:
            continue
        sch.add_job(fn, trig, id=jid, name=jid, max_instances=1, coalesce=True, misfire_grace_time=600, replace_existing=True)
    return sch
