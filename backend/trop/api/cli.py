"""`trop serve` and the `trop demo` sub-app (record | replay | generate)."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import typer

app = typer.Typer(help="Demo recordings of SSE streams (F6 fallback): generate | record | replay | list", no_args_is_help=True)


def serve(
    host: str = typer.Option("127.0.0.1", help="Bind address (never 0.0.0.0 on the host; inside Docker the compose maps it)"),
    port: int = typer.Option(18000, help="API port"),
    mock: bool = typer.Option(False, "--mock", help="Serve the fictional demo universe (TROP_MODE=mock)"),
    reload: bool = typer.Option(False, help="Auto-reload (dev)"),
) -> None:
    """Run the API (uvicorn). Docs at /api/v1/docs, OpenAPI at /api/v1/openapi.json."""
    import uvicorn
    if mock:
        os.environ["TROP_MODE"] = "mock"
    uvicorn.run("trop.api.app:app", host=host, port=port, reload=reload, log_level="info", proxy_headers=True)


@app.command("generate")
def generate(out: Path = typer.Option(None, help="Directory (default: package trop/api/replay and data/replay)")) -> None:
    """(Re)generate the canned demo recordings from the mock fixtures."""
    from trop.api import streams
    for p in streams.generate_canned(out or streams.PKG_REPLAY):
        typer.echo(f"wrote {p}")
    if out is None:
        streams.ensure_replay_files()


@app.command("record")
def record(
    url: str = typer.Argument(..., help="SSE URL, e.g. http://127.0.0.1:18000/api/v1/jobs/JOB-X/stream"),
    name: str = typer.Option("demo-analyze", help="Recording name -> <replay_dir>/<name>.jsonl"),
    max_seconds: float = typer.Option(120.0),
) -> None:
    """Record a live SSE stream with original timing."""
    from trop.api import streams
    out = streams.replay_dir() / f"{name}.jsonl"
    n = asyncio.run(streams.record_stream(url, out, max_seconds))
    typer.echo(f"recorded {n} events -> {out}")


@app.command("replay")
def replay(name: str = typer.Argument("demo-analyze"), speed: float = typer.Option(1.0)) -> None:
    """Print a recording to the terminal with its original timing."""
    import time
    from trop.api import streams
    kind = name.split("-", 1)[-1] if "-" in name else name
    p = streams.find_recording(name, kind) or streams.find_recording(name.split("-")[0], kind)
    if not p:
        raise typer.Exit(f"no recording {name}")
    t0 = time.monotonic()
    for off, ev in streams.load_recording(p):
        time.sleep(max(0.0, off / speed - (time.monotonic() - t0)))
        typer.echo(f"{off:6.2f}s  {ev.type:20s} {str(ev.data)[:90]}")


@app.command("list")
def list_() -> None:
    """List available recordings."""
    from trop.api import streams
    for d in (streams.replay_dir(), streams.PKG_REPLAY):
        for f in sorted(d.glob("*.jsonl")):
            typer.echo(f"{f}  ({sum(1 for _ in f.open())} events)")
