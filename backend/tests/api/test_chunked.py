"""Chunked uploads: small requests, assembled server side, same outcome as POST /analyze | /batch."""
import os
import time
import zipfile
import io

import pytest

from trop.api import chunked as CH

P = "/api/v1"


def _zip(names):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in names:
            z.writestr(n, os.urandom(40000))
    return buf.getvalue()


def _send_zip(client, data, name="x.zip", chunk=64 * 1024):
    up = client.post(f"{P}/uploads", json={"name": name, "size": len(data), "kind": "zip"})
    assert up.status_code == 200 and up.json()["chunk_size"] == CH.CHUNK
    uid = up.json()["upload_id"]
    n = 0
    for i in range(0, len(data), chunk):
        r = client.put(f"{P}/uploads/{uid}/chunks/{n}", content=data[i:i + chunk])
        assert r.status_code == 200, r.text
        n += 1
    return uid, n


@pytest.fixture()
def small(monkeypatch, tmp_path):
    monkeypatch.setattr(CH, "CHUNK", 64 * 1024)
    from trop.config import settings
    monkeypatch.setattr(settings, "artifact_dir", tmp_path)


def test_zip_in_chunks_is_idempotent_and_analyzes(client, small):
    data = _zip(["1/a.png", "1/b.html"])
    uid, n = _send_zip(client, data)
    assert client.put(f"{P}/uploads/{uid}/chunks/0", content=data[:64 * 1024]).json()["ok"]      # re-send: idempotent
    r = client.post(f"{P}/uploads/{uid}/complete", json={"mode": "analyze"})
    assert r.status_code == 200 and r.json()["job_id"] and r.json()["batch"] is False


def test_zip_of_folders_becomes_batch(client, small):
    uid, _ = _send_zip(client, _zip([f"w/{i}/a.png" for i in (1, 2, 3)]))
    r = client.post(f"{P}/uploads/{uid}/complete", json={"mode": "analyze"})
    assert r.headers.get("x-trop-batch") == "1" and r.json()["batch"] is True
    uid, _ = _send_zip(client, _zip(["1/a.png"]))
    rb = client.post(f"{P}/uploads/{uid}/complete", json={"mode": "batch"})
    assert rb.status_code == 200 and client.get(f"{P}/batch/{rb.json()['job_id']}").status_code == 200


def test_rejections(client, small):
    data = _zip(["1/a.png"])
    uid, n = _send_zip(client, data)
    assert client.put(f"{P}/uploads/{uid}/chunks/{n + 5}", content=b"x").status_code == 422
    assert client.put(f"{P}/uploads/{uid}/chunks/0", content=b"x" * (64 * 1024 + 1)).status_code == 413
    assert client.put(f"{P}/uploads/{uid}/chunks/0", content=b"short").status_code == 422
    assert client.post(f"{P}/uploads/{'0' * 16}/complete", json={}).status_code == 404
    assert client.put(f"{P}/uploads/..%2F..%2Fx/chunks/0", content=b"x").status_code == 404
    assert client.post(f"{P}/uploads", json={"kind": "zip", "size": CH.TOTAL_CAP + 1, "name": "a.zip"}).status_code == 413
    assert client.post(f"{P}/uploads", json={"kind": "tar", "size": 1}).status_code == 422
    u2 = client.post(f"{P}/uploads", json={"kind": "zip", "size": 200000, "name": "b.zip"}).json()["upload_id"]
    assert client.post(f"{P}/uploads/{u2}/complete", json={}).status_code == 409           # chunks missing


def test_folder_mode_and_traversal(client, small):
    u = client.post(f"{P}/uploads", json={"kind": "files", "size": 10, "n_files": 3, "name": "1"}).json()["upload_id"]
    bad = client.put(f"{P}/uploads/{u}/chunks/0", files=[("files", ("../evil.png", b"x", "image/png"))])
    assert bad.status_code == 400
    r = client.put(f"{P}/uploads/{u}/chunks/0", files=[("files", ("1/a.png", b"x", "image/png")), ("files", ("1/x_files/a.js", b"y", "text/plain"))])
    assert r.json()["files"] == 2
    assert client.post(f"{P}/uploads/{u}/complete", json={}).status_code == 409             # 2 of 3
    client.put(f"{P}/uploads/{u}/chunks/1", files=[("files", ("1/b.png", b"z", "image/png"))])
    ok = client.post(f"{P}/uploads/{u}/complete", json={"mode": "analyze"})
    assert ok.status_code == 200 and ok.json()["job_id"]


def test_abandoned_uploads_are_swept(client, small):
    u = client.post(f"{P}/uploads", json={"kind": "zip", "size": 10, "name": "a.zip"}).json()["upload_id"]
    d = CH.base() / u
    old = time.time() - 7 * 3600
    for f in [d, *d.rglob("*")]:
        os.utime(f, (old, old))
    assert CH.sweep() == 1 and not d.exists()
