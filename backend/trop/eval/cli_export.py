"""`trop export dataset` — incidents + engine features + labels -> JSONL + CSV (for NASK / model training)."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import typer

app = typer.Typer(help="Exports.", no_args_is_help=True)

FLAT = [("tracking", k) for k in ("fb_pixels", "capi_gateways", "google_ads", "ga4", "gtm", "tiktok_pixels", "kit_tenants",
                                   "lander_ids", "landing_type_ids", "video_hosts", "path_shapes")] + \
       [("content", k) for k in ("persons", "comment_names", "brands", "products")]


@app.command()
def dataset(out: str = typer.Option("", help="output dir (default: data/out/dataset)"),
            with_dane: bool = typer.Option(True, help="include DANE (labels_dane.yaml)"),
            pairs: bool = typer.Option(True, help="also write labelled pairs with engine scores (pairs.csv)")) -> None:
    os.environ["TROP_NO_LIVE"] = "1"
    from trop.engine import evidence
    from . import data
    od = Path(out) if out else data.data_dir() / "out" / "dataset"
    od.mkdir(parents=True, exist_ok=True)
    lab = data.load_yaml("labels.yaml")["incidents"]
    LD = data.load_yaml("labels_dane.yaml") if with_dane else {"incidents": {}, "sample_operations": {}}
    lab = {**lab, **LD["incidents"]}
    ops = {**LD.get("sample_operations", {}), **{k: v.get("operation") for k, v in LD["incidents"].items()}}
    incs = []
    for corpus in ("sample_v1", "dane") if with_dane else ("sample_v1",):
        incs += (data.extract_corpus(corpus, phash="compute", faces="gallery") if data.raw_dir(corpus).exists()
                 else data.load_precomputed(corpus, "incidents_q36.json"))
    with open(od / "incidents.jsonl", "w", encoding="utf-8") as f:
        for inc in incs:
            L = lab.get(inc["id"], {})
            rec = {k: v for k, v in inc.items() if not k.startswith("_")}
            rec["labels"] = {"campaign": L.get("campaign"), "variant": L.get("variant"), "operator": L.get("operator"),
                             "operation": ops.get(inc["id"]), "dup_of": L.get("dup_of")}
            for k in ("source",):
                rec[k] = {kk: vv for kk, vv in rec[k].items() if kk != "path"}
            f.write(json.dumps(rec, ensure_ascii=False, default=list) + "\n")
    with open(od / "incidents.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "campaign", "operator", "operation", "entry_etld1", "title", "vertical", "lang", "advertiser",
                    "faces"] + [f"{s}.{k}" for s, k in FLAT])
        for inc in incs:
            L = lab.get(inc["id"], {})
            w.writerow([inc["id"], L.get("campaign"), L.get("operator"), ops.get(inc["id"]), inc["landing"].get("etld1"),
                        inc["landing"].get("title"), inc["content"].get("vertical"), inc["content"].get("lang"),
                        inc["ad"].get("advertiser"), "|".join(x.get("identity") or "" for x in (inc.get("media") or {}).get("faces", []))]
                       + ["|".join(map(str, inc.get(s, {}).get(k) or [])) for s, k in FLAT])
    n_pairs = 0
    if pairs:
        items = [i for i in incs if lab.get(i["id"], {}).get("campaign") not in (None, "UNK")]
        allp = evidence.all_pairs(items)
        with open(od / "pairs.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["a", "b", "same_campaign", "same_operation", "score_campaign", "score_operator", "n_layers", "coverage",
                        "evidence"])
            for (i, j), (ev, s) in allp.items():
                a, b = items[i]["id"], items[j]["id"]
                w.writerow([a, b, int(lab[a]["campaign"] == lab[b]["campaign"]), int(ops.get(a) == ops.get(b)),
                            s["score_campaign"], s["score_operator"], s["n_layers"], s["coverage"],
                            "; ".join(f"{e['type']}={e['weight']}" for e in ev)])
                n_pairs += 1
    typer.echo(f"{len(incs)} incidents, {n_pairs} pairs -> {od}")
