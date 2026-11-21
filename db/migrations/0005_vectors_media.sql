-- 0005 · vectors + derived media (OCR/ASR text, faces, voice segments)
--
-- One embeddings table for every space. Dimensions differ per model, so the column is an
-- un-dimensioned halfvec and every space gets its own PARTIAL HNSW index with a cast
-- (the pattern pgvector recommends for mixed dimensions). Adding a model = INSERT into
-- embedding_spaces + one CREATE INDEX; no table rewrite. halfvec halves storage at no
-- practical recall cost for cosine search.

CREATE TABLE model_versions (
    id           int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         text NOT NULL,          -- 'rules', 'm1-linker-gbm', 'siglip-base', 'm3-domain-dna', …
    kind         text NOT NULL CHECK (kind IN ('rules','linker','encoder','classifier','clusterer','oracle','adjudicator','extractor')),
    version      text NOT NULL,
    params       jsonb NOT NULL DEFAULT '{}',
    metrics      jsonb NOT NULL DEFAULT '{}',  -- B-cubed F1, ARI, open-set precision, calibration error …
    artifact_uri text,                         -- model file in object storage / registry
    trained_at   timestamptz,
    is_active    boolean NOT NULL DEFAULT false,
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);

CREATE TABLE embedding_spaces (
    space      text PRIMARY KEY,         -- '<modality>.<model>.<rev>'
    modality   text NOT NULL CHECK (modality IN ('text','image','face','voice','dom','multimodal')),
    model      text NOT NULL,
    dim        int NOT NULL,
    metric     text NOT NULL DEFAULT 'cosine' CHECK (metric IN ('cosine','l2','ip')),
    inputs     text[],                   -- which input kinds go in: landing_text, ad_text, ocr, asr, screenshot, creative…
    notes      text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE media_texts (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id     bigint REFERENCES incidents(id) ON DELETE CASCADE,
    artifact_sha256 text REFERENCES artifacts(sha256),
    kind            text NOT NULL CHECK (kind IN ('ocr','asr','vlm_caption','llm_extract','page_text')),
    lang            text,
    text            text NOT NULL,
    confidence      real,
    model_version_id int REFERENCES model_versions(id),
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX media_texts_incident ON media_texts (incident_id);
CREATE INDEX media_texts_trgm ON media_texts USING gin (text gin_trgm_ops);

CREATE TABLE faces (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id          bigint REFERENCES incidents(id) ON DELETE CASCADE,
    artifact_sha256      text NOT NULL REFERENCES artifacts(sha256),
    frame_ms             int,                 -- for video frames
    bbox                 int[4],
    det_score            real,
    person_observable_id bigint REFERENCES observables(id),  -- gallery match → person
    identity_score       real,
    deepfake_score       real,                -- facetorch
    attrs                jsonb NOT NULL DEFAULT '{}',
    model_version_id     int REFERENCES model_versions(id)
);
CREATE INDEX faces_incident ON faces (incident_id);
CREATE INDEX faces_person ON faces (person_observable_id);

CREATE TABLE voice_segments (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id          bigint REFERENCES incidents(id) ON DELETE CASCADE,
    artifact_sha256      text NOT NULL REFERENCES artifacts(sha256),
    t_start_ms           int,
    t_end_ms             int,
    person_observable_id bigint REFERENCES observables(id),
    identity_score       real,
    synthetic_score      real,                -- synthetic-voice / TTS likelihood
    model_version_id     int REFERENCES model_versions(id)
);
CREATE INDEX voice_segments_incident ON voice_segments (incident_id);

CREATE TABLE embeddings (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    space            text NOT NULL REFERENCES embedding_spaces(space),
    incident_id      bigint REFERENCES incidents(id) ON DELETE CASCADE,
    capture_id       bigint REFERENCES captures(id) ON DELETE CASCADE,
    ad_id            bigint REFERENCES ads(id) ON DELETE CASCADE,
    artifact_sha256  text REFERENCES artifacts(sha256),
    face_id          bigint REFERENCES faces(id) ON DELETE CASCADE,
    voice_segment_id bigint REFERENCES voice_segments(id) ON DELETE CASCADE,
    input_kind       text NOT NULL,           -- landing_text | ad_text | ocr | asr | screenshot | creative | face | voice | incident
    vec              halfvec NOT NULL,
    model_version_id int REFERENCES model_versions(id),
    created_at       timestamptz NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(incident_id, capture_id, ad_id, artifact_sha256, face_id, voice_segment_id) >= 1)
);
CREATE INDEX embeddings_incident ON embeddings (incident_id, space);
CREATE UNIQUE INDEX embeddings_owner ON embeddings
    (space, input_kind, incident_id, capture_id, ad_id, artifact_sha256, face_id, voice_segment_id) NULLS NOT DISTINCT;

INSERT INTO schema_migrations(version) VALUES ('0005_vectors_media') ON CONFLICT DO NOTHING;
