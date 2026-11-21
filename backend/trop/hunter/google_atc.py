"""Google Ads Transparency Center (BigQuery public dataset, EEA incl. PL): advertiser enrichment.

No ad text, no landing URL, no media: the value is advertiser identity / verification, PL delivery windows and Google's own
removals (weak labels). Cost control (free tier 1 TiB/month): every query is DRY-RUN first, refused above MAX_SCAN_BYTES
(2 GB) and run with maximum_bytes_billed. Disabled (status "disabled") when Application Default Credentials are missing.
Credentials: GOOGLE_APPLICATION_CREDENTIALS, else ~/.config/gcloud-trop/application_default_credentials.json
(CLOUDSDK_CONFIG=~/.config/gcloud-trop). The file is never read for printing.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from trop.config import settings
from trop.enrich import cache

DATASET = "bigquery-public-data.google_ads_transparency_center"
MAX_SCAN_BYTES = int(float(os.environ.get("TROP_ATC_MAX_GB", "2")) * 10**9)   # lead cap: 2 GB per query
DEFAULT_ADC = Path.home() / ".config" / "gcloud-trop" / "application_default_credentials.json"
cache.SHORT_TTL["google_atc"] = 86400

SQL_ADVERTISERS = """
SELECT c.advertiser_id, ANY_VALUE(c.advertiser_disclosed_name) AS name, ANY_VALUE(c.advertiser_legal_name) AS legal_name,
       ANY_VALUE(c.advertiser_location) AS location, ANY_VALUE(c.advertiser_verification_status) AS verification,
       COUNT(DISTINCT c.creative_id) AS creatives,
       MIN(SAFE_CAST(rs.first_shown AS DATE)) AS first_shown, MAX(SAFE_CAST(rs.last_shown AS DATE)) AS last_shown,
       ARRAY_AGG(DISTINCT c.topic IGNORE NULLS LIMIT 5) AS topics
FROM `bigquery-public-data.google_ads_transparency_center.creative_stats` AS c, UNNEST(c.region_stats) AS rs
WHERE rs.region_code = @region
  AND SAFE_CAST(rs.last_shown AS DATE) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
GROUP BY c.advertiser_id
"""

SQL_BY_NAME = """
SELECT c.advertiser_id, ANY_VALUE(c.advertiser_disclosed_name) AS name, ANY_VALUE(c.advertiser_legal_name) AS legal_name,
       ANY_VALUE(c.advertiser_location) AS location, ANY_VALUE(c.advertiser_verification_status) AS verification,
       COUNT(DISTINCT c.creative_id) AS creatives,
       MIN(SAFE_CAST(rs.first_shown AS DATE)) AS first_shown, MAX(SAFE_CAST(rs.last_shown AS DATE)) AS last_shown
FROM `bigquery-public-data.google_ads_transparency_center.creative_stats` AS c, UNNEST(c.region_stats) AS rs
WHERE rs.region_code = @region AND LOWER(c.advertiser_disclosed_name) IN UNNEST(@names)
GROUP BY c.advertiser_id
"""


def credentials_path() -> Path | None:
    p = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not p:                                       # .env is not parsed into os.environ by pydantic: read the one key
        env = Path(settings.model_config["env_file"][0])
        if env.is_file():
            for ln in env.read_text(encoding="utf-8").splitlines():
                if ln.startswith("GOOGLE_APPLICATION_CREDENTIALS="):
                    p = ln.split("=", 1)[1].strip().strip('"')
    cand = Path(p) if p else DEFAULT_ADC
    return cand if cand.is_file() else None


def credentials_status() -> str:
    return "set" if credentials_path() else "missing"


def _client():
    from google.cloud import bigquery
    from google.oauth2 import service_account  # noqa: F401  (ensures google-auth present)
    cred = credentials_path()
    if not cred:
        raise RuntimeError("Google ADC missing: Ads Transparency source disabled")
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", str(cred))
    project = settings.google_cloud_project
    try:
        project = json.loads(cred.read_text()).get("quota_project_id") or project
    except (OSError, ValueError):
        pass
    return bigquery, bigquery.Client(project=project)


def _dry(client, bq, sql: str, params: list) -> int:
    d = client.query(sql, job_config=bq.QueryJobConfig(dry_run=True, use_query_cache=False, query_parameters=params))
    return int(d.total_bytes_processed or 0)


def _run(sql: str, params: list, max_rows: int = 5000, dry_only: bool = False) -> dict[str, Any]:
    """Dry-run first, refuse above the cap. NOTE: creative_stats is ~164M rows; measured 2026-11-21: any query that touches
    advertiser_id / names + region_stats scans 6-35 GB (TABLESAMPLE does not reduce the billed bytes), so with the default
    2 GB cap these calls are refused (nothing billed). Raise TROP_ATC_MAX_GB (e.g. 8 = <1 % of the monthly free tier)
    deliberately to run them."""
    bq, client = _client()
    full = sql.replace("{SAMPLE}", "")
    scan = _dry(client, bq, full, params)
    pct = None
    if dry_only:
        return {"scan_bytes": scan, "sampled_pct": pct, "rows": []}
    if scan > MAX_SCAN_BYTES:
        return {"error": f"refused: would scan {scan / 1e9:.2f} GB > {MAX_SCAN_BYTES / 1e9:.0f} GB cap", "scan_bytes": scan, "rows": []}
    sql = full
    try:
        job = client.query(sql, job_config=bq.QueryJobConfig(query_parameters=params, maximum_bytes_billed=MAX_SCAN_BYTES))
        rows = [dict(r) for r in job.result(max_results=max_rows)]
    except Exception as e:      # bytesBilledLimitExceeded etc.: nothing is billed
        return {"error": f"{type(e).__name__}: {str(e)[:200]}", "scan_bytes": scan, "sampled_pct": pct, "rows": []}
    return {"scan_bytes": scan, "sampled_pct": pct, "billed_bytes": job.total_bytes_billed, "rows": [{k: (str(v) if not isinstance(v, (int, float, str, list, type(None))) else v) for k, v in r.items()} for r in rows]}


def advertiser_lookup(names: list[str], region: str = "PL") -> dict[str, Any]:
    """Advertisers (by disclosed name) seen in our data -> registry rows. Cached 24 h; disabled without ADC."""
    names = sorted({n.lower().strip() for n in names if n})[:200]
    if not names:
        return {"rows": []}
    if not credentials_path():
        return {"disabled": "google ADC missing", "rows": []}
    key = f"adv:{region}:" + ",".join(names)
    hit = cache.get("google_atc", key)
    if hit is not None and hit.status == "ok":
        return hit.data
    if cache.is_offline():
        return {"offline": True, "rows": []}
    bq = __import__("google.cloud.bigquery", fromlist=["bigquery"])
    out = _run(SQL_BY_NAME, [bq.ScalarQueryParameter("region", "STRING", region), bq.ArrayQueryParameter("names", "STRING", names)])
    if not out.get("error"):
        cache.put("google_atc", key, cache.Result("ok", out))
    return out


def advertiser_registry(days: int = 2, region: str = "PL", dry_run: bool = False, max_rows: int = 5000) -> dict[str, Any]:
    """One row per advertiser active in `region` in the last `days` days (dry-run first; refused above 2 GB)."""
    if not credentials_path():
        return {"disabled": "google ADC missing", "rows": []}
    bq = __import__("google.cloud.bigquery", fromlist=["bigquery"])
    return _run(SQL_ADVERTISERS, [bq.ScalarQueryParameter("region", "STRING", region), bq.ScalarQueryParameter("days", "INT64", days)],
                max_rows, dry_only=dry_run)
