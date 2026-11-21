"""White Rabbit tools: JSON-schema specs for the LLM + executors that grow the case graph.

Each executor gets (args, ctx) and returns a ToolResult: a compact `view` the LLM reads next turn, a Polish
one-line `summary` for the case file, and the node ids it produced. External lookups go through `ctx.ext`
(default: WS5's `trop.enrich.tools`, cached and offline-safe), DB lookups through `trop.agent.db` — both injectable.

Safety: nothing here contacts a scam host except `capture`, which is budgeted per investigation, runs only in the
Docker sandbox (no local fallback), never submits forms, and goes through WS5's per-domain politeness budget.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from . import db as _db
from .case import Case, dom_id

log = logging.getLogger("trop.agent.tools")

# hosts that show up in pivots but are never campaign infrastructure
IGNORE = {
    "facebook.com", "fb.com", "instagram.com", "google.com", "googleapis.com", "gstatic.com", "googletagmanager.com",
    "cloudflare.com", "cloudflareinsights.com", "jsdelivr.net", "cdnjs.com", "unpkg.com", "youtube.com", "tiktok.com",
    "apple.com", "microsoft.com", "amazonaws.com", "on.aws", "doubleclick.net", "urlscan.io", "archive.org", "w3.org",
    "wordpress.com", "github.io", "vercel.app", "netlify.app", "pages.dev", "workers.dev", "web.app", "firebaseapp.com",
}
MAX_DOMAIN_NODES = 90
WHY = {"type": "string", "description": "One short sentence in Polish: why this call (shown in the case file)."}


@dataclass
class ToolResult:
    view: dict
    summary: str
    produced: list[str] = field(default_factory=list)
    stop: bool = False


@dataclass
class Ctx:
    case: Case
    seed: str
    campaign_id: str | None = None
    campaign_domains: set[str] = field(default_factory=set)
    ext: Any = None                          # module/object with crtsh, rdap, dns_ns, urlscan_search, certpl_check, ...
    dbm: Any = _db
    captures_left: int = 1
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    _known: dict[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.ext is None:
            from trop.enrich import tools as ext
            self.ext = ext

    def known(self, domains: list[str]) -> set[str]:
        miss = [d for d in domains if d not in self._known]
        if miss:
            try:
                k = self.dbm.known_domains(miss)
            except Exception:  # noqa: BLE001
                k = set()
            for d in miss:
                self._known[d] = d in k
        return {d for d in domains if self._known.get(d)}


# ============================================================================== helpers
def _apex(x: str) -> str:
    x = (x or "").strip().lower().rstrip(".")
    x = re.sub(r"^[a-z]+://", "", x).split("/")[0].split(":")[0]
    return _db.etld1(x) if x else ""


def _ignored(d: str) -> bool:
    return not d or d in IGNORE or any(d.endswith("." + i) for i in IGNORE) or not _db.is_domain(d)


def add_domains(ctx: Ctx, domains: list[str], *, branch: str, parent: str | None, edge_label: str | None,
                evidence: dict, meta: dict[str, dict] | None = None) -> list[str]:
    """Add/merge domain nodes with one piece of evidence each. Returns ids of nodes touched."""
    seed = _apex(ctx.seed)
    out: list[str] = []
    ds = [d for d in dict.fromkeys(_apex(x) for x in domains) if not _ignored(d) and d != seed]
    known = ctx.known(ds)
    for d in ds:
        nid = dom_id(d)
        exists = nid in ctx.case.nodes
        if not exists and len(ctx.case.domains()) >= MAX_DOMAIN_NODES:
            continue
        in_c = d in ctx.campaign_domains
        m = {"known_in_db": d in known, **((meta or {}).get(d) or {})}
        camps = None
        if not exists:
            try:
                camps = ctx.dbm.campaigns_for_domain(d) if d in known else []
            except Exception:  # noqa: BLE001
                camps = []
            m["campaigns"] = camps
        ctx.case.node(nid, "domain", d, branch=branch, parent=parent, edge_label=edge_label, meta=m,
                      status=("in_campaign" if in_c else "new") if not exists else None,
                      is_new=(not in_c and d not in known) if not exists else None)
        ctx.case.add_evidence(nid, evidence)
        out.append(nid)
    return out


def _ensure_seed(ctx: Ctx) -> str:
    d = _apex(ctx.seed)
    nid = dom_id(d)
    if nid not in ctx.case.nodes:
        in_c = d in ctx.campaign_domains
        ctx.case.node(nid, "domain", d, branch="db", status="in_campaign" if in_c else "in_progress",
                      meta={"seed": True, "known_in_db": bool(ctx.known([d]))}, is_new=None)
    return nid


def _target_node(ctx: Ctx, domain: str) -> str:
    d = _apex(domain)
    nid = dom_id(d)
    if nid in ctx.case.nodes:
        return nid
    return _ensure_seed(ctx) if d == _apex(ctx.seed) else add_domains(
        ctx, [d], branch="db", parent=_ensure_seed(ctx), edge_label="analityk",
        evidence={"type": "analyst", "value": "wskazana do sprawdzenia", "level": "platform"})[0]


def _h(x: str) -> str:
    return hashlib.sha1(str(x).encode()).hexdigest()[:8]


def _short(xs: list, n: int) -> list:
    return list(xs)[:n]


# ============================================================================== executors
def t_db_search(a: dict, ctx: Ctx) -> ToolResult:
    q = str(a.get("query") or ctx.seed)
    r = ctx.dbm.db_search(q)
    if r.get("error"):
        return ToolResult({"error": r["error"]}, f"Baza: błąd ({r['error'][:60]}).")
    produced: list[str] = []
    if r.get("kind") == "domain":
        root = _target_node(ctx, r["domain"])
        ctx.case.node(root, "domain", r["domain"], meta={"known_in_db": r.get("known"), "incidents": [i["id"] for i in r.get("incidents", [])][:10],
                                                        "campaigns": r.get("campaigns") or []})
        view_traces = []
        n_new = 0
        for t in r.get("traces", []):
            doms = t.get("domains") or []
            view_traces.append({k: t.get(k) for k in ("type", "value", "level", "df", "n_domains")} | {"domains": doms[:12]})
            if not doms or t["level"] in ("infra",) or (t["level"] == "platform" and len(doms) > 15):
                continue
            tid = f"n-db-{t['type']}-{_h(t['value'])}"
            label = f"{t['type']}: {t['value'][:24]}{'…' if len(t['value']) > 24 else ''} → {len(doms)} domen"
            ctx.case.node(tid, "query_result", label, branch="db", parent=root, edge_label=t["type"],
                          meta={"type": t["type"], "value": t["value"], "level": t["level"], "df": t.get("df"), "domains": len(doms)})
            produced.append(tid)
            before = len(ctx.case.domains())
            produced += add_domains(ctx, doms, branch="db", parent=tid, edge_label=t["type"],
                                    evidence={"type": t["type"], "value": t["value"], "level": t["level"], "source": "db"})
            n_new += len(ctx.case.domains()) - before
        view = {"domain": r["domain"], "known": r.get("known"), "campaigns": r.get("campaigns"),
                "incidents": _short(r.get("incidents", []), 6), "traces": view_traces}
        s = (f"{r['domain']}: {len(r.get('incidents', []))} incydentów w bazie, {len(view_traces)} śladów; "
             f"{n_new} powiązanych domen.") if r.get("known") else f"{r['domain']}: brak w naszej bazie."
        return ToolResult(view, s, produced)
    matches = r.get("matches", [])
    for m in matches:
        doms = m.get("domains") or []
        if not doms:
            continue
        tid = f"n-db-{m['type']}-{_h(m['value'])}"
        ctx.case.node(tid, "query_result", f"{m['type']}: {m['value'][:24]} → {len(doms)} domen", branch="db",
                      parent=_ensure_seed(ctx), edge_label=m["type"], meta={"type": m["type"], "value": m["value"], "level": m.get("level")})
        produced.append(tid)
        if m.get("level") != "platform" or len(doms) <= 15:
            produced += add_domains(ctx, doms, branch="db", parent=tid, edge_label=m["type"],
                                    evidence={"type": m["type"], "value": m["value"], "level": m.get("level", "campaign"), "source": "db"})
    view = {"query": q, "matches": [{k: m.get(k) for k in ("type", "value", "level", "df", "n_domains")} | {"domains": (m.get("domains") or [])[:12]}
                                    for m in matches]}
    return ToolResult(view, f"Ślad „{q[:30]}”: {len(matches)} dopasowań w bazie.", produced)


def t_neighborhood(a: dict, ctx: Ctx) -> ToolResult:
    r = ctx.dbm.incident_neighborhood(a.get("incident_id"), int(a.get("depth") or 1))
    if r.get("error"):
        return ToolResult({"error": r["error"]}, f"Sąsiedztwo: {r['error'][:60]}.")
    produced: list[str] = []
    root = _ensure_seed(ctx)
    for g in r.get("groups", []):
        if g["level"] in ("operator", "campaign") and g["domains"]:
            produced += add_domains(ctx, g["domains"][:30], branch="db", parent=root, edge_label=g["via_type"],
                                    evidence={"type": g["via_type"], "value": g["via_value"], "level": g["level"], "source": "db"})
    view = {"incident_id": r["incident_id"], "neighbours": r["neighbours"],
            "groups": [{"via_type": g["via_type"], "via_value": g["via_value"][:60], "level": g["level"],
                        "n_domains": len(g["domains"]), "domains": g["domains"][:10]} for g in r.get("groups", [])[:10]]}
    return ToolResult(view, f"Sąsiedztwo {r['incident_id']}: {r['neighbours']} incydentów przez {len(r.get('groups', []))} śladów.", produced)


def _tonight(ctx: Ctx, ts: str | None) -> bool:
    if not ts:
        return False
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        t = t if t.tzinfo else t.replace(tzinfo=timezone.utc)
        return ctx.now() - t <= timedelta(hours=24)
    except ValueError:
        return False


def t_crtsh(a: dict, ctx: Ctx) -> ToolResult:
    d = _apex(a.get("domain") or ctx.seed)
    r = ctx.ext.crtsh(d)
    certs = r.get("certs") or []
    root = _target_node(ctx, d)
    if not certs:
        return ToolResult({"domain": d, "count": 0, "error": r.get("error")}, f"crt.sh: brak certyfikatów dla {d}.")
    sans = sorted({_apex(n.lstrip("*.")) for c in certs for n in c.get("names", [])} - {d, ""})
    first = certs[0].get("not_before")
    tonight = [c for c in certs if _tonight(ctx, c.get("not_before"))]
    ctx.case.node(root, "domain", d, meta={"first_cert": first, "cert_issuers": r.get("issuers", [])[:3],
                                           "certs_tonight": len(tonight)})
    cid = f"n-cert-{d}"
    ctx.case.node(cid, "cert", f"crt.sh: {len(certs)} certyfikatów · pierwszy {str(first)[:16]}", branch="crtsh", parent=root,
                  edge_label="crt.sh", meta={"count": len(certs), "first": first, "issuers": r.get("issuers", [])[:3], "san": len(sans)})
    produced = [cid] + add_domains(ctx, sans, branch="crtsh", parent=cid, edge_label="SAN",
                                   evidence={"type": "cert_san", "value": f"wspólny certyfikat z {d}", "level": "campaign", "source": "crtsh"})
    view = {"domain": d, "count": len(certs), "first_not_before": first, "issuers": r.get("issuers", [])[:4],
            "san_domains": sans[:20], "certs_last_24h": len(tonight),
            "recent": [{"not_before": c.get("not_before"), "issuer": c.get("issuer"), "names": c.get("names", [])[:4]} for c in certs[-5:]]}
    return ToolResult(view, f"crt.sh: {len(certs)} certyfikatów dla {d}, pierwszy {str(first)[:10]}; {len(sans)} domen w SAN.", produced)


def t_rdap(a: dict, ctx: Ctx) -> ToolResult:
    d = _apex(a.get("domain") or ctx.seed)
    r = ctx.ext.rdap(d)
    nid = _target_node(ctx, d)
    ok = r.get("status") == "ok" or any(r.get(k) for k in ("registrar", "created", "ns"))  # RDAP's own `status` list may shadow "ok"
    if not ok:
        return ToolResult({"domain": d, "status": r.get("status"), "error": r.get("error")}, f"RDAP {d}: {r.get('status')}.", [nid])
    ctx.case.node(nid, "domain", d, meta={"registrar": r.get("registrar"), "created": r.get("created"), "ns": r.get("ns")})
    view = {k: r.get(k) for k in ("domain", "registrar", "created", "expires", "ns")}
    return ToolResult(view, f"RDAP {d}: rejestrator {r.get('registrar') or 'ukryty'}, utworzona {str(r.get('created'))[:16]}.", [nid])


def t_dns(a: dict, ctx: Ctx) -> ToolResult:
    d = _apex(a.get("domain") or ctx.seed)
    r = ctx.ext.dns_ns(d)
    nid = _target_node(ctx, d)
    produced = [nid]
    asns = r.get("asn") or {}
    for ip in (r.get("a") or [])[:3]:
        info = asns.get(ip) or {}
        asn = info.get("asn") or info.get("as") or ""
        org = (info.get("org") or info.get("name") or info.get("as_name") or "")[:30]
        cdn = "cloudflare" in org.lower() or str(asn) in ("13335", "AS13335")
        iid = f"n-ip-{ip}"
        ctx.case.node(iid, "ip", f"{ip} · AS{str(asn).replace('AS', '')} {org}".strip(), branch="crtsh", parent=nid,
                      edge_label="DNS", meta={"asn": asn, "org": org, "cdn": cdn, "weight_zero": cdn})
        produced.append(iid)
    ctx.case.node(nid, "domain", d, meta={"ns": r.get("ns"), "nxdomain": r.get("nxdomain")})
    view = {"domain": d, "ns": r.get("ns"), "a": r.get("a"), "asn": asns, "nxdomain": r.get("nxdomain"),
            "note": "Cloudflare IPs are shared by millions of sites: weight 0; the NS pair is account-specific."}
    return ToolResult(view, f"DNS {d}: NS {', '.join((r.get('ns') or [])[:2]) or 'brak'}; A {', '.join((r.get('a') or [])[:2]) or 'brak'}.", produced)


def t_urlscan(a: dict, ctx: Ctx) -> ToolResult:
    q = str(a.get("query") or f"domain:{_apex(ctx.seed)}")
    r = ctx.ext.urlscan_search(q, size=int(a.get("size") or 100))
    if r.get("error") and not r.get("results"):
        return ToolResult({"query": q, "error": r["error"]}, f"urlscan „{q[:40]}”: błąd ({str(r['error'])[:50]}).")
    res = r.get("results") or []
    by_apex: dict[str, dict] = {}
    for s in res:
        d = _apex(s.get("apex") or s.get("domain") or "")
        if d and not _ignored(d) and not (s.get("umbrella_rank") and int(s["umbrella_rank"] or 0) < 200000):
            by_apex.setdefault(d, s)
    # evidence level of the pivot: hash of a kit-wide SDK bundle = platform; rare asset = campaign
    level, ptype, pval = "campaign", "urlscan", q
    m = re.match(r"^\s*hash:([0-9a-f]{64})\s*$", q)
    if m:
        ptype, pval = "asset_sha256", m.group(1)
        o = ctx.dbm.observable_df(pval)
        if o:
            level = _db.level_of("asset_sha256", o.get("df") or 0, o.get("noise_reason"))
    elif q.startswith(("domain:", "page.domain:")):
        level = "infra"
    try:
        from trop.enrich.urlscan import classify_pivot
        verdict, vstats = classify_pivot(list(by_apex.values()))
    except Exception:  # noqa: BLE001
        verdict, vstats = "campaign", {}
    if verdict == "shared_service":
        level = "platform"
    qid = f"n-us-{_h(q)}"
    ctx.case.node(qid, "query_result", f"urlscan: {q[:40]} → {len(by_apex)} domen", branch="urlscan", parent=_ensure_seed(ctx),
                  edge_label="urlscan", meta={"query": q, "total": r.get("total"), "domains": len(by_apex), "level": level,
                                              "verdict": verdict, **vstats})
    meta = {d: {"title": (s.get("title") or "")[:80], "first_seen": s.get("time"), "ip": s.get("ip"), "asn": s.get("asn"),
                "tls_issuer": s.get("tls_issuer"), "tls_valid_from": s.get("tls_valid_from")} for d, s in by_apex.items()}
    seed = _apex(ctx.seed)
    produced = [qid] + add_domains(ctx, [d for d in by_apex if d != seed], branch="urlscan", parent=qid, edge_label=ptype,
                                   evidence={"type": ptype, "value": pval[:80], "level": level, "source": "urlscan"}, meta=meta)
    view = {"query": q, "total": r.get("total"), "distinct_domains": len(by_apex), "pivot_level": level, "verdict": verdict,
            "domains": [{"domain": d, "title": (s.get("title") or "")[:60], "time": str(s.get("time"))[:10], "ip": s.get("ip"),
                         "asn": s.get("asn"), "known": ctx._known.get(d, False)} for d, s in list(by_apex.items())[:30]]}
    return ToolResult(view, f"urlscan „{q[:48]}”: {len(by_apex)} domen ({level}).", produced)


def t_certpl(a: dict, ctx: Ctx) -> ToolResult:
    doms = a.get("domains") or []
    if isinstance(doms, str):
        doms = [doms]
    if not doms or doms == ["all"] or a.get("all_candidates"):
        doms = [n.label for n in ctx.case.domains()]
    doms = [d for d in dict.fromkeys(_apex(x) for x in doms) if d][:120]
    listed, not_listed, unknown = [], [], []
    for d in doms:
        r = ctx.ext.certpl_check(d)
        st = r.get("listed")
        (listed if st else not_listed if st is False else unknown).append(d)
        nid = dom_id(d)
        if nid in ctx.case.nodes:
            ctx.case.node(nid, "domain", d, meta={"certpl": st, "on_certpl": bool(st)})
    lid = "n-certpl"
    ctx.case.node(lid, "list_status", f"CERT PL: {len(not_listed)} z {len(doms)} poza listą", branch="certpl",
                  parent=_ensure_seed(ctx), edge_label="lista CERT PL",
                  meta={"not_listed": len(not_listed), "listed": len(listed), "unknown": len(unknown), "total": len(doms)})
    view = {"checked": len(doms), "listed": listed[:30], "not_listed_count": len(not_listed), "not_listed": not_listed[:30],
            "unknown": unknown[:10]}
    return ToolResult(view, f"CERT PL: {len(not_listed)} z {len(doms)} domen nie ma na liście ostrzeżeń.", [lid])


def t_wayback(a: dict, ctx: Ctx) -> ToolResult:
    u = str(a.get("url") or ctx.seed)
    r = ctx.ext.wayback(u, limit=10)
    view = {k: r.get(k) for k in ("query", "count", "first", "urls", "error")}
    return ToolResult(view, f"Wayback {u[:40]}: {r.get('count', 0)} kopii, pierwsza {str(r.get('first') or '-')[:8]}.")


def t_adlib(a: dict, ctx: Ctx) -> ToolResult:
    terms = str(a.get("terms") or "")
    r = ctx.ext.adlib_search(terms, countries=str(a.get("countries") or "PL"), limit=int(a.get("limit") or 25),
                             active=str(a.get("active") or "ALL"), page_ids=a.get("page_ids"))
    ads = r.get("ads") or []
    pages = sorted({x.get("page_name") or x.get("page_id") or "?" for x in ads})
    if r.get("error") and not ads:
        return ToolResult({"terms": terms, "error": r["error"]}, f"Ad Library „{terms[:30]}”: błąd ({str(r['error'])[:50]}).")
    aid = f"n-ads-{_h(terms + str(a.get('page_ids')))}"
    ctx.case.node(aid, "ad", f"Ad Library: {len(ads)} reklam, {len(pages)} stron", branch="adlib", parent=_ensure_seed(ctx),
                  edge_label="reklamy", meta={"terms": terms, "ads": len(ads), "pages": len(pages), "advertisers": pages[:20],
                                              "library_ids": [x.get("id") for x in ads][:50]})
    produced = [aid]
    caps = {}
    for x in ads:
        c = _apex(x.get("caption") or "")
        if c and c in {n.label for n in ctx.case.domains()}:
            caps.setdefault(c, []).append(x.get("id"))
    for d, ids in caps.items():
        ctx.case.edge(aid, dom_id(d), "reklama → domena")
        ctx.case.node(dom_id(d), "domain", d, meta={"ads": len(ids), "library_ids": ids[:20]})
    view = {"terms": terms, "count": len(ads), "pages": pages[:15],
            "ads": [{k: x.get(k) for k in ("id", "page_name", "page_id", "caption", "start")} | {"body": (x.get("body") or "")[:120]}
                    for x in ads[:10]], "domains_with_ads": {d: len(i) for d, i in caps.items()}}
    return ToolResult(view, f"Ad Library „{terms[:30]}”: {len(ads)} reklam na {len(pages)} stronach.", produced)


def t_capture(a: dict, ctx: Ctx) -> ToolResult:
    url = str(a.get("url") or "")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    if ctx.captures_left <= 0:
        return ToolResult({"url": url, "error": "capture budget for this investigation is used up"}, "Przechwycenie: budżet wyczerpany.")
    try:
        from trop.capture import cli as cap
        if not (cap.docker_available() and cap.ensure_image()):
            return ToolResult({"url": url, "error": "sandbox (docker) unavailable; capture refused"}, "Przechwycenie: brak sandboksa.")
    except Exception as e:  # noqa: BLE001
        return ToolResult({"url": url, "error": str(e)[:120]}, "Przechwycenie: niedostępne.")
    ctx.captures_left -= 1
    r = ctx.ext.capture(url, docker=True)
    b = (r.get("bundles") or [{}])[0]
    nid = _target_node(ctx, url)
    ctx.case.node(nid, "domain", _apex(url), meta={"captured": r.get("ok"), "capture_title": b.get("title"),
                                                    "capture_status": b.get("status"), "bundle": r.get("bundle")})
    view = {"url": url, "ok": r.get("ok"), "error": r.get("error"), "final_url": b.get("final_url"), "status": b.get("status"),
            "title": b.get("title"), "page_role_hint": b.get("page_role_hint"), "challenge": b.get("challenge")}
    return ToolResult(view, f"Przechwycenie {_apex(url)}: {'ok' if r.get('ok') else 'nieudane'} · {str(b.get('title') or r.get('error') or '')[:50]}.", [nid])


def t_propose(a: dict, ctx: Ctx) -> ToolResult:
    doms = a.get("domains") or ([a["domain"]] if a.get("domain") else [])
    conf = str(a.get("confidence") or "high")
    ev = a.get("evidence") or []
    rationale = str(a.get("rationale") or "")[:300]
    done, missing = [], []
    for d in doms:
        nid = dom_id(_apex(d))
        if nid not in ctx.case.nodes:
            missing.append(d)
            continue
        n = ctx.case.nodes[nid]
        meta = {"proposed": True, "confidence": conf, "rationale": rationale, "proposed_evidence": ev[:6]}
        if conf == "low":
            ctx.case.node(nid, "domain", n.label, status="skipped", meta=meta)
        elif conf == "needs_decision":
            ctx.case.node(nid, "domain", n.label, status="to_decide", meta=meta)
            q = str(a.get("question") or f"{n.label}: {rationale or 'dowody niejednoznaczne'}. Dołączyć do tej kampanii?")
            ctx.case.decision(nid, q, ["Dołącz", "Pomiń"])
        else:
            ctx.case.node(nid, "domain", n.label, meta=meta,
                          status=None if n.status in ("in_campaign", "skipped") else "new")
        done.append(nid)
    s = {"high": "kandydat", "medium": "kandydat (średnia pewność)", "low": "pominięta",
         "needs_decision": "do decyzji analityka"}.get(conf, conf)
    return ToolResult({"accepted": [ctx.case.nodes[i].label for i in done], "unknown_domains": missing, "confidence": conf},
                      f"Sędzia: {len(done)} domen → {s}." + (f" {rationale[:120]}" if rationale else ""), done)


def t_finish(a: dict, ctx: Ctx) -> ToolResult:
    for c in a.get("conclusions") or []:
        if isinstance(c, dict):
            ctx.case.conclude(str(c.get("text") or "")[:400], [str(x) for x in (c.get("evidence_refs") or [])][:8])
        elif c:
            ctx.case.conclude(str(c)[:400])
    return ToolResult({"ok": True}, "Sędzia zamyka śledztwo.", stop=True)


# ============================================================================== specs
def _s(props: dict, req: list[str]) -> dict:
    return {"type": "object", "properties": {**props, "why": WHY}, "required": req}


SPECS: list[dict] = [
    {"name": "db_search", "description": "Look a domain or a trace value (kit tenant UUID or prefix, FB pixel, CAPI gateway, "
     "asset sha256, template) up in OUR corpus of ~1700 incidents. For a domain returns its incidents and its rare traces "
     "with every other domain sharing them, each with an evidence level (operator > campaign > platform).",
     "parameters": _s({"query": {"type": "string"}}, ["query"])},
    {"name": "incident_neighborhood", "description": "Incidents linked to one incident (INC-<n> from db_search) through shared "
     "strong/medium traces, grouped by the shared trace.",
     "parameters": _s({"incident_id": {"type": "string"}, "depth": {"type": "integer", "minimum": 1, "maximum": 2}}, ["incident_id"])},
    {"name": "crtsh", "description": "Certificate Transparency (crt.sh): certificates of a domain, first issuance, SAN co-domains.",
     "parameters": _s({"domain": {"type": "string"}}, ["domain"])},
    {"name": "rdap", "description": "RDAP registration: registrar, creation date, nameservers.",
     "parameters": _s({"domain": {"type": "string"}}, ["domain"])},
    {"name": "dns_ns", "description": "DNS from public resolvers: NS pair (Cloudflare account), A records and their ASN.",
     "parameters": _s({"domain": {"type": "string"}}, ["domain"])},
    {"name": "urlscan_search", "description": "urlscan.io SEARCH (never submits a scan). Query syntax: 'hash:<sha256 of a page "
     "resource>' finds every page loading the same file (best kit/asset pivot), 'domain:x', 'page.domain:x', 'page.ip:\"1.2.3.4\"', "
     "'page.asn:AS123', 'page.title:\"...\"'. Returns distinct domains.",
     "parameters": _s({"query": {"type": "string"}, "size": {"type": "integer", "maximum": 100}}, ["query"])},
    {"name": "certpl_check", "description": "Which domains are on the CERT Polska warning list. Pass domains, or all_candidates=true.",
     "parameters": _s({"domains": {"type": "array", "items": {"type": "string"}}, "all_candidates": {"type": "boolean"}}, [])},
    {"name": "wayback", "description": "Internet Archive snapshots of a URL or domain (first seen).",
     "parameters": _s({"url": {"type": "string"}}, ["url"])},
    {"name": "adlib_search", "description": "Meta Ad Library search (ads reaching PL): by search terms and/or advertiser page_ids.",
     "parameters": _s({"terms": {"type": "string"}, "page_ids": {"type": "string", "description": "comma-separated"},
                       "active": {"type": "string", "enum": ["ACTIVE", "ALL"]}}, ["terms"])},
    {"name": "capture", "description": "Capture ONE landing page in the isolated headless sandbox (budget: 1 per investigation; "
     "never clicks, never submits). Use only when a candidate's kit/tenant cannot be confirmed otherwise.",
     "parameters": _s({"url": {"type": "string"}}, ["url"])},
    {"name": "propose_link", "description": "Your judgement on candidate domains already in the graph: confidence high "
     "(operator/campaign-level evidence), medium, low (skip: only platform/infra noise), or needs_decision (conflicting "
     "evidence: ask the analyst, give a Polish question).",
     "parameters": _s({"domains": {"type": "array", "items": {"type": "string"}},
                       "confidence": {"type": "string", "enum": ["high", "medium", "low", "needs_decision"]},
                       "evidence": {"type": "array", "items": {"type": "string"}}, "rationale": {"type": "string"},
                       "question": {"type": "string"}}, ["domains", "confidence"])},
    {"name": "finish", "description": "End the investigation with 2-4 conclusions in Polish, each citing node ids or step numbers.",
     "parameters": _s({"conclusions": {"type": "array", "items": {"type": "object", "properties": {
         "text": {"type": "string"}, "evidence_refs": {"type": "array", "items": {"type": "string"}}}, "required": ["text"]}}},
         ["conclusions"])},
]
EXEC: dict[str, Callable[[dict, Ctx], ToolResult]] = {
    "db_search": t_db_search, "incident_neighborhood": t_neighborhood, "crtsh": t_crtsh, "rdap": t_rdap, "dns_ns": t_dns,
    "urlscan_search": t_urlscan, "certpl_check": t_certpl, "wayback": t_wayback, "adlib_search": t_adlib,
    "capture": t_capture, "propose_link": t_propose, "finish": t_finish,
}
TOOL_NAMES = [s["name"] for s in SPECS]


def specs(allow: list[str] | None = None) -> list[dict]:
    return [s for s in SPECS if not allow or s["name"] in allow or s["name"] in ("propose_link", "finish")]


def run_tool(name: str, args: dict, ctx: Ctx) -> ToolResult:
    fn = EXEC.get(name)
    if fn is None:
        return ToolResult({"error": f"unknown tool {name}"}, f"Nieznane narzędzie {name}.")
    try:
        return fn(dict(args or {}), ctx)
    except Exception as e:  # noqa: BLE001  (a failing source must not end the investigation)
        log.exception("tool %s failed", name)
        return ToolResult({"error": f"{type(e).__name__}: {str(e)[:200]}"}, f"{name}: błąd ({type(e).__name__}).")


def query_of(name: str, args: dict) -> str:
    for k in ("query", "domain", "url", "terms", "incident_id"):
        if args.get(k):
            return str(args[k])
    if args.get("domains"):
        d = args["domains"]
        return ", ".join(d[:4]) + (f" (+{len(d) - 4})" if len(d) > 4 else "") if isinstance(d, list) else str(d)
    return "wszyscy kandydaci" if name == "certpl_check" else ""
