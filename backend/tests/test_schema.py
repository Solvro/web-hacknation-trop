import json
from pathlib import Path

from trop.schema import Decision, Incident, Job, json_schema

REPO = Path(__file__).resolve().parents[2]


def test_incident_accepts_engine_dicts():
    p = REPO / "data/experiments/dane/incidents_q36.json"
    if not p.exists():
        return
    for raw in json.loads(p.read_text()):
        inc = Incident.model_validate(raw)
        assert inc.id
        assert inc.model_dump()["tracking"]["kit_tenants"] == raw["tracking"].get("kit_tenants", [])


def test_job_has_six_bots():
    j = Job(id="JOB-1", input={"kind": "url", "name": "https://example.test"})
    assert [s.bot for s in j.steps] == ["zwiadowca", "tropiciel", "czytelnik", "notariusz", "archiwista", "sedzia"]


def test_decision_states():
    d = Decision(incident_id="x", decision="new", score=0.4)
    assert d.tau == 5.0 and d.delta == 1.0


def test_schema_dumps():
    s = json_schema()
    assert "$defs" in s and "Decision" in s["$defs"]
