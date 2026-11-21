"""DB round trip of the engine corpus. Skips when the dev DB is unreachable or not seeded."""
from __future__ import annotations

import pytest


def _db():
    try:
        from trop.store.db import connect
        with connect() as conn:
            return conn.execute("SELECT to_regclass('engine_incidents') IS NOT NULL").fetchone()[0]
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not _db(), reason="dev DB unreachable or migration 0013 not applied")
def test_load_corpus_from_db():
    from trop.store.corpus import load_corpus
    try:
        c = load_corpus()
    except LookupError:
        pytest.skip("DB not seeded")
    assert c.incidents and all(c.campaign_of[i["id"]].startswith("KMP-") for i in c.incidents)
    assert all("tracking" in i for i in c.incidents)


def test_migrations_present():
    from trop.store.db import MIGRATIONS
    names = sorted(p.name for p in MIGRATIONS.glob("*.sql"))
    assert names[0].startswith("0001") and names[-1] == "0013_trop.sql"
    sql = (MIGRATIONS / "0013_trop.sql").read_text()
    assert "DROP " not in sql.upper().replace("DROP NOT", "")   # additive only
