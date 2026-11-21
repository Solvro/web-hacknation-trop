"""Worker-side wiring of the other workstreams: Hunter drafts -> engine attribution, Oracle matches -> SSE, scheduler."""
from __future__ import annotations

import logging
import os
import zlib

log = logging.getLogger("trop.worker")


def hunter_publisher(draft) -> str | None:
    """IncidentDraft -> Incident -> engine decision (+ store) -> `hunter.capture` + `incident.attributed` on Redis `events`."""
    from trop.api.engine_adapter import _remember, worker_corpus
    from trop.engine import service
    from trop.worker import bus
    inc = draft.model_dump(mode="json")
    key = f"{(inc.get('source') or {}).get('ref') or ''}|{(inc.get('landing') or {}).get('entry_url') or ''}|{(inc.get('ad') or {}).get('library_id') or ''}"
    inc["id"] = inc.get("id") or f"INC-H{zlib.crc32(key.encode()):08x}"
    dec, _ = service.analyze_incident(inc, worker_corpus())
    _remember(inc, dec)
    src = (inc.get("source") or {}).get("type") or "hunter"
    bus.publish_sync("events", "incident.created", {"incident_id": inc["id"], "source": src})
    bus.publish_sync("events", "hunter.capture", {"source_id": src, "incident_id": inc["id"]})
    bus.publish_sync("events", "incident.attributed", {"incident_id": inc["id"], "decision": dec.decision,
                                                         "campaign_id": dec.campaign_id or dec.candidate_campaign_id, "p": dec.p})
    return inc["id"]


def oracle_notifier(pred) -> None:
    from trop.worker import bus
    d = pred.model_dump(mode="json")
    bus.publish_sync("oracle", "oracle.match", d)
    bus.publish_sync("events", "oracle.match", d)


def install() -> object | None:
    """Called from the worker startup. Returns the scheduler when TROP_SCHEDULER=1 (off by default)."""
    from trop.hunter import sink
    from trop.oracle import service as oracle
    sink.set_publisher(hunter_publisher)
    oracle.set_notifier(oracle_notifier)
    if os.environ.get("TROP_SCHEDULER") == "1":
        from trop.hunter.scheduler import build_scheduler
        sch = build_scheduler(background=True)
        sch.start()
        log.info("hunter/oracle scheduler started (%d jobs)", len(sch.get_jobs()))
        return sch
    return None
