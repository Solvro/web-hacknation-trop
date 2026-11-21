"""The port is byte-for-byte equivalent in scoring to the frozen experiments code (experiments/rp)."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from trop.engine import cluster, evidence
from trop.eval import data

REPO = Path(__file__).resolve().parents[3]
PRE = data.exp_dir("sample_v1") / "incidents_q36.json"


def _rp():
    sys.path.insert(0, str(REPO / "experiments"))
    try:
        return importlib.import_module("rp.evidence"), importlib.import_module("rp.cluster")
    except ImportError:
        return None, None
    finally:
        sys.path.pop(0)


def test_constants_identical():
    rp_ev, rp_cl = _rp()
    if rp_ev is None:
        pytest.skip("experiments/rp not importable")
    # the only additions are the video/ASR types (absent from every RESULTS input)
    added = {"media_text", "voice_id"}
    assert {k: v for k, v in evidence.STRENGTH.items() if k not in added} == rp_ev.STRENGTH
    assert evidence.STRENGTH["media_text"] == rp_ev.STRENGTH["text_minhash"] and evidence.STRENGTH["voice_id"] == 4.0
    assert evidence.NEG == rp_ev.NEG
    assert {k: v for k, v in evidence.LAYER.items() if k not in added} == rp_ev.LAYER
    assert evidence.OPERATOR_ONLY - {"voice_id"} == rp_ev.OPERATOR_ONLY and "voice_id" in evidence.OPERATOR_ONLY
    assert evidence.IDENTIFIER_TYPES == rp_ev.IDENTIFIER_TYPES
    assert evidence.HIGH == rp_ev.HIGH and evidence.CONJUNCTION is True
    assert cluster.AGG == rp_cl.AGG == "max"


@pytest.mark.skipif(not PRE.exists(), reason="organizer data absent")
def test_pair_scores_identical_to_experiments():
    import copy
    rp_ev, _ = _rp()
    if rp_ev is None:
        pytest.skip("experiments/rp not importable")
    incs = data.load_precomputed("sample_v1", "incidents_q36.json") + data.load_precomputed("dane", "incidents_q36.json")
    a = evidence.all_pairs(copy.deepcopy(incs))
    b = rp_ev.all_pairs(copy.deepcopy(incs))
    assert a.keys() == b.keys()
    for k in a:
        assert a[k][1] == b[k][1], k
        assert [(e["type"], e["weight"], e["value"]) for e in a[k][0]] == [(e["type"], e["weight"], e["value"]) for e in b[k][0]]


def test_assign_open_set_rules():
    # tau=5, delta=1 (RESULTS §4): assign needs >= 5 AND margin >= 1; max-linkage per campaign
    assert cluster.assign_open_set({"A": [6.0, 0.1], "B": [4.5]}, 5.0, 1.0)[0] == "A"
    assert cluster.assign_open_set({"A": [5.5], "B": [5.0]}, 5.0, 1.0)[0] is None      # ambiguous
    assert cluster.assign_open_set({"A": [4.9]}, 5.0, 1.0)[0] is None                  # confirm band
