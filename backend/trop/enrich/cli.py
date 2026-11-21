"""`trop enrich <domain>` | `trop enrich --incidents <json> [--out f]` | `trop enrich --seed` | `trop enrich --certpl-sync`."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="Enrichment (DNS/NS, RDAP, crt.sh, CERT PL), FS-cached, offline replay", add_completion=False)


@app.callback(invoke_without_command=True)
def enrich(
    domain: Optional[str] = typer.Argument(None, help="domain to enrich"),
    incidents: Optional[Path] = typer.Option(None, "--incidents", help="incidents JSON: adds infra.domains[].enrich"),
    out: Optional[Path] = typer.Option(None, "--out", help="output file (default: in place)"),
    providers: str = typer.Option("dns,rdap,crtsh,certpl", help="comma list"),
    all_domains: bool = typer.Option(False, "--all-domains", help="enrich every domain of an incident, not only the landing"),
    seed: bool = typer.Option(False, "--seed", help="pre-seed the cache from data/experiments/*/infra_enrich.json"),
    certpl_sync: bool = typer.Option(False, "--certpl-sync", help="download/refresh the CERT PL list"),
    seed_db: bool = typer.Option(False, "--seed-db", help="pre-seed the cache from the dev DB enrichment_cache (read-only)"),
) -> None:
    from . import certpl, enrich as E, seed as S
    prov = [p for p in providers.split(",") if p]
    if seed:
        typer.echo(json.dumps(S.seed_all()))
    if seed_db:
        typer.echo(json.dumps(S.seed_from_db()))
    if certpl_sync:
        typer.echo(json.dumps(certpl.sync()))
    if incidents:
        r = E.enrich_incidents_file(incidents, out, prov, only_landing=not all_domains,
                                    progress=lambda i, n: typer.echo(f"\r{i}/{n}", nl=False, err=True))
        typer.echo(json.dumps(r))
    elif domain:
        typer.echo(json.dumps(E.enrich_domain(domain, prov), indent=1, ensure_ascii=False))
    elif not (seed or certpl_sync or seed_db):
        raise typer.BadParameter("give a domain, --incidents, --seed or --certpl-sync")
