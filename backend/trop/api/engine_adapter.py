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
        from trop.api.mockstore import scenario_of
        scenario = scenario_of(material.name)
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


_CORPUS = None


def worker_corpus():
    """Corpus loaded once per process (DB first, JSON fallback)."""
    global _CORPUS
    if _CORPUS is None:
        from trop.engine import service
        try:
            _CORPUS = service.Corpus.load(source="db")
        except Exception:  # noqa: BLE001
            _CORPUS = service.Corpus.load()
    return _CORPUS


def capture_mode() -> str:
    """off | sandbox | local. TROP_CAPTURE wins; default = sandbox in live mode, else off."""
    import importlib.util
    from trop.config import settings
    m = (settings.trop_capture or ("sandbox" if settings.trop_mode == "live" and os.environ.get("TROP_NO_LIVE") != "1" else "off")).lower()
    if m not in ("sandbox", "local") or importlib.util.find_spec("trop.capture.capture") is None:
        return "off"
    return m


def capture_available() -> bool:
    return capture_mode() != "off"


class ServiceAdapter:
    """Real engine (WS1): `service.analyze_path` runs the six bot steps; events get a job_id and are forwarded 1:1."""

    def __init__(self):
        self.service = importlib.import_module("trop.engine.service")

    def analyze(self, material: Material, emit: Emit) -> Decision:
        jid = material.job_id
        held: list[tuple[str, dict]] = []

        def cb(typ: str, data: dict) -> None:
            data = {"job_id": jid, **data}
            if typ == "job.done":          # job.done must be the LAST event (findings first)
                held.append((typ, data))
            else:
                emit(typ, data)

        src = material.name if material.kind == "url" else (material.paths[0] if len(material.paths) == 1 else str(_common_dir(material.paths)))
        skip_capture_run = False
        if material.kind == "url":
            from trop.engine.progress import Steps
            st = Steps(cb)
            if not capture_available():
                self._page_down(jid, st, emit, "przechwytywanie na żywo jest niedostępne w tym trybie (offline). Wgraj zrzut/HAR/ZIP zamiast adresu URL.")
            st.start("capture")
            try:
                from trop.capture.cli import capture_url
                res = capture_url(material.name, docker=capture_mode() == "sandbox" and os.environ.get("TROP_CAPTURE_LOCAL") != "1", fast=True)
            except Exception as e:  # noqa: BLE001
                res = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            if not res.get("ok") or not res.get("bundle"):
                st.done("capture", status="error", detail=f"Strona niedostępna: {str(res.get('error') or 'brak odpowiedzi')[:160]}", warnings=["capture failed"])
                self._page_down(jid, None, emit, f"strona nie odpowiada ({str(res.get('error') or 'brak odpowiedzi')[:160]}).")
            src, skip_capture_run = res["bundle"], True
            _inner = cb

            def cb(typ: str, data: dict, _inner=_inner) -> None:     # noqa: F811 -- we already emitted `capture` run
                if skip_capture_run and typ == "job.step" and data["step"]["key"] == "capture" and data["step"]["status"] == "run":
                    return
                _inner(typ, data)
        inc_id = "INC-U" + jid.rsplit("-", 1)[-1][:6]
        dec, inc, findings = self.service.analyze_path(src, worker_corpus(), emit=cb, inc_id=inc_id)
        for f in findings:
            emit("job.finding", {"job_id": jid, "finding": f.model_dump(mode="json")})
        _remember(inc, dec)
        for typ, data in held:
            emit(typ, data)
        return dec


    @staticmethod
    def _page_down(jid: str, st, emit: Emit, why: str):
        if st is not None:
            st.start("capture")
            st.done("capture", status="error", detail="Strona niedostępna dla przechwytywania", warnings=["capture unavailable"])
        emit("job.error", {"job_id": jid, "step": "capture", "message": "Nie udało się pobrać strony: " + why})
        raise CaptureUnavailable(why)


class CaptureUnavailable(RuntimeError):
    """Raised after job.error was emitted (the worker must not emit a second one)."""


def _common_dir(paths: list[str]):
    from pathlib import Path
    return Path(paths[0]).parent


def _remember(inc: dict, dec: Decision) -> None:
    """Keep the analysed incident + decision for GET /incidents/{id} (Redis 7 days; DB best effort)."""
    import json
    try:
        import redis
        from trop.config import settings
        r = redis.Redis.from_url(settings.redis_url)
        r.set(f"trop:incident:{dec.incident_id}", json.dumps({"incident": inc, "decision": dec.model_dump(mode="json")}, default=str), ex=7 * 86400)
    except Exception:  # noqa: BLE001
        pass
    try:
        from trop.store.corpus import save_decision
        save_decision(dec, inc)
    except Exception:  # noqa: BLE001
        pass


def get_adapter() -> EngineAdapter:
    try:
        return ServiceAdapter()
    except ModuleNotFoundError:
        return StubAdapter()
