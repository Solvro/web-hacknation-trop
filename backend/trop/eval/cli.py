"""`trop eval` — G-ENGINE regression (RESULTS §2a / §2b).

    trop eval                         sample_v1: B³/ARI (avg-link τ=5), LOCO open set, perturbation table
    trop eval --dane                  DANE held out: open set 9/9, 0 wrong links, incremental + joint batch B³/ARI
    --source precomputed|extract|both precomputed = data/experiments JSON the RESULTS rows used (default: both)
    --json out.json                   write all numbers
Exit code 1 when a gate number does not reproduce.
"""
from __future__ import annotations

import json
import time
import warnings

import typer

app = typer.Typer(help="Evaluation: G-ENGINE regression, LOCO, DANE held-out, perturbations.", invoke_without_command=True)

# RESULTS §2a/§2b — the numbers G-ENGINE requires
SAMPLE_PRECOMPUTED = "incidents_all.json"     # run_a_all.log: VLM (qwen38) ad fields + face clusters + embeddings
DANE_PRECOMPUTED = "incidents_q36.json"       # run_dane_eval.py default (VLM qwen36 ad fields), faces jointly


def _gate_sample(r: dict) -> list[str]:
    bad = []
    t5 = r["avglink_tau5"]
    if t5["b3_F1"] != 1.0 or t5["ARI"] != 1.0:
        bad.append(f"B3 {t5['b3_F1']} / ARI {t5['ARI']} != 1.00")
    lo = r["loco"]
    if lo["should_link_acc"] != 1.0 or lo["should_not_link_acc"] != 1.0 or lo["wrong_assign"]:
        bad.append(f"LOCO {lo}")
    for k, v in (r.get("robustness") or {}).items():
        if v["wrong_assign"]:
            bad.append(f"perturbation {k}: {v['wrong_assign']} wrong links")
    return bad


def _gate_dane(r: dict) -> list[str]:
    bad = []
    o = r["open_set"]
    if o["correct"] != o["n"] or o["wrong_links"]:
        bad.append(f"open set {o['correct']}/{o['n']}, wrong {o['wrong_links']}")
    rep = r["incremental"]["report"]
    if rep["b3_F1"] != 1.0 or rep["ARI"] != 1.0:
        bad.append(f"incremental B3 {rep['b3_F1']} / ARI {rep['ARI']}")
    j = next(x for x in r["joint"] if x["level"] == "campaign" and x["method"] == "avglink")
    if j["b3_F1"] != 1.0 or j["ARI"] != 1.0:
        bad.append(f"joint B3 {j['b3_F1']} / ARI {j['ARI']}")
    return bad


def sample_inputs(source: str) -> list[dict]:
    from . import data, runs
    if source == "precomputed":
        return data.load_precomputed("sample_v1", SAMPLE_PRECOMPUTED)
    S = data.extract_corpus("sample_v1", ad_model="qwen38-27b-fp8", phash="cache_only", faces="none", live=False)
    fid = runs.joint_face_clusters(S)          # incidents_all used face clusters (faces.json), not gallery names
    for inc in S:
        inc["media"]["faces"] = [{"identity": x} for x in fid.get(inc["id"], [])]
    return S


def dane_inputs(source: str) -> tuple[list[dict], list[dict]]:
    from . import data
    if source == "precomputed":
        return data.load_precomputed("sample_v1", DANE_PRECOMPUTED), data.load_precomputed("dane", DANE_PRECOMPUTED)
    kw = dict(ad_model="qwen36-35b-a3b", phash="cache_only", faces="none", live=False)
    return data.extract_corpus("sample_v1", **kw), data.extract_corpus("dane", **kw)


def run(dane: bool = False, source: str = "both", robustness: bool = True, ablation: bool = False) -> dict:
    from . import data, harness, runs
    warnings.filterwarnings("ignore")
    L = harness.load_labels(str(data.labels_path("labels.yaml")))
    out: dict = {}
    for src in (("precomputed", "extract") if source == "both" else (source,)):
        t0 = time.time()
        if dane:
            S, D = dane_inputs(src)
            r = runs.run_dane(S, D, L, data.load_yaml("labels_dane.yaml"), faces="joint")
            r["gate_failures"] = _gate_dane(r)
        else:
            r = runs.run_sample(sample_inputs(src), L, robustness=robustness, ablation=ablation)
            r["gate_failures"] = _gate_sample(r) if robustness else [x for x in _gate_sample(r) if "perturb" not in x]
        r["seconds"] = round(time.time() - t0, 1)
        out[src] = r
    return out


def _print_sample(src: str, r: dict) -> None:
    t = r["avglink_tau5"]
    lo = r["loco"]
    typer.echo(f"\n## sample_v1 [{src}]  n={r['n']}  ({r['seconds']} s)")
    typer.echo(f"  avg-link tau=5: B3-F1 {t['b3_F1']:.2f}  ARI {t['ARI']:.2f}  clusters {t['n_pred']}/{t['n_gold']}  "
               f"hard-neg viol {t['hardneg_viol']}  pair AUC {r['pair_auc']}")
    typer.echo(f"  LOCO tau=5 delta=1: link {lo['should_link_acc']:.2f} (n={lo['n_link']})  not-link "
               f"{lo['should_not_link_acc']:.2f} (n={lo['n_nolink']})  wrong {lo['wrong_assign']}")
    if r.get("robustness"):
        typer.echo("  perturbation      acc    wrong")
        for k, v in r["robustness"].items():
            typer.echo(f"  {k:<16} {v['acc']:.3f}  {v['wrong_assign']}")
    for op in r["operator_avglink"]:
        typer.echo(f"  operator level tau={op['tau']}: B3-F1 {op['b3_F1']:.3f} ARI {op['ARI']:.3f}")


def _print_dane(src: str, r: dict) -> None:
    o = r["open_set"]
    typer.echo(f"\n## DANE held out [{src}]  ({r['seconds']} s)")
    typer.echo(f"  open set (known = sample_v1): correct {o['correct']}/{o['n']}, wrong links {o['wrong_links']}")
    for x in o["rows"]:
        typer.echo(f"   {x['query']:<4} expect {x['expected']:<4} got {x['assigned']:<4} score {x['score']:>6} "
                   f"margin {x['margin']:>6} op {x['operation'] or '-':<8} {x['best'][:70]}")
    rep = r["incremental"]["report"]
    typer.echo(f"  incremental: B3-F1 {rep['b3_F1']:.2f} ARI {rep['ARI']:.2f}")
    for j in r["joint"]:
        typer.echo(f"  joint {j['level']:<8} {j['method']:<10} tau={j['tau']}: B3-F1 {j['b3_F1']:.3f} ARI {j['ARI']:.3f}")


@app.callback()
def main(ctx: typer.Context,
         dane: bool = typer.Option(False, "--dane", help="DANE held-out evaluation (RESULTS §2b)"),
         source: str = typer.Option("both", help="precomputed | extract | both"),
         robustness: bool = typer.Option(True, help="perturbation table (sample only)"),
         ablation: bool = typer.Option(False, help="layer ablation (sample only, slow)"),
         json_out: str = typer.Option("", "--json", help="write all numbers to this file")) -> None:
    """G-ENGINE: reproduce RESULTS §2a (default) or §2b (--dane)."""
    if ctx.invoked_subcommand:
        return
    from . import data
    if data.labels_path("labels.yaml") is None or not data.exp_dir("sample_v1").exists():
        typer.echo("labels/data not found (set DATA_DIR / TROP_LABELS_DIR)", err=True)
        raise typer.Exit(2)
    out = run(dane=dane, source=source, robustness=robustness, ablation=ablation)
    fails = []
    for src, r in out.items():
        (_print_dane if dane else _print_sample)(src, r)
        fails += [f"[{src}] {f}" for f in r["gate_failures"]]
    if json_out:
        json.dump(out, open(json_out, "w", encoding="utf-8"), indent=1, default=str)
    typer.echo("\nG-ENGINE " + ("PASS" if not fails else "FAIL: " + "; ".join(fails)))
    if fails:
        raise typer.Exit(1)
