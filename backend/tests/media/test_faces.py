"""RESULTS §2c truth test: 11 named faces in 7 screenshots -> 9 TP / 0 FP / 2 FN with cos>=0.45 and lead>=0.10.
Skips when organizer data / face index are absent (they are git-ignored)."""
import json
from pathlib import Path

import pytest

from trop.config import settings
from trop.media import faces

DATA = Path(settings.data_dir)
EXP = DATA.resolve().parent / "experiments"
DANE_TRUTH = {"d1": ["rafał brzoska"], "d3": ["monika olejnik", "adam glapiński"]}

needs = pytest.mark.skipif(
    not ((DATA / "experiments" / "face_gallery" / "index_sface.npz").exists() and (DATA / "experiments" / "sample_v1" / "incidents.json").exists()
         and (EXP / "ad_truth.yaml").exists()),
    reason="organizer data / face gallery not available")


def _first_shot(inc: dict) -> Path | None:
    ad = inc["ad"]
    lst = ad.get("screenshots") or ([ad["screenshot_path"]] if ad.get("screenshot_path") else [])
    if not lst:
        return None
    s = lst[0].replace("\\", "/").removeprefix("../data/")
    p = DATA / s
    return p if p.exists() else None


def test_rule_constants():
    assert faces.COS_MIN == 0.45 and faces.LEAD_MIN == 0.10


@needs
def test_gallery_truth_9tp_0fp_2fn():
    import yaml
    truth = {k: [x.lower() for x in (v.get("persons") or [])] for k, v in yaml.safe_load(open(EXP / "ad_truth.yaml", encoding="utf-8")).items()}
    truth.update(DANE_TRUTH)
    m = faces.matcher()
    assert m.n_people >= 6000
    names = set(m.names)
    tp = fp = fn = 0
    for corpus in ("sample_v1", "dane"):
        for inc in json.load(open(DATA / "experiments" / corpus / "incidents.json", encoding="utf-8")):
            if inc["id"] not in truth:
                continue
            p = _first_shot(inc)
            if p is None:
                continue
            got = {h.identity for h in faces.match(str(p))}
            want = set(truth[inc["id"]]) & names
            tp += len(got & want)
            fp += len(got - want)
            fn += len(want - got)
    assert (tp, fp, fn) == (9, 0, 2)


@needs
def test_hits_carry_rule_fields():
    for inc in json.load(open(DATA / "experiments" / "sample_v1" / "incidents.json", encoding="utf-8")):
        p = _first_shot(inc)
        if p is None:
            continue
        for h in faces.match(str(p)):
            assert h.score >= 0.45 and h.lead >= 0.10 and h.identity
