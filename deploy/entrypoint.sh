#!/bin/sh
# 1. seed the /data volume from the image's /bundle (organizer-derived runtime data) without overwriting existing files
#    (skip with TROP_SKIP_DATA_SEED=1);
# 2. real modes only: purge leftovers of the fictional demo universe from an older volume (mock replays, KMP-017 Act
#    packages, cached model outputs that mention it) -- the real product must never show them;
# 3. with TROP_DB_SEED=1 restore the Postgres seed dump when the DB is empty (deploy/seed.sh, idempotent);
# 4. exec the service command.
set -e
if [ "${TROP_SKIP_DATA_SEED:-0}" != "1" ] && [ -d /bundle ]; then
  mkdir -p /data
  cd /bundle
  find . -type f ! -path './seed/*' | while IFS= read -r f; do
    if [ ! -e "/data/$f" ]; then
      mkdir -p "/data/$(dirname "$f")"
      cp "$f" "/data/$f"
    fi
  done
  cd /
fi
if [ "${TROP_MODE:-live}" != "mock" ] && [ -d /data ]; then
  rm -f /data/replay/demo-*.jsonl
  for d in /data/act/ACT-*; do
    [ -f "$d/package.json" ] && grep -q '"campaign_id": *"KMP-017"' "$d/package.json" && rm -rf "$d"
  done
  [ -d /data/cache/models ] && grep -rlE 'KMP-017|«Zamach»|INC-24817|Kurier Dnia' /data/cache/models 2>/dev/null | xargs -r rm -f
fi
if [ "${TROP_DB_SEED:-0}" = "1" ]; then
  /seed.sh
fi
# drop root: the worker runs as uid 1000 (Chromium) and both share /data, so the api must create files as 1000 too
if [ "$(id -u)" = "0" ] && [ "${TROP_RUN_AS_ROOT:-0}" != "1" ] && command -v setpriv >/dev/null 2>&1; then
  chown -R 1000:1000 /data 2>/dev/null || true
  exec setpriv --reuid=1000 --regid=1000 --clear-groups env HOME=/tmp "$@"
fi
exec "$@"
