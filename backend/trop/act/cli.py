"""`trop act …` — takedown packages (nothing is ever sent).

    trop act package <campaign_id> [--kind bundle] [--no-llm] [--out DIR] [--submit]
    trop act list · trop act show <ACT-id> · trop act rules <campaign_id> [--test]
    trop act test-rule <kind> <body> [--campaign ID]
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="Act — one takedown package per campaign (DSA art. 16, CERT PL, STIX 2.1)", no_args_is_help=True)


@app.command("package")
def package(campaign_id: str, kind: str = typer.Option("bundle"), no_llm: bool = typer.Option(False, "--no-llm"),
            out: Optional[Path] = typer.Option(None, help="also write pdf/json/stix/misp/csv/certpl here"),
            submit: bool = typer.Option(False, help="mark as 'sent' (prepared + exported + logged; NOTHING is sent)")) -> None:
    """Build the package for a campaign (KMP-017 = fictional demo; LAB-A / A = real labelled campaign A)."""
    from trop.schema import ActPackageCreate

    from . import service as S
    pkg = S.create_package(ActPackageCreate(campaign_id=campaign_id, kind=kind), use_llm=not no_llm)
    typer.echo(f"{pkg.id} · {pkg.campaign_id} · {pkg.status} · {json.dumps(pkg.contents, ensure_ascii=False)}")
    typer.echo("\n" + pkg.notice_text + "\n")
    for r in pkg.recipients:
        typer.echo(f"  [{'x' if r['enabled'] else ' '}] {r['label']:<34} {r['progress']['total']}")
    if out:
        out.mkdir(parents=True, exist_ok=True)
        for fmt in ("pdf", "json", "stix", "misp", "csv", "certpl"):
            data, _, name = S.download(pkg.id, fmt)
            (out / name).write_bytes(data)
            typer.echo(f"  -> {out / name} ({len(data)} B)")
    if submit:
        p = S.submit(pkg.id)
        typer.echo(f"{p.id}: {p.status} at {p.sent_at} · {p.disclaimer}")


@app.command("list")
def list_() -> None:
    from . import service as S
    for p in S.list_packages():
        typer.echo(f"{p.id} {p.campaign_id:<10} {p.kind:<7} {p.status:<6} {p.created_at} {json.dumps(p.contents)}")


@app.command("show")
def show(pid: str) -> None:
    from . import service as S
    typer.echo(S.get_package(pid).model_dump_json(indent=1))


@app.command("rules")
def rules_cmd(campaign_id: str, test: bool = typer.Option(True)) -> None:
    from . import service as S
    for r in S.rules(campaign_id):
        line = f"{r.kind:<15} {r.body}"
        if test:
            t = S.test_rule(r.kind, r.body, campaign_id)
            line += f"\n{'':<15} hits {t.hits} · tp {t.tp} · review {t.needs_review} · benign {t.benign_hits}/{t.benign_total} · precision {t.precision}"
        typer.echo(line)


@app.command("test-rule")
def test_rule_cmd(kind: str, body: str, campaign: Optional[str] = typer.Option(None)) -> None:
    from . import service as S
    typer.echo(S.test_rule(kind, body, campaign).model_dump_json())
