"""Approach (b) on sample+DANE: tau tuned on sample_v1 ONLY, then applied to DANE open-set and joint clustering.
Usage: uv run python run_b_joint.py"""
import json
import os
from collections import defaultdict

import numpy as np
import yaml
from sklearn.cluster import HDBSCAN
from tabulate import tabulate

from rp import cluster, harness, metrics

E = "../data/experiments/joint/emb"
ids = json.load(open(os.path.join(E, "ids.json")))
L = harness.load_labels("labels.yaml")
LD = yaml.safe_load(open("labels_dane.yaml", encoding="utf-8"))
gold = {**L["campaign"], **{k: v["campaign"] for k, v in LD["incidents"].items()}}
expect = LD["expected_open_set"]
S_ids = [i for i in ids if i.startswith("p")]
D_ids = [i for i in ids if i.startswith("d") and gold[i] != "UNK"]
lab_ids = S_ids + D_ids
V = {}
for m in ("mmlw", "bgem3", "qwen3emb"):
    V[f"{m}:landing"] = np.load(os.path.join(E, f"emb_{m}_text.npy"))
V["siglip:screenshot"] = np.nan_to_num(np.load(os.path.join(E, "emb_siglip_shot.npy")))


def cos(X, a, b):
    return float(X[ids.index(a)] @ X[ids.index(b)])


rows = []
for name, X in V.items():
    # tune tau on sample only
    sc_s = {(i, j): cos(X, S_ids[i], S_ids[j]) for i in range(len(S_ids)) for j in range(i + 1, len(S_ids))}
    best = max(((metrics.report(cluster.average_linkage(S_ids, sc_s, t), {k: gold[k] for k in S_ids})["b3_F1"], t)
                for t in np.arange(0.5, 0.99, 0.02)), key=lambda x: (x[0], x[1]))
    tau = round(float(best[1]), 2)
    # DANE open-set with that tau
    ok = wrong = 0
    for q in D_ids:
        per = defaultdict(list)
        for k in S_ids:
            per[gold[k]].append(cos(X, q, k))
        got, s, m = cluster.assign_open_set(per, tau, 0.02)
        exp = expect[q]
        ok += (got == exp) or (got is None and exp == "new")
        wrong += got is not None and got != exp
    # joint clustering at tau
    sc = {(i, j): cos(X, lab_ids[i], lab_ids[j]) for i in range(len(lab_ids)) for j in range(i + 1, len(lab_ids))}
    r = metrics.report(cluster.average_linkage(lab_ids, sc, tau), {k: gold[k] for k in lab_ids})
    auc, margin = harness.pair_auc(sc, lab_ids, gold)
    Y = X[[ids.index(i) for i in lab_ids]]
    hl = HDBSCAN(min_cluster_size=2, metric="precomputed", copy=True).fit_predict(np.clip(1 - Y @ Y.T, 0, 2))
    rh = metrics.report({k: (int(l) if l >= 0 else 1000 + n) for n, (k, l) in enumerate(zip(lab_ids, hl))}, {k: gold[k] for k in lab_ids})
    rows.append([name, tau, f"{ok}/9", wrong, r["b3_F1"], r["ARI"], auc, margin, rh["b3_F1"], rh["ARI"]])
print(tabulate(rows, headers=["embedding", "tau (tuned on sample)", "DANE open-set correct", "wrong links", "joint F1@tau", "joint ARI@tau",
                              "joint pair AUC", "sep.margin", "HDBSCAN F1", "HDBSCAN ARI"], tablefmt="github"))
json.dump(rows, open("../data/experiments/joint/results_b_joint.json", "w"), indent=1, default=str)
