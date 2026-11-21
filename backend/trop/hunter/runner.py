"""Hunter sources: run_meta / run_certpl / run_urlscan / run_google -> HunterRun (+ IncidentDrafts through `sink`).

Every run writes data/hunter/<run_id>/{draft_*.json, run.json}; drafts are also published to the store/engine when wired.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from trop.capture._util import etld1_of, host_of
from trop.config import settings
from trop.enrich import cache, certpl, urlscan
from trop.schema import AdLayer, Content, DomainInfo, HunterRun, Incident, IncidentDraft, IncidentSource, Infra, Landing

from . import gazetteer, meta, sink

Progress = Callable[[str], None]
FB_LURE_MIN = 0.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def apply_bundle(draft: IncidentDraft, bundle: str | Path) -> IncidentDraft:
    """Fill landing / tracking / infra / quality of a draft from a capture bundle (organizer layout)."""
    from trop.capture.bundle import bundle_sections
    s = bundle_sections(bundle)
    draft.landing = Landing(**s["landing"])
    for k, v in s["tracking"].items():
        setattr(draft.tracking, k, v)
    draft.infra = Infra(domains=[DomainInfo(**d) for d in s["infra"]["domains"]], ips=s["infra"]["ips"])
    draft.source.path = str(bundle)
    draft.quality.available = sorted(set(draft.quality.available) | set(s["quality"]["available"]))
    draft.quality.missing = [m for m in draft.quality.missing if m != "landing_url"]
    draft.quality.errors += s["quality"]["errors"]
    if s["challenge"]:
        draft.quality.errors.append("landing: challenge page (blocked, not solved)")
    return draft


def _select(ads: list[dict], n: int) -> list[dict]:
    """Prioritise lure/person ads, one per (page_id, body-template) so a farm of identical ads costs one snapshot."""
    seen, out = set(), []
    for a in sorted(ads, key=lambda a: -gazetteer.lure_score(" ".join(a.get("ad_creative_bodies") or []) + " " + " ".join(a.get("ad_creative_link_titles") or []))):
        body = ((a.get("ad_creative_bodies") or [""])[0] or "")[:60]
        k = (a.get("page_id"), body)
        if k in seen:
            continue
        seen.add(k)
        out.append(a)
        if len(out) >= n:
            break
    return out


def run_meta(terms: list[str] | None = None, *, max_queries: int = 6, per_query: int = 25, snapshot_limit: int = 6,
             capture_limit: int = 2, capture: bool = True, docker: bool = True, countries: list[str] | None = None,
             page_ids: list[str] | None = None, progress: Progress = print) -> HunterRun:
    """Meta Ad Library -> drafts -> snapshot render (CTA link) -> sandboxed landing capture -> enriched drafts."""
    run = HunterRun(id=sink.new_run_id("meta"), source_id="meta_adlibrary", started_at=_now())
    sink.write_run(run)
    errors: list[str] = []
    ads: dict[str, dict] = {}
    queries = list(terms) if terms else list(meta.iter_queries())[:max_queries]
    for q in queries:
        try:
            got = meta.search(q, countries or ["PL"], limit=per_query, max_pages=1)
        except meta.MetaError as e:
            errors.append(f"{q!r}: {e}")
            progress(f"  meta query {q!r} failed: {e}")
            if "token" in str(e).lower():
                break
            continue
        progress(f"  meta {q!r}: {len(got)} ads")
        for a in got:
            ads.setdefault(a["id"], a)
    if page_ids:
        try:
            for a in meta.search(None, countries or ["PL"], limit=per_query, max_pages=1, page_ids=page_ids):
                ads.setdefault(a["id"], a)
        except meta.MetaError as e:
            errors.append(f"page_ids: {e}")
    run.found = len(ads)
    drafts: dict[str, IncidentDraft] = {a: meta.to_draft(ad, run.id) for a, ad in ads.items()}
    picks = _select(list(ads.values()), snapshot_limit)
    # snapshot -> CTA link + creative
    from .snapshot import render_snapshots
    shots = sink.hunter_dir() / run.id / "creatives"
    snaps = render_snapshots([p["id"] for p in picks], shots)
    progress(f"  snapshots rendered: {len(snaps)} / {len(picks)}; with CTA link: {sum(1 for s in snaps.values() if s.get('links'))}")
    for aid, rec in snaps.items():
        d = drafts[aid]
        if rec.get("screenshot"):
            d.ad.screenshot_path = rec["screenshot"]
            d.ad.screenshots = [rec["screenshot"]]
        if rec.get("links"):
            d.landing.entry_url = rec["links"][0]
            d.landing.host = host_of(rec["links"][0])
            d.landing.etld1 = etld1_of(rec["links"][0])
            d.quality.missing = [m for m in d.quality.missing if m != "landing_url"]
        if rec.get("error"):
            d.quality.errors.append("snapshot: " + rec["error"])
    # landing capture (budgeted, sandboxed, victim profile)
    captured = 0
    if capture:
        from trop.capture.cli import capture_url
        todo = [aid for aid, r in snaps.items() if r.get("links")]
        done_sites: set[str] = set()
        for aid in todo:
            if captured >= capture_limit:
                break
            url = snaps[aid]["links"][0]
            site = etld1_of(url)
            if site in done_sites:
                continue
            done_sites.add(site)
            progress(f"  capture {site} (ad {aid}) ...")
            r = capture_url(url, "fb_inapp_android_pl", docker=docker, fast=True)
            if r.get("ok"):
                apply_bundle(drafts[aid], r["bundle"])
                captured += 1
                progress(f"    ok: status={r['bundles'][0]['status']} title={str(r['bundles'][0]['title'])[:50]!r}")
            else:
                errors.append(f"capture {site}: {r.get('error')}")
                progress(f"    skipped: {r.get('error')}")
    run.captured = captured
    ids: list[str] = []
    for aid, d in drafts.items():
        sink.write_draft(run.id, d)
        iid = sink.publish(d)
        if iid:
            ids.append(iid)
    run.incident_ids = ids
    run.attributed = 0
    run.error = "; ".join(errors)[:500] or None
    run.status = "error" if (errors and not ads) else "ok"
    run.finished_at = _now()
    sink.write_run(run, {"queries": queries, "snapshots": len(snaps), "with_link": sum(1 for s in snaps.values() if s.get("links")),
                         "drafts": len(drafts), "published": len(ids)})
    return run


# ------------------------------------------------------------------------------------------------ CERT PL
def run_certpl(max_drafts: int = 100, progress: Progress = print) -> HunterRun:
    run = HunterRun(id=sink.new_run_id("certpl"), source_id="certpl", started_at=_now())
    st = certpl.sync()
    progress(f"  certpl sync: {st}")
    diff = certpl.last_diff() if not st.get("not_modified") else {"added": []}
    added = [] if diff.get("first_sync") else diff.get("added", [])
    run.found = len(added)
    for dom in added[:max_drafts]:
        d = IncidentDraft(source=IncidentSource(type="hunter", ref=f"certpl:{dom}", captured_at=_now()),
                          landing=Landing(host=host_of(dom), etld1=etld1_of(dom), entry_url=f"http://{dom}/"),
                          infra=Infra(domains=[DomainInfo(fqdn=host_of(dom), etld1=etld1_of(dom))], on_certpl_list=True))
        d.source.hunter_run = run.id
        d.source.via = "certpl"
        sink.write_draft(run.id, d)
        iid = sink.publish(d)
        if iid:
            run.incident_ids.append(iid)
    run.error = st.get("error")
    run.status = "error" if st.get("error") else "ok"
    run.finished_at = _now()
    sink.write_run(run, {"sync": st, "first_sync": diff.get("first_sync", st.get("first_sync"))})
    return run


# ------------------------------------------------------------------------------------------------ urlscan pivots
def known_incidents() -> list[dict]:
    """Incidents with tracking/infra for pivoting: the store when importable, else data/experiments/*/incidents.json."""
    out: list[dict] = []
    for p in sorted((Path(settings.data_dir) / "experiments").glob("*/incidents.json")):
        try:
            out += json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return out


def pivot_values(incs: list[dict], min_df: int = 2, limit: int = 40) -> list[tuple[str, str, list[str]]]:
    """-> [(kind, value, seen_on_etld1s)] campaign values shared by >= min_df incidents (capi gateways first, then assets)."""
    seen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for i in incs:
        et = (i.get("landing") or {}).get("etld1") or ""
        t = i.get("tracking") or {}
        for v in t.get("capi_gateways", []):
            seen[("capi_gateway", v)].add(et)
        for v in t.get("asset_hashes", []):
            seen[("asset_sha256", v)].add(et)
        for v in (i.get("infra") or {}).get("origin_ips", []):
            seen[("ip", v)].add(et)
    order = {"capi_gateway": 0, "asset_sha256": 1, "ip": 2}
    rows = [(k, v, sorted(s)) for (k, v), s in seen.items() if len(s) >= min_df]
    rows.sort(key=lambda r: (order[r[0]], -len(r[2])))
    return rows[:limit]


QUERY = {"asset_sha256": lambda v: f"hash:{v}", "capi_gateway": lambda v: f"domain:{v}", "ip": lambda v: f'page.ip:"{v}"'}
SCORE = {"asset_sha256": 0.9, "capi_gateway": 0.9, "ip": 0.6}


def run_urlscan(budget: int = 40, min_df: int = 2, progress: Progress = print) -> HunterRun:
    """Search-only urlscan pivots from campaign assets -> new candidate domains -> drafts + data/oracle/candidates_urlscan.json."""
    run = HunterRun(id=sink.new_run_id("urlscan"), source_id="urlscan", started_at=_now())
    incs = known_incidents()
    known = {(i.get("landing") or {}).get("etld1") for i in incs}
    found: dict[str, dict] = {}
    errors = 0
    for kind, value, seen_on in pivot_values(incs, min_df, budget):
        data = urlscan.search(QUERY[kind](value))
        if data.get("error"):
            errors += 1
            progress(f"  urlscan error: {data['error']}")
            if "429" in str(data["error"]) or "rate" in str(data["error"]).lower():
                break
            continue
        scans = data["results"]
        verdict, _ = urlscan.classify_pivot(scans)
        if verdict == "shared_service":
            continue
        for s in scans:
            d = s.get("apex") or etld1_of(s.get("domain") or "")
            if not d or d in known or s.get("umbrella_rank"):
                continue
            f = found.setdefault(d, {"fqdn": s["domain"], "etld1": d, "first": s["time"], "pivots": [], "ips": set(), "titles": set(),
                                     "uuids": [], "tls_issuer": s.get("tls_issuer"), "tls_valid_from": s.get("tls_valid_from")})
            f["pivots"].append({"type": kind, "value": value[:80], "seen_on": seen_on})
            f["ips"].add(s.get("ip"))
            if s.get("title"):
                f["titles"].add(s["title"][:100])
            f["uuids"].append(s["uuid"])
    run.found = len(found)
    cands = []
    for d, f in found.items():
        types = {p["type"] for p in f["pivots"]}
        score = min(0.99, max(SCORE[t] for t in types) + 0.05 * (len({(p["type"], p["value"]) for p in f["pivots"]}) - 1))
        listed = certpl.check(d).get("listed")
        cands.append({"domain": d, "fqdn": f["fqdn"], "first_seen": f["first"], "score": score, "tls_issuer": f["tls_issuer"],
                      "tls_valid_from": f["tls_valid_from"], "ips": sorted(x for x in f["ips"] if x), "titles": sorted(f["titles"])[:3],
                      "urlscan_uuids": f["uuids"][:5], "pivots": f["pivots"][:5], "on_certpl": listed})
        draft = IncidentDraft(source=IncidentSource(type="hunter", ref=f"urlscan:{d}", captured_at=_now()),
                              landing=Landing(host=f["fqdn"], etld1=d, entry_url=f"https://{f['fqdn']}/", title=(sorted(f["titles"]) or [None])[0]),
                              infra=Infra(domains=[DomainInfo(fqdn=f["fqdn"], etld1=d)], ips=sorted(x for x in f["ips"] if x),
                                          on_certpl_list=listed))
        draft.source.via, draft.source.hunter_run, draft.source.pivots = "urlscan", run.id, f["pivots"][:5]
        if len(cands) <= 50:
            sink.write_draft(run.id, draft)
            iid = sink.publish(draft)
            if iid:
                run.incident_ids.append(iid)
    out = Path(settings.data_dir) / "oracle"
    out.mkdir(parents=True, exist_ok=True)
    (out / "candidates_urlscan.json").write_text(json.dumps(cands, ensure_ascii=False, indent=1))
    run.status = "error" if errors and not found else "ok"
    run.error = f"{errors} urlscan error(s)" if errors else None
    run.finished_at = _now()
    sink.write_run(run, {"candidates": len(cands), "budget": budget})
    progress(f"  urlscan: {len(cands)} candidate domains not yet in the corpus")
    return run


# ------------------------------------------------------------------------------------------------ Google ATC
def run_google(days: int = 2, progress: Progress = print) -> HunterRun:
    from . import google_atc
    run = HunterRun(id=sink.new_run_id("google"), source_id="google_ads_transparency", started_at=_now())
    if google_atc.credentials_status() != "set":
        run.status, run.error = "error", "Google ADC missing: source disabled"
    else:
        names = sorted({(i.get("ad") or {}).get("advertiser") or "" for i in known_incidents()} - {""})
        r = google_atc.advertiser_lookup(names)
        run.found = len(r.get("rows", []))
        run.error = r.get("error")
        run.status = "error" if run.error else "ok"
        progress(f"  google ATC: {run.found} advertiser rows; scan={r.get('scan_bytes')} error={run.error}")
        (sink.hunter_dir() / run.id).mkdir(parents=True, exist_ok=True)
        (sink.hunter_dir() / run.id / "advertisers.json").write_text(json.dumps(r, ensure_ascii=False, indent=1, default=str))
    run.finished_at = _now()
    sink.write_run(run)
    return run


RUNNERS = {"meta": run_meta, "certpl": run_certpl, "urlscan": run_urlscan, "google": run_google}
