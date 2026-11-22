"""Campaign dossier for Act: everything a takedown package lists (ads, advertisers, domains, shared evidence).

    load_campaign(campaign_id) -> dict
      KMP-017 (and other ids of the fictional BRIEF universe)  -> deterministic FICTIONAL dossier (mock mode / demo)
      LAB-<x> | A | KMP-A                                        -> hand-labelled campaign (experiments/labels*.yaml) + DB
      KMP-<n> / engine code in the DB `campaigns` table          -> current campaign_memberships + DB
    Domains promoted by White Rabbit (data/investigations/promotions.jsonl) are merged in ("w tym N ze śledztwa").
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from trop.config import settings

FICTIONAL = {"KMP-017"}
EVIDENCE_TYPES = ("kit_tenant", "fb_pixel", "capi_gateway", "lander_id", "headline_template", "clickbait_template",
                  "ns_set", "registration_batch", "cert_batch", "asset_sha256", "kit_endpoint", "lander_path",
                  "url_param_schema", "google_tag", "person", "brand")
STRENGTH = {"kit_tenant": "H", "fb_pixel": "H", "capi_gateway": "H", "lander_id": "H", "headline_template": "H",
            "asset_sha256": "H", "google_tag": "H", "clickbait_template": "M", "ns_set": "M", "registration_batch": "M",
            "cert_batch": "M", "kit_endpoint": "M", "lander_path": "M", "url_param_schema": "M", "person": "M", "brand": "L"}
LAYER = {"kit_tenant": "kit", "lander_id": "kit", "asset_sha256": "kit", "kit_endpoint": "kit", "lander_path": "kit",
         "url_param_schema": "kit", "fb_pixel": "tracking", "capi_gateway": "tracking", "google_tag": "tracking",
         "headline_template": "content", "clickbait_template": "ad", "ns_set": "infra", "registration_batch": "infra",
         "cert_batch": "infra", "person": "persons", "brand": "content"}


class CampaignNotFound(KeyError):
    pass


def load_campaign(campaign_id: str) -> dict[str, Any]:
    cid = campaign_id.strip()
    if cid in FICTIONAL:
        d = fictional_kmp017()
    else:
        d = _from_db(cid)
    _merge_promotions(d)
    from .pl import polish_dossier
    polish_dossier(d)
    d["counts"] = {"ads": len(d["ads"]), "advertisers": len(d["advertisers"]), "domains": len(d["domains"]),
                   "evidence_items": len(d["evidence"]), "incidents": len(d["incidents"]),
                   "certpl_listed": sum(1 for x in d["domains"] if x.get("on_certpl"))}
    return d


# ============================================================================== real data (labels / DB)
def _labels_members(cid: str) -> tuple[str, list[str], dict]:
    import yaml

    from trop.agent.db import experiments_dir
    letter = cid.split("-")[-1] if cid.upper().startswith(("LAB-", "KMP-")) else cid
    exp = experiments_dir()
    if exp is None:
        return letter, [], {}
    refs, meta = [], {}
    for fn, prefix in (("labels.yaml", "sample_v1/"), ("labels_dane.yaml", "dane/")):
        f = exp / fn
        if not f.is_file():
            continue
        y = yaml.safe_load(f.read_text()) or {}
        for k, v in (y.get("incidents") or {}).items():
            if (v or {}).get("campaign") == letter:
                refs.append(prefix + (k[1:] if prefix == "dane/" and k.startswith("d") else k))
        meta = meta or ((y.get("campaigns") or {}).get(letter) or {})
    return letter, refs, meta


def _from_db(cid: str) -> dict[str, Any]:
    from trop.agent.db import PG
    if PG.conn() is None:
        raise CampaignNotFound(f"{cid}: database unavailable")
    ids: list[int] = []
    name, narrative, vertical, persons = cid, "", None, []
    rows = PG.q("SELECT id, code, name, narrative, vertical FROM campaigns WHERE code = %s OR 'KMP-' || id = %s", (cid, cid))
    if rows:
        c = rows[0]
        name, narrative, vertical = c["name"] or cid, c["narrative"] or "", c["vertical"]
        ids = [r["incident_id"] for r in PG.q("SELECT incident_id FROM campaign_memberships WHERE campaign_id = %s "
                                               "AND valid_to IS NULL AND decision IN ('assign','confirm','manual')", (c["id"],))]
    if not ids:
        letter, refs, meta = _labels_members(cid)
        if refs:
            ids = [r["id"] for r in PG.q("SELECT id FROM incidents WHERE source_ref = ANY(%s)", (refs,))]
            name = meta.get("name") or f"Kampania {letter}"
            vertical = meta.get("vertical")
            persons = [p for p in (meta.get("impersonates") or []) if " " in p]
            narrative = meta.get("name") or ""
    if not ids:
        raise CampaignNotFound(cid)
    incs = PG.q("""SELECT i.id, i.source_ref, i.entry_url, coalesce(i.final_etld1, i.entry_etld1) AS domain, i.title,
                          i.observed_at, i.ad_id, s.name AS source FROM incidents i JOIN sources s ON s.id = i.source_id
                    WHERE i.id = ANY(%s) ORDER BY i.observed_at""", (ids,))
    ads = PG.q("""SELECT a.id, a.platform, a.library_id, a.body, a.display_link, a.link_url, a.delivery_start, a.snapshot_url,
                         adv.name AS advertiser, adv.platform_id AS page_id, i.id AS incident_id
                    FROM incidents i JOIN ads a ON a.id = i.ad_id LEFT JOIN advertisers adv ON adv.id = a.advertiser_id
                   WHERE i.id = ANY(%s)""", (ids,))
    doms = sorted({r["domain"] for r in incs if r["domain"]})
    dinfo = {r["etld1"]: r for r in PG.q(
        """SELECT DISTINCT ON (d.etld1) d.etld1, d.registrar, d.created_at, d.nameservers, d.first_cert_at, d.certpl_listed_at
             FROM obs_domains d WHERE d.etld1 = ANY(%s) ORDER BY d.etld1, d.enriched_at DESC NULLS LAST""", (doms,))}
    ev = PG.q("""SELECT o.type, o.value, o.display, count(DISTINCT io.incident_id) AS n, max(o.df_incidents) AS df
                   FROM incident_observables io JOIN observables o ON o.id = io.observable_id
                  WHERE io.incident_id = ANY(%s) AND o.type = ANY(%s) AND NOT o.noise
                  GROUP BY o.type, o.value, o.display HAVING count(DISTINCT io.incident_id) >= 2
                  ORDER BY count(DISTINCT io.incident_id) DESC, max(o.df_incidents) ASC LIMIT 60""", (ids, list(EVIDENCE_TYPES)))
    n = len(ids)
    evidence, per_type = [], {}
    cap = {"asset_sha256": 2, "lander_path": 1, "kit_endpoint": 2}
    for e in sorted(ev, key=lambda e: (EVIDENCE_TYPES.index(e["type"]), -e["n"], e["df"] or 0)):
        if per_type.get(e["type"], 0) >= cap.get(e["type"], 3):
            continue
        per_type[e["type"]] = per_type.get(e["type"], 0) + 1
        evidence.append({"type": LAYER.get(e["type"], "kit"), "field": e["type"], "value": e["value"],
                         "display": _display(e["type"], e["value"], e["display"]), "strength": STRENGTH.get(e["type"], "M"),
                         "members_with": e["n"], "members_total": n, "df": e["df"]})
    adv: dict[str, dict] = {}
    for a in ads:
        k = a["advertiser"] or "(nieznany)"
        adv.setdefault(k, {"name": k, "page_id": a["page_id"], "platform": a["platform"], "n_ads": 0})["n_ads"] += 1
    return {
        "id": cid, "name": name, "narrative": narrative, "vertical": vertical, "fictional": False, "persons": persons,
        "brands": [], "operator_id": None,
        "incidents": [{"id": f"INC-{r['id']}", "ref": r["source_ref"], "domain": r["domain"], "url": r["entry_url"],
                       "title": r["title"], "captured_at": str(r["observed_at"] or "")[:19], "source": r["source"]} for r in incs],
        "ads": [{"platform": a["platform"], "library_id": a["library_id"], "advertiser": a["advertiser"], "page_id": a["page_id"],
                 "text": (a["body"] or "")[:300], "display_link": a["display_link"], "landing_url": a["link_url"],
                 "library_url": f"https://www.facebook.com/ads/library/?id={a['library_id']}" if a["library_id"] else None,
                 "start": str(a["delivery_start"] or "")[:10] or None, "incident_id": f"INC-{a['incident_id']}"} for a in ads],
        "advertisers": sorted(adv.values(), key=lambda x: -x["n_ads"]),
        "domains": [{"fqdn": d, "registrar": (dinfo.get(d) or {}).get("registrar"),
                     "registered_at": str((dinfo.get(d) or {}).get("created_at") or "")[:19] or None,
                     "cert_issued_at": str((dinfo.get(d) or {}).get("first_cert_at") or "")[:19] or None,
                     "ns": list((dinfo.get(d) or {}).get("nameservers") or []),
                     "on_certpl": bool((dinfo.get(d) or {}).get("certpl_listed_at")), "source": "campaign",
                     "incidents": [f"INC-{r['id']}" for r in incs if r["domain"] == d],
                     "urls": [r["entry_url"] for r in incs if r["domain"] == d and r["entry_url"]][:3]} for d in doms],
        "evidence": evidence,
    }


def _display(typ: str, value: str, display: str | None) -> str:
    names = {"kit_tenant": "konto (tenant) kitu", "fb_pixel": "piksel FB", "capi_gateway": "bramka CAPI", "lander_id": "lander",
             "headline_template": "szablon nagłówka", "clickbait_template": "szablon reklamy", "ns_set": "para NS",
             "registration_batch": "partia rejestracji", "cert_batch": "partia certyfikatów", "kit_endpoint": "endpoint kitu",
             "lander_path": "ścieżka kitu", "url_param_schema": "gramatyka URL", "google_tag": "tag Google"}
    if typ == "asset_sha256":
        base = (display or "").rstrip("/").rsplit("/", 1)[-1][:40] if display and "/" in display else "plik"
        return f"wspólny plik {base} (sha256 {value[:10]}…)"
    v = value if len(value) <= 70 else value[:67] + "…"
    return f"{names.get(typ, typ)} {v}"


def _merge_promotions(d: dict) -> None:
    p = Path(settings.data_dir) / "investigations" / "promotions.jsonl"
    if not p.is_file():
        return
    have = {x["fqdn"] for x in d["domains"]}
    for ln in p.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if r.get("campaign_id") != d["id"] or r.get("kind") != "domain" or r.get("label") in have:
            continue
        have.add(r["label"])
        d["domains"].append({"fqdn": r["label"], "source": "investigation", "investigation_id": r.get("investigation_id"),
                             "on_certpl": bool(r.get("certpl")), "evidence": [e.get("type") for e in r.get("evidence", [])][:5],
                             "level": r.get("level")})


# ============================================================================== fictional KMP-017 (BRIEF.md)
def fictional_kmp017() -> dict[str, Any]:
    """Deterministic FICTIONAL dossier: 46 ads, 11 advertisers, 29 domains (19 + 10 from the agent run), 5 on CERT PL."""
    rnd = random.Random(17)
    base = datetime(2026, 11, 21, 8, 50, tzinfo=UTC)
    advertisers = ["Ogród i Pasja 24", "Puzzle Mania PL", "Lena Kwiatkowska Sklep", "Domowe Okazje 365", "Kwiaciarnia Pod Lipą",
                   "Rowerowy Zakątek", "Akwarystyka Nemo", "Moda Basi", "Słodkie Wypieki Ewy", "Zoo Market Pruszków",
                   "Antyki u Marka"]
    domains19 = ["morvanta.click", "orvinta.click", "plessuro.live", "velmoria.click", "trastino.live", "quorvex.click",
                 "ambrelio.live", "dunvarra.click", "selqueno.live", "tranvello.click", "brevanto.click", "corlenta.live",
                 "fenmaro.click", "garvessa.live", "holvento.click", "jastrino.live", "lumbrecia.click", "marvessa.live",
                 "norvaldo.click"]
    agent10 = ["kelmora.click", "dravento.live", "vastrino.live", "sulvane.click", "morquel.live", "pentaro.click",
               "ombrela.click", "trevanio.live", "quilmora.click", "zorvento.live"]
    listed = {"velmoria.click", "trastino.live", "quorvex.click", "dunvarra.click", "ambrelio.live"}
    tonight = {"plessuro.live": "2026-11-21T00:47:00", "orvinta.click": "2026-11-21T01:12:00", "morvanta.click": "2026-11-21T02:31:00"}
    doms = []
    for i, d in enumerate(domains19 + agent10):
        reg = base - timedelta(days=3 + i % 12, hours=rnd.randint(0, 3))
        doms.append({"fqdn": d, "registrar": "R-114 (anonimizowany)", "registered_at": reg.isoformat()[:19],
                     "cert_issued_at": tonight.get(d) or (reg + timedelta(minutes=34)).isoformat()[:19],
                     "ns": ["ada.ns.cloudflare.com", "rob.ns.cloudflare.com"], "on_certpl": d in listed,
                     "source": "investigation" if d in agent10 else "campaign",
                     "investigation_id": "INV-DEMO" if d in agent10 else None,
                     "ips": ["203.0.113.10"], "origin": "198.51.100.23 (AS64500)",
                     "urls": [f"https://{d}/?utm_source=fb&utm_medium=paid&utm_campaign=kd{i:03d}&utm_content=v{i % 3 + 1}"
                              f"&utm_term=pl&utm_visit=0193b2c1-{i:04x}-7000-8000-00000000{i:04x}"]})
    ads, n = [], 0
    weights = [8, 7, 6, 5, 4, 4, 3, 3, 2, 2, 2]
    headlines = ["PILNE: Jan Kowalski przerywa milczenie po napaści…", "«Wiem, kto to zrobił»: atak na Annę Nowak",
                 "PILNE: Tomasz Lewandowski przerywa milczenie po napaści…"]
    for a_i, (adv, w) in enumerate(zip(advertisers, weights)):
        for _ in range(w):
            n += 1
            d = doms[(n * 7) % 29]["fqdn"]
            start = base - timedelta(days=rnd.randint(0, 13), hours=rnd.randint(0, 23))
            ads.append({"platform": "meta", "library_id": f"990000{n:010d}", "advertiser": adv, "page_id": f"61000000{a_i:04d}",
                        "text": headlines[n % 3], "display_link": "OKAZJE-DNIA.COM", "landing_url": f"https://{d}/",
                        "library_url": f"https://www.facebook.com/ads/library/?id=990000{n:010d}",
                        "start": start.date().isoformat(), "incident_id": f"INC-{24700 + n}", "decoy": n % 4 == 0})
    adv = [{"name": a, "page_id": f"61000000{i:04d}", "platform": "meta", "n_ads": w} for i, (a, w) in enumerate(zip(advertisers, weights))]
    ev = [
        {"type": "tracking", "field": "capi_gateway", "value": "cg-7f3a91e0.ecs.eu-west-1.on.aws/events",
         "display": "bramka CAPI cg-7f3a…", "strength": "H", "members_with": 46, "members_total": 46, "df": 47},
        {"type": "kit", "field": "kit_endpoint", "value": "/api/v2/relay/lead/{uuid}/", "display": "kit relay v1 (relay/lead)",
         "strength": "H", "members_with": 46, "members_total": 46, "df": 58},
        {"type": "kit", "field": "asset_sha256", "value": hashlib.sha256(b"fictional KMP-017 relay/lead kit bundle").hexdigest(),
         "display": "plik kitu relay.js (sha256)", "strength": "H", "members_with": 46, "members_total": 46, "df": 58},
        {"type": "content", "field": "headline_template", "value": "PILNE: {PER} przerywa milczenie po napaści…",
         "display": "szablon „PILNE: {PER}…”", "strength": "H", "members_with": 22, "members_total": 46, "df": 22},
        {"type": "content", "field": "headline_template", "value": "«Wiem, kto to zrobił»: atak na {PER}",
         "display": "szablon „«Wiem, kto to zrobił»…”", "strength": "H", "members_with": 19, "members_total": 46, "df": 19},
        {"type": "infra", "field": "cert_batch", "value": "LE R11 00:00–03:00 UTC", "display": "nocne partie certyfikatów LE R11",
         "strength": "M", "members_with": 29, "members_total": 29, "df": 31},
        {"type": "kit", "field": "url_param_schema", "value": "utm×5 + utm_visit=uuidv7", "display": "gramatyka URL utm×5 + utm_visit",
         "strength": "M", "members_with": 46, "members_total": 46, "df": 61},
    ]
    return {"id": "KMP-017", "name": "Zamach", "narrative": "Fałszywy portal «Kurier Dnia» → „inwestycja”", "vertical": "investment",
            "fictional": True, "operator_id": "OP-03", "persons": ["Jan Kowalski", "Anna Nowak", "Tomasz Lewandowski"],
            "brands": ["Kurier Dnia"],
            "incidents": [{"id": a["incident_id"], "domain": a["landing_url"].split("/")[2],
                           "url": next(x["urls"][0] for x in doms if x["fqdn"] == a["landing_url"].split("/")[2]),
                           "title": a["text"], "captured_at": a["start"], "source": "hunter"} for a in ads],
            "ads": ads, "advertisers": adv, "domains": doms, "evidence": ev}
