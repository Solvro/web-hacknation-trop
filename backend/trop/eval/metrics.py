"""Ported from experiments/rp/metrics.py.

Clustering metrics: B-cubed P/R/F1, ARI, pairwise P/R, hard pair checks, open-set accuracy."""
from __future__ import annotations

from itertools import combinations

from sklearn.metrics import adjusted_rand_score


def bcubed(pred: dict, gold: dict) -> tuple[float, float, float]:
    items = list(gold)
    p_sum = r_sum = 0.0
    for i in items:
        same_pred = {j for j in items if pred[j] == pred[i]}
        same_gold = {j for j in items if gold[j] == gold[i]}
        inter = len(same_pred & same_gold)
        p_sum += inter / len(same_pred)
        r_sum += inter / len(same_gold)
    p, r = p_sum / len(items), r_sum / len(items)
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def pairwise(pred: dict, gold: dict) -> tuple[float, float]:
    tp = fp = fn = 0
    for a, b in combinations(list(gold), 2):
        sp, sg = pred[a] == pred[b], gold[a] == gold[b]
        tp += sp and sg
        fp += sp and not sg
        fn += sg and not sp
    return (tp / (tp + fp) if tp + fp else 1.0), (tp / (tp + fn) if tp + fn else 1.0)


def ari(pred: dict, gold: dict) -> float:
    items = list(gold)
    return adjusted_rand_score([gold[i] for i in items], [pred[i] for i in items])


def hard_pairs(pred: dict, labels: dict) -> tuple[int, int, int, int]:
    """(#hard negatives wrongly linked, #hard negatives, #hard positives linked, #hard positives)."""
    hn = [p["pair"] for p in labels.get("hard_negatives", []) if all(x in pred for x in p["pair"])]
    hp = [p["pair"] for p in labels.get("hard_positives", []) if all(x in pred for x in p["pair"])]
    bad = sum(pred[a] == pred[b] for a, b in hn)
    good = sum(pred[a] == pred[b] for a, b in hp)
    return bad, len(hn), good, len(hp)


def report(pred: dict, gold: dict, labels: dict | None = None) -> dict:
    p, r, f = bcubed(pred, gold)
    pp, pr = pairwise(pred, gold)
    out = {"b3_P": p, "b3_R": r, "b3_F1": f, "ARI": ari(pred, gold), "pair_P": pp, "pair_R": pr,
           "n_pred": len(set(pred.values())), "n_gold": len(set(gold.values()))}
    if labels:
        bad, nhn, good, nhp = hard_pairs(pred, labels)
        out["hardneg_viol"] = f"{bad}/{nhn}"
        out["hardpos_ok"] = f"{good}/{nhp}"
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in out.items()}
