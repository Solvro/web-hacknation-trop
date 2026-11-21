"""DANE evaluation: known = sample_v1 (gold campaigns), queries = DANE incidents.
  A. open-set, each DANE item alone           B. incremental (DANE in order, predictions become known)
  C. joint clustering of 24 labelled items (campaign + operation level)   D. layer variants   E. explanations
Usage: uv run python run_dane_eval.py [variant_name]   (reads */incidents_q36.json; faces computed jointly here)"""
import copy
import json
import os
import sys
from collections import defaultdict

import cv2
import numpy as np
import yaml
from tabulate import tabulate

from rp import cluster, evidence, harness, metrics

NAME = sys.argv[1] if len(sys.argv) > 1 else "incidents_q36.json"
S = json.load(open(f"../data/experiments/sample_v1/{NAME}", encoding="utf-8"))
Dn = json.load(open(f"../data/experiments/dane/{NAME}", encoding="utf-8"))
L = harness.load_labels("labels.yaml")
LD = yaml.safe_load(open("labels_dane.yaml", encoding="utf-8"))
gold = dict(L["campaign"])
gold.update({k: v["campaign"] for k, v in LD["incidents"].items()})
oper = {**LD["sample_operations"], **{k: v["operation"] for k, v in LD["incidents"].items()}}
expect = LD["expected_open_set"]

# ---------------------------------------------------------------- joint face clusters (SFace, CPU)
M = "../data/experiments/models"
det = cv2.FaceDetectorYN.create(os.path.join(M, "yunet.onnx"), "", (320, 320), score_threshold=0.75)
rec = cv2.FaceRecognizerSF.create(os.path.join(M, "sface.onnx"), "")


def face_feats(path):
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return []
    h, w = img.shape[:2]
    sc = 1.0 if max(h, w) <= 1600 else 1600 / max(h, w)
    im = cv2.resize(img, (int(w * sc), int(h * sc))) if sc != 1 else img
    det.setInputSize((im.shape[1], im.shape[0]))
    _, f = det.detect(im)
    out = []
    for row in (f if f is not None else []):
        v = rec.feature(rec.alignCrop(im, row))[0]
        out.append(v / np.linalg.norm(v))
    return out


allinc = S + Dn
feats = []
for inc in allinc:
    p = (inc["ad"].get("screenshots") or [inc["ad"].get("screenshot_path")])[0] if (inc["ad"].get("screenshots") or inc["ad"].get("screenshot_path")) else None
    for v in (face_feats(p) if p else []):
        feats.append((inc["id"], v))
lab = list(range(len(feats)))
for i in range(len(feats)):
    for j in range(i + 1, len(feats)):
        if feats[i][0] != feats[j][0] and float(feats[i][1] @ feats[j][1]) >= 0.45:
            a, b = lab[i], lab[j]
            lab = [a if x == b else x for x in lab]
fid = defaultdict(set)
for (iid, _), l in zip(feats, lab):
    fid[iid].add(f"face{l}")
for inc in allinc:
    inc.setdefault("media", {})["faces"] = [{"identity": x} for x in sorted(fid.get(inc["id"], []))]
shared_faces = {k: v for k, v in fid.items() if any(v & fid[o] for o in fid if o != k)}
print("faces with cross-ad matches:", {k: sorted(v) for k, v in shared_faces.items()})


def decide(known, q, tau=5.0, delta=1.0):
    sub = known + [q]
    evidence.prepare(sub)
    df = evidence.doc_freq(sub)
    per_c, per_o, best = defaultdict(list), defaultdict(list), []
    for k in known:
        ev, s = evidence.pair_evidence(q, k, df, len(sub))
        per_c[k["_gold"]].append(s["score_campaign"])
        per_o[k["_oper"]].append(s["score_operator"])
        best.append((s["score_campaign"], s["score_operator"], k["id"], ev))
    c, sc, mg = cluster.assign_open_set(per_c, tau, delta)
    o, so, _ = cluster.assign_open_set(per_o, 3.0, 0.0)
    best.sort(key=lambda x: (-x[0], -x[1]))
    return c, round(sc, 2), round(mg, 2), o, round(so, 2), best[0]


def label_known(items, glab, olab):
    for it in items:
        it["_gold"] = glab[it["id"]]
        it["_oper"] = olab.get(it["id"], it["id"])
    return items


# ---------------------------------------------------------------- A. open-set, each DANE query alone
known = label_known(copy.deepcopy(S), gold, oper)
rows, ok, wrong = [], 0, 0
for q in Dn:
    c, sc, mg, o, so, (bs, bo, bid, bev) = decide(known, q)
    exp = expect.get(q["id"], "n/a")
    good = (c == exp) or (c is None and exp == "new")
    if exp != "n/a" and q["id"] != "d5":
        ok += good
        wrong += (c is not None and c != exp)
    top = ", ".join(f"{e['type']}={e['weight']:.1f}" for e in sorted(bev, key=lambda e: -abs(e["weight"]))[:5])
    rows.append([q["id"], exp, c or "new", sc, mg, o or "-", so, "OK" if good else ("n/a" if exp == "n/a" else "MISS"), f"{bid}: {top}"])
print(f"\n### A. open-set (known = sample_v1 15 items): correct {ok}/9, wrong links {wrong}")
print(tabulate(rows, headers=["query", "expected", "assigned", "score", "margin", "operation", "op score", "", "best match: top evidence"], tablefmt="github"))

# ---------------------------------------------------------------- B. incremental: DANE in order, predictions become known
known = label_known(copy.deepcopy(S), gold, oper)
pred = {k["id"]: k["_gold"] for k in known}
newc = 0
inc_rows = []
for q in Dn:
    c, sc, mg, o, so, (bs, bo, bid, bev) = decide(known, q)
    if c is None:
        newc += 1
        c = f"NEW{newc}"
    qq = copy.deepcopy(q)
    qq["_gold"], qq["_oper"] = c, (o or f"OPNEW{newc}")
    known.append(qq)
    pred[q["id"]] = c
    inc_rows.append([q["id"], gold[q["id"]], c, sc, bid])
print("\n### B. incremental (each DANE item added to the known set with its predicted label)")
print(tabulate(inc_rows, headers=["query", "gold", "predicted", "score", "best match"], tablefmt="github"))
lab_ids = [k for k in pred if gold.get(k) != "UNK"]
print("B3/ARI of incremental labels vs gold (24 labelled):", metrics.report({k: pred[k] for k in lab_ids}, {k: gold[k] for k in lab_ids}))

# ---------------------------------------------------------------- C. joint clustering (batch)
items = [x for x in copy.deepcopy(allinc) if gold.get(x["id"]) != "UNK"]
ids = [x["id"] for x in items]
res = []
for lvl, tau, gl in (("campaign", 5.0, gold), ("operator", 3.0, oper)):
    evidence.LEVEL = lvl
    pairs = evidence.all_pairs(items)
    sc = {k: (s["score_campaign"] if lvl == "campaign" else s["score_operator"]) for k, (ev, s) in pairs.items()}
    for method in ("avglink", "components"):
        p = cluster.average_linkage(ids, sc, tau) if method == "avglink" else cluster.components(ids, sc, tau)
        r = metrics.report(p, {k: gl[k] for k in ids})
        auc, margin = harness.pair_auc(sc, ids, gl)
        res.append([lvl, method, tau, r["b3_P"], r["b3_R"], r["b3_F1"], r["ARI"], auc, margin, r["n_pred"], r["n_gold"]])
evidence.LEVEL = "campaign"
print("\n### C. joint batch clustering of 24 labelled incidents (sample 15 + DANE 9)")
print(tabulate(res, headers=["level", "method", "tau", "B3 P", "B3 R", "B3 F1", "ARI", "pair AUC", "sep.margin", "#clu", "#gold"], tablefmt="github"))
json.dump({"open_set": rows, "incremental": inc_rows, "joint": res}, open(f"../data/experiments/dane/results_dane_{NAME.split('.')[0]}.json", "w"), indent=1, default=str)
