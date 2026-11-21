"""Real-mode data layer. Source of truth = the engine corpus (`trop.engine.service.Corpus`, Postgres via `trop.store`
with JSON fallback) held in memory; jobs/SSE run through arq + Redis pub/sub.

Implemented (same method names as MockStore): health, stats, search, analyze/jobs/streams, incidents (+decision, matches,
features, history, artifacts), links, evidence values, traces, campaigns (+dna, members, indicators, timeline, variants,
phylogeny, summary), operators, operations, graph (+focus), batch (+results.csv), lab metrics (from `trop eval`).
Everything else (oracle, act, triage, hunter, persons, public, investigations CRUD ...) answers 501 -- never mock data.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import subprocess
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from fastapi import HTTPException

from trop.api import models as M
from trop.api.graphview import focus_view, norm_type
from trop.config import settings
from trop.schema import (
    AnalyzeAccepted,
    BOT_STEPS, Campaign, CampaignCounts, CampaignDNA, CampaignSummary, Decision, DnaRow, DomainIndicator, EvidenceItem,
    EvidenceValue, Event, GraphEdge, GraphNode, GraphPayload, Heat, Incident, IncidentSummary, Indicators, Job, JobInput,
    JobStep, LabMetrics, LinkExplanation, Member, Operation, Operator, Timeline, Variant, BatchResult, BatchRow,
    SearchHit, StatsOverview, MergePreview,
)
from trop.worker import bus

LAYERS = ["tracking", "kit", "infra", "content", "persons", "visual", "ad", "media"]
PL_NAMES = {
    "KMP-001": "Fałszywa Gazeta.pl — „Zyskarnia/Switowin”: inwestycja przez szokujący news (zmiana persony)",
    "KMP-002": "FinNews „Trudna odpowiedź” — inwestycja Baltic Pipe przez polityczny fake news",
    "KMP-003": "Fałszywa Gazeta.pl — Monika Olejnik kontra NBP/Glapiński (platforma inwestycyjna)",
    "KMP-004": "Cukrzyca — wywiad z „Ojcem Bonifacym z Jasnej Góry”",
    "KMP-005": "Bóle stawów RelieFlex — historia „weterynarza i konia 600 kg”",
    "KMP-006": "Ubytek słuchu (OtinaxMax) — VSL „przepis z kaktusa”",
    "KMP-007": "Nadciśnienie Kardivix — fałszywy czeski lekarz „MUDr. Štěpán Kovář”",
    "KMP-008": "Grzybica paznokci — „Dr Merritz”, oferta „dla wszystkich Polaków”",
    "KMP-009": "Divine Script — manifestacja obfitości (EN, brazylijski stos afiliacyjny)",
}
# (layer, section, key, strength)
FIELDS = [
    ("tracking", "tracking", "fb_pixels", "H"), ("tracking", "tracking", "capi_gateways", "H"), ("tracking", "tracking", "google_ads", "H"),
    ("tracking", "tracking", "ga4", "M"), ("tracking", "tracking", "gtm", "M"), ("tracking", "tracking", "tiktok_pixels", "H"),
    ("kit", "tracking", "kit_tenants", "H"), ("kit", "tracking", "lander_ids", "H"), ("kit", "tracking", "landing_type_ids", "M"),
    ("kit", "tracking", "kit_endpoints", "M"), ("kit", "tracking", "path_shapes", "M"), ("kit", "tracking", "chain_param_schemas", "M"),
    ("content", "content", "headline_template", "H"), ("content", "content", "h1_template", "M"), ("content", "content", "brands", "M"),
    ("persons", "content", "persons", "M"), ("persons", "content", "comment_names", "M"), ("persons", "ad", "persons", "M"),
    ("ad", "ad", "advertiser", "L"), ("visual", "ad", "creative_phash", "M"), ("visual", "landing", "favicon_mmh3", "M"),
]
W = {"H": 1.0, "M": 0.6, "L": 0.3}


def _s(x) -> list[str]:
    if x is None or x == "":
        return []
    return [str(i) for i in x if i not in (None, "")] if isinstance(x, (list, tuple, set)) else [str(x)]


def _triples(inc: dict) -> set[tuple[str, str, str]]:
    out = set()
    for layer, sec, key, _ in FIELDS:
        for v in _s((inc.get(sec) or {}).get(key)):
            out.add((layer, key, v))
    for d in (inc.get("infra") or {}).get("domains") or []:
        if d.get("etld1"):
            out.add(("infra", "etld1", d["etld1"]))
        if d.get("asn"):
            out.add(("infra", "asn", str(d["asn"])))
    for ip in (inc.get("infra") or {}).get("origin_ips") or []:
        out.add(("infra", "origin_ip", ip))
    return out


def _strength(layer: str, key: str) -> str:
    return next((s for l, _, k, s in FIELDS if l == layer and k == key), "M")


def _nf(what: str) -> HTTPException:
    return HTTPException(404, f"{what} not found")


class RealStore:
    mode = "live"

    def __init__(self) -> None:
        self._corpus = None
        self._dec: dict[str, Decision] = {}
        self.df: Counter = Counter()
        self.holders: dict[tuple, list[str]] = defaultdict(list)
        self.N = 0
        self._by_id: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)

        def not_wired(*a, **k):
            raise HTTPException(501, f"'{name}' is not available in real mode yet (no data source wired); the demo universe is served with --mock")
        return not_wired

    # ------------------------------------------------------------------------------------------ corpus
    @property
    def corpus(self):
        if self._corpus is None:
            from trop.engine import service
            try:
                self._corpus = service.Corpus.load(source="db")
            except Exception:  # noqa: BLE001
                self._corpus = service.Corpus.load()
            self._by_id = {i["id"]: i for i in self._corpus.incidents}
            self._index()
        return self._corpus

    def _index(self) -> None:
        c = self._corpus
        self.df: Counter = Counter()
        self.holders: dict[tuple, list[str]] = defaultdict(list)
        for inc in c.incidents:
            for t in _triples(inc):
                self.df[t] += 1
                self.holders[t].append(inc["id"])
        self.N = len(c.incidents)

    def reload(self) -> None:
        self._corpus, self._dec = None, {}

    def _camp_name(self, cid: str) -> str:
        return PL_NAMES.get(cid) or self.corpus.campaigns.get(cid, {}).get("name") or cid

    def health_counts(self) -> dict[str, int]:
        try:
            c = self.corpus
            return {"incidents": len(c.incidents), "campaigns_active": len(c.campaigns), "operators": len(c.operators)}
        except Exception:  # noqa: BLE001
            return {}

    # ------------------------------------------------------------------------------------------ evidence helpers
    def _item(self, layer: str, key: str, value: str, df: int | None = None, bot: str | None = None) -> EvidenceItem:
        import math
        self.corpus
        df = df if df is not None else self.df.get((layer, key, value), 1)
        n = max(self.N, 1)
        idf = round(math.log(n / max(df, 1)), 2) if df else 0.0
        st = _strength(layer, key)
        return EvidenceItem(type=layer, field=key, value=value, display=f"{key}: {value[:60]}", strength=st, weight=round(idf * W[st], 2),
                            df=df, N=n, idf=idf, state="zero" if df > n * 0.5 and n > 4 else "match", bot=bot)

    def _members(self, cid: str) -> list[dict]:
        return self.corpus.members(cid)

    def _camp_of(self, iid: str) -> str | None:
        return self.corpus.campaign_of.get(iid)

    # ------------------------------------------------------------------------------------------ dashboard
    def overview(self, window: str) -> StatsOverview:
        c = self.corpus
        return StatsOverview(window=window, incidents=len(c.incidents), incidents_new=0, campaigns_active=len(c.campaigns),
                             operators=len(c.operators), N=len(c.incidents))

    def alerts(self, status):
        return []

    def search(self, q: str) -> list[SearchHit]:
        ql, out = q.lower().strip(), []
        if not ql:
            return out
        for cid, m in self.corpus.campaigns.items():
            if ql in cid.lower() or ql in self._camp_name(cid).lower():
                out.append(SearchHit(kind="campaign", id=cid, label=self._camp_name(cid), href=f"/kampanie/{cid}"))
        for oid in self.corpus.operators:
            if ql in oid.lower():
                out.append(SearchHit(kind="operator", id=oid, label=oid, href=f"/operatorzy/{oid}"))
        for inc in self.corpus.incidents:
            host = (inc.get("landing") or {}).get("host") or ""
            adv = (inc.get("ad") or {}).get("advertiser") or ""
            if ql in inc["id"].lower() or ql in host.lower() or ql in adv.lower():
                out.append(SearchHit(kind="incident", id=inc["id"], label=f"{inc['id']} · {host or adv}", href=f"/incydenty/{inc['id']}"))
            for p in _s((inc.get("content") or {}).get("persons")):
                if ql in p.lower() and not any(h.id == p for h in out):
                    out.append(SearchHit(kind="person", id=p, label=p, href=f"/slad/persons/{p}"))
        for (layer, key, val), df in self.df.items():
            if ql in val.lower() and layer in ("tracking", "kit") and not any(h.id == val for h in out):
                out.append(SearchHit(kind="tracking", id=val, label=f"{key}: {val}", href=f"/slad/{layer}/{val}"))
        return out[:40]

    # ------------------------------------------------------------------------------------------ jobs (arq -> Redis -> SSE)
    async def analyze(self, kind: str, name: str, saved: list[str] | None = None) -> AnalyzeAccepted:
        if kind == "trace":
            return AnalyzeAccepted(job_id=None, trace={"type": "trace", "value": name})
        from arq import create_pool
        from arq.connections import RedisSettings
        jid = "JOB-" + uuid.uuid4().hex[:12].upper()
        r = bus.client()
        k = kind if kind in ("url", "file", "zip", "folder", "batch") else "file"
        await bus.set_state(r, jid, {"id": jid, "status": "queued", "input": {"kind": k, "name": name}})
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            await pool.enqueue_job("analyze", jid, {"kind": kind, "name": name, "paths": saved or []}, _job_id=jid)
        finally:
            await pool.aclose()
        return AnalyzeAccepted(job_id=jid, incident_id=None)

    async def job(self, jid: str) -> Job:
        r = bus.client()
        st = await bus.get_state(r, jid)
        if not st:
            raise HTTPException(404, "job not found")
        job = Job(id=jid, status=st["status"], input=JobInput(**st["input"]) if "input" in st else JobInput(kind="batch", name=jid),
                  incident_id=st.get("incident_id"), decision=st.get("decision"), campaign_id=st.get("campaign_id"), error=st.get("error"))
        steps = {s.key: s for s in job.steps}
        for raw in await r.lrange(bus.ekey(f"job:{jid}"), 0, -1):
            ev = Event.model_validate_json(raw)
            if ev.type == "job.step":
                s = JobStep.model_validate(ev.data["step"])
                steps[s.key] = s
        job.steps = [steps[k] for k, _, _ in BOT_STEPS]
        done = [s.duration_ms or 0 for s in job.steps]
        if job.status == "done":
            job.total_ms = sum(done)
        return job

    async def jobs_list(self, limit: int) -> list[Job]:
        r = bus.client()
        ids = await r.zrevrange("trop:jobs", 0, limit - 1)
        out = []
        for i in ids:
            try:
                out.append(await self.job(i))
            except HTTPException:
                pass
        return out

    async def job_events(self, jid: str) -> AsyncIterator[Event]:
        """History + live events; ends right after job.done / job.error, or when the job state says it is finished and nothing arrives."""
        r = bus.client()
        it = bus.subscribe(r, f"job:{jid}").__aiter__()
        try:
            while True:
                try:
                    ev = await asyncio.wait_for(it.__anext__(), 3.0)
                except StopAsyncIteration:
                    return
                except asyncio.TimeoutError:
                    st = await bus.get_state(r, jid)
                    if st and st.get("status") in ("done", "error"):
                        return
                    continue
                yield ev
                if ev.type in ("job.done", "job.error"):
                    return
        finally:
            await it.aclose()
            await r.aclose()

    def channel_events(self, name: str) -> AsyncIterator[Event]:
        return bus.subscribe(bus.client(), name, history=False, stop_on_terminal=False)

    # ------------------------------------------------------------------------------------------ incidents
    async def _stored(self, iid: str) -> dict | None:
        raw = await bus.client().get(f"trop:incident:{iid}")
        return json.loads(raw) if raw else None

    def _loo_decision(self, iid: str) -> Decision:
        """Decision for a known incident, leave-one-out (otherwise it trivially duplicates itself)."""
        if iid in self._dec:
            return self._dec[iid]
        from trop.engine import service
        c2 = self.corpus.copy()
        c2.incidents = [i for i in c2.incidents if i["id"] != iid]
        d, _ = service.analyze_incident(self._by_id[iid], c2)
        self._dec[iid] = d
        return d

    def _summary(self, inc: dict, with_decision: bool = False) -> IncidentSummary:
        ad, lan = inc.get("ad") or {}, inc.get("landing") or {}
        persons = _s(ad.get("persons")) or _s((inc.get("content") or {}).get("persons"))
        d = self._loo_decision(inc["id"]) if with_decision and self.N <= 120 else None
        return IncidentSummary(id=inc["id"], captured_at=(inc.get("source") or {}).get("captured_at"), source=(inc.get("source") or {}).get("type") or "manual",
                               domain=lan.get("host") or None, title=lan.get("title") or (ad.get("text") or "")[:90] or None,
                               person=persons[0] if persons else None, campaign_id=self._camp_of(inc["id"]),
                               decision=d.decision if d else None, p=d.p if d else None, coverage=d.coverage if d else None)

    def incidents(self, campaign_id=None, source=None, q=None, frm=None, to=None, limit=50, cursor=None):
        rows = []
        for inc in self.corpus.incidents:
            s = self._summary(inc)
            if campaign_id and s.campaign_id != campaign_id:
                continue
            if source and s.source != source:
                continue
            if q and q.lower() not in f"{s.id} {s.domain} {s.title}".lower():
                continue
            rows.append(s)
        i = int(cursor or 0)
        return [self._summary(self._by_id[s.id], True) for s in rows[i:i + limit]], (str(i + limit) if i + limit < len(rows) else None)

    async def incident(self, iid: str) -> M.IncidentDetail:
        self.corpus
        if iid in self._by_id:
            d = self._loo_decision(iid)
            doc = dict(self._by_id[iid])
        else:
            st = await self._stored(iid)
            if not st:
                raise _nf("incident")
            doc, d = dict(st["incident"]), Decision.model_validate(st["decision"])
        doc = {k: v for k, v in doc.items() if not k.startswith("_")}
        doc["source"] = {**(doc.get("source") or {}), "path": None}     # local paths are never exposed
        return M.IncidentDetail.model_validate({**doc, "decision": {"campaign_id": d.campaign_id, "p": d.p, "decision": d.decision}, "coverage": d.coverage})

    async def decision(self, iid: str) -> Decision:
        self.corpus
        if iid in self._by_id:
            return self._loo_decision(iid)
        st = await self._stored(iid)
        if not st:
            raise _nf("incident")
        return Decision.model_validate(st["decision"])

    async def matches(self, iid: str, k: int, scope: str) -> list[M.Match]:
        d = await self.decision(iid)
        out = [M.Match(kind="campaign", id=s.campaign_id, label=self._camp_name(s.campaign_id), score=s.score, p=s.p, same_operator=s.score_operator >= 3,
                       top_evidence=[e.display for e in d.evidence[:2]]) for s in d.scores]
        if scope == "incidents":
            cid = d.campaign_id or d.candidate_campaign_id
            out = [M.Match(kind="incident", id=m["id"], label=m["id"], score=0.0, same_operator=True) for m in self._members(cid or "") if m["id"] != iid]
        return out[:k]

    async def features(self, iid: str) -> list[M.FeatureGroup]:
        self.corpus
        inc = self._by_id.get(iid) or (await self._stored(iid) or {}).get("incident")
        if not inc:
            raise _nf("incident")
        groups: dict[str, list[M.FeatureRow]] = defaultdict(list)
        for layer, key, v in sorted(_triples(inc)):
            df = max(self.df.get((layer, key, v), 0), 1)
            it = self._item(layer, key, v, df)
            groups[layer].append(M.FeatureRow(field=key, value=v, df=df, N=self.N, idf=it.idf))
        return [M.FeatureGroup(layer=k, features=v) for k, v in groups.items()]

    async def history(self, iid: str) -> list[M.HistoryEvent]:
        inc = await self.incident(iid)
        d = await self.decision(iid)
        at = (inc.source.captured_at if inc.source else None) or ""
        return [M.HistoryEvent(at=str(at), kind="captured", text=f"Przechwycono ({inc.source.type})"),
                M.HistoryEvent(at=str(at), kind="decision", text=f"Decyzja: {d.decision} (p={d.p:.2f})")]

    async def artifacts(self, iid: str) -> list[M.Artifact]:
        inc = await self.incident(iid)
        out = []
        for key, kind in (("screenshot_path", "screenshot"),):
            for sec in (inc.ad, inc.landing):
                p = getattr(sec, key, None)
                if p:
                    out.append(M.Artifact(kind=kind, name=Path(p).name, url="", size=0))
        return out

    # ------------------------------------------------------------------------------------------ links / evidence
    async def link(self, a: str, b: str, view: str):
        if view == "diff":
            raise HTTPException(501, "template diff is not available in real mode yet")
        from trop.engine import service
        self.corpus
        extra = {}
        for x in (a, b):
            if x not in self._by_id and not x.startswith("KMP-"):
                st = await self._stored(x)
                if st:
                    extra[x] = st["incident"]
        try:
            return service.explain(extra.get(a, a), extra.get(b, b), self.corpus)
        except KeyError as e:
            raise HTTPException(404, str(e))

    def evidence_value(self, type_: str, value: str) -> EvidenceValue:
        self.corpus
        try:
            canon, layer = norm_type(type_)
        except KeyError:
            raise _nf(f"evidence type {type_}")
        type_ = layer
        trip = [t for t in self.holders if t[0] == type_ and (t[2] == value or (canon == "domain" and t[2].endswith(value)))]
        if not trip:
            raise _nf("evidence value")
        ids = sorted({i for t in trip for i in self.holders[t]})
        camps = Counter(self._camp_of(i) for i in ids)
        it = self._item(*trip[0])
        seen = sorted(str((self._by_id[i].get("source") or {}).get("captured_at") or "") for i in ids)
        return EvidenceValue(type=type_, field=trip[0][1], value=value, df=len(ids), N=self.N, idf=it.idf, first_seen=seen[0] or None, last_seen=seen[-1] or None,
                             campaigns=[{"id": c, "n": n} for c, n in camps.most_common() if c], incidents=[self._summary(self._by_id[i]) for i in ids[:20]])

    def trace(self, type_: str, value: str) -> M.TraceView:
        ev = self.evidence_value(type_, value)
        type_ = norm_type(type_)[0]
        ids = [s.id for s in ev.incidents]
        co = Counter(t for i in ids for t in _triples(self._by_id[i]) if t[2] != value and t[0] in ("tracking", "kit"))
        return M.TraceView(value=value, type=type_, campaigns=ev.campaigns, weekly=[], latest=[s.model_dump(mode="json") for s in ev.incidents[:10]],
                           usage=[{"where": "incydenty", "count": ev.df}],
                           co_traces=[{"type": t[0], "value": t[2], "count": n} for t, n in co.most_common(8)])

    # ------------------------------------------------------------------------------------------ campaigns
    def _dna_rows(self, cid: str) -> list[DnaRow]:
        mem = self._members(cid)
        cnt: Counter = Counter()
        for inc in mem:
            for t in _triples(inc):
                cnt[t] += 1
        rows = []
        for t, n in cnt.items():
            df = self.df[t]
            if df > max(3, self.N * 0.4) or (n < 2 and len(mem) > 1):
                continue
            it = self._item(*t)
            rows.append(DnaRow(layer=t[0], field=t[1], value=t[2], display=it.display, members_with=n, members_total=len(mem), strength=it.strength))
        rows.sort(key=lambda r: (-r.members_with / max(r.members_total, 1), {"H": 0, "M": 1, "L": 2}[r.strength], r.field))
        return rows[:24]

    def _persons(self, mem: list[dict]) -> list[str]:
        return sorted({p for i in mem for p in _s((i.get("content") or {}).get("persons")) + _s((i.get("ad") or {}).get("persons"))})

    def _domains(self, mem: list[dict]) -> list[str]:
        return sorted({d["fqdn"] for i in mem for d in (i.get("infra") or {}).get("domains") or [] if d.get("fqdn")})

    def _csummary(self, cid: str) -> Campaign:
        m, mem = self.corpus.campaigns[cid], self._members(cid)
        doms = self._domains(mem)
        advs = {(i.get("ad") or {}).get("advertiser") for i in mem} - {None, ""}
        return Campaign(id=cid, name=self._camp_name(cid), narrative=(m.get("name") or "")[:160], vertical=m.get("vertical"),
                        status=m.get("status") if m.get("status") in ("active", "fading", "candidate", "closed") else "active",
                        operator_id=m.get("operator_id"), operation_id=m.get("operation_id"), heat=Heat(), n_incidents=len(mem), n_domains=len(doms),
                        persons=self._persons(mem), description=m.get("name") or "",
                        counts=CampaignCounts(incidents=len(mem), domains=len(doms), advertisers=len(advs), persons=len(self._persons(mem))),
                        brands=sorted({b for i in mem for b in _s((i.get("content") or {}).get("brands"))})[:6])

    def campaigns(self, sort: str | None, status: str | None) -> list[CampaignSummary]:
        rows = [self._csummary(c) for c in sorted(self.corpus.campaigns)]
        rows = [r for r in rows if not status or r.status == status]
        if sort in ("-heat", "heat"):
            rows.sort(key=lambda r: r.n_incidents, reverse=sort.startswith("-"))
        return [CampaignSummary.model_validate(r.model_dump(include=set(CampaignSummary.model_fields))) for r in rows]

    def campaign(self, cid: str) -> Campaign:
        if cid not in self.corpus.campaigns:
            raise _nf("campaign")
        return self._csummary(cid)

    def dna(self, cid: str) -> CampaignDNA:
        self.campaign(cid)
        return CampaignDNA(campaign_id=cid, signature=self._dna_rows(cid))

    def timeline(self, cid: str) -> Timeline:
        self.campaign(cid)
        days = Counter(str((i.get("source") or {}).get("captured_at") or "")[:10] for i in self._members(cid))
        days.pop("", None)
        return Timeline(days=[{"date": d, "incidents": n} for d, n in sorted(days.items())], events=[])

    def members(self, cid: str, level=None, sort=None, coverage_lt=None, limit=100, cursor=None):
        self.campaign(cid)
        out = []
        for inc in self._members(cid):
            d = self._loo_decision(inc["id"]) if self.N <= 120 else None
            s = self._summary(inc)
            out.append(Member(incident_id=inc["id"], captured_at=str(s.captured_at) if s.captured_at else None, source=s.source, domain=s.domain, person=s.person,
                              level="L2", variant_id=self.corpus.variant_of.get(inc["id"]), score=d.score if d else 0.0, p=d.p if d else 0.0,
                              top_evidence=(d.evidence[:3] if d else []), layers=d.layers if d else []))
        if coverage_lt is not None:
            out = [m for m in out if sum(1 for l in m.layers if l.state == "available") / 8 < coverage_lt]
        i = int(cursor or 0)
        return out[i:i + limit], (str(i + limit) if i + limit < len(out) else None)

    def indicators(self, cid: str, type_: str | None) -> Indicators:
        self.campaign(cid)
        mem = self._members(cid)
        doms = {}
        for i in mem:
            for d in (i.get("infra") or {}).get("domains") or []:
                en = d.get("enrich") or {}
                doms.setdefault(d["fqdn"], DomainIndicator(fqdn=d["fqdn"], cert_issued_at=(d.get("cert") or {}).get("not_before"),
                                                           registered_at=en.get("created"), on_certpl=bool((i.get("infra") or {}).get("on_certpl_list")), ads_seen=0))
                doms[d["fqdn"]].ads_seen += 1
        rows = self._dna_rows(cid)
        mk = lambda layer: [self._item(r.layer, r.field, r.value) for r in rows if r.layer == layer]  # noqa: E731
        pc = Counter(p for i in mem for p in _s((i.get("content") or {}).get("persons")))
        adv = sorted({(i.get("ad") or {}).get("advertiser") for i in mem} - {None, ""})
        return Indicators(domains=list(doms.values()), tracking=mk("tracking"), kit=mk("kit"),
                          persons=[{"id": p, "name": p, "count": n} for p, n in pc.most_common()],
                          advertisers=[{"name": a, "page_id": next((i["ad"].get("page_id") for i in mem if i["ad"].get("advertiser") == a), None), "removed": False} for a in adv])

    def variants(self, cid: str) -> list[Variant]:
        self.campaign(cid)
        g: dict[str, list[str]] = defaultdict(list)
        for i in self._members(cid):
            g[self.corpus.variant_of.get(i["id"]) or "V1"].append(i["id"])
        return [Variant(id=v, campaign_id=cid, label=f"{v} ({len(m)})", members=m) for v, m in sorted(g.items())]

    def phylogeny(self, cid: str) -> M.Phylogeny:
        vs = self.variants(cid)
        return M.Phylogeny(campaign_id=cid, nodes=[{"id": cid, "kind": "campaign", "label": cid}] + [{"id": v.id, "kind": "variant", "label": v.label} for v in vs],
                           edges=[{"a": cid, "b": v.id} for v in vs])

    def summary(self, cid: str) -> M.CampaignSummaryText:
        c = self.campaign(cid)
        return M.CampaignSummaryText(campaign_id=cid, text=f"{c.name}. {c.n_incidents} incydentów, {c.n_domains} domen.",
                                     bullets=[f"Operator: {c.operator_id or 'nieustalony'}", f"Operacja: {c.operation_id or '—'}"], generated_by="engine")

    def operators(self) -> list[Operator]:
        return [self.operator(o) for o in sorted(self.corpus.operators)]

    def operator(self, oid: str) -> Operator:
        o = self.corpus.operators.get(oid)
        if o is None:
            raise _nf("operator")
        camps = o.get("campaigns") or [c for c, m in self.corpus.campaigns.items() if m.get("operator_id") == oid]
        shared: list[EvidenceItem] = []
        for c in camps:
            for r in self._dna_rows(c)[:3]:
                shared.append(self._item(r.layer, r.field, r.value))
        return Operator(id=oid, codename=oid, campaigns=[{"id": c, "name": self._camp_name(c), "incidents": len(self._members(c))} for c in camps],
                        shared=shared[:8], narratives=[self._camp_name(c) for c in camps],
                        operation_id=self.corpus.campaigns.get(camps[0], {}).get("operation_id") if camps else None)

    def operations(self) -> list[Operation]:
        return [self.operation(o) for o in sorted(self.corpus.operations)]

    def operation(self, oid: str) -> Operation:
        o = self.corpus.operations.get(oid)
        if o is None:
            raise _nf("operation")
        camps = o.get("campaigns") or []
        return Operation(id=oid, name=o.get("name") or " + ".join(camps) or oid, campaigns=camps, operators=o.get("operators") or [], funnel=[],
                         shared=[self._item(r.layer, r.field, r.value) for c in camps for r in self._dna_rows(c)[:2]][:6])

    def merge_preview(self, cid: str, other: str) -> MergePreview:
        a, b = self.campaign(cid), self.campaign(other)
        sa = CampaignSummary.model_validate(a.model_dump(include=set(CampaignSummary.model_fields)))
        sb = CampaignSummary.model_validate(b.model_dump(include=set(CampaignSummary.model_fields)))
        sh = {(r.layer, r.field, r.value) for r in self._dna_rows(cid)} & {(r.layer, r.field, r.value) for r in self._dna_rows(other)}
        return MergePreview(a=sa, b=sb, shared=[self._item(*t) for t in sh], before={cid: a.n_incidents, other: b.n_incidents}, after={cid: a.n_incidents + b.n_incidents})

    # ------------------------------------------------------------------------------------------ graph
    async def graph(self, scope=None, layers=None, level=None, min_weight=0.0, focus=None, origin=None) -> GraphPayload:
        c = self.corpus
        extra: dict[str, dict] = {}                 # freshly analysed incidents (not in the corpus) referenced by focus/origin
        for x in (focus, origin):
            if x and x.startswith("INC-") and x not in self._by_id:
                st = await self._stored(x)
                if st:
                    extra[x] = st["incident"]
        nodes: dict[str, GraphNode] = {}
        edges: list[GraphEdge] = []
        ls = set(layers.split(",")) if layers else None
        for cid in c.campaigns:
            nodes[cid] = GraphNode(id=cid, kind="campaign", label=f"{cid} · {self._camp_name(cid)[:40]}", campaign_id=cid, size=2 + len(self._members(cid)))
            op = c.campaigns[cid].get("operator_id")
            if op:
                nodes.setdefault(op, GraphNode(id=op, kind="operator", label=op, size=4))
                edges.append(GraphEdge(a=cid, b=op, type="operator", weight=3, level="L3"))
        for inc in c.incidents:
            iid, cid = inc["id"], self._camp_of(inc["id"])
            nodes[iid] = GraphNode(id=iid, kind="incident", label=iid, campaign_id=cid, size=1.5, first_seen=str((inc.get("source") or {}).get("captured_at") or "") or None)
            if cid:
                edges.append(GraphEdge(a=iid, b=cid, type="member", weight=1, level="L2"))
            host = (inc.get("landing") or {}).get("host")
            if host:
                nodes.setdefault(f"d:{host}", GraphNode(id=f"d:{host}", kind="domain", label=host, campaign_id=cid, size=1))
                edges.append(GraphEdge(a=f"d:{host}", b=iid, type="member", weight=1, level="L2"))
        holders = {k: list(v) for k, v in self.holders.items()}
        for xid, xinc in extra.items():
            lan = xinc.get("landing") or {}
            nodes[xid] = GraphNode(id=xid, kind="incident", label=xid, size=1.5)
            if lan.get("host"):
                nodes.setdefault(f"d:{lan['host']}", GraphNode(id=f"d:{lan['host']}", kind="domain", label=lan["host"], size=1))
                edges.append(GraphEdge(a=f"d:{lan['host']}", b=xid, type="member", weight=1, level="L2"))
            for t in _triples(xinc):
                holders.setdefault(t, []).append(xid)
            for cdn in _s((xinc.get("infra") or {}).get("cdn")):
                holders.setdefault(("infra", "cdn", cdn), []).append(xid)
        for inc in c.incidents:                                                  # the CDN (Cloudflare) is a weak, platform-level trace
            for cdn in _s((inc.get("infra") or {}).get("cdn")):
                holders.setdefault(("infra", "cdn", cdn), []).append(inc["id"])
        for (layer, key, val), ids in holders.items():
            fresh = any(i in extra for i in ids)
            if (layer in ("tracking", "kit") or key == "cdn") and (fresh or 2 <= len(ids) <= max(3, self.N // 2) or key == "cdn") and (ls is None or layer in ls):
                tid = f"trace:{key}:{val}"
                it = self._item(layer, key, val, len(ids)) if key != "cdn" else self._item("infra", "cdn", val, len(ids))
                nodes[tid] = GraphNode(id=tid, kind="trace", label=f"{key}: {val[:28]}", size=2,
                                       meta={"field": key, "value": val, "layer": layer, **({"weak": True} if key == "cdn" else {})})
                edges += [GraphEdge(a=tid, b=i, type=layer, weight=max(it.weight, 0.1), level="L2") for i in ids]
        if scope and scope.startswith("campaign:"):
            cid = scope.split(":", 1)[1]
            keep = {n for n, v in nodes.items() if v.campaign_id == cid or n == cid}
            keep |= {e.a for e in edges if e.b in keep} | {e.b for e in edges if e.a in keep}
            nodes = {k: v for k, v in nodes.items() if k in keep}
        edges = [e for e in edges if e.a in nodes and e.b in nodes and e.weight >= min_weight]
        hulls = [{"id": cid, "kind": "campaign", "members": [n for n, v in nodes.items() if v.campaign_id == cid], "label": cid} for cid in c.campaigns]
        g = GraphPayload(nodes=list(nodes.values()), edges=edges, hulls=[h for h in hulls if h["members"]])
        if focus:
            for p in {i for inc in c.incidents for i in _s((inc.get("content") or {}).get("persons"))}:   # person:<name> nodes
                pid = f"person:{p}"
                if pid not in nodes:
                    g.nodes.append(GraphNode(id=pid, kind="person", label=p, size=1.5))
                    g.edges += [GraphEdge(a=pid, b=i["id"], type="persons", weight=1.5, level="L2") for i in c.incidents if p in _s((i.get("content") or {}).get("persons"))]
            focus = self._alias_focus(g, focus, origin)
            try:
                return focus_view(g, focus, origin)
            except KeyError:
                raise _nf("node")
        return g

    KIT_FIELDS = {"kit_tenants", "lander_ids", "landing_type_ids", "kit_endpoints", "path_shapes", "chain_param_schemas"}

    def _alias_focus(self, g: GraphPayload, focus: str, origin: str | None) -> str:
        """Ids the web derives from chips (web/lib/graph.ts): trace:kit | trace:capi | trace:cdn | trace:pixel:<v> | trace:content:<v> |
        trace:<field>:<value> | bare domain | cert:... -> real node ids (`trace:<field>:<value>`, `d:<host>`)."""
        ids = {n.id for n in g.nodes}
        if focus in ids:
            return focus
        near = {e.b if e.a == origin else e.a for e in g.edges if origin and origin in (e.a, e.b)}
        trace_nodes = [n for n in g.nodes if n.kind == "trace"]

        def best(cands):
            cands = sorted(cands, key=lambda n: (n.id not in near, -(n.size or 0), n.id))
            return cands[0].id if cands else None
        if focus.startswith("trace:"):
            parts = focus.split(":", 2)
            if len(parts) == 2:
                fields = {"kit": self.KIT_FIELDS, "capi": {"capi_gateways"}, "cdn": {"cdn"}}.get(parts[1], {parts[1]})
                hit = best([n for n in trace_nodes if n.meta.get("field") in fields])
            else:
                key, val = parts[1], parts[2]
                field = {"pixel": "fb_pixels", "content": "headline_template"}.get(key, key)
                hit = best([n for n in trace_nodes if n.meta.get("value") == val and n.meta.get("field") in (field, key, None)]
                           or [n for n in trace_nodes if n.meta.get("value") == val])
            if hit:
                return hit
        elif "." in focus and ":" not in focus and f"d:{focus}" in ids:         # bare domain
            return f"d:{focus}"
        return focus

    # ------------------------------------------------------------------------------------------ batch
    async def batch(self, names: list[str], path: str | None = None) -> M.BatchAccepted:
        from arq import create_pool
        from arq.connections import RedisSettings
        jid = "JOB-B" + uuid.uuid4().hex[:10].upper()
        await bus.set_state(bus.client(), jid, {"id": jid, "status": "queued"})
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            await pool.enqueue_job("batch", jid, path, _job_id=jid)
        finally:
            await pool.aclose()
        return M.BatchAccepted(job_id=jid)

    async def batch_result(self, jid: str) -> BatchResult:
        st = await bus.get_state(bus.client(), jid)
        if not st:
            raise _nf("batch")
        if st["status"] == "error":
            raise HTTPException(500, st.get("error") or "batch failed")
        if st["status"] != "done":
            raise HTTPException(202, "batch still running")
        rows = [BatchRow.model_validate(r) for r in st["rows"]]
        return BatchResult(job_id=jid, n_items=len(rows), rows=rows, csv_url=f"/api/v1/batch/{jid}/results.csv", json_url=f"/api/v1/batch/{jid}")

    async def batch_csv(self, jid: str) -> str:
        r = await self.batch_result(jid)
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(BatchRow.model_fields))
        w.writeheader()
        for row in r.rows:
            w.writerow({k: ("" if v is None else v) for k, v in row.model_dump().items()})
        return buf.getvalue()

    # ------------------------------------------------------------------------------------------ investigations (WS6 agent)
    def investigations(self, status=None):
        from trop.agent import service as svc
        return [i for i in svc.list_investigations(status) if not i.campaign_id or i.campaign_id in self.corpus.campaigns]

    def investigation(self, iid: str):
        from trop.agent import service as svc
        try:
            return svc.get_investigation(iid)
        except (FileNotFoundError, KeyError):
            raise _nf("investigation")

    async def create_investigation(self, body) -> dict:
        from arq import create_pool
        from arq.connections import RedisSettings
        from trop.agent import service as svc
        from datetime import datetime, timezone
        from trop.schema import Investigation
        iid = svc.new_investigation_id()
        svc._save(Investigation(id=iid, seed=body.seed, campaign_id=body.campaign_id, status="running",       # visible to GET at once (no 404 race)
                                budget={"steps": float(body.budget_steps), "used": 0.0, "usd": 1.0, "usd_used": 0.0},
                                started_at=datetime.now(timezone.utc).isoformat(timespec="seconds")))
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            await pool.enqueue_job("agent", iid, body.model_dump(), _job_id=iid)
        finally:
            await pool.aclose()
        return {"id": iid}

    async def _inv_stream(self, iid: str):
        from trop.agent import service as svc
        r = bus.client()
        if await r.llen(bus.ekey(f"inv:{iid}")):
            async for ev in bus.subscribe(r, f"inv:{iid}"):
                yield ev
            return
        try:
            hist = svc.events(iid)
        except (FileNotFoundError, KeyError):
            hist = []
        for e in hist:                                  # finished (or not yet started) run: recorded history
            yield Event.model_validate(e)
        if not hist or hist[-1].get("type") != "investigation.done":
            async for ev in bus.subscribe(r, f"inv:{iid}", history=False):
                yield ev

    def investigation_events(self, iid: str):
        return self._inv_stream(iid)

    def steer(self, iid: str, body):
        from trop.agent import service as svc
        r = svc.steer(iid, message=body.message, node_id=body.node_id, choice=body.choice)
        return M.Ack(ok=bool(r.get("ok", True)), detail=r.get("detail"))

    def stop(self, iid: str):
        from trop.agent import service as svc
        r = svc.stop(iid)
        return M.Ack(ok=bool(r.get("ok", True)), detail=r.get("detail"))

    def promote(self, iid: str, campaign_id: str, node_ids: list[str]):
        from trop.agent import service as svc
        r = svc.promote(iid, campaign_id, node_ids)
        return M.PromoteResult(campaign_id=r["campaign_id"], added=int(r["added"]))

    # ------------------------------------------------------------------------------------------ act (WS6)
    def act_packages(self):
        from trop.act import service as act
        return [x for x in act.list_packages() if x.campaign_id in self.corpus.campaigns]   # no fictional campaigns in real mode

    def act_package(self, pid: str):
        from trop.act import service as act
        try:
            return act.get_package(pid)
        except (FileNotFoundError, KeyError):
            raise _nf("package")

    async def act_create(self, body):
        from trop.act import service as act
        use_llm = bool(settings.gemini_api_key or settings.openrouter_api_key) and __import__("os").environ.get("TROP_NO_LIVE") != "1"
        return await asyncio.to_thread(lambda: act.create_package(body, use_llm=use_llm))

    def act_notice(self, pid: str, text: str):
        from trop.act import service as act
        return act.update_notice(pid, text)

    def act_submit(self, pid: str):
        from trop.act import service as act
        return act.submit(pid, emit=lambda t, d: bus.publish_sync("events", t, d))

    def act_download(self, pid: str, fmt: str):
        from trop.act import service as act
        try:
            return act.download(pid, fmt)
        except (FileNotFoundError, KeyError):
            raise _nf("package")

    def act_rules(self, campaign):
        from trop.act import service as act
        return act.rules(campaign) if campaign else [r for c in self.corpus.campaigns for r in act.rules(c)]

    def act_rule_test(self, body):
        from trop.act import service as act
        return act.test_rule(body.kind, body.body)

    # ------------------------------------------------------------------------------------------ hunter (WS5)
    def hunter_sources(self):
        from trop.hunter import sources
        return sources.list_sources()

    def hunter_runs(self, limit: int):
        from trop.hunter import sources
        return sources.list_runs(limit=limit)

    def hunter_creds(self):
        from trop.hunter import sources
        return [M.CredStatus(source_id=x.id, status=x.credentials_status) for x in sources.list_sources()]

    async def hunter_run(self, sid: str):
        from arq import create_pool
        from arq.connections import RedisSettings
        from trop.worker.tasks import HUNT_RUNNERS
        if sid not in HUNT_RUNNERS:
            raise _nf("source")
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            job = await pool.enqueue_job("hunt", sid)
        finally:
            await pool.aclose()
        return M.RunStarted(run_id=f"queued:{job.job_id if job else sid}")

    # ------------------------------------------------------------------------------------------ oracle (WS5)
    def predictions(self, status=None):
        from trop.oracle import service as oracle
        return oracle.list_predictions(status)

    def oracle_dna(self, campaign=None):
        from trop.oracle import service as oracle
        d = oracle.get_dna(campaign)
        if d is None:
            raise _nf("domain DNA (run `trop oracle train`)")
        return d

    def oracle_metrics(self):
        from trop.oracle import service as oracle
        return oracle.get_metrics()

    # ------------------------------------------------------------------------------------------ public (coarse; never KMP ids / indicators)
    PUBLIC_NAME = {"investment": "Fałszywe wiadomości z „inwestycją”", "health": "Fałszywy lekarz poleca preparat",
                   "loan": "Pożyczki „bez BIK” z fałszywym bankiem"}
    PUBLIC_REASON = {"tracking": "ta sama sieć reklam i przekierowań", "kit": "ta sama sieć reklam i przekierowań",
                     "content": "ten sam szablon tekstu", "persons": "ten sam wizerunek osoby", "visual": "ten sam wygląd strony",
                     "infra": "ta sama infrastruktura stron", "ad": "ten sam schemat reklamy", "media": "to samo nagranie"}

    def _public_campaign(self, d: Decision):
        from trop.schema import PublicCampaign
        cid = d.campaign_id or d.candidate_campaign_id
        if not cid or cid not in self.corpus.campaigns:
            return None
        mem = self._members(cid)
        seen = sorted(str((i.get("source") or {}).get("captured_at") or "")[:10] for i in mem if (i.get("source") or {}).get("captured_at"))
        vert = (self.corpus.campaigns[cid].get("vertical") or "").split(" ")[0]
        reasons = []
        for e in d.evidence:
            r = self.PUBLIC_REASON.get(e.type)
            if e.state == "match" and e.weight > 0 and r and r not in reasons:
                reasons.append(r)
        return PublicCampaign(name=self.PUBLIC_NAME.get(vert, "Znana kampania oszustwa reklamowego"), seen_count=len(mem),
                              since=seen[0] if seen else "2026", reasons=reasons[:4] or ["podobieństwo do znanych oszustw"])

    def _quick_decision(self, inc_doc: dict) -> Decision:
        from trop.engine import service
        inc = Incident.model_validate({"id": "PUB-TMP", **inc_doc}).model_dump(mode="json")
        d, _ = service.analyze_incident(inc, self.corpus)
        return d

    async def public_check(self, url, text):
        from trop.schema import CheckResult
        inc: dict = {}
        if url:
            from urllib.parse import urlsplit
            host = (urlsplit(url if "//" in url else "//" + url).hostname or "").lower()
            inc = {"landing": {"entry_url": url, "host": host, "etld1": ".".join(host.split(".")[-2:])},
                   "infra": {"domains": [{"fqdn": host, "etld1": ".".join(host.split(".")[-2:])}]}}
        if text:
            inc.setdefault("landing", {})["text"] = text
            inc["ad"] = {"text": text}
        if not inc:
            raise HTTPException(422, "provide `url` or `text`")
        d = await asyncio.to_thread(self._quick_decision, inc)
        pc = self._public_campaign(d) if d.decision in ("assign", "confirm") else None
        if pc:
            return CheckResult(verdict="scam", public_campaign=pc, advice=["Nie klikaj w link i nie podawaj danych.", "Zgłoś reklamę platformie i na incydent.cert.pl."])
        return CheckResult(verdict="unknown", advice=["Brak dopasowania nie oznacza, że strona jest bezpieczna.", "Zachowaj ostrożność; możesz ją zgłosić."])

    async def public_match(self, p):
        from trop.schema import ExtensionMatch
        inc = {"ad": {"advertiser": p.advertiser, "text": p.caption, "creative_phash": p.creative_phash},
               "landing": {"entry_url": p.cta_url, "text": p.caption}}
        d = await asyncio.to_thread(self._quick_decision, inc)
        pc = self._public_campaign(d) if d.decision in ("assign", "confirm") else None
        if pc:
            return ExtensionMatch(match=True, label="Pasuje do znanej kampanii oszustwa", public_campaign=pc, reasons=pc.reasons)
        return ExtensionMatch(match=False)

    async def public_report(self, r):
        rid = "REP-" + uuid.uuid4().hex[:8].upper()
        rc = bus.client()
        await rc.rpush("trop:public:reports", json.dumps({"id": rid, "report": r.model_dump(mode="json")}, ensure_ascii=False))
        if r.post and r.post.install_id:
            await rc.incr(f"trop:public:mine:{r.post.install_id}")
        iid = "INC-X" + rid[4:]
        doc = {"ad": {"advertiser": r.post.advertiser if r.post else None, "text": r.post.caption if r.post else None},
               "landing": {"entry_url": (r.url or (r.post.cta_url if r.post else None))}, "source": {"type": "extension", "ref": rid}}
        await bus.publish(rc, "events", Event(type="extension.report", at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                               data={"incident_id": iid}))
        return M.PublicReportAck(report_id=rid)

    def public_schemes(self, window: str):
        out = []
        for cid in self.corpus.campaigns:
            mem = self._members(cid)
            seen = sorted(str((i.get("source") or {}).get("captured_at") or "")[:10] for i in mem if (i.get("source") or {}).get("captured_at"))
            vert = (self.corpus.campaigns[cid].get("vertical") or "").split(" ")[0]
            out.append(M.PublicScheme(name=self.PUBLIC_NAME.get(vert, "Znana kampania oszustwa reklamowego"), seen_count=len(mem),
                                      since=seen[0] if seen else "2026", reasons=["ta sama sieć reklam i przekierowań"]))
        agg: dict[str, M.PublicScheme] = {}
        for x in out:                                   # public names merge campaigns of the same kind
            if x.name in agg:
                agg[x.name].seen_count += x.seen_count
            else:
                agg[x.name] = x
        return list(agg.values())

    async def public_reports_mine(self):
        n = await bus.client().llen("trop:public:reports")
        return M.ReportsMine(submitted=int(n), matched=0)

    # ------------------------------------------------------------------------------------------ lab (from `trop eval`)
    async def _eval_json(self, name: str, *args: str) -> dict:
        """cache_dir/<name>.json written by `trop eval <args> --json`; computed once when missing (cache dir must be writable then)."""
        path = Path(settings.cache_dir) / f"{name}.json"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            proc = await asyncio.create_subprocess_exec(sys.executable, "-m", "trop.cli", "eval", *args, "--json", str(path),
                                                        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            try:
                await asyncio.wait_for(proc.wait(), 300)
            except asyncio.TimeoutError:
                proc.kill()
                raise HTTPException(504, "eval did not finish in time")
        try:
            res = json.loads(path.read_text())
        except (OSError, ValueError):
            raise HTTPException(503, f"{name}.json unavailable")
        return res.get("precomputed") or next(iter(res.values()))

    async def _lab_all(self) -> dict:
        pre = await self._eval_json("lab_eval")
        dane = await self._eval_json("lab_eval_dane", "--dane")
        abl = await self._eval_json("lab_eval_ablation", "--ablation")
        return {"sample": pre, "dane": dane, "ablation": abl.get("ablation") or []}

    async def lab_metrics(self, view: str) -> LabMetrics:
        if view not in ("summary", "baselines", "loco", "conformal", "models", "layer_compare"):
            raise HTTPException(404, f"unknown view {view}")
        a = await self._lab_all()
        pre, dane, abl = a["sample"], a["dane"], a["ablation"]
        t5, lo = pre.get("avglink_tau5") or {}, pre.get("loco") or {}
        osr = dane.get("open_set") or {}
        rows = osr.get("rows") or []
        new_rows = [r for r in rows if r.get("expected") == "new"]
        wrong = int(osr.get("wrong_links") or 0) + int(lo.get("wrong_assign") or 0) + sum(int(v.get("wrong_assign") or 0) for v in (pre.get("robustness") or {}).values())
        drop_infra = next((r for r in abl if r.get("setting") == "drop infra"), None)
        summary = {
            "source": "trop eval", "n": pre.get("n"), "bcubed_f1": t5.get("b3_F1"), "ari": t5.get("ARI"), "pairwise_precision": t5.get("pair_P"),
            "pair_auc": pre.get("pair_auc"), "open_set_accuracy": (osr["correct"] / osr["n"]) if osr.get("n") else None,
            "dane_open_set": {"correct": osr.get("correct"), "n": osr.get("n"), "wrong_links": osr.get("wrong_links")},
            "new_campaign_precision": (sum(1 for r in new_rows if r.get("assigned") == "new") / len(new_rows)) if new_rows else None,
            "wrong_links": wrong, "loco_link": lo.get("should_link_acc"), "loco_not_link": lo.get("should_not_link_acc"),
            "operator_f1": ((pre.get("operator_avglink") or [{}])[0]).get("b3_F1"),
            "m2_infra_blind_f1": drop_infra.get("b3_F1") if drop_infra else None, "gate_failures": pre.get("gate_failures"),
            "raw": {"sample": pre, "dane": dane, "ablation": abl},
        }
        mk = lambda name, d: {"model": name, "bcubed_f1": (d or {}).get("b3_F1")}  # noqa: E731
        views = {
            "summary": summary,
            "baselines": {"source": "trop eval", "rows": [r for r in (mk("TROP: średnie wiązanie (τ=5)", t5), mk("Składowe spójne (τ=5)", pre.get("components_tau5")),
                                                                      mk("Louvain (τ=5)", pre.get("louvain_tau5"))) if r["bcubed_f1"] is not None],
                          "avglink_grid": pre.get("avglink_grid")},
            "loco": {"source": "trop eval", "loco": lo, "misses": pre.get("loco_misses"), "robustness": pre.get("robustness")},
        }
        return LabMetrics(view=view, model_version="engine@1", data=views.get(view, {"available": False, "note": "not computed by trop eval"}))

    async def lab_ablation(self) -> list[dict]:
        abl = (await self._lab_all())["ablation"]
        return [{"layer": r["setting"].split(" ", 1)[1], "delta_f1": round(r["b3_F1"] - 1.0, 3), "b3_F1": r["b3_F1"], "ari": r.get("ARI"), "pair_auc": r.get("pair_auc"),
                 "loco_link": r.get("loco_link"), "wrong": r.get("wrong")} for r in abl if r["setting"].startswith("drop ")]
