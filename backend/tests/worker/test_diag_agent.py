"""Worker diagnostics and the never-hang guarantees of the agent task."""
import json
import time
import uuid

import pytest
import redis

from trop.config import settings
from trop.worker import diag, tasks


@pytest.fixture()
def r():
    c = redis.Redis.from_url(settings.redis_url)
    try:
        c.ping()
    except Exception:
        pytest.skip("redis not reachable")
    return c


async def test_recorded_wrapper_logs_exception_and_error_results(r):
    async def boom(ctx, jid):
        raise ValueError("kaboom " * 80)

    async def soft(ctx, jid):
        return {"error": "swallowed"}

    jid = "T" + uuid.uuid4().hex[:6]
    with pytest.raises(ValueError):
        await diag.recorded(boom)({"job_id": jid}, jid)
    await diag.recorded(soft)({"job_id": jid + "b"}, jid + "b")
    rows = {x["job_id"]: x for x in (json.loads(v) for v in r.lrange(diag.LOG, 0, 10))}
    assert rows[jid]["status"] == "exception" and rows[jid]["exception_type"] == "ValueError" and len(rows[jid]["message"]) <= 300
    assert rows[jid + "b"]["status"] == "error" and rows[jid + "b"]["message"] == "swallowed"
    assert not r.hexists(diag.RUNNING, jid)


async def test_agent_internal_error_emits_investigation_done_error(r, monkeypatch, tmp_path):
    from trop.agent import service as svc
    from trop.worker import bus
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    iid = "INV-T" + uuid.uuid4().hex[:5]

    def broken(*a, **k):
        raise PermissionError("[Errno 13] Permission denied: '/data/investigations/x'")
    monkeypatch.setattr(svc, "run_investigation", broken)
    res = await tasks.agent({}, iid, {"seed": "example.com", "budget_steps": 3}, [])
    assert "PermissionError" in res["error"]
    evs = [json.loads(x) for x in r.lrange(bus.ekey(f"inv:{iid}"), 0, -1)]
    done = [e for e in evs if e["type"] == "investigation.done"]
    assert done and done[-1]["data"]["status"] == "error" and "Śledztwo przerwane" in done[-1]["data"]["summary"]["error"]
    r.delete(bus.ekey(f"inv:{iid}"))


def test_hung_llm_falls_back_within_the_deadline(monkeypatch):
    from trop.agent import loop
    from trop.media import gateway as G
    monkeypatch.setattr(loop, "LLM_DEADLINE_S", 0.3)
    monkeypatch.setattr(G.gateway, "llm", lambda *a, **k: time.sleep(5) or {"text": "late"})
    t = time.time()
    res = loop.default_llm("pro")([{"role": "user", "content": "x"}], [])
    assert time.time() - t < 2 and res["missing"] and "nie odpowiedział" in res["error"]


def test_first_step_is_immediate_even_if_the_model_is_dead(monkeypatch, tmp_path):
    from trop.agent import loop, service as svc
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(loop, "default_llm", lambda model="pro": (lambda m, t: {"missing": True, "error": "dead"}))
    t0, firsts = time.time(), []
    res = svc.run_investigation({"seed": "dorquesio.click", "budget_steps": 4, "offline": True},
                                lambda typ, d: typ == "agent.step" and firsts.append(time.time() - t0))
    assert firsts and firsts[0] < 10 and res["status"] in ("done", "error")
    assert res["steps"][0]["tool"] == "db_search"


def test_debug_worker_endpoint_real(r):
    from fastapi.testclient import TestClient
    from api.test_real import DATA
    if not (DATA / "corpus" / "known.json").exists():
        pytest.skip("no corpus")
    from trop.api import deps
    from trop.api.app import create_app
    prev = deps._store
    with TestClient(create_app("live")) as c:
        j = c.get("/api/v1/debug/worker").json()
    deps.set_store(prev)
    assert {"queue_length", "recent", "heartbeat", "running"} <= set(j["worker_state"]) and "spend_usd" in j["llm"]
    assert j["api"]["dirs"]["investigations"]["writable"] is True
    assert "gemini_api_key" not in json.dumps(j).lower() and "AQ." not in json.dumps(j)
