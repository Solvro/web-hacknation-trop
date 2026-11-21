"""Approach (c): learned linkage model M1 = LightGBM on the pair evidence vector.

* Training pairs = originals + synthetic perturbations (drop HAR/HTML/screenshot, swap domain, rotate tracking,
  502 page, full rotation), labels from gold campaigns (or weak labels from labelling functions when no gold).
* Strict leave-one-campaign-out: the model that scores any pair touching campaign c never saw c.
* Monotone constraints (more evidence never lowers P), isotonic calibration, TreeSHAP contributions per link.
Usage: uv run python run_c_gbm.py [incidents.json] [labels.yaml]"""
import copy
import json
import os
import random
import sys
import time
from collections import defaultdict
from itertools import combinations

import lightgbm as lgb
import numpy as np
from sklearn.isotonic import IsotonicRegression
from tabulate import tabulate

from rp import cluster, evidence, harness, metrics
from rp.perturb import PERTURBATIONS

INC = sys.argv[1] if len(sys.argv) > 1 else "../data/experiments/sample_v1/incidents.json"
LAB = sys.argv[2] if len(sys.argv) > 2 else "labels.yaml"
OUT = os.path.join(os.path.dirname(INC), f"results_c_{os.environ.get('C_VARIANT', 'types')}.json")
incs = json.load(open(INC, encoding="utf-8"))
L = harness.load_labels(LAB)
gold, raw = L["campaign"], L["raw"]
dup_of = {k: v.get("dup_of") for k, v in raw["incidents"].items()}
ids = [i["id"] for i in incs]
rng = random.Random(0)

# ------------------------------------------------------------------ augmentation pool (cached re-extractions)
t0 = time.time()
KINDS = ["drop_screenshot", "drop_har", "drop_html", "swap_domain", "rotate_tracking", "error_502", "full_rotation"]
pool = []   # (source_id, kind, incident)
for x in incs:
    pool.append((x["id"], "orig", x))
    for k in KINDS:
        y = copy.deepcopy(PERTURBATIONS[k](x, rng))
        y["id"] = f"{x['id']}~{k}"
        pool.append((x["id"], k, y))
print(f"pool: {len(pool)} items ({time.time()-t0:.1f}s)")

# df from ORIGINALS only (realistic rarity), applied to every pair
evidence.prepare(incs)
DF, N = evidence.doc_freq(incs), len(incs)
evidence.prepare([p[2] for p in pool])


VARIANT = os.environ.get("C_VARIANT", "types")
LAYERS = ["tracking", "kit", "infra", "content", "ad", "visual", "persons"]
if VARIANT == "layers":
    evidence.VECTOR_NAMES = [f"camp_{l}" for l in LAYERS] + ["op_only_sum", "neg_sum", "hand_campaign", "hand_operator", "n_layers", "coverage"]


def vec(a, b):
    ev, s = evidence.pair_evidence(a, b, DF, N)
    if VARIANT != "layers":
        return evidence.pair_vector(ev, s), ev
    camp = {l: 0.0 for l in LAYERS}
    op = neg = 0.0
    for e in ev:
        if e["weight"] < 0:
            neg += e["weight"]
        elif e["type"] in evidence.OPERATOR_ONLY:
            op += e["weight"]
        elif e["layer"] in camp:
            camp[e["layer"]] += e["weight"]
    return [camp[l] for l in LAYERS] + [op, neg, s["score_campaign"], s["score_operator"], s["n_layers"], s["coverage"]], ev


# all pool pairs (skip pairs of two perturbations of the same source except one positive per kind pair)
X, Y, SRC = [], [], []
for (sa, ka, a), (sb, kb, b) in combinations(pool, 2):
    if sa == sb and not (ka == "orig" or kb == "orig"):
        continue
    v, _ = vec(a, b)
    X.append(v)
    Y.append(int(gold[sa] == gold[sb]))
    SRC.append((sa, sb, ka, kb))
X, Y = np.asarray(X, dtype=np.float32), np.asarray(Y)
print(f"pairs: {len(Y)} (pos {Y.sum()}), dims {X.shape[1]} ({time.time()-t0:.1f}s)")

mono = [1] * X.shape[1]
mono[evidence.VECTOR_NAMES.index("coverage")] = 0
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=7, min_data_in_leaf=5, n_estimators=250,
              monotone_constraints=mono, monotone_constraints_method="advanced", verbose=-1, seed=0,
              feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1)


def train(mask):
    m = lgb.LGBMClassifier(**PARAMS)
    m.fit(X[mask], Y[mask])
    # isotonic calibration on out-of-fold predictions (3 folds by source pair hash)
    folds = np.array([hash((s[0], s[1])) % 3 for s in np.asarray(SRC, dtype=object)[mask]])
    oof = np.zeros(mask.sum())
    Xm, Ym = X[mask], Y[mask]
    for f in range(3):
        mm = lgb.LGBMClassifier(**PARAMS).fit(Xm[folds != f], Ym[folds != f])
        oof[folds == f] = mm.predict_proba(Xm[folds == f])[:, 1]
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(oof, Ym)
    return m, iso


camps = sorted(set(gold.values()))
models = {}
t1 = time.time()
for c in camps:
    mask = np.array([gold[s[0]] != c and gold[s[1]] != c for s in SRC])
    models[c] = train(mask)
t_train = time.time() - t1
full_model = train(np.ones(len(Y), dtype=bool))
print(f"trained {len(models)} LOCO models + 1 full in {t_train + 0:.1f}s")


def base(i):
    return i.split("~")[0]


def gbm_scorer(sub):
    """LOCO scorer: pair (a,b) scored by the models that never saw a's or b's campaign; score = 10*P (same scale as tau)."""
    evidence.prepare(sub)
    out = {}
    for i, j in combinations(range(len(sub)), 2):
        v, _ = vec(sub[i], sub[j])
        ps = []
        for c in {gold[base(sub[i]["id"])], gold[base(sub[j]["id"])]}:
            m, iso = models[c]
            ps.append(float(iso.predict([m.predict_proba(np.asarray([v], dtype=np.float32))[0, 1]])[0]))
        out[(i, j)] = 10 * float(np.mean(ps))
    return out


# ------------------------------------------------------------------ clustering on originals
TAUS = [3, 4, 5, 6, 7, 8]
res, sc, t = harness.cluster_eval(incs, gbm_scorer, gold, raw, TAUS, "louvain")
print("\n### (c) GBM LOCO -> Louvain on 10*P")
print(tabulate([[r["tau"], r["b3_P"], r["b3_R"], r["b3_F1"], r["ARI"], r["pair_P"], r["pair_R"], r["n_pred"], r["hardneg_viol"], r["hardpos_ok"]] for r, _ in res],
               headers=["tau(10P)", "B3 P", "B3 R", "B3 F1", "ARI", "pairP", "pairR", "#clu", "hardneg viol", "hardpos ok"], tablefmt="github"))

TAU, DELTA = 5.0, 1.0   # P>=0.5, margin 0.1
os_ = harness.open_set_loco(incs, gbm_scorer, gold, TAU, DELTA, dup_of)
print(f"\n### open-set LOCO: link acc={os_['should_link_acc']} (n={os_['n_link']}), not-link acc={os_['should_not_link_acc']} (n={os_['n_nolink']}), wrong={os_['wrong_assign']}")
for d in os_["decisions"]:
    if d["got"] != d["expect"]:
        print("   MISS", d)
rob = harness.robustness(incs, gbm_scorer, gold, TAU, DELTA)
print(tabulate([[k, v["acc"], v["wrong_assign"], v["n"]] for k, v in rob.items()], headers=["perturbation", "acc", "wrong", "n"], tablefmt="github"))

# ------------------------------------------------------------------ SHAP: global importance + example link explanations
m, iso = full_model
contrib = m.booster_.predict(X, pred_contrib=True)[:, :-1]
imp = sorted(zip(evidence.VECTOR_NAMES, np.abs(contrib).mean(0)), key=lambda x: -x[1])
print("\n### mean |SHAP| (full model)")
print(tabulate([[n, round(v, 3)] for n, v in imp[:20]], headers=["feature", "mean|SHAP|"], tablefmt="github"))
expl = {}
for a, b in [("p8", "p11"), ("p3", "p4"), ("p1", "p15"), ("p5", "p1"), ("p11", "p1"), ("p6", "p12")]:
    ia, ib = ids.index(a), ids.index(b)
    v, ev = vec(incs[ia], incs[ib])
    c = m.booster_.predict(np.asarray([v], dtype=np.float32), pred_contrib=True)[0]
    p = float(iso.predict([m.predict_proba(np.asarray([v], dtype=np.float32))[0, 1]])[0])
    top = sorted([(n, round(float(x), 2)) for n, x in zip(evidence.VECTOR_NAMES, c[:-1]) if abs(x) > 0.05], key=lambda t: -abs(t[1]))[:6]
    expl[f"{a}-{b}"] = {"P": round(p, 3), "gold_same": gold[a] == gold[b], "shap": top}
    print(f"{a}-{b}: P={p:.3f} gold_same={gold[a]==gold[b]}  SHAP {top}")

# ------------------------------------------------------------------ weak supervision: labelling functions vs gold
def lfs(a, b, ev):
    t = {e["type"] for e in ev if e["weight"] > 0}
    out = []
    out.append(1 if t & {"fb_pixel", "capi_gateway", "google_ads", "ga4", "gtm"} else -1)            # LF same tracking id
    out.append(1 if {"kit_tenant", "lander_id"} <= t or "lander_id" in t else -1)                       # LF same lander
    out.append(1 if "text_minhash" in t and any(e["type"] == "text_minhash" and e["weight"] >= 3 for e in ev) else -1)  # near-dup text
    out.append(0 if any(e["type"] == "kit_tenant_conflict" for e in ev) else -1)                        # tenant conflict
    hi = t & evidence.HIGH
    out.append(0 if any(e["type"] in ("vertical_conflict", "lang_conflict") for e in ev) and not hi else -1)
    out.append(0 if not hi and sum(e["weight"] for e in ev) < 1.5 else -1)                              # nothing shared
    return out


lf_rows = defaultdict(lambda: [0, 0])
votes = []
for i, j in combinations(range(len(incs)), 2):
    v, ev = vec(incs[i], incs[j])
    o = lfs(incs[i], incs[j], ev)
    g = int(gold[ids[i]] == gold[ids[j]])
    for k, x in enumerate(o):
        if x != -1:
            lf_rows[k][0] += 1
            lf_rows[k][1] += int(x == g)
    pos, neg = sum(x == 1 for x in o), sum(x == 0 for x in o)
    votes.append((1 if pos > neg else 0 if neg > pos else -1, g))
names = ["same tracking id ->1", "same lander ->1", "near-dup text ->1", "tenant conflict ->0", "vertical/lang conflict & no H ->0", "nothing shared ->0"]
print("\n### labelling functions on 105 gold pairs (coverage, accuracy)")
print(tabulate([[names[k], v[0], round(v[1] / v[0], 3) if v[0] else None] for k, v in sorted(lf_rows.items())], headers=["LF", "covers", "acc"], tablefmt="github"))
cov = [v for v in votes if v[0] != -1]
print(f"majority vote: coverage {len(cov)}/{len(votes)}, accuracy {np.mean([a == b for a, b in cov]):.3f}")

json.dump({"grid": [r for r, _ in res], "open_set": os_, "robustness": rob, "shap_global": [(n, float(v)) for n, v in imp],
           "explanations": expl, "train_s": t_train, "n_pairs": int(len(Y))}, open(OUT, "w", encoding="utf-8"), indent=1, default=str)
print("saved", OUT)
