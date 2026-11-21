"""Detection rules per campaign (urlscan query, URL regex, HTML signature) and "Testuj na zbiorze".

    rules_for(dossier) -> list[Rule]
    test_rule(kind, body, campaign_id=None, dossier=None) -> RuleTest

Test set = our corpus (DB incidents: entry URL, title, headline, observables) + a fixed list of benign Polish pages.
tp = hits on the campaign's own incidents, benign_hits = hits on the benign list, needs_review = other hits (unlabelled
incidents: possibly the same campaign, a human decides). precision = tp / (tp + benign_hits).
For a fictional campaign the corpus is its own fictional incidents (never mixed with real data).
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from trop.schema import Rule, RuleTest

BENIGN = [
    ("https://www.gazeta.pl/0,0.html", "Gazeta.pl — Wiadomości, Sport, Kobieta, Moto"),
    ("https://wiadomosci.gazeta.pl/wiadomosci/0,114871.html", "Wiadomości z kraju — Gazeta.pl"),
    ("https://www.onet.pl/", "Onet — Jesteś na bieżąco"), ("https://wiadomosci.onet.pl/kraj", "Kraj — Wiadomości Onet"),
    ("https://www.wp.pl/", "Wirtualna Polska — Wszystko co ważne"), ("https://www.interia.pl/", "Interia — Polska i świat"),
    ("https://tvn24.pl/", "TVN24 — najnowsze informacje z kraju i ze świata"), ("https://www.polsatnews.pl/", "Polsat News"),
    ("https://www.bankier.pl/", "Bankier.pl — finanse, giełda, waluty"), ("https://www.money.pl/", "Money.pl — pieniądze, biznes"),
    ("https://businessinsider.com.pl/", "Business Insider Polska"), ("https://www.rp.pl/", "Rzeczpospolita"),
    ("https://www.pb.pl/", "Puls Biznesu"), ("https://www.parkiet.com/", "Parkiet — giełda, inwestycje"),
    ("https://www.gpw.pl/", "Giełda Papierów Wartościowych w Warszawie"), ("https://www.knf.gov.pl/", "Komisja Nadzoru Finansowego"),
    ("https://www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne", "Lista ostrzeżeń publicznych KNF"),
    ("https://www.nbp.pl/", "Narodowy Bank Polski"), ("https://www.gov.pl/web/cyfryzacja", "Ministerstwo Cyfryzacji — Portal Gov.pl"),
    ("https://cert.pl/", "CERT Polska"), ("https://www.nask.pl/", "NASK — Państwowy Instytut Badawczy"),
    ("https://incydent.cert.pl/", "Zgłoś incydent — CERT Polska"), ("https://www.pkobp.pl/", "PKO Bank Polski"),
    ("https://www.mbank.pl/indywidualny/", "mBank — bank internetowy"), ("https://www.ing.pl/", "ING Bank Śląski"),
    ("https://www.santander.pl/", "Santander Bank Polska"), ("https://www.allegro.pl/", "Allegro — atrakcyjne ceny"),
    ("https://www.olx.pl/", "OLX — ogłoszenia lokalne"), ("https://www.inpost.pl/", "InPost — paczkomaty i kurier"),
    ("https://www.orlen.pl/pl", "ORLEN"), ("https://www.zus.pl/", "ZUS"), ("https://www.podatki.gov.pl/", "Podatki.gov.pl"),
    ("https://pl.wikipedia.org/wiki/Oszustwo", "Oszustwo — Wikipedia, wolna encyklopedia"),
    ("https://www.facebook.com/ads/library/", "Biblioteka reklam Meta"), ("https://www.youtube.com/", "YouTube"),
    ("https://www.rmf24.pl/", "RMF24 — fakty"), ("https://www.tvp.info/", "TVP Info"), ("https://www.fakt.pl/", "Fakt — wiadomości"),
    ("https://www.pudelek.pl/", "Pudelek"), ("https://www.sport.pl/", "Sport.pl"),
    ("https://www.bankier.pl/wiadomosc/Jak-inwestowac-w-ETF", "Jak inwestować w ETF? Poradnik — Bankier.pl"),
    ("https://www.money.pl/gielda/", "Giełda — notowania — Money.pl"),
]


def _norm_benign() -> list[dict]:
    return [{"id": f"BENIGN-{i}", "url": u, "title": t, "domain": urlsplit(u).hostname, "hashes": set(), "benign": True}
            for i, (u, t) in enumerate(BENIGN)]


# ============================================================================== generation
def _value_shape(v: str) -> str:
    if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", v, re.I):
        return "[0-9a-f-]{36}"
    if re.fullmatch(r"[A-Za-z0-9]+", v):
        return "[A-Za-z0-9]{%d}" % len(v) if len(v) >= 6 else "[A-Za-z0-9]+"
    return "[^&]+"


def url_regex_for(d: dict[str, Any]) -> str | None:
    urls = [u for x in d["domains"] for u in x.get("urls", [])] + [i.get("url") for i in d["incidents"] if i.get("url")]
    urls = [u for u in urls if u and "?" in u]
    tlds = sorted({x["fqdn"].rsplit(".", 1)[-1] for x in d["domains"]})
    labels = [x["fqdn"].rsplit(".", 1)[0] for x in d["domains"]]
    if not labels:
        return None
    lo, hi = min(map(len, labels)), max(map(len, labels))
    host = r"[a-z0-9-]{%d,%d}\.(?:%s)" % (max(3, lo - 1), hi + 1, "|".join(map(re.escape, tlds)))
    if not urls:
        return r"^https?://" + host + r"/"
    schemas = Counter(tuple(k for k, _ in parse_qsl(urlsplit(u).query)) for u in urls)
    keys, _ = schemas.most_common(1)[0]
    ex = next(u for u in urls if tuple(k for k, _ in parse_qsl(urlsplit(u).query)) == keys)
    vals = dict(parse_qsl(urlsplit(ex).query))
    shapes = {k: Counter(_value_shape(dict(parse_qsl(urlsplit(u).query)).get(k, "")) for u in urls).most_common(1)[0][0] for k in keys}
    q = "&".join(f"{re.escape(k)}={shapes.get(k) or _value_shape(vals[k])}" for k in keys)
    return r"^https?://" + host + r"/\?" + q if q else r"^https?://" + host + r"/"


def html_signature_for(d: dict[str, Any]) -> str | None:
    tpl = next((e["value"] for e in d["evidence"] if e["field"] in ("headline_template", "clickbait_template")), None)
    if tpl:
        parts = [re.escape(p.strip()) for p in re.split(r"\{[A-Z]+\}", tpl)]
        return r"(?i)" + r".{2,60}?".join(p for p in parts if p)
    kit = next((e["value"] for e in d["evidence"] if e["field"] in ("kit_endpoint", "lander_path")), None)
    return re.escape(kit).replace(r"\{uuid\}", "[0-9a-f-]{36}") if kit else None


def urlscan_query_for(d: dict[str, Any]) -> str:
    h = sorted((e for e in d["evidence"] if e["field"] == "asset_sha256"), key=lambda e: e.get("df") or 0)
    if h:
        return f"hash:{h[0]['value']}"
    kit = next((e["value"] for e in d["evidence"] if e["field"] == "kit_endpoint"), None)
    if kit:
        return 'page.url:"' + kit.split("{")[0] + '"'
    return "domain:(" + " OR ".join(x["fqdn"] for x in d["domains"][:25]) + ")"


def rules_for(d: dict[str, Any]) -> list[Rule]:
    out = [Rule(id=f"RUL-{d['id']}-urlscan", campaign_id=d["id"], kind="urlscan", body=urlscan_query_for(d))]
    if (rx := url_regex_for(d)):
        out.append(Rule(id=f"RUL-{d['id']}-url", campaign_id=d["id"], kind="url_regex", body=rx))
    if (sig := html_signature_for(d)):
        out.append(Rule(id=f"RUL-{d['id']}-html", campaign_id=d["id"], kind="html_signature", body=sig))
    return out


# ============================================================================== test on the dataset
def _corpus_db() -> list[dict]:
    from trop.agent.db import PG
    if PG.conn() is None:
        return []
    rows = PG.q("""SELECT i.id, i.entry_url, coalesce(i.final_etld1, i.entry_etld1) AS domain,
                          concat_ws(' ', i.title, i.headline, i.headline_template) AS title,
                          array(SELECT o.value FROM incident_observables io JOIN observables o ON o.id = io.observable_id
                                 WHERE io.incident_id = i.id AND o.type = 'asset_sha256') AS hashes
                     FROM incidents i WHERE i.duplicate_of IS NULL""")
    return [{"id": f"INC-{r['id']}", "url": r["entry_url"] or "", "title": r["title"] or "", "domain": r["domain"] or "",
             "hashes": set(r["hashes"] or [])} for r in rows]


def _corpus_fictional(d: dict) -> list[dict]:
    """The fictional campaign's own incidents; every member loads the campaign's shared asset files."""
    shared = {e["value"] for e in d["evidence"] if e["field"] == "asset_sha256" and e["members_with"] == e["members_total"]}
    return [{"id": i["id"], "url": i.get("url") or "", "title": i.get("title") or "", "domain": i.get("domain") or "",
             "hashes": set(shared)} for i in d["incidents"]]


def _urlscan_match(q: str, it: dict) -> bool:
    terms = [t.strip() for t in re.split(r"\s+OR\s+", q.strip().strip("()")) if t.strip()]
    for t in terms:
        m = re.match(r'^(hash|domain|page\.domain|page\.title|page\.url):\(?"?([^"]*?)"?\)?$', t)
        if not m:
            if it["domain"] == t.strip("()").lower():
                return True
            continue
        f, v = m.group(1), m.group(2).lower()
        if f == "hash" and v in it["hashes"]:
            return True
        if f in ("domain", "page.domain") and (it["domain"] == v or it["domain"].endswith("." + v)):
            return True
        if f == "page.title" and v in it["title"].lower():
            return True
        if f == "page.url" and v in it["url"].lower():
            return True
    return False


def _matcher(kind: str, body: str):
    if kind == "urlscan":
        return lambda it: _urlscan_match(body, it)
    rx = re.compile(body)
    if kind == "url_regex":
        return lambda it: bool(it["url"] and rx.search(it["url"]))
    if kind == "html_signature":
        return lambda it: bool(rx.search(it["title"]) or rx.search(it["url"]))
    raise ValueError("yara rules need page bodies; not testable on this dataset")


def test_rule(kind: str, body: str, campaign_id: str | None = None, dossier: dict | None = None) -> RuleTest:
    d = dossier
    if d is None and campaign_id:
        from .campaign import load_campaign
        try:
            d = load_campaign(campaign_id)
        except Exception:  # noqa: BLE001
            d = None
    corpus = _corpus_fictional(d) if d and d.get("fictional") else _corpus_db()
    members = {i["id"] for i in (d or {}).get("incidents", [])}
    member_domains = {x["fqdn"] for x in (d or {}).get("domains", [])}
    benign = _norm_benign()
    try:
        match = _matcher(kind, body)
    except (re.error, ValueError):
        return RuleTest(hits=0, tp=0, needs_review=0, benign_hits=0, benign_total=len(benign), precision=0.0)
    tp = rev = 0
    for it in corpus:
        if match(it):
            if it["id"] in members or it["domain"] in member_domains:
                tp += 1
            else:
                rev += 1
    bh = sum(1 for it in benign if match(it))
    hits = tp + rev + bh
    return RuleTest(hits=hits, tp=tp, needs_review=rev, benign_hits=bh, benign_total=len(benign),
                    precision=round(tp / (tp + bh), 3) if (tp + bh) else 0.0)
