-- 0012 · platform-level values in multi-tenant scam kits
--
-- Kit A is a landing/cloaking SaaS rented by many operators (tenant uuid in /landing-cdn/{TENANT}/…).
-- Its SDK files, API paths and shared static assets appear under many tenants, so they identify the
-- PLATFORM, not the campaign/operator. A value seen with >= p_min_tenants distinct kit tenants is marked
-- noise_reason = 'platform:multi_tenant' (zero weight for campaign linking and blocking) and keeps the
-- tenant count in attrs, so "uses kit A" stays queryable (postings are not deleted).

CREATE OR REPLACE FUNCTION mark_platform_values(p_min_tenants int DEFAULT 3)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE n int;
BEGIN
    WITH tenant_of AS (
        SELECT io.incident_id, o.value AS tenant
        FROM incident_observables io JOIN observables o ON o.id = io.observable_id
        WHERE o.type = 'kit_tenant'
    ), spread AS (
        SELECT io.observable_id, count(DISTINCT t.tenant) AS tenants
        FROM incident_observables io
        JOIN tenant_of t ON t.incident_id = io.incident_id
        JOIN observables o ON o.id = io.observable_id
        WHERE o.type IN ('asset_sha256','kit_endpoint','lander_path','html_signature','third_party_host',
                         'capi_gateway','url_param_schema','favicon_mmh3')
        GROUP BY io.observable_id
        HAVING count(DISTINCT t.tenant) >= p_min_tenants
    )
    UPDATE observables o
       SET noise = true,
           noise_reason = coalesce(o.noise_reason, 'platform:multi_tenant'),
           attrs = o.attrs || jsonb_build_object('kit_tenants', s.tenants)
      FROM spread s
     WHERE o.id = s.observable_id AND NOT o.noise;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END $$;

INSERT INTO schema_migrations(version) VALUES ('0012_platform_values') ON CONFLICT DO NOTHING;
