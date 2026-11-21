"""`trop engine …` — corpus, calibration, explanations."""
from __future__ import annotations

import sys

import typer

app = typer.Typer(help="Déjà Vu engine: known corpus, calibration, explanations.", no_args_is_help=True)


@app.command("build-corpus")
def build_corpus(with_dane: bool = typer.Option(False, help="also add the labelled DANE items (demo DB; never for evaluation)"),
                 offline: bool = typer.Option(True, help="never call live models")) -> None:
    """(Re)build data/corpus/known.json from the labelled sample (re-extracted, or precomputed if raw is absent)."""
    import os
    if offline:
        os.environ["TROP_NO_LIVE"] = "1"
    from .corpus import Corpus, corpus_path
    c = Corpus.load(rebuild=True, include_dane=with_dane)
    typer.echo(f"{len(c.incidents)} incidents, {len(c.campaigns)} campaigns, {len(c.operators)} operators, "
               f"{len(c.operations)} operations -> {corpus_path() if not with_dane else corpus_path().with_name('known_with_dane.json')}")


@app.command()
def calibrate() -> None:
    """Fit isotonic score_campaign -> P(same campaign) on the labelled pairs; writes trop/engine/calibration/engine_1.json."""
    import os
    os.environ["TROP_NO_LIVE"] = "1"
    from . import calibration
    c = calibration.build_default()
    typer.echo(f"{c['n_pairs']} pairs ({c['n_pos']} positive): P(tau=5) = {c['summary']['p_at_tau']} -> "
               f"{calibration.path_for()}")


@app.command()
def rebuild() -> None:
    """build-corpus + calibrate."""
    build_corpus(with_dane=False, offline=True)
    calibrate()


@app.command()
def explain(a: str, b: str) -> None:
    """LinkExplanation between two corpus incidents (or an incident and a KMP campaign)."""
    from . import service
    sys.stdout.write(service.explain(a, b).model_dump_json(indent=1) + "\n")
