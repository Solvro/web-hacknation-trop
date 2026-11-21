#!/bin/sh
# 1. seed the /data volume from the image's /bundle (organizer-derived runtime data) without overwriting existing files
#    (skip with TROP_SKIP_DATA_SEED=1);
# 2. with TROP_DB_SEED=1 restore the Postgres seed dump when the DB is empty (deploy/seed.sh, idempotent);
# 3. exec the service command.
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
if [ "${TROP_DB_SEED:-0}" = "1" ]; then
  /seed.sh
fi
exec "$@"
