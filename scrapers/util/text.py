"""Light-weight content extraction used at ingest time (no ML): persons/brands gazetteer with Polish
inflection, headline templates, contacts (phone/IBAN/e-mail/Telegram/wallets), narrative keyword rules.
The features stream replaces/extends this with NER, OCR, ASR and embeddings; these rules give the
deterministic baseline and the observables the blocking index needs from day one."""
from __future__ import annotations

import re
import unicodedata

# ---- impersonated persons (seed gazetteer; extend in refdb/) ----
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

BRANDS = ["Gazeta.pl", "Onet", "Wirtualna Polska", "WP.pl", "Interia", "TVN24", "TVN", "Polsat", "TVP",
          "Fakt", "Rzeczpospolita", "Business Insider", "Forbes", "InPost", "NBP", "PKO BP", "mBank",
          "Pekao", "ING", "Santander", "Allegro", "Orlen", "PGE", "ZUS", "Biedronka", "Lidl", "Amazon",
          "Revolut", "Facebook", "Jasna Góra", "Ministerstwo Zdrowia", "NFZ"]


def _stem(word: str) -> str:
    """Polish declension mostly rewrites a final vowel (Brzoska→Brzoskę) or appends (Stanowski→Stanowskiego,
    Olejnik→Olejnika), so drop a final vowel only."""
    return word[:-1] if word[-1].lower() in "aeiouyąę" and len(word) > 4 else word


def _person_regex(full: str) -> re.Pattern:
    first, *rest = full.split()
    last = rest[-1]
    return re.compile(rf"\b{re.escape(_stem(first))}\w{{0,4}}\s+{re.escape(_stem(last))}\w{{0,4}}\b", re.UNICODE)


# surname-only mentions: only for distinctive surnames (not shared by two gazetteer entries, not common)
COMMON_SURNAMES = {"kowalczyk", "nowak", "kowalski", "wiśniewski", "wójcik", "lewandowski", "lewandowska",
                   "kamiński", "zieliński", "szymański", "woźniak", "duda", "prokop"}
_stems = [(_stem(n.split()[-1]), n) for n in PERSONS]
_PERSON_PATTERNS = [(name, role, _person_regex(name)) for name, role in PERSONS.items()]
_SURNAME_PATTERNS = [
    (name, re.compile(rf"\b{re.escape(st)}\w{{0,4}}\b"))
    for st, name in _stems
    if len(st) >= 5 and name.split()[-1].lower() not in COMMON_SURNAMES
    and sum(1 for s2, _ in _stems if s2 == st) == 1
]


def find_persons(text: str) -> list[tuple[str, str, float, tuple[int, int]]]:
    """-> [(canonical_name, role, confidence, span)]"""
    out, taken = [], []
    for name, role, pat in _PERSON_PATTERNS:
        for m in pat.finditer(text):
            out.append((name, role, 1.0, m.span()))
            taken.append(m.span())
    for name, pat in _SURNAME_PATTERNS:
        for m in pat.finditer(text):
            if not any(a <= m.start() < b for a, b in taken) and m.group(0)[0].isupper():
                out.append((name, PERSONS[name], 0.6, m.span()))
    return out


def find_brands(text: str) -> list[str]:
    low = text.lower()
    out = set()
    for b in BRANDS:
        if len(b) <= 4:   # ING, NBP, ZUS, TVP: case-sensitive, they collide with ordinary words
            if re.search(rf"(?<!\w){re.escape(b)}(?!\w)", text):
                out.add(b)
        elif re.search(rf"(?<!\w){re.escape(b.lower())}(?!\w)", low):
            out.add(b)
    return sorted(out)


def headline_template(title: str | None) -> str | None:
    """Mask persons (with inflection) and numbers: 'PILNE: Brutalna napaść na {PER} tuż po …'."""
    if not title:
        return None
    t = re.sub(r"\s+", " ", title).strip()
    spans = sorted({s for *_, s in find_persons(t)}, reverse=True)
    for a, b in spans:
        t = t[:a] + "{PER}" + t[b:]
    t = re.sub(r"\{PER\}(\s*\{PER\})+", "{PER}", t)
    t = re.sub(r"\d+([.,]\d+)?", "{NUM}", t)
    return t


def normalize_text(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", t).strip()


# ---- contacts ----
PHONE_RE = re.compile(r"(?<!\d)(?:\+48[\s-]?|0048[\s-]?)?(?:\d{3}[\s-]?\d{3}[\s-]?\d{3}|\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2})(?!\d)")
IBAN_RE = re.compile(r"\b([A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?)\b")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
TG_RE = re.compile(r"(?:t\.me|telegram\.me)/([A-Za-z0-9_]{4,32})", re.I)
WALLET_RES = {
    "btc": re.compile(r"\b(bc1[a-z0-9]{25,59}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b"),
    "eth": re.compile(r"\b0x[a-fA-F0-9]{40}\b"),
    "trx": re.compile(r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b"),
}


def iban_valid(iban: str) -> bool:
    s = iban.replace(" ", "").upper()
    if len(s) < 15 or len(s) > 34:
        return False
    r = s[4:] + s[:4]
    digits = "".join(str(int(c, 36)) for c in r)
    return int(digits) % 97 == 1


def find_contacts(text: str) -> list[tuple[str, str, str]]:
    """-> [(type, normalized_value, display)]"""
    out: list[tuple[str, str, str]] = []
    for m in PHONE_RE.finditer(text):
        raw = m.group(0)
        d = re.sub(r"\D", "", raw)
        if d.startswith("0048"):
            d = d[4:]
        elif d.startswith("48") and len(d) == 11:
            d = d[2:]
        if len(d) == 9 and d[0] in "4567891" and len(set(d)) > 2:
            out.append(("phone", "+48" + d, raw.strip()))
    for m in IBAN_RE.finditer(text):
        if iban_valid(m.group(1)):
            v = m.group(1).replace(" ", "").upper()
            out.append(("iban", v, m.group(1)))
    for m in EMAIL_RE.finditer(text):
        e = m.group(0).lower()
        if not e.endswith((".png", ".jpg", ".webp", ".gif", ".svg")):
            out.append(("email", e, m.group(0)))
    for m in TG_RE.finditer(text):
        out.append(("telegram", m.group(1).lower(), m.group(0)))
    for chain, pat in WALLET_RES.items():
        for m in pat.finditer(text):
            out.append(("crypto_wallet", f"{chain}:{m.group(0)}", m.group(0)))
    return out


# ---- narrative / vertical keyword rules (baseline; M4 classifier replaces) ----
NARRATIVE_RULES = [
    ("fake_news_attack", "finance", r"zamach|napaś|napad|strzel|pobit|śledztw|aresztow|skandal|na żywo|zmiażdży"),
    ("health_cure", "health", r"cukrzy|grzybic|staw|kręgosłup|serc|ciśnieni|słuch|wzrok|odchudz|prostat|lek |leczen|kardio|dermatolog|suplement"),
    ("investment", "finance", r"inwest|zarabia|zarobi|krypto|bitcoin|platform[ay] inwest|dochód pasywny|giełd"),
    ("giveaway", "shop", r"za darmo|gratis|nagrod|wygra|losowani|limited time|tylko dziś"),
]


def classify_narrative(text: str) -> tuple[str | None, str | None]:
    low = text.lower()
    best, best_n = (None, None), 0
    for narrative, vertical, pat in NARRATIVE_RULES:
        n = len(re.findall(pat, low))
        if n > best_n:
            best, best_n = (narrative, vertical), n
    return best


def product_from_title(title: str | None) -> str | None:
    """Health-scam offer pages are often titled with just the product name (Kardivix, RelieFlex)."""
    if not title:
        return None
    t = title.strip()
    if re.fullmatch(r"[A-Z][A-Za-z]{3,15}(?:[- ][A-Z][a-z]+)?", t) and t.lower() not in {"home", "index", "loading"}:
        return t
    return None


def guess_lang(text: str) -> str | None:
    low = text.lower()
    pl = sum(low.count(c) for c in "ąćęłńóśźż")
    if len(low) < 40:
        return None
    if pl / max(len(low), 1) > 0.004:
        return "pl"
    return "en" if re.search(r"\b(the|and|you|your)\b", low) else None
