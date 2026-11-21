"""White Rabbit loop logic with a fake LLM and fake sources (fictional BRIEF universe only)."""
from __future__ import annotations

import json

import pytest

from trop.agent import service
from trop.agent.case import Case
from trop.agent.demo import CAMPAIGN, DECIDE, IN_CAMPAIGN, NEW_KIT, NEW_SAN, NOW, SEED, FakeDB, FakeSources, build_demo
from trop.agent.loop import Control, build_messages, run
from trop.agent.tools import Ctx, specs
from trop.config import settings
from trop.schema import Event, Investigation, InvestigationNode, InvestigationStep


@pytest.fixture(autouse=True)
def _tmp_data(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)


def _ctx(events: list | None = None) -> Ctx:
    inv = Investigation(id="INV-T", seed=SEED, campaign_id=CAMPAIGN, started_at=NOW.isoformat())
    emit = (lambda t, d: events.append((t, d))) if events is not None else None
    return Ctx(case=Case(inv, emit), seed=SEED, campaign_id=CAMPAIGN, campaign_domains=set(IN_CAMPAIGN), ext=FakeSources(),
               dbm=FakeDB(), captures_left=0, now=lambda: NOW)


def scripted(*turns, cost=0.01):
    it = iter(turns)
    seen = []

    def llm(messages, tools):
        seen.append((messages, tools))
        try:
            return {"tool_calls": [{"name": n, "args": a} for n, a in next(it)], "cost_usd": cost}
        except StopIteration:
            return {"text": "done", "tool_calls": []}
    llm.seen = seen
    return llm


def test_tool_calls_grow_graph_and_emit_contract_events():
    ev: list = []
    ctx = _ctx(ev)
    llm = scripted([("db_search", {"query": SEED, "why": "start"})],
                   [("urlscan_search", {"query": "hash:" + "a" * 64})],
                   [("finish", {"conclusions": [{"text": "koniec", "evidence_refs": ["n-x"]}]})])
    s = run(ctx, llm=llm, steps=10, planner="llm")
    types = [t for t, _ in ev]
    assert types[0] == "graph.node_added"            # the seed
    assert {"agent.step", "graph.node_added", "graph.edge_added", "casefile.delta", "investigation.done"} <= set(types)
    assert types[-1] == "investigation.done"
    for t, d in ev:                                   # every payload fits the contract shapes
        assert d["investigation_id"] == "INV-T"
        Event(type=t, at=NOW.isoformat(), data=d)
        if t == "graph.node_added":
            n = InvestigationNode.model_validate(d["node"])
            assert n.branch in ("crtsh", "urlscan", "adlib", "certpl", "db", "content")
            assert n.status in (None, "new", "in_campaign", "to_decide", "in_progress", "skipped")
        if t == "agent.step":
            InvestigationStep.model_validate(d["step"])
        if t == "graph.edge_added":
            assert set(d["edge"]) == {"a", "b", "label"}
    doms = {n.label: n for n in ctx.case.domains()}
    assert doms["trastino.live"].status == "in_campaign" and doms["trastino.live"].meta["level"] == "operator"
    # the fake urlscan only answers the real kit hash -> nothing found for "a"*64
    assert s["steps"] == 3 and ctx.case.inv.conclusions[0]["text"] == "koniec"
    assert ctx.case.inv.budget["usd_used"] == pytest.approx(0.03)


def test_step_budget_is_a_hard_stop_and_seed_never_listed_as_candidate():
    ctx = _ctx()
    many = [[("crtsh", {"domain": SEED}), ("dns_ns", {"domain": SEED}), ("rdap", {"domain": SEED})]] * 10
    s = run(ctx, llm=scripted(*many), steps=4, planner="llm")
    assert s["steps"] == 4 and len(ctx.case.inv.steps) == 4
    assert SEED not in s["candidates"]


def test_prompt_is_compact_and_lists_tools():
    ctx = _ctx()
    llm = scripted([("db_search", {"query": SEED})], [("finish", {"conclusions": []})])
    run(ctx, llm=llm, steps=5, planner="llm")
    msgs, tools = llm.seen[-1]
    assert msgs[0]["role"] == "system" and "operator" in msgs[0]["content"]
    assert "#1 db_search" in msgs[1]["content"] and len(msgs[1]["content"]) < 20000
    assert {t["name"] for t in tools} >= {"db_search", "urlscan_search", "crtsh", "propose_link", "finish"}
    assert all(t["parameters"]["type"] == "object" for t in specs())


def test_decision_card_and_analyst_skip():
    ev: list = []
    ctx = _ctx(ev)
    control = Control()
    kit = __import__("trop.agent.demo", fromlist=["KIT_HASH"]).KIT_HASH

    def llm_factory():
        turns = iter([
            [("urlscan_search", {"query": f"hash:{kit}"})],
            [("propose_link", {"domains": [DECIDE], "confidence": "needs_decision", "question": "Dołączyć?"})],
            [("propose_link", {"domains": NEW_SAN + NEW_KIT, "confidence": "high"})],
            [("finish", {"conclusions": []})],
        ])

        def llm(m, t):
            nxt = next(turns)
            if nxt[0][1].get("confidence") == "high":
                control.put({"type": "decision", "choice": "Pomiń"})
            return {"tool_calls": [{"name": n, "args": a} for n, a in nxt]}
        return llm
    s = run(ctx, llm=llm_factory(), steps=10, control=control, planner="llm")
    dec = [d for t, d in ev if t == "investigation.decision"]
    assert dec and dec[0]["node_id"] == "d-" + DECIDE and dec[0]["options"] == ["Dołącz", "Pomiń"]
    # card comes right after its agent.step
    i = [t for t, _ in ev].index("investigation.decision")
    assert [t for t, _ in ev][:i][::-1].index("agent.step") < 4
    assert ctx.case.nodes["d-" + DECIDE].status == "skipped"
    assert ctx.case.inv.pending_decision is None
    assert s["new_domains"] == 10 and s["skipped"] == 1


def test_stop_control_ends_the_run():
    ctx = _ctx()
    control = Control()

    def llm(m, t):
        control.put({"type": "stop"})
        return {"tool_calls": [{"name": "db_search", "args": {"query": SEED}}]}
    run(ctx, llm=llm, steps=20, control=control, planner="llm")
    assert ctx.case.inv.status == "stopped" and len(ctx.case.inv.steps) == 1


def test_missing_llm_falls_back_to_heuristic_plan():
    ctx = _ctx()
    s = run(ctx, llm=lambda m, t: {"missing": True, "error": "offline"}, steps=20, planner="auto")
    tools = [st.tool for st in ctx.case.inv.steps]
    assert tools[0] == "db_search" and tools[-1] == "finish" and "certpl_check" in tools
    assert s["domains_found"] >= 6 and ctx.case.inv.conclusions


def test_usd_cap_switches_to_heuristic():
    ctx = _ctx()
    llm = scripted(*([[("rdap", {"domain": SEED})]] * 20), cost=0.6)
    run(ctx, llm=llm, steps=20, usd_cap=1.0, planner="auto")
    assert len(llm.seen) == 2           # 0.6 + 0.6 >= 1.0 -> no more model calls
    assert ctx.case.inv.steps[-1].tool == "finish"


def test_failing_tool_does_not_kill_the_run():
    class Boom(FakeSources):
        def crtsh(self, domain, subdomains=False):
            raise TimeoutError("crt.sh down")
    ctx = _ctx()
    ctx.ext = Boom()
    run(ctx, llm=scripted([("crtsh", {"domain": SEED})], [("finish", {"conclusions": []})]), steps=5, planner="llm")
    assert "błąd" in ctx.case.inv.steps[0].result_summary and ctx.case.inv.status == "done"


def test_service_run_persist_steer_promote(tmp_path):
    llm = scripted([("db_search", {"query": SEED})], [("crtsh", {"domain": SEED})], [("finish", {"conclusions": []})])
    inv = service.run_investigation({"seed": SEED, "campaign_id": CAMPAIGN, "budget_steps": 10}, None, llm=llm,
                                    ext=FakeSources(), dbm=FakeDB())
    iid = inv["id"]
    assert iid.startswith("INV-") and inv["status"] == "done"
    got = service.get_investigation(iid)
    assert got.steps and service.list_investigations("done")[0].id == iid
    evs = service.events(iid)
    assert evs[0]["type"] == "graph.node_added" and evs[-1]["type"] == "investigation.done"
    assert service.steer(iid, message="skup się na certyfikatach")["ok"]
    new = [n.id for n in got.nodes if n.kind == "domain" and n.status == "new"]
    assert new, "SAN batch should give new domains"
    r = service.promote(iid, CAMPAIGN, new + ["d-" + SEED, "d-nonexistent.click"])
    assert r == {"campaign_id": CAMPAIGN, "added": len(new)}
    rows = [json.loads(x) for x in (tmp_path / "investigations" / "promotions.jsonl").read_text().splitlines()]
    assert {x["label"] for x in rows} == {n[2:] for n in new}
    assert service.promote(iid, CAMPAIGN, new)["added"] == 0     # already in the campaign now


def test_cross_process_control_file(tmp_path):
    iid = service.new_investigation_id()
    c = Control(service._dir(iid) / "control.jsonl")
    service.steer(iid, node_id="d-x.click", choice="Dołącz")
    service.stop(iid, resume=True)
    cmds = c.poll()
    assert [x["type"] for x in cmds] == ["decision", "pause"] and c.poll() == []


def test_demo_replay_matches_brief(tmp_path):
    out = tmp_path / "demo.jsonl"
    inv = build_demo(out)
    rows = [json.loads(x) for x in out.read_text().splitlines()]
    assert rows[0]["t"] == 0 and rows[-1]["type"] == "investigation.done" and 60 < rows[-1]["t"] < 150
    assert all(rows[i]["t"] <= rows[i + 1]["t"] for i in range(len(rows) - 1))
    s = rows[-1]["event"]["data"]["summary"]
    assert (s["new_domains"], s["ads"], s["advertisers"], s["certs_tonight"], s["skipped"]) == (10, 9, 4, 3, 1)
    assert any("11 z 14" in r["event"]["data"]["step"]["result_summary"] for r in rows if r["type"] == "agent.step")
    assert len(inv.steps) <= 20 and inv.status == "done"


def test_build_messages_mentions_pending_decision():
    ctx = _ctx()
    ctx.case.decision("d-x", "Q?", ["Dołącz", "Pomiń"])
    m = build_messages(ctx, [], ["focus on certs"], 5, 0.5)
    assert "Pending analyst decision" in m[1]["content"] and "focus on certs" in m[1]["content"]


def test_unused_hash_pivots_are_suggested_to_the_model():
    from trop.agent.loop import suggested_pivots
    h = [{"tool": "db_search", "args": {"query": SEED}, "view": {"traces": [
        {"type": "asset_sha256", "value": "b" * 64, "level": "platform"},
        {"type": "asset_sha256", "value": "a" * 64, "level": "campaign"}]}}]
    assert suggested_pivots(h) == ["hash:" + "a" * 64, "hash:" + "b" * 64]
    h.append({"tool": "urlscan_search", "args": {"query": "hash:" + "a" * 64}, "view": {}})
    assert suggested_pivots(h) == ["hash:" + "b" * 64]
