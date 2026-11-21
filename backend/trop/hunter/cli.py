"""`trop hunter run <meta|certpl|urlscan|google>` · `trop hunter sources` · `trop hunter runs`."""
from __future__ import annotations

import json
from typing import Optional

import typer

app = typer.Typer(help="Hunter: live sources (Meta Ad Library, CERT PL, urlscan, Google ATC)", no_args_is_help=True)


@app.command()
def run(
    source: str = typer.Argument(..., help="meta | certpl | urlscan | google"),
    term: Optional[list[str]] = typer.Option(None, "--term", help="meta: search term (repeatable); default lure phrases + persons"),
    queries: int = typer.Option(6, help="meta: max queries"),
    per_query: int = typer.Option(25, help="meta: ads per query"),
    snapshots: int = typer.Option(6, help="meta: ad snapshots to render for CTA links"),
    captures: int = typer.Option(2, help="meta: landing captures (politeness budget applies)"),
    no_capture: bool = typer.Option(False, "--no-capture"),
    local: bool = typer.Option(False, "--local", help="capture without the Docker sandbox"),
    budget: int = typer.Option(40, help="urlscan: max searches"),
) -> None:
    from . import runner
    if source not in runner.RUNNERS:
        raise typer.BadParameter(f"source must be one of {sorted(runner.RUNNERS)}")
    if source == "meta":
        r = runner.run_meta(term or None, max_queries=queries, per_query=per_query, snapshot_limit=snapshots, capture_limit=captures,
                            capture=not no_capture, docker=not local)
    elif source == "urlscan":
        r = runner.run_urlscan(budget=budget)
    else:
        r = runner.RUNNERS[source]()
    typer.echo(json.dumps(r.model_dump(), ensure_ascii=False, indent=1))


@app.command()
def sources() -> None:
    from .sources import list_sources
    typer.echo(json.dumps([s.model_dump() for s in list_sources()], ensure_ascii=False, indent=1))


@app.command()
def runs(source: Optional[str] = None, limit: int = 20) -> None:
    from .sources import list_runs
    typer.echo(json.dumps([r.model_dump() for r in list_runs(source, limit)], ensure_ascii=False, indent=1))
