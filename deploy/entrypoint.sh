#!/bin/sh
# 1. seed the /data volume from the image's /bundle (organizer-derived runtime data); files that the image ships newer
#    than the volume copy are refreshed, runtime-only files are left alone
#    (skip with TROP_SKIP_DATA_SEED=1);
# 2. with TROP_DB_SEED=1 restore the Postgres seed dump when the DB is empty (deploy/seed.sh, idempotent);
# 3. exec the service command.
set -e
if [ "${TROP_SKIP_DATA_SEED:-0}" != "1" ] && [ -d /bundle ]; then
  mkdir -p /data
  cd /bundle
  find . -type f ! -path './seed/*' | while IFS= read -r f; do
    if [ ! -e "/data/$f" ] || [ "$f" -nt "/data/$f" ]; then   # new or updated in this image
      mkdir -p "/data/$(dirname "$f")"
      cp "$f" "/data/$f"
    fi
  done
  cd /
fi
# the worker image runs as uid 1000 (Chromium); the api (root) makes the shared volume writable for it
if [ "$(id -u)" = "0" ] && [ -d /data ]; then chown -R 1000:1000 /data 2>/dev/null || true; fi
if [ "${TROP_DB_SEED:-0}" = "1" ]; then
  /seed.sh
fi
exec "$@"
