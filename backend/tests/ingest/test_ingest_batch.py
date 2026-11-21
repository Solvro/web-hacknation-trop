"""Ingest adapters, batch mode and the service API. Synthetic fixtures use fictional values only; the DANE batch test
reads DATA_DIR and skips when it is absent."""
from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

import pytest

from trop.engine import service
from trop.engine.corpus import Corpus
from trop.eval import data
from trop.ingest.adapters import batch_items, safe_unzip
from trop.ingest.pipeline import build_incident, validate

BODY = " ".join(["Niezwykła okazja inwestycyjna platforma zysk wypłata codziennie bez ryzyka"] * 12)


def _page(d: Path, host: str, pixel: str, title: str) -> Path:
    d.mkdir(parents=True)
    html = (f"<!-- saved from url=(0040)https://{host}/?utm_visit=aaaaaaaaaaaaaaaaaaaa -->"
            f"<html><head><title>{title}</title><script>fbq('init', '{pixel}');</script></head>"
            f"<body><h1>{title}</h1><p>{BODY}</p></body></html>")
    (d / "strona.html").write_text(html, encoding="utf-8")
    har = {"log": {"pages": [], "entries": [{"request": {"url": f"https://{host}/", "method": "GET"},
                                               "response": {"status": 200, "content": {"mimeType": "text/html", "text": html}},
                                               "serverIPAddress": "203.0.113.7", "startedDateTime": "2026-01-01T00:00:00Z"}]}}
    (d / "ruch.har").write_text(json.dumps(har), encoding="utf-8")
    return d


@pytest.fixture()
def fake_batch(tmp_path, monkeypatch):
    monkeypatch.setenv("TROP_NO_LIVE", "1")
    root = tmp_path / "wrapper" / "batch"
    _page(root / "a", "przyklad-jeden.pl", "111111111111111", "Fikcyjny nagłówek o wielkiej okazji")
    _page(root / "b", "przyklad-dwa.pl", "111111111111111", "Fikcyjny nagłówek o wielkiej okazji")
    _page(root / "c", "inny-przyklad.pl", "222222222222222", "Zupełnie inna historia zdrowotna")
    (root / "empty").mkdir()
    return tmp_path / "wrapper"


def test_batch_items_descend_and_kinds(fake_batch):
    items = batch_items(fake_batch)
    assert [i.name for i in items] == ["a", "b", "c", "empty"]
    assert items[0].kind == "sample_dir"


def test_extract_and_schema(fake_batch):
    inc = build_incident(fake_batch / "batch" / "a", inc_id="X1")
    assert inc["tracking"]["fb_pixels"] == ["111111111111111"]
    assert inc["landing"]["host"] == "przyklad-jeden.pl"
    assert validate(inc) == []


def test_batch_joint_clusters_without_corpus(fake_batch, tmp_path):
    from trop.ingest.cli import run_batch, write_results
    res = run_batch(fake_batch, Corpus.empty())
    rows = {r.item: r for r in res["rows"]}
    assert rows["a"].campaign == rows["b"].campaign != rows["c"].campaign
    assert rows["empty"].decision in ("insufficient", "new")
    c, j = write_results(res, tmp_path / "out" / "results.csv")
    got = list(csv.DictReader(open(c)))
    assert {"campaign", "operation", "decision", "top_evidence"} <= set(got[0]) and len(got) == 4
    assert json.load(open(j))["meta"]["n_items"] == 4


def test_zip_is_safe(tmp_path):
    zp = tmp_path / "x.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("../evil.txt", "no")
        z.writestr("/abs.txt", "no")
        z.writestr("ok/a.html", "<html></html>")
    out = safe_unzip(zp, tmp_path / "u")
    assert (out / "ok" / "a.html").exists()
    assert not (tmp_path / "evil.txt").exists() and not (out / "abs.txt").exists()


def test_progress_events_order(fake_batch):
    corpus = Corpus.empty()
    corpus.add(build_incident(fake_batch / "batch" / "a", inc_id="K1"), "KMP-001")
    ev = []
    d, inc, _ = service.analyze_path(fake_batch / "batch" / "b", corpus, inc_id="Q1", emit=lambda e, x: ev.append((e, x)))
    steps = [(x["step"]["key"], x["step"]["status"]) for e, x in ev if e == "job.step"]
    keys = [k for k, s in steps if s == "run"]
    assert keys == ["capture", "tracking", "content", "infra", "compare", "verdict"]
    assert any(e == "job.evidence" for e, _ in ev) and any(e == "job.ranking" for e, _ in ev)
    assert ev[-1][0] == "job.done"
    assert d.decision == "assign" and d.campaign_id == "KMP-001"
    ex = service.explain(inc, "KMP-001", corpus)
    assert ex.decision == "linked" and any(e.field == "fb_pixel" for e in ex.evidence)


DANE = data.raw_dir("dane")
HAVE = DANE.exists() and data.labels_path("labels.yaml") is not None and (data.exp_dir("sample_v1") / "incidents_q36.json").exists()


@pytest.mark.skipif(not HAVE, reason="DANE / labels absent")
def test_dane_batch_matches_labels(monkeypatch, tmp_path):
    monkeypatch.setenv("TROP_NO_LIVE", "1")
    from trop.ingest.cli import run_batch
    corpus = Corpus.load(tmp_path / "known.json")
    res = run_batch(DANE.parent, corpus)
    rows = {r.item: r for r in res["rows"]}
    assert len(rows) == 10 and not res["meta"]["errors"]
    assert res["meta"]["seconds"] < 120
    assert rows["1"].campaign == rows["2"].campaign == corpus.campaign_of["p1"]
    assert rows["3"].campaign == corpus.campaign_of["p5"]
    assert rows["48"].campaign == rows["61"].campaign and rows["48"].campaign.startswith("NEW-")
    new = [rows[k].campaign for k in ("10", "14", "36", "47", "48")]
    assert len(set(new)) == 5 and all(c.startswith("NEW-") for c in new)
    assert len({rows[k].operation for k in ("1", "2", "3", "48", "61")}) == 1     # one investment funnel (A + C + K)
