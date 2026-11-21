"""`trop oracle train|backtest|run|predictions|dna`."""
from __future__ import annotations

import json
from typing import Optional

import typer

app = typer.Typer(help="Oracle: predict campaign domains from certificate issuance", no_args_is_help=True)


@app.command()
def train(refresh: bool = typer.Option(False, help="re-read the DB / experiments"), timing: bool = typer.Option(False, help="(re)collect cert/first-seen timing via urlscan")) -> None:
    from . import data, service
    if timing:
        recs = data.load_training(refresh=True)
        data.save_training(data.add_timing(recs, progress=typer.echo))
    r = service.train(refresh=refresh and not timing)
    typer.echo(json.dumps(r, ensure_ascii=False, indent=1))


@app.command()
def backtest(train_frac: float = 0.6, fpr: float = 0.02, latency_h: float = 0.25, rows: int = 15) -> None:
    """Historical backtest: would the Oracle have flagged later kit-A domains from their certificate, and how early?"""
    from . import backtest as bt, data
    recs, neg = data.load_training(), data.load_negatives()
    res = bt.run_backtest(recs, neg, train_frac=train_frac, fpr=fpr, ct_latency_h=latency_h)
    res["summary"]["cv_auc_5fold"] = bt.cross_val_auc(recs, neg)
    (data.oracle_dir() / "backtest.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    typer.echo(json.dumps(res["summary"], ensure_ascii=False, indent=1))
    for r in [x for x in res["rows"] if x["flagged"] and x["lead_h"] is not None][:rows]:
        typer.echo(f"  would have flagged {r['domain']:<34} {r['lead_h']:>8.1f} h before first activity ({r['first_activity_source']})")


@app.command()
def run(once: bool = typer.Option(True, help="single poll"), certstream_s: float = 0.0, no_urlscan: bool = False,
        from_file: Optional[str] = typer.Option(None, "--from-file", help="replay a JSON list of cert sightings")) -> None:
    """Poll certificate sightings for the campaign TLDs and store predictions."""
    from . import ct, service
    if from_file:
        preds = service.predict(ct.from_file(from_file))
        typer.echo(json.dumps([p.model_dump() for p in preds], ensure_ascii=False, indent=1))
        return
    typer.echo(json.dumps(service.poll_once(not no_urlscan, certstream_s), indent=1))


@app.command()
def predictions(status: Optional[str] = None, limit: int = 30) -> None:
    from . import service
    typer.echo(json.dumps([p.model_dump() for p in service.list_predictions(status, limit)], ensure_ascii=False, indent=1))


@app.command()
def dna() -> None:
    from . import service
    d = service.get_dna()
    typer.echo(d.model_dump_json(indent=1) if d else "{}")


@app.command()
def metrics() -> None:
    from . import service
    typer.echo(service.get_metrics().model_dump_json(indent=1))
