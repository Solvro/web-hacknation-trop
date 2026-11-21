"""`trop worker` — arq worker on Redis."""
from __future__ import annotations

import typer


def worker(burst: bool = typer.Option(False, help="Exit when the queue is empty")) -> None:
    """Run the arq worker (jobs: analyze, batch, capture, enrich, hunt, oracle, agent, act)."""
    from arq import run_worker

    from trop.worker.settings import WorkerSettings
    run_worker(WorkerSettings, burst=burst)  # type: ignore[arg-type]
