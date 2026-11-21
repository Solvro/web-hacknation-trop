"""Ported from experiments/rp/harness.py.

Evaluation harness shared by all approaches.

A *scorer* is f(incidents) -> {(i, j): score} over all pairs (i<j) of the given list, higher = more likely same campaign.
Every approach (evidence graph, embeddings, GBM, ...) is wrapped as a scorer so clustering, open-set LOCO,
robustness and ablations are computed identically for all of them.
"""
from __future__ import annotations

import copy
import random
import time
from collections import defaultdict

import numpy as np
import yaml

from trop.engine import cluster, evidence

from . import metrics
from .perturb import PERTURBATIONS


def load_labels(path: str) -> dict:
    lab = yaml.safe_load(open(path, encoding="utf-8"))
    gold = {k: v["campaign"] for k, v in lab["incidents"].items()}
    op = {k: v["operator"] for k, v in lab["incidents"].items()}
    return {"raw": lab, "campaign": gold, "operator": op}


# ------------------------------------------------------------------------------------------- scorers

def evidence_scorer(incs: list[dict]) -> dict:
    pairs = evidence.all_pairs(incs)
    return {k: s["score"] for k, (ev, s) in pairs.items()}


# ------------------------------------------------------------------------------------------ clustering

def cluster_eval(incs, scorer, gold, labels_raw, taus, method="louvain"):
    ids = [i["id"] for i in incs]
    t0 = time.time()
    sc = scorer(incs)
    t_score = time.time() - t0
    rows = []
    for tau in taus:
        if method == "louvain":
            pred = cluster.louvain(ids, sc, tau)
        elif method == "components":
            pred = cluster.components(ids, sc, tau)
        else:
            pred = cluster.average_linkage(ids, sc, tau)
        r = metrics.report(pred, {k: gold[k] for k in ids}, labels_raw)
        r["tau"] = tau
        rows.append((r, pred))
    return rows, sc, t_score


# ----------------------------------------------------------------------------------- open-set (LOCO)

def open_set_loco(incs, scorer, gold, tau, delta, dup_of=None):
    """Two query types:
       * should-link: one member of a multi-member campaign held out; others known -> must be assigned to its campaign
       * should-not-link: a whole campaign held out (all members unknown) -> each member must be 'new'
    Duplicates of the query (L0) are removed from the known set so the test is not trivial.
    Returns dict with accuracy per type and the raw decisions."""
    dup_of = dup_of or {}
    ids = [i["id"] for i in incs]
    by_c = defaultdict(list)
    for i in ids:
        by_c[gold[i]].append(i)
    decisions = []

    def run(query_id, known_ids, expect):
        sub = [x for x in incs if x["id"] in known_ids or x["id"] == query_id]
        sc = scorer(sub)
        sid = [x["id"] for x in sub]
        q = sid.index(query_id)
        per_c = defaultdict(list)
        for (a, b), s in sc.items():
            if q in (a, b):
                other = sid[b if a == q else a]
                per_c[gold[other]].append(s)
        got, top, margin = cluster.assign_open_set(per_c, tau, delta)
        decisions.append({"query": query_id, "expect": expect, "got": got, "score": round(top, 2), "margin": round(margin, 2)})

    for c, members in by_c.items():
        real = [m for m in members if not dup_of.get(m)]
        if len(real) >= 2:
            for m in members:
                dups = {x for x in members if dup_of.get(x) == m or dup_of.get(m) == x}
                known = [x for x in ids if x != m and x not in dups]
                if not any(gold[x] == c for x in known):
                    continue
                run(m, set(known), c)
        for m in members:   # whole campaign unknown
            known = [x for x in ids if gold[x] != c]
            run(m, set(known), None)
    link = [d for d in decisions if d["expect"] is not None]
    nolink = [d for d in decisions if d["expect"] is None]
    return {
        "should_link_acc": round(np.mean([d["got"] == d["expect"] for d in link]), 3) if link else None,
        "should_not_link_acc": round(np.mean([d["got"] is None for d in nolink]), 3) if nolink else None,
        "wrong_assign": sum(d["got"] is not None and d["got"] != d["expect"] for d in decisions),
        "n_link": len(link), "n_nolink": len(nolink), "decisions": decisions,
    }


# ----------------------------------------------------------------------------------------- robustness

def robustness(incs, scorer, gold, tau, delta, kinds=None, seed=0):
    """Query = perturbed copy of each incident; known = all ORIGINAL incidents except the source and its duplicates.
    Expected: assigned to the source's campaign if the campaign has other members, else 'new'."""
    rng = random.Random(seed)
    kinds = kinds or list(PERTURBATIONS)
    ids = [i["id"] for i in incs]
    out = {}
    for kind in kinds:
        ok = 0
        n = 0
        wrong = 0
        for x in incs:
            # skip duplicate twin for the source
            twins = {y["id"] for y in incs if y["id"] != x["id"] and _is_dup(x, y)}
            known = [y for y in incs if y["id"] != x["id"] and y["id"] not in twins]
            expect = gold[x["id"]] if any(gold[y["id"]] == gold[x["id"]] for y in known) else None
            try:
                q = PERTURBATIONS[kind](x, rng)
            except Exception:  # noqa: BLE001
                continue
            q = copy.deepcopy(q)
            q["id"] = x["id"] + "~q"
            sub = known + [q]
            sc = scorer(sub)
            qi = len(sub) - 1
            per_c = defaultdict(list)
            for (a, b), s in sc.items():
                if qi in (a, b):
                    other = sub[b if a == qi else a]["id"]
                    per_c[gold[other]].append(s)
            got, _, _ = cluster.assign_open_set(per_c, tau, delta)
            ok += got == expect
            wrong += got is not None and got != expect
            n += 1
        out[kind] = {"acc": round(ok / n, 3) if n else None, "wrong_assign": wrong, "n": n}
    return out


def _is_dup(a, b):
    return (a["landing"].get("entry_url") and a["landing"].get("entry_url") == b["landing"].get("entry_url")
            and a["tracking"].get("asset_hashes") == b["tracking"].get("asset_hashes"))


def pair_auc(sc: dict, ids: list[str], gold: dict) -> tuple[float, float]:
    """ROC-AUC of pair scores for same-campaign vs different-campaign, and separation margin
    (min score among same-campaign pairs minus max score among different-campaign pairs; >0 = perfectly separable)."""
    from sklearn.metrics import roc_auc_score
    y, s = [], []
    for (i, j), v in sc.items():
        y.append(int(gold[ids[i]] == gold[ids[j]]))
        s.append(v)
    pos = [v for v, t in zip(s, y) if t]
    neg = [v for v, t in zip(s, y) if not t]
    return round(float(roc_auc_score(y, s)), 3), round(float(min(pos) - max(neg)), 2)


def best_row(rows, key="b3_F1"):
    return max(rows, key=lambda rp: (rp[0][key], -abs(rp[0]["n_pred"] - rp[0]["n_gold"])))
