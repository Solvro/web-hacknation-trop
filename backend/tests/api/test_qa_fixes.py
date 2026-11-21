"""QA round: files win over url, /operators, investigation create race, graph focus ids, /lab shape, SSE close, duplicate_of."""
import asyncio
import json
import uuid
from pathlib import Path

import pytest
import redis as sync_redis
import redis.asyncio as aioredis

from api.test_real import live  # noqa: F401
from trop.config import settings

P = "/api/v1"
SAMPLE = Path(settings.data_dir) / "raw" / "sample_v1" / "p1"


def _redis_ok() -> bool:
    try:
        return sync_redis.Redis.from_url(settings.redis_url).ping()
    except Exception:  # noqa: BLE001
        return False


needs_redis = pytest.mark.skipif(not _redis_ok(), reason="redis not reachable")


def test_files_win_over_prefilled_url(client):
    r = client.post(f"{P}/analyze", data={"url": "https://example.test/"}, files=[("files", ("shot.png", b"\x89PNG", "image/png"))])
    j = client.get(f"{P}/jobs/{r.json()['job_id']}").json()
    assert j["input"]["kind"] == "file" and j["input"]["name"] == "shot.png"
    u = client.post(f"{P}/analyze", data={"url": "https://example.test/"}).json()
    assert client.get(f"{P}/jobs/{u['job_id']}").json()["input"]["kind"] == "url"


def test_operators_list_mock(client):
    ops = client.get(f"{P}/operators").json()
    assert {o["id"] for o in ops} >= {"OP-03", "OP-05"} and all(o["codename"] for o in ops)
    assert [o["id"] for o in client.get(f"{P}/operators?ids=OP-03").json()] == ["OP-03"]


def test_operators_list_real(live):
    ops = live.get(f"{P}/operators").json()
    assert len(ops) >= 7 and all(o["campaigns"] for o in ops)


@needs_redis
def test_investigation_visible_immediately(live):
    r = live.post(f"{P}/investigations", json={"seed": "example.test", "budget_steps": 1, "offline": True})
    iid = r.json()["id"]
    g = live.get(f"{P}/investigations/{iid}")
    assert g.status_code == 200 and g.json()["status"] in ("running", "done")
    assert live.get(f"{P}/investigations/{iid}/stream", headers={"Accept": "text/event-stream"}, params={"replay": "live"}).status_code in (200, 404)


@needs_redis
def test_graph_focus_ids_from_the_web(live):
    for f in ("trace:kit", "trace:capi", "trace:cdn", "trace:pixel:2012165449475163", "dorquesio.click", "cert:abc", "trace:content:x", "person:Nikt"):
        r = live.get(f"{P}/graph", params={"focus": f, "origin": "p1"})
        assert r.status_code == 200, (f, r.text[:120])
        assert r.json()["focus"] and r.json()["panel"]
    # origin = freshly analysed incident that is not in the corpus
    inc = json.loads(json.dumps(live.get(f"{P}/incidents/p1").json()))
    inc.pop("decision", None), inc.pop("coverage", None)
    sync_redis.Redis.from_url(settings.redis_url).set("trop:incident:INC-UQATEST", json.dumps({"incident": inc, "decision": live.get(f"{P}/incidents/p1/decision").json()}), ex=300)
    g = live.get(f"{P}/graph", params={"focus": "trace:kit", "origin": "INC-UQATEST"})
    assert g.status_code == 200
    ids = {n["id"] for n in g.json()["nodes"]}
    assert "INC-UQATEST" in ids and any(i.startswith("trace:") for i in ids)


def test_lab_shape(live):
    d = live.get(f"{P}/lab/metrics").json()["data"]
    for k in ("bcubed_f1", "ari", "pairwise_precision", "open_set_accuracy", "wrong_links", "loco_link", "loco_not_link", "dane_open_set", "raw"):
        assert k in d, k
    assert d["bcubed_f1"] == 1.0 and d["dane_open_set"]["n"] == 9
    rows = live.get(f"{P}/lab/metrics?view=baselines").json()["data"]["rows"]
    assert rows and all("model" in r and "bcubed_f1" in r for r in rows)
    abl = live.get(f"{P}/lab/ablation").json()
    assert abl and {"layer", "delta_f1"} <= set(abl[0]) and any(r["layer"] == "tracking" and r["delta_f1"] < 0 for r in abl)


@needs_redis
async def test_job_stream_closes_after_terminal_event():
    from trop.api.realstore import RealStore
    from trop.schema import Event
    from trop.worker import bus
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    jid = "JOB-S" + uuid.uuid4().hex[:6]
    mk = lambda t, d: Event(type=t, at="2026-01-01T00:00:00Z", data=d)  # noqa: E731
    await bus.set_state(r, jid, {"id": jid, "status": "running", "input": {"kind": "url", "name": "x"}})
    await bus.publish(r, f"job:{jid}", mk("job.step", {"job_id": jid, "step": {"key": "capture"}}))
    s = RealStore()

    async def collect():
        return [e.type async for e in s.job_events(jid)]
    t = asyncio.create_task(collect())
    await asyncio.sleep(0.5)
    await bus.publish(r, f"job:{jid}", mk("job.done", {"job_id": jid}))
    assert await asyncio.wait_for(t, 5) == ["job.step", "job.done"]
    # lost terminal event: the job state alone must end the stream
    jid2 = "JOB-W" + uuid.uuid4().hex[:6]
    await bus.set_state(r, jid2, {"id": jid2, "status": "done", "input": {"kind": "url", "name": "x"}})
    await bus.publish(r, f"job:{jid2}", mk("job.step", {"job_id": jid2, "step": {"key": "capture"}}))
    types = await asyncio.wait_for((lambda: collect2(s, jid2))(), 8)
    assert types == ["job.step"]


async def collect2(s, jid):
    return [e.type async for e in s.job_events(jid)]


@needs_redis
@pytest.mark.skipif(not SAMPLE.exists(), reason="sample_v1/p1 not present")
async def test_known_item_is_marked_duplicate(tmp_path):
    import os
    os.environ["TROP_NO_LIVE"] = "1"
    from trop.api.engine_adapter import ServiceAdapter
    from trop.worker import bus, tasks
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    jid = "JOB-D" + uuid.uuid4().hex[:6]
    res = await tasks.run_analysis(r, ServiceAdapter(), jid, {"kind": "folder", "name": "p1", "paths": [str(SAMPLE / "x")] if False else [str(SAMPLE)]})
    last = json.loads((await r.lrange(bus.ekey(f"job:{jid}"), 0, -1))[-1])
    d = last["data"]["decision"]
    assert res.get("decision") == "assign" and d["duplicate_of"] == "p1"
