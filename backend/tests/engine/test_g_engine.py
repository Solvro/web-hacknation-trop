"""G-ENGINE regression: the ported engine reproduces RESULTS §2a (sample_v1) and §2b (DANE held out).

Organizer data is read from DATA_DIR; every test skips when it (or the labels) is absent.
"""
from __future__ import annotations

import pytest

from trop.eval import data

HAVE_LABELS = data.labels_path("labels.yaml") is not None and data.labels_path("labels_dane.yaml") is not None
HAVE_PRE = (data.exp_dir("sample_v1") / "incidents_all.json").exists() and (data.exp_dir("dane") / "incidents_q36.json").exists()
HAVE_RAW_S = data.raw_dir("sample_v1").exists()
HAVE_RAW = HAVE_RAW_S and data.raw_dir("dane").exists()
HAVE_MODELS = (data.data_dir() / "experiments" / "models" / "sface.onnx").exists() or \
    (data.exp_dir("joint") / "face_clusters_sface.json").exists()

# sample: the drop_har/drop_html perturbations re-extract from the raw folders; DANE: joint SFace face clusters
need_pre_sample = pytest.mark.skipif(not (HAVE_LABELS and HAVE_PRE and HAVE_RAW_S), reason="organizer data / labels absent")
need_pre_dane = pytest.mark.skipif(not (HAVE_LABELS and HAVE_PRE and HAVE_MODELS), reason="organizer data / face models absent")
need_raw_dane = pytest.mark.skipif(not (HAVE_LABELS and HAVE_PRE and HAVE_MODELS and data.raw_dir("dane").exists()),
                                   reason="raw DANE absent")
need_raw = pytest.mark.skipif(not (HAVE_LABELS and HAVE_RAW and HAVE_PRE and HAVE_MODELS), reason="raw organizer data absent")


@pytest.fixture(scope="module", autouse=True)
def _offline():
    import os
    old = os.environ.get("TROP_NO_LIVE")
    os.environ["TROP_NO_LIVE"] = "1"
    yield
    if old is None:
        os.environ.pop("TROP_NO_LIVE", None)


def _assert_sample(r):
    t5 = r["avglink_tau5"]
    assert (t5["b3_F1"], t5["ARI"]) == (1.0, 1.0)
    assert t5["hardneg_viol"] == "0/9"
    lo = r["loco"]
    assert (lo["should_link_acc"], lo["should_not_link_acc"], lo["wrong_assign"]) == (1.0, 1.0, 0)
    assert (lo["n_link"], lo["n_nolink"]) == (8, 15)
    rob = r["robustness"]
    assert all(v["wrong_assign"] == 0 for v in rob.values()), rob
    # RESULTS §3 robustness row "+ embeddings + conjunction (final)": 502 page 0.87, -HTML 0.87, rest 1.0
    assert rob["error_502"]["acc"] == pytest.approx(0.867, abs=1e-3)
    assert rob["drop_html"]["acc"] == pytest.approx(0.867, abs=1e-3)
    for k in ("duplicate", "drop_screenshot", "drop_har", "swap_domain", "rotate_tracking", "full_rotation"):
        assert rob[k]["acc"] == 1.0, k


def _assert_dane(r):
    o = r["open_set"]
    assert (o["correct"], o["n"], o["wrong_links"]) == (9, 9, 0)
    got = {x["query"]: x["assigned"] for x in o["rows"]}
    assert got["d1"] == "A" and got["d2"] == "A" and got["d3"] == "C"
    assert all(got[q] == "new" for q in ("d10", "d14", "d36", "d47", "d48", "d61"))
    rep = r["incremental"]["report"]
    assert (rep["b3_F1"], rep["ARI"]) == (1.0, 1.0)
    inc = {x["query"]: x["predicted"] for x in r["incremental"]["rows"]}
    assert inc["d61"] == inc["d48"] and inc["d48"].startswith("NEW")      # K forms once d48 is known
    j = {(x["level"], x["method"]): x for x in r["joint"]}
    assert (j[("campaign", "avglink")]["b3_F1"], j[("campaign", "avglink")]["ARI"]) == (1.0, 1.0)
    assert r["n_joint"] == 24


@need_pre_sample
def test_sample_precomputed_reproduces_results_2a():
    from trop.eval import cli
    _assert_sample(cli.run(dane=False, source="precomputed")["precomputed"])


@need_raw
def test_sample_reextracted_reproduces_results_2a():
    from trop.eval import cli
    _assert_sample(cli.run(dane=False, source="extract")["extract"])


@need_pre_dane
def test_dane_precomputed_reproduces_results_2b():
    from trop.eval import cli
    _assert_dane(cli.run(dane=True, source="precomputed")["precomputed"])


@need_raw_dane
def test_dane_reextracted_reproduces_results_2b():
    from trop.eval import cli
    _assert_dane(cli.run(dane=True, source="extract")["extract"])
