"""Clean boundary between Hunter and the rest of the system.

* always: drafts + run record are written as JSON under <data_dir>/hunter/<run_id>/ (draft_*.json, run.json)
* when importable: the draft is handed to WS1's store / engine (`trop.store` / `trop.engine.service`), duck-typed so this
  module works before they exist. Register a custom publisher with `set_publisher(fn)` (the worker does this).

    publisher(draft: IncidentDraft) -> incident_id: str | None
"""
from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from trop.config import settings
from trop.schema import HunterRun, IncidentDraft

_publisher: Callable[[IncidentDraft], str | None] | None = None
_STORE_FNS = ("add_incident", "save_incident", "insert_incident", "create_incident", "ingest_draft")


def hunter_dir() -> Path:
    p = Path(settings.data_dir) / "hunter"
    p.mkdir(parents=True, exist_ok=True)
    return p


def set_publisher(fn: Callable[[IncidentDraft], str | None] | None) -> None:
    global _publisher
    _publisher = fn


def new_run_id(source: str) -> str:
    return f"HR-{source}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"


def _auto_publisher() -> Callable[[IncidentDraft], str | None] | None:
    for modname in ("trop.engine.service", "trop.store"):
        try:
            m = importlib.import_module(modname)
        except Exception:      # not built yet / DB not up
            continue
        for fn in _STORE_FNS:
            if callable(getattr(m, fn, None)):
                return getattr(m, fn)
    return None


def publish(draft: IncidentDraft) -> str | None:
    """Hand a draft to the store/engine; returns the incident id or None when nothing is wired (drafts stay on disk)."""
    pub = _publisher or _auto_publisher()
    if pub is None:
        return None
    try:
        r = pub(draft)
        return str(getattr(r, "id", r)) if r is not None else None
    except Exception as e:     # a store hiccup must not kill the run
        draft.quality.errors = [*draft.quality.errors, f"publish: {type(e).__name__}: {str(e)[:150]}"]
        return None


def write_draft(run_id: str, draft: IncidentDraft) -> Path:
    d = hunter_dir() / run_id
    d.mkdir(parents=True, exist_ok=True)
    name = (draft.source.ref or draft.id or "draft").replace(":", "_").replace("/", "_")
    p = d / f"draft_{name}.json"
    p.write_text(draft.model_dump_json(indent=1), encoding="utf-8")
    return p


def write_run(run: HunterRun, extra: dict | None = None) -> Path:
    d = hunter_dir() / run.id
    d.mkdir(parents=True, exist_ok=True)
    p = d / "run.json"
    body = run.model_dump()
    if extra:
        body["detail"] = extra
    p.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def list_runs(source_id: str | None = None, limit: int = 50) -> list[HunterRun]:
    runs: list[HunterRun] = []
    for p in sorted(hunter_dir().glob("HR-*/run.json"), reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            d.pop("detail", None)
            r = HunterRun(**d)
        except Exception:
            continue
        if source_id is None or r.source_id == source_id:
            runs.append(r)
        if len(runs) >= limit:
            break
    return runs


def load_drafts(run_id: str) -> list[IncidentDraft]:
    return [IncidentDraft.model_validate_json(p.read_text(encoding="utf-8")) for p in sorted((hunter_dir() / run_id).glob("draft_*.json"))]
