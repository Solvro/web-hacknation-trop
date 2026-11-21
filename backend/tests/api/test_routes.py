"""Every route in mock mode (httpx TestClient)."""
import json
import re

from trop.schema import BOT_STEPS

P = "/api/v1"
IDS = {"{incident_id}": "INC-24817", "{cid}": "KMP-017", "{oid}": "OP-03", "{job_id}": "JOB-DEMO", "{iid}": "INV-3", "{pid}": "ACT-7", "{tid}": "TRI-1",
       "{sid}": "SRC-meta", "{rid}": "RUN-x", "{a}": "INC-24817", "{b}": "KMP-017", "{type}": "tracking", "{value:path}": "cg-7f3a91e0.ecs.eu-west-1.on.aws/events",
       "{campaign_id}": "KMP-017", "{name}": "x.svg"}
SKIP = ("/stream", "/events", "/oracle/stream", "/mock/asset", "/lab/runs", "/batch/", "/jobs/{job_id}", "/openapi", "/docs", "/download")


def test_every_get_route_answers_200(client):
    paths = client.get(f"{P}/openapi.json").json()["paths"]
    n = 0
    for path, ops in paths.items():
        if "get" not in ops or any(s in path for s in SKIP):
            continue
        url = path.replace("/operations/{oid}", "/operations/OPN-01").replace("/persons/{pid}", "/persons/P-01")
        for k, v in IDS.items():
            url = url.replace(k, v)
        if "{" in url:
            url = re.sub(r"\{[^}]+\}", "KMP-017", url)
        if path.endswith("merge-preview"):
            url += "?other=KMP-043"
        r = client.get(url)
        assert r.status_code == 200, (url, r.status_code, r.text[:200])
        n += 1
    assert n >= 40


def test_openapi_complete(client):
    o = client.get(f"{P}/openapi.json").json()
    for p in ["/health", "/stats/overview", "/analyze", "/jobs/{job_id}/stream", "/incidents/{incident_id}/decision", "/links/{a}/{b}", "/campaigns/{cid}/merge-preview",
              "/graph", "/operations", "/batch/{job_id}/results.csv", "/traces/{type}/{value}", "/oracle/stream", "/public/check", "/triage/{tid}/decision"]:
        assert f"{P}{p}" in o["paths"], p
    assert o["components"]["schemas"]["Decision"]


def test_health_and_header(client):
    r = client.get(f"{P}/health")
    assert r.json()["mode"] == "mock" and r.headers["x-trop-mode"] == "mock"


def test_inc_24817_numbers(client):
    d = client.get(f"{P}/incidents/INC-24817/decision").json()
    assert d["decision"] == "assign" and d["campaign_id"] == "KMP-017" and d["p"] == 0.94 and d["coverage"] == 0.78
    assert d["set"] == ["KMP-017"] and d["runner_up"]["campaign_id"] == "KMP-034" and d["runner_up"]["p"] == 0.41 and d["margin"] == 0.53
    ev = [(e["type"], e["strength"], e["weight"], e["df"]) for e in d["evidence"] if e["state"] in ("match", "zero")]
    assert ev == [("tracking", "H", 3.1, 47), ("kit", "H", 2.7, 58), ("content", "H", 2.2, 22), ("infra", "M", 1.4, 6), ("visual", "M", 0.9, 9),
                  ("persons", "M", 0.8, 61), ("ad", "L", 0.3, 140), ("infra", "L", 0.0, 512)]
    inc = client.get(f"{P}/incidents/INC-24817").json()
    assert inc["decision"]["p"] == 0.94 and inc["landing"]["host"] == "morvanta.click"


def test_consistent_counts(client):
    c = client.get(f"{P}/campaigns/KMP-017").json()
    assert (c["n_incidents"], c["n_domains"], c["counts"]["advertisers"], c["operator_id"]) == (46, 19, 11, "OP-03")
    assert len(client.get(f"{P}/campaigns/KMP-017/members?limit=500").json()) == 46
    ind = client.get(f"{P}/campaigns/KMP-017/indicators").json()
    assert len(ind["domains"]) == 19 and sum(d["on_certpl"] for d in ind["domains"]) == 5 and len(ind["advertisers"]) == 11
    assert [v["id"] for v in client.get(f"{P}/campaigns/KMP-017/variants").json()] == ["V2", "V1", "V3"]
    ids = {x["id"] for x in client.get(f"{P}/campaigns").json()}
    assert {"KMP-017", "KMP-034", "KMP-022", "KMP-031", "KMP-040", "KMP-043"} <= ids
    assert client.get(f"{P}/operators/OP-03").json()["codename"] == "Kestrel"
    s = client.get(f"{P}/stats/overview").json()
    assert s["N"] == 1284 and s["campaigns_active"] == 41 and s["operators"] == 6


def test_links_and_diff(client):
    a = client.get(f"{P}/links/INC-24817/KMP-017").json()
    b = client.get(f"{P}/links/INC-24817/KMP-034").json()
    assert a["decision"] == "linked" and b["decision"] == "not_linked" and b["shared_level"] == "L3"
    assert client.get(f"{P}/links/INC-24817/INC-24900?view=diff").json()["text"]["a_tokens"]


def test_merge_flow(client):
    p = client.get(f"{P}/campaigns/KMP-017/merge-preview?other=KMP-043").json()
    assert p["before"] == {"KMP-017": 46, "KMP-043": 4} and p["after"] == {"KMP-017": 50}
    r = client.post(f"{P}/campaigns/KMP-017/merge", json={"other_id": "KMP-043"})
    assert r.status_code == 200 and r.json()["n_incidents"] == 50


def test_analyze_url_and_job_state(client):
    r = client.post(f"{P}/analyze", data={"url": "https://morvanta.click/?utm_source=x"})
    assert r.status_code == 200
    jid = r.json()["job_id"]
    assert jid.startswith("JOB-") and r.json()["incident_id"] == "INC-24817"
    stream = client.get(f"{P}/jobs/{jid}/stream").text
    assert "job.done" in stream
    j = client.get(f"{P}/jobs/{jid}").json()
    assert j["status"] == "done" and j["decision"] == "assign" and j["total_ms"] == 19600
    assert [s["key"] for s in j["steps"]] == [k for k, _, _ in BOT_STEPS]
    assert any(x["id"] == jid for x in client.get(f"{P}/jobs").json())


def test_analyze_upload_trace_and_new(client, tmp_path):
    r = client.post(f"{P}/analyze", files=[("files", ("shot.png", b"\x89PNG", "image/png"))])
    assert r.status_code == 200 and r.json()["job_id"]
    t = client.post(f"{P}/analyze", data={"trace": "cg-7f3a91e0"})
    assert t.json()["job_id"] is None
    n = client.post(f"{P}/analyze", data={"url": "https://bonenergetyczny24.site/"}).json()
    assert n["incident_id"] == "INC-24901"
    assert client.get(f"{P}/incidents/INC-24901/decision").json()["decision"] == "new"
    assert client.post(f"{P}/analyze").status_code == 422


def test_investigation_flow(client):
    inv = client.get(f"{P}/investigations/INV-3").json()
    assert inv["seed"] == "velmoria.click" and inv["status"] == "done" and inv["budget"]["steps"] == 20
    new = client.post(f"{P}/investigations", json={"seed": "velmoria.click", "campaign_id": "KMP-017"}).json()["id"]
    assert client.get(f"{P}/investigations/{new}/stream").text.count("agent.step") >= 9
    assert client.get(f"{P}/investigations/{new}").json()["status"] == "done"
    assert client.post(f"{P}/investigations/{new}/steer", json={"message": "sprawdź ASN"}).json()["ok"]
    assert client.post(f"{P}/investigations/INV-3/promote", json={"campaign_id": "KMP-017", "node_ids": ["a", "b"]}).json()["added"] == 2


def test_oracle_act_triage_hunter_lab_public(client):
    preds = client.get(f"{P}/oracle/predictions").json()
    assert {p["domain"]: p["dna_score"] for p in preds}["orvinta.click"] == 0.93
    m = client.get(f"{P}/oracle/metrics").json()
    assert m["precision_at_20"] == 0.85 and m["median_lead_h"] == 31.0
    assert client.patch(f"{P}/oracle/dna/KMP-017", json={"threshold": 0.7}).json()["threshold"] == 0.7
    # act
    pkg = client.post(f"{P}/act/packages", json={"campaign_id": "KMP-017", "kind": "dsa"}).json()
    assert pkg["status"] == "draft" and pkg["id"].startswith("ACT-")
    assert client.post(f"{P}/act/packages/{pkg['id']}/submit", json={"confirm": False}).status_code == 422
    sent = client.post(f"{P}/act/packages/{pkg['id']}/submit", json={"confirm": True}).json()
    assert sent["status"] == "sent" and "Nic nie zostało wysłane" in sent["disclaimer"]
    for fmt, mime in [("pdf", "application/pdf"), ("json", "application/json"), ("csv", "text/csv"), ("stix", "application/json"), ("misp", "application/json")]:
        r = client.get(f"{P}/act/packages/ACT-7/download?format={fmt}")
        assert r.status_code == 200 and r.headers["content-type"].startswith(mime)
    assert client.get(f"{P}/act/packages/ACT-7/download?format=stix").json()["type"] == "bundle"
    assert client.post(f"{P}/act/rules/test", json={"kind": "yara", "body": "x"}).json()["precision"] == 0.93
    # triage
    t = client.get(f"{P}/triage").json()
    assert len(t["items"]) == 23 and t["facets"]["type"]["uncertain"] == 8
    it = client.get(f"{P}/triage/TRI-1").json()
    assert it["candidates"][0]["for"]
    assert client.post(f"{P}/triage/TRI-1/decision", json={"action": "accept", "campaign_id": "KMP-034"}, headers={"If-Match": "9"}).status_code == 409
    ok = client.post(f"{P}/triage/TRI-1/decision", json={"action": "accept", "campaign_id": "KMP-034"}, headers={"If-Match": "1"})
    assert ok.status_code == 200 and ok.json()["item"]["status"] == "closed" and ok.json()["feedback_id"]
    assert client.get(f"{P}/triage?status=open").json()["items"].__len__() == 22
    # hunter
    assert len(client.get(f"{P}/hunter/sources").json()) == 6
    assert client.get(f"{P}/hunter/sources?fields=credentials_status").json()[0]["status"]
    assert client.patch(f"{P}/hunter/sources/SRC-meta", json={"enabled": False}).json()["status"] == "disabled"
    assert client.post(f"{P}/hunter/sources/SRC-meta/run").json()["run_id"]
    # lab (marked sample)
    lab = client.get(f"{P}/lab/metrics?view=summary").json()
    assert lab["data"]["sample"] is True and lab["data"]["bcubed_f1"] == 0.91
    run = client.post(f"{P}/lab/stress", json={}).json()
    assert client.get(f"{P}/lab/runs/{run['run_id']}").json()["status"] == "done"
    # public never says safe / never leaks KMP ids
    chk = client.post(f"{P}/public/check", data={"url": "https://velmoria.click/x"}).json()
    assert chk["verdict"] == "scam" and "KMP-" not in json.dumps(chk)
    assert client.post(f"{P}/public/check", data={"url": "https://example.test"}).json()["verdict"] == "unknown"
    mt = client.post(f"{P}/public/extension/match", json={"caption": "PILNE: przerywa milczenie po napaści"}).json()
    assert mt["match"] and "KMP-" not in json.dumps(mt)
    assert client.post(f"{P}/public/report", json={"url": "https://x.test"}).json()["ok"]


def test_search_graph_traces_persons_batch(client):
    kinds = {h["kind"] for h in client.get(f"{P}/search?q=morvanta").json()}
    assert {"incident", "domain"} <= kinds
    assert any(h["id"] == "KMP-017" for h in client.get(f"{P}/search?q=zamach").json())
    g = client.get(f"{P}/graph?focus=KMP-017").json()
    assert g["focus"] == "KMP-017" and g["panel"] and g["nodes"] and g["hulls"]
    assert client.get(f"{P}/graph?scope=campaign:KMP-034").json()["nodes"]
    t = client.get(f"{P}/traces/tracking/cg-7f3a91e0.ecs.eu-west-1.on.aws/events").json()
    assert t["campaigns"][0]["id"] == "KMP-017" and len(t["latest"]) == 5
    assert client.get(f"{P}/evidence/values/tracking/cg-7f3a91e0.ecs.eu-west-1.on.aws/events").json()["df"] == 47
    assert "Raport" in client.get(f"{P}/persons?format=brief").text
    assert client.get(f"{P}/persons/P-01").json()["name"] == "Jan Kowalski"
    b = client.post(f"{P}/batch", files=[("files", ("a.png", b"x", "image/png"))]).json()["job_id"]
    res = client.get(f"{P}/batch/{b}").json()
    assert res["n_items"] == len(res["rows"]) > 0
    csv = client.get(f"{P}/batch/{b}/results.csv")
    assert csv.text.splitlines()[0].startswith("item,incident_id,decision,campaign")
    assert client.get(f"{P}/operations/OPN-01").json()["campaigns"][0] == "KMP-017"


def test_404s_and_pagination(client):
    assert client.get(f"{P}/incidents/INC-0").status_code == 404
    assert client.get(f"{P}/campaigns/KMP-999").status_code == 404
    r = client.get(f"{P}/incidents?limit=10")
    assert len(r.json()) == 10 and r.headers["x-next-cursor"] == "10"
    assert len(client.get(f"{P}/incidents?limit=10&cursor=10").json()) == 10
    assert all(i["campaign_id"] == "KMP-022" for i in client.get(f"{P}/incidents?campaign_id=KMP-022&limit=100").json())
