"""G-ENGINE regression runs — ports of experiments/run_a_evidence.py (RESULTS §2a/§3) and run_dane_eval.py (§2b).

Every function returns a plain dict of numbers (also written as JSON by `trop eval`). The logic, thresholds and
aggregation are the experiments' own; only I/O changed.
"""
from __future__ import annotations

import copy
import os
from collections import defaultdict
from pathlib import Path

from trop.engine import cluster, evidence

from . import harness, metrics
from .data import data_dir

TAU, DELTA = 5.0, 1.0
PERTURBATION_KINDS = ["duplicate", "drop_screenshot", "drop_har", "drop_html", "swap_domain", "rotate_tracking",
                      "error_502", "full_rotation"]


def _reset():
    evidence.DISABLED = set()
    evidence.LEVEL = "campaign"
    evidence.CONJUNCTION = True
    cluster.AGG = "max"


# ------------------------------------------------------------------------------------------------ sample_v1 (§2a)
def run_sample(incs: list[dict], labels: dict, *, robustness: bool = True, ablation: bool = False) -> dict:
    """incs: sample_v1 incidents; labels: harness.load_labels() result."""
    _reset()
    gold, raw = labels["campaign"], labels["raw"]
    dup_of = {k: v.get("dup_of") for k, v in raw["incidents"].items()}
    ids = [i["id"] for i in incs]
    out: dict = {"n": len(incs)}

    res, sc, t = harness.cluster_eval(incs, harness.evidence_scorer, gold, raw, [1, 2, 3, 4, 5, 6, 7, 8, 10, 12], "avglink")
    out["avglink_grid"] = [r for r, _ in res]
    out["avglink_tau5"] = next(r for r, _ in res if r["tau"] == 5)
    auc, margin = harness.pair_auc(sc, ids, gold)
    out["pair_auc"], out["separation_margin"] = auc, margin
    for method in ("components", "louvain"):
        r2, _, _ = harness.cluster_eval(incs, harness.evidence_scorer, gold, raw, [5], method)
        out[f"{method}_tau5"] = r2[0][0]

    o = harness.open_set_loco(incs, harness.evidence_scorer, gold, TAU, DELTA, dup_of)
    out["loco"] = {k: o[k] for k in ("should_link_acc", "should_not_link_acc", "wrong_assign", "n_link", "n_nolink")}
    out["loco_misses"] = [d for d in o["decisions"] if d["got"] != d["expect"]]

    if robustness:
        out["robustness"] = harness.robustness(incs, harness.evidence_scorer, gold, TAU, DELTA, kinds=PERTURBATION_KINDS)

    # operator level (all evidence) vs operator labels
    evidence.LEVEL = "operator"
    res_op, _, _ = harness.cluster_eval(incs, harness.evidence_scorer, labels["operator"], {}, [3, 5], "avglink")
    out["operator_avglink"] = [r for r, _ in res_op]
    evidence.LEVEL = "campaign"

    if ablation:
        out["ablation"] = _ablation(incs, gold, raw, dup_of, ids)
    _reset()
    return out


def _ablation(incs, gold, raw, dup_of, ids) -> list[dict]:
    layers = sorted(set(evidence.LAYER.values()))
    rows = []
    for mode in ("drop", "only"):
        for layer in layers + ["neg"]:
            if mode == "only" and layer == "neg":
                continue
            types = {t for t, l in evidence.LAYER.items() if l == layer} | (
                {"kit_tenant_conflict", "lang_conflict", "vertical_conflict"} if layer == "neg" else set())
            evidence.DISABLED = types if mode == "drop" else (set(evidence.LAYER) - types) | {"neg"}
            res, sc, _ = harness.cluster_eval(incs, harness.evidence_scorer, gold, raw, [TAU], "avglink")
            r = res[0][0]
            auc, margin = harness.pair_auc(sc, ids, gold)
            o = harness.open_set_loco(incs, harness.evidence_scorer, gold, TAU, DELTA, dup_of)
            rows.append({"setting": f"{mode} {layer}", "b3_F1": r["b3_F1"], "ARI": r["ARI"], "pair_auc": auc,
                         "loco_link": o["should_link_acc"], "loco_not_link": o["should_not_link_acc"],
                         "wrong": o["wrong_assign"]})
    evidence.DISABLED = set()
    return rows


# ------------------------------------------------------------------------------------------------ DANE (§2b)
def models_dir() -> str | None:
    from trop.config import settings
    for d in (data_dir() / "experiments" / "models", Path(settings.models_dir)):
        if (d / "sface.onnx").exists() and (d / "yunet.onnx").exists():
            return str(d)
    return None


FACE_CACHE = "face_clusters_sface.json"


def joint_face_clusters(incs: list[dict], models: str | None = None, thr: float = 0.45) -> dict[str, list[str]]:
    """Joint SFace face clusters; computed when the ONNX models are present (and cached under
    experiments/joint/face_clusters_sface.json), else read from that cache (only cross-incident clusters matter:
    a face label seen in one incident never produces evidence)."""
    import json
    ids = sorted(i["id"] for i in incs)
    cache_p = data_dir() / "experiments" / "joint" / FACE_CACHE
    m = models or models_dir()
    if m is None:
        if not cache_p.exists():
            raise FileNotFoundError("SFace/YuNet models and face-cluster cache both absent")
        c = json.load(open(cache_p))
        out = {k: v for k, v in c["shared"].items() if k in ids}
        cnt: dict = defaultdict(int)
        for v in out.values():
            for x in set(v):
                cnt[x] += 1
        return {k: [x for x in v if cnt[x] > 1] for k, v in out.items() if any(cnt[x] > 1 for x in v)}
    res = _joint_face_clusters(incs, m, thr)
    try:
        prev = json.load(open(cache_p)) if cache_p.exists() else {}
        if len(ids) >= len(prev.get("ids", [])):
            shared = {k: v for k, v in res.items() if any(set(v) & set(res[o]) for o in res if o != k)}
            cache_p.parent.mkdir(parents=True, exist_ok=True)
            json.dump({"ids": ids, "shared": shared, "thr": thr}, open(cache_p, "w"), indent=1)
    except OSError:
        pass
    return res


def _joint_face_clusters(incs: list[dict], models_dir: str, thr: float = 0.45) -> dict[str, list[str]]:
    """run_dane_eval.py's joint SFace face clustering: first ad screenshot of every incident, YuNet detect, SFace
    embed, link faces of different incidents at cos >= 0.45, label = face<k>. Returns {incident_id: [face labels]}."""
    import cv2
    import numpy as np

    m = models_dir
    det = cv2.FaceDetectorYN.create(os.path.join(m, "yunet.onnx"), "", (320, 320), score_threshold=0.75)
    rec = cv2.FaceRecognizerSF.create(os.path.join(m, "sface.onnx"), "")

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

    feats = []
    for inc in incs:
        ad = inc.get("ad") or {}
        shots = ad.get("screenshots") or ([ad["screenshot_path"]] if ad.get("screenshot_path") else [])
        p = shots[0] if shots else None
        for v in (face_feats(p) if p and os.path.exists(p) else []):
            feats.append((inc["id"], v))
    lab = list(range(len(feats)))
    for i in range(len(feats)):
        for j in range(i + 1, len(feats)):
            if feats[i][0] != feats[j][0] and float(feats[i][1] @ feats[j][1]) >= thr:
                a, b = lab[i], lab[j]
                lab = [a if x == b else x for x in lab]
    fid = defaultdict(set)
    for (iid, _), l in zip(feats, lab):
        fid[iid].add(f"face{l}")
    return {k: sorted(v) for k, v in fid.items()}


def _decide(known, q, tau=TAU, delta=DELTA):
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


def _label_known(items, glab, olab):
    for it in items:
        it["_gold"] = glab[it["id"]]
        it["_oper"] = olab.get(it["id"], it["id"])
    return items


def run_dane(S: list[dict], Dn: list[dict], labels: dict, labels_dane: dict, *, faces: str = "joint") -> dict:
    """S = sample_v1 (known), Dn = DANE queries. faces: 'joint' = recompute SFace clusters jointly (as the experiment),
    'keep' = use media.faces already on the incidents."""
    _reset()
    S, Dn = copy.deepcopy(S), copy.deepcopy(Dn)
    LD = labels_dane
    gold = dict(labels["campaign"])
    gold.update({k: v["campaign"] for k, v in LD["incidents"].items()})
    oper = {**LD["sample_operations"], **{k: v["operation"] for k, v in LD["incidents"].items()}}
    expect = LD["expected_open_set"]
    allinc = S + Dn
    out: dict = {}
    if faces == "joint":
        fid = joint_face_clusters(allinc)
        for inc in allinc:
            inc.setdefault("media", {})["faces"] = [{"identity": x} for x in fid.get(inc["id"], [])]
        out["face_clusters_shared"] = {k: v for k, v in fid.items() if any(set(v) & set(fid[o]) for o in fid if o != k)}

    # A. open-set, each DANE query alone
    known = _label_known(copy.deepcopy(S), gold, oper)
    rows, ok, wrong = [], 0, 0
    for q in Dn:
        c, sc, mg, o, so, (bs, bo, bid, bev) = _decide(known, q)
        exp = expect.get(q["id"], "n/a")
        good = (c == exp) or (c is None and exp == "new")
        if exp != "n/a" and q["id"] != "d5":
            ok += good
            wrong += (c is not None and c != exp)
        top = ", ".join(f"{e['type']}={e['weight']:.1f}" for e in sorted(bev, key=lambda e: -abs(e["weight"]))[:5])
        rows.append({"query": q["id"], "expected": exp, "assigned": c or "new", "score": sc, "margin": mg,
                     "operation": o, "op_score": so, "ok": bool(good) if exp != "n/a" else None, "best": f"{bid}: {top}"})
    n_lab = sum(1 for q in Dn if expect.get(q["id"], "n/a") != "n/a" and q["id"] != "d5")
    out["open_set"] = {"correct": ok, "n": n_lab, "wrong_links": wrong, "rows": rows}

    # B. incremental
    known = _label_known(copy.deepcopy(S), gold, oper)
    pred = {k["id"]: k["_gold"] for k in known}
    newc, inc_rows = 0, []
    for q in Dn:
        c, sc, mg, o, so, (bs, bo, bid, bev) = _decide(known, q)
        if c is None:
            newc += 1
            c = f"NEW{newc}"
        qq = copy.deepcopy(q)
        qq["_gold"], qq["_oper"] = c, (o or f"OPNEW{newc}")
        known.append(qq)
        pred[q["id"]] = c
        inc_rows.append({"query": q["id"], "gold": gold[q["id"]], "predicted": c, "score": sc, "best": bid})
    lab_ids = [k for k in pred if gold.get(k) != "UNK"]
    out["incremental"] = {"rows": inc_rows,
                          "report": metrics.report({k: pred[k] for k in lab_ids}, {k: gold[k] for k in lab_ids})}

    # C. joint batch clustering of the labelled items
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
            res.append({"level": lvl, "method": method, "tau": tau, **r, "pair_auc": auc, "sep_margin": margin})
    evidence.LEVEL = "campaign"
    out["joint"] = res
    out["n_joint"] = len(items)
    _reset()
    return out
