-- 0011 · corpus expansion: third-party captures (urlscan scans) as a source, and the daily expansion job
--        (urlscan pivots → scan results → incidents; Meta ads → snapshot → landing URL → sandboxed capture).

INSERT INTO sources (key, kind, name, homepage, auth, license, redistribution, default_ttl) VALUES
 ('urlscan_scan', 'capture', 'urlscan.io public scan results (third-party captures, no visit by us)',
  'https://urlscan.io/', 'api_key', 'Public scans; commercial use needs urlscan permission', 'internal', '7 days')
ON CONFLICT (key) DO NOTHING;

INSERT INTO jobs (key, source_id, kind, schedule, interval_s, enabled, params, budget)
SELECT 'expand_daily', s.id, 'recapture', '45 6 * * *', 86400, true,
       '{"steps":["urlscan_pivots","urlscan_results","meta_snapshots","sandbox_capture","enrich","relink"]}'::jsonb,
       '{"urlscan_searches":60,"urlscan_results":200,"meta_snapshots":40,"captures":60}'::jsonb
FROM sources s WHERE s.key = 'urlscan_scan'
ON CONFLICT (key) DO NOTHING;

INSERT INTO schema_migrations(version) VALUES ('0011_expansion') ON CONFLICT DO NOTHING;
