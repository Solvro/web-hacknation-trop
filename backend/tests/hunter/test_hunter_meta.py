"""Hunter: Meta ads_archive -> IncidentDraft (fictional fixture), snapshot link parsing, sink, scheduler, sources, bundle."""
import json
from pathlib import Path

from trop.enrich import cache
from trop.hunter import gazetteer, meta, runner, scheduler, sink, snapshot, sources
from trop.schema import HunterRun, IncidentDraft

FIX = Path(__file__).parent / "fixtures" / "ads_archive_fictional.json"


def _ads():
    return json.loads(FIX.read_text(encoding="utf-8"))["data"]


def test_to_draft_maps_ad_layer_and_redacts_token():
    ad = _ads()[1]
    ad["ad_snapshot_url"] = "https://www.facebook.com/ads/archive/render_ad/?id=1&access_token=SECRETTOKEN123"
    d = meta.to_draft(ad, "HR-test")
    assert isinstance(d, IncidentDraft) and d.source.type == "hunter" and d.source.ref == f"meta:{ad['id']}"
    assert d.ad.platform == "meta" and d.ad.library_id == ad["id"] and d.ad.advertiser == "Example Flux Studio"
    assert "Rafał Brzoska" in d.content.persons            # gazetteer (never ad.persons: that is face-gallery only)
    assert d.ad.persons == []
    assert "SECRETTOKEN123" not in d.model_dump_json()
    assert d.quality.missing == ["landing_url", "creative_media"]


def test_lure_score_and_selection():
    ads = _ads()
    assert gazetteer.lure_score(ads[1]["ad_creative_bodies"][0]) > gazetteer.lure_score("Sprzedam rower")
    assert len(runner._select(ads, 1)) == 1


def test_fetch_replays_from_cache_offline(tmp_trop):
    params = meta.build_params("PILNE", ["PL"], limit=5)
    import hashlib
    key = hashlib.sha256(json.dumps([params, 1], sort_keys=True).encode()).hexdigest()[:24]
    cache.put("meta", key, cache.Result("ok", _ads()))
    assert len(meta.fetch(params, max_pages=1)) == 2          # served from cache, no token needed
    assert meta.fetch(meta.build_params("other", ["PL"]), 1) == []   # offline miss -> empty, no network


def test_snapshot_landing_from_href():
    assert snapshot.landing_from_href("https://l.facebook.com/l.php?u=https%3A%2F%2Fshop-zz.xyz%2Fp%3Fa%3D1&h=x") == "https://shop-zz.xyz/p?a=1"
    assert snapshot.landing_from_href("https://www.facebook.com/page") is None
    assert snapshot.landing_from_href("https://instagram.com/x") is None
    assert snapshot.landing_from_href("https://shop-zz.xyz/") == "https://shop-zz.xyz/"


def test_sink_writes_drafts_and_runs(tmp_trop):
    d = meta.to_draft(_ads()[0], "HR-x")
    sink.write_draft("HR-x", d)
    run = HunterRun(id="HR-x", source_id="meta_adlibrary", started_at="2026-11-21T00:00:00+00:00", found=2, status="ok")
    sink.write_run(run)
    assert [r.id for r in sink.list_runs()] == ["HR-x"]
    assert sink.load_drafts("HR-x")[0].ad.library_id == _ads()[0]["id"]
    sink.set_publisher(lambda draft: "INC-1")
    try:
        assert sink.publish(d) == "INC-1"
    finally:
        sink.set_publisher(None)


def test_sources_and_scheduler(tmp_trop):
    srcs = {s.id: s for s in sources.list_sources()}
    assert set(srcs) == {"meta_adlibrary", "certpl", "urlscan", "google_ads_transparency"}
    assert srcs["certpl"].credentials_status == "not_needed"
    sch = scheduler.build_scheduler(background=True)
    assert {j.id for j in sch.get_jobs()} == {"hunter:certpl", "hunter:meta", "hunter:urlscan", "hunter:google", "oracle:poll"}


def test_apply_bundle(tmp_path):
    b = tmp_path / "archive_shop-zz.xyz_20261121_000000_fb_inapp_android_pl"
    (b / "html").mkdir(parents=True)
    (b / "screenshots").mkdir()
    (b / "screenshots" / "viewport.png").write_bytes(b"\x89PNG")
    (b / "archive_info.json").write_text(json.dumps({"url": "https://shop-zz.xyz/a", "final_url": "https://shop-zz.xyz/b", "status": 200,
                                                      "title": "Fiction", "timestamp_utc": "2026-11-21T00:00:00+00:00"}))
    (b / "dns_ssl.json").write_text(json.dumps({"ip": "192.0.2.7"}))
    (b / "page_text.txt").write_text("Witaj")
    (b / "html" / "rendered.html").write_text("<script>fbq('init','123456789012345');gtag('G-ABCDEF1234')</script>")
    (b / "forms.json").write_text("[]")
    (b / "redirects.json").write_text(json.dumps([{"url": "https://shop-zz.xyz/a"}, {"url": "https://shop-zz.xyz/b"}]))
    (b / "outlinks.json").write_text("[]")
    d = runner.apply_bundle(meta.to_draft(_ads()[0], "HR-y"), b)
    assert d.landing.host == "shop-zz.xyz" and d.landing.etld1 == "shop-zz.xyz" and d.landing.title == "Fiction"
    assert d.tracking.fb_pixels == ["123456789012345"] and d.tracking.ga4 == ["G-ABCDEF1234"]
    assert d.infra.domains[0].ips == ["192.0.2.7"] and d.source.path == str(b)
    assert "landing_url" not in d.quality.missing


def test_google_atc_disabled_without_adc(monkeypatch, tmp_path):
    from trop.hunter import google_atc
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setattr(google_atc, "DEFAULT_ADC", tmp_path / "missing.json")
    monkeypatch.setattr(google_atc, "credentials_path", lambda: None)
    assert google_atc.credentials_status() == "missing"
    assert google_atc.advertiser_lookup(["x"])["disabled"]


def test_pivot_values():
    incs = [{"landing": {"etld1": "a-zz.xyz"}, "tracking": {"asset_hashes": ["h1", "h2"], "capi_gateways": ["gw.example.com"]}, "infra": {}},
            {"landing": {"etld1": "b-zz.xyz"}, "tracking": {"asset_hashes": ["h1"], "capi_gateways": ["gw.example.com"]}, "infra": {}},
            {"landing": {"etld1": "c-zz.xyz"}, "tracking": {"asset_hashes": ["h3"]}, "infra": {}}]
    pv = runner.pivot_values(incs)
    assert [(k, v) for k, v, _ in pv] == [("capi_gateway", "gw.example.com"), ("asset_sha256", "h1")]
