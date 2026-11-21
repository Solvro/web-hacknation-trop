"""Second half of the fictional universe: campaign sub-resources, operators, graph, investigation, oracle, act, triage,
hunter, lab, persons. See universe.py."""
from __future__ import annotations

import random
from typing import Any

from trop.api.mock import universe as U
from trop.api.mock.universe import CAPI, KIT, SPEC, ev
from trop.schema import (
    ActPackage, DomainDNA, DomainIndicator, EvidenceItem, GraphEdge, GraphNode, GraphPayload, HunterRun, HunterSource,
    Indicators, Investigation, InvestigationNode, InvestigationStep, MergePreview, Operation, Operator, OracleMetrics,
    OraclePrediction, Rule, RuleTest, TimelineEvent, Timeline, TriageCandidate, TriageItem, Variant,
)

# ------------------------------------------------------------------------------------------- campaign sub-resources
def timeline(cid: str) -> Timeline:
    c = U.campaigns()
    camp = next(x for x in c if x.id == cid)
    series = camp.heat.series_14d
    days = [{"date": d, "incidents": series[i]} for i, d in enumerate(U.DAY)]
    events: list[TimelineEvent] = []
    if cid == "KMP-017":
        for fqdn, cert, _, _, _, pred in U.KMP017_DOMAINS:
            events.append(TimelineEvent(at=cert, kind="cert_batch" if cert.startswith("2026-11-21") else "domain_registered", ref=fqdn))
            if pred:
                events.append(TimelineEvent(at=pred, kind="oracle_predicted", ref=fqdn))
        events.append(TimelineEvent(at="2026-11-21T02:31:00Z", kind="hunter_capture", ref="INC-24817"))
    elif cid == "KMP-022":
        events.append(TimelineEvent(at="2026-11-12T10:00:00Z", kind="act_sent", ref="ACT-3"))
    events.sort(key=lambda e: e.at)
    return Timeline(days=days, events=events)


def indicators(cid: str) -> Indicators:
    if cid == "KMP-017":
        doms = [DomainIndicator(fqdn=f, cert_issued_at=cert, registered_at=cert[:10] + "T00:00:00Z", oracle_predicted_at=pred, on_certpl=pl,
                                online=on, ads_seen=ads) for f, cert, pl, on, ads, pred in U.KMP017_DOMAINS]
        return Indicators(
            domains=doms, tracking=[U.E_CAPI], kit=[U.E_KIT],
            persons=[{"id": "P-01", "name": "Jan Kowalski", "count": 28}, {"id": "P-02", "name": "Anna Nowak", "count": 11},
                     {"id": "P-03", "name": "Tomasz Lewandowski", "count": 7}],
            advertisers=[{"name": n, "page_id": p, "removed": r} for n, p, r in U.ADVERTISERS_017])
    doms = [DomainIndicator(fqdn=f, ads_seen=2, online=True, cert_issued_at="2026-11-1%dT01:00:00Z" % (i % 9)) for i, f in enumerate(U._DOMS[cid])]
    rows = U.dna_rows(cid)
    return Indicators(domains=doms, tracking=[ev(r.layer, r.field, r.value, r.display or r.value, r.strength, 2.0, max(6, r.members_with), r.bot) for r in rows if r.layer == "tracking"],
                      kit=[ev(r.layer, r.field, r.value, r.display or r.value, r.strength, 2.0, max(6, r.members_with), r.bot) for r in rows if r.layer == "kit"],
                      persons=[{"id": "P-%02d" % (i + 1), "name": p, "count": 5 + i} for i, p in enumerate(SPEC[cid]["persons"])],
                      advertisers=[{"name": "Sklep Mock %d" % i, "page_id": "10420011334%04d" % i, "removed": i < SPEC[cid]["advrm"]} for i in range(SPEC[cid]["adv"])])


def variants(cid: str) -> list[Variant]:
    mem = U.members(cid)
    if cid in U.VARIANTS:
        return [Variant(id=v, campaign_id=cid, label=f"{v} — {t}", members=[m.incident_id for m in mem if m.variant_id == v], template=t) for v, _, t in U.VARIANTS[cid]]
    return [Variant(id="V1", campaign_id=cid, label="V1 — wariant główny", members=[m.incident_id for m in mem], template=None)]


def phylogeny(cid: str) -> dict:
    vs = variants(cid)
    nodes = [{"id": cid, "kind": "campaign", "label": cid}] + [{"id": v.id, "kind": "variant", "label": v.label, "n": len(v.members)} for v in vs]
    return {"campaign_id": cid, "nodes": nodes, "edges": [{"a": cid, "b": v.id} for v in vs]}


def summary_text(cid: str) -> dict:
    s = SPEC[cid]
    return {"campaign_id": cid, "text": f"{s['name']}: {s['narrative']} {s['n']} incydentów, {s['dom']} domen, {s['adv']} reklamodawców.",
            "bullets": [f"{s['n']} incydentów w korpusie (N = {U.N})", f"{s['dom']} domen, {s['advrm']} reklamodawców usuniętych", f"Operator: {s['op'] or 'nieustalony'}"],
            "generated_by": "mock"}


# ------------------------------------------------------------------------------------------- operators / operations
def operators() -> list[Operator]:
    shared03 = [U.E_CAPI, U.E_KIT, U.E_CERT, ev("infra", "asn", "AS64500", "origin AS64500", "M", 1.2, 60, "notariusz")]
    camps = lambda op: [{"id": c["id"], "name": c["name"], "incidents": c["n"]} for c in U.CAMP_SPEC if c["op"] == op]
    spec = [("OP-01", "Marten", [ev("kit", "kit_tenant", "kit-tenant-b07", "kit tenant b07", "H", 2.4, 22, "tropiciel")], ["Pożyczki i kredyty z fałszywymi bankami."], None),
            ("OP-03", "Kestrel", shared03, ["Fałszywe portale newsowe → inwestycje", "Deepfake lekarza → suplementy"], "OPN-01"),
            ("OP-04", "Lynx", [ev("kit", "kit_tenant", "kit-tenant-d19", "kit tenant d19", "H", 2.2, 17, "tropiciel")], ["Bony i dopłaty rządowe z ankietą."], None),
            ("OP-05", "Heron", [ev("tracking", "google_ads", "AW-11122233344", "Google Ads AW-1112…", "H", 3.0, 50, "tropiciel")], ["Platformy AI z udziałem celebrytów."], None),
            ("OP-07", "Orchid", [ev("tracking", "fb_pixel", "870011223344556", "FB pixel 8700…556", "H", 3.0, 29, "tropiciel")], ["Fałszywy lekarz i syntetyczny głos."], "OPN-02"),
            ("OP-09", "Sable", [ev("infra", "asn", "AS64507", "origin AS64507", "M", 1.3, 14, "notariusz")], ["Boty handlowe krypto."], None)]
    return [Operator(id=i, codename=cn, campaigns=camps(i), shared=sh, narratives=nr, operation_id=opn) for i, cn, sh, nr, opn in spec]


def operations() -> list[Operation]:
    return [Operation(id="OPN-01", name="Lejek relay: portal → inwestycja / suplement", campaigns=["KMP-017", "KMP-034", "KMP-043"], operators=["OP-03"],
                      funnel=["pre-lander A (klon portalu)", "lander C (relay/lead)", "kit K (relay v1/v2)"], shared=[U.E_CAPI, U.E_KIT]),
            Operation(id="OPN-02", name="Lejek Keitaro: lekarz → sklep", campaigns=["KMP-022"], operators=["OP-07"],
                      funnel=["pre-lander A (wywiad z lekarzem)", "lander C (artovita-forte.shop)"], shared=[ev("tracking", "fb_pixel", "870011223344556", "FB pixel 8700…556", "H", 3.0, 29, "tropiciel")])]


def merge_preview() -> MergePreview:
    camps = {c.id: c for c in U.campaigns()}
    a, b = camps["KMP-017"], camps["KMP-043"]
    return MergePreview(a=a, b=b, shared=[U.E_CAPI, U.E_KIT], before={"KMP-017": 46, "KMP-043": 4}, after={"KMP-017": 50}, undo_token="UNDO-0001")


# ------------------------------------------------------------------------------------------- graph
def graph() -> GraphPayload:
    nodes: list[GraphNode] = [GraphNode(id="OP-03", kind="operator", label="OP-03 «Kestrel»", size=4),
                              GraphNode(id="OPN-01", kind="operation", label="OPN-01 lejek relay", size=3)]
    edges: list[GraphEdge] = [GraphEdge(a="OPN-01", b="OP-03", type="operation", weight=2)]
    hulls: list[dict[str, Any]] = [{"id": "OP-03", "kind": "operator", "members": ["KMP-017", "KMP-034", "KMP-043"], "label": "OP-03 «Kestrel»"}]
    for cid in ("KMP-017", "KMP-034", "KMP-043", "KMP-022", "KMP-031"):
        c = SPEC[cid]
        nodes.append(GraphNode(id=cid, kind="campaign", label=f"{cid} {c['name'].split('—')[0].strip()}", campaign_id=cid, size=2 + c["n"] / 20, first_seen=c["first"]))
        if c["op"]:
            edges.append(GraphEdge(a=cid, b=c["op"], type="operator", weight=3, level="L3"))
            if c["op"] != "OP-03":
                nodes.append(GraphNode(id=c["op"], kind="operator", label=c["op"], size=3))
    for f, cert, pl, on, ads, pred in U.KMP017_DOMAINS:
        nodes.append(GraphNode(id=f, kind="domain", label=f, campaign_id="KMP-017", size=1 + ads / 3, first_seen=cert[:10], meta={"certpl": pl}))
        edges.append(GraphEdge(a=f, b="KMP-017", type="member", weight=1, level="L2"))
    for f in U._DOMS["KMP-034"]:
        nodes.append(GraphNode(id=f, kind="domain", label=f, campaign_id="KMP-034", size=1))
        edges.append(GraphEdge(a=f, b="KMP-034", type="member", weight=1, level="L2"))
    for p in ("Jan Kowalski", "Anna Nowak", "Tomasz Lewandowski"):
        nodes.append(GraphNode(id=f"person:{p}", kind="person", label=p, size=1.5))
        edges.append(GraphEdge(a=f"person:{p}", b="KMP-017", type="persons", weight=1.5, level="L2"))
    nodes += [GraphNode(id="trace:capi", kind="trace", label="CAPI cg-7f3a…", size=2.5), GraphNode(id="trace:kit", kind="trace", label="relay/lead kit", size=2.5),
              GraphNode(id="cert:le-r11-night", kind="cert", label="LE R11 00:47–02:31", size=2),
              GraphNode(id="INC-24817", kind="incident", label="INC-24817", campaign_id="KMP-017", size=1.5, first_seen="2026-11-21")]
    for cid in ("KMP-017", "KMP-034"):
        edges.append(GraphEdge(a="trace:capi", b=cid, type="tracking", weight=3.1, level="L3", label="wspólna bramka CAPI"))
        edges.append(GraphEdge(a="trace:kit", b=cid, type="kit", weight=2.7, level="L3", label="wspólny relay kit"))
    for f in ("morvanta.click", "orvinta.click", "plessuro.live"):
        edges.append(GraphEdge(a="cert:le-r11-night", b=f, type="infra", weight=1.4, level="L2"))
    edges.append(GraphEdge(a="INC-24817", b="morvanta.click", type="member", weight=1, level="L2"))
    edges.append(GraphEdge(a="INC-24817", b="KMP-017", type="member", weight=1, level="L2"))
    hulls.append({"id": "KMP-017", "kind": "campaign", "members": [d[0] for d in U.KMP017_DOMAINS] + ["INC-24817"], "label": "KMP-017 «Zamach»"})
    return GraphPayload(nodes=nodes, edges=edges, hulls=hulls)


# ------------------------------------------------------------------------------------------- investigation (White Rabbit)
def investigation() -> Investigation:
    N_ = InvestigationNode
    nodes = [N_(id="n-seed", kind="domain", label="velmoria.click", status="in_campaign", branch="db", meta={"on_certpl": True})]
    san = ["velmoria.click", "trastino.live", "quorvex.click", "ambrelio.live", "dunvarra.click", "selqueno.live"]
    nodes.append(N_(id="n-cert", kind="cert", label="crt.sh: partia certyfikatów (6 SAN)", branch="crtsh", meta={"san": 6}))
    nodes.append(N_(id="n-ip", kind="ip", label="198.51.100.23 · AS64500 (origin)", branch="content", meta={"asn": "AS64500"}))
    nodes.append(N_(id="n-urlscan", kind="query_result", label="urlscan: ścieżka kitu → 14 domen", branch="urlscan", meta={"domains": 14}))
    others = [d[0] for d in U.KMP017_DOMAINS if d[0] not in san and d[0] not in ("plessuro.live", "orvinta.click", "morvanta.click", "ormalto.click", "brenvilo.live")]
    for d in others[:8]:
        nodes.append(N_(id=f"d-{d}", kind="domain", label=d, status="to_decide", is_new=True, branch="urlscan"))
    for d in san[1:]:
        nodes.append(N_(id=f"d-{d}", kind="domain", label=d, status="in_campaign", branch="crtsh"))
    nodes.append(N_(id="n-ads", kind="ad", label="Ad Library: 9 aktywnych reklam, 4 strony reklamodawców", branch="adlib", meta={"ads": 9, "pages": 4}))
    nodes.append(N_(id="n-certpl", kind="list_status", label="CERT PL: 11 z 14 poza listą", branch="certpl", meta={"not_listed": 11, "total": 14}))
    for d, t in (("plessuro.live", "00:47"), ("orvinta.click", "01:12"), ("morvanta.click", "02:31")):
        nodes.append(N_(id=f"d-{d}", kind="cert", label=f"{d} · cert {t} UTC", status="to_decide", is_new=True, branch="crtsh", meta={"issued": t}))
    nodes.append(N_(id="n-oracle", kind="oracle_flag", label="Oracle: wcześniej oznaczył orvinta, morvanta", branch="db", meta={"flagged": 2}))
    edges = [{"a": "n-seed", "b": "n-cert", "label": "crt.sh"}, {"a": "n-cert", "b": "d-trastino.live", "label": "SAN"}, {"a": "n-seed", "b": "n-ip", "label": "DNS/RDAP"},
             {"a": "n-seed", "b": "n-urlscan", "label": "kit path"}, {"a": "n-urlscan", "b": "n-ads", "label": "reklamy"}, {"a": "n-urlscan", "b": "n-certpl", "label": "lista CERT PL"},
             {"a": "n-certpl", "b": "d-plessuro.live", "label": "3 certy tej nocy"}, {"a": "d-morvanta.click", "b": "n-oracle", "label": "Oracle"}]
    t0 = "2026-11-21T08:00:00+01:00"

    def S(n, tool, q, res, why, prod, sec, bot, usd=0.0):
        return InvestigationStep(n=n, tool=tool, query=q, result_summary=res, why=why, produced=prod, at=t0[:14] + "%02d:%02d+01:00" % (sec // 60, sec % 60), bot=bot, cost_usd=usd)

    steps = [
        S(1, "db.lookup", "velmoria.click", "Domena w KMP-017, na liście CERT PL.", "Zaczynam od tego, co już wiemy.", ["n-seed"], 0, "archiwista"),
        S(2, "crtsh.search", "velmoria.click", "Partia certyfikatów: 6 domen SAN.", "Certyfikaty z tej samej partii zwykle należą do tego samego operatora.", ["n-cert"] + [f"d-{d}" for d in san[1:]], 6, "notariusz", 0.0),
        S(3, "dns.rdap", "velmoria.click", "Origin 198.51.100.23, AS64500; RDAP bez rejestratora (anonimizowany).", "Szukam wspólnego hostingu.", ["n-ip"], 12, "notariusz"),
        S(4, "urlscan.search", "page.url:\"/api/v2/relay/lead/\"", "14 domen z tą samą ścieżką kitu.", "Ścieżka relay/lead jest dowodem kitu (H).", ["n-urlscan"] + [f"d-{d}" for d in others[:8]], 19, "tropiciel", 0.0),
        S(5, "adlibrary.search", "strony 14 domen", "9 aktywnych reklam, 4 strony reklamodawców.", "Sprawdzam, czy domeny są aktywnie promowane.", ["n-ads"], 27, "zwiadowca"),
        S(6, "certpl.check", "14 domen", "11 z 14 nie ma na liście CERT PL.", "Domeny poza listą to kandydaci do zgłoszenia.", ["n-certpl"], 33, "archiwista"),
        S(7, "crtsh.search", "certy z ostatnich 6 h (LE R11)", "3 certyfikaty tej nocy: plessuro.live 00:47, orvinta.click 01:12, morvanta.click 02:31.", "Nocne partie LE R11 to podpis KMP-017.", [f"d-{d}" for d in ("plessuro.live", "orvinta.click", "morvanta.click")], 41, "notariusz"),
        S(8, "oracle.lookup", "3 domeny", "Oracle wcześniej oznaczył 2 z 3 (orvinta 20.11, morvanta 19.11).", "Weryfikuję, czy Oracle przewidział te domeny.", ["n-oracle"], 48, "archiwista"),
        S(9, "engine.compare", "14 domen vs KMP-017", "Wszystkie 14 pasuje do DNA KMP-017 (p ≥ 0.8).", "Porównanie z DNA kampanii.", [], 54, "sedzia"),
    ]
    return Investigation(
        id="INV-3", seed="velmoria.click", campaign_id="KMP-017", status="done", budget={"steps": 20, "used": 9, "usd": 0.5, "usd_used": 0.07},
        model="gemini-pro-latest", tools=["db.lookup", "crtsh.search", "dns.rdap", "urlscan.search", "adlibrary.search", "certpl.check", "oracle.lookup", "engine.compare"],
        started_at=t0, nodes=nodes, edges=edges, steps=steps,
        conclusions=[{"text": "velmoria.click należy do KMP-017 (operator OP-03 «Kestrel»); partia certyfikatów ujawnia 6 domen, kit — 14.", "evidence_refs": ["n-cert", "n-urlscan"]},
                     {"text": "11 z 14 domen nie ma na liście CERT PL — pakiet zgłoszeniowy do przygotowania.", "evidence_refs": ["n-certpl"]},
                     {"text": "Tej nocy wydano 3 certyfikaty; Oracle wcześniej oznaczył 2 z nich (orvinta, morvanta).", "evidence_refs": ["n-oracle"]}],
        pending_decision={"node_id": "n-certpl", "question": "Dodać 14 domen do KMP-017 i przygotować zgłoszenie CERT PL?",
                          "options": ["Dodaj 14 domen do KMP-017", "Dodaj tylko 11 spoza listy", "Pomiń"]})


def investigation_old() -> Investigation:
    return Investigation(id="INV-2", seed="artovita-forte.shop", campaign_id="KMP-022", status="done", budget={"steps": 20, "used": 7, "usd": 0.5, "usd_used": 0.05},
                         started_at="2026-11-20T15:10:00+01:00", tools=["db.lookup", "urlscan.search"],
                         nodes=[InvestigationNode(id="n1", kind="domain", label="artovita-forte.shop", status="in_campaign")], edges=[],
                         steps=[InvestigationStep(n=1, tool="db.lookup", query="artovita-forte.shop", result_summary="W KMP-022.", at="2026-11-20T15:10:05+01:00")],
                         conclusions=[{"text": "Domena należy do KMP-022 (OP-07 «Orchid»).", "evidence_refs": ["n1"]}])


# ------------------------------------------------------------------------------------------- oracle
def oracle_predictions() -> list[OraclePrediction]:
    P = OraclePrediction
    return [
        P(domain="morvanta.click", issued_at="2026-11-19T19:28:00Z", issuer="R11", dna_score=0.91, campaign_id="KMP-017", status="confirmed", first_ad_at="2026-11-21T02:31:00Z", lead_time_h=31.1, reasons=["gramatyka CVCCVCV", "tld .click", "partia LE R11 w oknie nocnym", "ASN AS64500"]),
        P(domain="orvinta.click", issued_at="2026-11-20T21:40:00Z", issuer="R11", dna_score=0.93, campaign_id="KMP-017", status="confirmed", first_ad_at="2026-11-21T06:55:00Z", lead_time_h=9.3, reasons=["gramatyka CVCCVCV", "tld .click", "partia LE R11"]),
        P(domain="plessuro.live", issued_at="2026-11-21T00:48:00Z", issuer="R11", dna_score=0.88, campaign_id="KMP-017", status="predicted", reasons=["gramatyka CVCCVCV", "tld .live", "okno nocne"]),
        P(domain="tranvello.click", issued_at="2026-11-21T02:49:00Z", issuer="R10", dna_score=0.71, campaign_id="KMP-017", status="predicted", reasons=["gramatyka", "tld .click"]),
        P(domain="kelvaro.live", issued_at="2026-11-21T01:30:00Z", issuer="R10", dna_score=0.64, campaign_id="KMP-034", status="predicted", reasons=["tld .live", "długość 7"]),
        P(domain="brustia.click", issued_at="2026-11-21T03:10:00Z", issuer="R10", dna_score=0.42, campaign_id="KMP-017", status="below_threshold", reasons=["tylko tld"]),
    ]


def oracle_dna() -> list[DomainDNA]:
    mk = lambda cid, g, ex, tld, reg: DomainDNA(campaign_id=cid, grammar=g, examples=ex, tld_dist=tld, length_hist={"7": 9, "8": 16, "9": 11}, registrars=reg,
                                                issuance_hours=[0, 1, 2], asns=["AS64500"], model={"name": "gbm-domain-dna", "auc": 0.94}, threshold=0.6)
    return [mk("KMP-017", "CVCCVCV-like pseudo-words 7–9 liter, .click|.live", ["morvanta.click", "orvinta.click", "plessuro.live", "tranvello.click"], {"click": 0.62, "live": 0.38}, ["R-114 (anonimizowany)"]),
            mk("KMP-034", "produkt-pl.shop / pseudo-słowo.live", ["glikonor-pl.shop", "kelvaro.live"], {"shop": 0.5, "live": 0.5}, ["R-114 (anonimizowany)"])]


def oracle_metrics() -> OracleMetrics:
    return OracleMetrics(flagged_24h=5, confirmed=2, precision_at_20=0.85, median_lead_h=31.0, ct_rate_per_h=1840.0, false_alarms_24h=1,
                         backtest=[{"domain": "velmoria.click", "flagged_at": "2026-11-16T22:00:00Z", "first_ad_at": "2026-11-18T05:20:00Z", "lead_h": 31.3},
                                   {"domain": "trastino.live", "flagged_at": "2026-11-15T20:10:00Z", "first_ad_at": "2026-11-17T04:00:00Z", "lead_h": 31.8},
                                   {"domain": "quorvex.click", "flagged_at": "2026-11-14T21:00:00Z", "first_ad_at": "2026-11-16T07:30:00Z", "lead_h": 34.5}])


# ------------------------------------------------------------------------------------------- act
def act_packages() -> list[ActPackage]:
    parts = lambda ready: [{"key": "notice", "label": "Zgłoszenie DSA (PDF)", "bot": "archiwista", "ready": ready}, {"key": "stix", "label": "Pakiet STIX 2.1", "bot": "notariusz", "ready": ready},
                           {"key": "certpl", "label": "Lista domen dla CERT PL", "bot": "notariusz", "ready": ready}, {"key": "rules", "label": "Reguły (urlscan/YARA)", "bot": "tropiciel", "ready": False}]
    rec = lambda: [{"id": "meta_dsa", "label": "Meta (DSA art. 16)", "enabled": True, "progress": {"done": 0, "total": 11}, "status": "ready"},
                   {"id": "certpl", "label": "CERT Polska", "enabled": True, "progress": {"done": 0, "total": 14}, "status": "ready"},
                   {"id": "google", "label": "Google Ads", "enabled": True, "progress": {"done": 0, "total": 2}, "status": "ready"}]
    return [ActPackage(id="ACT-7", kind="bundle", campaign_id="KMP-017", status="draft", contents={"ads": 38, "advertisers": 11, "domains": 19, "evidence_items": 64},
                       recipients=rec(), parts=parts(True), formats=["pdf", "json", "stix", "misp", "csv"], created_at="2026-11-21T08:20:00+01:00",
                       notice_text="Zgłaszamy 38 reklam 11 reklamodawców promujących fałszywy portal «Kurier Dnia» (kampania KMP-017) naruszających art. 16 DSA. Dowody w załączniku."),
            ActPackage(id="ACT-3", kind="bundle", campaign_id="KMP-022", status="sent", contents={"ads": 29, "advertisers": 7, "domains": 6, "evidence_items": 41},
                       recipients=[{"id": "meta_dsa", "label": "Meta (DSA art. 16)", "enabled": True, "progress": {"done": 7, "total": 7}, "status": "done"}], parts=parts(True),
                       created_at="2026-11-12T09:40:00+01:00", sent_at="2026-11-12T10:00:00+01:00", outcome={"removed": 22, "total": 29}, notice_text="Zgłoszenie KMP-022.")]


def act_rules() -> list[Rule]:
    return [Rule(id="R-1", campaign_id="KMP-017", kind="urlscan", body='page.url:"/api/v2/relay/lead/" AND page.domain:(*.click OR *.live)'),
            Rule(id="R-2", campaign_id="KMP-017", kind="url_regex", body=r"^https://[a-z]{7,9}\.(click|live)/\?utm_source=.*utm_visit=[0-9a-f-]{36}$"),
            Rule(id="R-3", campaign_id="KMP-017", kind="html_signature", body='<script src="*cg-7f3a91e0.ecs.eu-west-1.on.aws*">'),
            Rule(id="R-4", campaign_id="KMP-017", kind="yara", body='rule kmp017_relay { strings: $a = "/api/v2/relay/lead/" condition: $a }')]


RULE_TEST = RuleTest(hits=41, tp=38, needs_review=3, benign_hits=0, benign_total=500, precision=0.93)


# ------------------------------------------------------------------------------------------- triage
def triage() -> list[TriageItem]:
    rnd = random.Random(11)
    out: list[TriageItem] = []
    k17 = U.E_CAPI
    cand = lambda cid, sc, p: TriageCandidate(campaign_id=cid, score=sc, p=p, **{"for": [U.E_CAPI, U.E_KIT][:2 if p > .4 else 1]}, against=[U.E_TPL.model_copy(update={"state": "conflict", "weight": -1.2})], missing=[U.E_ASR])
    mk = lambda i, t, subj, sug, sc, pri, cands=(), age=0: TriageItem(id=f"TRI-{i}", type=t, subject_id=subj, suggestion=sug, score=sc, priority=pri,
                                                                    created_at=f"2026-11-21T0{max(0, 8 - age)}:{rnd.randint(10, 59)}:00+01:00", candidates=list(cands))
    members_ = [m for m in U.members("KMP-034")][:8]
    for i in range(8):
        out.append(mk(i + 1, "uncertain", members_[i].incident_id, "Niepewne przypisanie: KMP-034 vs KMP-017 (p 0.35–0.65)", round(3.2 + i * .1, 1), 90 - i,
                      [cand("KMP-034", 3.9, 0.52), cand("KMP-017", 3.7, 0.42)], i % 6))
    for i, iid in enumerate(U.KMP040_IDS):
        out.append(mk(9 + i, "new_campaign", iid, "Kandydat nowej kampanii: bon energetyczny (KMP-040)", 0.7, 80 - i, [cand("KMP-017", 0.7, 0.07)], i))
    for i, d in enumerate(["plessuro.live", "tranvello.click", "kelvaro.live", "brustia.click"]):
        out.append(mk(12 + i, "oracle", d, f"Oracle: domena przewidziana ({d})", [0.88, 0.71, 0.64, 0.42][i], 70 - i, (), i))
    for i in range(4):
        out.append(mk(16 + i, "hunter", f"INC-249{10 + i}", "Hunter: nowa reklama z Ad Library", 2.0, 50 - i, (), i + 1))
    for i in range(2):
        out.append(mk(20 + i, "extension", f"INC-249{20 + i}", "Zgłoszenie z wtyczki", 1.5, 40 - i, (), i + 2))
    out.append(mk(22, "merge", "KMP-043", "Propozycja scalenia: KMP-043 → KMP-017", 6.0, 60, [cand("KMP-017", 6.0, 0.77)], 2))
    out.append(mk(23, "merge", "KMP-029", "Propozycja scalenia: KMP-029 → KMP-011 (niska pewność)", 2.2, 20, (), 5))
    return out


# ------------------------------------------------------------------------------------------- hunter
def hunter_sources() -> list[HunterSource]:
    H = HunterSource
    return [H(id="SRC-meta", kind="meta_adlibrary", label="Meta Ad Library", schedule="*/30 * * * *", status="ok", last_run_at="2026-11-21T08:30:00+01:00", new_24h=37, errors_24h=0, credentials_status="set",
              config={"phrases": ["przerywa milczenie", "napaść", "Glikonor"], "persons": ["Jan Kowalski", "Anna Nowak"], "country": "PL"}),
            H(id="SRC-gads", kind="google_ads_transparency", label="Google Ads Transparency", schedule="0 * * * *", status="degraded", last_run_at="2026-11-21T08:00:00+01:00", new_24h=4, errors_24h=2, credentials_status="not_needed", config={"advertisers": ["Ogród i Pasja 24"], "country": "PL"}),
            H(id="SRC-certpl", kind="certpl", label="Lista ostrzeżeń CERT PL", schedule="0 */6 * * *", status="ok", last_run_at="2026-11-21T06:00:00+01:00", new_24h=3, credentials_status="not_needed"),
            H(id="SRC-urlscan", kind="urlscan", label="urlscan.io", schedule="*/15 * * * *", status="ok", last_run_at="2026-11-21T08:45:00+01:00", new_24h=14, credentials_status="set", config={"phrases": ["/api/v2/relay/lead/"]}),
            H(id="SRC-ct", kind="ct", label="Strumień CT (certstream)", schedule="live", status="ok", last_run_at=U.NOW, new_24h=5, credentials_status="not_needed"),
            H(id="SRC-ext", kind="extension", label="Wtyczka przeglądarkowa", schedule="live", status="ok", last_run_at="2026-11-21T08:41:00+01:00", new_24h=2, credentials_status="not_needed")]


def hunter_runs() -> list[HunterRun]:
    return [HunterRun(id="RUN-901", source_id="SRC-meta", started_at="2026-11-21T08:30:00+01:00", finished_at="2026-11-21T08:31:12+01:00", status="ok", found=12, captured=9, attributed=8, incident_ids=["INC-24817"]),
            HunterRun(id="RUN-900", source_id="SRC-gads", started_at="2026-11-21T08:00:00+01:00", finished_at="2026-11-21T08:00:40+01:00", status="error", found=0, error="HTTP 429 (limit zapytań)"),
            HunterRun(id="RUN-899", source_id="SRC-urlscan", started_at="2026-11-21T08:45:00+01:00", status="running", found=3)]


# ------------------------------------------------------------------------------------------- lab (marked as sample)
NOTE = "przykładowe wartości, podmienić z eval/"


def lab() -> dict[str, dict]:
    s = {"sample": True, "note": NOTE}
    return {
        "summary": {**s, "bcubed_f1": 0.91, "ari": 0.87, "pairwise_precision": 0.96, "open_set_accuracy": 0.93, "new_campaign_precision": 0.95,
                    "conformal_target": 0.05, "conformal_achieved": 0.041, "m2_infra_blind_f1": 0.74},
        "baselines": {**s, "rows": [{"model": "M1 (uczony)", "bcubed_f1": 0.91}, {"model": "ręczne wagi", "bcubed_f1": 0.78}, {"model": "HDBSCAN", "bcubed_f1": 0.61}]},
        "loco": {**s, "rows": [{"campaign": c, "f1": f} for c, f in (("KMP-017", 0.93), ("KMP-022", 0.9), ("KMP-031", 0.92), ("KMP-034", 0.88))]},
        "conformal": {**s, "alpha": 0.05, "achieved_error": 0.041, "n_cal": 412, "avg_set_size": 1.08},
        "models": {**s, "rows": [{"id": "M1", "version": "engine@mock", "trained_at": "2026-11-21T04:00:00+01:00", "bcubed_f1": 0.91}, {"id": "M2", "version": "infra-blind", "bcubed_f1": 0.74}]},
        "layer_compare": {**s, "rows": [{"layer": l, "alone_f1": v} for l, v in (("tracking", 0.84), ("kit", 0.8), ("infra", 0.74), ("content", 0.7), ("persons", 0.52), ("visual", 0.61), ("ad", 0.4), ("media", 0.35))]},
    }


def ablation() -> list[dict]:
    return [{"layer": l, "delta_f1": d, "sample": True, "note": NOTE} for l, d in (("tracking", -0.12), ("kit", -0.09), ("infra", -0.17), ("content", -0.06), ("persons", -0.03), ("visual", -0.04), ("ad", -0.01), ("media", -0.02))]


# ------------------------------------------------------------------------------------------- persons / alerts / misc
def persons() -> list[dict]:
    rows = [("P-01", "Jan Kowalski", "przedsiębiorca", 61, 38.0, [("KMP-017", 28), ("KMP-043", 4)], 0.91, 0.82, None),
            ("P-02", "Anna Nowak", "dziennikarka", 24, 20.0, [("KMP-017", 11)], 0.88, None, None),
            ("P-03", "Tomasz Lewandowski", "dziennikarz", 18, 5.0, [("KMP-017", 7)], 0.86, None, None),
            ("P-04", "dr Piotr Wiśniewski", "lekarz (persona)", 43, -4.0, [("KMP-022", 31), ("KMP-034", 12)], 0.9, 0.79, 0.87),
            ("P-05", "Marek Zieliński", "sportowiec", 52, 3.0, [("KMP-031", 40), ("KMP-036", 12)], 0.89, 0.74, None),
            ("P-06", "Katarzyna Wójcik", "prezenterka", 33, 2.0, [("KMP-031", 33)], 0.87, 0.7, None)]
    return [{"id": i, "name": n, "role": r, "count": c, "trend_pct": t, "campaigns": [{"id": a, "count": b} for a, b in cs], "face_match": fm, "deepfake_score": df, "voice_score": vs,
             "weekly": [{"week": f"2026-W{w}", "count": max(1, c // 8 + (w % 3))} for w in range(40, 48)],
             "narratives": ["Fałszywy news o napaści"] if "KMP-017" in str(cs) else ["Fałszywa rekomendacja produktu/inwestycji"],
             "sample_incidents": [m.incident_id for m in U.members(cs[0][0])[:3]]} for i, n, r, c, t, cs, fm, df, vs in rows]


def brands() -> list[dict]:
    return [{"name": "Kurier Dnia", "kind": "portal (podszycie)", "count": 46, "campaigns": ["KMP-017", "KMP-043"]},
            {"name": "TV Info24", "kind": "stacja (podszycie)", "count": 31, "campaigns": ["KMP-031", "KMP-029"]},
            {"name": "Bank Przykładowy", "kind": "bank (podszycie)", "count": 22, "campaigns": ["KMP-011", "KMP-031"]}]


def alerts() -> list[dict]:
    return [{"id": "ALR-1", "kind": "hunter", "severity": "hot", "title": "Hunter: nowa domena morvanta.click dołączona do KMP-017 (INC-24817)", "subject_id": "INC-24817", "created_at": "2026-11-21T02:31:00Z", "status": "open"},
            {"id": "ALR-2", "kind": "oracle", "severity": "warn", "title": "Oracle: plessuro.live (0.88) — cert 00:47, brak jeszcze reklam", "subject_id": "plessuro.live", "created_at": "2026-11-21T00:48:00Z", "status": "open"},
            {"id": "ALR-3", "kind": "campaign", "severity": "hot", "title": "KMP-017 «Zamach»: +38% w 48 h", "subject_id": "KMP-017", "created_at": "2026-11-21T07:00:00Z", "status": "open"},
            {"id": "ALR-4", "kind": "triage", "severity": "info", "title": "Kandydat nowej kampanii: bon energetyczny (KMP-040)", "subject_id": "KMP-040", "created_at": "2026-11-21T06:10:00Z", "status": "open"}]


def stats() -> dict[str, dict]:
    return {"24h": {"window": "24h", "incidents": 1284, "incidents_new": 37, "campaigns_active": 41, "operators": 6, "domains_new": 23, "oracle_flagged": 5, "triage_open": 23, "N": 1284},
            "night": {"window": "night", "incidents": 1284, "incidents_new": 14, "campaigns_active": 41, "operators": 6, "domains_new": 9, "oracle_flagged": 4, "triage_open": 23, "N": 1284}}
