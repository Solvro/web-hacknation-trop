"""Production QA round: persistence across restarts, zombies, signals, Polish act texts, idempotent packages, image check."""
import io
import json
import os
import time
import uuid

import pytest
import redis

from api.test_real import live  # noqa: F401
from trop.config import settings
from trop.schema import Decision
from trop.worker import bus, persist

P = "/api/v1"


@pytest.fixture()
def r():
    c = redis.Redis.from_url(settings.redis_url)
    try:
        c.ping()
    except Exception:
        pytest.skip("redis not reachable")
    return c


async def test_job_and_events_survive_a_redis_wipe(r, tmp_path, monkeypatch):
    import redis.asyncio as aioredis
    from trop.schema import Event
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    jid = "JOB-P" + uuid.uuid4().hex[:8]
    ar = aioredis.from_url(settings.redis_url, decode_responses=True)
    await bus.set_state(ar, jid, {"id": jid, "status": "done", "input": {"kind": "url", "name": "x"}, "incident_id": "INC-UP1", "decision": "new"})
    await bus.publish(ar, f"job:{jid}", Event(type="job.step", at="2026-01-01T00:00:00Z", data={"job_id": jid}))
    await bus.publish(ar, f"job:{jid}", Event(type="job.done", at="2026-01-01T00:00:01Z", data={"job_id": jid}))
    await ar.delete(f"trop:job:{jid}:state", bus.ekey(f"job:{jid}"))                 # = Redis restarted without snapshots
    await ar.zrem("trop:jobs", jid)
    st = await bus.get_state(ar, jid)
    assert st and st["incident_id"] == "INC-UP1"
    await ar.delete(bus.ekey(f"job:{jid}"))
    got = [e.type async for e in bus.follow(ar, f"job:{jid}")]
    assert got == ["job.step", "job.done"]
    await ar.delete(f"trop:job:{jid}:state", bus.ekey(f"job:{jid}"))
    await ar.zrem("trop:jobs", jid)
    await ar.aclose()


def test_incident_files_and_realstore_fallback(live, r, tmp_path, monkeypatch):  # noqa: F811
    from trop.api.engine_adapter import _remember
    from trop.engine import service
    monkeypatch.setattr(persist, "incidents_dir", lambda: tmp_path)
    corpus = service.Corpus.load()
    inc = json.loads(json.dumps(corpus.incidents[0]))
    inc["id"] = "INC-UPERS1"
    dec, _ = service.analyze_incident(inc, corpus)
    assert dec.decision in ("new", "assign", "confirm", "ambiguous", "insufficient")
    _remember(inc, dec)
    assert persist.load_incident("INC-UPERS1")["decision"]["incident_id"] == "INC-UPERS1"
    r.delete("trop:incident:INC-UPERS1")                                               # Redis wiped
    assert live.get(f"{P}/incidents/INC-UPERS1").status_code == 200
    assert live.get(f"{P}/incidents/INC-UPERS1/decision").status_code == 200
    r.delete("trop:incident:INC-UPERS1")


def test_stale_investigations_are_reaped(tmp_path, monkeypatch):
    from trop.agent import service as svc
    from trop.schema import Investigation
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    old = Investigation(id="INV-901", seed="a.pl", status="running", budget={"steps": 5.0, "used": 0.0, "usd": 1.0, "usd_used": 0.0}, started_at="2026-01-01T00:00:00+00:00")
    new = Investigation(id="INV-902", seed="b.pl", status="running", budget={"steps": 5.0, "used": 0.0, "usd": 1.0, "usd_used": 0.0}, started_at="2026-01-01T00:00:00+00:00")
    svc._save(old)
    svc._save(new)
    p = svc._dir("INV-901") / "investigation.json"
    t = time.time() - 3600
    os.utime(p, (t, t))
    assert svc.reap_stale(publish=False) == ["INV-901"]
    assert svc.get_investigation("INV-901").status == "error" and svc.get_investigation("INV-902").status == "running"
    last = svc.events("INV-901")[-1]
    assert last["type"] == "investigation.done" and "restart serwera" in last["data"]["summary"]["error"]


def test_signals_none_for_a_url_without_any_overlap():
    from trop.api.engine_adapter import no_signals
    dec = Decision(incident_id="INC-U1", decision="new")
    assert no_signals({"tracking": {}, "content": {}, "infra": {}}, dec) is True
    assert no_signals({"tracking": {"fb_pixels": ["123"]}}, dec) is False
    assert no_signals({}, Decision(incident_id="x", decision="assign", campaign_id="KMP-001")) is False


def test_polish_plurals_and_vertical():
    from trop.act import pl
    assert [pl.n_domains(n) for n in (1, 4, 5, 12, 22, 0)] == ["1 domena", "4 domeny", "5 domen", "12 domen", "22 domeny", "0 domen"]
    assert pl.n_ads(1) == "1 reklama" and pl.n_ads(3) == "3 reklamy" and pl.n_ads(46) == "46 reklam"
    assert pl.vertical_pl("investment") == "inwestycje"


def test_act_texts_use_polish_name_and_plurals(live, tmp_path, monkeypatch):  # noqa: F811
    from trop.act import notice, pl
    d = {"id": "KMP-001", "name": "Gazeta", "narrative": "x", "vertical": "investment", "fictional": False,
         "counts": {"ads": 1, "advertisers": 2, "domains": 4, "incidents": 3}, "ads": [], "evidence": [{"display": "e", "members_with": 1, "members_total": 2}], "persons": [], "brands": []}
    d = pl.polish_dossier(d)
    assert d["vertical"] == "inwestycje" and "Zyskarnia" in d["name"] and "investment" not in json.dumps(d, ensure_ascii=False)
    txt = notice.template_notice(d)
    assert "1 reklama" in txt and "2 konta reklamodawców" in txt and "4 domeny" in txt
    assert "4 domeny" in notice.certpl_text(d, [{"fqdn": "a"}] * 4) and "1 domena" in notice.certpl_text(d, [{"fqdn": "a"}])


def test_act_create_is_idempotent_mock(client):
    a = client.post(f"{P}/act/packages", json={"campaign_id": "KMP-017", "kind": "dsa"}).json()
    b = client.post(f"{P}/act/packages", json={"campaign_id": "KMP-017", "kind": "dsa"}).json()
    assert a["id"] == b["id"]
    c = client.post(f"{P}/act/packages", json={"campaign_id": "KMP-017", "kind": "certpl"}).json()
    assert c["id"] != a["id"]


def test_samples_have_a_polish_expected_label(client):
    s = {x["id"]: x for x in client.get(f"{P}/samples").json()}
    if "dane-5" in s:
        assert s["dane-5"]["expected_label"] == "nowa kampania (kandydat)"


def _png():
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (200, 300), "white").save(b, "PNG")
    return b.getvalue()


def test_public_check_accepts_an_image(live, monkeypatch):  # noqa: F811
    r1 = live.post(f"{P}/public/check", files={"image": ("reklama.png", _png(), "image/png")})
    assert r1.status_code == 200 and r1.json()["verdict"] in ("scam", "unknown")
    r2 = live.post(f"{P}/public/check", files={"image": ("x.png", b"not an image", "image/png")})
    assert r2.status_code == 422
