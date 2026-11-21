"""Deploy-mode behaviour: capture setting, health fields, real-mode replay alias."""
import pytest

from trop.config import settings
from api.test_real import live  # noqa: F401,E402  (fixture shared with test_real)

P = "/api/v1"


def test_capture_mode_setting(monkeypatch):
    from trop.api import engine_adapter as ea
    monkeypatch.setattr(settings, "trop_capture", "off")
    assert ea.capture_mode() == "off" and not ea.capture_available()
    monkeypatch.setattr(settings, "trop_capture", "local")
    assert ea.capture_mode() == "local"


def test_real_health_reports_capture_and_llm(live):
    h = live.get(f"{P}/health").json()
    assert h["capture"] in ("off", "sandbox", "local") and h["llm"] in ("off", "live")


def test_real_replay_demo_is_the_live_recording(live):
    r = live.get(f"{P}/jobs/JOB-X/stream?replay=demo")
    if r.status_code == 404:
        pytest.skip("data/replay/live-analyze.jsonl not present")
    assert "KMP-001" in r.text and "KMP-017" not in r.text
