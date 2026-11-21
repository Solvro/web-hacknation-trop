import numpy as np

from trop.media import adjudicator as A
from trop.media import voice
from trop.media.pipeline import incident_id_for


def test_adjudication_mapping():
    same = A.to_adjudication({"model": "m", "json": {"same_campaign": True, "same_operator": True, "confidence": 0.9, "rationale": "x"}})
    assert same.verdict == "same" and same.confidence == 0.9
    low = A.to_adjudication({"model": "m", "json": {"same_campaign": True, "same_operator": False, "confidence": 0.3, "rationale": "x"}})
    assert low.verdict == "unsure"
    diff = A.to_adjudication({"model": "m", "json": {"same_campaign": False, "same_operator": False, "confidence": 0.95, "rationale": "x"}})
    assert diff.verdict == "different"
    veto = A.to_adjudication({"model": "m", "json": {"same_campaign": False, "same_operator": False, "confidence": 0.95, "rationale": "x"}},
                             {"engine_score": 4.2})
    assert veto.verdict == "veto"
    miss = A.to_adjudication({"missing": True, "error": "offline"})
    assert miss.verdict == "unsure" and miss.confidence == 0.0


def test_prompt_from_structured_dossier():
    p = A.build_prompt({"a": {"x": 1}, "b": {"x": 2}, "evidence": [{"type": "t", "value": "v", "weight": 3}]})
    assert "Incident A features" in p and '"weight": 3' in p
    assert A.build_prompt({"prompt": "raw"}) == "raw"


def test_fbank_shape_and_voice_unit_norm():
    x = (np.random.RandomState(0).randn(16000 * 3) * 3000).astype(np.float32)
    f = voice.fbank(x)
    assert f.shape[1] == 80 and f.shape[0] == 1 + (len(x) - 400) // 160


def test_incident_id_for_dane_layout():
    assert incident_id_for("/x/do_udostępnienia/47/clip.mp4") == "d47"
    assert incident_id_for("/x/other/clip.mp4") is None
