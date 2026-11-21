"""urlscan.io search pivots (SEARCH ONLY — this module never submits scans).

    python -m scrapers.enrich.urlscan domain example.com      # what urlscan saw on a domain
    python -m scrapers.enrich.urlscan pivots --budget 40       # campaign-asset pivots → oracle_candidates
    python -m scrapers.enrich.urlscan query 'hash:<sha256>'    # raw search

Why search-only: submitting a scan makes urlscan visit (and, for public/unlisted scans, publish) the URL.
Sample/DANE URLs are organizer data and must not be published; live captures are our own worker's job.

Pivots (what turns one incident into new campaign domains):
  asset_sha256 (kit JS/CSS/images shared by ≥2 incidents)  →  hash:<sha256>     other pages loading the same bytes
  capi_gateway / rare third-party host                     →  domain:<host>     other pages talking to the same backend
  non-CDN origin IP                                         →  page.ip:"<ip>"   other sites on the same origin server
Hits on domains we have not seen become oracle_candidates(source='urlscan') with the pivot as explanation,
and are checked against the CERT PL mirror (listed vs. not yet listed).

Quotas (free account): 120 searches/min, 1,000/hour, 1,000/day — the --budget flag caps a run.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from psycopg.types.json import Jsonb

from ..ingest.extract import cdn_of
from ..ingest.model import RelationDraft
from ..store import artifacts
from ..store.db import Loader, connect
from ..util.urls import etld1_of
from .http import CachedClient

API = "https://urlscan.io/api/v1/search/"


def _ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def search(conn, q: str, size: int = 100) -> dict:
    key = os.environ.get("URLSCAN_API_KEY")
    headers = {"API-Key": key} if key else {}
    res = CachedClient(conn, "urlscan").get_json(f"search:{size}:{q}", API, params={"q": q, "size": size},
                                                 headers=headers, not_found_codes=(404,))
    if res.status != "ok":
        return {"results": [], "error": res.error or res.status, "http_status": res.http_status, "cached": res.cached}
    data = res.data or {}
    data["cached"] = res.cached
    return data


def _summ(r: dict) -> dict:
    t, p = r.get("task", {}), r.get("page", {})
    return {"uuid": t.get("uuid"), "time": t.get("time"), "task_url": t.get("url"), "task_domain": t.get("domain"),
            "visibility": t.get("visibility"), "source": t.get("source"), "url": p.get("url"),
            "domain": (p.get("domain") or "").lower(), "apex": (p.get("apexDomain") or "").lower(),
            "ip": p.get("ip"), "asn": p.get("asn"), "asnname": p.get("asnname"), "country": p.get("country"),
            "server": p.get("server"), "title": p.get("title"), "status": p.get("status"),
            "tls_issuer": p.get("tlsIssuer"), "tls_valid_from": p.get("tlsValidFrom"),
            "domain_age_days": p.get("apexDomainAgeDays") or p.get("domainAgeDays"),
            "umbrella_rank": p.get("umbrellaRank"), "screenshot": r.get("screenshot")}


def classify_pivot(scans: list[dict]) -> tuple[str, dict]:
    """Is a pivot value campaign infrastructure or a shared service? Decided from what else uses it.

    shared_service : many distinct sites, mostly OLD domains, DIVERSE titles  (hosted CAPI gateway, analytics SaaS)
    campaign       : otherwise — young domains (fresh scam domains) or homogeneous titles (one lander planted on
                     many hijacked old sites) both indicate one kit / one operator.
    """
    by_apex: dict[str, dict] = {}
    for s in scans:
        d = s["apex"] or etld1_of(s["domain"])
        if d:
            by_apex.setdefault(d, s)
    n = len(by_apex)
    if n == 0:
        return "empty", {"domains": 0}
    ages = [s["domain_age_days"] for s in by_apex.values() if isinstance(s["domain_age_days"], int)]
    old_share = sum(a > 365 for a in ages) / len(ages) if ages else 0.0
    titles = [(s["title"] or "").strip().lower()[:60] for s in by_apex.values() if s["title"]]
    title_diversity = len(set(titles)) / len(titles) if titles else 1.0
    stats = {"domains": n, "old_share": round(old_share, 2), "title_diversity": round(title_diversity, 2)}
    if n >= 20 and old_share > 0.5 and title_diversity > 0.6:
        return "shared_service", stats
    return "campaign", stats


def enrich_domain(loader: Loader, domain: str) -> dict:
    """What urlscan has seen for a landing domain: IPs over time, redirects into it, pages that load it."""
    etld1 = etld1_of(domain)
    data = search(loader.conn, f"domain:{etld1}")
    scans = [_summ(r) for r in data.get("results", [])]
    for s in scans:
        at = {"at": s["time"], "urlscan_uuid": s["uuid"]}
        if s["domain"] and etld1_of(s["domain"]) == etld1:
            if s["ip"]:
                cdn = cdn_of(s["ip"])
                loader.observable_id("ip", s["ip"], noise_reason=f"cdn:{cdn}" if cdn else None, attrs={"cdn": cdn})
                loader.relate(RelationDraft(("fqdn", s["domain"]), "resolves_to", ("ip", s["ip"]), "urlscan", at))
                if s["asn"] and not cdn:
                    loader.relate(RelationDraft(("ip", s["ip"]), "in_asn", ("asn", s["asn"].upper()), "urlscan",
                                                {"name": s["asnname"]}))
            if s["task_domain"] and s["task_domain"].lower() != s["domain"]:
                # someone submitted a different URL that ended up here: a TDS / redirector in front of the lander
                loader.relate(RelationDraft(("fqdn", s["task_domain"].lower()), "redirects_to", ("fqdn", s["domain"]),
                                            "urlscan", at))
        elif s["domain"]:
            # a page on another site requested something from this domain
            loader.relate(RelationDraft(("fqdn", s["domain"]), "loads_from", ("fqdn", etld1), "urlscan", at))
    loader.conn.commit()
    times = sorted(s["time"] for s in scans if s["time"])
    return {"domain": etld1, "scans": len(scans), "total": data.get("total"), "first": times[0] if times else None,
            "last": times[-1] if times else None,
            "page_domains": sorted({s["domain"] for s in scans if s["domain"]})[:10],
            "ips": sorted({s["ip"] for s in scans if s["ip"]})[:10],
            "titles": sorted({(s["title"] or "")[:60] for s in scans if s["title"]})[:5],
            "error": data.get("error"), "cached": data.get("cached")}


PIVOT_SQL = """
-- campaign-specific values worth a pivot: shared by >= %(min_df)s incidents, not noise
SELECT o.type, o.value, o.display, o.df_incidents,
       array_agg(DISTINCT i.entry_etld1) FILTER (WHERE i.entry_etld1 IS NOT NULL) AS seen_on
FROM observables o
JOIN incident_observables io ON io.observable_id = o.id
JOIN incidents i ON i.id = io.incident_id
WHERE NOT o.noise
  AND o.df_incidents >= %(min_df)s
  AND ((o.type = 'asset_sha256' AND coalesce(o.display, '') !~* '\\.(woff2?|ttf|svg)$')
       OR o.type IN ('capi_gateway', 'third_party_host')
       OR (o.type = 'ip' AND EXISTS (SELECT 1 FROM obs_ips x WHERE x.observable_id = o.id AND NOT coalesce(x.is_cdn, false))))
GROUP BY o.id
ORDER BY CASE o.type WHEN 'capi_gateway' THEN 0 WHEN 'asset_sha256' THEN 1 WHEN 'ip' THEN 2 ELSE 3 END,
         o.df_incidents DESC
LIMIT %(limit)s
"""

PIVOT_QUERY = {"asset_sha256": lambda v: f"hash:{v}", "capi_gateway": lambda v: f"domain:{v}",
               "third_party_host": lambda v: f"domain:{v}", "ip": lambda v: f'page.ip:"{v}"'}
PIVOT_SCORE = {"asset_sha256": 0.9, "capi_gateway": 0.9, "ip": 0.6, "third_party_host": 0.5}


def run_pivots(loader: Loader, budget: int = 40, min_df: int = 2) -> dict:
    conn = loader.conn
    known = {r[0] for r in conn.execute(
        """SELECT DISTINCT o.value FROM observables o JOIN incident_observables io ON io.observable_id = o.id
           WHERE o.type = 'etld1' AND io.field LIKE 'landing.%%'""")}
    rows = conn.execute(PIVOT_SQL, {"min_df": min_df, "limit": budget}).fetchall()
    stats = {"queries": 0, "hits": 0, "new_domains": 0, "already_known": 0, "errors": 0,
             "shared_service_values": 0, "brand_assets": 0, "popular_skipped": 0}
    found: dict[str, dict] = {}
    for typ, value, display, df, seen_on in rows:
        q = PIVOT_QUERY[typ](value)
        data = search(conn, q)
        stats["queries"] += 1
        if data.get("error"):
            stats["errors"] += 1
            continue
        scans = [_summ(r) for r in data.get("results", [])]
        verdict, vstats = classify_pivot(scans)
        if verdict == "shared_service":
            # external rarity says this value is NOT operator infrastructure: zero weight everywhere
            conn.execute("UPDATE observables SET noise = true, noise_reason = %s, attrs = attrs || %s WHERE type = %s AND value = %s",
                         ("urlscan:shared_service", Jsonb({"urlscan_pivot": vstats}), typ, value))
            stats["shared_service_values"] += 1
            continue
        popular = [s for s in scans if s["umbrella_rank"]]
        if popular and typ == "asset_sha256":
            # the same bytes live on a popular legitimate site: a copied brand asset (logo, stock photo)
            conn.execute("UPDATE observables SET noise = true, noise_reason = %s WHERE type = %s AND value = %s",
                         (f"brand_asset:{popular[0]['apex'] or popular[0]['domain']}", typ, value))
            stats["brand_assets"] += 1
            continue
        for s in scans:
            stats["hits"] += 1
            d = s["apex"] or etld1_of(s["domain"])
            if s["umbrella_rank"]:
                stats["popular_skipped"] += 1
                continue
            if not d or d in known or (typ == "third_party_host" and etld1_of(value) == d):
                stats["already_known"] += d in known
                continue
            f = found.setdefault(d, {"fqdn": s["domain"], "etld1": d, "first": s["time"], "pivots": [], "titles": set(),
                                     "ips": set(), "tls_issuer": s["tls_issuer"], "uuids": []})
            f["first"] = min(f["first"] or s["time"], s["time"] or f["first"])
            f["pivots"].append({"type": typ, "value": value[:80], "display": (display or "")[:120], "df": df,
                                "seen_on": seen_on})
            if s["title"]:
                f["titles"].add(s["title"][:100])
            if s["ip"]:
                f["ips"].add(s["ip"])
            f["uuids"].append(s["uuid"])
    for d, f in found.items():
        types = {p["type"] for p in f["pivots"]}
        score = min(0.99, max(PIVOT_SCORE[t] for t in types) + 0.05 * (len({(p['type'], p['value']) for p in f['pivots']}) - 1))
        listed = conn.execute("SELECT first_seen_at FROM certpl_domains WHERE domain = %s OR etld1 = %s ORDER BY 1 LIMIT 1",
                              (d, d)).fetchone()
        exists = conn.execute("SELECT 1 FROM oracle_candidates WHERE etld1 = %s AND source = 'urlscan'", (d,)).fetchone()
        features = {"pivots": f["pivots"][:20], "titles": sorted(f["titles"])[:5], "ips": sorted(f["ips"])[:5],
                    "tls_issuer": f["tls_issuer"], "urlscan_uuids": f["uuids"][:10]}
        explanation = {"why": [f"{p['type']} shared with {', '.join(p['seen_on'] or [])}" for p in f["pivots"][:5]]}
        if exists:
            conn.execute("UPDATE oracle_candidates SET score = greatest(score, %s), features = %s, explanation = %s, "
                         "certpl_listed_at = %s WHERE etld1 = %s AND source = 'urlscan'",
                         (score, Jsonb(features), Jsonb(explanation), listed[0] if listed else None, d))
        else:
            conn.execute(
                """INSERT INTO oracle_candidates (seen_at, fqdn, etld1, source, score, features, explanation, certpl_listed_at)
                   VALUES (%s, %s, %s, 'urlscan', %s, %s, %s, %s)""",
                (_ts(f["first"]) or datetime.now(timezone.utc), f["fqdn"] or d, d, score, Jsonb(features),
                 Jsonb(explanation), listed[0] if listed else None))
            stats["new_domains"] += 1
    conn.commit()
    stats["candidates"] = len(found)
    return stats


def fetch_result(conn, uuid: str) -> tuple[dict | None, bytes | None, bytes | None]:
    """Result JSON (cached in enrichment_cache), rendered DOM and screenshot of an existing public scan."""
    import httpx
    key = os.environ.get("URLSCAN_API_KEY")
    headers = {"API-Key": key} if key else {}
    res = CachedClient(conn, "urlscan").get_json(f"result:{uuid}", f"https://urlscan.io/api/v1/result/{uuid}/",
                                                 headers=headers)
    if res.status != "ok":
        return None, None, None
    dom = shot = None
    with httpx.Client(timeout=60, headers=headers, follow_redirects=True) as c:
        try:
            r = c.get(f"https://urlscan.io/dom/{uuid}/")
            dom = r.content if r.status_code == 200 else None
            r = c.get(f"https://urlscan.io/screenshots/{uuid}.png")
            shot = r.content if r.status_code == 200 and r.content[:4] == b"\x89PNG" else None
        except httpx.HTTPError:
            pass
    return res.data, dom, shot


def load_results(loader: Loader, limit: int = 50, min_score: float = 0.5) -> dict:
    """Turn urlscan Oracle candidates into full incidents from their latest public scan (no visit by us)."""
    from ..ingest.urlscan_result import to_incident
    conn = loader.conn
    rows = conn.execute(
        """SELECT id, seen_at, etld1, features->'urlscan_uuids'->>0 FROM oracle_candidates
           WHERE source = 'urlscan' AND status = 'new' AND score >= %s AND features ? 'urlscan_uuids'
           ORDER BY score DESC, seen_at DESC LIMIT %s""", (min_score, limit)).fetchall()
    stats = {"candidates": len(rows), "incidents": 0, "no_result": 0}
    for cid, seen_at, etld1, uuid in rows:
        result, dom, shot = fetch_result(conn, uuid)
        if not result:
            stats["no_result"] += 1
            continue
        try:
            inc = to_incident(result, dom, shot)
            iid = loader.ingest(inc)
            conn.execute("UPDATE oracle_candidates SET status = 'captured', confirmed_incident_id = %s "
                         "WHERE id = %s AND seen_at = %s", (iid, cid, seen_at))
            conn.commit()
        except Exception as e:  # one odd scan must not stop the batch
            conn.rollback()
            stats["errors"] = stats.get("errors", 0) + 1
            print(f"  {etld1:<34} ERROR {type(e).__name__}: {str(e)[:120]}", flush=True)
            continue
        stats["incidents"] += 1
        print(f"  {etld1:<34} → incident {iid}  {(inc.title or '')[:60]!r}", flush=True)
    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    rs = sub.add_parser("results", help="load the latest public scan of each Oracle candidate as an incident")
    rs.add_argument("--limit", type=int, default=50)
    rs.add_argument("--min-score", type=float, default=0.5)
    d = sub.add_parser("domain")
    d.add_argument("domain")
    p = sub.add_parser("pivots")
    p.add_argument("--budget", type=int, default=40, help="max searches this run (free plan: 1,000/day)")
    p.add_argument("--min-df", type=int, default=2)
    q = sub.add_parser("query")
    q.add_argument("q")
    sub.add_parser("domains", help="enrich every landing domain in the DB")
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    if not os.environ.get("URLSCAN_API_KEY"):
        print("note: URLSCAN_API_KEY not set — anonymous search (30/min, last 30 days only)", file=sys.stderr)
    with connect(args.db) as conn:
        loader = Loader(conn, artifacts.from_env(), sensitivity="internal")
        if args.cmd == "results":
            run_id = loader.start_run("urlscan", trigger="manual", params={"cmd": "results", "limit": args.limit})
            stats = load_results(loader, args.limit, args.min_score)
            conn.execute("SELECT refresh_observable_stats()")
            loader.finish_run(run_id, "ok", {**loader.stats, **stats})
            conn.commit()
            print(stats)
        elif args.cmd == "domain":
            print(json.dumps(enrich_domain(loader, args.domain.lower()), indent=1, default=str))
        elif args.cmd == "query":
            data = search(conn, args.q)
            for r in data.get("results", [])[:50]:
                s = _summ(r)
                print(s["time"], s["domain"], s["ip"], (s["title"] or "")[:60])
            print({k: data.get(k) for k in ("total", "took", "has_more", "error", "cached")})
        elif args.cmd == "domains":
            run_id = loader.start_run("urlscan", trigger="manual", params={"cmd": "domains"})
            doms = [r[0] for r in conn.execute(
                """SELECT DISTINCT o.value FROM observables o JOIN incident_observables io ON io.observable_id = o.id
                   WHERE o.type = 'etld1' AND io.field LIKE 'landing.%%' AND NOT o.noise ORDER BY 1""")]
            for dom in doms:
                r = enrich_domain(loader, dom)
                print(f"  {dom:<30} scans={r['scans']:<4} total={r['total']} first={str(r['first'])[:10]} "
                      f"last={str(r['last'])[:10]} ips={r['ips'][:3]} err={r['error']}")
            loader.finish_run(run_id, "ok", {"domains": len(doms)})
            conn.commit()
        else:
            run_id = loader.start_run("urlscan", trigger="manual", params={"cmd": "pivots", "budget": args.budget})
            stats = run_pivots(loader, args.budget, args.min_df)
            loader.finish_run(run_id, "ok", stats)
            conn.commit()
            print(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
