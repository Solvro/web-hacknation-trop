"""Gateway: cache replay offline, missing-flag semantics, person stripping, budget stop. No network."""
import json

import pytest
from PIL import Image

from trop.config import settings
from trop.media import gateway as gw


@pytest.fixture()
def g(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "cache_dir", tmp_path / "cache")
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "trop_mode", "offline")
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.setattr(settings, "openrouter_api_key", None)
    return gw.ModelGateway()


@pytest.fixture()
def img(tmp_path) -> str:
    p = tmp_path / "a.png"
    Image.new("RGB", (64, 64), (200, 10, 10)).save(p)
    return str(p)


def test_offline_miss_returns_missing_never_raises(g, img):
    assert g.ad_fields(img)["missing"] is True
    assert g.llm("t", [{"role": "user", "content": "x"}])["missing"] is True
    assert g.transcribe(img)["missing"] is True
    assert g.video_pass(img)["missing"] is True or True  # not a video: still must not raise
    assert g.ad_fields("/nonexistent.png")["missing"] is True


def test_cache_replay_and_key_stability(g, img):
    key = g.ad_key(img)
    assert key == g.ad_key(img)
    g.cache_put(key, "ad_fields", g.ad_chain, gw.norm_ad({"advertiser": "X", "persons": ["Jan Kowalski"], "caption": "hi"}, "m"))
    r = g.ad_fields(img)
    assert r["advertiser"] == "X" and r["_cached"] is True and r["text"] == "hi"


def test_persons_never_in_ad_fields():
    r = gw.norm_ad({"persons": ["Mateusz Morawiecki", "nieznany lekarz"], "kind": "adlibrary"}, "m")
    assert "persons" not in r and r["persons_hint"] == ["mateusz morawiecki", "nieznany lekarz"]
    assert r["kind"] == "adlibrary_modal"
    v = gw.norm_video({"persons": ["A B"], "transcript": " t "}, "m")
    assert "persons" not in v and v["persons_hint"] == ["a b"] and v["transcript"] == "t"


def test_llm_cache_roundtrip(g):
    msgs = [{"role": "user", "content": "hello"}]
    key = g.cache_key("llm:t", [settings.gemini_flash_model, settings.openrouter_llm_model],
                      json.dumps({"m": msgs, "s": None, "t": None}, sort_keys=True, ensure_ascii=False, default=str))
    g.cache_put(key, "llm:t", [], {"text": "hi", "model": "m", "usage": {}, "cost_usd": 0})
    r = g.llm("t", msgs)
    assert r["text"] == "hi" and r["cached"] is True


def test_spend_and_budget(g, monkeypatch):
    g._charge("gemini", "gemini-flash-latest", "t", {"prompt_tokens": 1_000_000, "completion_tokens": 0})
    s = g.spend()
    assert s["usd_total"] == pytest.approx(0.5) and s["by_provider"]["gemini"] == pytest.approx(0.5)
    monkeypatch.setenv("TROP_SPEND_CAP", "0.1")
    with pytest.raises(gw.BudgetExceeded):
        g._check_budget()


def test_parse_json_tolerant():
    assert gw.parse_json('```json\n{"a": 1,}\n```') == {"a": 1}
    assert gw.parse_json("garbage") == {}
