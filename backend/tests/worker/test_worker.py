"""Worker: analyze task through the adapter boundary + Redis pub/sub (skipped when Redis on 56379 is down)."""
import asyncio
import uuid

import pytest
import redis.asyncio as aioredis

from trop.api.engine_adapter import EngineAdapter, Material, StubAdapter
from trop.config import settings
from trop.schema import BOT_STEPS, Decision
from trop.worker import bus, tasks


async def _redis():
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await r.ping()
    except Exception:
        pytest.skip("redis not reachable (docker compose -f deploy/compose.yml up -d redis)")
    return r


async def test_analyze_publishes_ordered_events_and_state():
    r = await _redis()
    jid = "JOB-T" + uuid.uuid4().hex[:8]
    got = []

    async def listen():
        async for ev in bus.subscribe(r, f"job:{jid}"):
            got.append(ev)

    lt = asyncio.create_task(listen())
    await asyncio.sleep(0.2)
    res = await tasks.run_analysis(r, StubAdapter(speed=400), jid, {"kind": "url", "name": "https://morvanta.click/", "paths": []})
    await asyncio.wait_for(lt, 10)
    assert res["decision"] == "assign" and res["incident_id"] == "INC-24817"
    assert got[-1].type == "job.done"
    assert [e.data["step"]["key"] for e in got if e.type == "job.step" and e.data["step"]["status"] == "run"] == [k for k, _, _ in BOT_STEPS]
    st = await bus.get_state(r, jid)
    assert st["status"] == "done" and st["campaign_id"] == "KMP-017"
    # a late subscriber gets the full history
    late = [e async for e in bus.subscribe(r, f"job:{jid}")]
    assert len(late) == len(got)


async def test_failing_adapter_reports_job_error():
    r = await _redis()

    class Boom:
        def analyze(self, material: Material, emit):
            emit("job.step", {"job_id": material.job_id, "step": {"key": "capture", "bot": "zwiadowca", "label": "x", "status": "run"}})
            raise RuntimeError("page down")

    jid = "JOB-E" + uuid.uuid4().hex[:8]
    res = await tasks.run_analysis(r, Boom(), jid, {"kind": "url", "name": "https://down.test", "paths": []})
    assert res["error"] == "page down"
    last = (await r.lrange(bus.ekey(f"job:{jid}"), 0, -1))[-1]
    assert '"job.error"' in last
    assert (await bus.get_state(r, jid))["status"] == "error"


async def test_placeholders_degrade_gracefully():
    out = await tasks.capture({}, "https://x.test")
    assert out["task"] == "capture"


def test_stub_adapter_matches_protocol():
    a: EngineAdapter = StubAdapter(speed=1000)
    events = []
    dec = a.analyze(Material(job_id="JOB-P", kind="url", name="https://bonenergetyczny24.site/"), lambda t, d: events.append(t))
    assert isinstance(dec, Decision) and dec.decision == "new" and events[-1] == "job.done"


def test_worker_settings_register_all_jobs():
    from trop.worker.settings import WorkerSettings
    names = {f.name for f in WorkerSettings.functions}
    assert {"analyze", "batch", "capture", "enrich", "hunt", "oracle", "agent", "act"} <= names
    assert str(WorkerSettings.redis_settings.port) == "56379"
