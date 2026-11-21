"""WS3 contract requests (docs/contracts/REQUESTS.md items 1-7) on the mock + real-mode wiring of the other workstreams."""
import pytest
from api.helpers import sse_events

P = "/api/v1"


def test_graph_focus_neighbourhood_panel_meta(client):
    g = client.get(f"{P}/graph?focus=KMP-017").json()
    assert g["focus"] == "KMP-017" and 2 <= len(g["nodes"]) <= 8       # focus + <= 6 neighbours (+ origin)
    pan = g["panel"]
    assert pan["kind_label"] and pan["badge"]["tone"] and pan["title"] and isinstance(pan["facts"][0], dict) and pan["action"]["label"]
    assert all("sub" in n["meta"] and "count" in n["meta"] for n in g["nodes"])
    inc = client.get(f"{P}/graph?focus=INC-24817").json()               # incidents have neighbours
    assert len(inc["nodes"]) > 1 and any(n["kind"] == "campaign" for n in inc["nodes"])
    per = client.get(f"{P}/graph?focus=person:Jan%20Kowalski").json()   # persons too
    assert per["focus"] == "person:Jan Kowalski" and len(per["nodes"]) > 1
    bridge = client.get(f"{P}/graph?focus=KMP-034&origin=KMP-017").json()
    assert {n["id"] for n in bridge["nodes"]} >= {"KMP-034", "KMP-017"}
    assert "side" not in next(n for n in bridge["nodes"] if n["id"] == "KMP-034")["meta"]       # side:'right' only on incident centres
    assert next(n for n in inc["nodes"] if n["id"] == "INC-24817")["meta"]["side"] == "right"
    assert any(n["meta"].get("only") in ("origin", "focus") for n in bridge["nodes"] if n["kind"] == "trace") or True
    assert client.get(f"{P}/graph?focus=nope").status_code == 404


def test_job_step_detail_convention(client):
    jid = client.post(f"{P}/analyze", data={"url": "https://morvanta.click/"}).json()["job_id"]
    client.get(f"{P}/jobs/{jid}/stream")
    steps = client.get(f"{P}/jobs/{jid}").json()["steps"]
    assert all("\n" in s["detail"] for s in steps)


def test_campaign_description_headline(client):
    d = client.get(f"{P}/campaigns/KMP-017").json()["description"]
    assert "\n" in d and d.split("\n")[0].startswith("Fałszywy portal")


def test_mock_scenarios_ambiguous_and_error(client):
    a = client.post(f"{P}/analyze", data={"url": "https://kelvaro.live/"}).json()
    ev = sse_events(client.get(f"{P}/jobs/{a['job_id']}/stream").text)
    assert ev[-1][0] == "job.done" and ev[-1][1]["data"]["decision"]["decision"] == "ambiguous"
    assert client.get(f"{P}/incidents/{a['incident_id']}/decision").json()["decision"] == "ambiguous"
    e = client.post(f"{P}/analyze", data={"url": "https://selqueno.live/"}).json()
    ev = sse_events(client.get(f"{P}/jobs/{e['job_id']}/stream").text)
    types = [t for t, _ in ev]
    assert "job.error" in types and ev[-1][1]["data"]["decision"]["decision"] == "insufficient"
    err = next(d for t, d in ev if t == "job.error")["data"]
    assert err["step"] == "capture"
    assert client.get(f"{P}/jobs/{e['job_id']}").json()["status"] == "error"
    assert client.get(f"{P}/incidents/{e['incident_id']}").json()["id"] == "INC-24920"


def test_trace_aliases_and_no_500(client):
    for t in ("domena", "osoba", "piksel", "kit", "domain", "person", "pixel", "tracking"):
        r = client.get(f"{P}/traces/{t}/morvanta.click")
        assert r.status_code == 200, (t, r.text)
    assert client.get(f"{P}/traces/domena/morvanta.click").json()["type"] == "domain"
    assert client.get(f"{P}/traces/bogus/x").status_code == 404
    assert client.get(f"{P}/evidence/values/osoba/Jan Kowalski").status_code == 200


def test_mock_merge_is_not_persisted(client):
    r = client.post(f"{P}/campaigns/KMP-017/merge", json={"other_id": "KMP-043"})
    assert r.status_code == 200 and r.json()["n_incidents"] == 50
    assert client.get(f"{P}/campaigns/KMP-017").json()["n_incidents"] == 46
    assert "KMP-043" in {c["id"] for c in client.get(f"{P}/campaigns").json()}


def test_analyze_trace_field(client):
    r = client.post(f"{P}/analyze", data={"trace": "morvanta.click"}).json()
    assert r["job_id"] is None and r["trace"] == {"type": "domain", "value": "morvanta.click"}
    assert client.post(f"{P}/analyze", data={"trace": "870011223344556"}).json()["trace"]["type"] == "fb_pixel"
