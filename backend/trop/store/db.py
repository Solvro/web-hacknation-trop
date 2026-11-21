"""Postgres access (psycopg 3) + migrations from backend/migrations (idempotent, recorded in schema_migrations)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import psycopg

from trop.config import settings

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


def url() -> str:
    return os.environ.get("DATABASE_URL") or settings.database_url


def connect(autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(url(), autocommit=autocommit)


def applied(conn) -> set[str]:
    if not conn.execute("SELECT to_regclass('schema_migrations') IS NOT NULL").fetchone()[0]:
        return set()
    return {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}


def status() -> list[tuple[str, bool]]:
    with connect() as conn:
        done = applied(conn)
    return [(f.name, f.stem in done) for f in sorted(MIGRATIONS.glob("*.sql"))]


def migrate() -> list[str]:
    files = sorted(MIGRATIONS.glob("*.sql"))
    ran = []
    with connect() as conn:
        if not conn.execute("SELECT to_regclass('schema_migrations') IS NOT NULL").fetchone()[0]:
            conn.execute("CREATE TABLE schema_migrations (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
        done = applied(conn)
        for f in files:
            if f.stem in done:
                continue
            with conn.transaction():
                conn.execute(f.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations(version) VALUES (%s) ON CONFLICT DO NOTHING", (f.stem,))
            ran.append(f.name)
        conn.commit()
    return ran


def dump(out: Path) -> Path:
    """pg_dump -Fc snapshot (backup before migrating; judges' seed)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["pg_dump", "-Fc", "-d", url(), "-f", str(out)], check=True)
    return out
