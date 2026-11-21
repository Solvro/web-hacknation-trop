"""Canned event sequences for mock mode and the demo recordings.

A sequence is a list of (offset_seconds, Event). The same sequences feed (a) live mock SSE streams, (b) the recorded
`?replay=demo` files and (c) time-based job/investigation state (GET /jobs/{id} while the stream is still running).
Job sequence follows docs/CONTRACTS.md §4.1; investigation sequence §4.3.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from trop.schema import (
    BOT_STEPS, CampaignScore, Decision, EvidenceItem, Event, Finding, GraphEdge, GraphNode, GraphPayload, Investigation, Job,
    JobInput, JobStep,
)

MOCK_DIR = Path(__file__).parent / "mock"
Seq = list[tuple[float, Event]]

# (key, duration_ms, detail, warnings) -- adds up to 18.3 s + 1.3 s dispatch = 19.6 s (BRIEF.md pipeline)
STEP_PLAN = {
    # detail convention (WS3 req. 4): line 1 = summary shown in the strip, following lines = the bot's sentences
    "capture": (7000, "4 redirecty · HAR 212 żądań · DOM · TLS\nOtworzyłem stronę w piaskownicy z profilem Facebook (Android, PL).\nZapisałem HAR, DOM, zrzut ekranu i certyfikat TLS.", []),
    "tracking": (600, "bramka CAPI + kit relay/lead\nZnalazłem bramkę CAPI cg-7f3a… i ścieżkę /api/v2/relay/lead/{uuid}/.\nObie rzadkie: 47 i 58 z 1 284 incydentów.", []),
    "content": (7500, "szablon „PILNE: {PER}…” · Jan Kowalski\nOCR + VLM 3.9 s, twarze 1.7 s, tekst/NER/szablon 0.8 s, embeddingi 1.1 s.\nTwarz Jana Kowalskiego (0.91) potwierdza nazwisko z tekstu.", []),
    "infra": (2400, "partia LE R11 · RDAP timeout\nCertyfikat z nocnej partii 00:47–02:31 UTC; origin AS64500 za Cloudflare (waga 0).\nRDAP nie odpowiedział — dane częściowe.", ["RDAP timeout — brak rejestratora"]),
    "compare": (700, "312 kandydatów → 9 kampanii\nPorównałem z 1 284 znanymi incydentami (blocking + dowody).\nNajlepsza: KMP-017, druga KMP-034 (ten sam operator).", []),
    "verdict": (100, "decyzja konformalna\nZbiór konformalny = {KMP-017} przy α = 0,05.", []),
}
DISPATCH_S = 1.3
TOTAL_MS = 19600


def _ts(base: datetime, off: float) -> str:
    return (base + timedelta(seconds=off)).isoformat(timespec="milliseconds")


def _load(name: str) -> Any:
    return json.loads((MOCK_DIR / f"{name}.json").read_text(encoding="utf-8"))


def job_sequence(job_id: str, kind: str = "known", base: datetime | None = None) -> Seq:
    """kind: known -> INC-24817 joins KMP-017 (p=0.94); new -> INC-24901 (KMP-040 candidate); ambiguous -> INC-24866
    (kelvaro.live, board 12); error -> INC-24920 (selqueno.live: capture fails, job.error + insufficient, board 13)."""
    base = base or datetime.now(timezone.utc)
    decs = _load("decisions")["data"]
    dec = Decision.model_validate(decs[{"known": "INC-24817", "new": "INC-24901", "ambiguous": "INC-24866", "error": "INC-24920"}[kind]])
    if kind == "error":
        return _error_sequence(job_id, dec, base)
    by_field = {e.field: e for e in dec.evidence}
    ev_for: dict[str, list[EvidenceItem]] = {
        "zwiadowca": [e for e in dec.evidence if e.bot == "zwiadowca"], "tropiciel": [e for e in dec.evidence if e.bot == "tropiciel"],
        "czytelnik": [e for e in dec.evidence if e.bot == "czytelnik" and e.state == "match"],
        "notariusz": [e for e in dec.evidence if e.bot == "notariusz" and e.state != "missing"], "archiwista": [], "sedzia": []}
    seq: Seq = []
    t = DISPATCH_S
    emit = lambda off, typ, data: seq.append((round(off, 3), Event(type=typ, at=_ts(base, off), data=data)))
    for key, bot, label in BOT_STEPS:
        dur, detail, warns = STEP_PLAN[key]
        if kind == "new" and key == "tracking":
            detail = "brak znanych pikseli/kitu"
        if kind == "known" or key != "infra":
            pass
        run = JobStep(key=key, bot=bot, label=label, status="run", started_at=_ts(base, t))
        emit(t, "job.step", {"job_id": job_id, "step": run.model_dump(mode="json")})
        items = ev_for[bot]
        for i, e in enumerate(items):
            off = t + dur / 1000 * (i + 1) / (len(items) + 1)
            emit(off, "job.evidence", {"job_id": job_id, "bot": bot, "item": e.model_dump(mode="json")})
            if bot in ("zwiadowca", "tropiciel"):
                f = Finding(evidence=e, where="html" if bot == "tropiciel" else "screenshot", selector=None, bbox=[0.08, 0.1 + 0.2 * i, 0.84, 0.14])
                emit(off + 0.05, "job.finding", {"job_id": job_id, "finding": f.model_dump(mode="json")})
        if bot == "archiwista":
            for j, frac in enumerate((0.4, 1.0)):
                scores = [s.model_copy(update={"score": round(s.score * frac, 2), "p": round(s.p * (0.55 + 0.45 * frac), 2)}) for s in dec.scores]
                emit(t + dur / 1000 * frac, "job.ranking", {"job_id": job_id, "scores": [s.model_dump(mode="json") for s in scores],
                                                            "graph": _mini_graph(dec).model_dump(mode="json")})
        status = "warn" if ((warns and kind in ("known", "ambiguous")) or (key == "verdict" and dec.decision in ("ambiguous", "confirm"))) else "done"
        done = JobStep(key=key, bot=bot, label=label, status=status, started_at=_ts(base, t), duration_ms=dur, detail=detail,
                       warnings=warns if kind == "known" else [])
        t += dur / 1000
        emit(t, "job.step", {"job_id": job_id, "step": done.model_dump(mode="json")})
    emit(t + 0.05, "job.done", {"job_id": job_id, "incident_id": dec.incident_id, "decision": dec.model_dump(mode="json")})
    seq.sort(key=lambda x: x[0])
    return seq


def _error_sequence(job_id: str, dec: Decision, base: datetime) -> Seq:
    seq: Seq = []
    emit = lambda off, typ, data: seq.append((round(off, 3), Event(type=typ, at=_ts(base, off), data=data)))
    t = DISPATCH_S
    for key, bot, label in BOT_STEPS:
        if key == "capture":
            emit(t, "job.step", {"job_id": job_id, "step": JobStep(key=key, bot=bot, label=label, status="run", started_at=_ts(base, t)).model_dump(mode="json")})
            t += 4.2
            err = JobStep(key=key, bot=bot, label=label, status="error", started_at=_ts(base, t - 4.2), duration_ms=4200,
                          detail="strona nie odpowiada (HTTP 502)\nPróbowałem 3 razy z profilem Facebook (Android, PL).\nSerwer zwraca 502 — nie mam z czego wyciągnąć śladów.",
                          warnings=["HTTP 502 po 3 próbach"])
            emit(t, "job.step", {"job_id": job_id, "step": err.model_dump(mode="json")})
            emit(t + 0.05, "job.error", {"job_id": job_id, "step": "capture", "message": "Nie udało się pobrać strony: serwer odpowiada 502 (selqueno.live)."})
        else:
            t += 0.15
            st = JobStep(key=key, bot=bot, label=label, status="skip" if key != "verdict" else "warn", duration_ms=0,
                         detail=("pominięto — brak materiału ze strony" if key != "verdict" else "za mało materiału\nZostały tylko cechy samego adresu URL.\nBrak decyzji — spróbuj ponownie lub wgraj HAR/zrzut."))
            emit(t, "job.step", {"job_id": job_id, "step": st.model_dump(mode="json")})
    emit(t + 0.1, "job.done", {"job_id": job_id, "incident_id": dec.incident_id, "decision": dec.model_dump(mode="json")})
    return seq


def _mini_graph(dec: Decision) -> GraphPayload:
    cid = dec.campaign_id or dec.candidate_campaign_id or "KMP-040"
    nodes = [GraphNode(id=dec.incident_id, kind="incident", label=dec.incident_id, campaign_id=cid, size=2),
             GraphNode(id=cid, kind="campaign", label=cid, campaign_id=cid, size=3)]
    edges = [GraphEdge(a=dec.incident_id, b=cid, type="member", weight=dec.score)]
    for s in dec.scores[1:]:
        nodes.append(GraphNode(id=s.campaign_id, kind="campaign", label=s.campaign_id, size=1.5))
        edges.append(GraphEdge(a=dec.incident_id, b=s.campaign_id, type="tracking", weight=s.score))
    return GraphPayload(nodes=nodes, edges=edges, focus=dec.incident_id)


def fold_job(job_id: str, inp: JobInput, seq: Seq, elapsed: float) -> Job:
    """Job state as of `elapsed` seconds after creation (GET /jobs/{id} in mock mode)."""
    job = Job(id=job_id, input=inp, status="queued" if elapsed < DISPATCH_S else "running")
    steps = {s.key: s for s in job.steps}
    for off, ev in seq:
        if off > elapsed:
            break
        if ev.type == "job.step":
            st = JobStep.model_validate(ev.data["step"])
            steps[st.key] = st
        elif ev.type == "job.error":
            job.status, job.error = "error", ev.data.get("message")
        elif ev.type == "job.done":
            job.status, job.incident_id = ("error" if job.status == "error" else "done"), ev.data["incident_id"]
            d = Decision.model_validate(ev.data["decision"])
            job.decision, job.campaign_id, job.total_ms = d.decision, d.campaign_id or d.candidate_campaign_id, TOTAL_MS
    job.steps = [steps[k] for k, _, _ in BOT_STEPS]
    return job


# ------------------------------------------------------------------------------------------------- investigation
def investigation_sequence(inv_id: str, base: datetime | None = None) -> Seq:
    base = base or datetime.now(timezone.utc)
    inv = Investigation.model_validate(_load("investigations")["data"][0])
    nodes = {n.id: n for n in inv.nodes}
    seq: Seq = []
    emit = lambda off, typ, data: seq.append((round(off, 3), Event(type=typ, at=_ts(base, off), data=data)))
    seen: set[str] = set()
    sec = lambda s: int(s.at[14:16]) * 60 + int(s.at[17:19]) if s.at[11:13] == "08" else 0
    # `at` was built as 08:MM:SS in universe2 (MM*60+SS seconds since start)
    last = 0.0
    for st in inv.steps:
        off = float(sec(st))
        last = off
        emit(off, "agent.step", {"investigation_id": inv_id, "step": st.model_dump(mode="json")})
        for k, nid in enumerate(st.produced):
            n = nodes.get(nid)
            if not n:
                continue
            emit(off + 0.7 + 0.25 * k, "graph.node_added", {"investigation_id": inv_id, "node": n.model_dump(mode="json"), "parent": next((e["a"] for e in inv.edges if e["b"] == nid), None)})
            seen.add(nid)
            for e in inv.edges:
                if (e["a"] == nid and e["b"] in seen) or (e["b"] == nid and e["a"] in seen):
                    emit(off + 0.75 + 0.25 * k, "graph.edge_added", {"investigation_id": inv_id, "edge": e})
        text = f"**Krok {st.n}** · `{st.tool}` — {st.result_summary} _{st.why}_\n\n"
        for c, i in enumerate(range(0, len(text), 60)):
            emit(off + 1.5 + 0.15 * c, "casefile.delta", {"investigation_id": inv_id, "step_n": st.n, "text_delta": text[i:i + 60]})
    emit(last + 3.0, "investigation.decision", {"investigation_id": inv_id, "node_id": (inv.pending_decision or {}).get("node_id"),
                                                "question": (inv.pending_decision or {}).get("question"), "options": (inv.pending_decision or {}).get("options", [])})
    emit(last + 6.0, "investigation.done", {"investigation_id": inv_id, "summary": {"conclusions": inv.conclusions, "steps": len(inv.steps), "domains_found": 14, "usd": 0.07}})
    seq.sort(key=lambda x: x[0])
    return seq


def fold_investigation(inv_id: str, seed: str, seq: Seq, elapsed: float, template: Investigation) -> Investigation:
    inv = template.model_copy(deep=True)
    inv.id, inv.seed = inv_id, seed
    steps, node_ids = [], set()
    done = False
    for off, ev in seq:
        if off > elapsed:
            break
        if ev.type == "agent.step":
            steps.append(ev.data["step"])
        elif ev.type == "graph.node_added":
            node_ids.add(ev.data["node"]["id"])
        elif ev.type == "investigation.done":
            done = True
    from trop.schema import InvestigationStep
    inv.steps = [InvestigationStep.model_validate(s) for s in steps]
    inv.nodes = [n for n in inv.nodes if n.id in node_ids]
    inv.edges = [e for e in inv.edges if e["a"] in node_ids and e["b"] in node_ids]
    inv.budget = {**inv.budget, "used": len(inv.steps)}
    if not done:
        inv.status, inv.conclusions, inv.pending_decision = "running", [], None
    return inv


# ------------------------------------------------------------------------------------------------- oracle / events
def oracle_events(base: datetime | None = None) -> list[Event]:
    base = base or datetime.now(timezone.utc)
    preds = _load("oracle")["data"]["predictions"]
    out = []
    for i, p in enumerate(preds):
        p = dict(p, issued_at=_ts(base, i * 0.0), status="predicted", first_ad_at=None, lead_time_h=None)
        out.append(Event(type="oracle.match", at=_ts(base, 0), data=p))
    return out


def oracle_sequence(base: datetime | None = None) -> Seq:
    return [(2.0 + 5.0 * i, e) for i, e in enumerate(oracle_events(base))]


def global_sequence(base: datetime | None = None) -> Seq:
    """A short loop of dashboard events (S01 live feed)."""
    base = base or datetime.now(timezone.utc)
    E = lambda typ, data: Event(type=typ, at=_ts(base, 0), data=data)
    items = [
        ("incident.created", {"incident_id": "INC-24850", "source": "hunter"}),
        ("incident.attributed", {"incident_id": "INC-24850", "decision": "assign", "campaign_id": "KMP-017", "p": 0.93}),
        ("campaign.updated", {"campaign_id": "KMP-017", "counts": {"incidents": 47, "incidents_24h": 6, "domains": 19}, "heat": {"trend_pct": 39.0}}),
        ("alert.created", {"id": "ALR-5", "kind": "oracle", "severity": "warn", "title": "Oracle: tranvello.click (0.71)", "subject_id": "tranvello.click", "created_at": _ts(base, 0), "status": "open"}),
        ("triage.created", {"item_id": "TRI-24", "type": "uncertain"}),
        ("hunter.capture", {"source_id": "SRC-meta", "incident_id": "INC-24851"}),
        ("oracle.match", {"domain": "brustia.click", "issued_at": _ts(base, 0), "issuer": "R10", "dna_score": 0.42, "campaign_id": "KMP-017", "status": "below_threshold", "reasons": ["tylko tld"]}),
        ("extension.report", {"incident_id": "INC-24852"}),
    ]
    return [(1.0 + 4.0 * i, E(t, d)) for i, (t, d) in enumerate(items)]


# ------------------------------------------------------------------------------------------------- recordings
def record_to(path: Path, seq: Seq) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for off, ev in seq:
            f.write(json.dumps({"t": off, "type": ev.type, "event": ev.model_dump(mode="json")}, ensure_ascii=False) + "\n")


def canned_recordings() -> dict[str, Seq]:
    """name -> sequence. File name `<name>.jsonl`; `?replay=demo` resolves to `demo-<kind>.jsonl`."""
    base = datetime(2026, 11, 21, 8, 50, tzinfo=timezone.utc)
    return {"demo-analyze": job_sequence("JOB-DEMO", "known", base), "demo-analyze-new": job_sequence("JOB-DEMO-NEW", "new", base),
            "demo-investigation": investigation_sequence("INV-DEMO", base), "demo-events": global_sequence(base), "demo-oracle": oracle_sequence(base)}
