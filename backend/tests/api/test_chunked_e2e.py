"""Big zip (DANE folder 14, ~360 MB) through the chunk endpoints of a running API + worker. Opt-in: TROP_E2E_URL=http://127.0.0.1:18001"""
import os
import time
import zipfile
from pathlib import Path

import httpx
import pytest

from trop.config import settings

URL = os.environ.get("TROP_E2E_URL")
D14 = Path(settings.data_dir) / "raw" / "dane" / "unpacked" / "do_udostępnienia" / "14"


@pytest.mark.skipif(not URL or not D14.exists(), reason="set TROP_E2E_URL and have DANE folder 14")
def test_360mb_zip_in_8mib_chunks(tmp_path):
    z = tmp_path / "14.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as zf:
        for f in D14.rglob("*"):
            if f.is_file():
                zf.write(f, "14/" + f.relative_to(D14).as_posix())
    size = z.stat().st_size
    assert size > 300 * 1024 * 1024
    c = httpx.Client(base_url=URL + "/api/v1", timeout=60)
    up = c.post("/uploads", json={"name": "14.zip", "size": size, "kind": "zip"}).json()
    cs, slowest = up["chunk_size"], 0.0
    with open(z, "rb") as fh:
        n = 0
        while chunk := fh.read(cs):
            t = time.time()
            assert c.put(f"/uploads/{up['upload_id']}/chunks/{n}", content=chunk).status_code == 200
            slowest, n = max(slowest, time.time() - t), n + 1
    t = time.time()
    r = c.post(f"/uploads/{up['upload_id']}/complete", json={"mode": "analyze"})
    assert r.status_code == 200 and not r.json()["batch"]
    assert time.time() - t < 30 and slowest < 30
    jid = r.json()["job_id"]
    for _ in range(240):
        j = c.get(f"/jobs/{jid}").json()
        if j.get("status") in ("done", "error", "failed"):
            break
        time.sleep(2)
    assert j["status"] == "done", j
    d = c.get(f"/incidents/{j['incident_id']}/decision").json()
    assert d["decision"] == "new"
