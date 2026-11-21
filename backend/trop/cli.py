"""`trop` CLI. Each workstream registers a Typer sub-app in its own module (`trop/<pkg>/cli.py: app`).

This file is owned by the integrator; workstreams do NOT edit it — they create `trop/<pkg>/cli.py` with
`app = typer.Typer()` and commands, and it is picked up here automatically.
"""
from __future__ import annotations

import importlib

import typer

app = typer.Typer(help="TROP — follow the fake", no_args_is_help=True)


@app.callback()
def _root() -> None:
    """TROP — follow the fake."""

# name -> module providing `app` (Typer) ; top-level commands -> (module, function)
SUBAPPS = {
    "db": "trop.store.cli",          # db migrate | seed | snapshot      (WS1)
    "eval": "trop.eval.cli",         # eval [--dane]                     (WS1)  G-ENGINE
    "engine": "trop.engine.cli",     # engine rebuild (re-cluster DB)     (WS1)
    "gallery": "trop.media.cli",     # gallery build | match             (WS4)
    "media": "trop.media.cli_media", # media video|asr <path>            (WS4)
    "enrich": "trop.enrich.cli",     # enrich <domain|--all>             (WS5)
    "hunter": "trop.hunter.cli",     # hunter run <source>               (WS5)
    "oracle": "trop.oracle.cli",     # oracle run | backtest             (WS5)
    "agent": "trop.agent.cli",       # agent run <seed>                  (WS6)
    "act": "trop.act.cli",           # act package <campaign>            (WS6)
    "demo": "trop.api.cli",          # demo record | replay              (WS2)
    "export": "trop.eval.cli_export",  # export dataset                  (WS1)
}
TOP = {
    "ingest": ("trop.ingest.cli", "ingest"),     # ingest <path> [--source]   (WS1)
    "analyze": ("trop.ingest.cli", "analyze"),   # analyze <url|file>         (WS1)
    "batch": ("trop.ingest.cli", "batch"),       # batch <dir|zip> --out results.csv  (WS1)  G-BATCH
    "capture": ("trop.capture.cli", "capture"),  # capture <url>              (WS5)
    "serve": ("trop.api.cli", "serve"),          # serve [--mock]             (WS2)
    "worker": ("trop.worker.cli", "worker"),     # worker                     (WS2)
}

for _name, _mod in SUBAPPS.items():
    try:
        app.add_typer(importlib.import_module(_mod).app, name=_name)
    except ModuleNotFoundError as e:  # not built yet
        if not str(e).startswith("No module named 'trop."):
            raise
for _name, (_mod, _fn) in TOP.items():
    try:
        app.command(_name)(getattr(importlib.import_module(_mod), _fn))
    except ModuleNotFoundError as e:
        if not str(e).startswith("No module named 'trop."):
            raise


@app.command()
def schema(out: str = "-") -> None:
    """Dump the contract JSON schema (web types are generated from it)."""
    import json
    import sys

    from trop.schema import json_schema
    s = json.dumps(json_schema(), ensure_ascii=False, indent=1)
    (sys.stdout.write(s) if out == "-" else open(out, "w").write(s))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
