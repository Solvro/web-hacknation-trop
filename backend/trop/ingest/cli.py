"""Top-level commands `trop ingest`, `trop analyze`, `trop batch` (registered by trop/cli.py)."""
from __future__ import annotations

import csv
import json
import logging
import sys
import tempfile
import time
import traceback
from pathlib import Path

import typer

from trop.schema import BatchRow

log = logging.getLogger(__name__)


def _offline(flag: bool) -> None:
    import os
    if flag:
        os.environ["TROP_NO_LIVE"] = "1"


def ingest(path: str = typer.Argument(..., help="folder / file / zip / URL"),
           out: str = typer.Option("", help="write the Incident JSON here (default: stdout)"),
           inc_id: str = typer.Option("", "--id", help="incident id (default: folder name)"),
           batch_mode: bool = typer.Option(False, "--batch", help="every sub-folder is one incident"),
           offline: bool = typer.Option(False, help="never call live models / capture")) -> None:
    """Ingest + extract into Incident JSON (schema.Incident)."""
    from .adapters import batch_items
    from .pipeline import build_incident, validate
    _offline(offline)
    wd = Path(tempfile.mkdtemp(prefix="trop-ingest-"))
    if batch_mode:
        incs = [build_incident(it, inc_id=it.name, workdir=wd) for it in batch_items(path, wd)]
    else:
        incs = [build_incident(path, inc_id=inc_id or None, workdir=wd)]
    for inc in incs:
        errs = validate(inc)
        if errs:
            typer.echo(f"[warn] {inc['id']}: schema: {errs[:3]}", err=True)
    s = json.dumps(incs if batch_mode else incs[0], ensure_ascii=False, indent=1, default=list)
    if out:
        Path(out).write_text(s, encoding="utf-8")
        typer.echo(f"{len(incs)} incident(s) -> {out}", err=True)
    else:
        sys.stdout.write(s + "\n")


def analyze(path: str = typer.Argument(..., help="folder / file / zip / URL"),
            inc_id: str = typer.Option("", "--id"),
            steps: bool = typer.Option(False, help="print the six bot steps to stderr as they run"),
            offline: bool = typer.Option(False, help="never call live models / capture"),
            explain_best: bool = typer.Option(False, "--explain", help="also print the LinkExplanation vs the best campaign")) -> None:
    """Analyse one item against the known corpus and print the Decision JSON."""
    from trop.engine import service
    _offline(offline)
    corpus = service.Corpus.load()

    def emit(ev, data):
        if ev == "job.step":
            st = data["step"]
            typer.echo(f"[{st['bot']}] {st['status']}" + (f" · {st['detail']}" if st.get("detail") else ""), err=True)
        elif ev == "job.evidence":
            it = data["item"]
            typer.echo(f"    + {it['display'][:90]}  ({it['strength']}, df {it['df']}/{it['N']})", err=True)

    d, inc, _ = service.analyze_path(path, corpus, emit=emit if steps else None, inc_id=inc_id or None)
    sys.stdout.write(d.model_dump_json(indent=1) + "\n")
    if explain_best and (d.campaign_id or d.candidate_campaign_id):
        e = service.explain(inc, d.campaign_id or d.candidate_campaign_id, corpus)
        sys.stdout.write(e.model_dump_json(indent=1) + "\n")


def _top_evidence(d, k: int = 3) -> str:
    items = [e for e in d.evidence if e.state == "match" and e.weight > 0][:k]
    return "; ".join(f"{e.field}:{e.value[:40]}(+{e.weight:.1f})" for e in items)


def run_batch(path: str | Path, corpus=None, *, workdir: Path | None = None, emit_item=None) -> dict:
    """Library entry point (WS2's POST /batch uses this): returns {rows: [BatchRow], items: {...}, meta}."""
    from trop.engine import service
    from trop.engine.batch import cluster_joint
    from .adapters import batch_items, natural_key
    from .pipeline import build_incident

    t0 = time.time()
    corpus = corpus or service.Corpus.load()
    wd = Path(workdir or tempfile.mkdtemp(prefix="trop-batch-"))
    items = sorted(batch_items(path, wd), key=lambda it: natural_key(it.name))
    known = set(corpus.ids)
    incs, errors, kinds = [], {}, {}
    for it in items:
        iid = it.name if it.name not in known else f"{it.name}#b"
        kinds[iid] = it.kind
        try:
            inc = build_incident(it, inc_id=iid, workdir=wd)
        except Exception as e:  # noqa: BLE001 - one broken item must not stop the batch
            errors[iid] = f"{type(e).__name__}: {e}"
            log.warning("ingest failed for %s: %s", it.path, traceback.format_exc(limit=3))
            inc = {"id": iid, "source": {"type": "upload", "path": str(it.path), "ref": it.name}, "ad": {}, "landing": {},
                   "tracking": {}, "infra": {"domains": []}, "content": {}, "media": {},
                   "quality": {"available": [], "missing": ["har", "html", "screenshot"], "errors": [errors[iid]]}}
        incs.append(inc)
        if emit_item:
            emit_item("ingested", {"item": it.name, "incident_id": iid})
    t_ingest = time.time() - t0

    decisions = {}
    for inc in incs:
        try:
            d, _ = service.analyze_incident(inc, corpus)
        except Exception as e:  # noqa: BLE001
            errors[inc["id"]] = errors.get(inc["id"]) or f"decide: {type(e).__name__}: {e}"
            from trop.schema import Decision
            d = Decision(incident_id=inc["id"], decision="insufficient")
        decisions[inc["id"]] = d
    t_decide = time.time() - t0 - t_ingest
    try:
        joint, _ = cluster_joint(incs, corpus)
    except Exception as e:  # noqa: BLE001
        log.warning("joint clustering failed: %s", e)
        joint = {i["id"]: {"campaign": f"NEW-{k + 1:02d}", "variant": None, "operator": None, "operation": f"OPNNEW-{k + 1:02d}"}
                 for k, i in enumerate(incs)}

    rows, details = [], {}
    for it, inc in zip(items, incs):
        iid = inc["id"]
        d, j = decisions[iid], joint[iid]
        if d.decision == "assign" and d.campaign_id:
            campaign = d.campaign_id
            operator = d.operator_id or corpus.campaigns.get(campaign, {}).get("operator_id") or j["operator"]
        else:
            campaign, operator = j["campaign"], j["operator"]
        row = BatchRow(item=it.name, incident_id=iid, decision=d.decision, campaign=campaign,
                       campaign_score=round(d.score, 3), campaign_p=d.p, operator=operator, operation=j["operation"],
                       variant=j.get("variant"), same_operator_as=d.same_operator_as, duplicate_of=d.duplicate_of,
                       coverage=d.coverage, top_evidence=_top_evidence(d))
        rows.append(row)
        details[it.name] = {"incident_id": iid, "kind": kinds.get(iid), "decision": d.model_dump(mode="json"),
                            "cluster": j, "error": errors.get(iid),
                            "quality": inc.get("quality"),
                            "summary": {"entry_url": (inc.get("landing") or {}).get("entry_url"),
                                        "title": (inc.get("landing") or {}).get("title"),
                                        "advertiser": (inc.get("ad") or {}).get("advertiser")}}
    meta = {"n_items": len(items), "corpus_n": len(corpus.incidents), "seconds": round(time.time() - t0, 1),
            "ingest_s": round(t_ingest, 1), "decide_s": round(t_decide, 1), "errors": errors,
            "model_version": next(iter(decisions.values())).model_version if decisions else None,
            "columns": {"campaign": "known KMP id when assigned (max-linkage >= 5, margin >= 1), else joint avg-link "
                                    "cluster (tau 5) of batch + known", "operation": "components of score_operator >= 3",
                        "operator": "assigned campaign's operator, else joint avg-link on score_operator (tau 3)"}}
    return {"rows": rows, "items": details, "meta": meta}


def write_results(res: dict, out_csv: Path) -> tuple[Path, Path]:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    cols = list(BatchRow.model_fields)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in res["rows"]:
            w.writerow({k: ("" if v is None else v) for k, v in r.model_dump().items()})
    out_json = out_csv.with_suffix(".json")
    json.dump({"meta": res["meta"], "rows": [r.model_dump() for r in res["rows"]], "items": res["items"]},
              open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    return out_csv, out_json


def batch(path: str = typer.Argument(..., help="folder of item folders, or a zip"),
          out: str = typer.Option("results.csv", help="results.csv path (results.json written next to it)"),
          offline: bool = typer.Option(False, help="never call live models / capture"),
          corpus_path: str = typer.Option("", "--corpus", help="known corpus JSON (default: data/corpus/known.json)")) -> None:
    """G-BATCH: every immediate sub-folder (or zip member folder) is one item -> results.csv + results.json."""
    from trop.engine import service
    _offline(offline)
    corpus = service.Corpus.load(corpus_path or None)
    res = run_batch(path, corpus)
    c, j = write_results(res, Path(out))
    m = res["meta"]
    typer.echo(f"{m['n_items']} items in {m['seconds']} s (ingest {m['ingest_s']} s) -> {c} + {j}", err=True)
    for r in res["rows"]:
        typer.echo(f"  {r.item:<24} {r.decision:<12} {r.campaign:<9} op {r.operation:<10} {r.campaign_score:>7.2f} "
                   f"p={r.campaign_p:.2f} {r.top_evidence[:60]}", err=True)
    if m["errors"]:
        typer.echo(f"  errors: {m['errors']}", err=True)
