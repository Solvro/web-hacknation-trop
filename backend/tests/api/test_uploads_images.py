"""Folder uploads (multipart relative paths), screenshots served as artifacts, person usage facts."""
import io
import os
import unicodedata
import zipfile
from pathlib import Path

import pytest

from api.test_real import live  # noqa: F401
from trop.api import images
from trop.api import uploads as UP
from trop.config import settings

P = "/api/v1"
DANE = Path(settings.data_dir) / "raw" / "dane" / "unpacked" / "do_udostępnienia"
needs_dane = pytest.mark.skipif(not (DANE / "1").exists(), reason="DANE folders not present")


def _parts(folder: Path, prefix: str):
    out = []
    for f in sorted(folder.rglob("*")):
        if f.is_file():
            out.append(("files", (f"{prefix}/{f.relative_to(folder).as_posix()}", f.read_bytes(), "application/octet-stream")))
    return out


def test_clean_rel_and_plan():
    assert UP.clean_rel("1\\a\\b.png") == ["1", "a", "b.png"]
    assert UP.clean_rel(unicodedata.normalize("NFD", "do_udostępnienia/Zrzut ś.png")) == ["do_udostępnienia", "Zrzut ś.png"]
    assert UP.clean_rel("C:/x/y.png") == ["x", "y.png"]
    assert UP.clean_rel("__MACOSX/1/a") == []
    for bad in ("../x", "a/../../b", ""):
        with pytest.raises(UP.BadPath):
            UP.clean_rel(bad)
    one = [["1", "x.png"], ["1", "x.html"], ["1", "x_files", "a.js"]]
    assert UP.plan(one) == ("single", ["1"])
    many = [[w, "a.png"] for w in ("1", "2", "3")]
    assert UP.plan(many) == ("batch", [])
    wrapped = [["do_udostępnienia", w, "a.png"] for w in ("1", "2")] + [["do_udostępnienia", "1", "x_files", "a.js"]]
    assert UP.plan(wrapped) == ("batch", ["do_udostępnienia"])
    assert UP.plan([["a.png"]]) == ("single", [])
    assert UP.plan([["only", "a.png"]]) == ("single", ["only"])


def test_traversal_is_rejected(client):
    r = client.post(f"{P}/analyze", files=[("files", ("../evil.png", b"x", "image/png"))])
    assert r.status_code == 400


@needs_dane
async def test_folder_sent_file_by_file_is_one_incident_and_assigns_kmp001(client, monkeypatch):
    from trop.api.engine_adapter import Material, ServiceAdapter
    from trop.api.mockstore import MockStore
    seen = {}
    monkeypatch.setattr(MockStore, "analyze", lambda self, kind, name, saved=None: seen.update(kind=kind, name=name, saved=saved) or
                        type("R", (), {"job_id": "JOB-X", "trace": None, "incident_id": None, "model_copy": lambda s, **k: s})())
    r = client.post(f"{P}/analyze", files=_parts(DANE / "1", "1"))
    assert r.status_code == 200 and "x-trop-batch" not in r.headers
    assert seen["kind"] == "folder" and seen["name"] == "1" and Path(seen["saved"][0]).is_dir()
    assert (Path(seen["saved"][0]) / "Zrzut ekranu 2026-10-09 082411.png").exists()
    os.environ["TROP_NO_LIVE"] = "1"
    ev = []
    dec = ServiceAdapter().analyze(Material(job_id="JOB-UP1", kind="folder", name="1", paths=seen["saved"]), lambda t, d: ev.append(t))
    assert dec.decision == "assign" and dec.campaign_id == "KMP-001" and ev[-1] == "job.done"


@needs_dane
def test_several_folders_and_wrapper_zip_become_a_batch(client):
    files = _parts(DANE / "1", "1") + _parts(DANE / "3", "3")
    r = client.post(f"{P}/analyze", files=files)
    assert r.status_code == 200 and r.headers.get("x-trop-batch") == "1" and r.json()["job_id"]
    b = client.get(f"{P}/batch/{r.json()['job_id']}")
    assert b.status_code == 200
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in ("do_udostępnienia/1/a.png", "do_udostępnienia/2/a.png", "do_udostępnienia/3/a.png"):
            z.writestr(n, b"x")
    r2 = client.post(f"{P}/analyze", files=[("files", ("DANE.zip", buf.getvalue(), "application/zip"))])
    assert r2.headers.get("x-trop-batch") == "1"
    buf1 = io.BytesIO()
    with zipfile.ZipFile(buf1, "w") as z:
        z.writestr("1/a.png", b"x")
        z.writestr("1/a_files/b.js", b"x")
    r3 = client.post(f"{P}/analyze", files=[("files", ("one.zip", buf1.getvalue(), "application/zip"))])
    assert "x-trop-batch" not in r3.headers
    rb = client.post(f"{P}/batch", files=_parts(DANE / "1", "1"))          # a single folder is a batch of one
    assert rb.status_code == 200
    assert client.get(f"{P}/batch/{rb.json()['job_id']}").json()["n_items"] >= 1


def test_images_store_list_and_serve(tmp_path, monkeypatch, live):  # noqa: F811
    monkeypatch.setattr(images, "images_dir", lambda: tmp_path)
    inc = live.get(f"{P}/incidents/p1").json()                         # sanitised: no local paths
    assert inc["ad"]["screenshot_path"] is None and inc["ad"]["screenshots"] == []
    from trop.engine import service
    raw = service.Corpus.load().get("p1")
    meta = images.store("p1", raw)
    if not meta:
        pytest.skip("sample_v1 screenshot not present")
    refs = live.get(f"{P}/incidents/p1/artifacts").json()
    assert refs and refs[0]["role"] == "ad_screenshot" and refs[0]["w"] <= 1200 and refs[0]["url"].startswith("/api/v1/artifacts/")
    assert str(Path(settings.data_dir)) not in json_dump(refs)
    r = live.get(refs[0]["url"].replace("/api/v1", P) if False else refs[0]["url"])
    assert r.status_code == 200 and r.headers["content-type"] == "image/webp" and r.content[:4] == b"RIFF"
    assert live.get(f"{P}/artifacts/nope--ad_screenshot--0").status_code == 404
    assert live.get(f"{P}/artifacts/..%2F..%2Fetc--x--0").status_code == 404


def json_dump(x):
    import json
    return json.dumps(x)


def test_artifacts_mock_shape(client):
    refs = client.get(f"{P}/incidents/INC-24817/artifacts").json()
    assert {r["role"] for r in refs} == {"ad_screenshot", "landing_screenshot"} and all(r["w"] and r["h"] for r in refs)
    assert client.get(refs[0]["url"]).status_code == 200


def test_live_capture_boxes_are_scaled_with_the_image(tmp_path):
    from PIL import Image
    shots = tmp_path / "b" / "screenshots"
    shots.mkdir(parents=True)
    Image.new("RGB", (2400, 1000), "white").save(shots / "full_page.png")
    (shots / "full_page.boxes.json").write_text('{"boxes": [{"kind": "form", "x": 240, "y": 100, "w": 480, "h": 50}]}')
    meta = images.store("INC-Ux", {"landing": {"screenshot_path": str(shots / "full_page.png")}}, tmp_path / "out", src=tmp_path / "b")
    assert meta[0]["w"] == 1200 and meta[0]["boxes"][0] == {"kind": "form", "x": 120, "y": 50, "w": 240, "h": 25}


def test_public_check_known_domain_is_scam_without_capture(live):  # noqa: F811
    from trop.engine import service
    corpus = service.Corpus.load()
    inc = next(i for i in corpus.incidents if (i.get("landing") or {}).get("host") and corpus.campaign_of.get(i["id"]))
    host = inc["landing"]["host"]
    j = live.post(f"{P}/public/check", data={"url": f"https://{host}/"}).json()
    assert j["verdict"] == "scam" and "domena znana z kampanii oszustwa" in j["public_campaign"]["reasons"]
    assert "KMP" not in json_dump(j) and host not in json_dump(j)
    m = live.post(f"{P}/public/extension/match", json={"cta_url": f"https://{host}/x"})
    assert m.status_code == 200 and m.json()["match"] is True
    assert live.post(f"{P}/public/check", data={"url": "https://zupelnie-nieznana-domena-xyz.pl/"}).json()["verdict"] == "unknown"


def test_person_trace_facts_mock(client):
    t = client.get(f"{P}/traces/person/Jan Kowalski").json()
    assert t["facts"]["campaigns"] and t["facts"]["text"] and t["facts"]["captions"]


def test_person_trace_facts_real(live):  # noqa: F811
    from trop.engine import service
    corpus = service.Corpus.load()
    name = next((p for i in corpus.incidents for p in (i.get("content") or {}).get("persons") or []), None)
    if not name:
        pytest.skip("no persons in corpus")
    t = live.get(f"{P}/traces/person/{name}")
    assert t.status_code == 200
    f = t.json()["facts"]
    assert f["incidents"] >= 1 and f["campaigns"] and f["text"] and f["first_seen"]
