"""Real mode (engine corpus + Redis + arq jobs). Skips without the corpus data / Redis / DANE folder."""
import asyncio
import shutil
import uuid
from pathlib import Path

import pytest
import redis.asyncio as aioredis
from fastapi.testclient import TestClient

from trop.api import deps
from trop.config import settings

DATA = Path(settings.data_dir)
DANE1 = DATA / "raw" / "dane" / "unpacked" / "do_udostępnienia" / "1"
P = "/api/v1"


@pytest.fixture()
def live():
    if not (DATA / "raw" / "sample_v1").exists() and not (DATA / "corpus" / "known.json").exists():
        pytest.skip("no organizer corpus under DATA_DIR")
    from trop.api.app import create_app
    prev = deps._store
    with TestClient(create_app("live")) as c:
        yield c
    deps.set_store(prev)


def test_real_campaigns_have_no_fiction(live):
    cs = live.get(f"{P}/campaigns").json()
    ids = {c["id"] for c in cs}
    assert "KMP-001" in ids and "KMP-017" not in ids and not any("Zamach" in c["name"] for c in cs)
    assert all(c["id"].startswith("KMP-0") for c in cs)
    assert live.get(f"{P}/health").json()["db"] != "mock"


def test_real_campaign_resources(live):
    assert live.get(f"{P}/campaigns/KMP-001").json()["n_incidents"] >= 1
    assert live.get(f"{P}/campaigns/KMP-001/dna").json()["signature"]
    assert live.get(f"{P}/campaigns/KMP-001/members").json()
    assert live.get(f"{P}/campaigns/KMP-001/indicators").json()["domains"]
    assert live.get(f"{P}/operations").json()
    g = live.get(f"{P}/graph?focus=KMP-001").json()
    assert g["focus"] == "KMP-001" and g["panel"]
    assert live.get(f"{P}/campaigns/KMP-999").status_code == 404


def test_real_incident_decision_link(live):
    d = live.get(f"{P}/incidents/p1/decision").json()
    assert d["model_version"].startswith("engine@") and d["decision"] in ("assign", "confirm", "new", "ambiguous", "insufficient")
    inc = live.get(f"{P}/incidents/p1").json()
    assert inc["source"]["path"] is None          # local paths never leave the server
    assert live.get(f"{P}/links/p1/KMP-001").json()["decision"] in ("linked", "not_linked", "triage")
    assert live.get(f"{P}/incidents/NOPE").status_code == 404


def test_real_unwired_is_501_not_mock(live):
    r = live.get(f"{P}/oracle/predictions")
    assert r.status_code == 501 and "KMP-017" not in r.text


def test_real_lab_metrics_from_eval(live, tmp_path, monkeypatch):
    p = Path(settings.cache_dir) / "lab_eval.json"
    if not p.exists():
        pytest.skip("run `trop eval --json data/cache/lab_eval.json` first")
    assert live.get(f"{P}/lab/metrics").json()["data"]["source"] == "trop eval"


async def _redis():
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await r.ping()
    except Exception:
        pytest.skip("redis not reachable")
    return r


@pytest.mark.skipif(not DANE1.exists(), reason="DANE folder 1 not present")
async def test_g2_dane_folder_zip_assigns_kmp001(tmp_path):
    """Gate G2: DANE folder 1 (zip) -> six bots -> assign KMP-001, offline, < 60 s."""
    import os
    os.environ["TROP_NO_LIVE"] = "1"
    from trop.api.engine_adapter import ServiceAdapter
    from trop.worker import bus, tasks
    r = await _redis()
    z = shutil.make_archive(str(tmp_path / "dane1"), "zip", DANE1.parent, "1")
    jid = "JOB-G2" + uuid.uuid4().hex[:6]
    got = []

    async def listen():
        async for ev in bus.subscribe(r, f"job:{jid}"):
            got.append(ev)
    lt = asyncio.create_task(listen())
    await asyncio.sleep(0.2)
    res = await asyncio.wait_for(tasks.run_analysis(r, ServiceAdapter(), jid, {"kind": "zip", "name": "dane1.zip", "paths": [z]}), 60)
    await asyncio.wait_for(lt, 10)
    assert res["decision"] == "assign"
    done = got[-1]
    assert done.type == "job.done" and done.data["decision"]["campaign_id"] == "KMP-001" and done.data["job_id"] == jid
    steps = [e.data["step"]["key"] for e in got if e.type == "job.step" and e.data["step"]["status"] == "run"]
    assert steps == ["capture", "tracking", "content", "infra", "compare", "verdict"]
    assert all(e.data.get("job_id") == jid for e in got)
    assert any(e.type == "job.evidence" for e in got) and any(e.type == "job.ranking" for e in got)


async def test_url_without_capture_is_job_error():
    import os
    os.environ["TROP_NO_LIVE"] = "1"
    from trop.api.engine_adapter import ServiceAdapter
    from trop.worker import bus, tasks
    r = await _redis()
    jid = "JOB-U" + uuid.uuid4().hex[:6]
    res = await tasks.run_analysis(r, ServiceAdapter(), jid, {"kind": "url", "name": "https://down.test/", "paths": []})
    assert "error" in res
    evs = await r.lrange(bus.ekey(f"job:{jid}"), 0, -1)
    assert sum('"job.error"' in e for e in evs) == 1
    assert (await bus.get_state(r, jid))["status"] == "error"
