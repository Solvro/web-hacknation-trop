"""Google Ads Transparency Center hunter (BigQuery public dataset, EEA incl. PL).

    pip install google-cloud-bigquery && gcloud auth application-default login   (BigQuery sandbox works)
    python -m scrapers.hunter.google_atc --days 2 --dry-run      # prints SQL + bytes that would be scanned
    python -m scrapers.hunter.google_atc --days 2 --ingest --max-rows 5000

The dataset has advertiser + creative ids, region stats and the Transparency Center page URL — no ad text,
no landing URL, no media. Its value for us: advertiser identity/verification, delivery windows in PL,
and removed_creative_stats (Google's own removal reasons) as weak labels. Always select explicit columns:
the tables are large and the free tier is 1 TiB scanned / month.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone

from psycopg.types.json import Jsonb

from ..ingest.model import AdDraft, IncidentDraft, ObsHit

DATASET = "bigquery-public-data.google_ads_transparency_center"

SQL_ACTIVE = f"""
SELECT c.advertiser_id, c.advertiser_disclosed_name, c.advertiser_legal_name, c.advertiser_location,
       c.advertiser_verification_status, c.creative_id, c.creative_page_url, c.ad_format_type, c.topic,
       rs.region_code, rs.first_shown, rs.last_shown, rs.times_shown_lower_bound, rs.times_shown_upper_bound
FROM `{DATASET}.creative_stats` AS c, UNNEST(c.region_stats) AS rs
WHERE rs.region_code = @region
  AND SAFE_CAST(rs.last_shown AS DATE) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
"""

SQL_REMOVED = f"""
SELECT r.creative_page_url, rs.region_code, rs.first_shown, rs.last_shown,
       d.removal_reason, d.violation_category, d.decision_type
FROM `{DATASET}.removed_creative_stats` AS r, UNNEST(r.region_stats) AS rs, UNNEST(r.disapproval) AS d
WHERE rs.region_code = @region
  AND SAFE_CAST(rs.last_shown AS DATE) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
"""


# Registry granularity: one row per advertiser active in the region (the creative-level table is ~4M rows/2 days for PL).
SQL_ADVERTISERS = f"""
SELECT c.advertiser_id, ANY_VALUE(c.advertiser_disclosed_name) AS name, ANY_VALUE(c.advertiser_legal_name) AS legal_name,
       ANY_VALUE(c.advertiser_location) AS location, ANY_VALUE(c.advertiser_verification_status) AS verification,
       COUNT(DISTINCT c.creative_id) AS creatives,
       MIN(SAFE_CAST(rs.first_shown AS DATE)) AS first_shown, MAX(SAFE_CAST(rs.last_shown AS DATE)) AS last_shown,
       ARRAY_AGG(DISTINCT c.topic IGNORE NULLS LIMIT 5) AS topics,
       ARRAY_AGG(DISTINCT c.ad_format_type IGNORE NULLS LIMIT 5) AS formats
FROM `{DATASET}.creative_stats` AS c, UNNEST(c.region_stats) AS rs
WHERE rs.region_code = @region
  AND SAFE_CAST(rs.last_shown AS DATE) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
GROUP BY c.advertiser_id
"""

def _date(v):
    """region_stats dates arrive as STRING ('YYYY-MM-DD') in the public dataset."""
    from datetime import date
    if v is None or isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def to_incident(row: dict) -> IncidentDraft:
    first, last = _date(row.get("first_shown")), _date(row.get("last_shown"))
    ad = AdDraft(platform="google", library_id=row["creative_id"], advertiser_platform_id=row["advertiser_id"],
                 advertiser_name=row.get("advertiser_disclosed_name"), snapshot_url=row.get("creative_page_url"),
                 delivery_start=datetime.combine(first, datetime.min.time(), timezone.utc) if first else None,
                 delivery_stop=datetime.combine(last, datetime.min.time(), timezone.utc) if last else None,
                 raw={k: str(v) for k, v in row.items()})
    inc = IncidentDraft(source_key="google_atc_bq", source_ref=f"google:{row['creative_id']}:{row.get('region_code')}",
                        kind="ad_only", observed_at=ad.delivery_start, ad=ad, sensitivity="internal",
                        quality={"available": ["ad_registry"], "missing": ["ad_text", "landing_url", "creative_media"], "errors": []})
    ctx = {"creative_id": row["creative_id"]}
    inc.observables.append(ObsHit("ad_page_id", f"google:{row['advertiser_id']}", "ad.advertiser_id",
                                  display=row.get("advertiser_disclosed_name"), context=ctx))
    if row.get("advertiser_disclosed_name"):
        inc.observables.append(ObsHit("advertiser_name", row["advertiser_disclosed_name"].lower(), "ad.advertiser_name", context=ctx))
    return inc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="PL")
    ap.add_argument("--days", type=int, default=2)
    ap.add_argument("--removed", action="store_true", help="query removed_creative_stats instead")
    ap.add_argument("--advertisers", action="store_true", help="aggregate to one row per active advertiser (registry)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ingest", action="store_true")
    ap.add_argument("--max-rows", type=int, default=5000)
    args = ap.parse_args()
    # note: removed creatives do not appear in creative_stats, so their owners cannot be resolved from this dataset
    sql = SQL_ADVERTISERS if args.advertisers else SQL_REMOVED if args.removed else SQL_ACTIVE
    try:
        from google.cloud import bigquery
    except ImportError:
        print(sql)
        print("google-cloud-bigquery not installed: pip install google-cloud-bigquery; then "
              "gcloud auth application-default login (BigQuery sandbox is enough)", file=sys.stderr)
        return 0 if args.dry_run else 2
    client = bigquery.Client()
    params = [bigquery.ScalarQueryParameter("region", "STRING", args.region),
              bigquery.ScalarQueryParameter("days", "INT64", args.days)]
    if args.dry_run:
        job = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False, query_parameters=params))
        print(sql)
        print(f"would scan {job.total_bytes_processed / 1e9:.2f} GB")
        return 0
    job = client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params, maximum_bytes_billed=70 * 10**9))
    rows = [dict(r) for r in job.result(max_results=args.max_rows)]
    print(f"{len(rows)} row(s); scanned {(job.total_bytes_processed or 0) / 1e9:.2f} GB, billed {(job.total_bytes_billed or 0) / 1e9:.2f} GB")
    if not args.ingest:
        for r in rows[:10]:
            print(r)
        return 0
    from ..store.db import Loader, connect
    from ..store import artifacts
    with connect() as conn:
        loader = Loader(conn, artifacts.from_env(), sensitivity="internal")
        run_id = loader.start_run("google_atc_bq", trigger="manual",
                                  params={"region": args.region, "days": args.days, "removed": args.removed},
                                  job_key="hunter:google_atc:pl")
        if args.advertisers:
            stats = load_advertisers(conn, rows)
        else:
            stats = load_removed(conn, rows) if args.removed else load_registry(conn, rows, loader.source_id("google_atc_bq"))
        loader.finish_run(run_id, "ok", {**stats, "rows": len(rows), "gb_scanned": round((job.total_bytes_processed or 0) / 1e9, 2)})
        conn.commit()
    print(stats)
    return 0


CREATIVE_URL = re.compile(r"(?:/advertiser/(AR\d+))?/creative/(CR\d+)")   # removed ads: /removed/creative/CR…


def load_registry(conn, rows: list[dict], source_id: int) -> dict:
    """Bulk upsert into advertisers + ads (platform='google'). Google ads are a *registry*: they become incidents
    only when they meet scam evidence (an advertiser or creative that also shows up in an incident or report)."""
    with conn.cursor() as cur:
        cur.execute("""CREATE TEMP TABLE _atc (advertiser_id text, name text, legal_name text, location text, verification text,
                       creative_id text, page_url text, format text, topic text, region text, first_shown date,
                       last_shown date, shown_lo bigint, shown_hi bigint) ON COMMIT DROP""")
        with cur.copy("COPY _atc FROM STDIN") as cp:
            for r in rows:
                cp.write_row((r.get("advertiser_id"), r.get("advertiser_disclosed_name"), r.get("advertiser_legal_name"),
                              r.get("advertiser_location"), r.get("advertiser_verification_status"), r.get("creative_id"),
                              r.get("creative_page_url"), r.get("ad_format_type"), r.get("topic"), r.get("region_code"),
                              _date(r.get("first_shown")), _date(r.get("last_shown")),
                              r.get("times_shown_lower_bound"), r.get("times_shown_upper_bound")))
        cur.execute("""INSERT INTO advertisers (platform, platform_id, name, country, verified, raw)
                       SELECT DISTINCT ON (advertiser_id) 'google', advertiser_id, name, location,
                              upper(verification) = 'VERIFIED',
                              jsonb_build_object('legal_name', legal_name, 'verification', verification)
                       FROM _atc WHERE advertiser_id IS NOT NULL
                       ON CONFLICT (platform, platform_id) WHERE platform_id IS NOT NULL
                       DO UPDATE SET last_seen_at = now(), name = EXCLUDED.name""")
        n_adv = cur.rowcount
        cur.execute("""INSERT INTO ads (platform, library_id, dedupe_key, advertiser_id, snapshot_url, delivery_start,
                                        delivery_stop, source_id, raw)
                       SELECT DISTINCT ON (t.creative_id) 'google', t.creative_id, 'google:' || t.creative_id, a.id,
                              t.page_url, t.first_shown, t.last_shown, %s,
                              jsonb_build_object('format', t.format, 'topic', t.topic, 'region', t.region,
                                                 'times_shown', jsonb_build_array(t.shown_lo, t.shown_hi))
                       FROM _atc t LEFT JOIN advertisers a ON a.platform = 'google' AND a.platform_id = t.advertiser_id
                       WHERE t.creative_id IS NOT NULL
                       ORDER BY t.creative_id, t.last_shown DESC
                       ON CONFLICT (dedupe_key) DO UPDATE SET last_seen_at = now(),
                         delivery_stop = greatest(ads.delivery_stop, EXCLUDED.delivery_stop), raw = ads.raw || EXCLUDED.raw""",
                    (source_id,))
        n_ads = cur.rowcount
    return {"advertisers_upserted": n_adv, "ads_upserted": n_ads}


def load_advertisers(conn, rows: list[dict], removed: bool = False) -> dict:
    """Advertiser registry (one row per advertiser). removed=True merges removal stats and links the removed
    creatives (already in ads from --removed) to their advertiser."""
    with conn.cursor() as cur:
        cur.execute("""CREATE TEMP TABLE _adv (advertiser_id text, name text, location text, verification text,
                       info jsonb, creative_ids text[]) ON COMMIT DROP""")
        with cur.copy("COPY _adv FROM STDIN") as cp:
            for r in rows:
                info = ({"removed_creatives": r.get("removed_creatives"), "misrepresentation": r.get("misrepresentation")}
                        if removed else
                        {"legal_name": r.get("legal_name"), "creatives_active": r.get("creatives"),
                         "first_shown": str(r.get("first_shown")), "last_shown": str(r.get("last_shown")),
                         "topics": list(r.get("topics") or []), "formats": list(r.get("formats") or [])})
                cp.write_row((r.get("advertiser_id"), r.get("name"), r.get("location"), r.get("verification"),
                              Jsonb({"google": info}) if not removed else Jsonb({"google_removed": info}),
                              list(r.get("creative_ids") or []) if removed else None))
        cur.execute("""INSERT INTO advertisers (platform, platform_id, name, country, verified, raw)
                       SELECT 'google', advertiser_id, name, location,
                              upper(verification) = 'VERIFIED',
                              info || jsonb_build_object('verification', verification)
                       FROM _adv WHERE advertiser_id IS NOT NULL
                       ON CONFLICT (platform, platform_id) WHERE platform_id IS NOT NULL
                       DO UPDATE SET last_seen_at = now(), name = coalesce(EXCLUDED.name, advertisers.name),
                                     raw = advertisers.raw || EXCLUDED.raw""")
        n = cur.rowcount
        linked = 0
        if removed:
            cur.execute("""UPDATE ads x SET advertiser_id = a.id
                           FROM _adv t JOIN advertisers a ON a.platform = 'google' AND a.platform_id = t.advertiser_id,
                                unnest(t.creative_ids) AS cid
                           WHERE x.platform = 'google' AND x.library_id = cid""")
            linked = cur.rowcount
    return {"advertisers_upserted": n, "removed_creatives_linked": linked}


def load_removed(conn, rows: list[dict]) -> dict:
    """Google's own removals → ads.raw.removed (weak labels: violation category, removal reason)."""
    with conn.cursor() as cur:
        cur.execute("""CREATE TEMP TABLE _rm (creative_id text, page_url text, first_shown date, last_shown date,
                       reason text, category text, decision text) ON COMMIT DROP""")
        with cur.copy("COPY _rm FROM STDIN") as cp:
            for r in rows:
                m = CREATIVE_URL.search(r.get("creative_page_url") or "")
                if m:
                    cp.write_row((m.group(2), r.get("creative_page_url"), _date(r.get("first_shown")),
                                  _date(r.get("last_shown")), r.get("removal_reason"), r.get("violation_category"),
                                  r.get("decision_type")))
        cur.execute("""INSERT INTO ads (platform, library_id, dedupe_key, snapshot_url, delivery_start, delivery_stop, raw)
                       SELECT 'google', creative_id, 'google:' || creative_id, min(page_url), min(first_shown), max(last_shown),
                              jsonb_build_object('removed', jsonb_build_object(
                                  'reasons', jsonb_agg(DISTINCT reason), 'categories', jsonb_agg(DISTINCT category),
                                  'decisions', jsonb_agg(DISTINCT decision)))
                       FROM _rm GROUP BY creative_id
                       ON CONFLICT (dedupe_key) DO UPDATE SET raw = ads.raw || EXCLUDED.raw,
                         delivery_stop = greatest(ads.delivery_stop, EXCLUDED.delivery_stop)""")
        n = cur.rowcount
    return {"removed_creatives": n}


if __name__ == "__main__":
    sys.exit(main())
