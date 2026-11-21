"""All /api/v1 routes (docs/design/README.md §7.1 + docs/CONTRACTS.md §4/§5). Routes only talk to the store."""
from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import PlainTextResponse

from trop.api import models as M
from trop.api import streams as ST
from trop.api.deps import current_mode, get_store
from trop.config import settings
from trop.schema import (
    ActPackage, ActPackageCreate, AnalyzeAccepted, BatchResult, Campaign, CampaignDNA, CampaignSummary, CheckResult, Decision,
    DomainDNA, EvidenceValue, ExtensionMatch, ExtensionPost, GraphPayload, HunterRun, HunterSource, IncidentSummary, Indicators,
    Investigation, InvestigationCreate, Job, LabMetrics, LinkExplanation, MergePreview, MergeRequest, Member, Operation, Operator,
    OracleMetrics, OraclePrediction, PromoteRequest, PublicReport, Rule, RuleTest, SearchHit, StatsOverview, TemplateDiff, Timeline,
    TriageDecision, TriageItem, Variant,
)

router = APIRouter()


async def _a(x: Any) -> Any:
    return await x if inspect.isawaitable(x) else x


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", Path(name).name)[:120] or "file"


# ============================================================================================== health / dashboard
@router.get("/health", response_model=M.Health, tags=["system"])
async def health() -> M.Health:
    s = get_store()
    db = redis = "n/a"
    if s.mode == "live":
        try:
            import psycopg
            with psycopg.connect(settings.database_url, connect_timeout=2) as c:
                c.execute("select 1")
            db = "ok"
        except Exception as e:  # noqa: BLE001
            db = f"down: {type(e).__name__}"
        try:
            from trop.worker import bus
            await bus.client().ping()
            redis = "ok"
        except Exception as e:  # noqa: BLE001
            redis = f"down: {type(e).__name__}"
    else:
        db = redis = "mock"
    return M.Health(ok=s.mode == "mock" or (db == "ok" and redis == "ok"), mode=current_mode() if s.mode != "mock" else "mock", db=db, redis=redis, version="0.1.0", counts=s.health_counts())


@router.get("/stats/overview", response_model=StatsOverview, tags=["dashboard"])
async def stats_overview(window: str = Query("24h", pattern="^(24h|night)$")):
    return await _a(get_store().overview(window))


@router.get("/alerts", response_model=list[M.Alert], tags=["dashboard"])
async def alerts(status: str | None = None):
    return await _a(get_store().alerts(status))


@router.get("/search", response_model=list[SearchHit], tags=["dashboard"])
async def search(q: str = ""):
    return await _a(get_store().search(q))


# ============================================================================================== analyze / jobs
@router.post("/analyze", response_model=M.AnalyzeResponse, tags=["jobs"])
async def analyze(url: str | None = Form(None), trace: str | None = Form(None), files: list[UploadFile] = File(default=[])):
    s = get_store()
    saved: list[str] = []
    if trace:
        return await _a(s.analyze("trace", trace, []))
    if not url and not files:
        raise HTTPException(422, "provide `url`, `files[]` or `trace`")
    if url:
        kind, name = "url", url
    else:
        folder = Path(settings.artifact_dir) / "uploads" / __import__("uuid").uuid4().hex[:12]
        folder.mkdir(parents=True, exist_ok=True)
        for f in files:
            p = folder / _safe(f.filename or "upload")
            p.write_bytes(await f.read())
            saved.append(str(p))
        names = [Path(p).name for p in saved]
        kind = "zip" if len(names) == 1 and names[0].lower().endswith(".zip") else "file" if len(names) == 1 else "folder"
        name = names[0] if len(names) == 1 else f"{len(names)} plików"
    return await _a(s.analyze(kind, name, saved))


@router.get("/jobs", response_model=list[Job], tags=["jobs"])
async def jobs(limit: int = 20):
    return await _a(get_store().jobs_list(limit))


@router.get("/jobs/{job_id}", response_model=Job, tags=["jobs"])
async def job(job_id: str):
    return await _a(get_store().job(job_id))


def _replay_or_none(replay: str | None, kind: str, jid: str | None, key: str) -> Any:
    if replay is None and settings.trop_replay:
        replay = "demo"
    if replay is None:
        return None
    p = ST.find_recording(replay, kind)
    if not p:
        raise HTTPException(404, f"no recording '{replay}' for {kind} (data/replay/{replay}-{kind}.jsonl)")
    return ST.response(ST.play(ST.load_recording(p), rewrite={key: jid} if jid else None))


@router.get("/jobs/{job_id}/stream", tags=["sse"], summary="SSE: the six-bot analysis (CONTRACTS §4.1)")
async def job_stream(job_id: str, replay: str | None = None):
    if (r := _replay_or_none(replay, "analyze", job_id, "job_id")):
        return r
    s = get_store()
    if s.mode == "mock":
        seq, start = s.job_stream(job_id)
        return ST.response(ST.play(seq, start_at=start))
    await _a(s.job(job_id))  # 404 for unknown ids
    return ST.response(_to_sse(s.job_events(job_id)))


async def _to_sse(events):
    async for ev in events:
        yield ST._sse(ev)


async def _loop(seq_factory, hold: bool = True):
    import asyncio
    while True:
        async for x in ST.play(seq_factory()):
            yield x
        await asyncio.sleep(1.0 / ST.speed())


@router.get("/events", tags=["sse"], summary="SSE: global event stream (CONTRACTS §4.2)")
async def events(replay: str | None = None):
    if (r := _replay_or_none(replay, "events", None, "")):
        return r
    s = get_store()
    if s.mode == "mock":
        return ST.response(_loop(s.events_sequence))
    return ST.response(_to_sse(s.channel_events("events")))


@router.get("/oracle/stream", tags=["sse"], summary="SSE: oracle.match")
async def oracle_stream(replay: str | None = None):
    if (r := _replay_or_none(replay, "oracle", None, "")):
        return r
    s = get_store()
    if s.mode == "mock":
        return ST.response(_loop(s.oracle_sequence))
    return ST.response(_to_sse(s.channel_events("oracle")))


# ============================================================================================== incidents
@router.get("/incidents", response_model=list[IncidentSummary], tags=["incidents"])
async def incidents(response: Response, campaign_id: str | None = None, source: str | None = None, q: str | None = None,
                    from_: str | None = Query(None, alias="from"), to: str | None = None, cursor: str | None = None, limit: int = Query(50, le=500)):
    rows, nxt = await _a(get_store().incidents(campaign_id, source, q, from_, to, limit, cursor))
    if nxt:
        response.headers["X-Next-Cursor"] = nxt
    return rows


@router.get("/incidents/{incident_id}", response_model=M.IncidentDetail, tags=["incidents"])
async def incident(incident_id: str):
    return await _a(get_store().incident(incident_id))


@router.get("/incidents/{incident_id}/artifacts", response_model=list[M.Artifact], tags=["incidents"])
async def artifacts(incident_id: str):
    return await _a(get_store().artifacts(incident_id))


@router.get("/incidents/{incident_id}/features", response_model=list[M.FeatureGroup], tags=["incidents"])
async def features(incident_id: str):
    return await _a(get_store().features(incident_id))


@router.get("/incidents/{incident_id}/matches", response_model=list[M.Match], tags=["incidents"])
async def matches(incident_id: str, k: int = 5, scope: str = Query("campaigns", pattern="^(campaigns|incidents)$")):
    return await _a(get_store().matches(incident_id, k, scope))


@router.get("/incidents/{incident_id}/decision", response_model=Decision, tags=["incidents"])
async def decision(incident_id: str):
    return await _a(get_store().decision(incident_id))


@router.get("/incidents/{incident_id}/history", response_model=list[M.HistoryEvent], tags=["incidents"])
async def history(incident_id: str):
    return await _a(get_store().history(incident_id))


@router.get("/links/{a}/{b}", response_model=LinkExplanation | TemplateDiff, tags=["links"])
async def links(a: str, b: str, view: str = Query("explain", pattern="^(explain|diff)$"), adjudicate: int = 0, compact: int = 0):
    return await _a(get_store().link(a, b, view))


@router.get("/evidence/values/{type}/{value:path}", response_model=EvidenceValue, tags=["links"])
async def evidence_value(type: str, value: str):
    return await _a(get_store().evidence_value(type, value))


@router.get("/traces/{type}/{value:path}", response_model=M.TraceView, tags=["links"])
async def trace(type: str, value: str):
    return await _a(get_store().trace(type, value))


# ============================================================================================== campaigns / operators
@router.get("/campaigns", response_model=list[CampaignSummary], tags=["campaigns"])
async def campaigns(sort: str | None = None, status: str | None = None):
    return await _a(get_store().campaigns(sort, status))


@router.post("/campaigns", response_model=Campaign, status_code=201, tags=["campaigns"])
async def create_campaign(body: M.CampaignCreate):
    return await _a(get_store().create_campaign(body))


@router.get("/campaigns/{cid}", response_model=Campaign, tags=["campaigns"])
async def campaign(cid: str):
    return await _a(get_store().campaign(cid))


@router.get("/campaigns/{cid}/dna", response_model=CampaignDNA, tags=["campaigns"])
async def campaign_dna(cid: str):
    return await _a(get_store().dna(cid))


@router.get("/campaigns/{cid}/timeline", response_model=Timeline, tags=["campaigns"])
async def campaign_timeline(cid: str, range: str | None = None):
    return await _a(get_store().timeline(cid))


@router.get("/campaigns/{cid}/members", response_model=list[Member], tags=["campaigns"])
async def campaign_members(cid: str, response: Response, level: str | None = None, sort: str | None = None, coverage_lt: float | None = None,
                           cursor: str | None = None, limit: int = Query(100, le=500)):
    rows, nxt = await _a(get_store().members(cid, level, sort, coverage_lt, limit, cursor))
    if nxt:
        response.headers["X-Next-Cursor"] = nxt
    return rows


@router.get("/campaigns/{cid}/indicators", response_model=Indicators, tags=["campaigns"])
async def campaign_indicators(cid: str, type: str | None = None):
    return await _a(get_store().indicators(cid, type))


@router.get("/campaigns/{cid}/variants", response_model=list[Variant], tags=["campaigns"])
async def campaign_variants(cid: str):
    return await _a(get_store().variants(cid))


@router.get("/campaigns/{cid}/phylogeny", response_model=M.Phylogeny, tags=["campaigns"])
async def campaign_phylogeny(cid: str):
    return await _a(get_store().phylogeny(cid))


@router.get("/campaigns/{cid}/summary", response_model=M.CampaignSummaryText, tags=["campaigns"])
async def campaign_summary(cid: str):
    return await _a(get_store().summary(cid))


@router.get("/campaigns/{cid}/merge-preview", response_model=MergePreview, tags=["campaigns"])
async def merge_preview(cid: str, other: str):
    return await _a(get_store().merge_preview(cid, other))


@router.post("/campaigns/{cid}/merge", response_model=Campaign, tags=["campaigns"])
async def merge(cid: str, body: MergeRequest):
    return await _a(get_store().merge(cid, body.other_id, body.keep))


@router.post("/campaigns/{cid}/split", response_model=Campaign, tags=["campaigns"])
async def split(cid: str, body: M.SplitRequest):
    return await _a(get_store().split(cid, body))


@router.get("/operators/{oid}", response_model=Operator, tags=["campaigns"])
async def operator(oid: str):
    return await _a(get_store().operator(oid))


@router.get("/operations", response_model=list[Operation], tags=["campaigns"])
async def operations():
    return await _a(get_store().operations())


@router.get("/operations/{oid}", response_model=Operation, tags=["campaigns"])
async def operation(oid: str):
    return await _a(get_store().operation(oid))


@router.get("/graph", response_model=GraphPayload, tags=["graph"])
async def graph(scope: str | None = None, layers: str | None = None, level: str | None = None, min_weight: float = 0.0, focus: str | None = None,
                from_: str | None = Query(None, alias="from"), to: str | None = None, group: str | None = None):
    return await _a(get_store().graph(scope, layers, level, min_weight, focus))


# ============================================================================================== investigations (White Rabbit)
@router.get("/investigations", response_model=list[Investigation], tags=["investigations"])
async def investigations(status: str | None = None):
    return await _a(get_store().investigations(status))


@router.post("/investigations", status_code=201, tags=["investigations"])
async def create_investigation(body: InvestigationCreate) -> dict:
    return await _a(get_store().create_investigation(body))


@router.get("/investigations/{iid}", response_model=Investigation, tags=["investigations"])
async def investigation(iid: str):
    return await _a(get_store().investigation(iid))


@router.get("/investigations/{iid}/stream", tags=["sse"], summary="SSE: agent.step / graph.* / casefile.delta (CONTRACTS §4.3)")
async def investigation_stream(iid: str, replay: str | None = None):
    if (r := _replay_or_none(replay, "investigation", iid, "investigation_id")):
        return r
    s = get_store()
    if s.mode == "mock":
        seq, start = s.investigation_stream(iid)
        return ST.response(ST.play(seq, start_at=start))
    return ST.response(_to_sse(s.investigation_events(iid)))


@router.post("/investigations/{iid}/steer", response_model=M.Ack, tags=["investigations"])
async def steer(iid: str, body: M.SteerRequest):
    return await _a(get_store().steer(iid, body))


@router.post("/investigations/{iid}/stop", response_model=M.Ack, tags=["investigations"])
async def stop(iid: str):
    return await _a(get_store().stop(iid))


@router.post("/investigations/{iid}/promote", response_model=M.PromoteResult, tags=["investigations"])
async def promote(iid: str, body: PromoteRequest):
    return await _a(get_store().promote(iid, body.campaign_id, body.node_ids))


# ============================================================================================== oracle
@router.get("/oracle/metrics", response_model=OracleMetrics, tags=["oracle"])
async def oracle_metrics():
    return await _a(get_store().oracle_metrics())


@router.get("/oracle/dna", response_model=DomainDNA, tags=["oracle"])
async def oracle_dna(campaign: str | None = None):
    return await _a(get_store().oracle_dna(campaign))


@router.patch("/oracle/dna/{campaign_id}", response_model=DomainDNA, tags=["oracle"])
async def oracle_dna_patch(campaign_id: str, body: M.OracleDnaPatch):
    return await _a(get_store().oracle_dna_patch(campaign_id, body.threshold))


@router.get("/oracle/predictions", response_model=list[OraclePrediction], tags=["oracle"])
async def oracle_predictions(status: str | None = None):
    return await _a(get_store().predictions(status))


# ============================================================================================== persons
@router.get("/persons", response_model=list[M.PersonSummary], tags=["persons"])
async def persons(window: str = "7d", bucket: str = "week", format: str | None = None):
    s = get_store()
    if format == "brief":
        return PlainTextResponse(await _a(s.persons_brief(window)), media_type="text/markdown; charset=utf-8")
    return await _a(s.persons(window, format))


@router.get("/persons/{pid}", response_model=M.Person, tags=["persons"])
async def person(pid: str):
    return await _a(get_store().person(pid))


@router.get("/brands", response_model=list[M.Brand], tags=["persons"])
async def brands(window: str = "7d"):
    return await _a(get_store().brands(window))


# ============================================================================================== act
@router.get("/act/packages", response_model=list[ActPackage], tags=["act"])
async def act_packages():
    return await _a(get_store().act_packages())


@router.post("/act/packages", response_model=ActPackage, status_code=201, tags=["act"])
async def act_create(body: ActPackageCreate):
    return await _a(get_store().act_create(body))


@router.get("/act/packages/{pid}", response_model=ActPackage, tags=["act"])
async def act_package(pid: str):
    return await _a(get_store().act_package(pid))


@router.get("/act/packages/{pid}/download", tags=["act"], response_class=Response)
async def act_download(pid: str, format: str = Query("pdf", pattern="^(pdf|json|csv|stix|misp)$")):
    data, mime, name = await _a(get_store().act_download(pid, format))
    return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/act/packages/{pid}/submit", response_model=ActPackage, tags=["act"])
async def act_submit(pid: str, body: M.ActSubmit):
    if not body.confirm:
        raise HTTPException(422, "confirm must be true (two-step action; nothing is sent externally)")
    return await _a(get_store().act_submit(pid))


@router.get("/act/rules", response_model=list[Rule], tags=["act"])
async def act_rules(campaign: str | None = None):
    return await _a(get_store().act_rules(campaign))


@router.post("/act/rules/test", response_model=RuleTest, tags=["act"])
async def act_rules_test(body: M.RuleTestRequest):
    return await _a(get_store().act_rule_test(body))


# ============================================================================================== triage / feedback
@router.get("/triage", response_model=M.TriageList, tags=["triage"])
async def triage(status: str | None = None, type: str | None = None, sort: str = "priority"):
    return await _a(get_store().triage(status, type, sort))


@router.post("/triage", response_model=TriageItem, status_code=201, response_model_by_alias=True, tags=["triage"])
async def triage_create(body: M.TriageCreate):
    return await _a(get_store().triage_create(body))


@router.get("/triage/{tid}", response_model=TriageItem, response_model_by_alias=True, tags=["triage"])
async def triage_item(tid: str):
    return await _a(get_store().triage_item(tid))


@router.post("/triage/{tid}/decision", response_model=M.TriageDecided, tags=["triage"])
async def triage_decision(tid: str, body: TriageDecision, if_match: str | None = Header(None, alias="If-Match")):
    return await _a(get_store().triage_decide(tid, body, if_match))


@router.post("/feedback", response_model=M.Ack, tags=["triage"])
async def feedback(body: M.FeedbackIn):
    return await _a(get_store().feedback_add(body))


@router.get("/feedback/stats", response_model=M.FeedbackStats, tags=["triage"])
async def feedback_stats(window: str = "7d"):
    return await _a(get_store().feedback_stats(window))


# ============================================================================================== lab
@router.get("/lab/metrics", response_model=LabMetrics, tags=["lab"])
async def lab_metrics(view: str = "summary"):
    return await _a(get_store().lab_metrics(view))


@router.get("/lab/ablation", tags=["lab"])
async def lab_ablation() -> list[dict]:
    return await _a(get_store().lab_ablation())


@router.post("/lab/stress", response_model=M.StressRun, tags=["lab"])
async def lab_stress(body: M.StressCreate):
    return await _a(get_store().lab_stress(body))


@router.get("/lab/runs/{rid}", response_model=M.StressRun, tags=["lab"])
async def lab_run(rid: str):
    return await _a(get_store().lab_run(rid))


# ============================================================================================== hunter
@router.get("/hunter/sources", response_model=list[HunterSource] | list[M.CredStatus], tags=["hunter"])
async def hunter_sources(fields: str | None = None):
    s = get_store()
    if fields == "credentials_status":
        return await _a(s.hunter_creds())
    return await _a(s.hunter_sources())


@router.patch("/hunter/sources/{sid}", response_model=HunterSource, tags=["hunter"])
async def hunter_patch(sid: str, body: M.HunterSourcePatch):
    return await _a(get_store().hunter_source_patch(sid, body))


@router.post("/hunter/sources/{sid}/run", response_model=M.RunStarted, tags=["hunter"])
async def hunter_run(sid: str):
    return await _a(get_store().hunter_run(sid))


@router.get("/hunter/runs", response_model=list[HunterRun], tags=["hunter"])
async def hunter_runs(limit: int = 20):
    return await _a(get_store().hunter_runs(limit))


@router.get("/hunter/policy", response_model=M.CapturePolicy, tags=["hunter"])
async def hunter_policy():
    return await _a(get_store().hunter_policy())


# ============================================================================================== public (coarse, no internal ids)
@router.post("/public/check", response_model=CheckResult, tags=["public"])
async def public_check(url: str | None = Form(None), text: str | None = Form(None)):
    return await _a(get_store().public_check(url, text))


@router.post("/public/report", response_model=M.PublicReportAck, tags=["public"])
async def public_report(body: PublicReport):
    return await _a(get_store().public_report(body))


@router.post("/public/extension/match", response_model=ExtensionMatch, tags=["public"])
async def public_match(body: ExtensionPost):
    return await _a(get_store().public_match(body))


@router.get("/public/schemes", response_model=list[M.PublicScheme], tags=["public"])
async def public_schemes(window: str = "7d"):
    return await _a(get_store().public_schemes(window))


@router.get("/public/reports/mine", response_model=M.ReportsMine, tags=["public"])
async def public_reports_mine():
    return await _a(get_store().public_reports_mine())


# ============================================================================================== batch
@router.post("/batch", response_model=M.BatchAccepted, tags=["batch"])
async def batch_create(files: list[UploadFile] = File(default=[])):
    names = []
    folder = Path(settings.artifact_dir) / "uploads" / ("batch-" + __import__("uuid").uuid4().hex[:8])
    folder.mkdir(parents=True, exist_ok=True)
    for f in files:
        (folder / _safe(f.filename or "item")).write_bytes(await f.read())
        names.append(_safe(f.filename or "item"))
    # a single zip is handed to run_batch as is; several files -> the upload folder
    path = folder / names[0] if len(names) == 1 and names[0].lower().endswith(".zip") else folder
    return await _a(get_store().batch(names, str(path)))


@router.get("/batch/{job_id}", response_model=BatchResult, tags=["batch"])
async def batch_result(job_id: str):
    return await _a(get_store().batch_result(job_id))


@router.get("/batch/{job_id}/results.csv", tags=["batch"], response_class=PlainTextResponse)
async def batch_csv(job_id: str):
    return PlainTextResponse(await _a(get_store().batch_csv(job_id)), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": 'attachment; filename="results.csv"'})


# ============================================================================================== mock assets
@router.get("/mock/asset/{name}", include_in_schema=False)
async def mock_asset(name: str):
    if get_store().mode != "mock":
        raise HTTPException(404)
    label = _safe(name).rsplit(".", 1)[0]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="400" viewBox="0 0 640 400"><rect width="640" height="400" fill="#0b120e"/>'
           f'<rect x="24" y="24" width="592" height="40" fill="#16241b"/><rect x="24" y="84" width="592" height="170" fill="#1c3326"/>'
           f'<text x="32" y="50" fill="#9fe7b6" font-family="monospace" font-size="16">{label}</text>'
           f'<text x="32" y="300" fill="#6f8f7b" font-family="monospace" font-size="14">PRZYKŁADOWY MATERIAŁ (fikcyjny)</text></svg>')
    return Response(svg, media_type="image/svg+xml")
