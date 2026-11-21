"""Durable job/investigation event streams, real-mode filters, Polish campaign texts, jury samples."""
import asyncio
import json
import os
import uuid
from pathlib import Path

import pytest
import redis.asyncio as aioredis

from api.test_qa_fixes import needs_redis
from api.test_real import live  # noqa: F401
from trop.config import settings
from trop.schema import Event
from trop.worker import bus

P = "/api/v1"


def mk(t, d):
    return Event(type=t, at="2026-01-01T00:00:00Z", data=d)


async def _drain(store, jid):
    return [e.type async for e in store.job_events(jid)]


@needs_redis
async def test_slow_producer_gap_longer_than_old_watchdog_does_not_end_stream():
    """Regression (prod): a 15 s capture used to end the stream after 3 s of silence."""
    from trop.api.realstore import RealStore
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    jid = "JOB-G" + uuid.uuid4().hex[:6]
    await bus.set_state(r, jid, {"id": jid, "status": "running", "input": {"kind": "url", "name": "x"}})
    await bus.publish(r, f"job:{jid}", mk("job.step", {"job_id": jid, "step": {"key": "capture", "status": "run"}}))
    t = asyncio.create_task(_drain(RealStore(), jid))
    await asyncio.sleep(6.0)                       # > idle watchdog (4 s) with the job still running
    assert not t.done()
    await bus.publish(r, f"job:{jid}", mk("job.step", {"job_id": jid, "step": {"key": "capture", "status": "done"}}))
    await bus.publish(r, f"job:{jid}", mk("job.done", {"job_id": jid}))
    assert await asyncio.wait_for(t, 5) == ["job.step", "job.step", "job.done"]


@needs_redis
async def test_late_and_slow_consumers_get_everything_then_close():
    from trop.api.realstore import RealStore
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    jid = "JOB-L" + uuid.uuid4().hex[:6]
    types = ["job.step", "job.evidence", "job.step", "job.ranking", "job.done"]
    for t in types:
        await bus.publish(r, f"job:{jid}", mk(t, {"job_id": jid}))
    await bus.set_state(r, jid, {"id": jid, "status": "done", "input": {"kind": "url", "name": "x"}})
    assert await asyncio.wait_for(_drain(RealStore(), jid), 5) == types          # connects after the job finished
    got, s = [], RealStore()
    async for e in s.job_events(jid):                                            # slow consumer
        got.append(e.type)
        await asyncio.sleep(0.2)
    assert got == types
    assert (await r.ttl(bus.ekey(f"job:{jid}"))) > 23 * 3600                      # 24 h TTL


@needs_redis
async def test_job_error_is_terminal_and_finished_state_closes_lost_terminal():
    from trop.api.realstore import RealStore
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    jid = "JOB-E" + uuid.uuid4().hex[:6]
    await bus.publish(r, f"job:{jid}", mk("job.step", {"job_id": jid}))
    await bus.publish(r, f"job:{jid}", mk("job.error", {"job_id": jid, "step": "capture", "message": "x"}))
    assert await asyncio.wait_for(_drain(RealStore(), jid), 5) == ["job.step", "job.error"]
    jid2 = "JOB-W" + uuid.uuid4().hex[:6]
    await bus.set_state(r, jid2, {"id": jid2, "status": "done", "input": {"kind": "url", "name": "x"}})
    await bus.publish(r, f"job:{jid2}", mk("job.step", {"job_id": jid2}))
    assert await asyncio.wait_for(_drain(RealStore(), jid2), 10) == ["job.step"]


@needs_redis
async def test_investigation_stream_is_durable():
    from trop.api.realstore import RealStore
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    iid = "INV-T" + uuid.uuid4().hex[:6]
    for t in ("agent.step", "graph.node_added", "investigation.done"):
        await bus.publish(r, f"inv:{iid}", mk(t, {"investigation_id": iid}))
    got = [e.type async for e in RealStore().investigation_events(iid)]
    assert got == ["agent.step", "graph.node_added", "investigation.done"]


def test_real_act_and_oracle_filters(live):  # noqa: F811
    pk = live.get(f"{P}/act/packages?campaign_id=KMP-001").json()
    assert all(p["campaign_id"] == "KMP-001" for p in pk)
    assert live.get(f"{P}/act/packages?campaign_id=KMP-017").json() == []
    assert all(p["campaign_id"] != "KMP-017" for p in live.get(f"{P}/act/packages").json())
    preds = live.get(f"{P}/oracle/predictions?campaign=NOPE").json()
    assert preds == []


def test_real_campaigns_are_polish(live):  # noqa: F811
    c = live.get(f"{P}/campaigns/KMP-001").json()
    assert "Gazeta" in c["name"] and "\n" in c["description"] and "investment" not in c["description"].lower()
    for cid in [f"KMP-00{i}" for i in range(1, 10)]:
        d = live.get(f"{P}/campaigns/{cid}").json()
        assert d["description"].count("\n") == 1 and not any(w in d["name"] for w in ("Fake", "pre-lander", "interview"))


def test_samples_list_and_analyze_mock(client):
    s = client.get(f"{P}/samples").json()
    if not s:
        pytest.skip("deploy/bundle/samples not built (deploy/make_bundle.sh)")
    assert {"dane-1", "dane-3", "dane-36", "dane-5"} <= {x["id"] for x in s}
    assert all(x["title"] and x["description"] and x["size"] > 0 for x in s)
    assert client.post(f"{P}/samples/nope/analyze").status_code == 404
    j = client.post(f"{P}/samples/dane-1/analyze").json()
    assert j["job_id"]


@needs_redis
@pytest.mark.parametrize("sid", ["dane-1", "dane-3", "dane-36", "dane-5", "p13", "p14"])
async def test_every_sample_gives_its_expected_decision(sid):
    meta = json.loads((Path(__file__).resolve().parents[3] / "deploy" / "bundle" / "samples" / "samples.json").read_text()) if (Path(__file__).resolve().parents[3] / "deploy" / "bundle" / "samples" / "samples.json").exists() else []
    m = next((x for x in meta if x["id"] == sid), None)
    if not m:
        pytest.skip("sample not in bundle")
    os.environ["TROP_NO_LIVE"] = "1"
    from trop.api.engine_adapter import ServiceAdapter
    from trop.worker import tasks
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    z = Path(__file__).resolve().parents[3] / "deploy" / "bundle" / "samples" / m["file"]
    jid = "JOB-X" + uuid.uuid4().hex[:6]
    res = await tasks.run_analysis(r, ServiceAdapter(), jid, {"kind": "zip", "name": m["file"], "paths": [str(z)]})
    dec, _, camp = m["expected"].partition(":")
    assert res["decision"] == dec, (sid, res)
    last = json.loads((await r.lrange(bus.ekey(f"job:{jid}"), 0, -1))[-1])["data"]["decision"]
    if camp:
        assert last["campaign_id"] == camp
