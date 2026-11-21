"""Meta Ad Library API hunter (ads_archive, DSA coverage of all EU-delivered ads).

    set META_ACCESS_TOKEN=...      (see docs/db/META_AD_LIBRARY_ACCESS.md — identity verification needed)
    python -m scrapers.hunter.meta_adlib --terms "Brzoska" --terms "PILNE" --dry-run       # print the request only
    python -m scrapers.hunter.meta_adlib --job "hunter:meta:lures_pl"                     # run a configured job
    python -m scrapers.hunter.meta_adlib --fixture scrapers/hunter/fixtures/ads_archive_fictional.json --ingest

Each ad becomes an 'ad_only' incident (source meta_adlib_api, ref meta:<ad_archive_id>) with an
ad_observations row per run (reach growth → "heating up"). The API has no landing URL: landing capture is
queued separately (capture_tasks) once the link is known (snapshot rendering / extension report / OCR).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from psycopg.types.json import Jsonb

from ..ingest.model import AdDraft, IncidentDraft, ObsHit
from ..util.text import find_brands, find_persons

GRAPH = "https://graph.facebook.com/v27.0/ads_archive"
FIELDS = ["id", "ad_creation_time", "ad_creative_bodies", "ad_creative_link_captions", "ad_creative_link_descriptions",
          "ad_creative_link_titles", "ad_delivery_start_time", "ad_delivery_stop_time", "ad_snapshot_url",
          "page_id", "page_name", "publisher_platforms", "languages", "eu_total_reach", "target_ages",
          "target_gender", "target_locations", "beneficiary_payers", "age_country_gender_reach_breakdown"]


def build_params(terms: str, countries: list[str], active: str = "ACTIVE", search_type: str = "KEYWORD_UNORDERED",
                 date_min: str | None = None, limit: int = 100, after: str | None = None) -> dict:
    p = {"search_terms": terms[:100], "ad_reached_countries": json.dumps(countries), "ad_active_status": active,
         "ad_type": "ALL", "search_type": search_type, "fields": ",".join(FIELDS), "limit": str(limit)}
    if date_min:
        p["ad_delivery_date_min"] = date_min
    if after:
        p["after"] = after
    return p


def _dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00").replace("+0000", "+00:00"))
    except ValueError:
        return None


def redact_token(s):
    """ad_snapshot_url embeds the caller's access token — never persist it (DB, artifacts, logs)."""
    return re.sub(r"access_token=[^&\"\s]*", "access_token=REDACTED", s) if isinstance(s, str) else s


def to_incident(ad: dict) -> IncidentDraft:
    ad = {**ad, "ad_snapshot_url": redact_token(ad.get("ad_snapshot_url"))}
    body = (ad.get("ad_creative_bodies") or [None])[0]
    title = (ad.get("ad_creative_link_titles") or [None])[0]
    caption = (ad.get("ad_creative_link_captions") or [None])[0]
    reach = ad.get("eu_total_reach")
    draft = AdDraft(
        platform="meta", library_id=str(ad["id"]), advertiser_platform_id=str(ad.get("page_id") or "") or None,
        advertiser_name=ad.get("page_name"), body=body, title=title, display_link=caption,
        delivery_start=_dt(ad.get("ad_delivery_start_time")), delivery_stop=_dt(ad.get("ad_delivery_stop_time")),
        eu_total_reach=int(reach) if str(reach or "").isdigit() else None,
        targeting={k: ad.get(k) for k in ("target_ages", "target_gender", "target_locations") if ad.get(k)},
        snapshot_url=ad.get("ad_snapshot_url"), raw=ad)
    inc = IncidentDraft(source_key="meta_adlib_api", source_ref=f"meta:{ad['id']}", kind="ad_only",
                        observed_at=draft.delivery_start or datetime.now(timezone.utc), ad=draft,
                        title=title or (body or "")[:120], sensitivity="internal")
    ctx = {"ad_archive_id": str(ad["id"])}
    if draft.advertiser_platform_id:
        inc.observables.append(ObsHit("ad_page_id", draft.advertiser_platform_id, "ad.page_id", display=draft.advertiser_name, context=ctx))
    if draft.advertiser_name:
        inc.observables.append(ObsHit("advertiser_name", draft.advertiser_name.lower(), "ad.page_name", display=draft.advertiser_name, context=ctx))
    if caption:
        inc.observables.append(ObsHit("ad_display_link", caption.lower(), "ad.link_caption", display=caption, context=ctx))
    text = " ".join(x for x in (body, title) if x)
    if body:
        tpl = re.sub(r"\d+", "{NUM}", body.strip())
        for _, _, _, (a, b) in sorted(find_persons(tpl), key=lambda x: -x[3][0]):
            tpl = tpl[:a] + "{PER}" + tpl[b:]
        inc.observables.append(ObsHit("clickbait_template", tpl, "ad.body", display=body[:200], context=ctx))
    for name, role, conf, _ in find_persons(text):
        inc.observables.append(ObsHit("person", name, "ad.text", confidence=conf, context=ctx, attrs={"role": role}))
    for b in find_brands(text):
        inc.observables.append(ObsHit("brand", b.lower(), "ad.text", display=b, context=ctx))
    inc.quality = {"available": ["ad_api"], "missing": ["landing_url", "creative_media"], "errors": []}
    return inc


def fetch_pages(token: str, params: dict, max_pages: int):
    with httpx.Client(timeout=60) as c:
        url, p = GRAPH, {**params, "access_token": token}
        for _ in range(max_pages):
            r = c.get(url, params=p)
            if r.status_code != 200:
                err = r.json().get("error", {}) if r.headers.get("content-type", "").startswith("application/json") else {}
                hint = ""
                if err.get("error_subcode") == 2332004:
                    hint = " → app tokens are not accepted: use a USER token of an identity-confirmed person with a role on the app"
                elif err.get("code") == 10 or err.get("error_subcode") == 2332002:
                    hint = (" → the token's user has no Ad Library API access yet: finish identity confirmation at "
                            "https://www.facebook.com/ID and accept https://www.facebook.com/ads/library/api, then generate a NEW token")
                raise RuntimeError(
                    f"Graph API {r.status_code}: code={err.get('code')} subcode={err.get('error_subcode')} "
                    f"{err.get('message', r.text[:200])} | {err.get('error_user_title') or ''} {err.get('error_user_msg') or ''}{hint}")
            data = r.json()
            yield data.get("data", []), (data.get("paging") or {}).get("cursors", {}).get("after")
            nxt = (data.get("paging") or {}).get("next")
            if not nxt:
                return
            url, p = nxt, None


GRAPH_ROOT = "https://graph.facebook.com/v27.0"
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def app_token() -> str | None:
    app_id, secret = os.environ.get("META_APP_ID"), os.environ.get("META_APP_SECRET")
    return f"{app_id}|{secret}" if app_id and secret else None


def debug_token(token: str) -> dict:
    """Which app issued the token, validity, expiry, scopes — never prints the token itself."""
    at = app_token()
    if not at:
        return {"error": "META_APP_ID / META_APP_SECRET not set"}
    r = httpx.get(f"{GRAPH_ROOT}/debug_token", params={"input_token": token, "access_token": at}, timeout=30)
    d = r.json().get("data", r.json())
    return {k: d.get(k) for k in ("app_id", "application", "type", "is_valid", "expires_at", "data_access_expires_at",
                                  "scopes", "error")}


def exchange_token(short_token: str) -> tuple[str | None, dict]:
    """Short-lived user token → ~60-day token (needs the issuing app's id + secret). No login dialog involved."""
    app_id, secret = os.environ.get("META_APP_ID"), os.environ.get("META_APP_SECRET")
    r = httpx.get(f"{GRAPH_ROOT}/oauth/access_token", timeout=30, params={
        "grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": secret, "fb_exchange_token": short_token})
    d = r.json()
    return d.get("access_token"), {"status": r.status_code, "expires_in": d.get("expires_in"), "error": d.get("error")}


def set_env(key: str, value: str) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    out, done = [], False
    for ln in lines:
        if ln.split("=", 1)[0].strip() == key:
            out.append(f"{key}={value}")
            done = True
        else:
            out.append(ln)
    if not done:
        out.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--token-info", action="store_true", help="show which app issued META_ACCESS_TOKEN and its expiry")
    ap.add_argument("--exchange-token", action="store_true", help="swap META_ACCESS_TOKEN for a ~60-day token in .env")
    ap.add_argument("--use-app-token", action="store_true", help="query with META_APP_ID|META_APP_SECRET instead")
    ap.add_argument("--terms", action="append", default=[])
    ap.add_argument("--countries", default="PL")
    ap.add_argument("--job", default=None, help="jobs.key with params (search_terms list, countries …)")
    ap.add_argument("--max-pages", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fixture", type=Path, default=None, help="offline: a saved ads_archive JSON response")
    ap.add_argument("--ingest", action="store_true")
    args = ap.parse_args()

    if args.token_info or args.exchange_token:
        tok = os.environ.get("META_ACCESS_TOKEN")
        if not tok:
            print("META_ACCESS_TOKEN not set", file=sys.stderr)
            return 2
        info = debug_token(tok)
        exp = info.get("expires_at")
        info["expires_at"] = datetime.fromtimestamp(exp, timezone.utc).isoformat() if exp else exp
        print("token:", info)
        if args.exchange_token:
            new, meta = exchange_token(tok)
            print("exchange:", meta)
            if new:
                set_env("META_ACCESS_TOKEN", new)
                print("long-lived token written to .env (value not shown)")
        return 0

    terms, countries = list(args.terms), args.countries.split(",")
    conn = None
    if args.job or args.ingest:
        from ..store.db import connect
        conn = connect()
    if args.job:
        params = conn.execute("SELECT params FROM jobs WHERE key = %s", (args.job,)).fetchone()[0]
        terms = terms or params.get("search_terms", [])
        countries = params.get("ad_reached_countries", countries)

    batches: list[tuple[str, list[dict]]] = []
    if args.fixture:
        batches.append(("fixture", json.loads(args.fixture.read_text(encoding="utf-8")).get("data", [])))
    else:
        token = app_token() if args.use_app_token else os.environ.get("META_ACCESS_TOKEN")
        for t in terms or ["PILNE"]:
            params = build_params(t, countries)
            if args.dry_run or not token:
                shown = {k: v for k, v in params.items()}
                print(f"GET {GRAPH}?{httpx.QueryParams(shown)}&access_token=<META_ACCESS_TOKEN>")
                if not token and not args.dry_run:
                    print("META_ACCESS_TOKEN not set — see docs/db/META_AD_LIBRARY_ACCESS.md", file=sys.stderr)
                continue
            for page, _after in fetch_pages(token, params, args.max_pages):
                batches.append((t, page))

    if not args.ingest:
        for t, ads in batches:
            for ad in ads:
                inc = to_incident(ad)
                print(f"[{t}] {inc.source_ref} {inc.ad.advertiser_name!r}: {(inc.ad.body or '')[:80]!r}")
        return 0

    from ..store import artifacts
    from ..store.db import Loader
    loader = Loader(conn, artifacts.from_env(), sensitivity="internal")
    run_id = loader.start_run("meta_adlib_api", trigger="manual", params={"terms": terms, "fixture": str(args.fixture or "")},
                              job_key=args.job)
    n = 0
    for _t, ads in batches:
        for ad in ads:
            inc = to_incident(ad)
            iid = loader.ingest(inc, run_id)
            ad_id = conn.execute("SELECT ad_id FROM incidents WHERE id = %s", (iid,)).fetchone()[0]
            conn.execute(
                """INSERT INTO ad_observations (ad_id, run_id, is_active, eu_total_reach, raw) VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT DO NOTHING""",
                (ad_id, run_id, inc.ad.delivery_stop is None, inc.ad.eu_total_reach,
                 Jsonb({"snapshot_url": inc.ad.snapshot_url})))
            n += 1
    loader.finish_run(run_id, "ok", {**loader.stats, "ads": n})
    conn.commit()
    print(f"ingested {n} ad(s) into run {run_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
