"""White Rabbit: the budgeted LLM tool-use loop (Gemini Pro function calling via the model gateway).

Every turn rebuilds one compact prompt (case state + tool log + analyst notes) instead of replaying native
function-call turns: no provider-specific thought signatures, short contexts, and the gateway's sha256 cache makes a
run replay offline when the tool results come from the (also cached) enrichment layer.

If the LLM is unavailable (offline without a cache hit, no key, budget exhausted) the loop switches to a
deterministic planner that runs the same tools in a fixed, sensible order, so an investigation always completes.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Iterator

from .case import LEVEL_RANK, Case, dom_id
from .tools import Ctx, ToolResult, _apex, query_of, run_tool, specs

log = logging.getLogger("trop.agent.loop")

LLM = Callable[[list[dict], list[dict]], dict]
MAX_CALLS_PER_TURN = 3

SYSTEM = """You are White Rabbit, the investigator of TROP (NASK scam-ad attribution). From one seed domain you find the
rest of the scam operation: sibling domains, ads and advertisers, with explainable evidence. You work by calling tools.

Evidence levels (strongest first):
- operator: same account — kit tenant UUID, FB pixel, CAPI gateway, the same Cloudflare NS pair, GTM/Ads id.
- campaign: same operation — lander id, rare shared asset hash, the same certificate (SAN) or registration/cert batch
  minutes apart, the same masked headline template.
- platform: shared commercial tooling — multi-tenant kit endpoints/paths, an SDK bundle loaded by hundreds of unrelated
  sites. Never enough alone. infra: Cloudflare IPs, ASN, registrar — weight zero alone.

Method: start with db_search on the seed (our corpus), pivot on its RAREST operator/campaign traces; pivot outward with
urlscan_search 'hash:<sha256>' on a rare asset (and on a kit-wide asset only to enumerate kit siblings, which are
platform-level); crtsh/rdap/dns_ns confirm registration/cert batches and the NS pair; certpl_check tells which domains
still need reporting; adlib_search finds ads promoting them. Call propose_link to state your judgement (needs_decision
when a candidate matches the kit but conflicts on certificate/hosting or fits another campaign), then finish with 2-4
conclusions. Be efficient: do not repeat a query, 1-3 tool calls per turn, stay within the step budget.
Every tool call takes a `why`: one short sentence in Polish. Conclusions are in Polish. Never invent domains or numbers:
use only what tools returned."""


def default_llm(model: str = "pro") -> LLM:
    from trop.media.gateway import gateway

    def call(messages: list[dict], tools: list[dict]) -> dict:
        return gateway.llm("white_rabbit", messages, tools=tools, model=model)
    return call


# ============================================================================== control (steer / stop)
class Control:
    """Commands from the analyst. `poll()` returns new commands; sources: in-memory queue + an append-only file
    (data/investigations/<id>/control.jsonl) so the API process can steer a worker process."""

    def __init__(self, path=None) -> None:
        from pathlib import Path
        self.path = Path(path) if path else None
        self.queue: list[dict] = []
        self._pos = 0

    def put(self, cmd: dict) -> None:
        self.queue.append(cmd)

    def poll(self) -> list[dict]:
        out, self.queue = self.queue, []
        if self.path and self.path.is_file():
            lines = self.path.read_text(encoding="utf-8").splitlines()
            for ln in lines[self._pos:]:
                try:
                    out.append(json.loads(ln))
                except json.JSONDecodeError:
                    pass
            self._pos = len(lines)
        return out


# ============================================================================== prompt
def _state(ctx: Ctx) -> dict:
    case = ctx.case
    seed = dom_id(_apex(ctx.seed))
    cands = [n for n in case.domains() if n.id != seed]
    cands.sort(key=lambda n: (-LEVEL_RANK.get(n.meta.get("level", "platform"), 0), n.label))
    lv: dict[str, int] = {}
    for n in cands:
        lv[n.meta.get("level", "?")] = lv.get(n.meta.get("level", "?"), 0) + 1
    return {
        "domains_in_graph": len(cands), "by_level": lv,
        "new_to_us": sum(1 for n in cands if n.is_new), "status": {s: sum(1 for n in cands if n.status == s)
                                                                    for s in ("new", "in_campaign", "to_decide", "skipped")},
        "candidates": [f"{n.label} [{n.meta.get('level', '?')}{', known' if n.meta.get('known_in_db') else ''}"
                       f"{', certpl=' + str(n.meta['certpl']) if 'certpl' in n.meta else ''}"
                       f"{', ' + n.status if n.status in ('to_decide', 'skipped') else ''}]" for n in cands[:45]],
        "more": max(0, len(cands) - 45),
    }


def build_messages(ctx: Ctx, history: list[dict], notes: list[str], steps_left: int, usd_left: float) -> list[dict]:
    inv = ctx.case.inv
    log_lines = []
    for i, h in enumerate(history):
        line = f"#{h['n']} {h['tool']}({json.dumps(h['args'], ensure_ascii=False)[:200]}) -> {h['summary']}"
        if i >= len(history) - 3:
            line += "\n   result: " + json.dumps(h["view"], ensure_ascii=False, default=str)[:3000]
        log_lines.append(line)
    pending = inv.pending_decision
    body = (
        f"Seed: {ctx.seed}\nCampaign: {ctx.campaign_id or 'none given'}\n"
        f"Budget left: {steps_left} tool calls, ${usd_left:.2f}.\n"
        f"Case graph now: {json.dumps(_state(ctx), ensure_ascii=False)}\n"
        + (f"Pending analyst decision: {json.dumps(pending, ensure_ascii=False)}\n" if pending else "")
        + ("Analyst notes (follow them):\n- " + "\n- ".join(notes) + "\n" if notes else "")
        + ("Tool log:\n" + "\n".join(log_lines) if log_lines else "No tool calls yet.")
        + ("\n\nBudget almost used: call propose_link for the strongest candidates and finish now." if steps_left <= 2 else
           "\n\nDecide the next tool call(s).")
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": body}]


# ============================================================================== deterministic planner
def heuristic_plan(ctx: Ctx, history: list[dict]) -> Iterator[tuple[str, dict]]:
    """Fixed, sensible pivot order (fallback when no LLM). Reads results from `history` as it goes."""
    seed = _apex(ctx.seed)
    yield "db_search", {"query": seed, "why": "Zaczynam od tego, co już wiemy o domenie."}
    yield "crtsh", {"domain": seed, "why": "Certyfikaty z tej samej partii zwykle należą do tego samego operatora."}
    yield "dns_ns", {"domain": seed, "why": "Para NS wskazuje konto Cloudflare operatora."}
    view = next((h["view"] for h in history if h["tool"] == "db_search"), {}) or {}
    traces = view.get("traces") or []
    hashes = [t for t in traces if t.get("type") == "asset_sha256"]
    rare = sorted([t for t in hashes if t.get("level") != "platform"], key=lambda t: t.get("df") or 0)
    wide = sorted([t for t in hashes if t.get("level") == "platform"], key=lambda t: -(t.get("df") or 0))
    for t in (rare[:1] + wide[:1]) or []:
        yield "urlscan_search", {"query": f"hash:{t['value']}", "why": "Szukam innych stron ładujących ten sam plik."}
    if not hashes:
        yield "urlscan_search", {"query": f"domain:{seed}", "why": "Historia skanów domeny w urlscan."}
    incs = view.get("incidents") or []
    if incs:
        yield "incident_neighborhood", {"incident_id": incs[0]["id"], "why": "Sprawdzam sąsiedztwo incydentu w bazie."}
    yield "rdap", {"domain": seed, "why": "Data rejestracji i rejestrator."}
    yield "certpl_check", {"all_candidates": True, "why": "Domeny spoza listy to kandydaci do zgłoszenia."}
    yield "adlib_search", {"terms": seed.split(".")[0], "active": "ALL", "why": "Czy domeny są promowane reklamami."}
    strong = [n.label for n in ctx.case.domains() if n.meta.get("level") in ("operator", "campaign") and n.id != dom_id(seed)]
    weak = [n.label for n in ctx.case.domains() if n.meta.get("level") in ("platform", "infra") and n.id != dom_id(seed)]
    if strong:
        yield "propose_link", {"domains": strong, "confidence": "high", "rationale": "wspólny ślad operatora lub kampanii",
                               "why": "Dowody na poziomie operatora/kampanii."}
    if weak:
        yield "propose_link", {"domains": weak, "confidence": "medium", "rationale": "tylko wspólny kit (platforma)",
                               "why": "Wspólna platforma to za mało na operatora."}
    yield "finish", {"conclusions": [], "why": "Podsumowanie."}


# ============================================================================== run
def _apply_controls(ctx: Ctx, control: Control | None, notes: list[str]) -> list[str]:
    """Apply analyst commands; -> control verbs in order ('stop' | 'pause' | 'resume')."""
    if control is None:
        return []
    verbs: list[str] = []
    for c in control.poll():
        typ = c.get("type") or ("decision" if c.get("choice") else "steer")
        if typ in ("stop", "pause", "resume"):
            verbs.append(typ)
        if typ == "decision" or c.get("choice"):
            nid = c.get("node_id") or (ctx.case.inv.pending_decision or {}).get("node_id")
            ch = str(c.get("choice") or "").lower()
            join = ch.startswith(("dołącz", "dolacz", "join", "accept", "tak", "yes", "dodaj"))
            if nid in ctx.case.nodes:
                n = ctx.case.nodes[nid]
                ctx.case.node(nid, n.kind, n.label, status="new" if join else "skipped",
                              meta={"decision": "join" if join else "skip", "decided_by": "analyst"})
                ctx.case.note(f"_Analityk: {n.label} → {'dołącz' if join else 'pomiń'}._")
                notes.append(f"Analyst decided {n.label}: {'JOIN' if join else 'SKIP'}.")
            if (ctx.case.inv.pending_decision or {}).get("node_id") == nid:
                ctx.case.inv.pending_decision = None
        if c.get("message"):
            notes.append(str(c["message"])[:300])
            ctx.case.note(f"_Analityk: {str(c['message'])[:300]}_")
    return verbs


def _control_state(verbs: list[str], paused: bool) -> tuple[bool, bool]:
    """-> (stop, paused) after applying verbs in order."""
    stop = False
    for v in verbs:
        if v == "stop":
            stop = True
        elif v == "pause":
            paused = True
        elif v == "resume":
            paused = False
    return stop, paused


def run(ctx: Ctx, *, llm: LLM | None = None, steps: int = 20, usd_cap: float = 1.0, control: Control | None = None,
        planner: str = "auto", sleep: Callable[[float], None] = time.sleep, pause_timeout_s: float = 1800) -> dict:
    """Run the investigation to completion. planner: auto (LLM, heuristic fallback) | llm | heuristic."""
    case, inv = ctx.case, ctx.case.inv
    inv.budget.update({"steps": float(steps), "usd": float(usd_cap)})
    inv.status = "running"
    seed_id = None
    history: list[dict] = []
    notes: list[str] = []
    use_llm = planner in ("auto", "llm")
    llm = llm or (default_llm() if use_llm else None)
    plan: Iterator[tuple[str, dict]] | None = None if use_llm else heuristic_plan(ctx, history)
    finished = False
    stopped = False
    empty_turns = 0
    from .tools import _ensure_seed
    seed_id = _ensure_seed(ctx)

    def do(name: str, args: dict, cost: float) -> ToolResult:
        tgt = args.get("domain") or (args.get("query") if name == "db_search" else None)
        nid = dom_id(_apex(tgt)) if tgt else None
        prev = case.nodes[nid].status if nid in case.nodes else None
        if nid in case.nodes and prev not in ("in_campaign", "in_progress", "skipped"):
            case.set_status(nid, "in_progress")
        res = run_tool(name, args, ctx)
        if nid in case.nodes and case.nodes[nid].status == "in_progress" and nid != seed_id:
            case.set_status(nid, prev or "new")
        why = str(args.get("why") or "")[:200]
        case.step(name, query_of(name, args), res.summary, why, res.produced, cost)
        history.append({"n": len(inv.steps), "tool": name, "args": {k: v for k, v in args.items() if k != "why"},
                        "summary": res.summary, "view": res.view})
        return res

    while not finished:
        stop, paused = _control_state(_apply_controls(ctx, control, notes), False)
        if paused and not stop:
            inv.status = "paused"
            case.save()
            t0 = time.monotonic()
            while paused and not stop and time.monotonic() - t0 < pause_timeout_s:
                sleep(1.0)
                stop, paused = _control_state(_apply_controls(ctx, control, notes), paused)
            inv.status = "running"
        if stop:
            stopped = True
            break
        used = len(inv.steps)
        if used >= steps:
            break
        usd_used = inv.budget.get("usd_used", 0.0)
        if usd_used >= usd_cap and plan is None:
            case.note("_Budżet kosztowy wyczerpany — dokańczam bez modelu._")
            plan = heuristic_plan(ctx, history)
        if plan is None:
            msgs = build_messages(ctx, history, notes, steps - used, usd_cap - usd_used)
            r = llm(msgs, specs(inv.tools or None)) if llm else {"missing": True}
            cost = float(r.get("cost_usd") or 0.0) if not r.get("cached") else 0.0
            if r.get("missing") or r.get("error"):
                if planner == "llm":
                    case.note(f"_Model niedostępny: {str(r.get('error'))[:120]}._")
                    break
                case.note("_Model niedostępny — przechodzę na plan deterministyczny._")
                plan = heuristic_plan(ctx, history)
                continue
            calls = r.get("tool_calls") or []
            if not calls:
                empty_turns += 1
                if r.get("text"):
                    notes.append("(previous answer had no tool call — you MUST call a tool; call finish when done)")
                if empty_turns >= 2:
                    break
                inv.budget["usd_used"] = round(inv.budget.get("usd_used", 0.0) + cost, 6)
                continue
            empty_turns = 0
            for i, c in enumerate(calls[:MAX_CALLS_PER_TURN]):
                if len(inv.steps) >= steps:
                    break
                res = do(c.get("name", ""), c.get("args") or {}, cost if i == 0 else 0.0)
                if res.stop:
                    finished = True
                    break
        else:
            try:
                name, args = next(plan)
            except StopIteration:
                break
            res = do(name, args, 0.0)
            finished = res.stop
    return finalize(ctx, stopped=stopped)


def finalize(ctx: Ctx, stopped: bool = False) -> dict:
    case, inv = ctx.case, ctx.case.inv
    seed = dom_id(_apex(ctx.seed))
    if seed in case.nodes and case.nodes[seed].status == "in_progress":
        case.set_status(seed, "in_campaign" if _apex(ctx.seed) in ctx.campaign_domains else "new")
    for n in case.domains():
        if n.status == "in_progress":
            case.set_status(n.id, "new")
    cands = [n for n in case.domains() if n.id != seed and n.status != "skipped"]
    new = [n for n in cands if n.is_new]
    lv = {k: sum(1 for n in cands if n.meta.get("level") == k) for k in ("operator", "campaign", "platform", "infra")}
    not_listed = [n for n in cands if n.meta.get("certpl") is False]
    ads = [n for n in case.nodes.values() if n.kind == "ad"]
    n_ads = sum(int(n.meta.get("ads") or 0) for n in ads)
    advertisers = sorted({a for n in ads for a in n.meta.get("advertisers", [])})
    tonight = sum(1 for n in case.domains() if n.meta.get("certs_tonight"))
    if not inv.conclusions:
        strong = [n for n in cands if n.meta.get("level") in ("operator", "campaign")]
        if strong:
            ev = sorted({e.get("type") for n in strong for e in n.meta.get("evidence", []) if e.get("level") in ("operator", "campaign")})
            case.conclude(f"{len(strong)} domen dzieli z {_apex(ctx.seed)} ślady operatora lub kampanii ({', '.join(ev[:4])}).",
                          [n.id for n in strong[:8]])
        if lv["platform"]:
            case.conclude(f"{lv['platform']} kolejnych domen używa tej samej platformy (kit), co samo w sobie nie dowodzi tego samego operatora.",
                          [n.id for n in cands if n.meta.get("level") == "platform"][:8])
        if not_listed:
            case.conclude(f"{len(not_listed)} z {len(cands)} domen nie ma na liście CERT PL — do zgłoszenia.", ["n-certpl"])
    summary = {
        "conclusions": inv.conclusions, "steps": len(inv.steps), "domains_found": len(cands), "new_domains": len(new),
        "known_in_db": sum(1 for n in cands if n.meta.get("known_in_db")),
        "in_campaign": sum(1 for n in cands if n.status == "in_campaign"),
        "to_decide": sum(1 for n in cands if n.status == "to_decide"),
        "skipped": sum(1 for n in case.domains() if n.status == "skipped"), "by_level": lv,
        "not_on_certpl": len(not_listed), "ads": n_ads, "advertisers": len(advertisers), "certs_tonight": tonight,
        "usd": round(inv.budget.get("usd_used", 0.0), 4), "candidates": [n.label for n in cands],
    }
    case.done(summary, status="stopped" if stopped else "done")
    return summary
