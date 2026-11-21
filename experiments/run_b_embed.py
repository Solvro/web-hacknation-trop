"""Approach (b): embeddings only (no IDs, no infra). Text: mmlw / bge-m3 / Qwen3-Embedding on landing text (+ad text);
image: SigLIP on the ad creative crop. Clustering: HDBSCAN (precomputed cosine distance) and cosine-threshold
average linkage; open-set LOCO with a cosine threshold.  Usage: uv run python run_b_embed.py <dir>"""
import json
import os
import sys

import numpy as np
from sklearn.cluster import HDBSCAN
from tabulate import tabulate

from rp import cluster, harness, metrics

D = sys.argv[1] if len(sys.argv) > 1 else "../data/experiments/sample_v1"
E = os.path.join(D, "emb")
L = harness.load_labels("labels.yaml")
gold, raw = L["campaign"], L["raw"]
dup_of = {k: v.get("dup_of") for k, v in raw["incidents"].items()}
ids = json.load(open(os.path.join(E, "ids.json")))
incs = json.load(open(os.path.join(D, "incidents.json"), encoding="utf-8"))
order = [i["id"] for i in incs]


def load(name):
    p = os.path.join(E, name)
    return np.load(p) if os.path.exists(p) else None


V = {}
for m in ("mmlw", "bgem3", "qwen3emb"):
    t, a = load(f"emb_{m}_text.npy"), load(f"emb_{m}_ad_text.npy")
    if t is not None:
        V[f"{m}:landing"] = t
        V[f"{m}:landing+ad"] = (t + a) / np.linalg.norm(t + a, axis=1, keepdims=True)
s = load("emb_siglip_crop.npy")
if s is not None:
    V["siglip:creative"] = s
    if "mmlw:landing" in V:
        S = np.nan_to_num(s)
        V["mmlw+siglip"] = np.hstack([V["mmlw:landing"], 0.7 * S]) / np.sqrt(1 + 0.49)


def cos_scores(X, sub_ids):
    idx = [ids.index(i.split("~")[0]) for i in sub_ids]
    Y = np.nan_to_num(X[idx])
    C = Y @ Y.T
    return {(i, j): float(C[i, j]) for i in range(len(idx)) for j in range(i + 1, len(idx))}


rows = []
for name, X in V.items():
    sc = cos_scores(X, order)
    auc, margin = harness.pair_auc(sc, order, gold)
    # HDBSCAN on cosine distance
    Y = np.nan_to_num(X[[ids.index(i) for i in order]])
    Dm = np.clip(1 - Y @ Y.T, 0, 2)
    hl = HDBSCAN(min_cluster_size=2, metric="precomputed", allow_single_cluster=False).fit_predict(Dm)
    pred_h = {order[k]: (int(l) if l >= 0 else 1000 + k) for k, l in enumerate(hl)}
    rh = metrics.report(pred_h, {k: gold[k] for k in order}, raw)
    # threshold grid (avg linkage on cosine)
    best = None
    grid = {}
    for tau in np.arange(0.5, 0.99, 0.02):
        pred = cluster.average_linkage(order, sc, float(tau))
        r = metrics.report(pred, {k: gold[k] for k in order}, raw)
        grid[round(float(tau), 2)] = r
        if best is None or r["b3_F1"] > best[1]["b3_F1"]:
            best = (round(float(tau), 2), r)
    # open-set LOCO at the best tau (optimistic: tau tuned on the same data)
    tau = best[0]
    scorer = lambda sub, X=X: cos_scores(X, [x["id"] for x in sub])  # noqa: E731
    o = harness.open_set_loco(incs, scorer, gold, tau, 0.02, dup_of)
    rows.append([name, auc, margin, rh["b3_F1"], rh["ARI"], rh["hardneg_viol"], tau, best[1]["b3_F1"], best[1]["ARI"],
                 best[1]["hardneg_viol"], best[1]["hardpos_ok"], o["should_link_acc"], o["should_not_link_acc"], o["wrong_assign"]])
    if name in ("mmlw:landing", "bgem3:landing"):
        top = sorted(sc.items(), key=lambda kv: -kv[1])[:12]
        print(name, "top pairs:", [(order[i], order[j], round(v, 3), gold[order[i]] == gold[order[j]]) for (i, j), v in top])
print(tabulate(rows, headers=["embedding", "pair AUC", "sep.margin", "HDBSCAN F1", "HDBSCAN ARI", "HDB hardneg", "best tau*", "F1@tau*",
                              "ARI@tau*", "hardneg@tau*", "hardpos@tau*", "LOCO link", "LOCO not-link", "wrong"], tablefmt="github"))
print("* tau tuned on the same 15 items = optimistic upper bound for (b)")
json.dump(rows, open(os.path.join(D, "results_b.json"), "w"), indent=1, default=str)
