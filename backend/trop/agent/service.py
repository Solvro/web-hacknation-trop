"""White Rabbit service API (what WS2's API routes and arq worker call).

    run_investigation(body, emit=None, *, investigation_id=None, usd_cap=1.0, ...) -> dict   # blocking (worker task)
    start_investigation(body, emit=None, **kw) -> Investigation                             # background thread, returns at once
    steer(iid, message=None, node_id=None, choice=None) -> dict                             # {ok, detail}
    stop(iid, resume=False) -> dict                       # resume=True = pause (design: "pause = stop with resume:true")
    resume(iid) -> dict
    get_investigation(iid) -> Investigation · list_investigations(status=None) -> list[Investigation]
    events(iid) -> list[dict]  (recorded schema.Event dicts, for SSE history / late subscribers)
    promote(iid | Investigation, campaign_id, node_ids) -> {campaign_id, added}
    new_investigation_id() -> "INV-<n>"

Persistence (until the lead wires the DB): data/investigations/<id>/{investigation.json, events.jsonl, control.jsonl},
promotions in data/investigations/promotions.jsonl through `PROMOTE_SINK` (replace it to write to the store).
Control works across processes: steer/stop append to control.jsonl, the running loop polls it between steps.
"""
from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trop.config import settings
from trop.schema import Investigation, InvestigationCreate

from .case import Case, Emit, Recorder, dom_id
from .loop import LLM, Control, default_llm, run
from .tools import TOOL_NAMES, Ctx, _apex

_LOCK = threading.Lock()
_RUNNING: dict[str, tuple[threading.Thread, Control]] = {}


def root() -> Path:
    p = Path(settings.data_dir) / "investigations"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _dir(iid: str) -> Path:
    if not iid or "/" in iid or ".." in iid:
        raise ValueError("bad investigation id")
    return root() / iid


def new_investigation_id() -> str:
    with _LOCK:
        ns = [int(p.name.split("-")[1]) for p in root().glob("INV-*") if p.name.split("-")[1].isdigit()]
        n = max(ns + [99]) + 1
        _dir(f"INV-{n}").mkdir(parents=True, exist_ok=True)
        return f"INV-{n}"


def _body(body: InvestigationCreate | dict | str) -> InvestigationCreate:
    if isinstance(body, InvestigationCreate):
        return body
    if isinstance(body, str):
        return InvestigationCreate(seed=body)
    return InvestigationCreate.model_validate(body)


def run_investigation(body: InvestigationCreate | dict | str, emit: Emit | None = None, *, investigation_id: str | None = None,
                      usd_cap: float = 1.0, model: str = "pro", llm: LLM | None = None, planner: str = "auto",
                      record: str | Path | None = None, ext: Any = None, dbm: Any = None, captures: int = 1,
                      tools: list[str] | None = None, control: Control | None = None) -> dict:
    """Blocking run. Returns the final Investigation as a dict. `body.offline` forces cache-only enrichment + LLM."""
    b = _body(body)
    iid = investigation_id or new_investigation_id()
    d = _dir(iid)
    d.mkdir(parents=True, exist_ok=True)
    if b.offline:
        import os
        os.environ["TROP_OFFLINE"] = "1"
        settings.trop_mode = "offline"
    from . import db as _db
    dbm = dbm or _db
    seed = _apex(b.seed) or b.seed
    inv = Investigation(id=iid, seed=seed, campaign_id=b.campaign_id, status="running",
                        budget={"steps": float(b.budget_steps), "used": 0.0, "usd": usd_cap, "usd_used": 0.0},
                        model={"pro": settings.gemini_pro_model, "flash": settings.gemini_flash_model}.get(model, model),
                        tools=tools or [t for t in TOOL_NAMES if t not in ("propose_link", "finish")],
                        started_at=datetime.now(UTC).isoformat(timespec="seconds"))
    rec = Recorder(record or d / "events.jsonl")
    if record:   # also keep the per-investigation copy
        rec2 = Recorder(d / "events.jsonl")
        _w = rec.write
        rec.write = lambda ev, t=None: (_w(ev, t), rec2.write(ev, t))  # type: ignore[method-assign]
    case = Case(inv, emit, rec, d / "investigation.json")
    try:
        camp = dbm.campaign_domains(b.campaign_id) if b.campaign_id else set()
    except Exception:  # noqa: BLE001
        camp = set()
    ctx = Ctx(case=case, seed=seed, campaign_id=b.campaign_id, campaign_domains=camp, ext=ext, dbm=dbm, captures_left=captures)
    control = control or Control(d / "control.jsonl")
    (d / "control.jsonl").touch()
    control._pos = len((d / "control.jsonl").read_text().splitlines())
    try:
        run(ctx, llm=llm or (default_llm(model) if planner != "heuristic" else None), steps=b.budget_steps,
            usd_cap=usd_cap, control=control, planner=planner)
    except Exception as e:  # noqa: BLE001
        inv.status = "error"
        case.note(f"_Błąd: {type(e).__name__}: {str(e)[:200]}_")
        case.done({"error": str(e)[:300], "steps": len(inv.steps)}, status="error")
    return inv.model_dump()


def start_investigation(body: InvestigationCreate | dict | str, emit: Emit | None = None, **kw: Any) -> Investigation:
    """Start in a daemon thread (in-process API use). Returns the initial Investigation (status running)."""
    b = _body(body)
    iid = kw.pop("investigation_id", None) or new_investigation_id()
    control = Control(_dir(iid) / "control.jsonl")
    t = threading.Thread(target=run_investigation, args=(b, emit), kwargs={"investigation_id": iid, "control": control, **kw},
                         daemon=True, name=f"white-rabbit-{iid}")
    _RUNNING[iid] = (t, control)
    inv = Investigation(id=iid, seed=_apex(b.seed) or b.seed, campaign_id=b.campaign_id, status="running",
                        budget={"steps": float(b.budget_steps), "used": 0.0, "usd": kw.get("usd_cap", 1.0), "usd_used": 0.0},
                        started_at=datetime.now(UTC).isoformat(timespec="seconds"))
    _save(inv)
    t.start()
    return inv


def _control(iid: str, cmd: dict) -> dict:
    d = _dir(iid)
    if not d.exists():
        return {"ok": False, "detail": "investigation not found"}
    with (d / "control.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({**cmd, "at": datetime.now(UTC).isoformat(timespec="seconds")}, ensure_ascii=False) + "\n")
    try:
        inv = get_investigation(iid)
        running = inv.status in ("running", "paused")
    except FileNotFoundError:
        running = True
    return {"ok": True, "detail": "queued for the running agent" if running else "investigation already finished"}


def steer(iid: str, message: str | None = None, node_id: str | None = None, choice: str | None = None) -> dict:
    """Analyst steer: a free-text hint and/or the answer to the Sędzia card (choice 'Dołącz' | 'Pomiń')."""
    cmd: dict[str, Any] = {"type": "decision" if choice else "steer"}
    if message:
        cmd["message"] = message
    if node_id:
        cmd["node_id"] = node_id
    if choice:
        cmd["choice"] = choice
    return _control(iid, cmd)


def stop(iid: str, resume: bool = False) -> dict:
    return _control(iid, {"type": "pause" if resume else "stop"})


def resume(iid: str) -> dict:
    return _control(iid, {"type": "resume"})


def _save(inv: Investigation) -> None:
    p = _dir(inv.id) / "investigation.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(inv.model_dump_json(indent=1), encoding="utf-8")


def get_investigation(iid: str) -> Investigation:
    p = _dir(iid) / "investigation.json"
    if not p.is_file():
        raise FileNotFoundError(iid)
    return Investigation.model_validate_json(p.read_text(encoding="utf-8"))


def list_investigations(status: str | None = None) -> list[Investigation]:
    out = []
    for p in sorted(root().glob("INV-*/investigation.json")):
        try:
            inv = Investigation.model_validate_json(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not status or inv.status == status:
            out.append(inv)
    return out


def events(iid: str) -> list[dict]:
    p = _dir(iid) / "events.jsonl"
    if not p.is_file():
        return []
    return [json.loads(ln)["event"] for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


# ============================================================================== promote
def _json_sink(campaign_id: str, investigation_id: str, items: list[dict]) -> int:
    with (root() / "promotions.jsonl").open("a", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps({"campaign_id": campaign_id, "investigation_id": investigation_id, **it,
                                "at": datetime.now(UTC).isoformat(timespec="seconds")}, ensure_ascii=False) + "\n")
    return len(items)


PROMOTE_SINK: Callable[[str, str, list[dict]], int] = _json_sink
"""(campaign_id, investigation_id, items[{node_id, kind, label, evidence, level}]) -> number added. The lead swaps this
for a store function (e.g. new oracle_candidates / campaign domain rows) at integration."""


def promote(investigation: Investigation | str, campaign_id: str, node_ids: list[str]) -> dict:
    """'Dodaj do kampanii' (board 10): selected domain/incident nodes join the campaign. -> {campaign_id, added}."""
    inv = get_investigation(investigation) if isinstance(investigation, str) else investigation
    by_id = {n.id: n for n in inv.nodes}
    items = []
    for nid in dict.fromkeys(node_ids):
        n = by_id.get(nid) or by_id.get(dom_id(nid))
        if not n or n.kind not in ("domain", "incident") or n.status in ("in_campaign",) or n.meta.get("seed"):
            continue
        items.append({"node_id": n.id, "kind": n.kind, "label": n.label, "level": n.meta.get("level"),
                      "evidence": n.meta.get("evidence", [])[:10], "certpl": n.meta.get("certpl")})
    added = PROMOTE_SINK(campaign_id, inv.id, items) if items else 0
    for it in items:
        n = by_id[it["node_id"]]
        n.status = "in_campaign"
        n.meta["promoted_to"] = campaign_id
    if items and (_dir(inv.id) / "investigation.json").exists():
        _save(inv)
    return {"campaign_id": campaign_id, "added": added}
