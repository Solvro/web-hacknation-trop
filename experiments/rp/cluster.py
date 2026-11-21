"""Graph clustering + open-set assignment over a pair-score matrix."""
from __future__ import annotations

import numpy as np
import networkx as nx


def louvain(ids: list[str], score: dict, tau: float, resolution: float = 1.0, seed: int = 0) -> dict:
    """score: {(i,j): s}. Edge if s >= tau, weight = s. Louvain communities; isolated nodes are singletons."""
    g = nx.Graph()
    g.add_nodes_from(range(len(ids)))
    for (i, j), s in score.items():
        if s >= tau:
            g.add_edge(i, j, weight=float(s))
    comms = nx.community.louvain_communities(g, weight="weight", resolution=resolution, seed=seed)
    lab = {}
    for c, members in enumerate(sorted(comms, key=lambda m: min(m))):
        for m in members:
            lab[ids[m]] = c
    return lab


def components(ids: list[str], score: dict, tau: float) -> dict:
    g = nx.Graph()
    g.add_nodes_from(range(len(ids)))
    g.add_edges_from((i, j) for (i, j), s in score.items() if s >= tau)
    lab = {}
    for c, members in enumerate(nx.connected_components(g)):
        for m in members:
            lab[ids[m]] = c
    return lab


def average_linkage(ids: list[str], score: dict, tau: float) -> dict:
    """Agglomerative merge while mean inter-cluster score >= tau (robust to single spurious edges)."""
    n = len(ids)
    S = np.zeros((n, n))
    for (i, j), s in score.items():
        S[i, j] = S[j, i] = s
    clusters = [[i] for i in range(n)]
    while True:
        best, bi, bj = -1e9, -1, -1
        for a in range(len(clusters)):
            for b in range(a + 1, len(clusters)):
                m = S[np.ix_(clusters[a], clusters[b])].mean()
                if m > best:
                    best, bi, bj = m, a, b
        if best < tau or bi < 0:
            break
        clusters[bi] += clusters[bj]
        del clusters[bj]
    return {ids[m]: c for c, members in enumerate(clusters) for m in members}


AGG = "max"   # "max" (default: best single typed link) | "max_top3" (PLAN 6.4) | "top2"


def campaign_score(item_scores: list[float]) -> float:
    """Per-campaign aggregation. PLAN §6.4 default: 0.5*max linkage + 0.5*mean of top-3."""
    if not item_scores:
        return 0.0
    s = sorted(item_scores, reverse=True)
    if AGG == "max":
        return s[0]
    if AGG == "top2":
        return float(np.mean(s[:2]))
    return 0.5 * s[0] + 0.5 * float(np.mean(s[:3]))


def assign_open_set(item_to_known: dict[str, list[float]], tau: float, delta: float) -> tuple[str | None, float, float]:
    """item_to_known: campaign -> list of pair scores to its members. Returns (campaign or None=new, score, margin)."""
    scored = sorted(((campaign_score(v), c) for c, v in item_to_known.items()), reverse=True)
    if not scored:
        return None, 0.0, 0.0
    top, c = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    if top >= tau and top - second >= delta:
        return c, top, top - second
    return None, top, top - second
