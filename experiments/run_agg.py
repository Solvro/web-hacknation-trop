"""Compare per-campaign aggregation rules for open-set assignment (approach a). Usage: run_agg.py <incidents.json>"""
import json, sys
from tabulate import tabulate
from rp import cluster, harness
incs = json.load(open(sys.argv[1], encoding="utf-8"))
L = harness.load_labels("labels.yaml"); gold = L["campaign"]
dup_of = {k: v.get("dup_of") for k, v in L["raw"]["incidents"].items()}
rows = []
for agg in ("max", "max_top3", "top2"):
    cluster.AGG = agg
    for tau in (4.0, 5.0, 6.0):
        o = harness.open_set_loco(incs, harness.evidence_scorer, gold, tau, 1.0, dup_of)
        r = harness.robustness(incs, harness.evidence_scorer, gold, tau, 1.0, kinds=["error_502", "drop_html", "full_rotation", "rotate_tracking"])
        rows.append([agg, tau, o["should_link_acc"], o["should_not_link_acc"], o["wrong_assign"]] + [f"{v['acc']} ({v['wrong_assign']})" for v in r.values()])
print(tabulate(rows, headers=["aggregation", "tau", "LOCO link", "LOCO not-link", "LOCO wrong", "error_502", "drop_html", "full_rotation", "rotate_tracking"], tablefmt="github"))
