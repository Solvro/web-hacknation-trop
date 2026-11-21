-- 0003 · core records: advertisers, ads, incidents, captures (+hops, +requests), artifact roles
--
-- Vocabulary
--   incident  = one observation handed to us (a sample folder, a hunter hit, an extension report).
--               It is the unit that gets clustered.
--   ad        = a platform ad (deduped by platform + library id). Many incidents may point at one ad.
--   capture   = one browser visit of a landing URL (ours or someone else's). An incident may have
--               several (organizer bundle + analyst HAR, mobile vs desktop profile, re-captures).

CREATE TABLE advertisers (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    platform        text NOT NULL CHECK (platform IN ('meta','google','tiktok','x','other')),
    platform_id     text,                           -- Meta page_id, Google AR..., TikTok adv id
    name            text,
    country         text,
    verified        boolean,
    page_created_at date,
    page_likes      int,
    first_seen_at   timestamptz NOT NULL DEFAULT now(),
    last_seen_at    timestamptz,
    raw             jsonb NOT NULL DEFAULT '{}'
);
CREATE UNIQUE INDEX advertisers_platform_id ON advertisers (platform, platform_id) WHERE platform_id IS NOT NULL;
-- advertisers known only by name (screenshot OCR) dedupe on the lower-cased name
CREATE UNIQUE INDEX advertisers_platform_name ON advertisers (platform, lower(name)) WHERE platform_id IS NULL;

CREATE TABLE ads (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    platform            text NOT NULL CHECK (platform IN ('meta','google','tiktok','x','other')),
    library_id          text,                       -- Meta ad_archive_id, Google creative_id, TikTok ad id
    dedupe_key          text NOT NULL UNIQUE,       -- 'meta:<library_id>' | 'shot:<sha256>' | 'text:<sha256(norm body|advertiser)>'
    advertiser_id       bigint REFERENCES advertisers(id),
    body                text,                       -- ad_creative_bodies[0] or OCR
    title               text,                       -- link title
    description         text,
    display_link        text,                       -- link caption, e.g. the fake 'AMAZON.COM'
    cta                 text,
    link_url            text,                       -- rarely known (Meta API has none): from capture/OCR/report
    languages           text[],
    publisher_platforms text[],
    delivery_start      timestamptz,
    delivery_stop       timestamptz,
    eu_total_reach      bigint,
    targeting           jsonb NOT NULL DEFAULT '{}',-- ages, gender, locations (DSA fields)
    beneficiary         text,
    payer               text,
    snapshot_url        text,
    creative_is_decoy   boolean,                    -- cloaked decoy creative (bird / landscape / generic clickbait)
    decoy_score         real,
    clickbait_template  text,                       -- body with entities masked
    source_id           smallint REFERENCES sources(id),
    first_seen_at       timestamptz NOT NULL DEFAULT now(),
    last_seen_at        timestamptz,
    raw                 jsonb NOT NULL DEFAULT '{}'
);
CREATE UNIQUE INDEX ads_platform_library ON ads (platform, library_id) WHERE library_id IS NOT NULL;
CREATE INDEX ads_advertiser ON ads (advertiser_id);
CREATE INDEX ads_delivery ON ads (delivery_start);
CREATE INDEX ads_body_trgm ON ads USING gin (body gin_trgm_ops);

-- Time series of what the hunter saw for an ad on each run (active flag, reach growth → "heating up").
CREATE TABLE ad_observations (
    ad_id          bigint NOT NULL REFERENCES ads(id) ON DELETE CASCADE,
    run_id         bigint NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    observed_at    timestamptz NOT NULL DEFAULT now(),
    is_active      boolean,
    eu_total_reach bigint,
    raw            jsonb,
    PRIMARY KEY (ad_id, run_id)
);

CREATE TABLE incidents (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uid                uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,   -- public id for the API
    source_id          smallint NOT NULL REFERENCES sources(id),
    run_id             bigint REFERENCES job_runs(id),
    source_ref         text NOT NULL,              -- 'sample_v1/p3', 'bundle/archive_x', ad library id, report id
    kind               text NOT NULL CHECK (kind IN ('ad+landing','ad_only','landing_only','domain_only','report')),
    status             text NOT NULL DEFAULT 'ingested'
                       CHECK (status IN ('ingested','captured','extracted','linked','error')),
    ad_id              bigint REFERENCES ads(id),
    primary_capture_id bigint,                     -- FK added below (captures references incidents)
    entry_url          text,
    entry_etld1        text,
    final_etld1        text,
    title              text,
    lang               text,
    headline           text,
    headline_template  text,                       -- headline with persons/brands masked: 'PILNE: Brutalna napaść na {PER} …'
    narrative          text,                       -- 'fake_news_attack','health_cure','investment',...
    vertical           text,                       -- 'finance','health','crypto','shop',...
    observed_at        timestamptz,                -- when the scam was seen (capture time / ad delivery)
    ingested_at        timestamptz NOT NULL DEFAULT now(),
    dedupe_key         text NOT NULL,              -- sha256 over the sorted core-artifact hashes (exact duplicates)
    duplicate_of       bigint REFERENCES incidents(id),  -- L0 exact duplicate → canonical incident
    quality            jsonb NOT NULL DEFAULT '{}',-- {"available":[..],"missing":[..],"errors":[..],"layers":{"tracking":"observed|absent|unknown",..}}
    sensitivity        text NOT NULL DEFAULT 'restricted'
                       CHECK (sensitivity IN ('restricted','internal','public')),
    feature_version    int NOT NULL DEFAULT 0,     -- bumped on re-extraction; drives incremental re-linking
    needs_relink       boolean NOT NULL DEFAULT true,
    raw                jsonb NOT NULL DEFAULT '{}',-- the adapter's Incident-contract JSON (PLAN §4), for replay
    UNIQUE (source_id, source_ref)
);
CREATE INDEX incidents_dedupe ON incidents (dedupe_key);
CREATE INDEX incidents_observed ON incidents (observed_at);
CREATE INDEX incidents_etld1 ON incidents (entry_etld1);
CREATE INDEX incidents_relink ON incidents (id) WHERE needs_relink;
CREATE INDEX incidents_ad ON incidents (ad_id);
CREATE INDEX incidents_headline_tpl ON incidents USING gin (headline_template gin_trgm_ops);

CREATE TABLE captures (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id    bigint NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    tool           text NOT NULL,                  -- 'redpill-playwright' | 'organizer-bundle' | 'devtools-har' | 'browser-save-as' | 'urlscan'
    tool_version   text,
    profile        text,                           -- 'fb_inapp_android_pl' | 'desktop_chrome_pl' | ...
    user_agent     text,
    viewport       text,
    locale         text,
    timezone       text,
    egress         text,                           -- proxy / exit country
    referer        text,
    entry_url      text NOT NULL,
    entry_url_norm text,                           -- tracking params stripped, host lower-cased, query sorted
    final_url      text,
    final_status   int,
    title          text,
    captured_at    timestamptz NOT NULL,
    duration_ms    int,
    page_role      text CHECK (page_role IN ('prelander','offer','order_form','decoy','error','parked','blocked','unknown')),
    cloak_verdict  text CHECK (cloak_verdict IN ('served','cloaked','blocked','error','unknown')),
    dom_sha256     text,                           -- sha256 of rendered DOM
    text_sha256    text,                           -- sha256 of normalized visible text
    text_simhash   bigint,
    dom_minhash    int[],                          -- MinHash signature of tag-path shingles (LSH bands → observables)
    page_text      text,
    forms          jsonb NOT NULL DEFAULT '[]',    -- [{"action":..,"method":..,"fields":[..]}]
    outlinks       jsonb NOT NULL DEFAULT '[]',
    tls            jsonb,                          -- leaf certificate summary seen at capture time
    meta           jsonb NOT NULL DEFAULT '{}',    -- meta tags, storage summary, console errors, files present
    error          text
);
CREATE INDEX captures_incident ON captures (incident_id);
CREATE INDEX captures_url_norm ON captures (entry_url_norm);
CREATE INDEX captures_dom ON captures (dom_sha256);
CREATE INDEX captures_text ON captures (text_sha256);

ALTER TABLE incidents ADD CONSTRAINT incidents_primary_capture_fk
    FOREIGN KEY (primary_capture_id) REFERENCES captures(id) ON DELETE SET NULL;

-- Full redirect chain including client-side hops (meta refresh, JS location, frames).
CREATE TABLE capture_hops (
    capture_id bigint NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
    hop        smallint NOT NULL,
    url        text NOT NULL,
    host       text,
    status     int,
    kind       text NOT NULL CHECK (kind IN ('entry','http_redirect','meta_refresh','js_navigation','frame','final')),
    ip         inet,
    at         timestamptz,
    PRIMARY KEY (capture_id, hop)
);

-- One row per HAR entry. The HAR itself stays in object storage; this is the queryable index of it
-- (hosts, kit paths, asset body hashes, server IPs). Range-partitioned by month for retention/scale;
-- the default partition catches everything until monthly partitions are created by the retention job.
CREATE TABLE capture_requests (
    capture_id     bigint NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
    seq            int NOT NULL,
    captured_at    timestamptz NOT NULL,
    started_at     timestamptz,
    method         text,
    url            text NOT NULL,
    host           text,
    path_template  text,                           -- ids → {uuid} {hex} {int} {tok}
    status         int,
    mime           text,
    resource_type  text,                           -- document|script|xhr|fetch|image|media|ping|...
    server_ip      inet,
    body_sha256    text,
    body_size      int,
    is_third_party boolean,
    initiator      text,
    PRIMARY KEY (captured_at, capture_id, seq)
) PARTITION BY RANGE (captured_at);
CREATE TABLE capture_requests_default PARTITION OF capture_requests DEFAULT;
CREATE INDEX capture_requests_capture ON capture_requests (capture_id);
CREATE INDEX capture_requests_host ON capture_requests (host);
CREATE INDEX capture_requests_body ON capture_requests (body_sha256) WHERE body_sha256 IS NOT NULL;
CREATE INDEX capture_requests_path ON capture_requests (path_template);

-- Which blob plays which role for which record (one blob, many roles).
CREATE TABLE artifact_refs (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sha256      text NOT NULL REFERENCES artifacts(sha256),
    incident_id bigint REFERENCES incidents(id) ON DELETE CASCADE,
    capture_id  bigint REFERENCES captures(id) ON DELETE CASCADE,
    ad_id       bigint REFERENCES ads(id) ON DELETE CASCADE,
    role        text NOT NULL CHECK (role IN (
                    'ad_screenshot','ad_creative_image','ad_creative_video',
                    'landing_har','landing_html_source','landing_html_rendered','landing_html_saved',
                    'landing_screenshot_full','landing_screenshot_viewport','landing_pdf','landing_mhtml',
                    'landing_text','landing_video','favicon','asset_image','asset_script','media_video',
                    'media_audio','storage_cookies','storage_local','storage_session','dns_ssl_json',
                    'metadata_json','archive_info_json','sha256_manifest','bundle_zip','note','other')),
    rel_path    text,                              -- path inside the source folder / bundle
    url         text,                              -- URL it was fetched from (assets, favicon, media)
    created_at  timestamptz NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(incident_id, capture_id, ad_id) >= 1),
    UNIQUE NULLS NOT DISTINCT (sha256, incident_id, capture_id, ad_id, role, rel_path)
);
CREATE INDEX artifact_refs_incident ON artifact_refs (incident_id);
CREATE INDEX artifact_refs_capture ON artifact_refs (capture_id);
CREATE INDEX artifact_refs_sha ON artifact_refs (sha256);

INSERT INTO schema_migrations(version) VALUES ('0003_core') ON CONFLICT DO NOTHING;
