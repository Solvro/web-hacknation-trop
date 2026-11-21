-- 0013 TROP build: White Rabbit investigations, rules + rule tests, engine documents/decisions, operations.
-- ADDITIVE ONLY (new tables / nullable columns); safe to run on the existing redpill dev DB.

-- Engine Incident documents (schema.Incident dict the Déjà Vu engine consumes), one per incident.
CREATE TABLE IF NOT EXISTS engine_incidents (
    incident_id     bigint PRIMARY KEY REFERENCES incidents(id) ON DELETE CASCADE,
    ext_id          text NOT NULL UNIQUE,              -- engine id: 'p1', 'd3', 'INC-123'
    doc             jsonb NOT NULL,
    feature_version int NOT NULL DEFAULT 1,
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- Operations: shared funnels across operators / campaigns (DANE finding A + C + K).
CREATE TABLE IF NOT EXISTS operations (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code        text NOT NULL UNIQUE,                  -- 'OPN-01'
    name        text,
    funnel      jsonb NOT NULL DEFAULT '[]',
    created_at  timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS operation_id bigint REFERENCES operations(id);
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS meta jsonb NOT NULL DEFAULT '{}';

-- Engine decisions per incident and model version (GET /incidents/{id}/decision).
CREATE TABLE IF NOT EXISTS engine_decisions (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id      bigint NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    model_version    text NOT NULL,                    -- 'engine@1'
    state            text NOT NULL CHECK (state IN ('assign','confirm','ambiguous','new','insufficient')),
    campaign_id      bigint REFERENCES campaigns(id),
    score            real,
    p                real,
    decision         jsonb NOT NULL,                   -- schema.Decision
    is_current       boolean NOT NULL DEFAULT true,
    decided_at       timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS engine_decisions_current ON engine_decisions (incident_id, model_version) WHERE is_current;

-- White Rabbit (docs/db §9)
CREATE TABLE IF NOT EXISTS investigations (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code          text NOT NULL UNIQUE,                -- 'INV-12'
    seed          text NOT NULL,
    campaign_id   bigint REFERENCES campaigns(id),
    status        text NOT NULL DEFAULT 'running' CHECK (status IN ('running','paused','done','stopped','error')),
    model         text,
    budget        jsonb NOT NULL DEFAULT '{}',
    graph         jsonb NOT NULL DEFAULT '{"nodes": [], "edges": []}',
    conclusions   jsonb NOT NULL DEFAULT '[]',
    pending       jsonb,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz
);
CREATE TABLE IF NOT EXISTS investigation_steps (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    investigation_id bigint NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    n                int NOT NULL,
    tool             text NOT NULL,
    query            text,
    result_summary   text,
    why              text,
    produced         jsonb NOT NULL DEFAULT '[]',
    bot              text,
    cost_usd         real NOT NULL DEFAULT 0,
    at               timestamptz NOT NULL DEFAULT now(),
    UNIQUE (investigation_id, n)
);

-- Detection rules per campaign + their tests (Act)
CREATE TABLE IF NOT EXISTS rules (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code        text UNIQUE,
    campaign_id bigint REFERENCES campaigns(id) ON DELETE CASCADE,
    kind        text NOT NULL CHECK (kind IN ('urlscan','url_regex','html_signature','yara')),
    body        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS rule_tests (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_id      bigint NOT NULL REFERENCES rules(id) ON DELETE CASCADE,
    hits         int NOT NULL DEFAULT 0,
    tp           int NOT NULL DEFAULT 0,
    needs_review int NOT NULL DEFAULT 0,
    benign_hits  int NOT NULL DEFAULT 0,
    benign_total int NOT NULL DEFAULT 0,
    precision    real,
    tested_at    timestamptz NOT NULL DEFAULT now()
);
