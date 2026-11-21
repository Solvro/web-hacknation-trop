"""Investigation state + the CONTRACTS §4.3 event stream (one place builds every node, edge, step and delta).

Events go to `emit(event_type, data)` (WS2's worker publishes them on `inv:{id}`) and, when a path is given, into a
replay file in the `data/replay/*.jsonl` format: {"t": seconds since start, "type", "event": schema.Event}.
`graph.node_added` is an upsert: a node whose status changes is re-sent with the same id.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from trop.schema import Event, Investigation, InvestigationNode, InvestigationStep

Emit = Callable[[str, dict], None]

TOOL_BOT = {
    "db_search": "archiwista", "incident_neighborhood": "archiwista", "crtsh": "notariusz", "rdap": "notariusz",
    "dns_ns": "notariusz", "certpl_check": "notariusz", "urlscan_search": "tropiciel", "adlib_search": "zwiadowca",
    "wayback": "czytelnik", "capture": "czytelnik", "oracle_lookup": "notariusz", "propose_link": "sedzia", "finish": "sedzia",
}
TOOL_BRANCH = {
    "db_search": "db", "incident_neighborhood": "db", "crtsh": "crtsh", "rdap": "crtsh", "dns_ns": "crtsh",
    "certpl_check": "certpl", "urlscan_search": "urlscan", "adlib_search": "adlib", "wayback": "content",
    "capture": "content", "oracle_lookup": "db", "propose_link": "db",
}
LEVEL_RANK = {"operator": 3, "campaign": 2, "infra": 1, "platform": 0}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def dom_id(fqdn: str) -> str:
    return "d-" + fqdn.lower().strip(".")


class Recorder:
    """Writes the replay file (same envelope WS2's SSE replay reads)."""

    def __init__(self, path: str | Path | None, clock: Callable[[], float] = time.monotonic) -> None:
        self.path = Path(path) if path else None
        self.clock = clock
        self.t0 = clock()
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("")

    def write(self, ev: Event, t: float | None = None) -> None:
        if not self.path:
            return
        t = round(self.clock() - self.t0, 3) if t is None else t
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"t": t, "type": ev.type, "event": ev.model_dump()}, ensure_ascii=False) + "\n")


class Case:
    def __init__(self, inv: Investigation, emit: Emit | None = None, recorder: Recorder | None = None,
                 save_path: str | Path | None = None, *, at: Callable[[], str] = now_iso,
                 delta_chunk: int = 60) -> None:
        self.inv = inv
        self._emit = emit
        self.rec = recorder
        self.save_path = Path(save_path) if save_path else None
        self.at = at
        self.delta_chunk = delta_chunk
        self.nodes: dict[str, InvestigationNode] = {n.id: n for n in inv.nodes}
        self.edges: set[tuple[str, str]] = {(e["a"], e["b"]) for e in inv.edges}
        self.events: list[Event] = []
        self.t_override: float | None = None      # scripted demo timing
        self.defer = False                         # while a tool runs, Sędzia cards wait until its agent.step is out
        self._deferred: list[dict] = []

    # ------------------------------------------------------------------ emit
    def emit(self, typ: str, data: dict) -> None:
        data = {"investigation_id": self.inv.id, **data}
        ev = Event(type=typ, at=self.at(), data=data)
        self.events.append(ev)
        if self.rec:
            self.rec.write(ev, self.t_override)
        if self._emit:
            try:
                self._emit(typ, data)
            except Exception:  # noqa: BLE001  (a dead subscriber must not kill the investigation)
                pass

    # ------------------------------------------------------------------ graph
    def node(self, nid: str, kind: str, label: str, *, branch: str | None = None, status: str | None = None,
             meta: dict | None = None, parent: str | None = None, edge_label: str | None = None,
             is_new: bool | None = None) -> tuple[InvestigationNode, bool]:
        """Upsert a node. Returns (node, created). Re-emits only when something visible changed."""
        cur = self.nodes.get(nid)
        if cur is None:
            n = InvestigationNode(id=nid, kind=kind, label=label, meta=meta or {}, status=status, is_new=is_new, branch=branch)
            self.nodes[nid] = n
            self.inv.nodes.append(n)
            self.emit("graph.node_added", {"node": n.model_dump(), "parent": parent})
            if parent and parent in self.nodes:
                self.edge(parent, nid, edge_label)
            return n, True
        changed = False
        if meta:
            for k, v in meta.items():
                if cur.meta.get(k) != v:
                    cur.meta[k] = v
                    changed = k in ("level", "certpl", "on_certpl", "ads", "first_cert", "decision", "promoted_to")
        if status and status != cur.status:
            cur.status, changed = status, True
        if label and label != cur.label and kind != "domain":
            cur.label, changed = label, True
        if changed:
            self.emit("graph.node_added", {"node": cur.model_dump(), "parent": None})
        if parent and parent in self.nodes and parent != nid:
            self.edge(parent, nid, edge_label)
        return cur, False

    def edge(self, a: str, b: str, label: str | None = None) -> None:
        if (a, b) in self.edges or a == b:
            return
        self.edges.add((a, b))
        e = {"a": a, "b": b, "label": label}
        self.inv.edges.append(e)
        self.emit("graph.edge_added", {"edge": e})

    def set_status(self, nid: str, status: str) -> None:
        if nid in self.nodes:
            self.node(nid, self.nodes[nid].kind, self.nodes[nid].label, status=status)

    def add_evidence(self, nid: str, ev: dict) -> None:
        """Accumulate evidence on a node; meta.level = the strongest level seen."""
        n = self.nodes[nid]
        evs = n.meta.setdefault("evidence", [])
        key = (ev.get("type"), ev.get("value"))
        if all((e.get("type"), e.get("value")) != key for e in evs):
            evs.append(ev)
        best = max((e.get("level", "platform") for e in evs), key=lambda x: LEVEL_RANK.get(x, 0))
        if n.meta.get("level") != best:
            self.node(nid, n.kind, n.label, meta={"level": best})

    # ------------------------------------------------------------------ steps / case file
    def step(self, tool: str, query: str, summary: str, why: str = "", produced: list[str] | None = None,
             cost_usd: float = 0.0) -> InvestigationStep:
        n = len(self.inv.steps) + 1
        s = InvestigationStep(n=n, tool=tool, query=query[:300], result_summary=summary, why=why, produced=produced or [],
                              at=self.at(), bot=TOOL_BOT.get(tool), cost_usd=round(cost_usd, 6))
        self.inv.steps.append(s)
        self.inv.budget["used"] = float(n)
        self.inv.budget["usd_used"] = round(self.inv.budget.get("usd_used", 0.0) + cost_usd, 6)
        self.emit("agent.step", {"step": s.model_dump()})
        text = f"**Krok {n}** · `{tool}` — {summary}" + (f" _{why}_" if why else "") + "\n\n"
        for i in range(0, len(text), self.delta_chunk):
            self.emit("casefile.delta", {"step_n": n, "text_delta": text[i:i + self.delta_chunk]})
        self.save()
        return s

    def note(self, text: str) -> None:
        """Free case-file text not tied to a tool call (analyst steer, Sędzia remarks)."""
        n = len(self.inv.steps)
        self.emit("casefile.delta", {"step_n": n, "text_delta": text if text.endswith("\n\n") else text + "\n\n"})

    def decision(self, node_id: str, question: str, options: list[str]) -> None:
        self.inv.pending_decision = {"node_id": node_id, "question": question, "options": options}
        d = {"node_id": node_id, "question": question, "options": options}
        if self.defer:
            self._deferred.append(d)
        else:
            self.emit("investigation.decision", d)
        self.save()

    def flush(self) -> None:
        for d in self._deferred:
            self.emit("investigation.decision", d)
        self._deferred = []

    def conclude(self, text: str, refs: list[str] | None = None) -> None:
        self.inv.conclusions.append({"text": text, "evidence_refs": refs or []})

    def done(self, summary: dict, status: str = "done") -> None:
        self.inv.status = status
        self.emit("investigation.done", {"summary": summary})
        self.save()

    def save(self) -> None:
        if self.save_path:
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.save_path.with_suffix(".tmp")
            tmp.write_text(self.inv.model_dump_json(indent=1), encoding="utf-8")
            tmp.replace(self.save_path)

    # ------------------------------------------------------------------ views
    def domains(self) -> list[InvestigationNode]:
        return [n for n in self.nodes.values() if n.kind == "domain"]

    def candidates(self) -> list[InvestigationNode]:
        seed = dom_id(self.inv.seed)
        return [n for n in self.domains() if n.id != seed and n.status in ("new", "to_decide", "in_progress")]
