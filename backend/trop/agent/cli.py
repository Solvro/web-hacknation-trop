"""`trop agent …` — White Rabbit from the command line.

    trop agent run <seed> [--budget 20] [--usd 1.0] [--offline] [--planner auto|llm|heuristic] [--record FILE] [--campaign ID]
    trop agent show <INV-id>          # case file as markdown
    trop agent replay <file.jsonl>    # print a recorded stream (timing kept with --speed)
    trop agent demo [--out FILE]      # regenerate the fictional velmoria.click demo stream
    trop agent promote <INV-id> <campaign> <node ids…|--all>
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import typer

app = typer.Typer(help="White Rabbit — agent investigation from one seed", no_args_is_help=True)


def _printer(verbose: bool):
    def emit(typ: str, data: dict) -> None:
        if typ == "agent.step":
            s = data["step"]
            typer.echo(f"[{s['n']:>2}] {s['bot'] or '':<10} {s['tool']:<22} {s['query'][:50]:<50}  {s['result_summary']}"
                       + (f"  (${s['cost_usd']:.4f})" if s.get("cost_usd") else ""))
        elif typ == "investigation.decision":
            typer.echo(f"     ? Sędzia: {data['question']}  {data['options']}")
        elif typ == "investigation.done":
            sm = data["summary"]
            typer.echo(json.dumps({k: v for k, v in sm.items() if k != "candidates"}, ensure_ascii=False, indent=1))
        elif verbose and typ == "graph.node_added":
            n = data["node"]
            typer.echo(f"     + {n['kind']:<12} {n['label'][:60]:<60} {n.get('status') or ''} {n.get('branch') or ''}")
    return emit


@app.command("run")
def run_cmd(seed: str, budget: int = typer.Option(20, help="step budget (tool calls)"),
            usd: float = typer.Option(1.0, help="hard USD cap for this run"),
            offline: bool = typer.Option(False, help="cache-only: no network, cached LLM + enrichment"),
            planner: str = typer.Option("auto", help="auto (LLM, heuristic fallback) | llm | heuristic"),
            model: str = typer.Option("pro", help="pro | flash | <model id>"),
            campaign: str | None = typer.Option(None, help="campaign the seed belongs to (statuses 'in_campaign')"),
            record: Path | None = typer.Option(None, help="also write the SSE replay here (data/replay/*.jsonl format)"),
            captures: int = typer.Option(1, help="sandbox capture budget"),
            verbose: bool = typer.Option(False, "-v")) -> None:
    """Investigate from one seed domain and print the steps live."""
    from trop.schema import InvestigationCreate

    from .service import run_investigation
    t0 = time.time()
    inv = run_investigation(InvestigationCreate(seed=seed, campaign_id=campaign, budget_steps=budget, offline=offline),
                            _printer(verbose), usd_cap=usd, model=model, planner=planner, record=record, captures=captures)
    typer.echo(f"{inv['id']} {inv['status']} · {len(inv['steps'])} steps · ${inv['budget'].get('usd_used', 0):.4f} · "
               f"{time.time() - t0:.0f}s · data/investigations/{inv['id']}/")


@app.command("show")
def show(iid: str) -> None:
    from .service import get_investigation
    inv = get_investigation(iid)
    typer.echo(f"# {inv.id} · {inv.seed} · {inv.status}\n")
    for s in inv.steps:
        typer.echo(f"**Krok {s.n}** · `{s.tool}` ({s.query}) — {s.result_summary} _{s.why}_\n")
    typer.echo("## Wnioski\n" + "\n".join(f"- {c['text']}" for c in inv.conclusions))
    doms = [n for n in inv.nodes if n.kind == "domain"]
    typer.echo(f"\n## Domeny ({len(doms)})\n" + "\n".join(
        f"- {n.label} · {n.status} · {n.meta.get('level')} · {'nowa' if n.is_new else 'znana'}" for n in doms))


@app.command("replay")
def replay(path: Path, speed: float = typer.Option(0.0, help="0 = no waiting, 1 = real time")) -> None:
    last = 0.0
    em = _printer(True)
    for ln in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(ln)
        if speed:
            time.sleep(max(0.0, (r["t"] - last) / speed))
        last = r["t"]
        em(r["type"], r["event"]["data"])


@app.command("demo")
def demo(out: Path = typer.Option(Path(__file__).parent / "replay" / "velmoria_demo.jsonl")) -> None:
    """Regenerate the fictional velmoria.click run (BRIEF.md universe) through the real event builder."""
    from .demo import build_demo
    inv = build_demo(out)
    typer.echo(f"{out}: {len(inv.steps)} steps, {len([n for n in inv.nodes if n.kind == 'domain'])} domains")


@app.command("promote")
def promote_cmd(iid: str, campaign: str, node_ids: list[str] = typer.Argument(None),
                all_: bool = typer.Option(False, "--all", help="every non-skipped candidate")) -> None:
    from .service import get_investigation, promote
    inv = get_investigation(iid)
    ids = node_ids or []
    if all_:
        ids = [n.id for n in inv.nodes if n.kind == "domain" and n.status in ("new", "to_decide") and not n.meta.get("seed")]
    typer.echo(json.dumps(promote(inv, campaign, ids)))


if __name__ == "__main__":
    app(sys.argv[1:])
