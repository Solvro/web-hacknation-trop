-- 0002 · provenance: sources, scheduled jobs, job runs, content-addressed artifacts
-- Rule: every row that came from outside points back to (source_id, run_id, source_ref).

CREATE TABLE sources (
    id             smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    key            text NOT NULL UNIQUE,            -- 'sample_v1', 'meta_adlib_api', 'certpl', ...
    kind           text NOT NULL CHECK (kind IN (
                       'dataset','ad_library','threat_feed','ct','enrichment',
                       'capture','user_report','manual')),
    name           text NOT NULL,
    homepage       text,
    auth           text,                            -- none | api_key | oauth | identity_verified | account
    license        text,                            -- short ToS / licence note shown in the UI
    redistribution text NOT NULL DEFAULT 'internal'
                   CHECK (redistribution IN ('never','internal','attribution','open')),
    default_ttl    interval,                        -- how long facts from it stay fresh
    config         jsonb NOT NULL DEFAULT '{}',
    created_at     timestamptz NOT NULL DEFAULT now()
);
COMMENT ON COLUMN sources.redistribution IS
  'never = organizer data (must not leave the deployment); internal = keep in-house; attribution/open = may be exported with credit';

-- Scheduled work: hunter queries, list syncs, CT stream, enrichment refresh, re-captures.
CREATE TABLE jobs (
    id          int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    key         text NOT NULL UNIQUE,               -- 'certpl_sync', 'hunter:meta:brzoska', ...
    source_id   smallint REFERENCES sources(id),
    kind        text NOT NULL CHECK (kind IN (
                    'certpl_sync','adlib_search','atc_bq_pull','tiktok_ccl_search','ct_stream',
                    'urlscan_search','openphish_sync','enrich_refresh','recapture','oracle_score',
                    'recluster','retention')),
    params      jsonb NOT NULL DEFAULT '{}',        -- e.g. {"search_terms":"Brzoska","countries":["PL"]}
    schedule    text,                               -- cron expr, 'stream' or 'manual'
    interval_s  int,
    enabled     boolean NOT NULL DEFAULT true,
    priority    smallint NOT NULL DEFAULT 5,
    budget      jsonb NOT NULL DEFAULT '{}',        -- {"max_api_calls":200,"max_new_captures":50}
    cursor      jsonb NOT NULL DEFAULT '{}',        -- resumable position (paging cursor, CT index, ETag)
    last_run_at timestamptz,
    next_run_at timestamptz,
    created_by  text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX jobs_due ON jobs (next_run_at) WHERE enabled;

CREATE TABLE job_runs (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id        int REFERENCES jobs(id) ON DELETE SET NULL,
    source_id     smallint REFERENCES sources(id),
    trigger       text NOT NULL DEFAULT 'manual' CHECK (trigger IN ('schedule','manual','api','agent','seed')),
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    status        text NOT NULL DEFAULT 'running'
                  CHECK (status IN ('running','ok','partial','error','cancelled')),
    params        jsonb NOT NULL DEFAULT '{}',
    stats         jsonb NOT NULL DEFAULT '{}',      -- {"fetched":..,"new_ads":..,"api_calls":..,"errors":..}
    cursor_before jsonb,
    cursor_after  jsonb,
    error         text
);
CREATE INDEX job_runs_job ON job_runs (job_id, started_at DESC);

-- Content-addressed blob registry. Bytes live in MinIO/S3 (or local FS in dev) under sha256/aa/bb/<hex>.
-- The same blob may play several roles (see artifact_refs), so roles are NOT stored here.
CREATE TABLE artifacts (
    sha256        text PRIMARY KEY CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    size_bytes    bigint NOT NULL,
    mime          text,
    storage_uri   text NOT NULL,                    -- s3://redpill-artifacts/sha256/ab/cd/<hex> | file:///...
    sensitivity   text NOT NULL DEFAULT 'restricted'
                  CHECK (sensitivity IN ('restricted','internal','public')),
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    -- fingerprints of the content itself (images, favicons, media)
    phash         bigint,                           -- 64-bit DCT pHash (imagehash-compatible bit order)
    dhash         bigint,
    favicon_mmh3  integer,                          -- Shodan-style mmh3(base64(bytes))
    width         int,
    height        int,
    duration_ms   int,
    meta          jsonb NOT NULL DEFAULT '{}',
    -- multi-index hashing: split the 64-bit pHash into 4 x 16-bit bands. Two hashes within
    -- Hamming distance <= 3 always share at least one band exactly (pigeonhole), so near-dup
    -- search is 4 btree lookups + a hamming64() filter instead of a full scan.
    phash_b0 int GENERATED ALWAYS AS ((phash >> 48) & 65535) STORED,
    phash_b1 int GENERATED ALWAYS AS ((phash >> 32) & 65535) STORED,
    phash_b2 int GENERATED ALWAYS AS ((phash >> 16) & 65535) STORED,
    phash_b3 int GENERATED ALWAYS AS (phash & 65535) STORED
);
CREATE INDEX artifacts_phash_b0 ON artifacts (phash_b0) WHERE phash IS NOT NULL;
CREATE INDEX artifacts_phash_b1 ON artifacts (phash_b1) WHERE phash IS NOT NULL;
CREATE INDEX artifacts_phash_b2 ON artifacts (phash_b2) WHERE phash IS NOT NULL;
CREATE INDEX artifacts_phash_b3 ON artifacts (phash_b3) WHERE phash IS NOT NULL;
CREATE INDEX artifacts_favicon ON artifacts (favicon_mmh3) WHERE favicon_mmh3 IS NOT NULL;

INSERT INTO schema_migrations(version) VALUES ('0002_provenance') ON CONFLICT DO NOTHING;
