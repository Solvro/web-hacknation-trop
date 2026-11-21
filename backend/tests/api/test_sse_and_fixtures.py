import json
from pathlib import Path

from pydantic import TypeAdapter

from api.helpers import sse_events
from trop.api import streams
from trop.api.mock import build
from trop.schema import (BOT_STEPS, Campaign, CampaignDNA, Decision, IncidentSummary, Indicators, Investigation, Member, Operation, Operator,
                         TriageItem, Event)

P = "/api/v1"
MOCK = Path(build.__file__).parent


def test_fixtures_validate_against_models():
    def load(n):
        return json.loads((MOCK / f"{n}.json").read_text())["data"]
    TypeAdapter(list[Campaign]).validate_python(load("campaigns"))
    TypeAdapter(dict[str, CampaignDNA]).validate_python(load("dna"))
    TypeAdapter(dict[str, list[Member]]).validate_python(load("members"))
    TypeAdapter(dict[str, Indicators]).validate_python(load("indicators"))
    TypeAdapter(list[IncidentSummary]).validate_python(load("incident_summaries"))
    TypeAdapter(dict[str, Decision]).validate_python(load("decisions"))
    TypeAdapter(list[Operator]).validate_python(load("operators"))
    TypeAdapter(list[Operation]).validate_python(load("operations"))
    TypeAdapter(list[Investigation]).validate_python(load("investigations"))
    TypeAdapter(list[TriageItem]).validate_python(load("triage"))


def test_fixtures_are_up_to_date(tmp_path):
    """The committed JSON equals a fresh build (run `python -m trop.api.mock.build` after editing the universe)."""
    for name, payload in build.build().items():
        fresh = json.loads(json.dumps(build.dump(payload), ensure_ascii=False))
        assert json.loads((MOCK / f"{name}.json").read_text()) == fresh, name


def test_job_stream_order(client):
    jid = client.post(f"{P}/analyze", data={"url": "https://morvanta.click/"}).json()["job_id"]
    ev = sse_events(client.get(f"{P}/jobs/{jid}/stream").text)
    types = [t for t, _ in ev]
    assert types[-1] == "job.done" and types.count("job.done") == 1
    runs = [(d["data"]["step"]["key"], d["data"]["step"]["status"]) for t, d in ev if t == "job.step"]
    keys = [k for k, _, _ in BOT_STEPS]
    assert [k for k, s in runs if s == "run"] == keys
    # per bot: run -> (evidence|finding)* -> done|warn, strictly nested, one bot at a time
    open_ = None
    for t, d in ev:
        if t == "job.step":
            st = d["data"]["step"]
            if st["status"] == "run":
                assert open_ is None
                open_ = st["key"]
            else:
                assert open_ == st["key"] and st["status"] in ("done", "warn", "skip", "error")
                open_ = None
        elif t in ("job.evidence", "job.finding"):
            assert open_ is not None
        elif t == "job.ranking":
            assert d["data"]["scores"]
    first_rank = types.index("job.ranking")
    assert [k for k, s in runs if s == "run"].index("compare") >= 0
    arch_run = next(i for i, (t, d) in enumerate(ev) if t == "job.step" and d["data"]["step"]["key"] == "compare" and d["data"]["step"]["status"] == "run")
    assert first_rank > arch_run
    done = ev[-1][1]["data"]
    assert done["decision"]["p"] == 0.94 and done["incident_id"] == "INC-24817"
    for _, d in ev:
        Event.model_validate(d)
    assert any(t == "job.evidence" for t in types) and any(t == "job.finding" for t in types)


def test_job_total_duration_is_19_6s():
    from trop.api import sequences as S
    seq = S.job_sequence("JOB-X", "known")
    assert 19.5 <= seq[-1][0] <= 19.8


def test_investigation_stream_and_demo_duration():
    from trop.api import sequences as S
    seq = S.investigation_sequence("INV-X")
    kinds = {e.type for _, e in seq}
    assert {"agent.step", "graph.node_added", "graph.edge_added", "casefile.delta", "investigation.decision", "investigation.done"} <= kinds
    assert 55 <= seq[-1][0] <= 70


def test_replay_demo(client):
    streams.generate_canned(Path(streams.replay_dir()))
    r = client.get(f"{P}/jobs/JOB-MINE/stream?replay=demo")
    ev = sse_events(r.text)
    assert ev[-1][0] == "job.done" and ev[-1][1]["data"]["job_id"] == "JOB-MINE"  # job_id rewritten
    inv = sse_events(client.get(f"{P}/investigations/INV-3/stream?replay=demo").text)
    assert inv[-1][0] == "investigation.done" and all(d["data"]["investigation_id"] == "INV-3" for _, d in inv)
    assert client.get(f"{P}/jobs/x/stream?replay=nope").status_code == 404


def test_canned_files_in_package_and_copy_to_data():
    names = {p.name for p in streams.PKG_REPLAY.glob("*.jsonl")}
    assert {"demo-analyze.jsonl", "demo-investigation.jsonl", "demo-events.jsonl", "demo-oracle.jsonl"} <= names
    lines = (streams.PKG_REPLAY / "demo-analyze.jsonl").read_text().splitlines()
    last = json.loads(lines[-1])
    assert last["type"] == "job.done" and 19.5 <= last["t"] <= 19.8
    streams.ensure_replay_files()
    assert (streams.replay_dir() / "demo-analyze.jsonl").exists()


def test_mock_global_and_oracle_streams_emit(client):
    """Endless streams: read just the first events through the ASGI app directly."""
    import asyncio
    from trop.api.mockstore import MockStore
    from trop.api import streams as ST

    async def first(seq, n):
        out = []
        async for x in ST.play(seq):
            out.append(x.event)
            if len(out) >= n:
                break
        return out
    s = MockStore()
    assert asyncio.run(first(s.events_sequence(), 3)) == ["incident.created", "incident.attributed", "campaign.updated"]
    assert asyncio.run(first(s.oracle_sequence(), 2)) == ["oracle.match", "oracle.match"]
