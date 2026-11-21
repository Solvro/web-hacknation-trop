"""Enrichment: FS cache replay, offline guarantee, seeded cache -> engine-shaped `enrich` dicts (fictional domains)."""
import json

import httpx
import pytest

from trop.enrich import cache, certpl, crtsh, enrich, seed, tools

FICT = {  # run_infra.py output shape, invented domains
    "kit-one-zz.xyz": {
        "A": ["192.0.2.10"], "AAAA": [], "NS": ["ada.ns.cloudflare.com.", "bob.ns.cloudflare.com."], "MX": ["ERR:NoAnswer"], "TXT": ["ERR:NoAnswer"],
        "asn": {"192.0.2.10": {"asn": "64500", "prefix": "192.0.2.0/24", "cc": "ZZ", "name": "TEST-NET"}},
        "rdap": {"status_code": 200, "registrar": "Dynadot Inc", "created": "2026-10-08T18:20:08.697Z", "expires": "2027-10-08T18:20:08.697Z",
                 "updated": None, "ns": ["ada.ns.cloudflare.com", "bob.ns.cloudflare.com"], "status": []},
        "crtsh": [{"issuer": "C=US, O=Let's Encrypt, CN=R11", "not_before": "2026-10-08T19:00:00", "names": ["kit-one-zz.xyz"], "id": 1}],
    },
    "kit-two-zz.xyz": {
        "A": ["ERR:NXDOMAIN"], "AAAA": [], "NS": ["ns1.dyna-ns.net."], "MX": [], "TXT": [],
        "rdap": {"status_code": 200, "registrar": "Dynadot, LLC", "created": "2026-10-08T18:45:00.000Z", "ns": [], "status": []},
        "crtsh": [{"issuer": "C=US, O=Let's Encrypt, CN=R11", "not_before": "2026-10-08T19:20:00", "names": [], "id": 2}],
    },
}


@pytest.fixture()
def seeded(tmp_trop):
    p = tmp_trop / "infra_enrich.json"
    p.write_text(json.dumps(FICT))
    return seed.seed_from_file(p)


def test_cache_roundtrip_and_offline_miss(tmp_trop):
    assert cache.get("rdap", "domain:x-zz.xyz") is None
    cache.put("rdap", "domain:x-zz.xyz", cache.Result("ok", {"registrar": "R"}))
    assert cache.get("rdap", "domain:x-zz.xyz").data == {"registrar": "R"}
    r = cache.fetch_json("rdap", "domain:never-zz.xyz", "https://rdap.invalid/x")
    assert r.status == "offline"                      # offline mode: never goes to the network


def test_offline_never_touches_network(tmp_trop, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used in offline mode")
    monkeypatch.setattr(httpx.Client, "get", boom)
    out = enrich.enrich_domain("unseen-zz.xyz")
    assert out["domain"] == "unseen-zz.xyz"
    assert out.get("certs") == [] and out["ns"] == []


def test_seed_and_replay_engine_shape(seeded):
    assert seeded["domains"] == 2
    e1 = enrich.enrich_domain("kit-one-zz.xyz")
    assert e1["ns"] == ["ada.ns.cloudflare.com", "bob.ns.cloudflare.com"]       # trailing dots stripped, sorted
    assert e1["registrar"] == "Dynadot Inc" and e1["created"].startswith("2026-10-08T18:20")
    assert e1["certs"] == [{"issuer": "C=US, O=Let's Encrypt, CN=R11", "not_before": "2026-10-08T19:00:00"}]
    assert e1["asn"] == ["64500"]
    e2 = enrich.enrich_domain("kit-two-zz.xyz")
    assert e2["ns"] == []                                                       # parked NS pair is not operator evidence


def test_enrich_incident_adds_domain_enrich(seeded):
    inc = {"id": "t1", "landing": {"host": "www.kit-one-zz.xyz"},
           "infra": {"domains": [{"fqdn": "www.kit-one-zz.xyz", "etld1": "kit-one-zz.xyz"}]}}
    enrich.enrich_incident(inc)
    en = inc["infra"]["domains"][0]["enrich"]
    assert en["ns"] and en["registrar"] and en["created"] and en["certs"]
    # the engine joins NS lists with "|" for ns_pair
    assert "|".join(en["ns"]) == "ada.ns.cloudflare.com|bob.ns.cloudflare.com"


def test_certpl_check_and_diff(tmp_trop):
    d = certpl._dir()
    (d / "list.json").write_text(json.dumps({"bad-shop-zz.xyz": ["2026-11-01T00:00:00", None], "gone-zz.xyz": ["2026-10-01", "2026-11-02"]}))
    certpl._MEM.clear()
    assert certpl.check("https://www.bad-shop-zz.xyz/x")["listed"] is True
    assert certpl.check("gone-zz.xyz")["listed"] is False
    assert certpl.check("fine-zz.xyz")["listed"] is False
    assert certpl.check("x-zz.xyz")["listed"] is False


def test_tools_are_json_serialisable(seeded):
    for name in ("rdap", "dns_ns", "crtsh", "certpl_check"):
        res = tools.TOOLS[name]("kit-one-zz.xyz")
        json.dumps(res)
    assert set(tools.TOOLS) == {"crtsh", "rdap", "dns_ns", "urlscan_search", "certpl_check", "wayback", "adlib_search", "capture"}


def test_crtsh_normalisation():
    rows = [{"issuer_name": "C=US, O=Let's Encrypt, CN=R11", "not_before": "2026-01-01T00:00:00", "name_value": "a.x\nb.x", "id": 5}]
    n = crtsh._norm_crtsh(rows)
    assert n[0]["issuer"] == rows[0]["issuer_name"][-60:] and n[0]["names"] == ["a.x", "b.x"]
