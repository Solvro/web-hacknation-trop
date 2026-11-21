"""Chunked uploads: every request is small (<= 8 MiB), so a reverse proxy with a ~60 s request timeout never kills a big zip / folder.

Layout: <artifact_dir>/uploads/chunked/<upload_id>/  meta.json, chunks/<n> (zip mode: raw bytes), tree/ (folder mode: files at their sanitised
relative paths), chunks/<n>.json (folder mode: the relative paths a chunk carried; makes PUT idempotent).
complete() assembles (zip: concatenate the chunks into <name>; folder: the tree is already built) and returns (root, parts) for the same
single/batch decision as POST /analyze and /batch. Uploads untouched for 6 h are removed (swept on every create / complete).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path

from fastapi import HTTPException, Request

from trop.api import uploads as UP
from trop.config import settings

CHUNK = 8 * 1024 * 1024
TOTAL_CAP = 1536 * 1024 * 1024            # 1.5 GB
TTL_S = 6 * 3600
_ID = re.compile(r"^[0-9a-f]{16}$")


def base() -> Path:
    return Path(settings.artifact_dir) / "uploads" / "chunked"


def _dir(upload_id: str) -> Path:
    if not _ID.match(upload_id or ""):
        raise HTTPException(404, "unknown upload")
    d = base() / upload_id
    if not (d / "meta.json").is_file():
        raise HTTPException(404, "unknown upload (expired?)")
    return d


def _meta(d: Path) -> dict:
    return json.loads((d / "meta.json").read_text(encoding="utf-8"))


def _used(d: Path) -> int:
    return sum(f.stat().st_size for f in d.rglob("*") if f.is_file() and f.name != "meta.json")


def sweep(ttl: float = TTL_S) -> int:
    n, now = 0, time.time()
    if base().is_dir():
        for d in base().iterdir():
            try:
                if d.is_dir() and now - max(f.stat().st_mtime for f in [d, *d.rglob("*")]) > ttl:
                    shutil.rmtree(d, ignore_errors=True)
                    n += 1
            except OSError:
                pass
    return n


def create(body: dict) -> dict:
    sweep()
    kind = body.get("kind")
    if kind not in ("zip", "files"):
        raise HTTPException(422, "kind must be zip | files")
    try:
        size = int(body.get("size") or 0)
        n_files = int(body.get("n_files") or 0)
    except (TypeError, ValueError):
        raise HTTPException(422, "size / n_files must be numbers")
    if size < 0 or (kind == "zip" and size <= 0):
        raise HTTPException(422, "size required")
    if size > TOTAL_CAP:
        raise HTTPException(413, f"upload too large (max {TOTAL_CAP >> 20} MiB)")
    if n_files > UP.MAX_FILES:
        raise HTTPException(413, f"too many files (max {UP.MAX_FILES})")
    name = "upload.zip"
    if kind == "zip":
        try:
            parts = UP.clean_rel(str(body.get("name") or "upload.zip"))
        except UP.BadPath as e:
            raise HTTPException(400, str(e))
        name = parts[-1] if parts else "upload.zip"
    uid = uuid.uuid4().hex[:16]
    d = base() / uid
    (d / "chunks").mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"name": name, "size": size, "kind": kind, "n_files": n_files, "created": time.time()}), encoding="utf-8")
    return {"upload_id": uid, "chunk_size": CHUNK, "total_chunks": -(-size // CHUNK) if kind == "zip" else None}


async def put_chunk(upload_id: str, n: int, request: Request) -> dict:
    import asyncio
    d = _dir(upload_id)
    m = _meta(d)
    if n < 0 or n > 100000:
        raise HTTPException(422, "bad chunk number")
    if (request.headers.get("content-type") or "").startswith("multipart/"):
        if m["kind"] != "files":
            raise HTTPException(415, "multipart chunks are for folder uploads; send the raw body for a zip")
        return await _put_files(d, m, n, request)
    if m["kind"] != "zip":
        raise HTTPException(415, "folder uploads send multipart `files` parts")
    total_chunks = -(-m["size"] // CHUNK)
    if n >= total_chunks:
        raise HTTPException(422, f"chunk {n} out of range (0..{total_chunks - 1})")
    final = d / "chunks" / str(n)
    tmp = d / "chunks" / f".{n}.part"
    got = 0
    with open(tmp, "wb") as out:
        async for b in request.stream():
            got += len(b)
            if got > CHUNK:
                out.close()
                tmp.unlink(missing_ok=True)
                raise HTTPException(413, f"chunk larger than {CHUNK} bytes")
            await asyncio.to_thread(out.write, b)
    expect = CHUNK if n < total_chunks - 1 else m["size"] - CHUNK * (total_chunks - 1)
    if got != expect:
        tmp.unlink(missing_ok=True)
        raise HTTPException(422, f"chunk {n} has {got} bytes, expected {expect}")
    os.replace(tmp, final)                      # idempotent: a re-sent chunk simply replaces itself
    return {"ok": True, "chunk": n, "bytes": got, "received": len([f for f in (d / "chunks").iterdir() if f.name.isdigit()]), "total_chunks": total_chunks}


async def _put_files(d: Path, m: dict, n: int, request: Request) -> dict:
    import asyncio
    form = await request.form(max_files=2000, max_fields=2000)
    files = form.getlist("files")
    tree, got, paths = d / "tree", 0, []
    used = await asyncio.to_thread(_used, d)
    for f in files:
        try:
            p = UP.clean_rel(getattr(f, "filename", "") or "")
        except UP.BadPath as e:
            raise HTTPException(400, str(e))
        if not p:
            continue
        dest = tree.joinpath(*p)
        dest.parent.mkdir(parents=True, exist_ok=True)
        old = dest.stat().st_size if dest.is_file() else 0
        await asyncio.to_thread(_copy, f.file, dest)
        got += dest.stat().st_size
        used += dest.stat().st_size - old
        if used > TOTAL_CAP:
            shutil.rmtree(d, ignore_errors=True)
            raise HTTPException(413, f"upload too large (max {TOTAL_CAP >> 20} MiB)")
        paths.append(p)
    (d / "chunks" / f"{n}.json").write_text(json.dumps(paths), encoding="utf-8")
    return {"ok": True, "chunk": n, "files": len(paths), "bytes": got, "received": len(list((d / "chunks").glob("*.json")))}


def _copy(src, dest: Path) -> None:
    with open(dest, "wb") as out:
        shutil.copyfileobj(src, out, 1 << 20)


def assemble(upload_id: str) -> tuple[Path, list[list[str]]]:
    """-> (root dir, relative path segments of every file). Raises 409 when chunks are missing / sizes disagree."""
    d = _dir(upload_id)
    m = _meta(d)
    sweep()
    if m["kind"] == "zip":
        total = -(-m["size"] // CHUNK)
        have = {int(f.name) for f in (d / "chunks").iterdir() if f.name.isdigit()}
        missing = [i for i in range(total) if i not in have]
        if missing:
            raise HTTPException(409, f"missing chunks: {missing[:10]}")
        root = d / "assembled"
        root.mkdir(exist_ok=True)
        dest = root / m["name"]
        with open(dest, "wb") as out:
            for i in range(total):
                with open(d / "chunks" / str(i), "rb") as c:
                    shutil.copyfileobj(c, out, 1 << 20)
        if dest.stat().st_size != m["size"]:
            raise HTTPException(409, "assembled size differs from the declared size")
        shutil.rmtree(d / "chunks", ignore_errors=True)
        return root, [[m["name"]]]
    tree = d / "tree"
    parts: dict[str, list[str]] = {}
    for j in sorted((d / "chunks").glob("*.json")):
        for p in json.loads(j.read_text(encoding="utf-8")):
            parts["/".join(p)] = p
    if not parts:
        raise HTTPException(422, "no files received")
    if m.get("n_files") and len(parts) < m["n_files"]:
        raise HTTPException(409, f"only {len(parts)} of {m['n_files']} files received")
    return tree, list(parts.values())
