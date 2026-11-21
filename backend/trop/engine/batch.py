"""Batch view (RESULTS §4): joint clustering of a set of incidents.

  campaigns   average-linkage components on score_campaign, tau = 5
  variants    Louvain inside each campaign (score_campaign edges >= 5)
  operators   average-linkage on score_operator, tau = 3
  operations  connected components of score_operator >= 3 (shared funnel; the DANE A + C + K finding)

`cluster_joint(items, corpus)` clusters the batch together with the known corpus, so a cluster that contains known
members inherits their KMP / OP / OPN id; batch-only clusters get NEW-… / OPNEW-… ids.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from . import cluster as cluster_mod
from . import evidence

TAU_CAMPAIGN, TAU_OPERATOR = 5.0, 3.0


def pair_scores(incs: list[dict]) -> tuple[dict, dict, dict]:
    pairs = evidence.all_pairs(incs)
    sc = {k: s["score_campaign"] for k, (ev, s) in pairs.items()}
    so = {k: s["score_operator"] for k, (ev, s) in pairs.items()}
    return sc, so, pairs


def cluster(incs: list[dict]) -> dict[str, dict]:
    """Contract: {incident_id: {campaign, variant, operator, operation}} (provisional ids C1/V1/O1/N1)."""
    ids = [i["id"] for i in incs]
    if not ids:
        return {}
    sc, so, _ = pair_scores(incs)
    return _labels(ids, sc, so)


def _labels(ids, sc, so) -> dict[str, dict]:
    camp = cluster_mod.average_linkage(ids, sc, TAU_CAMPAIGN)
    oper = cluster_mod.average_linkage(ids, so, TAU_OPERATOR)
    opn = cluster_mod.components(ids, so, TAU_OPERATOR)
    variant = {}
    by_c = defaultdict(list)
    for i, iid in enumerate(ids):
        by_c[camp[iid]].append(i)
    for c, members in by_c.items():
        if len(members) == 1:
            variant[ids[members[0]]] = f"V{c}.0"
            continue
        sub_ids = [ids[m] for m in members]
        pos = {m: k for k, m in enumerate(members)}
        sub = {(pos[i], pos[j]): s for (i, j), s in sc.items() if i in pos and j in pos}
        lv = cluster_mod.louvain(sub_ids, sub, TAU_CAMPAIGN)
        for iid in sub_ids:
            variant[iid] = f"V{c}.{lv[iid]}"
    return {iid: {"campaign": f"C{camp[iid]}", "variant": variant[iid], "operator": f"O{oper[iid]}",
                  "operation": f"N{opn[iid]}"} for iid in ids}



def cluster_joint(items: list[dict], corpus=None) -> tuple[dict[str, dict], dict]:
    """Cluster batch items together with the known corpus; returns ({item_id: {...ids}}, pairs) for items only."""
    known = [k for k in (corpus.incidents if corpus else []) if k["id"] not in {x["id"] for x in items}]
    allinc = known + items
    ids = [i["id"] for i in allinc]
    sc, so, pairs = pair_scores(allinc)
    lab = _labels(ids, sc, so)
    known_ids = {k["id"] for k in known}

    def rename(level: str, known_map: dict, prefix: str) -> dict[str, str]:
        groups = defaultdict(list)
        for iid in ids:
            groups[lab[iid][level]].append(iid)
        out, n_new = {}, 0
        for g in sorted(groups, key=lambda g: min(ids.index(x) for x in groups[g])):
            mem = groups[g]
            kn = [known_map[x] for x in mem if x in known_ids and known_map.get(x)]
            if kn:
                name = Counter(kn).most_common(1)[0][0]
            else:
                n_new += 1
                name = f"{prefix}{n_new:02d}"
            for x in mem:
                out[x] = name
        return out

    cmap = rename("campaign", corpus.campaign_of if corpus else {}, "NEW-")
    omap = rename("operator", corpus.operator_of if corpus else {}, "OPNEW-")
    nmap = rename("operation", corpus.operation_of if corpus else {}, "OPNNEW-")
    res = {}
    for x in items:
        iid = x["id"]
        v = lab[iid]["variant"]
        res[iid] = {"campaign": cmap[iid], "variant": f"{cmap[iid]}/{v.split('.')[-1]}", "operator": omap[iid],
                    "operation": nmap[iid]}
    return res, {"ids": ids, "pairs": pairs}
