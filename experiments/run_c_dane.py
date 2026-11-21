"""Approach (c) held out: LightGBM (per-layer sums + hand scores, monotone, isotonic) trained on ALL sample_v1 pairs
(+ synthetic perturbations), tested on DANE open-set (known = sample) and joint clustering. Usage: uv run python run_c_dane.py"""
import copy
import json
import random
from collections import defaultdict
from itertools import combinations

import lightgbm as lgb
import numpy as np
import yaml
from sklearn.isotonic import IsotonicRegression
from tabulate import tabulate

from rp import cluster, evidence, harness, metrics
from rp.perturb import PERTURBATIONS

S = json.load(open("../data/experiments/sample_v1/incidents_q36.json", encoding="utf-8"))
Dn = json.load(open("../data/experiments/dane/incidents_q36.json", encoding="utf-8"))
L = harness.load_labels("labels.yaml")
LD = yaml.safe_load(open("labels_dane.yaml", encoding="utf-8"))
gold = {**L["campaign"], **{k: v["campaign"] for k, v in LD["incidents"].items()}}
expect = LD["expected_open_set"]
LAYERS = ["tracking", "kit", "infra", "content", "ad", "visual", "persons"]
rng = random.Random(0)


def vec(a, b, df, n):
    ev, s = evidence.pair_evidence(a, b, df, n)
    camp = {l: 0.0 for l in LAYERS}
    op = neg = 0.0
    for e in ev:
        if e["weight"] < 0:
            neg += e["weight"]
        elif e["type"] in evidence.OPERATOR_ONLY:
            op += e["weight"]
        elif e["layer"] in camp:
            camp[e["layer"]] += e["weight"]
    return [camp[l] for l in LAYERS] + [op, neg, s["score_campaign"], s["score_operator"], s["n_layers"], s["coverage"]]


pool = []
for x in S:
    pool.append((x["id"], "orig", x))
    for k in ["drop_screenshot", "drop_har", "drop_html", "swap_domain", "rotate_tracking", "error_502", "full_rotation"]:
        y = copy.deepcopy(PERTURBATIONS[k](x, rng))
        y["id"] = f"{x['id']}~{k}"
        pool.append((x["id"], k, y))
evidence.prepare(S)
DF, N = evidence.doc_freq(S), len(S)
evidence.prepare([p[2] for p in pool])
X, Y = [], []
for (sa, ka, a), (sb, kb, b) in combinations(pool, 2):
    if sa == sb and not (ka == "orig" or kb == "orig"):
        continue
    X.append(vec(a, b, DF, N))
    Y.append(int(gold[sa] == gold[sb]))
X, Y = np.asarray(X, dtype=np.float32), np.asarray(Y)
mono = [1] * X.shape[1]
mono[-1] = 0
P = dict(objective="binary", learning_rate=0.05, num_leaves=7, min_data_in_leaf=5, n_estimators=250, monotone_constraints=mono,
         monotone_constraints_method="advanced", verbose=-1, seed=0, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1)
m = lgb.LGBMClassifier(**P).fit(X, Y)
oof = np.zeros(len(Y))
folds = np.arange(len(Y)) % 3
for f in range(3):
    oof[folds == f] = lgb.LGBMClassifier(**P).fit(X[folds != f], Y[folds != f]).predict_proba(X[folds == f])[:, 1]
iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(oof, Y)
print(f"trained on {len(Y)} sample pairs ({Y.sum()} positive)")


def prob(a, b, df, n):
    return float(iso.predict([m.predict_proba(np.asarray([vec(a, b, df, n)], dtype=np.float32))[0, 1]])[0])


rows, ok, wrong = [], 0, 0
for q in Dn:
    sub = S + [q]
    evidence.prepare(sub)
    df = evidence.doc_freq(sub)
    per = defaultdict(list)
    for k in S:
        per[gold[k["id"]]].append(10 * prob(q, k, df, len(sub)))
    got, sc, mg = cluster.assign_open_set(per, 5.0, 1.0)
    exp = expect.get(q["id"], "n/a")
    if exp != "n/a" and q["id"] != "d5":
        ok += (got == exp) or (got is None and exp == "new")
        wrong += got is not None and got != exp
    rows.append([q["id"], exp, got or "new", round(sc / 10, 3)])
print(f"DANE open-set: correct {ok}/9, wrong links {wrong}")
print(tabulate(rows, headers=["query", "expected", "assigned", "P(best)"], tablefmt="github"))
items = [x for x in S + Dn if gold[x["id"]] != "UNK"]
evidence.prepare(items)
df = evidence.doc_freq(items)
ids = [x["id"] for x in items]
sc = {(i, j): 10 * prob(items[i], items[j], df, len(items)) for i, j in combinations(range(len(items)), 2)}
r = metrics.report(cluster.average_linkage(ids, sc, 5.0), {k: gold[k] for k in ids})
print("joint avg-link @P>=0.5:", r, "AUC/margin", harness.pair_auc(sc, ids, gold))
