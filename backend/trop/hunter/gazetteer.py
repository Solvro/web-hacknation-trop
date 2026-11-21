"""Persons / brands gazetteer (ported from scrapers/util/text.py) and the Polish lure phrases the Hunter searches for."""
from __future__ import annotations

import re

PERSONS = {
    "Rafał Brzoska": "businessman", "Krzysztof Stanowski": "journalist", "Tomasz Sekielski": "journalist",
    "Monika Olejnik": "journalist", "Adam Glapiński": "central_banker", "Robert Lewandowski": "athlete",
    "Anna Lewandowska": "celebrity", "Donald Tusk": "politician", "Andrzej Duda": "politician",
    "Karol Nawrocki": "politician", "Rafał Trzaskowski": "politician", "Mateusz Morawiecki": "politician",
    "Sławomir Mentzen": "politician", "Szymon Hołownia": "politician", "Kuba Wojewódzki": "celebrity",
    "Martyna Wojciechowska": "journalist", "Ewa Chodakowska": "celebrity", "Dorota Wellman": "journalist",
    "Marcin Prokop": "journalist", "Piotr Kraśko": "journalist", "Michał Sołowow": "businessman",
    "Dominika Kulczyk": "businesswoman", "Zbigniew Jakubas": "businessman", "Leszek Czarnecki": "businessman",
    "Jerzy Owsiak": "celebrity", "Magda Gessler": "celebrity", "Krzysztof Ibisz": "celebrity",
    "Justyna Kowalczyk": "athlete", "Iga Świątek": "athlete", "Agnieszka Holland": "celebrity",
}
BRANDS = ["Gazeta.pl", "Onet", "Wirtualna Polska", "WP.pl", "Interia", "TVN24", "TVN", "Polsat", "TVP", "Fakt",
          "Rzeczpospolita", "Business Insider", "Forbes", "InPost", "NBP", "PKO BP", "mBank", "Pekao", "ING",
          "Santander", "Allegro", "Orlen", "PGE", "ZUS", "Biedronka", "Lidl", "Amazon", "Revolut", "Facebook"]

# Lure phrases from our campaign templates (clickbait headline templates of the organizer sample, generalised)
LURE_PHRASES = ["PILNE", "Temat, o którym mówi cała Polska", "Wszyscy o tym rozmawiają", "UWAGA! Nowa informacja",
                "przerywa milczenie", "Nie uwierzysz", "Sprawdź, zanim zniknie", "Niesamowita historia z wczoraj",
                "Szokujące nagranie", "Zarabiaj w domu", "Inwestycja, która zmienia życie"]
LURE_RE = re.compile("|".join(re.escape(p.lower()) for p in LURE_PHRASES + ["ostatniej chwili", "zniknie z sieci"]))


def _stem(w: str) -> str:
    return w[:-1] if w[-1].lower() in "aeiouyąę" and len(w) > 4 else w


_PAT = []
for _n, _r in PERSONS.items():
    _f, *_rest = _n.split()
    _PAT.append((_n, _r, re.compile(rf"\b{re.escape(_stem(_f))}\w{{0,4}}\s+{re.escape(_stem(_rest[-1]))}\w{{0,4}}\b", re.U)))


def find_persons(text: str) -> list[str]:
    return sorted({n for n, _, p in _PAT if p.search(text or "")})


def find_brands(text: str) -> list[str]:
    low, out = (text or "").lower(), set()
    for b in BRANDS:
        if len(b) <= 4:
            if re.search(rf"(?<!\w){re.escape(b)}(?!\w)", text or ""):
                out.add(b)
        elif re.search(rf"(?<!\w){re.escape(b.lower())}(?!\w)", low):
            out.add(b)
    return sorted(out)


def lure_score(text: str) -> float:
    """0..1 heuristic used only to prioritise snapshots/captures (never as a verdict)."""
    t = (text or "").lower()
    s = 0.0
    s += 0.4 if LURE_RE.search(t) else 0.0
    s += 0.4 if find_persons(text) else 0.0
    s += 0.1 if find_brands(text) else 0.0
    s += 0.1 if re.search(r"\d+\s?(zł|pln|tys|mln)|%", t) else 0.0
    return min(1.0, s)
