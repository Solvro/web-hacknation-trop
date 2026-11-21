#!/bin/sh
# Restore /bundle/seed/trop_seed.dump into Postgres when the engine tables are missing (idempotent, safe to re-run).
set -e
DB="${DATABASE_URL:?DATABASE_URL not set}"
i=0
until pg_isready -d "$DB" >/dev/null 2>&1; do
  i=$((i+1))
  if [ "$i" -gt 90 ]; then echo "seed: postgres not reachable" >&2; exit 1; fi
  sleep 2
done
if [ "$(psql "$DB" -tAc "select to_regclass('public.engine_incidents') is not null")" = "t" ]; then
  echo "seed: database already seeded"
  exit 0
fi
if [ -f /bundle/seed/trop_seed.dump ]; then
  pg_restore --no-owner --no-acl -d "$DB" /bundle/seed/trop_seed.dump || echo "seed: pg_restore finished with warnings"
  echo "seed: engine_incidents = $(psql "$DB" -tAc 'select count(*) from engine_incidents')"
else
  echo "seed: no /bundle/seed/trop_seed.dump (engine falls back to the JSON corpus)"
fi
