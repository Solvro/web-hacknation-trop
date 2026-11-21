"""CERT Polska warning list sync (API v2) → certpl_domains (+ history) and obs_domains.certpl_listed_at.

    python -m scrapers.enrich.certpl            # conditional GET of domains.json (falls back to domains.txt)

v2 records: {RegisterPositionId, DomainAddress, InsertDate, DeleteDate}; DeleteDate != null ⇒ delisted.
The job cursor keeps ETag/Last-Modified, so the 10-minute schedule only downloads when the list changed.
Licence: any use incl. commercial; attribution optional and must not imply endorsement (cert.pl).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime

import httpx
from psycopg.types.json import Jsonb

from ..store.db import Loader, connect
from ..store import artifacts
from ..util.hashing import sha256_bytes
from ..util.urls import etld1_of
from .http import USER_AGENT

JSON_URL = "https://hole.cert.pl/domains/v2/domains.json"
TXT_URL = "https://hole.cert.pl/domains/v2/domains.txt"


def _dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch(cursor: dict) -> tuple[int, bytes | None, dict, str]:
    headers = {"User-Agent": USER_AGENT}
    if cursor.get("etag"):
        headers["If-None-Match"] = cursor["etag"]
    if cursor.get("last_modified"):
        headers["If-Modified-Since"] = cursor["last_modified"]
    with httpx.Client(timeout=120, follow_redirects=True) as c:
        for url in (JSON_URL, TXT_URL):
            try:
                r = c.get(url, headers=headers)
            except httpx.HTTPError:
                continue
            if r.status_code == 304:
                return 304, None, cursor, url
            if r.status_code == 200:
                new = {"etag": r.headers.get("etag"), "last_modified": r.headers.get("last-modified"), "url": url}
                return 200, r.content, new, url
    raise RuntimeError("CERT PL list unreachable")


def parse(body: bytes, url: str) -> list[dict]:
    if url.endswith(".json"):
        data = json.loads(body)
        rows = data if isinstance(data, list) else data.get("domains") or data.get("data") or []
        return [{"domain": str(r.get("DomainAddress", "")).strip().lower().rstrip("."),
                 "insert": _dt(r.get("InsertDate")), "delete": _dt(r.get("DeleteDate")),
                 "pos": r.get("RegisterPositionId")} for r in rows if r.get("DomainAddress")]
    return [{"domain": l.strip().lower(), "insert": None, "delete": None, "pos": None}
            for l in body.decode("utf-8", errors="ignore").splitlines() if l.strip() and not l.startswith("#")]


def sync(conn, force: bool = False) -> dict:
    loader = Loader(conn, artifacts.from_env(), sensitivity="public")
    job = conn.execute("SELECT id, cursor FROM jobs WHERE key = 'certpl_sync'").fetchone()
    cursor = {} if force or not job else (job[1] or {})
    run_id = loader.start_run("certpl", trigger="manual", params={"force": force}, job_key="certpl_sync")
    conn.commit()
    t0 = time.time()
    status, body, new_cursor, url = fetch(cursor)
    if status == 304:
        loader.finish_run(run_id, "ok", {"not_modified": True}, cursor_after=new_cursor)
        conn.commit()
        return {"not_modified": True}
    rows = parse(body, url)
    sha = sha256_bytes(body)
    with conn.cursor() as cur:
        cur.execute("CREATE TEMP TABLE _certpl (domain text, etld1 text, ins timestamptz, del timestamptz, pos bigint) ON COMMIT DROP")
        with cur.copy("COPY _certpl (domain, etld1, ins, del, pos) FROM STDIN") as cp:
            for r in rows:
                cp.write_row((r["domain"], etld1_of(r["domain"]), r["insert"], r["delete"], r["pos"]))
        # domains newly present
        cur.execute("""SELECT count(DISTINCT t.domain) FROM _certpl t LEFT JOIN certpl_domains d ON d.domain = t.domain
                       WHERE d.domain IS NULL""")
        added = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO certpl_domains (domain, etld1, first_seen_at, last_seen_at, removed_at, meta)
               SELECT DISTINCT ON (domain) domain, etld1, coalesce(ins, now()), now(), del,
                      jsonb_build_object('position', pos)
               FROM _certpl ORDER BY domain, ins DESC NULLS LAST
               ON CONFLICT (domain) DO UPDATE SET last_seen_at = now(),
                 removed_at = EXCLUDED.removed_at,
                 first_seen_at = least(certpl_domains.first_seen_at, EXCLUDED.first_seen_at)""")
        removed = 0
        if url.endswith(".txt"):
            # domains.txt lists only active entries: anything active before and missing now was delisted
            cur.execute("""UPDATE certpl_domains d SET removed_at = now()
                           WHERE d.removed_at IS NULL AND NOT EXISTS (SELECT 1 FROM _certpl t WHERE t.domain = d.domain)""")
            removed = cur.rowcount
        else:
            cur.execute("SELECT count(*) FROM _certpl WHERE del IS NOT NULL")
            removed = cur.fetchone()[0]
        cur.execute("""INSERT INTO certpl_snapshots (run_id, url, sha256, n_domains, added, removed)
                       VALUES (%s, %s, %s, %s, %s, %s)""", (run_id, url, sha, len(rows), added, removed))
        # flag known domains (exact fqdn or registrable domain match)
        cur.execute(
            """UPDATE obs_domains o SET certpl_listed_at = c.first_seen_at, certpl_removed_at = c.removed_at
               FROM certpl_domains c WHERE c.domain = o.fqdn OR c.domain = o.etld1""")
        flagged = cur.rowcount
    conn.execute("UPDATE jobs SET cursor = %s, last_run_at = now() WHERE key = 'certpl_sync'", (Jsonb(new_cursor),))
    stats = {"url": url, "domains": len(rows), "added": added, "removed": removed, "flagged_known": flagged,
             "seconds": round(time.time() - t0, 1)}
    loader.finish_run(run_id, "ok", stats, cursor_after=new_cursor)
    conn.commit()
    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="ignore ETag/Last-Modified")
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    with connect(args.db) as conn:
        print(sync(conn, args.force))
    return 0


if __name__ == "__main__":
    sys.exit(main())
