"""Approach (g): split-conformal open-set threshold.

Nonconformity of a query that should be NEW = its best campaign score s* = max_c campaign_score(q, c).
tau_alpha = ceil((n+1)(1-alpha))/n quantile of s* over calibration 'novel' queries  =>  P(novel item is linked) <= alpha
(marginal, exchangeability). Power = fraction of should-link queries with s* >= tau_alpha AND top campaign correct.
Queries: LOCO originals + all perturbations (each source incident x each perturbation kind), both 'novel' (its campaign
removed from the known set) and 'known' (its campaign kept, source + duplicates removed).
Usage: uv run python run_g_conformal.py <incidents.json>"""
import copy
import json
import math
import os
import random
import sys
from collections import defaultdict

import numpy as np
from tabulate import tabulate

from rp import cluster, harness
from rp.perturb import PERTURBATIONS

INC = sys.argv[1]
D = os.path.dirname(INC)
incs = json.load(open(INC, encoding="utf-8"))
L = harness.load_labels("labels.yaml")
gold = L["campaign"]
rng = random.Random(1)
scorer = harness.evidence_scorer
kinds = ["orig"] + [k for k in PERTURBATIONS if k != "duplicate"]
variants = {}
for x in incs:
    for k in kinds:
        q = copy.deepcopy(x if k == "orig" else PERTURBATIONS[k](x, rng))
        q["id"] = f"{x['id']}~{k}"
        variants[(x["id"], k)] = q


def best(q, known):
    sub = known + [q]
    sc = scorer(sub)
    qi = len(sub) - 1
    per_c = defaultdict(list)
    for (a, b), s in sc.items():
        if qi in (a, b):
            per_c[gold[sub[b if a == qi else a]["id"]]].append(s)
    ranked = sorted(((cluster.campaign_score(v), c) for c, v in per_c.items()), reverse=True)
    return ranked[0] if ranked else (0.0, None)


rows = []   # (source, kind, novel?, s*, top_campaign, true_campaign)
for (src, k), q in variants.items():
    c = gold[src]
    twins = {y["id"] for y in incs if y["id"] != src and harness._is_dup(y, next(i for i in incs if i["id"] == src))}
    known_nov = [y for y in incs if gold[y["id"]] != c]
    s, top = best(q, known_nov)
    rows.append((src, k, True, s, top, c))
    known_k = [y for y in incs if y["id"] != src and y["id"] not in twins]
    if any(gold[y["id"]] == c for y in known_k):
        s, top = best(q, known_k)
        rows.append((src, k, False, s, top, c))
nov = [r for r in rows if r[2]]
kno = [r for r in rows if not r[2]]
print(f"queries: novel {len(nov)}, known {len(kno)}")

res = []
for alpha in (0.01, 0.05, 0.10):
    fl, pw, taus = [], [], []
    for rep in range(200):
        # split by SOURCE incident (no leakage of perturbations of the same item across cal/test)
        srcs = sorted({r[0] for r in rows})
        rng.shuffle(srcs)
        cal_s = set(srcs[: len(srcs) // 2])
        cal = sorted(r[3] for r in nov if r[0] in cal_s)
        n = len(cal)
        kq = min(n - 1, math.ceil((n + 1) * (1 - alpha)) - 1)
        tau = cal[kq] + 1e-6
        taus.append(tau)
        test_nov = [r for r in nov if r[0] not in cal_s]
        test_kno = [r for r in kno if r[0] not in cal_s]
        fl.append(np.mean([r[3] >= tau for r in test_nov]) if test_nov else 0)
        pw.append(np.mean([r[3] >= tau and r[4] == r[5] for r in test_kno]) if test_kno else np.nan)
    res.append([alpha, round(float(np.median(taus)), 2), round(float(np.mean(fl)), 4), round(float(np.nanmean(pw)), 3)])
print(tabulate(res, headers=["target alpha (false-link rate on novel)", "median tau", "achieved false-link rate", "power (correct link rate on known)"], tablefmt="github"))
# fixed a-priori tau=5 for reference
f5 = np.mean([r[3] >= 5 for r in nov])
p5 = np.mean([r[3] >= 5 and r[4] == r[5] for r in kno])
print(f"a-priori tau=5: false-link {f5:.4f}, power {p5:.3f}")
# where does power get lost? per perturbation kind at tau=5
per = defaultdict(list)
for r in kno:
    per[r[1]].append(r[3] >= 5 and r[4] == r[5])
print({k: round(float(np.mean(v)), 2) for k, v in per.items()})
print("max novel score per kind:", {k: round(max(r[3] for r in nov if r[1] == k), 2) for k in kinds})
json.dump({"rows": rows, "table": res, "tau5": [f5, p5]}, open(os.path.join(D, f"results_g_{os.path.basename(INC).split('.')[0]}.json"), "w"), indent=1, default=str)
