"""Video/ASR evidence and the confirm-band adjudicator (veto/annotate only). Synthetic values are fictional."""
from __future__ import annotations

import copy

import pytest

from trop.engine import evidence
from trop.schema import Adjudication

WORDS = ("przewlekły ból pleców znika po jednym prostym rytuale który lekarze ukrywają przed pacjentami od lat a "
         "naukowcy z uniwersytetu potwierdzili że wystarczy dziesięć sekund dziennie aby odzyskać pełną sprawność").split()


def _inc(iid, text=None, voice=None, domains=None):
    return {"id": iid, "source": {}, "ad": {}, "landing": {}, "tracking": {}, "infra": {"domains": []},
            "content": {"video_domains": domains or []},
            "media": {"asr_text": text, "voice_id": voice, "video": {"gemini": {}}}}


def test_media_text_and_voice_evidence():
    text = " ".join(WORDS * 2)
    a, b = _inc("a", text, "VOICE-x"), _inc("b", text, "VOICE-x")
    c = _inc("c", None, "VOICE-x")
    evidence.prepare([a, b, c])
    df = evidence.doc_freq([a, b, c])
    ev, s = evidence.pair_evidence(a, b, df, 3)
    types = {e["type"]: e for e in ev}
    assert types["media_text"]["weight"] == pytest.approx(5.0) and types["media_text"]["layer"] == "content"
    assert "voice_id" in types and "voice_id" in evidence.OPERATOR_ONLY
    # same text + same voice: content agrees (5 >= 2.5) so the operator-only voice joins the campaign score (cap 4)
    assert s["score_campaign"] == pytest.approx(5.0 + types["voice_id"]["weight"])
    # a shared voice alone never reaches the campaign score
    ev2, s2 = evidence.pair_evidence(a, c, df, 3)
    assert any(e["type"] == "voice_id" for e in ev2) and s2["score_campaign"] == 0.0 and s2["score_operator"] > 0


def test_no_media_no_change():
    a, b = _inc("a"), _inc("b")
    evidence.prepare([a, b])
    ev, s = evidence.pair_evidence(a, b, evidence.doc_freq([a, b]), 2)
    assert ev == [] and s["score_campaign"] == 0.0


def _confirm_setup():
    """A video-only query in the confirm band (partly overlapping transcript, score ~2) against a one-incident corpus."""
    from trop.engine import decide
    from trop.engine.corpus import Corpus
    k = _inc("k", " ".join(WORDS * 2), None)
    q = _inc("q", " ".join(w if i % 8 else f"zmiana{i}" for i, w in enumerate(WORDS * 2)), None)
    corpus = Corpus.empty()
    corpus.add(k, "KMP-001")
    d, ctx = decide.decide(copy.deepcopy(q), corpus)
    return d, ctx, corpus


@pytest.mark.parametrize("verdict,conf", [("same", 0.99), ("veto", 0.9)])
def test_adjudicator_never_links(monkeypatch, verdict, conf):
    import sys
    import types
    from trop.engine import adjudicate
    fake = types.ModuleType("trop.media.adjudicator")
    fake.adjudicate = lambda dossier: Adjudication(model="fake", verdict=verdict, confidence=conf, rationale=["x"])
    monkeypatch.setitem(sys.modules, "trop.media.adjudicator", fake)
    d, ctx, corpus = _confirm_setup()
    if d.decision != "confirm":
        pytest.skip(f"fixture not in the confirm band ({d.decision}, {d.score})")
    cand = d.candidate_campaign_id
    adjudicate.apply(d, ctx, corpus)
    assert d.campaign_id is None and d.candidate_campaign_id == cand
    assert d.adjudicator is not None and d.adjudicator.verdict == verdict
    if verdict == "same":                       # never promotes to a link
        assert d.decision == "confirm" and d.why_not[0].bullets[0].startswith("Sędzia (LLM)")
    else:                                       # a veto removes the candidate link: confirm -> new
        assert d.decision == "new" and d.why_not[0].bullets[0].startswith("Sędzia odrzucił:")


@pytest.mark.parametrize("verdict,conf,final", [("different", 0.6, "new"), ("different", 0.25, "confirm"),
                                                ("unsure", 0.9, "confirm")])
def test_adjudicator_different_threshold(monkeypatch, verdict, conf, final):
    import sys
    import types
    from trop.engine import adjudicate
    fake = types.ModuleType("trop.media.adjudicator")
    fake.adjudicate = lambda dossier: Adjudication(model="fake", verdict=verdict, confidence=conf, rationale=["x"])
    monkeypatch.setitem(sys.modules, "trop.media.adjudicator", fake)
    d, ctx, corpus = _confirm_setup()
    assert d.decision == "confirm"
    adjudicate.apply(d, ctx, corpus)
    assert d.decision == final and d.campaign_id is None


def test_adjudicator_unavailable_is_silent(monkeypatch):
    import sys
    import types
    from trop.engine import adjudicate
    fake = types.ModuleType("trop.media.adjudicator")

    def boom(dossier):
        raise RuntimeError("no key")
    fake.adjudicate = boom
    monkeypatch.setitem(sys.modules, "trop.media.adjudicator", fake)
    d, ctx, corpus = _confirm_setup()
    note = adjudicate.apply(d, ctx, corpus)
    assert d.adjudicator is None and d.decision in ("confirm", "new", "insufficient")
    assert note == "" or "adjudicator" in note


def test_dossier_has_no_raw_text():
    from trop.engine.adjudicate import dossier
    inc = _inc("a", "tajny tekst strony")
    inc["landing"] = {"text": "PEŁNY TEKST", "etld1": "przyklad.pl"}
    d = dossier(inc)
    assert "PEŁNY TEKST" not in str(d) and "tajny tekst" not in str(d) and d["landing_domain"] == "przyklad.pl"


from trop.eval import data  # noqa: E402

HAVE = data.raw_dir("dane").exists() and (data.exp_dir("dane") / "media_gemini.json").exists()


@pytest.mark.skipif(not HAVE, reason="DANE / media_gemini.json absent")
def test_dane_video_layer(monkeypatch):
    monkeypatch.setenv("TROP_NO_LIVE", "1")
    from trop.ingest.pipeline import build_incident
    for name in ("5", "14", "47"):
        inc = build_incident(data.raw_dir("dane") / name, inc_id="d" + name)
        assert inc["quality"]["provenance"].get("video") == "experiments", name
        assert inc["media"].get("asr_text") and inc["media"].get("voice_id")
        assert all(f.get("source") != "gemini" for f in inc["media"].get("faces", []))   # persons only from SFace
