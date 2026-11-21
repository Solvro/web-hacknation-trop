"""Act package building on the FICTIONAL KMP-017 dossier (BRIEF universe); no model calls, nothing sent."""
from __future__ import annotations

import json
import re

import pytest

from trop.act import rules as R
from trop.act import service as S
from trop.act.campaign import fictional_kmp017, load_campaign
from trop.config import settings
from trop.schema import ActPackage, ActPackageCreate, RuleTest


@pytest.fixture(autouse=True)
def _tmp_data(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)


@pytest.fixture
def pkg() -> ActPackage:
    return S.create_package(ActPackageCreate(campaign_id="KMP-017"), use_llm=False)


def test_fixture_matches_board_7():
    d = load_campaign("KMP-017")
    assert d["fictional"] and d["counts"]["ads"] == 46 and d["counts"]["advertisers"] == 11 and d["counts"]["domains"] == 29
    assert sum(1 for x in d["domains"] if not x["on_certpl"]) == 24
    assert sum(1 for x in d["domains"] if x["source"] == "investigation") == 10


def test_package_shape(pkg):
    assert pkg.id.startswith("ACT-") and pkg.status == "ready" and pkg.campaign_id == "KMP-017"
    assert pkg.contents == {"ads": 46, "advertisers": 11, "domains": 29, "evidence_items": 7, "certpl_new": 24}
    rec = {r["id"]: r for r in pkg.recipients}
    assert rec["meta_dsa"]["enabled"] and rec["certpl"]["progress"]["total"] == 24 and not rec["registrar"]["enabled"]
    assert {p["bot"] for p in pkg.parts} >= {"zwiadowca", "archiwista", "notariusz", "tropiciel", "sedzia"}
    assert "art. 16 DSA" in pkg.notice_text and "46 reklam" in pkg.notice_text
    assert pkg.disclaimer.startswith("Nic nie zostało wysłane")
    assert S.get_package(pkg.id) == pkg and S.list_packages("KMP-017")[0].id == pkg.id


def test_pdf_has_polish_text_and_all_ads(pkg):
    data, mime, name = S.download(pkg.id, "pdf")
    assert mime == "application/pdf" and data[:5] == b"%PDF-" and name.endswith(".pdf") and len(data) > 20_000
    assert b"DejaVu" in data          # embedded font -> diacritics render without system fonts


def test_json_lists_every_ad_advertiser_domain_and_art16_parts(pkg):
    j = json.loads(S.download(pkg.id, "json")[0])
    assert len(j["ads"]) == 46 and len({a["library_id"] for a in j["ads"]}) == 46
    assert len(j["advertisers"]) == 11 and len(j["domains"]) == 29 and j["evidence"]
    art = j["dsa_art16"]
    assert art["explanation"] and art["legal_basis"] and art["notifier"]["email"] and "dobrej wierze" in art["good_faith_statement"]
    assert len(j["certpl"]["domains_not_listed"]) == 24 and "CERT Polska" in j["certpl"]["draft"]
    assert j["fictional"] is True


def test_stix_bundle_is_valid_2_1(pkg):
    b = json.loads(S.download(pkg.id, "stix")[0])
    assert b["type"] == "bundle" and b["id"].startswith("bundle--")
    objs = b["objects"]
    ids = {o["id"] for o in objs}
    assert len(ids) == len(objs)
    inds = [o for o in objs if o["type"] == "indicator"]
    assert len(inds) == 29 and all(re.fullmatch(r"\[domain-name:value = '[a-z0-9.-]+'\]", i["pattern"]) for i in inds)
    for o in objs:
        assert re.fullmatch(r"[a-z-]+--[0-9a-f-]{36}", o["id"]) and o.get("spec_version") == "2.1"
        if o["type"] == "relationship":
            assert o["source_ref"] in ids and o["target_ref"] in ids
    camp = next(o for o in objs if o["type"] == "campaign")
    assert "fictional" in camp["labels"]
    # stable ids across exports
    assert json.loads(S.download(pkg.id, "stix")[0])["objects"][1]["id"] == camp["id"]


def test_misp_csv_certpl_formats(pkg):
    m = json.loads(S.download(pkg.id, "misp")[0])
    assert sum(1 for a in m["Event"]["Attribute"] if a["type"] == "domain") == 29
    csv = S.download(pkg.id, "csv")[0].decode()
    assert csv.startswith("kind,value") and csv.count("\ndomain,") == 29
    txt = S.download(pkg.id, "certpl")[0].decode()
    assert "24 domen" in txt and "plessuro.live" in txt and "velmoria.click" not in txt   # velmoria is already listed
    with pytest.raises(ValueError):
        S.download(pkg.id, "exe")


def test_submit_never_sends_but_exports_and_logs(pkg, tmp_path, monkeypatch):
    import httpx
    monkeypatch.setattr(httpx.Client, "send", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network!")))
    events = []
    p = S.submit(pkg.id, emit=lambda t, d: events.append((t, d)))
    assert p.status == "sent" and p.sent_at and p.disclaimer.startswith("Nic nie zostało wysłane")
    assert all(r["status"] == "prepared" for r in p.recipients if r["enabled"])
    exp = tmp_path / "act" / pkg.id / "export"
    assert {f.suffix for f in exp.iterdir()} >= {".pdf", ".json", ".csv", ".txt"}
    log = [json.loads(x) for x in (tmp_path / "act" / "submissions.jsonl").read_text().splitlines()]
    assert log[-1]["sent_externally"] is False and log[-1]["package_id"] == pkg.id
    assert events == [("act.submitted", {"package_id": pkg.id, "kind": "bundle", "campaign_id": "KMP-017"})]
    # editing the notice after export puts it back to ready
    assert S.update_notice(pkg.id, "Nowa treść.").status == "ready"


def test_rules_and_rule_test_on_fictional_set():
    d = load_campaign("KMP-017")
    rl = R.rules_for(d)
    assert {r.kind for r in rl} == {"urlscan", "url_regex", "html_signature"}
    for r in rl:
        t = R.test_rule(r.kind, r.body, dossier=d)
        assert isinstance(t, RuleTest) and t.tp > 0 and t.benign_hits == 0 and t.precision == 1.0
        assert t.benign_total == len(R.BENIGN)
    broad = R.test_rule("html_signature", r"(?i)gazeta|bank|giełda", dossier=d)
    assert broad.benign_hits > 0 and broad.precision < 1.0
    assert R.test_rule("url_regex", "([", dossier=d).hits == 0          # invalid regex -> empty result, no crash


def test_promoted_domains_join_the_dossier(tmp_path):
    (tmp_path / "investigations").mkdir()
    (tmp_path / "investigations" / "promotions.jsonl").write_text(json.dumps(
        {"campaign_id": "KMP-017", "investigation_id": "INV-DEMO", "kind": "domain", "label": "nowydomen.click",
         "level": "campaign", "evidence": [{"type": "asset_sha256"}], "certpl": False}) + "\n")
    d = load_campaign("KMP-017")
    assert d["counts"]["domains"] == 30 and d["domains"][-1]["source"] == "investigation"


def test_fixture_is_deterministic():
    assert fictional_kmp017() == fictional_kmp017()
