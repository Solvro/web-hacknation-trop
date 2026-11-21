"""score_campaign -> P(same campaign) ("pewność" in the UI). Isotonic regression on the labelled pairs (sample_v1 +
DANE: every pair of the 24 labelled incidents), stored per model version as JSON next to this file. Between
isotonic breakpoints the curve is interpolated linearly; a Platt fit is stored as well (for the Lab).

The file holds only (score, probability) points and counts — no identifiers.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

MODEL_VERSION = "engine@1"
HERE = Path(__file__).resolve().parent / "calibration"
P_MIN, P_MAX = 0.01, 0.99


def path_for(version: str = MODEL_VERSION) -> Path:
    return HERE / f"{version.replace('@', '_')}.json"


@lru_cache(maxsize=4)
def load(version: str = MODEL_VERSION) -> dict | None:
    p = path_for(version)
    return json.load(open(p)) if p.exists() else None


def prob(score: float, version: str = MODEL_VERSION) -> float:
    """Calibrated P(same campaign | score_campaign). Falls back to a logistic prior centred on tau when uncalibrated."""
    c = load(version)
    if not c:
        return round(min(P_MAX, max(P_MIN, 1 / (1 + math.exp(-(score - 5.0))))), 3)
    x, y = c["isotonic"]["x"], c["isotonic"]["y"]
    p = float(np.interp(score, x, y))
    return round(min(P_MAX, max(P_MIN, p)), 3)


def labelled_pairs(incs: list[dict], gold: dict[str, str]) -> tuple[np.ndarray, np.ndarray]:
    from . import evidence
    items = [i for i in incs if gold.get(i["id"]) not in (None, "UNK")]
    pairs = evidence.all_pairs(items)
    s, y = [], []
    for (i, j), (_, summ) in pairs.items():
        s.append(summ["score_campaign"])
        y.append(int(gold[items[i]["id"]] == gold[items[j]["id"]]))
    return np.asarray(s, dtype=float), np.asarray(y, dtype=int)


def fit(scores: np.ndarray, y: np.ndarray, version: str = MODEL_VERSION, note: str = "") -> dict:
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0, increasing=True).fit(scores, y)
    xs = [float(v) for v in iso.X_thresholds_]
    ys = [float(v) for v in iso.y_thresholds_]
    lr = LogisticRegression(C=1e3).fit(scores.reshape(-1, 1), y)
    a, b = float(lr.coef_[0][0]), float(lr.intercept_[0])
    pos, neg = scores[y == 1], scores[y == 0]
    out = {
        "model_version": version, "method": "isotonic (linear interpolation between breakpoints)",
        "fitted_on": note or "all pairs of the labelled incidents (sample_v1 + DANE), score_campaign",
        "n_pairs": int(len(y)), "n_pos": int(y.sum()), "n_neg": int(len(y) - y.sum()),
        "isotonic": {"x": [round(v, 3) for v in xs], "y": [round(v, 4) for v in ys]},
        "platt": {"a": round(a, 4), "b": round(b, 4)},
        "clip": [P_MIN, P_MAX],
        "summary": {"pos_min": round(float(pos.min()), 3) if len(pos) else None,
                    "neg_max": round(float(neg.max()), 3) if len(neg) else None,
                    "p_at_tau": round(float(np.interp(5.0, xs, ys)), 3) if xs else None},
    }
    return out


def fit_and_save(incs: list[dict], gold: dict[str, str], version: str = MODEL_VERSION) -> dict:
    s, y = labelled_pairs(incs, gold)
    c = fit(s, y, version)
    HERE.mkdir(parents=True, exist_ok=True)
    json.dump(c, open(path_for(version), "w"), indent=1)
    load.cache_clear()
    return c


def build_default(version: str = MODEL_VERSION) -> dict:
    """Fit from the labelled sample_v1 + DANE (re-extracted with the product pipeline, offline caches)."""
    from trop.eval import data
    lab = data.load_yaml("labels.yaml")
    LD = data.load_yaml("labels_dane.yaml")
    gold = {k: v["campaign"] for k, v in lab["incidents"].items()}
    gold.update({k: v["campaign"] for k, v in LD["incidents"].items()})
    S = data.extract_corpus("sample_v1", phash="compute", faces="gallery")
    D = data.extract_corpus("dane", phash="compute", faces="gallery")
    return fit_and_save(S + D, gold, version)


__all__ = ["prob", "fit", "fit_and_save", "build_default", "MODEL_VERSION"]
