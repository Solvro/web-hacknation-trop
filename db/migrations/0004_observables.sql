-- 0004 · observables: typed entities + the incident↔observable inverted index + the infra graph
--
-- observables            one row per (type, normalized value): a pixel id, a kit path template, a domain …
-- incident_observables   posting lists: which incidents carry which value, where it was found (evidence pointer)
-- obs_*                  typed detail / enrichment for the types that need it (class-table inheritance)
-- observable_relations   observable→observable facts (domain resolves_to ip, ip in_asn asn, cert covers domain…)
--                        = the infrastructure graph used for pivots, independent of incidents; also passive DNS.

CREATE TABLE observable_types (
    type         text PRIMARY KEY,
    layer        text NOT NULL CHECK (layer IN ('tracking','kit','infra','content','persons','visual','ad','media','blocking')),
    strength     text NOT NULL CHECK (strength IN ('H','M','L','0')),
    prior_log_lr real NOT NULL,          -- Fellegi–Sunter log(m/u) prior; replaced by calibrated value per model version
    compare      text NOT NULL CHECK (compare IN ('exact','template','fuzzy','window','hamming','set')),
    max_df_ratio real,                   -- df/N above this → auto-noise (if also spread over many campaigns)
    description  text
);

CREATE TABLE observables (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    type          text NOT NULL REFERENCES observable_types(type),
    value         text NOT NULL,         -- canonical normalized form (lower-case domain, E.164 phone, templated path…)
    display       text,                  -- original form for UI chips
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at  timestamptz NOT NULL DEFAULT now(),
    df_incidents  int NOT NULL DEFAULT 0,-- distinct (non-duplicate) incidents carrying it
    df_campaigns  int NOT NULL DEFAULT 0,-- distinct current campaigns carrying it (spread ⇒ shared infra / noise)
    idf           real,                  -- ln((N+1)/(df+1)), cached by refresh_observable_stats()
    noise         boolean NOT NULL DEFAULT false,
    noise_reason  text,                  -- 'cdn_ip','public_cdn_library','platform_tracker','analyst',...
    stats_at      timestamptz,
    attrs         jsonb NOT NULL DEFAULT '{}'
);
-- md5() keeps the unique index small even for long templates (btree row limit ~2.7 kB)
CREATE UNIQUE INDEX observables_type_value ON observables (type, md5(value));
CREATE INDEX observables_type_df ON observables (type, df_incidents);
CREATE INDEX observables_value_trgm ON observables USING gin (value gin_trgm_ops)
    WHERE type IN ('etld1','fqdn','headline_template','clickbait_template','product','kit_endpoint','lander_path');

CREATE TABLE incident_observables (
    incident_id   bigint NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    observable_id bigint NOT NULL REFERENCES observables(id),
    field         text NOT NULL,         -- where: 'har.request_host','html.inline_script','url.query','bundle.dns_ssl','ocr.ad',…
    extractor     text NOT NULL,         -- extractor name@version
    confidence    real NOT NULL DEFAULT 1.0,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    context       jsonb NOT NULL DEFAULT '{}',  -- pointer for the evidence chip: {"capture_id":..,"seq":..,"url":..}
    PRIMARY KEY (incident_id, observable_id, field)
);
-- the posting list: observable → incidents (blocking, df, pivots)
CREATE INDEX incident_observables_posting ON incident_observables (observable_id, incident_id);

-- ---------- typed detail tables ----------
CREATE TABLE obs_domains (
    observable_id     bigint PRIMARY KEY REFERENCES observables(id) ON DELETE CASCADE,
    fqdn              text NOT NULL,
    etld1             text NOT NULL,
    tld               text NOT NULL,
    sld               text,              -- registrable label without suffix ('example')
    lexical           jsonb,             -- domain DNA: len, digits, hyphens, entropy, vowel ratio, dictionary words, pattern
    registrar         text,
    registrar_iana_id int,
    created_at        timestamptz,       -- RDAP registration event
    expires_at        timestamptz,
    updated_at        timestamptz,
    rdap_status       text[],
    nameservers       text[],
    first_cert_at     timestamptz,       -- earliest CT entry (crt.sh)
    certpl_listed_at  timestamptz,
    certpl_removed_at timestamptz,
    enriched_at       timestamptz
);
CREATE INDEX obs_domains_etld1 ON obs_domains (etld1);
CREATE INDEX obs_domains_created ON obs_domains (created_at);
CREATE INDEX obs_domains_registrar ON obs_domains (registrar);

CREATE TABLE obs_ips (
    observable_id bigint PRIMARY KEY REFERENCES observables(id) ON DELETE CASCADE,
    ip            inet NOT NULL UNIQUE,
    asn           int,
    as_org        text,
    country       text,
    cdn           text,                  -- 'cloudflare','akamai','fastly','cloudfront',… (CDN edge ⇒ noise for linking)
    is_cdn        boolean,
    hosting       text,                  -- 'digitalocean','hetzner','aws',…
    open_ports    int[],
    hostnames     text[],
    tags          text[],
    enriched_at   timestamptz
);
CREATE INDEX obs_ips_asn ON obs_ips (asn);

CREATE TABLE obs_certs (
    observable_id bigint PRIMARY KEY REFERENCES observables(id) ON DELETE CASCADE,
    sha256        text UNIQUE,           -- DER fingerprint when known (observable value is issuer_cn/serial)
    serial        text,
    issuer_cn     text,                  -- 'YE1','R10','E5',…
    issuer_org    text,
    subject_cn    text,
    sans          text[],
    not_before    timestamptz,
    not_after     timestamptz,
    precert       boolean,
    crtsh_id      bigint,
    ct_entry      jsonb                  -- {"log":"…","index":…,"timestamp":…}
);
-- certificate batch queries: same issuer, issued within N hours
CREATE INDEX obs_certs_batch ON obs_certs (issuer_cn, not_before);
CREATE INDEX obs_certs_sans ON obs_certs USING gin (sans);

CREATE TABLE obs_persons (
    observable_id  bigint PRIMARY KEY REFERENCES observables(id) ON DELETE CASCADE,
    canonical_name text NOT NULL,
    wikidata_qid   text,
    role           text,                 -- journalist | politician | businessman | doctor | priest | celebrity
    gallery_ref    text                  -- face/voice gallery entry
);

CREATE TABLE observable_relations (
    src_id        bigint NOT NULL REFERENCES observables(id) ON DELETE CASCADE,
    rel           text NOT NULL CHECK (rel IN (
                      'resolves_to','in_asn','has_cert','cert_covers','uses_ns','uses_mx','registered_by',
                      'subdomain_of','redirects_to','loads_from','posts_to','same_cert_batch','cname_to')),
    dst_id        bigint NOT NULL REFERENCES observables(id) ON DELETE CASCADE,
    source        text NOT NULL,         -- 'dns','rdap','crtsh','har','bundle','urlscan','ipinfo','ct_stream'
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at  timestamptz NOT NULL DEFAULT now(),
    attrs         jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (src_id, rel, dst_id)
);
CREATE INDEX observable_relations_dst ON observable_relations (dst_id, rel);

INSERT INTO schema_migrations(version) VALUES ('0004_observables') ON CONFLICT DO NOTHING;
