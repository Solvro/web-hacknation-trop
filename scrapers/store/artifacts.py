"""Content-addressed artifact storage: sha256/<aa>/<bb>/<sha256>.

ARTIFACT_STORE=file://<dir>   (default: data/artifacts — inside the git-ignored data/ folder)
ARTIFACT_STORE=s3://<bucket>  + S3_ENDPOINT (host:port), S3_ACCESS_KEY, S3_SECRET_KEY, S3_SECURE=0/1
                              works with AWS S3, MinIO, SeaweedFS, Garage (any S3-compatible store)
"""
from __future__ import annotations

import io
import os
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]


def key_for(sha: str) -> str:
    return f"sha256/{sha[:2]}/{sha[2:4]}/{sha}"


class LocalStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes, sha: str, mime: str | None = None) -> str:
        p = self.root / key_for(sha)
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(p)
        return p.resolve().as_uri()

    def get(self, uri: str) -> bytes:
        return Path(urlsplit(uri).path.lstrip("/") if os.name == "nt" else urlsplit(uri).path).read_bytes()


class S3Store:
    def __init__(self, bucket: str):
        from minio import Minio  # works with any S3-compatible endpoint
        self.bucket = bucket
        self.client = Minio(os.environ.get("S3_ENDPOINT", "127.0.0.1:58333"),
                            access_key=os.environ.get("S3_ACCESS_KEY", "redpill"),
                            secret_key=os.environ.get("S3_SECRET_KEY", "redpill_dev"),
                            secure=os.environ.get("S3_SECURE", "0") == "1")
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)

    def put(self, data: bytes, sha: str, mime: str | None = None) -> str:
        key = key_for(sha)
        try:
            self.client.stat_object(self.bucket, key)
        except Exception:
            self.client.put_object(self.bucket, key, io.BytesIO(data), len(data),
                                   content_type=mime or "application/octet-stream")
        return f"s3://{self.bucket}/{key}"

    def get(self, uri: str) -> bytes:
        p = urlsplit(uri)
        r = self.client.get_object(p.netloc, p.path.lstrip("/"))
        try:
            return r.read()
        finally:
            r.close()
            r.release_conn()


def from_env():
    spec = os.environ.get("ARTIFACT_STORE", "")
    if spec.startswith("s3://"):
        return S3Store(urlsplit(spec).netloc)
    if spec.startswith("file://"):
        return LocalStore(Path(spec[len("file://"):]))
    return LocalStore(REPO_ROOT / "data" / "artifacts")
