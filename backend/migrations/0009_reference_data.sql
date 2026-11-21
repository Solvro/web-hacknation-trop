-- 0009 · reference data: source catalogue, observable & evidence types, embedding spaces (+HNSW),
--        enrichment providers, default jobs, baseline model version, label sets.
-- Strength priors are log-likelihood ratios log(m/u) before calibration (PLAN §6); M1 replaces them per model version.

-- ---------- sources (the source matrix, as data) ----------
INSERT INTO sources (key, kind, name, homepage, auth, license, redistribution, default_ttl) VALUES
 ('sample_v1',       'dataset',     'HackNation sample_v1 (teaser CTF backup)', NULL, 'none', 'Organizer data – no publication', 'never', NULL),
 ('organizer_bundle','dataset',     'Organizer archive bundle (archive_<domain>_<ts>/)', NULL, 'none', 'Organizer data – no publication', 'never', NULL),
 ('dane',            'dataset',     'HackNation DANE.zip (official dataset)', NULL, 'none', 'Organizer data – no publication', 'never', NULL),
 ('redpill_capture', 'capture',     'RED PILL Playwright capture worker', NULL, 'none', 'Own captures of public pages', 'internal', '6 hours'),
 ('meta_adlib_api',  'ad_library',  'Meta Ad Library API (ads_archive)', 'https://www.facebook.com/ads/library/api', 'identity_verified', 'Meta Platform Terms + Ad Library API terms; research/transparency use', 'internal', '6 hours'),
 ('meta_adlib_web',  'ad_library',  'Meta Ad Library public web UI (fallback, demo only)', 'https://www.facebook.com/ads/library/', 'none', 'Automated collection restricted by Meta ToS – manual/demo only', 'internal', '6 hours'),
 ('google_atc_bq',   'ad_library',  'Google Ads Transparency Center (BigQuery public dataset)', 'https://console.cloud.google.com/marketplace/product/bigquery-public-data/google-ads-transparency-center', 'account', 'Google Cloud public dataset terms', 'attribution', '1 day'),
 ('tiktok_ccl',      'ad_library',  'TikTok Commercial Content Library / API', 'https://developers.tiktok.com/products/commercial-content-api', 'account', 'TikTok Commercial Content API terms (approval required)', 'internal', '1 day'),
 ('certpl',          'threat_feed', 'CERT Polska warning list (Lista ostrzeżeń, API v2)', 'https://hole.cert.pl/domains/v2/', 'none', 'Any use incl. commercial; attribution optional, must not imply endorsement', 'open', '5 minutes'),
 ('openphish',       'threat_feed', 'OpenPhish community feed (GitHub)', 'https://github.com/openphish/public_feed', 'none', 'Non-commercial only; no redistribution', 'internal', '12 hours'),
 ('certspotter',     'ct',          'SSLMate Cert Spotter issuances API', 'https://sslmate.com/ct_search_api/', 'api_key', 'Keyless = personal/evaluation; 100 hostname q/h', 'internal', '1 day'),
 ('mnemonic_pdns',   'enrichment',  'mnemonic passive DNS (public)', 'https://docs.mnemonic.no/api/services/pdns/01-public_api.html', 'none', 'TLP:WHITE data; 10/min, 1000/day', 'internal', '7 days'),
 ('urlscan',         'enrichment',  'urlscan.io search/scan API', 'https://urlscan.io/docs/api/', 'api_key', 'Search keyless (30/min, 30 days back); results need key since 2026-05-04; commercial use needs permission', 'internal', '1 day'),
 ('crtsh',           'ct',          'crt.sh Certificate Transparency search', 'https://crt.sh/', 'none', 'Free (Sectigo); 5 req/min per IP on 443; often 502/slow', 'open', '1 day'),
 ('ct_stream',       'ct',          'Live CT stream (self-hosted certstream-server-go incl. static-ct tiled logs)', 'https://github.com/d-Rickyy-b/certstream-server-go', 'none', 'CT logs are public', 'open', NULL),
 ('rdap',            'enrichment',  'RDAP (IANA bootstrap → registry/registrar)', 'https://data.iana.org/rdap/dns.json', 'none', 'Registry terms of use; GDPR-redacted', 'internal', '7 days'),
 ('dns',             'enrichment',  'Active DNS resolution (dnspython / DoH)', NULL, 'none', 'Public resolvers', 'open', '6 hours'),
 ('ipinfo',          'enrichment',  'IPinfo Lite', 'https://ipinfo.io/lite', 'api_key', 'CC BY-SA 4.0, attribution required; free unlimited with token', 'attribution', '30 days'),
 ('internetdb',      'enrichment',  'Shodan InternetDB', 'https://internetdb.shodan.io/', 'none', 'Free, non-commercial use', 'internal', '7 days'),
 ('wayback',         'enrichment',  'Internet Archive Wayback CDX', 'https://web.archive.org/cdx/search/cdx', 'none', 'Internet Archive terms', 'attribution', '7 days'),
 ('extension',       'user_report', 'RED PILL browser extension reports', NULL, 'none', 'User-submitted; pseudonymised', 'internal', NULL),
 ('web_upload',      'user_report', 'Analyze screen uploads / "Sprawdź reklamę"', NULL, 'none', 'User-submitted', 'internal', NULL),
 ('analyst',         'manual',      'Analyst input', NULL, 'none', 'Internal', 'internal', NULL);

-- ---------- observable types ----------
INSERT INTO observable_types (type, layer, strength, prior_log_lr, compare, max_df_ratio, description) VALUES
 -- tracking
 ('fb_pixel',            'tracking','H',4.0,'exact',   0.05,'Meta pixel / dataset id (fbq init, facebook.com/tr?id=, signals/config/<id>, pixel= params)'),
 ('google_tag',          'tracking','H',3.5,'exact',   0.05,'Google tag ids, prefixed: AW-…, G-…, GTM-…, UA-…'),
 ('tiktok_pixel',        'tracking','H',4.0,'exact',   0.05,'TikTok pixel id (ttq.load / sdkid=)'),
 ('tracker_id',          'tracking','H',3.0,'exact',   0.05,'Other analytics account ids, prefixed: ym:, hotjar:, clarity:, …'),
 ('capi_gateway',        'tracking','H',4.0,'exact',   0.05,'Server-side Conversions-API gateway host (*.on.aws, *.run.app, …)'),
 ('meta_campaign_id',    'tracking','H',5.0,'exact',   0.02,'Meta campaign id leaked in landing URL params'),
 ('meta_adset_id',       'tracking','H',5.0,'exact',   0.02,'Meta ad set id leaked in landing URL params'),
 ('meta_ad_id',          'tracking','H',5.0,'exact',   0.02,'Meta ad id leaked in landing URL params'),
 ('tds_key',             'tracking','H',4.0,'exact',   0.05,'Traffic-distribution-system campaign key (Keitaro/Binom key=, campaign token)'),
 -- kit
 ('kit_endpoint',        'kit',     'M',1.5,'template',0.10,'Same-site API path template, ids → {uuid}/{hex}/{int}/{tok}; PLATFORM-level (multi-tenant kits)'),
 ('kit_tenant',          'kit',     'H',4.5,'exact',   0.05,'Tenant/account id inside a multi-tenant landing kit (landing-cdn/{TENANT}/…) = operator level'),
 ('lander_id',           'kit',     'H',3.5,'exact',   0.05,'Lander/template id (landing-cdn/{tenant}/{LANDER}/, /l/{uuid}/, /lander/{uuid}_…) = variant level'),
 ('lander_path',         'kit',     'M',2.5,'template',0.10,'Static lander directory template (/landers/u_bp_l_o/, /lander/<slug>/)'),
 ('url_param_schema',    'kit',     'M',1.5,'template',0.20,'Landing URL parameter grammar: names + value shapes'),
 ('asset_sha256',        'kit',     'H',3.0,'exact',   0.05,'sha256 of a JS/CSS/image body (public CDN libraries flagged noise)'),
 ('favicon_mmh3',        'kit',     'M',2.0,'exact',   0.10,'Shodan-style favicon mmh3'),
 ('third_party_host',    'kit',     'L',0.8,'exact',   0.20,'Third-party host loaded by the landing'),
 ('third_party_account', 'kit',     'H',3.5,'exact',   0.05,'Account/library id on a third-party service (pandavideo vz-…, cloudinary cloud, firebase project)'),
 ('html_signature',      'kit',     'L',1.0,'exact',   0.30,'Kit behaviour signature (hue-rotate anti-hash, back-button hijack, right-click block, fake comments); context, not a pivot'),
 ('form_schema',         'kit',     'M',1.5,'set',     0.20,'Sorted form field names + action template'),
 ('ad_naming',           'kit',     'M',2.0,'template',0.10,'Operator naming convention leaked in ad_name/adset_name/campaign_name'),
 -- infra
 ('etld1',               'infra',   'H',4.0,'exact',   0.05,'Registrable domain'),
 ('fqdn',                'infra',   'H',4.0,'exact',   0.05,'Fully-qualified host'),
 ('ip',                  'infra',   'M',1.5,'exact',   0.05,'IP address (CDN edges flagged noise)'),
 ('asn',                 'infra',   'L',0.3,'exact',   0.30,'Autonomous system'),
 ('cert',                'infra',   'H',3.5,'exact',   0.02,'Certificate identity <issuer_cn>/<serial hex> (merges precert + final cert)'),
 ('cert_batch',          'infra',   'M',1.5,'window',  0.10,'Issuer + issuance hour bucket'),
 ('nameserver',          'infra',   'L',0.5,'exact',   0.10,'Authoritative NS host'),
 ('ns_set',              'infra',   'M',1.5,'exact',   0.05,'Sorted NS set; a Cloudflare NS pair is assigned per account'),
 ('registration_batch',  'infra',   'M',2.0,'window',  0.05,'Registrar + registration hour bucket (domains bought together)'),
 ('registrar',           'infra',   'L',0.3,'exact',   0.30,'Registrar (RDAP)'),
 ('registrant_email',    'infra',   'H',4.0,'exact',   0.02,'Registrant e-mail (rare after GDPR)'),
 ('domain_pattern',      'infra',   'M',1.2,'template',0.10,'Domain lexical grammar (e.g. {word}{word}.click, finance{NN}-{lorem}{NN}.sbs)'),
 -- content
 ('headline_template',   'content', 'H',3.0,'template',0.10,'Landing headline with persons/brands masked'),
 ('clickbait_template',  'content', 'M',1.5,'template',0.20,'Ad text template with entities masked'),
 ('product',             'content', 'H',3.0,'exact',   0.05,'Product name (Kardivix, RelieFlex, …)'),
 ('phone',               'content', 'H',4.0,'exact',   0.02,'E.164 phone'),
 ('iban',                'content', 'H',5.0,'exact',   0.02,'IBAN (checksum-valid)'),
 ('email',               'content', 'H',4.0,'exact',   0.02,'E-mail address in page/ad'),
 ('telegram',            'content', 'H',4.0,'exact',   0.02,'Telegram handle / t.me link'),
 ('crypto_wallet',       'content', 'H',5.0,'exact',   0.02,'Crypto wallet address'),
 ('brand',               'content', 'L',0.7,'set',     0.30,'Impersonated brand / media outlet'),
 -- persons
 ('person',              'persons', 'M',1.2,'exact',   0.30,'Impersonated person (from name NER or face gallery)'),
 -- ad layer
 ('ad_page_id',          'ad',      'M',2.5,'exact',   0.05,'Advertiser page id'),
 ('advertiser_name',     'ad',      'L',0.5,'fuzzy',   0.10,'Advertiser display name'),
 ('ad_display_link',     'ad',      'L',0.5,'exact',   0.30,'Display link caption (often fake, e.g. AMAZON.COM)'),
 -- blocking-only keys (never evidence by themselves)
 ('lsh_text',            'blocking','0',0.0,'fuzzy',   NULL,'MinHash-LSH band of landing text shingles'),
 ('lsh_dom',             'blocking','0',0.0,'fuzzy',   NULL,'MinHash-LSH band of DOM tag-path shingles'),
 ('phash_band',          'blocking','0',0.0,'hamming', NULL,'16-bit band of a screenshot pHash (multi-index hashing)');

-- ---------- evidence types ----------
INSERT INTO evidence_types (type, layer, observable_type, kind, description)
SELECT type, layer, type, 'shared_value', 'Both incidents carry the same ' || type
FROM observable_types WHERE strength IN ('H','M','L');

INSERT INTO evidence_types (type, layer, kind, description) VALUES
 ('text_cosine',          'content', 'similarity','Cosine of text embeddings (landing + ad + OCR + ASR)'),
 ('text_minhash',         'content', 'similarity','Jaccard (MinHash) of text shingles – near-duplicate text'),
 ('dom_minhash',          'kit',     'similarity','Jaccard (MinHash) of DOM tag-path shingles'),
 ('headline_fuzzy',       'content', 'similarity','Trigram similarity of headline templates'),
 ('screenshot_phash',     'visual',  'similarity','Landing screenshot pHash Hamming distance'),
 ('screenshot_embedding', 'visual',  'similarity','Cosine of landing screenshot image embeddings'),
 ('creative_phash',       'visual',  'similarity','Ad creative pHash Hamming distance'),
 ('face_identity',        'persons', 'similarity','Same gallery identity detected in both'),
 ('face_embedding',       'persons', 'similarity','Cosine of face embeddings (no gallery identity)'),
 ('voice_embedding',      'media',   'similarity','Cosine of speaker embeddings (synthetic voice re-use)'),
 ('cert_batch_window',    'infra',   'window',    'Certificates from the same issuer within N hours'),
 ('domain_created_window','infra',   'window',    'Domains registered within N hours at the same registrar'),
 ('domain_dna',           'infra',   'similarity','Domain lexical-grammar similarity'),
 ('delivery_window',      'ad',      'window',    'Ads delivered in overlapping windows by related advertisers'),
 ('conflict_tracking',    'tracking','conflict',  'Both sides have tracking ids and none overlap (negative)'),
 ('conflict_kit',         'kit',     'conflict',  'Both sides have kit endpoints and none overlap (negative)'),
 ('llm_adjudication',     'model',   'model',     'LLM adjudicator verdict for the uncertain band'),
 ('m1_linker',            'model',   'model',     'Calibrated linkage model output'),
 ('analyst_must_link',    'human',   'human',     'Analyst confirmed same campaign'),
 ('analyst_cannot_link',  'human',   'human',     'Analyst rejected the link');

-- ---------- embedding spaces (first-class vectors) + one partial HNSW index per space ----------
INSERT INTO embedding_spaces (space, modality, model, dim, metric, inputs, notes) VALUES
 ('text.mmlw-roberta-base.v1', 'text',      'sdadas/mmlw-roberta-base',          768, 'cosine', '{landing_text,ad_text,ocr,asr,incident}', 'Polish retrieval encoder'),
 ('text.bge-m3.v1',            'text',      'BAAI/bge-m3',                       1024,'cosine', '{landing_text,ad_text,ocr,asr,incident}', 'Multilingual fallback'),
 ('text.qwen3-emb-0.6b.v1',    'text',      'Qwen/Qwen3-Embedding-0.6B',         1024,'cosine', '{landing_text,ad_text,ocr,asr,incident}', 'Used by experiments; bigger Qwen3-Embedding variants must be MRL-truncated to <=4000 dims for HNSW'),
 ('image.siglip-b16.v1',       'image',     'google/siglip-base-patch16-224',    768, 'cosine', '{screenshot,creative}',                   'Landing screenshots + ad creatives'),
 ('face.arcface.v1',           'face',      'insightface/arcface (or AuraFace)', 512, 'cosine', '{face}',                                  'Face identity (gallery kNN)'),
 ('voice.ecapa.v1',            'voice',     'speechbrain/spkrec-ecapa-voxceleb', 192, 'cosine', '{voice}',                                 'Speaker / synthetic-voice re-use'),
 ('multimodal.m2.v1',          'multimodal','redpill/m2-infra-supervised',       512, 'cosine', '{incident}',                              'M2 infra-supervised content encoder (moonshot)');

CREATE INDEX embeddings_hnsw_text_mmlw ON embeddings USING hnsw ((vec::halfvec(768)) halfvec_cosine_ops)
    WHERE space = 'text.mmlw-roberta-base.v1';
CREATE INDEX embeddings_hnsw_text_bgem3 ON embeddings USING hnsw ((vec::halfvec(1024)) halfvec_cosine_ops)
    WHERE space = 'text.bge-m3.v1';
CREATE INDEX embeddings_hnsw_text_qwen3 ON embeddings USING hnsw ((vec::halfvec(1024)) halfvec_cosine_ops)
    WHERE space = 'text.qwen3-emb-0.6b.v1';
CREATE INDEX embeddings_hnsw_image_siglip ON embeddings USING hnsw ((vec::halfvec(768)) halfvec_cosine_ops)
    WHERE space = 'image.siglip-b16.v1';
CREATE INDEX embeddings_hnsw_face ON embeddings USING hnsw ((vec::halfvec(512)) halfvec_cosine_ops)
    WHERE space = 'face.arcface.v1';
CREATE INDEX embeddings_hnsw_voice ON embeddings USING hnsw ((vec::halfvec(192)) halfvec_cosine_ops)
    WHERE space = 'voice.ecapa.v1';
CREATE INDEX embeddings_hnsw_m2 ON embeddings USING hnsw ((vec::halfvec(512)) halfvec_cosine_ops)
    WHERE space = 'multimodal.m2.v1';

-- ---------- enrichment providers: TTLs + client-side rate limits ----------
INSERT INTO enrichment_providers (provider, source_id, ttl_ok, ttl_not_found, ttl_error, rate_per_min, burst, notes)
SELECT p.provider, s.id, p.ttl_ok::interval, p.ttl_nf::interval, p.ttl_err::interval, p.rate, p.burst, p.notes
FROM (VALUES
 ('dns',        'dns',        '6 hours', '1 hour',  '10 minutes', 600, 50, 'dnspython against system/1.1.1.1 resolver'),
 ('rdap',       'rdap',       '7 days',  '1 day',   '30 minutes',  30,  5, 'IANA bootstrap; per-registry limits vary'),
 ('crtsh',      'crtsh',      '1 day',   '6 hours', '30 minutes',   4,  1, '5 req/min/IP limit; often slow/502: 60s timeout, negative cache, Cert Spotter fallback'),
 ('certspotter','certspotter','1 day',   '6 hours', '30 minutes',   1,  1, 'Keyless 100 hostname queries/hour'),
 ('mnemonic_pdns','mnemonic_pdns','7 days','1 day', '1 hour',      10,  1, '10/min, 1000/day, no key'),
 ('urlscan',    'urlscan',    '1 day',   '1 day',   '30 minutes',  60, 10, 'Keyed free plan: 120 search/min, 1000/h, 1000/day; result 120/min, 10000/day. Keyless: 30/min, 30 days back'),
 ('ipinfo',     'ipinfo',     '30 days', '30 days', '1 hour',     300, 20, 'Lite: country + ASN'),
 ('internetdb', 'internetdb', '7 days',  '7 days',  '1 hour',      60, 10, 'No key; ports/hostnames/tags'),
 ('wayback',    'wayback',    '7 days',  '1 day',   '1 hour',      30,  5, 'CDX API'),
 ('certpl',     'certpl',     '5 minutes','5 minutes','5 minutes',  12,  1, 'Conditional GET (ETag/Last-Modified) of v2 lists'),
 ('meta_adlib', 'meta_adlib_api','6 hours','6 hours','15 minutes', 60,  5, 'Graph API app-level rate limiting (BUC)')
) AS p(provider, source_key, ttl_ok, ttl_nf, ttl_err, rate, burst, notes)
JOIN sources s ON s.key = p.source_key;

-- ---------- baseline model version + label sets ----------
INSERT INTO model_versions (name, kind, version, params, is_active)
SELECT 'rules', 'rules', 'v0',
       jsonb_build_object('weight', 'strength_prior x idf', 'priors',
                          (SELECT jsonb_object_agg(type, prior_log_lr) FROM observable_types)),
       true;

INSERT INTO label_sets (key, kind, description) VALUES
 ('sample_v1_manual', 'analyst',     'Rough manual grouping of sample_v1 (PLAN §2) – to verify'),
 ('dane_gt',          'ground_truth','Organizer ground truth from DANE.zip, if provided'),
 ('weak_lf_v1',       'weak',        'Snorkel-style labelling functions (same pixel / kit+gateway / …)'),
 ('analyst',          'analyst',     'Accept/reject decisions from the Triage UI');

-- ---------- default scheduled jobs (hunter/oracle jobs that need keys start disabled) ----------
INSERT INTO jobs (key, source_id, kind, schedule, interval_s, enabled, params, budget)
SELECT j.key, s.id, j.kind, j.schedule, j.interval_s, j.enabled, j.params::jsonb, j.budget::jsonb
FROM (VALUES
 ('certpl_sync',          'certpl',        'certpl_sync',    '*/10 * * * *', 600, true,  '{"url":"https://hole.cert.pl/domains/v2/domains.json","fallback":"https://hole.cert.pl/domains/v2/domains.txt"}', '{}'),
 ('openphish_sync',       'openphish',     'openphish_sync', '17 */12 * * *', 43200, false, '{"url":"https://raw.githubusercontent.com/openphish/public_feed/refs/heads/main/feed.txt"}', '{}'),
 ('enrich_refresh',       'dns',           'enrich_refresh', '30 3 * * *', 86400, true,  '{"providers":["dns","rdap","crtsh"],"scope":"active_campaign_domains"}', '{"max_lookups":2000}'),
 ('recapture_active',     'redpill_capture','recapture',     '0 */6 * * *', 21600, true,  '{"scope":"active_campaign_entry_urls","profiles":["fb_inapp_android_pl"]}', '{"max_new_captures":50}'),
 ('recluster_incremental',NULL,            'recluster',      '*/5 * * * *', 300,   true,  '{"mode":"incremental"}', '{}'),
 ('retention_daily',      NULL,            'retention',      '15 4 * * *', 86400, true,  '{"capture_requests_months":6,"oracle_days":90,"cache_purge":true}', '{}'),
 ('ct_stream',            'ct_stream',     'ct_stream',      'stream',     NULL,  false, '{"min_score":0.7,"tlds":["click","live","top","pro","ink","sbs","shop","online"]}', '{}'),
 ('hunter:meta:lures_pl', 'meta_adlib_api','adlib_search',   '20 */2 * * *', 7200, false,
     '{"ad_reached_countries":["PL"],"ad_active_status":"ACTIVE","search_terms":["PILNE","InPost","Brzoska","NBP","inwestycja","cukrzyca","Gazeta.pl"],"search_type":"KEYWORD_UNORDERED"}',
     '{"max_api_calls":200,"max_new_captures":50}'),
 ('hunter:google_atc:pl', 'google_atc_bq', 'atc_bq_pull',    '0 5 * * 1',  604800, false, '{"region":"PL","days":8}', '{"max_bytes_billed":70000000000}')
) AS j(key, source_key, kind, schedule, interval_s, enabled, params, budget)
LEFT JOIN sources s ON s.key = j.source_key;

INSERT INTO schema_migrations(version) VALUES ('0009_reference_data') ON CONFLICT DO NOTHING;
