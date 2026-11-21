-- 0006 · analysis results: evidence, pair links, the 4-level grouping, membership history, labels, feedback
--
-- Levels (PLAN §6):  L0 duplicate  → incidents.duplicate_of
--                    L1 variant    → variants
--                    L2 campaign   → campaigns
--                    L3 operator   → operator_families
-- Membership is temporal (SCD type 2): a row is current while valid_to IS NULL; re-clustering
-- closes rows and opens new ones, so "what did campaign X look like on Tuesday" is a query.

CREATE TABLE evidence_types (
    type            text PRIMARY KEY,     -- 'fb_pixel','kit_endpoint','text_cosine','cert_batch','face_identity',…
    layer           text NOT NULL,
    observable_type text REFERENCES observable_types(type),   -- set for exact-shared-value evidence
    kind            text NOT NULL CHECK (kind IN ('shared_value','similarity','window','conflict','model','human')),
    description     text
);

CREATE TABLE clustering_runs (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind               text NOT NULL CHECK (kind IN ('full','incremental','manual','eval')),
    model_version_id   int REFERENCES model_versions(id),
    started_at         timestamptz NOT NULL DEFAULT now(),
    finished_at        timestamptz,
    status             text NOT NULL DEFAULT 'running' CHECK (status IN ('running','ok','error')),
    params             jsonb NOT NULL DEFAULT '{}',  -- tau, delta, resolution, blocking caps …
    touched_incidents  int,
    metrics            jsonb NOT NULL DEFAULT '{}'   -- B-cubed, ARI, #merges, #splits
);

-- Pair-level aggregate: one row per candidate pair that survived blocking, per model version.
CREATE TABLE pair_links (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    a_id             bigint NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    b_id             bigint NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    model_version_id int NOT NULL REFERENCES model_versions(id),
    score            real NOT NULL,          -- Σ weights (rules) or logit (M1)
    p_same           real,                   -- calibrated P(same campaign)
    coverage         real,                   -- share of layers comparable on BOTH sides (missing ≠ different)
    level            smallint CHECK (level BETWEEN 0 AND 3),  -- strongest level supported: 0 dup … 3 operator
    n_evidence       int NOT NULL DEFAULT 0,
    shap             jsonb,                  -- {"base":-2.9,"fb_pixel":3.1,"text_cosine":0.4,…}
    run_id           bigint REFERENCES clustering_runs(id) ON DELETE SET NULL,
    is_current       boolean NOT NULL DEFAULT true,
    computed_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (a_id < b_id),
    UNIQUE (a_id, b_id, model_version_id)
);
CREATE INDEX pair_links_b ON pair_links (b_id) WHERE is_current;
CREATE INDEX pair_links_score ON pair_links (model_version_id, p_same DESC) WHERE is_current;

-- Typed evidence items behind a pair link: the "why" chips.
CREATE TABLE evidence (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    link_id          bigint NOT NULL REFERENCES pair_links(id) ON DELETE CASCADE,
    type             text NOT NULL REFERENCES evidence_types(type),
    observable_id    bigint REFERENCES observables(id),  -- the shared value, for exact evidence
    value            text,                    -- display: '2420768028414250', 'cos=0.93', 'YE1 ±2h'
    similarity       real,                    -- cosine / Jaccard / 1-hamming/64 for fuzzy evidence
    strength         real,                    -- calibrated log-LR of the type
    rarity           real,                    -- idf of the value when computed
    weight           real NOT NULL,           -- strength × rarity; negative = conflicting evidence
    shap             real,                    -- learned contribution (M1), sums with siblings to the pair logit
    a_context        jsonb,                   -- where side A has it (incident_observables.context)
    b_context        jsonb,
    model_version_id int REFERENCES model_versions(id)
);
CREATE INDEX evidence_link ON evidence (link_id);
CREATE INDEX evidence_observable ON evidence (observable_id);

CREATE TABLE operator_families (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uid            uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    code           text UNIQUE,              -- 'OPF-003'
    name           text,
    description    text,
    fingerprint    jsonb NOT NULL DEFAULT '{}', -- shared kit / gateway / pixel set across narratives
    status         text NOT NULL DEFAULT 'active' CHECK (status IN ('candidate','active','dormant','merged','archived')),
    merged_into    bigint REFERENCES operator_families(id),
    created_run_id bigint REFERENCES clustering_runs(id),
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE campaigns (
    id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uid                      uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    code                     text UNIQUE,    -- 'CMP-0007' (stable human handle)
    name                     text,
    family_id                bigint REFERENCES operator_families(id),
    status                   text NOT NULL DEFAULT 'candidate'
                             CHECK (status IN ('candidate','active','dormant','merged','split','archived')),
    narrative                text,
    vertical                 text,
    first_seen_at            timestamptz,
    last_seen_at             timestamptz,
    n_members                int NOT NULL DEFAULT 0,
    fingerprint              jsonb NOT NULL DEFAULT '{}', -- campaign DNA: top weighted observables, domain grammar, cert pattern
    summary                  text,
    summary_model_version_id int REFERENCES model_versions(id),
    merged_into              bigint REFERENCES campaigns(id),
    version                  int NOT NULL DEFAULT 1,       -- bumped on every membership change
    created_run_id           bigint REFERENCES clustering_runs(id),
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX campaigns_family ON campaigns (family_id);

CREATE TABLE variants (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    campaign_id  bigint NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name         text,
    template_key text,                       -- headline template / kit hash / DOM LSH bucket that defines it
    n_members    int NOT NULL DEFAULT 0,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE campaign_memberships (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id           bigint NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    campaign_id           bigint REFERENCES campaigns(id),       -- NULL + decision='new_campaign' is not allowed; see CHECK
    variant_id            bigint REFERENCES variants(id),
    valid_from            timestamptz NOT NULL DEFAULT now(),
    valid_to              timestamptz,
    run_id                bigint REFERENCES clustering_runs(id),
    decision              text NOT NULL CHECK (decision IN ('assigned','new_campaign','uncertain','manual')),
    decided_by            text NOT NULL CHECK (decided_by IN ('rules','model','conformal','llm','analyst')),
    score                 real,               -- campaign score (max-linkage + mean top-3)
    margin                real,               -- over the runner-up campaign
    runner_up_campaign_id bigint REFERENCES campaigns(id),
    p_value               real,               -- conformal p-value
    reason                jsonb NOT NULL DEFAULT '{}',  -- top evidence ids + human summary
    CHECK (campaign_id IS NOT NULL OR decision = 'uncertain')
);
CREATE UNIQUE INDEX campaign_memberships_current ON campaign_memberships (incident_id) WHERE valid_to IS NULL;
CREATE INDEX campaign_memberships_campaign ON campaign_memberships (campaign_id) WHERE valid_to IS NULL;

CREATE TABLE campaign_events (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    campaign_id bigint REFERENCES campaigns(id) ON DELETE CASCADE,
    family_id   bigint REFERENCES operator_families(id) ON DELETE CASCADE,
    kind        text NOT NULL CHECK (kind IN ('created','member_added','member_removed','merged','split',
                                              'renamed','status_changed','family_changed','summary_updated')),
    payload     jsonb NOT NULL DEFAULT '{}',
    run_id      bigint REFERENCES clustering_runs(id),
    actor       text,
    at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX campaign_events_campaign ON campaign_events (campaign_id, at DESC);

-- Ground truth & weak labels (eval/labels.yaml, DANE ground truth if provided, analyst decisions)
CREATE TABLE label_sets (
    id          int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    key         text NOT NULL UNIQUE,        -- 'sample_v1_manual', 'dane_gt', 'weak_lf_v1', 'analyst'
    kind        text NOT NULL CHECK (kind IN ('ground_truth','weak','analyst','synthetic')),
    description text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE labels (
    label_set_id int NOT NULL REFERENCES label_sets(id) ON DELETE CASCADE,
    incident_id  bigint NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    campaign_key text,                       -- L2 label-space campaign id ('A','B',…)
    variant_key  text,                       -- L1 ('A1','A2',…)
    family_key   text,                       -- L3 operator ('OP1',…)
    duplicate_of_ref text,                   -- L0: source_ref of the canonical incident
    confidence   real NOT NULL DEFAULT 1.0,
    created_by   text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (label_set_id, incident_id)
);
CREATE TABLE pair_labels (                   -- must-link / cannot-link constraints
    label_set_id int NOT NULL REFERENCES label_sets(id) ON DELETE CASCADE,
    a_id         bigint NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    b_id         bigint NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    same         boolean NOT NULL,
    source       text,                       -- 'labeling_fn:same_pixel', 'analyst', …
    created_by   text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CHECK (a_id < b_id),
    PRIMARY KEY (label_set_id, a_id, b_id)
);

CREATE TABLE feedback (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor       text NOT NULL,
    target_kind text NOT NULL CHECK (target_kind IN ('pair_link','evidence','membership','campaign','observable','incident','oracle_candidate')),
    target_id   bigint NOT NULL,
    verdict     text NOT NULL CHECK (verdict IN ('accept','reject','merge','split','noise','not_noise','relabel','comment')),
    payload     jsonb NOT NULL DEFAULT '{}',
    comment     text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    applied_at  timestamptz                  -- when the feedback was folded into labels / noise flags / retraining
);
CREATE INDEX feedback_target ON feedback (target_kind, target_id);
CREATE INDEX feedback_unapplied ON feedback (created_at) WHERE applied_at IS NULL;

INSERT INTO schema_migrations(version) VALUES ('0006_analysis') ON CONFLICT DO NOTHING;
