"""Builds the fictional TROP universe (docs/design/canvas/BRIEF.md) as pydantic objects.

`python -m trop.api.mock.build` dumps these to JSON files next to this module; the API loads (and validates) the JSON.
Everything here is FICTIONAL (IPs in documentation ranges, ASN 64500+, invented domains/people). Numbers are kept
consistent across resources: N=1284, KMP-017 = 46 incidents / 19 domains / 11 advertisers, INC-24817 p=0.94, ...
"""
from __future__ import annotations

import math
import random
import zlib
from typing import Any

from trop.schema import (
    AdLayer, Adjudication, Campaign, CampaignCounts, CampaignDNA, CampaignScore, Content, Counterfactual, Decision,
    DnaRow, DomainInfo, EvidenceItem, EvidenceValue, FaceHit, Heat, Incident, IncidentSource, IncidentSummary, Infra,
    Landing, LayerCoverage, LinkExplanation, Media, Member, Quality, RunnerUp, TemplateDiff, Tok, Tracking, WhyNot,
)

N = 1284
NOW = "2026-11-21T08:50:00+01:00"
LAYERS = ["tracking", "kit", "infra", "content", "persons", "visual", "ad", "media"]
CAPI = "cg-7f3a91e0.ecs.eu-west-1.on.aws/events"
KIT = "/api/v2/relay/lead/{uuid}/"
TPL_V2 = "PILNE: {PER} przerywa milczenie po napaści…"
TPL_V1 = "«Wiem, kto to zrobił»: atak na {PER}"
DAY = ["2026-11-%02d" % d for d in range(8, 22)]  # 14 days ending 21.11


def h(s: str) -> int:
    """Deterministic hash (python's str hash is salted per process)."""
    return zlib.crc32(s.encode())


def idf(df: int) -> float:
    return round(math.log(N / max(df, 1)), 2)


def ev(type_: str, field: str, value: str, display: str, strength: str, weight: float, df: int, bot: str | None = None,
       state: str = "match", level: str = "campaign", sides: dict | None = None) -> EvidenceItem:
    return EvidenceItem(type=type_, field=field, value=value, display=display, strength=strength, weight=weight, df=df,
                        N=N, idf=idf(df), state=state, level=level, sides=sides, bot=bot)


# --------------------------------------------------------------------------------------------- evidence library
E_CAPI = ev("tracking", "capi_gateway", CAPI, "CAPI cg-7f3a…", "H", 3.1, 47, "tropiciel")
E_KIT = ev("kit", "kit_endpoint", KIT, "relay/lead template", "H", 2.7, 58, "tropiciel")
E_TPL = ev("content", "headline_template", TPL_V2, "szablon „PILNE: {PER}…”", "H", 2.2, 22, "czytelnik")
E_CERT = ev("infra", "cert_batch", "LE-R11 2026-11-21T00:47Z..02:31Z", "cert batch LE R11 00:47–02:31", "M", 1.4, 6, "notariusz")
E_PHASH = ev("visual", "landing_phash", "d4:phash<=4", "landing pHash Δ4", "M", 0.9, 9, "zwiadowca")
E_PERSON = ev("persons", "face_identity", "Jan Kowalski", "Jan Kowalski (twarz 0.91 + NER)", "M", 0.8, 61, "czytelnik")
E_DECOY = ev("ad", "creative_decoy", "decoy:landscape/animal", "kreacja-wabik (krajobraz/zwierzę)", "L", 0.3, 140, "zwiadowca")
E_CF = ev("infra", "ip_range", "203.0.113.0/24", "Cloudflare 203.0.113.0/24", "L", 0.0, 512, "notariusz", state="zero")
E_ASR = ev("media", "asr_text", "", "brak ścieżki audio (ASR)", "M", 0.0, 0, "czytelnik", state="missing")
E_RDAP = ev("infra", "rdap_registrar", "", "RDAP — timeout (częściowe)", "L", 0.0, 0, "notariusz", state="missing")
INC_24817_EVIDENCE = [E_CAPI, E_KIT, E_TPL, E_CERT, E_PHASH, E_PERSON, E_DECOY, E_CF]

LAYERS_24817 = [
    LayerCoverage(layer="tracking", state="available"), LayerCoverage(layer="kit", state="available"),
    LayerCoverage(layer="infra", state="partial", reason="RDAP timeout — brak danych rejestratora"),
    LayerCoverage(layer="content", state="available"), LayerCoverage(layer="persons", state="available"),
    LayerCoverage(layer="visual", state="available"), LayerCoverage(layer="ad", state="available"),
    LayerCoverage(layer="media", state="missing", reason="brak wideo/ASR w tym materiale"),
]


def layers_full(missing: tuple[str, ...] = ()) -> list[LayerCoverage]:
    return [LayerCoverage(layer=l, state="missing" if l in missing else "available") for l in LAYERS]


# --------------------------------------------------------------------------------------------- domains
KMP017_DOMAINS = [
    # fqdn, cert_issued_at, on certpl, online, ads_seen, oracle_predicted_at
    ("morvanta.click", "2026-11-21T02:31:00Z", False, True, 4, "2026-11-19T19:28:00Z"),
    ("orvinta.click", "2026-11-21T01:12:00Z", False, True, 2, "2026-11-20T21:40:00Z"),
    ("plessuro.live", "2026-11-21T00:47:00Z", False, True, 0, None),
    ("velmoria.click", "2026-11-18T01:03:00Z", True, True, 7, None),
    ("trastino.live", "2026-11-17T00:22:00Z", True, True, 5, None),
    ("quorvex.click", "2026-11-16T02:10:00Z", True, True, 6, None),
    ("ambrelio.live", "2026-11-15T01:45:00Z", False, True, 3, None),
    ("dunvarra.click", "2026-11-14T02:02:00Z", False, True, 4, None),
    ("selqueno.live", "2026-11-13T00:31:00Z", False, "502", 2, None),
    ("tranvello.click", "2026-11-20T02:48:00Z", False, True, 1, None),
    ("korvelta.click", "2026-11-12T01:18:00Z", False, True, 3, None),
    ("mandurex.live", "2026-11-12T00:55:00Z", False, True, 2, None),
    ("vistorra.click", "2026-11-11T02:20:00Z", False, True, 5, None),
    ("plenvaro.live", "2026-11-11T01:07:00Z", False, True, 1, None),
    ("sarmelto.click", "2026-11-10T00:40:00Z", False, True, 3, None),
    ("dolvinex.click", "2026-11-10T02:33:00Z", False, True, 2, None),
    ("kervanta.live", "2026-11-09T01:51:00Z", False, True, 1, None),
    ("ormalto.click", "2026-11-09T00:14:00Z", True, True, 2, None),
    ("brenvilo.live", "2026-11-08T02:05:00Z", True, True, 1, None),
]
ADVERTISERS_017 = [
    ("Ogród i Pasja 24", "104200113345001", True), ("Puzzle Mania PL", "104200113345002", True),
    ("Lena Kwiatkowska Sklep", "104200113345003", True), ("Domek Ogrodnika", "104200113345004", False),
    ("Koty i Psy Sklep", "104200113345005", False), ("Pan Wędkarz 24", "104200113345006", True),
    ("Ekstra Okazje Shop", "104200113345007", False), ("Rower Dla Każdego", "104200113345008", False),
    ("Hobby Zakątek PL", "104200113345009", False), ("Mała Księgarnia Online", "104200113345010", False),
    ("Dom i Wnętrza Plus", "104200113345011", False),
]

# --------------------------------------------------------------------------------------------- campaigns
CAMP_SPEC: list[dict[str, Any]] = [
    dict(id="KMP-017", name="Zamach — fałszywy portal → „inwestycja”", vertical="investment", status="active", op="OP-03",
         opn="OPN-01", n=46, dom=19, new_dom=3, pred=2, trend=38.0, persons=["Jan Kowalski", "Anna Nowak", "Tomasz Lewandowski"],
         report="draft", narrative="Fałszywy portal „Kurier Dnia” z newsem o napaści prowadzi do „inwestycji”.",
         desc="Reklamy z kreacjami-wabikami (krajobrazy, zwierzęta) prowadzą na klon portalu «Kurier Dnia» z fałszywym "
              "newsem o napaści na znaną osobę; dalej przekierowanie do platformy „inwestycyjnej”.",
         brands=["Kurier Dnia"], first="2026-11-08", last="2026-11-21", inc24=5, adv=11, advrm=4, certs=3, certpl=5, persn=3),
    dict(id="KMP-034", name="Cukrzyca — Glikonor", vertical="health", status="active", op="OP-03", opn="OPN-01", n=12, dom=3,
         new_dom=1, pred=1, trend=12.0, persons=["dr Piotr Wiśniewski"], report="none",
         narrative="Deepfake lekarza reklamuje „cud-preparat” Glikonor na cukrzycę.",
         desc="Wideo-deepfake „dr Piotra Wiśniewskiego” i landing produktu Glikonor; ten sam kit relay v1 i bramka CAPI co KMP-017.",
         brands=["Glikonor"], first="2026-11-02", last="2026-11-21", inc24=2, adv=4, advrm=1, certs=0, certpl=1, persn=1),
    dict(id="KMP-022", name="Stawy — fałszywy lekarz", vertical="health", status="active", op="OP-07", opn="OPN-02", n=31, dom=6,
         new_dom=0, pred=0, trend=-8.0, persons=["dr Piotr Wiśniewski"], report="sent",
         narrative="Syntetyczny głos „lekarza” poleca Artovita Forte na stawy.",
         desc="Persona dr Piotr Wiśniewski (głos syntetyczny 0.87), produkt Artovita Forte, parametry Keitaro clickid/key/pixel_fb.",
         brands=["Artovita Forte"], first="2026-10-14", last="2026-11-20", inc24=1, adv=7, advrm=5, certs=0, certpl=3, persn=1),
    dict(id="KMP-031", name="Platforma AI — inwestycje", vertical="investment", status="active", op="OP-05", opn=None, n=58, dom=9,
         new_dom=1, pred=0, trend=4.0, persons=["Marek Zieliński", "Katarzyna Wójcik"], report="sent",
         narrative="„Platforma AI” z udziałem sportowca i prezenterki obiecuje zyski z inwestycji.",
         desc="Persony Marek Zieliński i Katarzyna Wójcik, landing quantapl-invest.top, Google Ads AW-11122233344.",
         brands=["TV Info24", "Bank Przykładowy"], first="2026-09-29", last="2026-11-21", inc24=3, adv=9, advrm=6, certs=0, certpl=4, persn=2),
    dict(id="KMP-040", name="Bon energetyczny (kandydat)", vertical="gov-subsidy", status="candidate", op=None, opn=None, n=3, dom=2,
         new_dom=2, pred=0, trend=0.0, persons=[], report="none",
         narrative="Dopłata „bon energetyczny” — wyłudzenie danych; brak wspólnej infrastruktury ze znanymi kampaniami.",
         desc="Kandydat nowej kampanii: przynęta rządowa, zbiór konformalny pusty, brak wspólnych warstw z KMP-017/022/031.",
         brands=["Ministerstwo (podszycie)"], first="2026-11-20", last="2026-11-21", inc24=3, adv=2, advrm=0, certs=0, certpl=0, persn=0),
    dict(id="KMP-043", name="Zamach — wariant z nagraniem (kandydat scalenia)", vertical="investment", status="candidate", op="OP-03",
         opn="OPN-01", n=4, dom=2, new_dom=0, pred=0, trend=0.0, persons=["Jan Kowalski"], report="none",
         narrative="Ten sam szablon V3 (deepfake) co w KMP-017, osobny klaster.", merge="może to KMP-017?",
         desc="Mała grupa z deepfake’iem Jana Kowalskiego; wspólny kit relay i CAPI z KMP-017.",
         brands=["Kurier Dnia"], first="2026-11-17", last="2026-11-20", inc24=0, adv=2, advrm=0, certs=0, certpl=0, persn=1),
    dict(id="KMP-011", name="Kredyt bez BIK", vertical="loan", status="fading", op="OP-01", opn=None, n=22, dom=5, new_dom=0, pred=0,
         trend=-31.0, persons=[], report="sent", narrative="Pożyczki „bez BIK” z fałszywą stroną banku.",
         desc="Wygasająca kampania pożyczkowa, 5 domen, ostatnia reklama 17.11.", brands=["Bank Przykładowy"],
         first="2026-09-02", last="2026-11-17", inc24=0, adv=5, advrm=5, certs=0, certpl=5, persn=0),
    dict(id="KMP-029", name="Bon paliwowy", vertical="gov-subsidy", status="active", op="OP-04", opn=None, n=17, dom=4, new_dom=1, pred=0,
         trend=9.0, persons=[], report="none", narrative="„Bon na paliwo” z ankietą zbierającą dane karty.",
         desc="Ankieta + formularz karty, infrastruktura kitu v2 niepowiązana z innymi.", brands=["TV Info24"],
         first="2026-10-21", last="2026-11-21", inc24=1, adv=4, advrm=2, certs=0, certpl=2, persn=0),
    dict(id="KMP-036", name="Kryptowaluta — bot handlowy", vertical="crypto", status="active", op="OP-09", opn=None, n=14, dom=4,
         new_dom=0, pred=0, trend=-3.0, persons=["Marek Zieliński"], report="draft",
         narrative="Bot handlowy „AutoProfit” promowany przez deepfake sportowca.",
         desc="Landing z licznikiem „miejsc”, ten sam wizerunek co w KMP-031 ale inna infrastruktura (OP-09).",
         brands=["AutoProfit"], first="2026-10-05", last="2026-11-19", inc24=0, adv=3, advrm=1, certs=0, certpl=1, persn=1),
]
SPEC = {c["id"]: c for c in CAMP_SPEC}


def _series(rnd: random.Random, n: int, total: int, trend: float) -> list[int]:
    w = [max(0.2, 1 + (trend / 100) * (i / max(1, n - 1)) + rnd.uniform(-0.35, 0.35)) for i in range(n)]
    s = sum(w)
    return [int(round(total * x / s)) for x in w]


def campaigns() -> list[Campaign]:
    rnd = random.Random(1)
    out = []
    for c in CAMP_SPEC:
        heat = Heat(series_48h=_series(rnd, 48, max(2, c["inc24"] * 2 + 3), c["trend"]),
                    series_14d=_series(rnd, 14, c["n"], c["trend"]), trend_pct=c["trend"])
        out.append(Campaign(
            id=c["id"], name=c["name"], narrative=c["narrative"], vertical=c["vertical"], status=c["status"],
            operator_id=c["op"], operation_id=c["opn"], heat=heat, n_incidents=c["n"], n_domains=c["dom"],
            new_domains_24h=c["new_dom"], predicted_domains=c["pred"], persons=c["persons"], report_status=c["report"],
            merge_hint=c.get("merge"), description=c["narrative"] + "\n" + c["desc"],   # line 1 = Raport headline (WS3 req. 5)
            counts=CampaignCounts(incidents=c["n"], incidents_24h=c["inc24"], domains=c["dom"], certs_tonight=c["certs"],
                                  advertisers=c["adv"], advertisers_removed=c["advrm"], persons=c["persn"],
                                  certpl_listed=c["certpl"]),
            first_seen=c["first"], last_seen=c["last"], brands=c["brands"]))
    return out


# --------------------------------------------------------------------------------------------- DNA per campaign
def dna_rows(cid: str) -> list[DnaRow]:
    n = SPEC[cid]["n"]
    if cid == "KMP-017":
        return [
            DnaRow(layer="tracking", field="capi_gateway", value=CAPI, display="CAPI cg-7f3a…", members_with=41, members_total=n, strength="H", bot="tropiciel"),
            DnaRow(layer="kit", field="kit_endpoint", value=KIT, display="relay/lead template", members_with=40, members_total=n, strength="H", bot="tropiciel"),
            DnaRow(layer="content", field="headline_template", value=TPL_V2, display="szablon V2 „PILNE: {PER}…”", members_with=22, members_total=n, strength="H", bot="czytelnik"),
            DnaRow(layer="content", field="headline_template", value=TPL_V1, display="szablon V1 „Wiem, kto to zrobił”", members_with=19, members_total=n, strength="H", bot="czytelnik"),
            DnaRow(layer="kit", field="url_param_schema", value="utm×5+utm_visit=uuidv7", display="gramatyka URL: utm×5 + utm_visit", members_with=44, members_total=n, strength="M", bot="tropiciel"),
            DnaRow(layer="infra", field="cert_batch", value="LE-R11 nocne partie 00:00–03:00 UTC", display="LE R11 nocne partie", members_with=33, members_total=n, strength="M", bot="notariusz"),
            DnaRow(layer="infra", field="asn", value="AS64500", display="origin AS64500 za Cloudflare", members_with=36, members_total=n, strength="M", bot="notariusz"),
            DnaRow(layer="persons", field="face_identity", value="Jan Kowalski", display="Jan Kowalski", members_with=28, members_total=n, strength="M", bot="czytelnik"),
            DnaRow(layer="visual", field="landing_phash", value="phash-cluster-k17", display="landing pHash (klon «Kurier Dnia»)", members_with=39, members_total=n, strength="M", bot="zwiadowca"),
            DnaRow(layer="ad", field="creative_decoy", value="decoy:landscape/animal", display="kreacje-wabiki", members_with=31, members_total=n, strength="L", bot="zwiadowca"),
        ]
    rows = [
        DnaRow(layer="content", field="headline_template", value=f"szablon {cid}", display=f"szablon nagłówka {cid}", members_with=max(1, int(n * .8)), members_total=n, strength="H", bot="czytelnik"),
        DnaRow(layer="infra", field="asn", value="AS645%02d" % (int(cid[-3:]) % 12), display="hosting wspólny", members_with=max(1, int(n * .7)), members_total=n, strength="M", bot="notariusz"),
        DnaRow(layer="visual", field="landing_phash", value=f"phash-{cid}", display="landing pHash", members_with=max(1, int(n * .75)), members_total=n, strength="M", bot="zwiadowca"),
    ]
    if cid == "KMP-034":
        rows = [DnaRow(layer="tracking", field="capi_gateway", value=CAPI, display="CAPI cg-7f3a… (wspólna z KMP-017)", members_with=10, members_total=n, strength="H", bot="tropiciel"),
                DnaRow(layer="kit", field="kit_endpoint", value="/api/v1/relay/lead/{uuid}/", display="relay kit v1", members_with=11, members_total=n, strength="H", bot="tropiciel"),
                DnaRow(layer="persons", field="face_identity", value="dr Piotr Wiśniewski", display="dr Piotr Wiśniewski (deepfake)", members_with=12, members_total=n, strength="M", bot="czytelnik")] + rows
    if cid == "KMP-022":
        rows = [DnaRow(layer="tracking", field="fb_pixel", value="870011223344556", display="FB pixel 8700…556", members_with=29, members_total=n, strength="H", bot="tropiciel"),
                DnaRow(layer="kit", field="url_param_schema", value="clickid/key/pixel_fb", display="parametry Keitaro clickid/key/pixel_fb", members_with=27, members_total=n, strength="M", bot="tropiciel"),
                DnaRow(layer="media", field="voice_id", value="voice-syn-0.87", display="głos syntetyczny 0.87", members_with=18, members_total=n, strength="M", bot="czytelnik")] + rows
    if cid == "KMP-031":
        rows = [DnaRow(layer="tracking", field="google_ads", value="AW-11122233344", display="Google Ads AW-11122233344", members_with=50, members_total=n, strength="H", bot="tropiciel")] + rows
    return rows


def dna(cid: str) -> CampaignDNA:
    return CampaignDNA(campaign_id=cid, signature=dna_rows(cid))


# --------------------------------------------------------------------------------------------- members / incidents
SOURCES = ["adlibrary", "hunter", "extension", "upload", "urlscan"]
_pool = list(range(24500, 24830))
random.Random(7).shuffle(_pool)
_pool = [x for x in _pool if x not in (24817, 24866)]
KMP040_IDS = ["INC-24901", "INC-24902", "INC-24903"]
_DOMS = {
    "KMP-017": [d[0] for d in KMP017_DOMAINS],
    "KMP-034": ["glikonor-pl.shop", "kelvaro.live", "glikonor-oferta.shop"],
    "KMP-022": ["artovita-forte.shop", "zdrowestawy-pl.store", "stawy-bez-bolu.store", "artovita-oferta.shop", "lekarz-stawy.store", "forte-stawy.shop"],
    "KMP-031": ["quantapl-invest.top", "ai-zysk.top", "platforma-ai24.top", "invest-ai-pl.top", "zyskpl-ai.top", "quantapl-pro.top", "aibroker-pl.top", "inwestuj-ai.top", "quantapl-live.top"],
    "KMP-040": ["bonenergetyczny24.site", "ddoplata-energia.info"],
    "KMP-043": ["zamach-nagranie.click", "kurier-wideo.live"],
    "KMP-011": ["kredyt-szybki.online", "bez-bik-pl.online", "pozyczka-24h.online", "bank-przyklad-kredyt.online", "kredyt-ok.online"],
    "KMP-029": ["bon-paliwowy.site", "paliwo-doplata.site", "ankieta-paliwo.site", "bon-stacja.site"],
    "KMP-036": ["autoprofit-bot.io", "crypto-zysk.io", "bot-handlowy.io", "autoprofit-pl.io"],
}


def _ids_for(cid: str) -> list[str]:
    if cid == "KMP-017":
        return ["INC-24817"] + ["INC-%d" % _pool.pop() for _ in range(45)]
    if cid == "KMP-034":
        return ["INC-24866"] + ["INC-%d" % _pool.pop() for _ in range(11)]
    if cid == "KMP-040":
        return KMP040_IDS
    return ["INC-%d" % _pool.pop() for _ in range(SPEC[cid]["n"])]


_IDS: dict[str, list[str]] = {c["id"]: _ids_for(c["id"]) for c in CAMP_SPEC}
VARIANTS = {"KMP-017": [("V2", 22, TPL_V2), ("V1", 19, TPL_V1), ("V3", 5, "nagranie wideo (deepfake)")]}


def _variant_of(cid: str, i: int) -> str | None:
    if cid != "KMP-017":
        return None
    return "V2" if i < 22 else "V1" if i < 41 else "V3"


def members(cid: str) -> list[Member]:
    rnd = random.Random(h(cid) % 1000 + 3)
    s, out = SPEC[cid], []
    ids = _IDS[cid]
    doms = _DOMS[cid]
    for i, iid in enumerate(ids):
        if iid == "INC-24817":
            out.append(Member(incident_id=iid, captured_at="2026-11-21T02:31:00Z", source="hunter", domain="morvanta.click", person="Jan Kowalski",
                              level="L2", variant_id="V2", parent_id=None, score=11.4, p=0.94,
                              top_evidence=[E_CAPI, E_KIT, E_TPL], layers=LAYERS_24817))
            continue
        day = rnd.randint(0, 13) if cid != "KMP-040" else rnd.randint(11, 13)
        hh, mm = rnd.randint(0, 23), rnd.randint(0, 59)
        lvl = "L0" if i % 11 == 7 else "L1" if i % 5 == 3 else "L2"
        var = _variant_of(cid, i)
        base_ev = [E_CAPI, E_KIT, E_TPL] if cid == "KMP-017" else [
            ev(r.layer, r.field, r.value, r.display or r.value, r.strength, round(1.2 + (i % 3), 1), max(6, r.members_with), r.bot)
            for r in dna_rows(cid)[:2]]
        out.append(Member(
            incident_id=iid, captured_at=f"{DAY[day]}T{hh:02d}:{mm:02d}:00Z", source=SOURCES[(i + len(cid)) % 5], domain=doms[i % len(doms)],
            person=(s["persons"][i % len(s["persons"])] if s["persons"] else None), level=lvl, variant_id=var,
            parent_id=(ids[max(0, i - 1)] if lvl in ("L0", "L1") else None),
            score=round(6.2 + rnd.random() * 5, 1), p=round(0.86 + rnd.random() * 0.12, 2) if cid != "KMP-040" else 0.07,
            top_evidence=base_ev, layers=layers_full(("media",) if i % 4 else ())))
    out.sort(key=lambda m: m.captured_at or "", reverse=True)
    return out


def _title(cid: str, var: str | None, person: str | None) -> str:
    per = person or "znana osoba"
    if cid == "KMP-017":
        return (TPL_V2 if var == "V2" else TPL_V1 if var == "V1" else "Nagranie: {PER} o napaści").replace("{PER}", per)
    return {"KMP-034": "Glikonor — cud na cukrzycę", "KMP-022": "Artovita Forte — koniec bólu stawów",
            "KMP-031": "Platforma AI — zarabiaj z %s" % per, "KMP-040": "Bon energetyczny 2026 — sprawdź przysługującą dopłatę",
            "KMP-043": "Nagranie: %s o napaści" % per, "KMP-011": "Kredyt bez BIK od ręki", "KMP-029": "Bon paliwowy — odbierz",
            "KMP-036": "AutoProfit — bot, który zarabia za Ciebie"}[cid]


def incident_summaries() -> list[IncidentSummary]:
    out = []
    for cid in SPEC:
        for m in members(cid):
            out.append(IncidentSummary(
                id=m.incident_id, captured_at=m.captured_at, source=m.source, domain=m.domain,
                title=_title(cid, m.variant_id, m.person), person=m.person, campaign_id=cid,
                decision="new" if cid == "KMP-040" else "assign", p=m.p,
                coverage=0.78 if m.incident_id == "INC-24817" else round(0.6 + (h(m.incident_id) % 30) / 100, 2)))
    out.sort(key=lambda s: s.captured_at or "", reverse=True)
    out.append(IncidentSummary(id="INC-24920", captured_at="2026-11-21T08:47:00Z", source="upload", domain="selqueno.live", title="selqueno.live — strona niedostępna (502)",
                               campaign_id=None, decision="insufficient", p=0.0, coverage=0.12))
    return out


def _incident(summary: IncidentSummary) -> dict:
    cid = summary.campaign_id or "KMP-017"        # INC-24920 has no campaign; shaped like its (down) KMP-017 domain
    dom = summary.domain or "example.invalid"
    is_k17 = cid == "KMP-017"
    tracking = Tracking(
        capi_gateways=[CAPI] if is_k17 or cid in ("KMP-034", "KMP-043") else [],
        kit_endpoints=["/api/v2/relay/lead/{uuid}/"] if is_k17 else [],
        kit_tenants=["kit-tenant-a41"] if cid in ("KMP-017", "KMP-034", "KMP-043") else [],
        fb_pixels=["870011223344556"] if cid == "KMP-022" else [], google_ads=["AW-11122233344"] if cid == "KMP-031" else [],
        url_param_schema="utm*5+utm_visit" if is_k17 else "clickid/key/pixel_fb" if cid == "KMP-022" else None)
    src = summary.source if summary.source in ("hunter", "adlibrary", "extension", "upload", "urlscan") else "manual"
    inc = Incident(
        id=summary.id, source=IncidentSource(type=src, ref=f"mock/{summary.id}", captured_at=summary.captured_at),
        ad=AdLayer(platform="meta", kind="feed", advertiser=ADVERTISERS_017[h(summary.id) % 11][0] if is_k17 else "Sklep Mock",
                   cta="Czytaj więcej", text=summary.title, display_link="OKAZJE-DNIA.COM" if is_k17 else None,
                   persons=[summary.person] if summary.person else [], is_decoy=is_k17, vertical=SPEC[cid]["vertical"],
                   screenshot_path=f"mock/{summary.id}/ad.png"),
        landing=Landing(entry_url=f"https://{dom}/", final_url=f"https://{dom}/", host=dom, etld1=dom, status=200, title=summary.title,
                        lang="pl", page_role="prelander", redirect_chain=[f"https://{dom}/r/1", f"https://{dom}/"], n_hars=1, n_pages=2,
                        screenshot_path=f"mock/{summary.id}/landing.png"),
        tracking=tracking,
        infra=Infra(domains=[DomainInfo(fqdn=dom, etld1=dom, tld=dom.rsplit(".", 1)[-1], sld_label=dom.split(".")[0], ips=["198.51.100.23"],
                                        asn="AS64500", enrich={"registrar": "R-114 (anonimizowany)"})],
                    ips=["203.0.113.7"], cdn=["cloudflare"], origin_ips=["198.51.100.23"] if is_k17 else [],
                    on_certpl_list=dom in ("velmoria.click", "trastino.live")),
        content=Content(headline_template=_title(cid, None, None), persons=[summary.person] if summary.person else [], lang="pl",
                        vertical=SPEC[cid]["vertical"], narrative=SPEC[cid]["narrative"]),
        media=Media(faces=[FaceHit(identity=summary.person, score=0.91, lead=0.2, source="ad_screenshot")] if summary.person else []),
        quality=Quality(available=[l for l in LAYERS if l != "media"], missing=["media"]),
    )
    d = inc.model_dump(mode="json")
    d["decision"] = {"campaign_id": cid if summary.decision == "assign" else None, "p": summary.p, "decision": summary.decision}
    d["coverage"] = summary.coverage or 0.7
    return d


def incident_details() -> dict[str, dict]:
    out = {s.id: _incident(s) for s in incident_summaries()}
    out["INC-24920"]["quality"] = {"available": [], "missing": LAYERS, "errors": ["capture: HTTP 502"]}
    out["INC-24920"]["decision"] = {"campaign_id": None, "p": 0.0, "decision": "insufficient"}
    k = out["INC-24817"]
    k["source"].update(type="hunter", ref="adlibrary:meta:INC-24817", captured_at="2026-11-21T02:31:00Z")
    k["ad"].update(advertiser="Ogród i Pasja 24", page_id="104200113345001", library_id="1049912003345117", cta="Czytaj więcej",
                   display_link="OKAZJE-DNIA.COM", is_decoy=True, text="PILNE: Jan Kowalski przerywa milczenie po napaści…",
                   persons=["Jan Kowalski"])
    k["landing"].update(
        entry_url="https://morvanta.click/?utm_source=fb&utm_medium=cpc&utm_campaign=c17&utm_content=a3&utm_term=x&utm_visit=018f3b1e-7c2a-7d10-9a55-3e1f2b6c4d90",
        final_url="https://morvanta.click/kurier-dnia/zamach", host="morvanta.click", title="Kurier Dnia — Jan Kowalski przerywa milczenie",
        redirect_chain=["https://morvanta.click/r/17", "https://morvanta.click/lp/3", "https://morvanta.click/kurier-dnia/zamach",
                        "https://invest.relay.example/lead"], n_hars=1, n_pages=4)
    k["infra"]["domains"] = [{"fqdn": "morvanta.click", "etld1": "morvanta.click", "tld": "click", "sld_label": "morvanta", "ips": ["203.0.113.7"],
                              "asn": "AS64500", "cdn": ["cloudflare"], "cert": {"issuer": "Let's Encrypt R11", "not_before": "2026-11-21T02:31:00Z"},
                              "enrich": {"rdap": "timeout", "certs_tonight": 3}}]
    k["infra"]["origin_ips"] = ["198.51.100.23"]
    k["quality"] = {"available": ["tracking", "kit", "content", "persons", "visual", "ad"], "missing": ["media"], "errors": ["rdap: timeout"]}
    k["coverage"] = 0.78
    k["decision"] = {"campaign_id": "KMP-017", "p": 0.94, "decision": "assign"}
    return out


# --------------------------------------------------------------------------------------------- decisions
def decision_24817() -> Decision:
    return Decision(
        incident_id="INC-24817", decision="assign", campaign_id="KMP-017", score=11.4, margin=0.53, p=0.94, operator_id="OP-03",
        operation_id="OPN-01",
        scores=[CampaignScore(campaign_id="KMP-017", score=11.4, score_operator=11.4, p=0.94, p_value=0.62, in_set=True),
                CampaignScore(campaign_id="KMP-034", score=3.6, score_operator=6.4, p=0.41, p_value=0.03, in_set=False),
                CampaignScore(campaign_id="KMP-043", score=2.9, score_operator=6.0, p=0.18, p_value=0.01, in_set=False)],
        runner_up=RunnerUp(campaign_id="KMP-034", score=3.6, p=0.41, same_operator=True), coverage=0.78, layers=LAYERS_24817,
        evidence=INC_24817_EVIDENCE + [E_ASR, E_RDAP],
        why_not=[WhyNot(campaign_id="KMP-034", bullets=["Wspólne: bramka CAPI i relay kit → ten sam operator OP-03, nie ta sama kampania.",
                                                         "Inny szablon nagłówka (zdrowie vs. napaść) i inna persona (dr Piotr Wiśniewski).",
                                                         "Brak wspólnych domen i partii certyfikatów."]),
                 WhyNot(campaign_id="KMP-043", bullets=["Tylko wariant V3 (deepfake) — ten materiał to wariant V2 z tekstem.",
                                                         "Kandydat scalenia z KMP-017."])],
        adjudicator=Adjudication(model="qwen/qwen3.8-27b", verdict="same", confidence=0.93,
                                 rationale=["Ta sama bramka CAPI i ścieżka relay/lead", "Szablon nagłówka V2 identyczny z członkami KMP-017",
                                            "Partia certyfikatów LE R11 z tej samej nocy"]),
        alpha=0.05, conformal_tau=0.55, set=["KMP-017"], calibration={"target": 0.05, "achieved": 0.041, "n_cal": 412}, model_version="engine@mock")


def decision_new() -> Decision:
    ev_ = [ev("content", "narrative", "gov-subsidy:bon-energetyczny", "przynęta: bon energetyczny", "M", 0.7, 3, "czytelnik"),
           ev("infra", "ip_range", "203.0.113.0/24", "Cloudflare 203.0.113.0/24", "L", 0.0, 512, "notariusz", state="zero")]
    return Decision(incident_id="INC-24901", decision="new", candidate_campaign_id="KMP-040", score=0.7, margin=0.0, p=0.07,
                    scores=[CampaignScore(campaign_id="KMP-017", score=0.7, score_operator=0.9, p=0.07, p_value=0.004),
                            CampaignScore(campaign_id="KMP-029", score=0.6, score_operator=0.6, p=0.05, p_value=0.003)],
                    coverage=0.71, layers=layers_full(("media",)), evidence=ev_,
                    why_not=[WhyNot(campaign_id="KMP-029", bullets=["Podobna przynęta rządowa, ale brak wspólnej infrastruktury i kitu."])],
                    alpha=0.05, conformal_tau=0.55, set=[], calibration={"target": 0.05, "achieved": 0.041, "n_cal": 412}, model_version="engine@mock")


def decision_confirm() -> Decision:
    """INC-24866 (kelvaro.live): two campaigns of the same operator in the conformal set -> ambiguous (board 12)."""
    d = decision_24817().model_copy(deep=True)
    d.incident_id, d.decision, d.campaign_id, d.candidate_campaign_id = "INC-24866", "ambiguous", None, "KMP-034"
    d.score, d.p, d.margin, d.set = 3.9, 0.52, 0.1, ["KMP-034", "KMP-017"]
    d.scores = [CampaignScore(campaign_id="KMP-034", score=3.9, score_operator=6.8, p=0.52, p_value=0.21, in_set=True),
                CampaignScore(campaign_id="KMP-017", score=3.7, score_operator=6.8, p=0.42, p_value=0.16, in_set=True)]
    d.runner_up = RunnerUp(campaign_id="KMP-017", score=3.7, p=0.42, same_operator=True)
    d.evidence = [E_CAPI, E_KIT, E_CF]
    return d


def decision_insufficient() -> Decision:
    """INC-24920 (selqueno.live, 502): page down at capture -> insufficient (board 13)."""
    return Decision(incident_id="INC-24920", decision="insufficient", score=0.0, p=0.0, coverage=0.12,
                    layers=[LayerCoverage(layer=l, state="error" if l in ("content", "visual", "persons", "ad") else "missing" if l != "tracking" else "partial",
                                          reason="serwer odpowiada 502" if l in ("content", "visual") else None) for l in LAYERS],
                    evidence=[ev("infra", "domain", "selqueno.live", "domena selqueno.live", "L", 0.0, 1, "notariusz", state="missing")],
                    set=[], model_version="engine@mock")


def decisions() -> dict[str, Decision]:
    return {"INC-24817": decision_24817(), "INC-24901": decision_new(), "INC-24866": decision_confirm(), "INC-24920": decision_insufficient()}


def generic_decision(summary: IncidentSummary) -> Decision:
    cid = summary.campaign_id
    base = decision_24817().model_copy(deep=True)
    base.incident_id, base.campaign_id = summary.id, cid
    base.p = summary.p or 0.9
    base.scores[0].campaign_id = cid
    base.set = [cid]
    base.operator_id, base.operation_id = SPEC[cid]["op"], SPEC[cid]["opn"]
    base.evidence = [E_CAPI, E_KIT, E_TPL] if cid == "KMP-017" else [
        ev(r.layer, r.field, r.value, r.display or r.value, r.strength, 2.0, max(6, r.members_with), r.bot) for r in dna_rows(cid)[:3]]
    base.why_not, base.runner_up, base.adjudicator = [], None, None
    return base


# --------------------------------------------------------------------------------------------- links
def link(a: str, b: str) -> LinkExplanation:
    if b == "KMP-034":
        return LinkExplanation(
            a=a, b=b, score_campaign=3.6, score_operator=6.4, p=0.41, decision="not_linked", shared_level="L3", operator_id="OP-03",
            layers_independent=2, layers_required=2, coverage=0.78,
            summary="Ten sam operator (OP-03), ale inna kampania: wspólne tylko tracking i kit.",
            contributions=[{"layer": "tracking", "value": 3.1}, {"layer": "kit", "value": 2.7}],
            evidence=[E_CAPI, E_KIT], missing=[E_ASR],
            conflicts=[ev("content", "headline_template", TPL_V2, "szablon nagłówka", "H", -1.8, 22, "czytelnik", state="conflict",
                          sides={"a": TPL_V2, "b": "Glikonor — cud na cukrzycę"}),
                       ev("persons", "face_identity", "Jan Kowalski", "persona", "M", -0.9, 61, "czytelnik", state="conflict",
                          sides={"a": "Jan Kowalski", "b": "dr Piotr Wiśniewski"})],
            zeroed=[E_CF], counterfactuals=[Counterfactual(change="gdyby wspólna była persona", p_new=0.77, decision_new="confirm")])
    return LinkExplanation(
        a=a, b=b, score_campaign=11.4, score_operator=11.4, p=0.94, decision="linked", shared_level="L2", operator_id="OP-03",
        layers_independent=5, layers_required=2, coverage=0.78, summary="Dołącza do KMP-017: 5 niezależnych warstw zgodnych, p = 0.94.",
        contributions=[{"layer": "tracking", "value": 3.1}, {"layer": "kit", "value": 2.7}, {"layer": "content", "value": 2.2},
                       {"layer": "infra", "value": 1.4}, {"layer": "visual", "value": 0.9}, {"layer": "persons", "value": 0.8},
                       {"layer": "ad", "value": 0.3}],
        evidence=[E_CAPI, E_KIT, E_TPL, E_CERT, E_PHASH, E_PERSON, E_DECOY], missing=[E_ASR, E_RDAP], conflicts=[], zeroed=[E_CF],
        counterfactuals=[Counterfactual(change="bez dowodu CAPI", p_new=0.81, decision_new="assign"),
                         Counterfactual(change="bez CAPI i relay kit", p_new=0.52, decision_new="confirm"),
                         Counterfactual(change="tylko warstwa infrastruktury", p_new=0.12, decision_new="new")],
        adjudicator=Adjudication(model="qwen/qwen3.8-27b", verdict="same", confidence=0.93, rationale=["Ta sama bramka CAPI", "Ten sam szablon V2"]))


def template_diff() -> TemplateDiff:
    a = [Tok(t="PILNE:", kind="same"), Tok(t="Jan Kowalski", kind="slot", slot="PER"), Tok(t="przerywa", kind="same"),
         Tok(t="milczenie", kind="same"), Tok(t="po", kind="same"), Tok(t="napaści", kind="same")]
    b = [Tok(t="PILNE:", kind="same"), Tok(t="Anna Nowak", kind="slot", slot="PER"), Tok(t="przerywa", kind="same"),
         Tok(t="milczenie", kind="same"), Tok(t="po", kind="same"), Tok(t="napaści", kind="same"), Tok(t="w", kind="ins"),
         Tok(t="Krakowie", kind="ins", slot="MIASTO")]
    return TemplateDiff(
        text={"a_tokens": a, "b_tokens": b}, dom={"matched": ["div.article > h1", "div.comments > ul.fake"], "differing": ["div.cta"]},
        assets=[{"url": "https://morvanta.click/a/logo.svg", "sha256": "9a1f…c0", "same": True, "third_party": False},
                {"url": "https://cdn.example.test/lib.js", "sha256": "77be…12", "same": True, "third_party": True}],
        visual={"phash_distance": 4, "regions": [{"x": 0.05, "y": 0.1, "w": 0.9, "h": 0.12}]},
        metrics={"minhash": 0.91, "dom_shingles": 0.88, "phash_delta": 4, "shared_assets": [11, 14]})


def evidence_value(type_: str, value: str) -> EvidenceValue:
    known = {("tracking", CAPI): 47, ("kit", KIT): 58, ("content", TPL_V2): 22, ("persons", "Jan Kowalski"): 61}
    df = known.get((type_, value), 1 + h(value) % 40)
    rnd = random.Random(h(value) % 10000)
    weekly = [rnd.randint(0, max(1, df // 5)) for _ in range(8)]
    camps = [{"id": "KMP-017", "n": max(1, int(df * 0.8))}] + ([{"id": "KMP-034", "n": df - int(df * 0.8)}] if df > 5 else [])
    return EvidenceValue(type=type_, field=type_, value=value, df=df, N=N, idf=idf(df), first_seen="2026-09-30", last_seen="2026-11-21",
                         weekly=weekly, campaigns=camps, operator_hint="OP-03 «Kestrel»" if df > 5 else None,
                         incidents=incident_summaries()[:5])
