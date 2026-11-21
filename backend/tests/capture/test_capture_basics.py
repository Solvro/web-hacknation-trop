"""Capture: politeness budget, profiles, and a real local capture of a fictional page served on 127.0.0.1 (skipped without a browser)."""
import functools
import http.server
import json
import threading

import pytest

from trop.capture import politeness
from trop.capture.profiles import PROFILES


def test_profiles_present():
    assert {"fb_inapp_android_pl", "plain_headless"} <= set(PROFILES)
    assert "FB_IAB" in PROFILES["fb_inapp_android_pl"].user_agent


def test_politeness_budget_and_breaker(tmp_trop):
    got = [politeness.acquire("scam-zz.xyz")[0] for _ in range(8)]
    assert got[:6] == [True] * 6 and got[6] is False
    politeness.report("other-zz.xyz", False)
    politeness.report("other-zz.xyz", False)
    politeness.report("other-zz.xyz", False)
    ok, wait = politeness.acquire("other-zz.xyz")
    assert not ok and wait > 3000                    # 1 h cooldown after 3 consecutive failures
    politeness.report("other-zz.xyz", True)
    assert politeness.acquire("other-zz.xyz")[0]


def test_capture_url_respects_budget(tmp_trop):
    from trop.capture.cli import capture_url
    for _ in range(6):
        politeness.acquire("budget-zz.xyz")
    r = capture_url("https://budget-zz.xyz/", docker=False)
    assert not r["ok"] and "politeness" in r["error"]
    assert not capture_url("https://x-zz.xyz/", profile="nope", docker=False)["ok"]


def test_local_capture_bundle_layout(tmp_path, tmp_trop):
    pytest.importorskip("playwright")
    page = tmp_path / "www"
    page.mkdir()
    (page / "index.html").write_text("<html><head><title>Fiction</title></head><body><h1>Hello</h1><form action='/x'><input name='q'></form></body></html>")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(page))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        from trop.capture.cli import capture_url
        r = capture_url(f"http://127.0.0.1:{srv.server_address[1]}/", docker=False, out=tmp_path / "out", fast=True, force=True)
    finally:
        srv.shutdown()
    if not r["ok"]:
        pytest.skip(f"no usable chromium here: {r}")
    b = tmp_path / "out"
    bundle = next(b.glob("archive_*/"))
    for f in ("archive_info.json", "network.har", "html/rendered.html", "screenshots/viewport.png", "dns_ssl.json", "forms.json"):
        assert (bundle / f).is_file(), f
    info = json.loads((bundle / "archive_info.json").read_text())
    assert info["status"] == 200 and info["title"] == "Fiction" and info["profile"] == "fb_inapp_android_pl"
    forms = json.loads((bundle / "forms.json").read_text())
    assert forms and forms[0]["fields"][0]["name"] == "q"        # observed, never submitted
