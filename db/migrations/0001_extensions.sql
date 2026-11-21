-- 0001 · extensions + migration bookkeeping
-- Every migration records itself in schema_migrations, so the same files work both as
-- docker-entrypoint-initdb.d scripts (first boot) and through db/migrate.py (incremental).

CREATE TABLE IF NOT EXISTS schema_migrations (
    version    text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector >= 0.7 (halfvec, HNSW)
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- fuzzy text / lookalike domains
CREATE EXTENSION IF NOT EXISTS btree_gin;  -- mixed GIN indexes
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- digest() for server-side hashing

-- 64-bit perceptual-hash Hamming distance (pHash / dHash / simhash)
CREATE OR REPLACE FUNCTION hamming64(a bigint, b bigint) RETURNS int
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS
$$ SELECT bit_count((a # b)::bit(64))::int $$;

INSERT INTO schema_migrations(version) VALUES ('0001_extensions') ON CONFLICT DO NOTHING;
