-- 0007 · operations: enrichment cache, CERT PL mirror, capture queue + politeness, oracle, act, reports, audit

CREATE TABLE enrichment_providers (
    provider      text PRIMARY KEY,          -- 'rdap','dns','crtsh','urlscan','ipinfo','internetdb','wayback','certpl'
    source_id     smallint REFERENCES sources(id),
    ttl_ok        interval NOT NULL,
    ttl_not_found interval NOT NULL,
    ttl_error     interval NOT NULL DEFAULT '15 minutes',
    rate_per_min  int,                       -- client-side token bucket
    burst         int,
    notes         text
);

-- Raw provider responses keyed by (provider, key). Workers read here first; offline/demo mode
-- runs purely from this cache. Not-found and errors are cached too (negative caching), with
-- shorter TTLs, so a flaky crt.sh does not get hammered.
CREATE TABLE enrichment_cache (
    provider        text NOT NULL REFERENCES enrichment_providers(provider),
    key             text NOT NULL,           -- 'example.com', '192.0.2.10', 'all:example.com'
    fetched_at      timestamptz NOT NULL DEFAULT now(),
    expires_at      timestamptz NOT NULL,
    status          text NOT NULL CHECK (status IN ('ok','not_found','error','rate_limited')),
    http_status     int,
    response        jsonb,
    response_sha256 text REFERENCES artifacts(sha256),  -- large bodies go to object storage
    error           text,
    attempts        int NOT NULL DEFAULT 1,
    PRIMARY KEY (provider, key)
);
CREATE INDEX enrichment_cache_expiry ON enrichment_cache (expires_at);

-- Mirror of the CERT PL warning list with history (list diffs = when a domain was added/removed).
CREATE TABLE certpl_snapshots (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id     bigint REFERENCES job_runs(id),
    fetched_at timestamptz NOT NULL DEFAULT now(),
    url        text NOT NULL,
    sha256     text NOT NULL,
    n_domains  int NOT NULL,
    added      int NOT NULL DEFAULT 0,
    removed    int NOT NULL DEFAULT 0
);
CREATE TABLE certpl_domains (
    domain        text PRIMARY KEY,
    etld1         text,
    first_seen_at timestamptz NOT NULL DEFAULT now(),  -- first snapshot that contained it (≈ listing time)
    last_seen_at  timestamptz NOT NULL DEFAULT now(),
    removed_at    timestamptz,
    meta          jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX certpl_domains_etld1 ON certpl_domains (etld1);
CREATE INDEX certpl_domains_trgm ON certpl_domains USING gin (domain gin_trgm_ops);

-- Durable capture work items (the live queue is Redis/arq; this table is the record + retry state).
CREATE TABLE capture_tasks (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url          text NOT NULL,
    url_norm     text NOT NULL,
    etld1        text NOT NULL,
    profile      text NOT NULL DEFAULT 'fb_inapp_android_pl',
    priority     smallint NOT NULL DEFAULT 5,
    requested_by text,                       -- 'hunter','oracle','analyst:<id>','agent','extension'
    reason       text,
    status       text NOT NULL DEFAULT 'queued'
                 CHECK (status IN ('queued','running','done','failed','skipped_budget','skipped_policy','duplicate')),
    attempts     int NOT NULL DEFAULT 0,
    not_before   timestamptz NOT NULL DEFAULT now(),
    incident_id  bigint REFERENCES incidents(id),
    capture_id   bigint REFERENCES captures(id),
    created_at   timestamptz NOT NULL DEFAULT now(),
    started_at   timestamptz,
    finished_at  timestamptz,
    error        text
);
CREATE INDEX capture_tasks_ready ON capture_tasks (priority DESC, not_before) WHERE status = 'queued';
CREATE UNIQUE INDEX capture_tasks_dedupe ON capture_tasks (url_norm, profile) WHERE status IN ('queued','running');

-- Per-registrable-domain politeness budget (token bucket) + circuit breaker.
CREATE TABLE domain_budgets (
    etld1              text PRIMARY KEY,
    max_per_hour       int NOT NULL DEFAULT 6,
    tokens             real NOT NULL DEFAULT 6,
    refilled_at        timestamptz NOT NULL DEFAULT now(),
    cooldown_until     timestamptz,
    consecutive_errors int NOT NULL DEFAULT 0,
    last_capture_at    timestamptz,
    notes              text
);

-- Oracle: domains seen in CT / feeds scored against campaign domain-DNA before any ad is seen.
CREATE TABLE oracle_candidates (
    id                    bigint GENERATED ALWAYS AS IDENTITY,
    seen_at               timestamptz NOT NULL,
    fqdn                  text NOT NULL,
    etld1                 text NOT NULL,
    source                text NOT NULL CHECK (source IN ('ct_stream','crtsh','urlscan','certpl','openphish','pivot')),
    ct_log                text,
    cert_sha256           text,
    issuer_cn             text,
    sans                  text[],
    score                 real NOT NULL,
    model_version_id      int REFERENCES model_versions(id),
    predicted_campaign_id bigint REFERENCES campaigns(id),
    features              jsonb NOT NULL DEFAULT '{}',
    explanation           jsonb NOT NULL DEFAULT '{}',
    status                text NOT NULL DEFAULT 'new'
                          CHECK (status IN ('new','queued_capture','captured','confirmed','false_positive','expired')),
    confirmed_incident_id bigint REFERENCES incidents(id),
    certpl_listed_at      timestamptz,
    resolved_at           timestamptz,
    PRIMARY KEY (seen_at, id)
) PARTITION BY RANGE (seen_at);
CREATE TABLE oracle_candidates_default PARTITION OF oracle_candidates DEFAULT;
CREATE INDEX oracle_candidates_etld1 ON oracle_candidates (etld1);
CREATE INDEX oracle_candidates_open ON oracle_candidates (score DESC) WHERE status = 'new';

-- Act center outputs (DSA notices, CERT PL submissions, STIX/MISP bundles, detection rules).
CREATE TABLE act_packages (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    campaign_id     bigint REFERENCES campaigns(id),
    kind            text NOT NULL CHECK (kind IN ('dsa_notice','certpl_submission','stix','misp','rules','case_file')),
    status          text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','sent','acknowledged','actioned','rejected')),
    payload         jsonb NOT NULL DEFAULT '{}',
    artifact_sha256 text REFERENCES artifacts(sha256),
    created_by      text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    sent_at         timestamptz
);

-- Citizen layer: extension / web-form reports (become incidents after triage).
CREATE TABLE reports (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    channel         text NOT NULL CHECK (channel IN ('extension','web_form','email','api')),
    reporter_hash   text,                    -- salted hash, never raw identity
    submitted_at    timestamptz NOT NULL DEFAULT now(),
    url             text,
    ad_library_id   text,
    screenshot_sha  text REFERENCES artifacts(sha256),
    note            text,
    matched_campaign_id bigint REFERENCES campaigns(id),
    incident_id     bigint REFERENCES incidents(id),
    status          text NOT NULL DEFAULT 'new' CHECK (status IN ('new','triaged','duplicate','spam','incident'))
);

-- Append-only audit trail (analyst decisions, agent tool calls, exports, deletions).
CREATE TABLE audit_log (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at          timestamptz NOT NULL DEFAULT now(),
    actor       text NOT NULL,
    actor_kind  text NOT NULL CHECK (actor_kind IN ('user','agent','worker','system')),
    action      text NOT NULL,
    target_kind text,
    target_id   text,
    details     jsonb NOT NULL DEFAULT '{}',
    request_id  text
);
CREATE INDEX audit_log_target ON audit_log (target_kind, target_id);

CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only';
END $$;
CREATE TRIGGER audit_log_no_update BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();

INSERT INTO schema_migrations(version) VALUES ('0007_operations') ON CONFLICT DO NOTHING;
