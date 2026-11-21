"""`trop db migrate | status | seed | snapshot`."""
from __future__ import annotations

import time
from pathlib import Path

import typer

from trop.config import settings

app = typer.Typer(help="Postgres: migrations, engine corpus seed, snapshots.", no_args_is_help=True)


@app.command()
def status() -> None:
    """List migrations and whether they are applied."""
    from .db import status as st
    for name, ok in st():
        typer.echo(("applied " if ok else "PENDING ") + name)


@app.command()
def migrate(backup: bool = typer.Option(True, help="pg_dump -Fc to data/backup/ before applying pending migrations")) -> None:
    """Apply pending migrations from backend/migrations (additive)."""
    from .db import dump, migrate as mg, status as st
    pending = [n for n, ok in st() if not ok]
    if not pending:
        typer.echo("nothing to apply")
        return
    if backup:
        p = dump(Path(settings.data_dir) / "backup" / f"pre_migrate_{time.strftime('%Y%m%d_%H%M%S')}.dump")
        typer.echo(f"backup -> {p}")
    for n in mg():
        typer.echo(f"applied {n}")


@app.command()
def seed(with_dane: bool = typer.Option(False, help="also seed the labelled DANE items as known (demo)")) -> None:
    """Write the engine corpus (labelled sample_v1 [+ DANE]) into the DB."""
    import os
    os.environ["TROP_NO_LIVE"] = "1"
    from trop.engine.corpus import Corpus
    from .corpus import save_corpus
    c = Corpus.load(include_dane=with_dane)
    typer.echo(save_corpus(c))


@app.command()
def snapshot(out: str = typer.Option("", help="default: data/seed/trop_seed.dump")) -> None:
    """pg_dump -Fc snapshot for judges (restore: pg_restore -d <url> --clean <file>)."""
    from .db import dump
    p = dump(Path(out) if out else Path(settings.data_dir) / "seed" / "trop_seed.dump")
    typer.echo(f"snapshot -> {p}")
