import json

import pytest

pytest.importorskip("playwright")
from trop.capture import render  # noqa: E402

HTML = """<!doctype html><html><head><meta charset=utf-8><title>x</title></head><body>
<h1>Fikcyjna Ekstra Oferta</h1>
<img src="face.png" width="300" height="300" alt="hero">
<script src="https://connect.facebook.net/en_US/fbevents.js"></script>
<img src="https://evil.example/pixel.gif" width=1 height=1>
<form action="/send" method="post"><input name="phone" type="tel"><button>OK</button></form>
<iframe src="https://evil.example/frame" width="200" height="100"></iframe>
</body></html>"""


def _fixture(tmp_path):
    from PIL import Image
    d = tmp_path / "page"
    d.mkdir()
    Image.new("RGB", (300, 300), (200, 120, 90)).save(d / "face.png")
    (d / "page.html").write_text(HTML, encoding="utf-8")
    return d


def test_render_saved_boxes_and_no_network(tmp_path):
    d = _fixture(tmp_path)
    r = render.render_saved(d, tmp_path / "o.png")
    assert r["ok"], r
    kinds = {b["kind"] for b in r["boxes"]}
    assert {"headline", "form", "input", "iframe", "image"} <= kinds
    assert r["blocked_requests"] >= 2                      # pixel + iframe (+ script) never leave the machine
    assert any(m["marker"] == "connect.facebook.net" for m in r["markers"])
    assert (tmp_path / "o.png").stat().st_size > 500
    head = next(b for b in r["boxes"] if b["kind"] == "headline")
    assert "Fikcyjna" in head["text"] and head["w"] > 10


def test_render_for_upload_and_missing(tmp_path):
    d = _fixture(tmp_path)
    r = render.render_for_upload(d)
    assert r and r["boxes"] and r["w"] == 1280
    assert render.render_for_upload(tmp_path / "nope") is None


def test_ensure_landing_screenshot_writes_webp_and_boxes(tmp_path):
    d = _fixture(tmp_path)
    out = tmp_path / "out"
    r = render.ensure_landing_screenshot(d, "x1", out)
    assert r and (out / "x1.webp").is_file()
    assert json.loads((out / "x1.boxes.json").read_text())["boxes"]
    assert render.ensure_landing_screenshot(d, "x1", out)["cached"]
