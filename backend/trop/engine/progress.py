"""Step-wise progress hooks for the six bots (Sprawdź stream, docs/CONTRACTS.md §4.1).

The callback is ONE callable with the SSE event shape, so WS2's worker can forward it 1:1:

    Emit = Callable[[str, dict], None]          # emit(event_type, data)

    event_type          data
    "job.step"          {"step": JobStep-dict}                      status run -> done|warn|skip|error
    "job.evidence"      {"bot": BotName, "item": EvidenceItem-dict}  steps capture..infra (+ compare: pair evidence)
    "job.finding"       {"finding": Finding-dict}                   optional
    "job.ranking"       {"scores": [CampaignScore-dict, ...]}        from Archiwista (compare) on
    "job.done"          {"incident_id", "decision": Decision-dict}  last

The worker adds `job_id` (and `at`) to every data dict. Steps run in the fixed order schema.BOT_STEPS:
capture (zwiadowca) -> tracking (tropiciel) -> content (czytelnik) -> infra (notariusz) -> compare (archiwista)
-> verdict (sedzia). An exception inside the callback is logged and never breaks the analysis.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Callable

from trop.schema import BOT_STEPS, JobStep

log = logging.getLogger(__name__)
Emit = Callable[[str, dict], None]
BOT = {k: b for k, b, _ in BOT_STEPS}
LABEL = {k: lbl for k, _, lbl in BOT_STEPS}


class Steps:
    def __init__(self, emit: Emit | None = None, df: dict | None = None, n: int = 0):
        self.emit_fn = emit
        self.df, self.n = df, n
        self.t: dict[str, float] = {}
        self.items: dict[str, list] = {}

    def emit(self, event: str, data: dict) -> None:
        if self.emit_fn is None:
            return
        try:
            self.emit_fn(event, data)
        except Exception as e:  # noqa: BLE001
            log.warning("progress callback failed on %s: %s", event, e)

    def _step(self, key: str, status: str, **kw) -> dict:
        return JobStep(key=key, bot=BOT[key], label=LABEL[key], status=status, **kw).model_dump()

    def start(self, key: str) -> None:
        self.t[key] = time.time()
        self.emit("job.step", {"step": self._step(key, "run", started_at=datetime.now(timezone.utc).isoformat())})

    def done(self, key: str, status: str = "done", detail: str | None = None, warnings: list[str] | None = None) -> None:
        ms = int((time.time() - self.t.get(key, time.time())) * 1000)
        self.emit("job.step", {"step": self._step(key, status, duration_ms=ms, detail=detail, warnings=warnings or [])})

    def evidence(self, key: str, item) -> None:
        d = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        self.items.setdefault(key, []).append(d)
        self.emit("job.evidence", {"bot": BOT[key], "item": d})

    def material(self, inc: dict, key: str) -> None:
        """Emit findings about the material for one step (value + corpus rarity)."""
        if self.emit_fn is None:
            return
        from trop.engine.evidence import prepare
        from trop.engine.items import material_items
        prepare([inc])                    # cheap, and the incident may have gained layers since the last step
        for it in material_items(inc, key, self.df, self.n):
            it.bot = BOT[key]
            self.evidence(key, it)
        inc.pop("_v", None)

    def ranking(self, scores: list) -> None:
        self.emit("job.ranking", {"scores": [s.model_dump() if hasattr(s, "model_dump") else s for s in scores]})
