"""Historical backtest + precision@k.

Protocol (no leakage): campaign domains are ordered by certificate time; the model is trained on the earliest `train_frac`
and must flag the later ones from the certificate alone ("would have flagged X N hours before its first ad / first public
sighting"). Negatives (CERT PL other-scam domains + benign popular domains) are split at random. Flag time = cert
issuance + `ct_latency_h` (CT log inclusion + our polling interval).
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from statistics import median
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score

from trop.enrich.util import parse_ts

from .model import DomainModel


def _t(s):
    d = parse_ts(s)
    return d.astimezone(timezone.utc) if d else None


def precision_at_k(scores: np.ndarray, y: np.ndarray, ks=(10, 20, 50)) -> dict[str, float]:
    order = np.argsort(-scores)
    return {f"p@{k}": round(float(y[order[:k]].mean()), 3) for k in ks if k <= len(y)}


def threshold_for_fpr(model_scores_neg: np.ndarray, fpr: float) -> float:
    return float(np.quantile(model_scores_neg, 1 - fpr))


def run_backtest(pos: list[dict], neg: list[dict], train_frac: float = 0.6, ct_latency_h: float = 0.25, fpr: float = 0.02,
                 seed: int = 11, neg_ratios=(1, 10, 50)) -> dict[str, Any]:
    rng = random.Random(seed)
    timed = sorted([r for r in pos if r.get("cert_time")], key=lambda r: r["cert_time"])
    untimed = [r for r in pos if not r.get("cert_time")]
    cut = int(len(timed) * train_frac)
    train_pos, test_pos = timed[:cut] + untimed[: len(untimed) * 6 // 10], timed[cut:] + untimed[len(untimed) * 6 // 10:]
    negs = neg[:]
    rng.shuffle(negs)
    ncut = int(len(negs) * 0.6)
    train_neg, test_neg = negs[:ncut], negs[ncut:]
    m = DomainModel().fit([r["domain"] for r in train_pos], [r["domain"] for r in train_neg])
    # threshold from the TRAIN negatives' out-of-sample behaviour: score held-out-negatives would leak, so use a split of train_neg
    half = len(train_neg) // 2
    m_thr = DomainModel().fit([r["domain"] for r in train_pos], [r["domain"] for r in train_neg[:half]])
    thr = threshold_for_fpr(m_thr.p_lex([r["domain"] for r in train_neg[half:]]), fpr)
    sp_ = m.p_lex([r["domain"] for r in test_pos])
    sn = m.p_lex([r["domain"] for r in test_neg])
    y = np.array([1] * len(sp_) + [0] * len(sn))
    auc = float(roc_auc_score(y, np.concatenate([sp_, sn]))) if len(sp_) and len(sn) else None
    # precision@k on a pool with `ratio` negatives per positive
    pk = {}
    for ratio in neg_ratios:
        n_need = min(len(sn), ratio * len(sp_))
        pool_s = np.concatenate([sp_, sn[:n_need]])
        pool_y = np.array([1] * len(sp_) + [0] * n_need)
        pk[f"1:{ratio}"] = {"pool": f"{len(sp_)} held-out kit-A + {n_need} negatives", **precision_at_k(pool_s, pool_y)}
    by_kind = {}
    for kind in sorted({r["kind"] for r in test_neg}):
        sk = np.array([s for s, r in zip(sn, test_neg) if r["kind"] == kind])
        yy = np.array([1] * len(sp_) + [0] * len(sk))
        by_kind[kind] = {"n": int(len(sk)), "auc": round(float(roc_auc_score(yy, np.concatenate([sp_, sk]))), 3) if len(sk) else None,
                         "fpr_at_thr": round(float((sk >= thr).mean()), 4) if len(sk) else None}
    rows, leads = [], []
    for r, s in zip(test_pos, sp_):
        ct, fs = _t(r.get("cert_time")), _t(r.get("first_seen"))
        flagged = bool(s >= thr)
        row = {"domain": r["domain"], "score": round(float(s), 3), "flagged": flagged, "cert_time": r.get("cert_time"),
               "flagged_at": None, "first_ad_at": r.get("first_seen"), "first_activity_source": r.get("first_activity_source"),
               "lead_h": None}
        if ct and fs:
            flag_t = ct.timestamp() + ct_latency_h * 3600
            row["flagged_at"] = datetime.fromtimestamp(flag_t, timezone.utc).isoformat()
            row["lead_h"] = round((fs.timestamp() - flag_t) / 3600, 1)
            if flagged:
                leads.append(row["lead_h"])
        rows.append(row)
    flagged_n = sum(r["flagged"] for r in rows)
    pos_leads = [x for x in leads if x > 0]
    summary = {
        "n_train_pos": len(train_pos), "n_test_pos": len(test_pos), "n_train_neg": len(train_neg), "n_test_neg": len(test_neg),
        "threshold": round(thr, 3), "target_fpr": fpr, "auc": None if auc is None else round(auc, 3),
        "recall_at_thr": round(flagged_n / max(1, len(rows)), 3), "flagged": flagged_n,
        "alerts_per_1000_certs": round(1000 * float((sn >= thr).mean()), 1),
        "precision_at_k": pk, "by_negative_kind": by_kind,
        "n_with_timing": len(leads), "flagged_before_first_activity": len(pos_leads),
        "median_lead_h": round(median(leads), 1) if leads else None,
        "median_lead_h_positive": round(median(pos_leads), 1) if pos_leads else None,
        "ct_latency_h": ct_latency_h, "split": f"temporal {int(train_frac * 100)}/{100 - int(train_frac * 100)} by certificate time",
    }
    return {"summary": summary, "rows": sorted(rows, key=lambda r: -(r["lead_h"] or -1e9) if r["flagged"] else 1e9)}


def cross_val_auc(pos: list[dict], neg: list[dict], k: int = 5, seed: int = 3) -> float | None:
    rng = random.Random(seed)
    P, N = pos[:], neg[:]
    rng.shuffle(P)
    rng.shuffle(N)
    ys, ss = [], []
    for i in range(k):
        tp, tn = [r for j, r in enumerate(P) if j % k != i], [r for j, r in enumerate(N) if j % k != i]
        vp, vn = [r for j, r in enumerate(P) if j % k == i], [r for j, r in enumerate(N) if j % k == i]
        m = DomainModel().fit([r["domain"] for r in tp], [r["domain"] for r in tn])
        ss += list(m.p_lex([r["domain"] for r in vp + vn]))
        ys += [1] * len(vp) + [0] * len(vn)
    return round(float(roc_auc_score(ys, ss)), 3) if len(set(ys)) > 1 else None
