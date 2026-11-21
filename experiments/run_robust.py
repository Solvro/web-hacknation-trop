"""Robustness table for several incident variants (approach a, tau=5). Usage: uv run python run_robust.py <dir> name1 name2 ..."""
import json, os, sys
from tabulate import tabulate
from rp import harness, evidence
D = sys.argv[1]
L = harness.load_labels("labels.yaml")
rows = []
for name in sys.argv[2:]:
    incs = json.load(open(os.path.join(D, name), encoding="utf-8"))
    r = harness.robustness(incs, harness.evidence_scorer, L["campaign"], 5.0, 1.0)
    rows.append([name] + [f"{v['acc']} ({v['wrong_assign']})" for v in r.values()])
    kinds = list(r)
print(tabulate(rows, headers=["variant"] + kinds, tablefmt="github"))
