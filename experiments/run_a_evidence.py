"""Approach (a): hand-weighted, rarity-weighted evidence graph + Louvain. Prints pair evidence, clustering grid,
open-set LOCO, robustness, ablation. Usage: uv run python run_a_evidence.py [incidents.json] [labels.yaml]"""
import json
import os
import sys
from itertools import combinations

from tabulate import tabulate

from rp import evidence, harness

INC = sys.argv[1] if len(sys.argv) > 1 else "../data/experiments/sample_v1/incidents.json"
LAB = sys.argv[2] if len(sys.argv) > 2 else "labels.yaml"
OUT = os.path.join(os.path.dirname(INC), "results_a.json")
incs = json.load(open(INC, encoding="utf-8"))
L = harness.load_labels(LAB)
gold, raw = L["campaign"], L["raw"]
dup_of = {k: v.get("dup_of") for k, v in raw["incidents"].items()}
ids = [i["id"] for i in incs]

# ---- 1. pair evidence dump (top pairs + all labelled-hard pairs)
pairs = evidence.all_pairs(incs)
rows = []
for (a, b), (ev, s) in sorted(pairs.items(), key=lambda kv: -kv[1][1]["score"]):
    same = gold[ids[a]] == gold[ids[b]]
    if s["score"] > 0.5 or same:
        top = ", ".join(f"{e['type']}={e['weight']:.1f}" for e in sorted(ev, key=lambda e: -abs(e["weight"]))[:5])
        rows.append([ids[a], ids[b], "SAME" if same else "", s["score"], s["n_layers"], s["coverage"], top])
print(tabulate(rows[:45], headers=["a", "b", "gold", "score", "layers", "cov", "top evidence"], tablefmt="github"))

TAU, DELTA = 5.0, 1.0
# ---- 2. clustering grid
TAUS = [1, 2, 3, 4, 5, 6, 7, 8, 10, 12]
summary = {}
for method in ("avglink", "components", "louvain"):
    res, sc, t = harness.cluster_eval(incs, harness.evidence_scorer, gold, raw, TAUS, method)
    print(f"\n### clustering: {method}  (scoring {t*1000:.0f} ms)")
    print(tabulate([[r["tau"], r["b3_P"], r["b3_R"], r["b3_F1"], r["ARI"], r["pair_P"], r["pair_R"], r["n_pred"], r["hardneg_viol"], r["hardpos_ok"]] for r, _ in res],
                   headers=["tau", "B3 P", "B3 R", "B3 F1", "ARI", "pairP", "pairR", "#clu", "hardneg viol", "hardpos ok"], tablefmt="github"))
    summary[method] = {"grid": [r for r, _ in res], "pred_at_5": next(p for r, p in res if r["tau"] == 5)}
    if method == "avglink":
        auc, margin = harness.pair_auc(sc, ids, gold)
        print(f"pair AUC={auc}  separation margin (min same-campaign score - max different-campaign score)={margin}")

# ---- 3. open-set LOCO + robustness at the a-priori threshold (tau=5: one H item, or >=2 M items)
os_ = harness.open_set_loco(incs, harness.evidence_scorer, gold, TAU, DELTA, dup_of)
print(f"\n### open-set LOCO (tau={TAU}, delta={DELTA}): should-link acc={os_['should_link_acc']} (n={os_['n_link']}), "
      f"should-NOT-link acc={os_['should_not_link_acc']} (n={os_['n_nolink']}), wrong assignments={os_['wrong_assign']}")
for d in os_["decisions"]:
    if d["got"] != d["expect"]:
        print("   MISS", d)
rob = harness.robustness(incs, harness.evidence_scorer, gold, TAU, DELTA)
print("\n### robustness (perturbed query vs originals)")
print(tabulate([[k, v["acc"], v["wrong_assign"], v["n"]] for k, v in rob.items()], headers=["perturbation", "acc", "wrong", "n"], tablefmt="github"))

# ---- 4. ablation: drop one layer at a time (and keep-only one layer)
layers = sorted(set(evidence.LAYER.values()))
abl = []
for mode in ("drop", "only"):
    for layer in layers + ["neg"]:
        if mode == "only" and layer == "neg":
            continue
        types = {t for t, l in evidence.LAYER.items() if l == layer} | ({"kit_tenant_conflict", "lang_conflict", "vertical_conflict"} if layer == "neg" else set())
        evidence.DISABLED = types if mode == "drop" else (set(evidence.LAYER) - types) | {"neg"}
        res, sc, _ = harness.cluster_eval(incs, harness.evidence_scorer, gold, raw, [TAU], "avglink")
        r = res[0][0]
        auc, margin = harness.pair_auc(sc, ids, gold)
        o = harness.open_set_loco(incs, harness.evidence_scorer, gold, TAU, DELTA, dup_of)
        abl.append([f"{mode} {layer}", r["b3_F1"], r["ARI"], auc, margin, r["hardneg_viol"], r["hardpos_ok"], o["should_link_acc"], o["should_not_link_acc"], o["wrong_assign"]])
evidence.DISABLED = set()
print("\n### ablation @tau=5 avg-linkage (campaign level)")
print(tabulate(abl, headers=["setting", "B3 F1", "ARI", "pair AUC", "sep. margin", "hardneg viol", "hardpos ok", "LOCO link", "LOCO not-link", "wrong"], tablefmt="github"))

# ---- 5. robustness per layer-drop for the two hardest perturbations
rob_abl = []
for layer in ["ad", "persons", "content", "visual"]:
    evidence.DISABLED = {t for t, l in evidence.LAYER.items() if l == layer}
    rr = harness.robustness(incs, harness.evidence_scorer, gold, TAU, DELTA, kinds=["error_502", "full_rotation", "drop_html"])
    rob_abl.append([f"drop {layer}"] + [f"{rr[k]['acc']} ({rr[k]['wrong_assign']} wrong)" for k in ("error_502", "full_rotation", "drop_html")])
evidence.DISABLED = set()
print("\n### robustness when a layer is dropped (acc, wrong links)")
print(tabulate(rob_abl, headers=["setting", "error_502", "full_rotation", "drop_html"], tablefmt="github"))

# ---- 6. operator level (all evidence incl. operator-only types) vs operator labels
evidence.LEVEL = "operator"
opg = L["operator"]
res_op, _, _ = harness.cluster_eval(incs, harness.evidence_scorer, opg, {}, [3, 5, 8, 12], "avglink")
print("\n### operator level (all evidence) vs operator labels, avg-linkage")
print(tabulate([[r["tau"], r["b3_P"], r["b3_R"], r["b3_F1"], r["ARI"], r["n_pred"], r["n_gold"]] for r, _ in res_op],
               headers=["tau", "B3 P", "B3 R", "B3 F1", "ARI", "#clu", "#gold"], tablefmt="github"))
evidence.LEVEL = "campaign"

json.dump({"summary": summary, "open_set": os_, "robustness": rob, "ablation": abl}, open(OUT, "w", encoding="utf-8"), indent=1, default=str)
print("saved", OUT)
