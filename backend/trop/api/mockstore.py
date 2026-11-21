"""Mock-mode data layer: serves the fictional universe from the JSON fixtures in trop/api/mock/ (validated on load).

Same method surface as `RealStore` (realstore.py); routes only talk to the store.
"""
from __future__ import annotations

import csv
import io
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from trop.api import models as M
from trop.api import sequences as S
from trop.api.mock import universe as U
from trop.schema import (
    ActPackage, ActPackageCreate, AnalyzeAccepted, BatchResult, BatchRow, Campaign, CampaignDNA, CampaignSummary, CheckResult,
    Decision, EvidenceValue, ExtensionMatch, ExtensionPost, GraphPayload, HunterRun, HunterSource, IncidentSummary, Indicators,
    Investigation, InvestigationCreate, InvestigationStep, Job, JobInput, LabMetrics, LinkExplanation, MergePreview, Member,
    Operation, Operator, OracleMetrics, OraclePrediction, DomainDNA, PublicCampaign, PublicReport, Rule, RuleTest, SearchHit,
    StatsOverview, TemplateDiff, Timeline, TriageDecision, TriageItem, Variant,
)

DIR = Path(__file__).parent / "mock"
NEW_HINTS = ("bon", "energ", "kmp-040", "new")


def _j(name: str) -> Any:
    return json.loads((DIR / f"{name}.json").read_text(encoding="utf-8"))["data"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _nf(what: str) -> HTTPException:
    return HTTPException(404, f"{what} not found")


class MockStore:
    mode = "mock"

    def __init__(self) -> None:
        self.campaigns_ = [Campaign.model_validate(c) for c in _j("campaigns")]
        self.dna_ = {k: CampaignDNA.model_validate(v) for k, v in _j("dna").items()}
        self.timeline_ = {k: Timeline.model_validate(v) for k, v in _j("timeline").items()}
        self.members_ = {k: [Member.model_validate(m) for m in v] for k, v in _j("members").items()}
        self.indicators_ = {k: Indicators.model_validate(v) for k, v in _j("indicators").items()}
        self.variants_ = {k: [Variant.model_validate(m) for m in v] for k, v in _j("variants").items()}
        extra = _j("campaign_extra")
        self.phylo_, self.summary_ = extra["phylogeny"], extra["summary"]
        self.inc_sum = [IncidentSummary.model_validate(s) for s in _j("incident_summaries")]
        self.inc_det: dict[str, dict] = _j("incident_details")
        self.decisions_ = {k: Decision.model_validate(v) for k, v in _j("decisions").items()}
        links = _j("links")
        self.link_k17 = LinkExplanation.model_validate(links["explain_kmp017"])
        self.link_k34 = LinkExplanation.model_validate(links["explain_kmp034"])
        self.diff_ = TemplateDiff.model_validate(links["diff"])
        self.operators_ = [Operator.model_validate(o) for o in _j("operators")]
        self.operations_ = [Operation.model_validate(o) for o in _j("operations")]
        self.merge_prev = MergePreview.model_validate(_j("merge_preview"))
        self.graph_ = GraphPayload.model_validate(_j("graph"))
        self.invs = {i["id"]: Investigation.model_validate(i) for i in _j("investigations")}
        o = _j("oracle")
        self.preds = [OraclePrediction.model_validate(p) for p in o["predictions"]]
        self.odna = [DomainDNA.model_validate(p) for p in o["dna"]]
        self.ometrics = OracleMetrics.model_validate(o["metrics"])
        a = _j("act")
        self.packages = {p["id"]: ActPackage.model_validate(p) for p in a["packages"]}
        self.rules = [Rule.model_validate(r) for r in a["rules"]]
        self.rule_test = RuleTest.model_validate(a["rule_test"])
        self.triage_ = {t["id"]: TriageItem.model_validate(t) for t in _j("triage")}
        h = _j("hunter")
        self.sources = {s["id"]: HunterSource.model_validate(s) for s in h["sources"]}
        self.runs = [HunterRun.model_validate(r) for r in h["runs"]]
        lab = _j("lab")
        self.lab_views, self.ablation_ = lab["views"], lab["ablation"]
        misc = _j("misc")
        self.persons_, self.brands_, self.alerts_, self.stats_ = misc["persons"], misc["brands"], misc["alerts"], misc["stats"]
        self.jobs: dict[str, dict] = {}
        self.invruns: dict[str, dict] = {}
        self.batches: dict[str, BatchResult] = {}
        self.feedback: list[dict] = []
        self.stress: dict[str, dict] = {}
        self.pkg_seq, self.inv_seq, self.reports = 8, 4, 0
        self.merged: dict[str, str] = {}

    # ---------------------------------------------------------------------------------------------- dashboard
    def health_counts(self) -> dict[str, int]:
        return {"incidents": 1284, "campaigns_active": 41, "operators": 6, "triage_open": sum(1 for t in self.triage_.values() if t.status == "open")}

    def overview(self, window: str) -> StatsOverview:
        d = dict(self.stats_["night" if window == "night" else "24h"])
        d["triage_open"] = self.health_counts()["triage_open"]
        return StatsOverview.model_validate(d)

    def alerts(self, status: str | None) -> list[M.Alert]:
        return [M.Alert.model_validate(a) for a in self.alerts_ if not status or a["status"] == status]

    def search(self, q: str) -> list[SearchHit]:
        ql, out = q.lower().strip(), []
        if not ql:
            return out
        for c in self.campaigns_:
            if ql in c.id.lower() or ql in c.name.lower():
                out.append(SearchHit(kind="campaign", id=c.id, label=c.name, href=f"/kampanie/{c.id}"))
        for o in self.operators_:
            if ql in o.id.lower() or ql in o.codename.lower():
                out.append(SearchHit(kind="operator", id=o.id, label=f"{o.id} «{o.codename}»", href=f"/operatorzy/{o.id}"))
        seen = set()
        for s in self.inc_sum:
            if ql in s.id.lower() or (s.domain and ql in s.domain.lower()):
                out.append(SearchHit(kind="incident", id=s.id, label=f"{s.id} · {s.domain}", href=f"/incydenty/{s.id}"))
            if s.domain and ql in s.domain.lower() and s.domain not in seen:
                seen.add(s.domain)
                out.append(SearchHit(kind="domain", id=s.domain, label=s.domain, href=f"/slad/domain/{s.domain}"))
            if len(out) > 40:
                break
        for p in self.persons_:
            if ql in p["name"].lower():
                out.append(SearchHit(kind="person", id=p["id"], label=p["name"], href=f"/osoby/{p['id']}"))
        for v in (U.CAPI, "870011223344556", "AW-11122233344"):
            if ql in v.lower():
                out.append(SearchHit(kind="tracking", id=v, label=v, href=f"/slad/tracking/{v}"))
        return out[:40]

    # ---------------------------------------------------------------------------------------------- jobs
    def analyze(self, kind: str, name: str, saved: list[str] | None = None) -> M.AnalyzeResponse:
        if kind == "trace":
            return M.AnalyzeResponse(job_id=None)
        jid = "JOB-" + uuid.uuid4().hex[:12].upper()
        scenario = "new" if any(h in name.lower() for h in NEW_HINTS) else "known"
        base = datetime.now(timezone.utc)
        seq = S.job_sequence(jid, scenario, base)
        self.jobs[jid] = {"input": JobInput(kind=kind if kind in ("url", "file", "zip", "folder", "batch") else "file", name=name), "seq": seq,
                          "t0": time.monotonic(), "scenario": scenario}
        return M.AnalyzeResponse(job_id=jid, incident_id="INC-24817" if scenario == "known" else "INC-24901")

    def _elapsed(self, j: dict) -> float:
        from trop.api.streams import speed
        return (time.monotonic() - j["t0"]) * speed()

    def job(self, jid: str) -> Job:
        j = self.jobs.get(jid)
        if not j:
            if jid.startswith("JOB-DEMO"):
                seq = S.job_sequence(jid, "known")
                return S.fold_job(jid, JobInput(kind="url", name="https://morvanta.click/"), seq, 99)
            raise _nf("job")
        return S.fold_job(jid, j["input"], j["seq"], self._elapsed(j))

    def jobs_list(self, limit: int) -> list[Job]:
        done = S.fold_job("JOB-DEMO-0", JobInput(kind="url", name="https://morvanta.click/"), S.job_sequence("JOB-DEMO-0", "known"), 99)
        return ([self.job(k) for k in reversed(list(self.jobs))] + [done])[:limit]

    def job_stream(self, jid: str) -> tuple[S.Seq, float]:
        j = self.jobs.get(jid)
        if not j:
            if jid.startswith("JOB-DEMO"):
                return S.job_sequence(jid, "known"), 0.0
            raise _nf("job")
        return j["seq"], self._elapsed(j)

    # ---------------------------------------------------------------------------------------------- incidents
    def incidents(self, campaign_id=None, source=None, q=None, frm=None, to=None, limit=50, cursor=None) -> tuple[list[IncidentSummary], str | None]:
        rows = [s for s in self.inc_sum if (not campaign_id or s.campaign_id == campaign_id) and (not source or s.source == source)
                and (not q or q.lower() in f"{s.id} {s.domain} {s.title}".lower())
                and (not frm or (s.captured_at or "") >= frm) and (not to or (s.captured_at or "") <= to)]
        i = int(cursor or 0)
        nxt = str(i + limit) if i + limit < len(rows) else None
        return rows[i:i + limit], nxt

    def _summary(self, iid: str) -> IncidentSummary:
        for s in self.inc_sum:
            if s.id == iid:
                return s
        raise _nf("incident")

    def incident(self, iid: str) -> M.IncidentDetail:
        d = self.inc_det.get(iid)
        if not d:
            raise _nf("incident")
        return M.IncidentDetail.model_validate(d)

    def artifacts(self, iid: str) -> list[M.Artifact]:
        self._summary(iid)
        return [M.Artifact(kind="screenshot", name="ad.png", url=f"/api/v1/mock/asset/{iid}-ad.svg", size=48211, mime="image/svg+xml"),
                M.Artifact(kind="screenshot", name="landing.png", url=f"/api/v1/mock/asset/{iid}-landing.svg", size=212004, mime="image/svg+xml"),
                M.Artifact(kind="har", name="capture.har", url=f"/api/v1/mock/asset/{iid}.har", size=1840211, mime="application/json"),
                M.Artifact(kind="html", name="dom.html", url=f"/api/v1/mock/asset/{iid}-dom.html", size=60112, mime="text/html")]

    def features(self, iid: str) -> list[M.FeatureGroup]:
        d = self.decision(iid)
        groups: dict[str, list[M.FeatureRow]] = {}
        for e in d.evidence:
            if e.state in ("match", "zero"):
                groups.setdefault(e.type, []).append(M.FeatureRow(field=e.field, value=e.value, df=e.df, N=e.N, idf=e.idf))
        return [M.FeatureGroup(layer=k, features=v) for k, v in groups.items()]

    def matches(self, iid: str, k: int, scope: str) -> list[M.Match]:
        d = self.decision(iid)
        out = [M.Match(kind="campaign", id=s.campaign_id, label=next((c.name for c in self.campaigns_ if c.id == s.campaign_id), s.campaign_id), score=s.score, p=s.p,
                       same_operator=s.score_operator >= 3, top_evidence=[e.display for e in d.evidence[:2]]) for s in d.scores]
        if scope == "incidents":
            mem = [m for m in self.members_.get(d.campaign_id or d.candidate_campaign_id or "", []) if m.incident_id != iid]
            out = [M.Match(kind="incident", id=m.incident_id, label=f"{m.incident_id} · {m.domain}", score=m.score, p=m.p, same_operator=True) for m in mem]
        return out[:k]

    def decision(self, iid: str) -> Decision:
        if iid in self.decisions_:
            return self.decisions_[iid]
        return U.generic_decision(self._summary(iid))

    def history(self, iid: str) -> list[M.HistoryEvent]:
        s = self._summary(iid)
        return [M.HistoryEvent(at=s.captured_at or _now(), kind="captured", text=f"Przechwycono ({s.source})"),
                M.HistoryEvent(at=s.captured_at or _now(), kind="attributed", text=f"Przypisano do {s.campaign_id} (p={s.p})"),
                M.HistoryEvent(at="2026-11-21T08:40:00+01:00", kind="viewed", text="Przegląd analityka", actor="analityk")]

    # ---------------------------------------------------------------------------------------------- links / evidence
    def link(self, a: str, b: str, view: str) -> LinkExplanation | TemplateDiff:
        if view == "diff":
            return self.diff_
        if b == "KMP-034":
            return self.link_k34.model_copy(update={"a": a, "b": b})
        if b == "KMP-017" or b.startswith("KMP"):
            if b not in {c.id for c in self.campaigns_}:
                raise _nf("campaign")
            if b not in ("KMP-017",):
                return self.link_k34.model_copy(update={"a": a, "b": b, "p": 0.18, "score_campaign": 1.2, "summary": f"Brak wystarczających dowodów wspólnych z {b}."})
            return self.link_k17.model_copy(update={"a": a, "b": b})
        ca, cb = self._camp_of(a), self._camp_of(b)
        if ca == cb:
            return self.link_k17.model_copy(update={"a": a, "b": b, "summary": f"{a} i {b} należą do {ca}: wspólne warstwy tracking, kit i treść."})
        return self.link_k34.model_copy(update={"a": a, "b": b, "summary": f"{a} ({ca}) i {b} ({cb}): ten sam operator, inne kampanie."})

    def _camp_of(self, iid: str) -> str | None:
        return self._summary(iid).campaign_id

    def evidence_value(self, type_: str, value: str) -> EvidenceValue:
        return U.evidence_value(type_, value)

    # ---------------------------------------------------------------------------------------------- campaigns
    def campaigns(self, sort: str | None, status: str | None) -> list[CampaignSummary]:
        rows = [c for c in self.campaigns_ if not status or c.status == status]
        if sort in ("-heat", "heat"):
            rows.sort(key=lambda c: c.heat.trend_pct, reverse=sort.startswith("-"))
        return [CampaignSummary.model_validate(c.model_dump(include=set(CampaignSummary.model_fields))) for c in rows]

    def campaign(self, cid: str) -> Campaign:
        cid = self.merged.get(cid, cid)
        for c in self.campaigns_:
            if c.id == cid:
                return c
        raise _nf("campaign")

    def dna(self, cid: str) -> CampaignDNA:
        self.campaign(cid)
        return self.dna_.get(cid) or CampaignDNA(campaign_id=cid, signature=[])

    def timeline(self, cid: str) -> Timeline:
        self.campaign(cid)
        return self.timeline_[cid]

    def members(self, cid: str, level=None, sort=None, coverage_lt=None, limit=100, cursor=None) -> tuple[list[Member], str | None]:
        self.campaign(cid)
        rows = [m for m in self.members_.get(cid, []) if (not level or m.level == level)]
        if coverage_lt is not None:
            rows = [m for m in rows if sum(1 for l in m.layers if l.state == "available") / 8 < coverage_lt]
        if sort == "score":
            rows.sort(key=lambda m: m.score, reverse=True)
        i = int(cursor or 0)
        return rows[i:i + limit], (str(i + limit) if i + limit < len(rows) else None)

    def indicators(self, cid: str, type_: str | None) -> Indicators:
        self.campaign(cid)
        ind = self.indicators_[cid]
        return ind

    def variants(self, cid: str) -> list[Variant]:
        self.campaign(cid)
        return self.variants_[cid]

    def phylogeny(self, cid: str) -> M.Phylogeny:
        self.campaign(cid)
        return M.Phylogeny.model_validate(self.phylo_[cid])

    def summary(self, cid: str) -> M.CampaignSummaryText:
        self.campaign(cid)
        return M.CampaignSummaryText.model_validate(self.summary_[cid])

    def create_campaign(self, body: M.CampaignCreate) -> Campaign:
        n = 41 + len([c for c in self.campaigns_ if c.id.startswith("KMP-9")])
        c = Campaign(id=f"KMP-9{n - 40:02d}", name=body.name, status="candidate", n_incidents=1, description="Nowy kandydat kampanii.")
        self.campaigns_.append(c)
        self.dna_[c.id], self.timeline_[c.id] = CampaignDNA(campaign_id=c.id, signature=[]), Timeline(days=[], events=[])
        self.members_[c.id], self.indicators_[c.id], self.variants_[c.id] = [], Indicators(), []
        self.phylo_[c.id] = {"campaign_id": c.id, "nodes": [], "edges": []}
        self.summary_[c.id] = {"campaign_id": c.id, "text": c.name, "bullets": [], "generated_by": "mock"}
        return c

    def merge_preview(self, cid: str, other: str) -> MergePreview:
        a, b = self.campaign(cid), self.campaign(other)
        return MergePreview(a=CampaignSummary.model_validate(a.model_dump(include=set(CampaignSummary.model_fields))),
                            b=CampaignSummary.model_validate(b.model_dump(include=set(CampaignSummary.model_fields))), shared=self.merge_prev.shared,
                            before={a.id: a.n_incidents, b.id: b.n_incidents}, after={a.id: a.n_incidents + b.n_incidents}, undo_token="UNDO-" + uuid.uuid4().hex[:6])

    def merge(self, cid: str, other: str, keep: str) -> Campaign:
        a, b = self.campaign(cid), self.campaign(other)
        keep_c, drop = (a, b) if keep == "self" else (b, a)
        keep_c.n_incidents += drop.n_incidents
        keep_c.counts.incidents += drop.n_incidents
        keep_c.merge_hint = None
        self.campaigns_ = [c for c in self.campaigns_ if c.id != drop.id]
        self.merged[drop.id] = keep_c.id
        return keep_c

    def split(self, cid: str, body: M.SplitRequest) -> Campaign:
        src = self.campaign(cid)
        new = self.create_campaign(M.CampaignCreate(seed_incident=body.incident_ids[0], name=body.name or f"Wydzielone z {cid}"))
        new.n_incidents = len(body.incident_ids)
        src.n_incidents = max(0, src.n_incidents - len(body.incident_ids))
        return new

    def operator(self, oid: str) -> Operator:
        for o in self.operators_:
            if o.id == oid:
                return o
        raise _nf("operator")

    def operations(self) -> list[Operation]:
        return self.operations_

    def operation(self, oid: str) -> Operation:
        for o in self.operations_:
            if o.id == oid:
                return o
        raise _nf("operation")

    def graph(self, scope=None, layers=None, level=None, min_weight=0.0, focus=None) -> GraphPayload:
        g = self.graph_.model_copy(deep=True)
        if layers:
            ls = set(layers.split(","))
            g.edges = [e for e in g.edges if e.type in ls or e.type in ("member", "operator", "operation")]
        g.edges = [e for e in g.edges if e.weight >= min_weight]
        if scope and scope.startswith("campaign:"):
            cid = scope.split(":", 1)[1]
            keep = {n.id for n in g.nodes if n.campaign_id == cid or n.id == cid}
            ids = keep | {e.a for e in g.edges if e.b in keep} | {e.b for e in g.edges if e.a in keep}
            g.nodes = [n for n in g.nodes if n.id in ids]
        ids = {n.id for n in g.nodes}
        g.edges = [e for e in g.edges if e.a in ids and e.b in ids]
        g.hulls = [h for h in g.hulls if any(m in ids for m in h["members"])]
        if focus:
            n = next((n for n in g.nodes if n.id == focus), None)
            if not n:
                raise _nf("node")
            deg = sum(1 for e in g.edges if focus in (e.a, e.b))
            g.focus = focus
            g.panel = {"title": n.label, "kind": n.kind, "facts": [f"Połączenia: {deg}", f"Kampania: {n.campaign_id or '—'}", f"Pierwszy raz: {n.first_seen or '—'}"],
                       "bot_sentence": f"Tropiciel: {n.label} łączy się z {deg} innymi węzłami w tym widoku.",
                       "primary_action": {"label": "Otwórz szczegóły", "href": f"/slad/{n.kind}/{n.id}"}}
        return g

    # ---------------------------------------------------------------------------------------------- investigations
    def investigations(self, status: str | None) -> list[Investigation]:
        rows = [self.investigation(i) for i in list(self.invs) + list(self.invruns)]
        return [r for r in rows if not status or r.status == status]

    def create_investigation(self, body: InvestigationCreate) -> dict:
        iid = f"INV-{self.inv_seq}"
        self.inv_seq += 1
        seq = S.investigation_sequence(iid)
        self.invruns[iid] = {"seed": body.seed, "campaign_id": body.campaign_id, "seq": seq, "t0": time.monotonic()}
        return {"id": iid}

    def investigation(self, iid: str) -> Investigation:
        if iid in self.invs:
            return self.invs[iid]
        r = self.invruns.get(iid)
        if r:
            inv = S.fold_investigation(iid, r["seed"], r["seq"], self._elapsed(r), self.invs["INV-3"])
            inv.campaign_id = r["campaign_id"] or inv.campaign_id
            return inv
        raise _nf("investigation")

    def investigation_stream(self, iid: str) -> tuple[S.Seq, float]:
        if iid in self.invruns:
            r = self.invruns[iid]
            return r["seq"], self._elapsed(r)
        if iid in self.invs:
            return S.investigation_sequence(iid), 0.0
        raise _nf("investigation")

    def steer(self, iid: str, body: M.SteerRequest) -> M.Ack:
        self.investigation(iid)
        return M.Ack(detail="Wskazówka przyjęta (mock): agent uwzględni ją w następnym kroku.")

    def stop(self, iid: str) -> M.Ack:
        self.investigation(iid)
        if iid in self.invruns:
            self.invruns[iid]["seq"] = [x for x in self.invruns[iid]["seq"] if x[0] <= self._elapsed(self.invruns[iid])]
        return M.Ack(detail="Śledztwo zatrzymane.")

    def promote(self, iid: str, campaign_id: str, node_ids: list[str]) -> M.PromoteResult:
        self.investigation(iid)
        self.campaign(campaign_id)
        return M.PromoteResult(campaign_id=campaign_id, added=len(node_ids))

    # ---------------------------------------------------------------------------------------------- oracle
    def predictions(self, status: str | None) -> list[OraclePrediction]:
        return [p for p in self.preds if not status or p.status == status]

    def oracle_dna(self, campaign: str | None) -> DomainDNA:
        for d in self.odna:
            if d.campaign_id == (campaign or "KMP-017"):
                return d
        raise _nf("domain DNA")

    def oracle_dna_patch(self, cid: str, threshold: float) -> DomainDNA:
        d = self.oracle_dna(cid)
        d.threshold = threshold
        return d

    def oracle_metrics(self) -> OracleMetrics:
        return self.ometrics

    # ---------------------------------------------------------------------------------------------- persons
    def persons(self, window: str, fmt: str | None) -> list[M.PersonSummary]:
        return [M.PersonSummary.model_validate({k: v for k, v in p.items() if k in M.PersonSummary.model_fields}) for p in self.persons_]

    def persons_brief(self, window: str) -> str:
        lines = [f"# Raport tygodniowy — osoby (okno {window})", ""] + [f"- **{p['name']}** ({p['role']}): {p['count']} reklam, trend {p['trend_pct']:+.0f}%" for p in self.persons_]
        return "\n".join(lines) + "\n"

    def person(self, pid: str) -> M.Person:
        for p in self.persons_:
            if p["id"] == pid:
                return M.Person.model_validate(p)
        raise _nf("person")

    def brands(self, window: str) -> list[M.Brand]:
        return [M.Brand.model_validate(b) for b in self.brands_]

    # ---------------------------------------------------------------------------------------------- act
    def act_packages(self) -> list[ActPackage]:
        return list(self.packages.values())

    def act_package(self, pid: str) -> ActPackage:
        if pid not in self.packages:
            raise _nf("package")
        return self.packages[pid]

    def act_create(self, body: ActPackageCreate) -> ActPackage:
        camp = self.campaign(body.campaign_id)
        base = self.packages["ACT-7"]
        p = base.model_copy(deep=True, update={"id": f"ACT-{self.pkg_seq}", "kind": body.kind, "campaign_id": camp.id, "status": "draft", "created_at": _now(),
                                               "contents": {"ads": camp.n_incidents, "advertisers": camp.counts.advertisers, "domains": camp.n_domains, "evidence_items": camp.n_incidents + 18},
                                               "recipients": [r for r in base.recipients if r["id"] in body.recipients]})
        self.pkg_seq += 1
        self.packages[p.id] = p
        return p

    def act_submit(self, pid: str) -> ActPackage:
        p = self.act_package(pid)
        p.status, p.sent_at = "sent", _now()  # "sent" = prepared + exported + logged; nothing leaves the system
        return p

    def act_download(self, pid: str, fmt: str) -> tuple[bytes, str, str]:
        p = self.act_package(pid)
        camp = self.campaign(p.campaign_id)
        doms = [d.fqdn for d in self.indicators_.get(camp.id, Indicators()).domains]
        if fmt == "json":
            return json.dumps(p.model_dump(mode="json"), ensure_ascii=False, indent=1).encode(), "application/json", f"{pid}.json"
        if fmt == "csv":
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["fqdn", "campaign", "operator"])
            [w.writerow([d, camp.id, camp.operator_id or ""]) for d in doms]
            return buf.getvalue().encode(), "text/csv", f"{pid}.csv"
        if fmt in ("stix", "misp"):
            objs = [{"type": "indicator", "spec_version": "2.1", "id": f"indicator--{uuid.uuid5(uuid.NAMESPACE_DNS, d)}", "name": d, "pattern": f"[domain-name:value = '{d}']", "pattern_type": "stix"} for d in doms]
            body = {"type": "bundle", "id": f"bundle--{uuid.uuid5(uuid.NAMESPACE_DNS, pid)}", "objects": objs} if fmt == "stix" else {"Event": {"info": f"{camp.id} {camp.name}", "Attribute": [{"type": "domain", "value": d} for d in doms]}}
            return json.dumps(body, ensure_ascii=False, indent=1).encode(), "application/json", f"{pid}.{fmt}.json"
        txt = f"({p.notice_text[:80]})".replace("(", "[").replace(")", "]")
        pdf = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
               b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 100]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n% " + txt.encode("ascii", "replace"))
        return pdf, "application/pdf", f"{pid}.pdf"

    def act_rules(self, campaign: str | None) -> list[Rule]:
        return [r for r in self.rules if not campaign or r.campaign_id == campaign]

    def act_rule_test(self, body: M.RuleTestRequest) -> RuleTest:
        return self.rule_test

    # ---------------------------------------------------------------------------------------------- triage / feedback
    def triage(self, status, type_, sort) -> M.TriageList:
        rows = list(self.triage_.values())
        facets = {"type": {}, "status": {}}
        for t in rows:
            facets["type"][t.type] = facets["type"].get(t.type, 0) + 1
            facets["status"][t.status] = facets["status"].get(t.status, 0) + 1
        rows = [t for t in rows if (not status or t.status == status) and (not type_ or t.type == type_)]
        key = {"priority": lambda t: -t.priority, "age": lambda t: t.created_at, "coverage": lambda t: t.score}.get(sort or "priority", lambda t: -t.priority)
        rows.sort(key=key)
        return M.TriageList(items=[t.model_dump(mode="json", by_alias=True) for t in rows], facets=facets)

    def triage_item(self, tid: str) -> TriageItem:
        if tid not in self.triage_:
            raise _nf("triage item")
        return self.triage_[tid]

    def triage_create(self, body: M.TriageCreate) -> TriageItem:
        n = len(self.triage_) + 1
        subj = body.subject_id or body.prediction_id or "INC-24817"
        t = TriageItem(id=f"TRI-{n}", type="oracle" if body.source == "prediction" else "uncertain", subject_id=subj, suggestion=f"Ręcznie dodane do triage: {subj}", priority=55, created_at=_now())
        self.triage_[t.id] = t
        return t

    def triage_decide(self, tid: str, d: TriageDecision, if_match: str | None) -> M.TriageDecided:
        t = self.triage_item(tid)
        if if_match is not None and str(if_match).strip('"') != str(t.version):
            raise HTTPException(409, f"stale version (current {t.version})")
        t.status, t.version = "closed", t.version + 1
        fid = "FB-" + uuid.uuid4().hex[:8]
        self.feedback.append({"id": fid, "item": tid, "action": d.action, "campaign_id": d.campaign_id})
        return M.TriageDecided(item=t.model_dump(mode="json", by_alias=True), feedback_id=fid)

    def feedback_add(self, fb: M.FeedbackIn) -> M.Ack:
        self.feedback.append(fb.model_dump())
        return M.Ack(detail="Dziękujemy — informacja zwrotna zapisana.")

    def feedback_stats(self, window: str) -> M.FeedbackStats:
        acts = [f.get("action") for f in self.feedback]
        return M.FeedbackStats(window=window, n=len(self.feedback) + 41, accepted=acts.count("accept") + 30, reassigned=acts.count("reassign") + 6, rejected=acts.count("reject") + 5, model_version="engine@mock")

    # ---------------------------------------------------------------------------------------------- lab
    def lab_metrics(self, view: str) -> LabMetrics:
        if view not in self.lab_views:
            raise HTTPException(404, f"unknown view {view}")
        return LabMetrics(view=view, model_version="engine@mock", data=self.lab_views[view])

    def lab_ablation(self) -> list[dict]:
        return self.ablation_

    def lab_stress(self, body: M.StressCreate) -> M.StressRun:
        rid = "RUN-" + uuid.uuid4().hex[:6]
        run = M.StressRun(run_id=rid, status="done", kind=body.kind, results={"sample": True, "note": "przykładowe wartości, podmienić z eval/", "wrong_links": 0, "cases": 120})
        self.stress[rid] = run.model_dump()
        return run

    def lab_run(self, rid: str) -> M.StressRun:
        if rid not in self.stress:
            raise _nf("run")
        return M.StressRun.model_validate(self.stress[rid])

    # ---------------------------------------------------------------------------------------------- hunter
    def hunter_sources(self) -> list[HunterSource]:
        return list(self.sources.values())

    def hunter_source_patch(self, sid: str, patch: M.HunterSourcePatch) -> HunterSource:
        s = self.sources.get(sid)
        if not s:
            raise _nf("source")
        for k, v in patch.model_dump(exclude_none=True).items():
            setattr(s, k, v)
        if patch.enabled is False:
            s.status = "disabled"
        return s

    def hunter_run(self, sid: str) -> M.RunStarted:
        if sid not in self.sources:
            raise _nf("source")
        rid = f"RUN-{902 + len(self.runs)}"
        self.runs.insert(0, HunterRun(id=rid, source_id=sid, started_at=_now(), status="running"))
        return M.RunStarted(run_id=rid)

    def hunter_runs(self, limit: int) -> list[HunterRun]:
        return self.runs[:limit]

    def hunter_policy(self) -> M.CapturePolicy:
        return M.CapturePolicy(notes=["Przechwytywanie tylko w piaskownicy.", "Nigdy nie wysyłamy formularzy ani nie logujemy się.", "Linki gclid/fbclid wyłącznie w piaskownicy."])

    def hunter_creds(self) -> list[M.CredStatus]:
        return [M.CredStatus(source_id=s.id, status=s.credentials_status) for s in self.sources.values()]

    # ---------------------------------------------------------------------------------------------- public
    def _public(self) -> PublicCampaign:
        return PublicCampaign(name="Fałszywy portal informacyjny z „inwestycją”", seen_count=46, since="2026-11-08",
                              reasons=["ta sama sieć reklam i przekierowań", "ten sam szablon artykułu", "ten sam wizerunek osoby"])

    def public_check(self, url: str | None, text: str | None) -> CheckResult:
        s = (url or text or "").lower()
        known = any(d[0] in s for d in U.KMP017_DOMAINS) or "kurier" in s or "napaśc" in s or "napasc" in s
        if known:
            return CheckResult(verdict="scam", public_campaign=self._public(), advice=["Nie klikaj w link i nie podawaj danych.", "Zgłoś reklamę platformie i na incydent.cert.pl."])
        return CheckResult(verdict="unknown", advice=["Brak dopasowania nie oznacza, że strona jest bezpieczna.", "Zachowaj ostrożność; możesz ją zgłosić."])

    def public_report(self, r: PublicReport) -> M.PublicReportAck:
        self.reports += 1
        return M.PublicReportAck(report_id=f"REP-{1000 + self.reports}")

    def public_match(self, p: ExtensionPost) -> ExtensionMatch:
        s = f"{p.advertiser or ''} {p.caption or ''} {p.cta_url or ''}".lower()
        if any(x in s for x in ("morvanta", "okazje-dnia", "przerywa milczenie", "kurier", "velmoria", "orvinta")):
            return ExtensionMatch(match=True, label="Pasuje do znanej kampanii oszustwa", public_campaign=self._public(), reasons=["ta sama ścieżka przekierowań", "ten sam szablon tekstu"])
        return ExtensionMatch(match=False)

    def public_schemes(self, window: str) -> list[M.PublicScheme]:
        return [M.PublicScheme(**self._public().model_dump()),
                M.PublicScheme(name="Fałszywy lekarz poleca suplement", seen_count=43, since="2026-10-14", reasons=["ten sam wizerunek", "ten sam sklep"])]

    def public_reports_mine(self) -> M.ReportsMine:
        return M.ReportsMine(submitted=self.reports, matched=self.reports // 2)

    # ---------------------------------------------------------------------------------------------- traces / batch
    def trace(self, type_: str, value: str) -> M.TraceView:
        ev = U.evidence_value(type_, value)
        latest = [s for s in self.inc_sum if s.campaign_id == "KMP-017"][:5]
        return M.TraceView(value=value, type=type_, campaigns=ev.campaigns, weekly=ev.weekly, latest=[s.model_dump(mode="json") for s in latest],
                           usage=[{"where": "reklamy", "count": ev.df // 2}, {"where": "strony docelowe", "count": ev.df - ev.df // 2}],
                           co_traces=[{"type": "tracking", "value": U.CAPI, "count": 41}, {"type": "kit", "value": U.KIT, "count": 40}])

    def batch(self, names: list[str]) -> M.BatchAccepted:
        jid = "JOB-B" + uuid.uuid4().hex[:10].upper()
        rows = []
        src = [m for cid in ("KMP-017", "KMP-034", "KMP-022", "KMP-031", "KMP-040") for m in self.members_[cid][:3]]
        for i, m in enumerate(src):
            cid = next(c for c, ms in self.members_.items() if m in ms)
            sp = U.SPEC[cid]
            rows.append(BatchRow(item=names[i] if i < len(names) else f"item_{i + 1:03d}", incident_id=m.incident_id, decision="new" if cid == "KMP-040" else "assign",
                                 campaign="NEW-001" if cid == "KMP-040" else cid, campaign_score=m.score, campaign_p=m.p, operator=sp["op"], operation=sp["opn"] or f"OPN-{cid[-3:]}",
                                 variant=m.variant_id, coverage=0.78, top_evidence="tracking:CAPI cg-7f3a(+3.1); kit:relay/lead(+2.7)"))
        self.batches[jid] = BatchResult(job_id=jid, n_items=len(rows), rows=rows, csv_url=f"/api/v1/batch/{jid}/results.csv", json_url=f"/api/v1/batch/{jid}")
        return M.BatchAccepted(job_id=jid)

    def batch_result(self, jid: str) -> BatchResult:
        if jid not in self.batches:
            raise _nf("batch")
        return self.batches[jid]

    def batch_csv(self, jid: str) -> str:
        r = self.batch_result(jid)
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(BatchRow.model_fields))
        w.writeheader()
        for row in r.rows:
            w.writerow(row.model_dump())
        return buf.getvalue()

    # ---------------------------------------------------------------------------------------------- live streams
    def events_sequence(self) -> S.Seq:
        return S.global_sequence()

    def oracle_sequence(self) -> S.Seq:
        return S.oracle_sequence()
