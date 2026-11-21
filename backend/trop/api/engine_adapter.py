"""Clean boundary between the API/worker and the evidence engine (WS1).

The worker only calls `get_adapter().analyze(material, emit)`; `emit(event_type, data)` publishes SSE events in the
CONTRACTS §4.1 order. Until `trop.engine.service` exists the `StubAdapter` replays the canned mock analysis so the
whole path (upload -> arq -> Redis pub/sub -> SSE) can be tested. The lead wires `ServiceAdapter._build_incident`
(WS1 ingest) at gate G2; everything else is already in place.
"""
from __future__ import annotations

import importlib
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol

from trop.schema import BOT_STEPS, CampaignScore, Decision, EvidenceItem, Finding, Incident, JobStep

Emit = Callable[[str, dict], None]


@dataclass
class Material:
    job_id: str
    kind: str                       # url | file | zip | folder | batch
    name: str                       # url or display name
    paths: list[str] = field(default_factory=list)   # uploaded files under settings.artifact_dir


class EngineAdapter(Protocol):
    def analyze(self, material: Material, emit: Emit) -> Decision: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class StepEmitter:
    """Produces the §4.1 event order from simple calls (used by ServiceAdapter)."""

    def __init__(self, job_id: str, emit: Emit):
        self.job_id, self.emit, self._t = job_id, emit, {}

    def run(self, key: str, detail: str | None = None) -> None:
        k, bot, label = next(s for s in BOT_STEPS if s[0] == key)
        self._t[key] = time.monotonic()
        st = JobStep(key=k, bot=bot, label=label, status="run", started_at=_now(), detail=detail)
        self.emit("job.step", {"job_id": self.job_id, "step": st.model_dump(mode="json")})

    def done(self, key: str, status: str = "done", detail: str | None = None, warnings: list[str] | None = None) -> None:
        k, bot, label = next(s for s in BOT_STEPS if s[0] == key)
        ms = int((time.monotonic() - self._t.get(key, time.monotonic())) * 1000)
        st = JobStep(key=k, bot=bot, label=label, status=status, duration_ms=ms, detail=detail, warnings=warnings or [])
        self.emit("job.step", {"job_id": self.job_id, "step": st.model_dump(mode="json")})

    def evidence(self, bot: str, item: EvidenceItem) -> None:
        self.emit("job.evidence", {"job_id": self.job_id, "bot": bot, "item": item.model_dump(mode="json")})

    def finding(self, f: Finding) -> None:
        self.emit("job.finding", {"job_id": self.job_id, "finding": f.model_dump(mode="json")})

    def ranking(self, scores: list[CampaignScore], graph=None) -> None:
        d = {"job_id": self.job_id, "scores": [s.model_dump(mode="json") for s in scores]}
        if graph is not None:
            d["graph"] = graph.model_dump(mode="json")
        self.emit("job.ranking", d)

    def finish(self, dec: Decision) -> None:
        self.emit("job.done", {"job_id": self.job_id, "incident_id": dec.incident_id, "decision": dec.model_dump(mode="json")})


class StubAdapter:
    """Replays the canned sequence (INC-24817 or the new-campaign case) with original timing."""

    def __init__(self, speed: float | None = None):
        self.speed = speed if speed is not None else float(os.environ.get("TROP_MOCK_SPEED", "1") or 1)

    def analyze(self, material: Material, emit: Emit) -> Decision:
        from trop.api import sequences as S
        scenario = "new" if any(h in material.name.lower() for h in ("bon", "energ")) else "known"
        seq = S.job_sequence(material.job_id, scenario)
        t0 = time.monotonic()
        dec = None
        for off, ev in seq:
            wait = off / self.speed - (time.monotonic() - t0)
            if wait > 0:
                time.sleep(wait)
            emit(ev.type, ev.data)
            if ev.type == "job.done":
                dec = Decision.model_validate(ev.data["decision"])
        assert dec
        return dec


class ServiceAdapter:
    """Real engine (WS1): ingest material -> Incident -> trop.engine.service.analyze_incident (engine/contract.py)."""

    def __init__(self):
        self.service = importlib.import_module("trop.engine.service")

    def _build_incident(self, material: Material, em: StepEmitter) -> Incident:
        """WIRING POINT (lead, gate G2): capture (WS5) + extract (WS1 ingest) emitting steps capture/tracking/content/infra
        through `em`, returning the Incident. Until then raise so the worker reports job.error."""
        raise NotImplementedError("trop.ingest -> Incident wiring pending (G2)")

    def analyze(self, material: Material, emit: Emit) -> Decision:
        em = StepEmitter(material.job_id, emit)
        inc = self._build_incident(material, em)
        em.run("compare")
        corpus = self.service.Corpus.load()
        dec, findings = self.service.analyze_incident(inc, corpus)
        for f in findings:
            em.finding(f)
        em.ranking(dec.scores)
        em.done("compare")
        em.run("verdict")
        em.done("verdict")
        em.finish(dec)
        return dec


def get_adapter() -> EngineAdapter:
    try:
        return ServiceAdapter()
    except ModuleNotFoundError:
        return StubAdapter()
