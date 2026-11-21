"""Real-mode data layer (DB + Redis). Jobs/SSE are implemented (arq + Redis pub/sub); DB-backed resources answer 501
until the lead wires `trop.store` (WS1) at gate G2: implement the same method names as `MockStore`.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import AsyncIterator

from fastapi import HTTPException

from trop.api import models as M
from trop.config import settings
from trop.schema import AnalyzeAccepted, Event, Job, JobInput, JobStep, BOT_STEPS
from trop.worker import bus


class RealStore:
    mode = "live"

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)

        def not_wired(*a, **k):
            raise HTTPException(501, f"'{name}' is not wired to the database yet (real mode); run with --mock for the demo universe")
        return not_wired

    def health_counts(self) -> dict[str, int]:
        return {}

    # ---- jobs (fully real: API -> arq -> worker -> Redis pub/sub -> SSE)
    async def analyze(self, kind: str, name: str, saved: list[str] | None = None) -> M.AnalyzeResponse:
        if kind == "trace":
            return M.AnalyzeResponse(job_id=None)
        from arq import create_pool
        from arq.connections import RedisSettings
        jid = "JOB-" + uuid.uuid4().hex[:12].upper()
        r = bus.client()
        k = kind if kind in ("url", "file", "zip", "folder", "batch") else "file"
        await bus.set_state(r, jid, {"id": jid, "status": "queued", "input": {"kind": k, "name": name}})
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            await pool.enqueue_job("analyze", jid, {"kind": kind, "name": name, "paths": saved or []}, _job_id=jid)
        finally:
            await pool.aclose()
        return M.AnalyzeResponse(job_id=jid, incident_id=None)

    async def job(self, jid: str) -> Job:
        r = bus.client()
        st = await bus.get_state(r, jid)
        if not st:
            raise HTTPException(404, "job not found")
        job = Job(id=jid, status=st["status"], input=JobInput(**st["input"]), incident_id=st.get("incident_id"), decision=st.get("decision"),
                  campaign_id=st.get("campaign_id"), error=st.get("error"))
        steps = {s.key: s for s in job.steps}
        for raw in await r.lrange(bus.ekey(f"job:{jid}"), 0, -1):
            ev = Event.model_validate_json(raw)
            if ev.type == "job.step":
                s = JobStep.model_validate(ev.data["step"])
                steps[s.key] = s
        job.steps = [steps[k] for k, _, _ in BOT_STEPS]
        return job

    async def jobs_list(self, limit: int) -> list[Job]:
        r = bus.client()
        ids = await r.zrevrange("trop:jobs", 0, limit - 1)
        return [await self.job(i) for i in ids]

    def job_events(self, jid: str) -> AsyncIterator[Event]:
        return bus.subscribe(bus.client(), f"job:{jid}")

    def channel_events(self, name: str) -> AsyncIterator[Event]:
        return bus.subscribe(bus.client(), name, history=False, stop_on_terminal=False)

    def investigation_events(self, iid: str) -> AsyncIterator[Event]:
        return bus.subscribe(bus.client(), f"inv:{iid}")

    @staticmethod
    def save_upload_dir(job_hint: str) -> Path:
        d = Path(settings.artifact_dir) / "uploads" / job_hint
        d.mkdir(parents=True, exist_ok=True)
        return d
