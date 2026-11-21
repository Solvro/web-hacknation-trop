"""Oracle on fully synthetic (fictional) domains: DNA training, backtest protocol, predictions persistence."""
import json
import random
from datetime import datetime, timedelta, timezone

import pytest

from trop.oracle import backtest as bt
from trop.oracle import data, service
from trop.oracle.model import DomainModel, build_dna, meta_bonus

C, V = "bcdfghklmnprstvxz", "aeiou"


def cv_word(rng, n):
    return "".join(rng.choice(C) + rng.choice(V) for _ in range(n))


def make_pos(n=60, seed=1):
    rng = random.Random(seed)
    t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    out = []
    for i in range(n):
        d = (cv_word(rng, 5) + ".autos") if i % 3 else f"{rng.choice(['alpha', 'delta', 'omega'])}-{cv_word(rng, 3)}-app.com"
        ct = t0 + timedelta(hours=7 * i)
        out.append({"domain": d, "cert_time": ct.isoformat(), "first_seen": (ct + timedelta(hours=30 + i % 5)).isoformat(),
                    "first_activity_source": "test", "registrar": "NameCheap, Inc.", "ns": ["ada.ns.test", "bob.ns.test"],
                    "issuer": "C=US, O=Let's Encrypt, CN=R11"})
    return out


def make_neg(n=400, seed=2):
    rng = random.Random(seed)
    words = ["garden", "market", "travel", "books", "kitchen", "sport", "news", "health", "music", "cars", "bank", "school"]
    out = []
    for i in range(n):
        d = f"{rng.choice(words)}{rng.choice(words)}{rng.choice(['', '24', 'pl'])}"
        out.append({"domain": d + rng.choice([".com", ".pl", ".net", ".autos"]), "kind": "benign" if i % 2 else "other_scam"})
    return out


def test_model_separates_grammar():
    pos, neg = make_pos(), make_neg()
    m = DomainModel().fit([r["domain"] for r in pos], [r["domain"] for r in neg])
    sp = m.p_lex(["tokabuhelo.autos", "delta-kahuno-app.com"])
    sn = m.p_lex(["gardenmarket.com", "newsbooks.pl"])
    assert sp.min() > sn.max()
    assert m.explain("tokabuhelo.autos")


def test_backtest_protocol_temporal_split_and_lead_times():
    pos, neg = make_pos(), make_neg()
    res = bt.run_backtest(pos, neg, train_frac=0.6, fpr=0.02, ct_latency_h=0.25)
    s = res["summary"]
    assert s["n_train_pos"] == 36 and s["n_test_pos"] == 24
    assert s["auc"] > 0.9 and s["recall_at_thr"] > 0.5
    assert s["precision_at_k"]["1:10"]["p@20"] >= 0.8
    assert s["median_lead_h_positive"] and s["median_lead_h_positive"] > 20       # flagged ~30 h before first activity
    flagged = [r for r in res["rows"] if r["flagged"]]
    assert flagged and all(r["lead_h"] is not None for r in flagged)


def test_meta_bonus_and_dna():
    pos = make_pos()
    dna = build_dna("KIT-T", pos, 0.99, 0.5)
    assert dna.tld_dist["autos"] > 0.5 and "namecheap" in dna.registrars
    b, why = meta_bonus(dna, {"ns": ["ada.ns.test", "bob.ns.test"], "registrar": "NameCheap Inc."})
    assert b >= 2.5 and any("NS pair" in w for w in why)
    assert meta_bonus(dna, {"ns": ["x.other", "y.other"]})[0] == 0


def test_service_train_predict_confirm(tmp_trop):
    d = data.oracle_dir()
    (d / "training.json").write_text(json.dumps(make_pos()))
    (d / "negatives.json").write_text(json.dumps(make_neg()))
    out = service.train(run_backtest=True)
    assert out["threshold"] and out["backtest"]["auc"] > 0.9 and (d / "backtest.json").is_file()
    got = []
    service.set_notifier(got.append)
    try:
        preds = service.predict([
            {"domain": "tohakuvolo.autos", "issuer": "C=US, O=Let's Encrypt, CN=R11", "not_before": "2026-11-20T10:00:00+00:00"},
            {"domain": "gardenmarket.com", "not_before": "2026-11-20T10:00:00+00:00"},
            {"domain": "tohakuvolo.xyz", "not_before": "2026-11-20T10:00:00+00:00"}], enrich_hits=False)
    finally:
        service.set_notifier(None)
    assert [p.domain for p in preds] == ["tohakuvolo.autos"] and got and preds[0].campaign_id == "KIT-A"
    assert service.list_predictions()[0].status == "predicted"
    c = service.confirm("tohakuvolo.autos", "2026-11-21T10:00:00+00:00")
    assert c.status == "confirmed" and c.lead_time_h == 24.0
    m = service.get_metrics()
    assert m.confirmed == 1 and m.precision_at_20 is not None and m.backtest
    assert service.predict([{"domain": "tohakuvolo.autos", "not_before": "x"}], enrich_hits=False) == []   # no duplicates
