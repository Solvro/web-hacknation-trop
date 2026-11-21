"""POST /investigations {seed: 'incident:<id>'}: pivots derived from an analysed incident."""
import json

import pytest
import redis as sync_redis

from api.test_qa_fixes import needs_redis
from api.test_real import live  # noqa: F401
from trop.api import pivots as PV
from trop.config import settings

P = "/api/v1"


def _inc(**kw):
    base = {"landing": {}, "ad": {}, "tracking": {}, "content": {}, "media": {}}
    for k, v in kw.items():
        base[k].update(v)
    return base


def test_derive_collects_domains_advertiser_kit():
    inc = _inc(landing={"etld1": "pre-lander.click", "chain_urls": ["https://pre-lander.click/x", "https://lander-two.pro/y?z=1"]},
               ad={"advertiser": "Formal Favorable", "page_id": "123", "library_id": "999", "display_link": "OKAZJE-DNIA.COM", "cta": "Zobacz sklep-oferta.shop"},
               tracking={"kit_tenants": ["f141c307"], "fb_pixels": ["2012165449475163"]},
               content={"video_domains": ["video-lander.live"]},
               media={"video": {"gemini": {"on_screen_text": ["wejdź na nagranie-sklep.store"]}}})
    p = PV.derive(inc)
    doms = [d["domain"] for d in p["domains"]]
    assert doms[0] == "pre-lander.click" and {"lander-two.pro", "okazje-dnia.com", "sklep-oferta.shop", "video-lander.live", "nagranie-sklep.store"} <= set(doms)
    assert p["seed"] == "pre-lander.click" and p["seed_kind"] == "domain"
    assert p["advertiser"] == "Formal Favorable" and p["library_id"] == "999" and p["kit"]["kit_tenants"] == ["f141c307"]
    hs = PV.hints(p, "INC-1")
    assert all(len(h) <= 300 for h in hs) and any("adlib_search" in h for h in hs) and any("lander-two.pro" in h for h in hs)


def test_derive_screenshot_only_starts_from_advertiser_and_empty_is_none():
    p = PV.derive(_inc(ad={"advertiser": "TreeKollo", "page_id": "1183383648198728"}))
    assert p["seed_kind"] == "advertiser" and p["seed"] == "TreeKollo"
    assert PV.hints(p, "INC-2")[0].startswith("W materiale nie ma żadnej domeny")
    assert PV.derive(_inc())["seed_kind"] == "none"


def test_mock_incident_seed_resolves_domain(client):
    r = client.post(f"{P}/investigations", json={"seed": "incident:INC-24817"}).json()
    assert client.get(f"{P}/investigations/{r['id']}").json()["seed"] == "morvanta.click"


@needs_redis
def test_real_create_from_incident(live):  # noqa: F811
    r = live.post(f"{P}/investigations", json={"seed": "incident:p1", "budget_steps": 1, "offline": True})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["seed"] and d["pivots"]["domains"] and d["hints"]
    inv = live.get(f"{P}/investigations/{d['id']}").json()
    assert inv["seed"] == d["seed"] and inv["campaign_id"] == "KMP-001" and inv["budget"]["steps"] == 1
    # fresh analysed incident (not in corpus), advertiser only
    fresh = {"id": "INC-USEEDX", "ad": {"advertiser": "TreeKollo", "page_id": "1183383648198728"}, "landing": {}, "tracking": {}, "content": {}, "media": {}}
    sync_redis.Redis.from_url(settings.redis_url).set("trop:incident:INC-USEEDX", json.dumps({"incident": fresh, "decision": {}}), ex=300)
    a = live.post(f"{P}/investigations", json={"seed": "incident:INC-USEEDX", "budget_steps": 1, "offline": True}).json()
    assert a["seed"] == "TreeKollo" and a["hints"][0].startswith("W materiale nie ma")
    sync_redis.Redis.from_url(settings.redis_url).set("trop:incident:INC-UEMPTY", json.dumps({"incident": {"id": "INC-UEMPTY"}, "decision": {}}), ex=300)
    assert live.post(f"{P}/investigations", json={"seed": "incident:INC-UEMPTY"}).status_code == 422
    assert live.post(f"{P}/investigations", json={"seed": "incident:NOPE"}).status_code == 404


async def test_worker_passes_hints_as_steer_notes(monkeypatch):
    from trop.agent import service as svc
    from trop.worker import tasks
    seen = {}

    def fake_run(body, emit, investigation_id=None, control=None, **kw):
        seen["notes"] = [c["message"] for c in control.queue]
        return {"status": "done"}
    monkeypatch.setattr(svc, "run_investigation", fake_run)
    out = await tasks.agent({}, "INV-TNOTE", {"seed": "x.com"}, ["pierwsza wskazówka", "druga"])
    assert out["status"] == "done" and seen["notes"] == ["pierwsza wskazówka", "druga"]
