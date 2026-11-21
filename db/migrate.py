"""Apply pending SQL migrations from db/migrations (idempotent).

Each migration file records itself in schema_migrations, so files that already ran through
docker-entrypoint-initdb.d are skipped here.

    python db/migrate.py                 # uses DATABASE_URL or the compose default
    python db/migrate.py --status
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg

DEFAULT_URL = "postgresql://redpill:redpill_dev@127.0.0.1:55432/redpill"
MIGRATIONS = Path(__file__).resolve().parent / "migrations"


def applied_versions(conn: psycopg.Connection) -> set[str]:
    exists = conn.execute("SELECT to_regclass('schema_migrations') IS NOT NULL").fetchone()[0]
    if not exists:
        return set()
    return {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("DATABASE_URL", DEFAULT_URL))
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    files = sorted(MIGRATIONS.glob("*.sql"))
    with psycopg.connect(args.url, autocommit=False) as conn:
        done = applied_versions(conn)
        pending = [f for f in files if f.stem not in done]
        if args.status:
            for f in files:
                print(("applied " if f.stem in done else "PENDING ") + f.name)
            return 0
        for f in pending:
            print(f"applying {f.name} ...", flush=True)
            with conn.transaction():
                conn.execute(f.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO schema_migrations(version) VALUES (%s) ON CONFLICT DO NOTHING", (f.stem,)
                )
        print(f"{len(pending)} migration(s) applied; {len(files)} total.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
