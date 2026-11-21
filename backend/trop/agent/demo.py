"""Fictional velmoria.click demo run (docs/design/canvas/BRIEF.md universe; every value here is FICTIONAL).

The demo goes through the real loop, tools and event builder; only the LLM (a fixed script), the external sources
and the corpus are fakes. Numbers follow BRIEF.md + boards 9/10: crt.sh batch → 6 SAN domains; origin 198.51.100.23
AS64500; urlscan kit pivot → 14 domains; Ad Library 9 ads on 4 pages; 11 of 14 not on CERT PL; 3 certificates
tonight (plessuro 00:47, orvinta 01:12, morvanta 02:31); Oracle had flagged 2 (orvinta, morvanta); Sędzia asks about
kalvesto.live (same kit, other cert/hosting, fits KMP-034) and the analyst skips it; 10 new domains → KMP-017 19 → 29.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from trop.schema import Investigation

from .case import Case
from .loop import Control, run
from .tools import Ctx

NOW = datetime(2026, 11, 21, 8, 50, tzinfo=UTC)
SEED = "velmoria.click"
CAMPAIGN = "KMP-017"
# KMP-017 has 19 domains; these are the ones the investigation touches
IN_CAMPAIGN = ["velmoria.click", "trastino.live", "quorvex.click", "ambrelio.live", "dunvarra.click", "selqueno.live",
               "morvanta.click"]
NEW_SAN = ["orvinta.click", "plessuro.live"]
NEW_KIT = ["tranvello.click", "kelmora.click", "dravento.live", "vastrino.live", "sulvane.click", "morquel.live",
           "pentaro.click", "ombrela.click"]
DECIDE = "kalvesto.live"
CERTPL_LISTED = {"velmoria.click", "trastino.live", "quorvex.click", "dunvarra.click"}
KIT_HASH = hashlib.sha256(b"fictional KMP-017 relay/lead kit bundle").hexdigest()   # fictional
CAPI = "cg-7f3a91e0.ecs.eu-west-1.on.aws"
TENANT = "relay-v1/lead"


class FakeDB:
    def db_search(self, q: str, limit: int = 15) -> dict:
        q = q.lower()
        if q == SEED:
            return {"query": q, "kind": "domain", "domain": SEED, "known": True, "campaigns": [CAMPAIGN],
                    "incidents": [{"id": "INC-24690", "domain": SEED, "title": "PILNE: Jan Kowalski przerywa milczenie…",
                                   "observed_at": "2026-11-12T21:04:00"},
                                  {"id": "INC-24702", "domain": SEED, "title": "«Wiem, kto to zrobił»: atak na Annę Nowak",
                                   "observed_at": "2026-11-14T19:40:00"}],
                    "traces": [{"type": "capi_gateway", "value": CAPI, "level": "operator", "df": 47, "n_domains": 6,
                                "domains": [d for d in IN_CAMPAIGN if d != SEED]},
                               {"type": "kit_endpoint", "value": "/api/v2/relay/lead/{uuid}/", "level": "platform", "df": 58,
                                "n_domains": 0, "domains": []}]}
        return {"query": q, "kind": "value", "matches": []}

    def incident_neighborhood(self, incident_id, depth: int = 1, max_df: int = 50) -> dict:
        return {"incident_id": str(incident_id), "neighbours": 46, "groups": []}

    def known_domains(self, ds: list[str]) -> set[str]:
        return {d for d in ds if d in IN_CAMPAIGN}

    def campaigns_for_domain(self, d: str) -> list[str]:
        return [CAMPAIGN] if d in IN_CAMPAIGN else (["KMP-034"] if d == DECIDE else [])

    def campaign_domains(self, cid: str | None) -> set[str]:
        return set(IN_CAMPAIGN) if cid == CAMPAIGN else set()

    def observable_df(self, value: str) -> dict | None:
        return {"type": "asset_sha256", "df": 14, "noise": False, "noise_reason": None} if value == KIT_HASH else None

    def oracle_flags(self, ds: list[str]) -> dict:
        f = {"orvinta.click": "2026-11-20T03:10:00", "morvanta.click": "2026-11-19T02:55:00"}
        return {d: {"score": 0.93 if d.startswith("orv") else 0.9, "seen_at": f[d], "source": "ct_stream", "status": "new"}
                for d in ds if d in f}


class FakeSources:
    def crtsh(self, domain: str, subdomains: bool = False) -> dict:
        tonight = {"plessuro.live": "2026-11-21T00:47:00", "orvinta.click": "2026-11-21T01:12:00",
                   "morvanta.click": "2026-11-21T02:31:00"}
        if domain == SEED:
            names = [SEED, "trastino.live", "morvanta.click", "quorvex.click", "ambrelio.live", *NEW_SAN]
            certs = [{"issuer": "C=US, O=Let's Encrypt, CN=R11", "not_before": "2026-11-09T01:31:00", "names": names[:5]},
                     {"issuer": "C=US, O=Let's Encrypt, CN=R11", "not_before": "2026-11-19T02:12:00", "names": names}]
            return {"domain": domain, "count": 2, "certs": certs, "first_not_before": certs[0]["not_before"],
                    "issuers": ["C=US, O=Let's Encrypt, CN=R11"]}
        if domain in tonight:
            c = {"issuer": "C=US, O=Let's Encrypt, CN=R11", "not_before": tonight[domain], "names": [domain]}
            return {"domain": domain, "count": 1, "certs": [c], "first_not_before": c["not_before"], "issuers": [c["issuer"]]}
        return {"domain": domain, "count": 0, "certs": []}

    def rdap(self, domain: str) -> dict:
        return {"domain": domain, "status": "ok", "registrar": "R-114 (anonimizowany)", "created": "2026-11-08T23:58:00Z",
                "ns": ["ada.ns.cloudflare.com", "rob.ns.cloudflare.com"]}

    def dns_ns(self, domain: str) -> dict:
        return {"domain": domain, "ns": ["ada.ns.cloudflare.com", "rob.ns.cloudflare.com"], "a": ["198.51.100.23"],
                "asn": {"198.51.100.23": {"asn": "AS64500", "org": "origin (za Cloudflare)"}}, "nxdomain": False}

    def urlscan_search(self, query: str, size: int = 100) -> dict:
        if KIT_HASH not in query:
            return {"query": query, "total": 0, "results": []}
        doms = NEW_SAN + NEW_KIT + [DECIDE, "trastino.live", "quorvex.click", "dunvarra.click"]
        res = [{"domain": d, "apex": d, "time": (NOW - timedelta(hours=3 + i * 7)).isoformat(), "title": "Kurier Dnia — PILNE",
                "ip": "198.51.100.23" if d != DECIDE else "203.0.113.77", "asn": "AS64500" if d != DECIDE else "AS64507",
                "domain_age_days": 3 + i} for i, d in enumerate(doms)]
        return {"query": query, "total": len(res), "results": res}

    def certpl_check(self, domain: str) -> dict:
        return {"domain": domain, "listed": domain in CERTPL_LISTED}

    def wayback(self, url: str, limit: int = 10) -> dict:
        return {"query": url, "count": 0, "snapshots": [], "first": None, "urls": []}

    def adlib_search(self, terms: str, countries: str = "PL", limit: int = 25, active: str = "ACTIVE", page_ids=None) -> dict:
        rows = []
        plan = [("Puzzle Mania PL", "tranvello.click", 3), ("Ogród i Pasja 24", "kelmora.click", 2),
                ("Domowe Okazje 365", "orvinta.click", 2), ("Kwiaciarnia Pod Lipą", "morvanta.click", 2)]
        n = 0
        for page, dom, k in plan:
            for _ in range(k):
                n += 1
                rows.append({"id": f"99000000000{n:02d}", "page_id": f"61000000{len(rows):04d}", "page_name": page,
                             "caption": dom.upper(), "body": "PILNE: Jan Kowalski przerywa milczenie po napaści…",
                             "start": "2026-11-20"})
        return {"terms": terms, "count": len(rows), "ads": rows}

    def capture(self, url: str, **kw) -> dict:
        return {"ok": False, "url": url, "error": "demo: capture disabled"}


def _script(control: Control):
    why = {
        "db": "Zaczynam od tego, co już wiemy o tej domenie.",
        "crt": "Certyfikaty z tej samej nocnej partii zwykle należą do tego samego operatora.",
        "dns": "Szukam wspólnego hostingu za Cloudflare.",
        "us": "Plik kitu relay/lead to mocny ślad: szukam innych stron, które go ładują.",
        "pl": "Domeny spoza listy to kandydaci do zgłoszenia.",
        "ad": "Sprawdzam, czy nowe domeny są promowane reklamami.",
    }
    turns = [
        [("db_search", {"query": SEED, "why": why["db"]})],
        [("crtsh", {"domain": SEED, "why": why["crt"]}), ("dns_ns", {"domain": SEED, "why": why["dns"]})],
        [("urlscan_search", {"query": f"hash:{KIT_HASH}", "why": why["us"]})],
        [("adlib_search", {"terms": "PILNE Jan Kowalski", "active": "ACTIVE", "why": why["ad"]})],
        [("certpl_check", {"domains": NEW_SAN + NEW_KIT + [DECIDE, "trastino.live", "quorvex.click", "dunvarra.click"],
                           "why": why["pl"]})],
        [("crtsh", {"domain": d, "why": "Kiedy wydano certyfikat?"}) for d in ("plessuro.live", "orvinta.click", "morvanta.click")],
        [("oracle_lookup", {"domains": ["plessuro.live", "orvinta.click", "morvanta.click"],
                            "why": "Czy Oracle przewidział te domeny przed pierwszą reklamą?"})],
        [("propose_link", {"domains": [DECIDE], "confidence": "needs_decision",
                           "question": "kalvesto.live ma ten sam kit, ale inny certyfikat i hosting. Pasuje też do KMP-034. "
                                       "Dołączyć ją do tej kampanii?",
                           "rationale": "ten sam kit, inny certyfikat i hosting (AS64507), pasuje też do KMP-034",
                           "why": "Dowody są sprzeczne: decyzja należy do analityka."})],
        [("propose_link", {"domains": NEW_SAN + NEW_KIT, "confidence": "high",
                           "evidence": ["ten sam plik kitu relay/lead", "nocna partia certyfikatów LE R11", "origin AS64500"],
                           "rationale": "ten sam kit i hosting, certyfikaty z nocnych partii",
                           "why": "Ten sam kit, hosting i nocne partie certyfikatów."})],
        [("finish", {"conclusions": [
            {"text": "Znaleźliśmy 10 nowych domen i 9 reklam na 4 stronach; wszystkie mają ten sam kit relay/lead i origin AS64500 "
                     "co KMP-017.", "evidence_refs": ["n-us-kit", "n-ads"]},
            {"text": "Trzy domeny dostały certyfikat tej nocy (plessuro.live 00:47, orvinta.click 01:12, morvanta.click 02:31); "
                     "Oracle oznaczył wcześniej dwie z nich.", "evidence_refs": ["n-oracle"]},
            {"text": "11 z 14 domen z kitu nie ma na liście CERT PL; żadnej z nowych.", "evidence_refs": ["n-certpl"]},
        ], "why": "Podsumowanie śledztwa."})],
    ]
    it = iter(turns)

    def llm(messages, tools):
        try:
            calls = next(it)
        except StopIteration:
            return {"text": "", "tool_calls": []}
        if calls[0][0] == "propose_link" and calls[0][1]["confidence"] == "high":
            control.put({"type": "decision", "node_id": "d-" + DECIDE, "choice": "Pomiń"})   # the analyst clicks "Pomiń"
        return {"tool_calls": [{"name": n, "args": a} for n, a in calls], "cost_usd": 0.0071, "model": "gemini-pro-latest"}
    return llm


def build_demo(out: str | Path | None = None, investigation_id: str = "INV-DEMO") -> Investigation:
    """Run the scripted investigation and write the replay (t in seconds: ~6 s per step, ~0.25 s per event)."""
    inv = Investigation(id=investigation_id, seed=SEED, campaign_id=CAMPAIGN, model="gemini-pro-latest",
                        budget={"steps": 20, "used": 0, "usd": 0.5, "usd_used": 0.0},
                        tools=["db_search", "crtsh", "dns_ns", "rdap", "urlscan_search", "adlib_search", "certpl_check",
                               "oracle_lookup", "capture"],
                        started_at=NOW.isoformat(timespec="seconds"))
    clock = {"t": 0.0}
    case = Case(inv, None, None, None, at=lambda: (NOW + timedelta(seconds=clock["t"])).isoformat(timespec="milliseconds"))
    # timing: each agent.step opens a new beat
    orig = case.emit

    def timed(typ: str, data: dict) -> None:
        clock["t"] += 6.0 if typ == "agent.step" and case.inv.steps and len(case.inv.steps) > 1 else 0.25
        orig(typ, data)
    case.emit = timed  # type: ignore[method-assign]
    control = Control()
    ctx = Ctx(case=case, seed=SEED, campaign_id=CAMPAIGN, campaign_domains=set(IN_CAMPAIGN), ext=FakeSources(),
              dbm=FakeDB(), captures_left=0, now=lambda: NOW)
    run(ctx, llm=_script(control), steps=20, usd_cap=0.5, control=control, planner="llm")
    # stable ids for the conclusion refs
    for c in inv.conclusions:
        c["evidence_refs"] = [next((n.id for n in inv.nodes if n.kind == "query_result" and n.branch == "urlscan"), r)
                              if r == "n-us-kit" else next((n.id for n in inv.nodes if n.kind == "ad"), r) if r == "n-ads" else r
                              for r in c["evidence_refs"]]
    if out:
        p = Path(out)
        p.parent.mkdir(parents=True, exist_ok=True)
        t0 = None
        with p.open("w", encoding="utf-8") as f:
            for ev in case.events:
                t = (datetime.fromisoformat(ev.at) - NOW).total_seconds()
                t0 = t if t0 is None else t0
                f.write(json.dumps({"t": round(t - t0, 2), "type": ev.type, "event": ev.model_dump()}, ensure_ascii=False) + "\n")
    return inv
