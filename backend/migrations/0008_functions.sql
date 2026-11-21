-- 0008 · functions & views: rarity stats, blocking, graph traversal, temporal membership, partitions, export

-- ---------- corpus statistics / rarity ----------
CREATE TABLE corpus_stats (
    id          boolean PRIMARY KEY DEFAULT true CHECK (id),   -- single row
    n_incidents int NOT NULL DEFAULT 0,                        -- non-duplicate incidents
    n_campaigns int NOT NULL DEFAULT 0,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
INSERT INTO corpus_stats DEFAULT VALUES;

-- idf against the current corpus size; stays correct when N grows even if df was cached earlier
CREATE OR REPLACE FUNCTION idf_of(p_df int) RETURNS real
LANGUAGE sql STABLE PARALLEL SAFE AS
$$ SELECT ln((greatest(n_incidents,1) + 1.0) / (greatest(p_df,0) + 1.0))::real FROM corpus_stats $$;

-- Recompute df / idf / auto-noise. p_since = only observables seen in incidents ingested since then
-- (incremental mode after a batch); NULL = full recompute (nightly).
CREATE OR REPLACE FUNCTION refresh_observable_stats(p_since timestamptz DEFAULT NULL)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
    v_n int;
    v_updated int;
BEGIN
    UPDATE corpus_stats SET
        n_incidents = (SELECT count(*) FROM incidents WHERE duplicate_of IS NULL),
        n_campaigns = (SELECT count(*) FROM campaigns WHERE status IN ('candidate','active','dormant')),
        updated_at  = now()
    RETURNING n_incidents INTO v_n;

    WITH touched AS (
        SELECT DISTINCT io.observable_id
        FROM incident_observables io
        WHERE p_since IS NULL OR io.first_seen_at >= p_since
    ), df AS (
        SELECT io.observable_id,
               count(DISTINCT io.incident_id) FILTER (WHERE i.duplicate_of IS NULL) AS dfi,
               count(DISTINCT cm.campaign_id) AS dfc
        FROM incident_observables io
        JOIN touched t USING (observable_id)
        JOIN incidents i ON i.id = io.incident_id
        LEFT JOIN campaign_memberships cm ON cm.incident_id = io.incident_id AND cm.valid_to IS NULL
        GROUP BY io.observable_id
    )
    UPDATE observables o
       SET df_incidents = df.dfi,
           df_campaigns = df.dfc,
           idf          = ln((v_n + 1.0) / (df.dfi + 1.0)),
           stats_at     = now()
      FROM df
     WHERE o.id = df.observable_id;
    GET DIAGNOSTICS v_updated = ROW_COUNT;

    -- automatic noise: very common AND spread over many campaigns (needs a corpus big enough to judge)
    UPDATE observables o
       SET noise = true, noise_reason = 'auto:df_ratio'
      FROM observable_types t
     WHERE o.type = t.type AND NOT o.noise AND t.max_df_ratio IS NOT NULL
       AND v_n >= 50
       AND o.df_incidents::real / v_n > t.max_df_ratio
       AND o.df_campaigns >= 3;
    RETURN v_updated;
END $$;

-- ---------- blocking: candidate pairs from the inverted index ----------
-- Returns incidents sharing at least one non-noise, sufficiently rare H/M observable with p_incident,
-- ranked by summed idf. This is the O(n·k) replacement for all-pairs comparison.
CREATE OR REPLACE FUNCTION blocking_candidates(
    p_incident bigint, p_max_df int DEFAULT 1000, p_min_idf real DEFAULT 0.3, p_limit int DEFAULT 200)
RETURNS TABLE (other_id bigint, n_shared int, sum_idf real, shared_observables bigint[])
LANGUAGE sql STABLE AS $$
    WITH mine AS (
        SELECT DISTINCT o.id, idf_of(o.df_incidents) AS idf
        FROM incident_observables io
        JOIN observables o ON o.id = io.observable_id
        JOIN observable_types t ON t.type = o.type
        WHERE io.incident_id = p_incident
          AND NOT o.noise
          AND t.strength IN ('H','M','0')          -- '0' = blocking-only keys (LSH bands, pHash bands)
          AND o.df_incidents <= p_max_df
    ), postings AS (
        SELECT DISTINCT io2.incident_id, m.id, m.idf
        FROM mine m
        JOIN incident_observables io2 ON io2.observable_id = m.id
        JOIN incidents i2 ON i2.id = io2.incident_id AND i2.duplicate_of IS NULL
        WHERE io2.incident_id <> p_incident AND m.idf >= p_min_idf
    )
    SELECT incident_id, count(*)::int, sum(idf)::real, array_agg(id ORDER BY idf DESC)
    FROM postings
    GROUP BY incident_id
    ORDER BY sum(idf) DESC
    LIMIT p_limit
$$;

-- ---------- graph traversal ----------
-- (1) Infrastructure pivot over observable_relations (domain → ip → domain, cert → SAN domains, …).
--     Recursive CTE with path-based cycle protection; noise nodes (CDN edges) are never entered and
--     low-strength hubs (registrar, ASN, shared NS) are reached but not expanded.
CREATE OR REPLACE FUNCTION infra_pivot(p_seed bigint, p_max_depth int DEFAULT 3, p_max_fanout int DEFAULT 100)
RETURNS TABLE (observable_id bigint, depth int, via_rel text, parent_id bigint, path bigint[])
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE walk(observable_id, depth, via_rel, parent_id, path, expandable) AS (
        SELECT p_seed, 0, NULL::text, NULL::bigint, ARRAY[p_seed], true
        UNION ALL
        SELECT nb.other, w.depth + 1, nb.rel, w.observable_id, w.path || nb.other,
               (t.strength IN ('H','M'))
        FROM walk w
        CROSS JOIN LATERAL (
            SELECT x.other, x.rel FROM (
                SELECT r.dst_id AS other, r.rel FROM observable_relations r WHERE r.src_id = w.observable_id
                UNION ALL
                SELECT r.src_id, r.rel FROM observable_relations r WHERE r.dst_id = w.observable_id
            ) x LIMIT p_max_fanout
        ) nb
        JOIN observables o ON o.id = nb.other
        JOIN observable_types t ON t.type = o.type
        WHERE w.expandable
          AND w.depth < p_max_depth
          AND NOT o.noise
          AND NOT nb.other = ANY (w.path)
    )
    SELECT DISTINCT ON (observable_id) observable_id, depth, via_rel, parent_id, path
    FROM walk
    ORDER BY observable_id, depth
$$;

-- (2) Incident neighbourhood over the incident–observable bipartite graph (k hops of shared rare values).
CREATE OR REPLACE FUNCTION incident_neighborhood(p_seed bigint, p_depth int DEFAULT 2, p_max_df int DEFAULT 50)
RETURNS TABLE (incident_id bigint, depth int, via_observable bigint, via_type text, via_value text)
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE walk(incident_id, depth, via_observable, path) AS (
        SELECT p_seed, 0, NULL::bigint, ARRAY[p_seed]
        UNION ALL
        SELECT io2.incident_id, w.depth + 1, io1.observable_id, w.path || io2.incident_id
        FROM walk w
        JOIN incident_observables io1 ON io1.incident_id = w.incident_id
        JOIN observables o ON o.id = io1.observable_id
                          AND NOT o.noise AND o.df_incidents BETWEEN 2 AND p_max_df
        JOIN observable_types t ON t.type = o.type AND t.strength IN ('H','M')
        JOIN incident_observables io2 ON io2.observable_id = io1.observable_id
                                     AND NOT io2.incident_id = ANY (w.path)
        WHERE w.depth < p_depth
    )
    SELECT DISTINCT ON (w.incident_id) w.incident_id, w.depth, w.via_observable, o.type, o.value
    FROM walk w LEFT JOIN observables o ON o.id = w.via_observable
    ORDER BY w.incident_id, w.depth
$$;

-- ---------- temporal campaign membership (SCD2) ----------
CREATE OR REPLACE FUNCTION set_membership(
    p_incident bigint, p_campaign bigint, p_decision text, p_decided_by text,
    p_score real DEFAULT NULL, p_margin real DEFAULT NULL, p_run bigint DEFAULT NULL,
    p_reason jsonb DEFAULT '{}', p_variant bigint DEFAULT NULL, p_runner_up bigint DEFAULT NULL,
    p_p_value real DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    cur    campaign_memberships%ROWTYPE;
    v_had  boolean;
    new_id bigint;
BEGIN
    SELECT * INTO cur FROM campaign_memberships
     WHERE incident_id = p_incident AND valid_to IS NULL FOR UPDATE;
    v_had := FOUND;
    IF v_had AND cur.campaign_id IS NOT DISTINCT FROM p_campaign
             AND cur.variant_id IS NOT DISTINCT FROM p_variant
             AND cur.decision = p_decision THEN
        RETURN cur.id;                                    -- unchanged: keep history quiet
    END IF;
    IF v_had THEN
        UPDATE campaign_memberships SET valid_to = now() WHERE id = cur.id;
        IF cur.campaign_id IS NOT NULL AND cur.campaign_id IS DISTINCT FROM p_campaign THEN
            INSERT INTO campaign_events (campaign_id, kind, payload, run_id, actor)
            VALUES (cur.campaign_id, 'member_removed',
                    jsonb_build_object('incident_id', p_incident, 'moved_to', p_campaign), p_run, p_decided_by);
            UPDATE campaigns SET n_members = n_members - 1, version = version + 1, updated_at = now()
             WHERE id = cur.campaign_id;
        END IF;
    END IF;
    INSERT INTO campaign_memberships (incident_id, campaign_id, variant_id, run_id, decision, decided_by,
                                      score, margin, runner_up_campaign_id, p_value, reason)
    VALUES (p_incident, p_campaign, p_variant, p_run, p_decision, p_decided_by,
            p_score, p_margin, p_runner_up, p_p_value, coalesce(p_reason, '{}'))
    RETURNING id INTO new_id;
    IF p_campaign IS NOT NULL AND (NOT v_had OR cur.campaign_id IS DISTINCT FROM p_campaign) THEN
        INSERT INTO campaign_events (campaign_id, kind, payload, run_id, actor)
        VALUES (p_campaign, 'member_added',
                jsonb_build_object('incident_id', p_incident, 'score', p_score, 'decision', p_decision),
                p_run, p_decided_by);
        UPDATE campaigns c SET n_members = n_members + 1, version = version + 1, updated_at = now(),
               first_seen_at = least(c.first_seen_at, i.observed_at),
               last_seen_at  = greatest(c.last_seen_at, i.observed_at)
          FROM incidents i WHERE c.id = p_campaign AND i.id = p_incident;
    END IF;
    RETURN new_id;
END $$;

-- ---------- monthly partitions for capture_requests / oracle_candidates ----------
-- Creates the partition for p_month, moving any rows that already landed in the DEFAULT partition.
CREATE OR REPLACE FUNCTION ensure_month_partition(p_parent text, p_month date)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    v_start date := date_trunc('month', p_month)::date;
    v_stop  date := (date_trunc('month', p_month) + interval '1 month')::date;
    v_name  text := p_parent || '_' || to_char(v_start, 'YYYYMM');
    v_def   text := p_parent || '_default';
    v_col   text := CASE p_parent WHEN 'oracle_candidates' THEN 'seen_at' ELSE 'captured_at' END;
BEGIN
    IF to_regclass(v_name) IS NOT NULL THEN
        RETURN v_name;
    END IF;
    EXECUTE format('ALTER TABLE %I DETACH PARTITION %I', p_parent, v_def);
    EXECUTE format('CREATE TABLE %I (LIKE %I INCLUDING DEFAULTS INCLUDING CONSTRAINTS)', v_name, p_parent);
    EXECUTE format('INSERT INTO %I SELECT * FROM %I WHERE %I >= %L AND %I < %L',
                   v_name, v_def, v_col, v_start, v_col, v_stop);
    EXECUTE format('DELETE FROM %I WHERE %I >= %L AND %I < %L', v_def, v_col, v_start, v_col, v_stop);
    EXECUTE format('ALTER TABLE %I ATTACH PARTITION %I FOR VALUES FROM (%L) TO (%L)',
                   p_parent, v_name, v_start, v_stop);
    EXECUTE format('ALTER TABLE %I ATTACH PARTITION %I DEFAULT', p_parent, v_def);
    RETURN v_name;
END $$;

-- ---------- views ----------
CREATE VIEW v_current_membership AS
SELECT cm.incident_id, cm.campaign_id, c.code AS campaign_code, c.name AS campaign_name,
       c.family_id, cm.variant_id, cm.decision, cm.decided_by, cm.score, cm.margin, cm.valid_from
FROM campaign_memberships cm
LEFT JOIN campaigns c ON c.id = cm.campaign_id
WHERE cm.valid_to IS NULL;

-- Campaign DNA: values carried by members, with rarity, for campaign cards / Oracle / rules export.
CREATE VIEW v_campaign_dna AS
SELECT cm.campaign_id, o.id AS observable_id, o.type, t.layer, t.strength, o.value, o.display,
       count(DISTINCT cm.incident_id) AS members_with, o.df_incidents, o.df_campaigns,
       idf_of(o.df_incidents) AS idf
FROM campaign_memberships cm
JOIN incident_observables io ON io.incident_id = cm.incident_id
JOIN observables o ON o.id = io.observable_id
JOIN observable_types t ON t.type = o.type
WHERE cm.valid_to IS NULL AND NOT o.noise
GROUP BY cm.campaign_id, o.id, t.layer, t.strength;

-- Per-incident feature coverage by layer (drives "missing ≠ different" and the quality badge).
CREATE VIEW v_incident_coverage AS
SELECT i.id AS incident_id, i.source_ref, t.layer, count(DISTINCT o.id) AS n_values,
       count(DISTINCT o.id) FILTER (WHERE NOT o.noise) AS n_informative
FROM incidents i
JOIN incident_observables io ON io.incident_id = i.id
JOIN observables o ON o.id = io.observable_id
JOIN observable_types t ON t.type = o.type
GROUP BY i.id, i.source_ref, t.layer;

-- Unified edge list for graph export (GraphML / Neo4j CSV / igraph). Node ids are typed strings.
CREATE VIEW v_graph_edges AS
SELECT 'inc:' || io.incident_id AS src, 'obs:' || io.observable_id AS dst,
       'HAS_' || upper(o.type) AS rel, NULL::real AS weight, io.field AS detail
FROM incident_observables io JOIN observables o ON o.id = io.observable_id
WHERE NOT o.noise
UNION ALL
SELECT 'obs:' || r.src_id, 'obs:' || r.dst_id, upper(r.rel), NULL, r.source
FROM observable_relations r
UNION ALL
SELECT 'inc:' || l.a_id, 'inc:' || l.b_id, 'LINKED', coalesce(l.p_same, l.score), 'L' || l.level
FROM pair_links l WHERE l.is_current
UNION ALL
SELECT 'inc:' || m.incident_id, 'cmp:' || m.campaign_id, 'MEMBER_OF', m.score, m.decision
FROM campaign_memberships m WHERE m.valid_to IS NULL AND m.campaign_id IS NOT NULL
UNION ALL
SELECT 'cmp:' || c.id, 'opf:' || c.family_id, 'OPERATED_BY', NULL, NULL
FROM campaigns c WHERE c.family_id IS NOT NULL;

INSERT INTO schema_migrations(version) VALUES ('0008_functions') ON CONFLICT DO NOTHING;
