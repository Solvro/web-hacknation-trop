"""Throwaway extractors: sample_dir -> Incident-like dict (PLAN.md §4 schema, §5 feature names).

Deterministic, CPU-only, no network. Heavy/optional extractors (OCR, VLM, embeddings, faces) live in
separate modules and merge into the same dict under ad.* / media.* / emb.*.
"""
from __future__ import annotations

import base64
import glob
import hashlib
import html as htmllib
import json
import os
import re
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import parse_qsl, unquote, urlsplit

import tldextract

_TLD = tldextract.TLDExtract(suffix_list_urls=())  # offline snapshot, no network

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
HEX_RE = re.compile(r"(?<![0-9a-z])[0-9a-f]{16,}(?![0-9a-z])", re.I)
NUM_RE = re.compile(r"(?<![0-9])\d{5,}(?![0-9])")

# Hosts whose presence says nothing about the operator (weight 0 in every method)
COMMON_HOSTS = {
    "connect.facebook.net", "www.facebook.com", "facebook.com", "code.jquery.com", "cdnjs.cloudflare.com",
    "fonts.googleapis.com", "fonts.gstatic.com", "www.gstatic.com", "www.googletagmanager.com",
    "www.google-analytics.com", "www.w3.org", "cdn.jsdelivr.net", "unpkg.com", "ajax.googleapis.com",
    "yt3.googleusercontent.com", "www.clarity.ms", "static.im-g.pl",
}
COMMON_ETLD1 = {"facebook.net", "facebook.com", "jquery.com", "cloudflare.com", "googleapis.com", "gstatic.com",
                "googletagmanager.com", "google-analytics.com", "w3.org", "jsdelivr.net", "unpkg.com",
                "googleusercontent.com", "clarity.ms", "google.com", "doubleclick.net"}
CDN_PREFIXES = {  # anycast CDN ranges -> IP evidence is noise
    "cloudflare": ("104.16.", "104.17.", "104.18.", "104.19.", "104.20.", "104.21.", "104.22.", "104.23.",
                   "104.24.", "104.25.", "104.26.", "104.27.", "172.64.", "172.65.", "172.66.", "172.67.",
                   "188.114.96.", "188.114.97.", "188.114.98.", "188.114.99.", "162.159."),
    "cloudfront": ("108.138.", "18.66.", "18.244.", "3.174.", "13.32.", "13.35.", "54.230.", "54.239."),
    "meta": ("57.144.", "31.13.", "157.240."),
    "fastly": ("151.101.",),
    "google": ("142.250.", "172.217.", "216.58.", "34.143."),
}
SERVERLESS = re.compile(r"\.(on\.aws|run\.app|amazonaws\.com|herokuapp\.com|workers\.dev|vercel\.app|netlify\.app)$")
BRAND_ASSET = re.compile(r"(favicon|logo|\.ico$|\.woff2?$|\.ttf$|\.otf$|\.eot$|nav-|icon)", re.I)
STATIC_EXT = re.compile(r"\.(?:js|css|png|jpe?g|gif|webp|svg|ico|woff2?|ttf|otf|eot|mp4|m3u8|ts|webm|json|map)$", re.I)

# --------------------------------------------------------------------------------------------- helpers

def etld1(host: str) -> str:
    if not host:
        return ""
    e = _TLD(host)
    return ".".join(p for p in (e.domain, e.suffix) if p) or host


def cdn_of(ip: str | None) -> str | None:
    if not ip:
        return None
    for name, prefixes in CDN_PREFIXES.items():
        if ip.startswith(prefixes):
            return name
    return None


def value_shape(v: str) -> str:
    """Shape of a URL parameter value: the 'grammar' part of the kit fingerprint."""
    v = unquote(v)
    if v == "":
        return "empty"
    if UUID_RE.fullmatch(v):
        return "uuid7" if v[14] == "7" else "uuid"
    if re.fullmatch(r"\d+", v):
        return f"num{min(len(v), 20)}"
    if re.fullmatch(r"[0-9a-f]+", v, re.I) and len(v) >= 16:
        return f"hex{len(v)}"
    if re.fullmatch(r"[A-Za-z0-9]+", v):
        mixed = bool(re.search(r"[a-z]", v)) and bool(re.search(r"[A-Z0-9]", v))
        return f"rand{len(v)}" if mixed and len(v) >= 8 else ("word" if v.isalpha() else f"alnum{len(v)}")
    if re.fullmatch(r"[A-Za-z0-9+/=_-]{20,}", v):
        return "b64"
    if "/" in v and v.count("/") >= 3:
        return "slashpath"   # e.g. ad_name=FARM/PL/persona/... naming convention
    if "|" in v:
        return "pipetext"
    return "text"


def path_template(path: str) -> str:
    p = UUID_RE.sub("{uuid}", path)
    p = HEX_RE.sub("{hex}", p)
    p = NUM_RE.sub("{n}", p)
    # random-looking 8-char campaign slugs (Keitaro alias): mixed case + digit
    p = re.sub(r"(?<=/)(?=[A-Za-z0-9]{8}(?:/|$))(?=[^/]*[A-Z])(?=[^/]*[a-z])[A-Za-z0-9]{8}", "{slug8}", p)
    # per-deploy uniquifier suffixes like 'logo-kaz-870.png' -> 'logo-{rnd}.png'
    p = re.sub(r"-(?:[a-z]{3})-\d{3}(?=[./-]|$)", "-{rnd}", p)
    return p


def path_shape(path: str) -> str | None:
    """Character-class shape of a mixed-alnum path segment: /L64823125fl-448t584-fkf697Y/ -> L9fl-9a9-fkf9A.
    Captures lander-tool naming grammars whose literal values are randomised per deploy. None if trivial."""
    segs = [x for x in path.split("/") if x]
    out = []
    for seg in segs:
        if len(seg) < 8 or not (re.search(r"\d", seg) and re.search(r"[A-Za-z]", seg)) or UUID_RE.search(seg):
            continue
        sh = re.sub(r"\d+", "9", seg)
        sh = re.sub(r"(?<![a-z])[a-z](?![a-z])", "a", sh)
        sh = re.sub(r"(?<![A-Z])[A-Z](?![A-Z])", "A", sh)
        out.append(sh)
    return "/".join(out) if out else None


def url_schema(url: str) -> str:
    q = urlsplit(url).query
    pairs = parse_qsl(q, keep_blank_values=True)
    return "&".join(sorted(f"{k}:{value_shape(v)}" for k, v in pairs))


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class _TextAndDom(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.stack: list[str] = []
        self.paths: list[str] = []
        self.skip = 0
        self.title = None
        self._in_title = False
        self.h1: list[str] = []
        self._in_h1 = False
        self.attrs_classes: Counter = Counter()
        self.links: list[str] = []
        self.scripts: list[str] = []
        self.icons: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.stack.append(tag)
        if len(self.stack) > 60:
            self.stack = self.stack[-60:]
        self.paths.append("/".join(self.stack[-4:]))
        if tag in self.SKIP:
            self.skip += 1
        if tag == "title":
            self._in_title = True
        if tag == "h1":
            self._in_h1 = True
            self.h1.append("")
        for c in (a.get("class") or "").split():
            self.attrs_classes[c] += 1
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "script" and a.get("src"):
            self.scripts.append(a["src"])
        if tag == "link" and "icon" in (a.get("rel") or "") and a.get("href"):
            self.icons.append(a["href"])

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == "title":
            self._in_title = False
        if tag == "h1":
            self._in_h1 = False
        if tag in self.stack:
            while self.stack and self.stack.pop() != tag:
                pass

    def handle_data(self, data):
        if self._in_title:
            self.title = ((self.title or "") + data).strip()
        if self.skip:
            return
        d = data.strip()
        if d:
            self.text.append(d)
            if self._in_h1 and self.h1:
                self.h1[-1] += " " + d


def parse_html(raw: str) -> dict:
    p = _TextAndDom()
    try:
        p.feed(raw)
    except Exception:  # noqa: BLE001 - throwaway
        pass
    text = re.sub(r"\s+", " ", " ".join(p.text)).strip()
    return {
        "title": re.sub(r"\s+", " ", htmllib.unescape(p.title or "")).strip(),
        "text": text,
        "h1": [re.sub(r"\s+", " ", h).strip() for h in p.h1 if h.strip()],
        "dom_paths": p.paths,
        "classes": p.attrs_classes,
        "links": p.links,
        "scripts": p.scripts,
        "icons": p.icons,
    }


# ------------------------------------------------------------------- person masking (headline templates)
_FIRST = ("adam andrzej anna barbara beata bogdan bonifacy borys dariusz donald ewa grzegorz jacek jakub jan janusz "
          "jarosław joanna józef karol katarzyna krzysztof krystyna leszek łukasz maciej magdalena małgorzata marcin "
          "marek maria mariusz mateusz michał monika natalia paweł piotr radosław rafał robert roman ryszard "
          "sławomir stanisław szymon tomasz ursula ursuli wojciech władysław wołodymyr zbigniew štěpán robert "
          "kuba kamil szymon hanna agata dorota elżbieta iwona").split()
_FIRST_RE = "|".join(sorted({re.escape(f[:-1] if len(f) > 4 else f) for f in _FIRST}, key=len, reverse=True))
PERSON_RE = re.compile(rf"\b((?:{_FIRST_RE})[a-ząćęłńóśźżěřšůý]{{0,4}})\s+([A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźżěřšůý-]+)", re.I)
TITLE_PREFIX_RE = re.compile(r"\b(?:Ojc[a-z]*|Ojciec|dr\.?|Dr\.?|MUDr\.?|prof\.?|prezes[a-z]*)\s+([A-ZŁŚŻ][a-ząćęłńóśźżý]+)")
KNOWN_SINGLE = {"Glapiński": "Adam Glapiński", "Nawrocki": "Karol Nawrocki", "Sikorski": "Radosław Sikorski",
                "Zełenski": "Wołodymyr Zełenski", "Morawiecki": "Mateusz Morawiecki", "Olejnik": "Monika Olejnik",
                "Brzoska": "Rafał Brzoska", "Tusk": "Donald Tusk", "Kaczyński": "Jarosław Kaczyński"}


def _norm_person(first: str, last: str) -> str:
    # crude lemmatisation of Polish genitive/accusative: Krzysztofa Stanowskiego -> krzysztof stanowski
    f = re.sub(r"(a|em|owi|u)$", "", first.lower()) if len(first) > 5 else first.lower()
    l = last.lower()
    l = re.sub(r"(skiego|skiej|skim)$", "ski", l)
    l = re.sub(r"(ckiego)$", "cki", l)
    l = re.sub(r"(ę|y)$", "a", l) if l.endswith(("skę", "ę")) else l
    return f"{f} {l}"


def mask_persons(s: str) -> tuple[str, list[str]]:
    persons = []

    def rep(m):
        persons.append(_norm_person(m.group(1), m.group(2)))
        return "{PER}"

    out = PERSON_RE.sub(rep, s)
    out = TITLE_PREFIX_RE.sub(lambda m: (persons.append(m.group(0).lower()) or "{PER}"), out)
    for k, v in KNOWN_SINGLE.items():
        if re.search(rf"\b{k[:-1]}\w*", out):
            persons.append(v.lower())
            out = re.sub(rf"\b{k[:-1]}\w*", "{PER}", out)
    return re.sub(r"\s+", " ", out).strip(), sorted(set(persons))


# Public figures commonly impersonated in PL scam ads (gazetteer; surname stem -> canonical). Faces gallery uses the same keys.
PUBLIC_FIGURES = {
    "morawieck": "mateusz morawiecki", "brzosk": "rafał brzoska", "stanowsk": "krzysztof stanowski",
    "sekielsk": "tomasz sekielski", "glapińsk": "adam glapiński", "olejnik": "monika olejnik", "nawrock": "karol nawrocki",
    "sikorsk": "radosław sikorski", "zełensk": "wołodymyr zełenski", "von der leyen": "ursula von der leyen",
    "tusk": "donald tusk", "kaczyńsk": "jarosław kaczyński", "domańsk": "andrzej domański", "duda": "andrzej duda",
    "lewandowsk robert": "robert lewandowski", "kubacki": "dawid kubacki", "hołowni": "szymon hołownia",
    "trzaskowsk": "rafał trzaskowski", "mentzen": "sławomir mentzen", "bosak": "krzysztof bosak",
    "kwaśniewsk": "aleksander kwaśniewski", "wojewódzk": "kuba wojewódzki", "majdan": "radosław majdan",
    "rozenek": "małgorzata rozenek", "solorz": "zygmunt solorz", "kulczyk": "jan kulczyk", "czarnek": "przemysław czarnek",
    "błaszczak": "mariusz błaszczak", "ziobr": "zbigniew ziobro", "musk": "elon musk", "gates": "bill gates",
}


def public_figures(text: str) -> list[str]:
    low = text.lower()
    out = set()
    for stem, canon in PUBLIC_FIGURES.items():
        parts = stem.split()
        if all(re.search(rf"\b{re.escape(p)}", low) for p in parts):
            out.add(canon)
    return sorted(out)


BRANDS = {"gazeta.pl": r"gazeta\.pl|gazeta", "tvn24": r"tvn24|kropk[aię] nad i", "nbp": r"\bNBP\b",
          "inpost": r"inpost|paczkomat", "baltic_pipe": r"baltic pipe", "finnews": r"finnews",
          "onet": r"\bonet\b", "pko": r"\bPKO\b", "pekao": r"pekao", "jasna_gora": r"jasnej g[óo]r",
          "zyskarnia": r"zyskarni", "switowin": r"świtowin|switowin", "orlen": r"orlen", "zus": r"\bZUS\b"}
VERTICAL_KW = {
    "investment": r"inwest|zysk|platform|wypłat|zarabia|krypto|bitcoin|akcj[ie]|dywidend|pensj|lokat|oszczędn",
    "health": r"cukrzyc|stawy|stawów|kolan|słuch|ciśnieni|nadciśnieni|grzybic|lekarz|dermatolog|kardiolog|preparat|tabletk|kuracj|ból",
    "politics": r"prezydent|premier|minister|rząd|unii europejskiej|ukrain|sejm",
    "crime_shock": r"zamach|strzela|napaść|pobit|postrzel|policj",
}

# ---------------------------------------------------------------------------------------- HAR parsing

def parse_har(path: str) -> dict:
    j = json.load(open(path, encoding="utf-8", errors="replace"))
    entries = j["log"]["entries"]
    pages = j["log"].get("pages") or []
    out = {"n_entries": len(entries), "requests": [], "page_title": (pages[0].get("title") if pages else None)}
    for e in entries:
        req, resp = e["request"], e["response"]
        content = resp.get("content", {}) or {}
        body_hash = None
        txt = content.get("text")
        if txt:
            try:
                b = base64.b64decode(txt) if content.get("encoding") == "base64" else txt.encode("utf-8", "replace")
                if len(b) > 0:
                    body_hash = sha256(b)
            except Exception:  # noqa: BLE001
                pass
        post = (req.get("postData") or {}).get("text") or ""
        out["requests"].append({
            "url": req["url"], "method": req["method"], "status": resp.get("status"),
            "mime": content.get("mimeType") or "", "size": content.get("size"), "ip": e.get("serverIPAddress"),
            "body_sha256": body_hash, "post": post[:4000],
            "location": next((h["value"] for h in resp.get("headers", []) if h["name"].lower() == "location"), None),
            "t": e.get("startedDateTime"),
            "body_text": txt if (txt and content.get("encoding") != "base64" and "html" in (content.get("mimeType") or "")) else None,
        })
    return out


# ------------------------------------------------------------------------------------- sample_dir I/O

def find_files(d: str) -> dict:
    files = {"har": [], "html": [], "screenshot": [], "archive": None, "files_dirs": [], "other": [], "video": [],
             "video_info": [], "pages": []}
    for f in sorted(os.listdir(d)):
        p = os.path.join(d, f)
        if os.path.isdir(p):
            if f.startswith("archive_") and os.path.exists(os.path.join(p, "archive_info.json")):
                files["archive"] = p
            elif f.endswith("_files"):
                files["files_dirs"].append(p)
            else:   # page of a multi-step chain (strona_N) or a nested capture tool dir (dom.html + page.har)
                files["pages"].append(p)
            continue
        fl = f.lower()
        if fl.endswith(".har"):
            files["har"].append(p)
        elif fl.endswith((".html", ".htm")):
            files["html"].append(p)
        elif fl.endswith((".png", ".jpg", ".jpeg", ".webp")):
            files["screenshot"].append(p)
        elif fl.endswith(".info.json"):
            files["video_info"].append(p)
        elif fl.endswith((".mp4", ".mov", ".webm")):
            files["video"].append(p)
        else:
            files["other"].append(p)
    # ad screenshot first: Ad Library / reklama / Zrzut ekranu before phone screenshots (IMG_*)
    files["screenshot"].sort(key=lambda x: (0 if re.search(r"reklama|zrzut|screenshot", os.path.basename(x), re.I) else 1, x))
    # multi-page chain: pull HAR/HTML/_files from page dirs (recursively, max depth 3)
    for pg in sorted(files["pages"]):
        for root, dirs, fs in os.walk(pg):
            if root.count(os.sep) - pg.count(os.sep) > 3 or root.endswith("_files") or os.sep + "resources" in root:
                continue
            for x in sorted(fs):
                xp = os.path.join(root, x)
                if x.lower().endswith(".har"):
                    files["har"].append(xp)
                elif x.lower().endswith((".html", ".htm")):
                    files.setdefault("page_html", []).append(xp)
            files["files_dirs"] += [os.path.join(root, y) for y in dirs if y.endswith("_files")]
    if not files["html"] and files.get("page_html"):
        files["html"] = files["page_html"][:1]
    return files


def find_bundle_files(d: str) -> dict:
    """Organizer capture bundle (as in sample_v1/p1/archive_*): archive_info.json, dns_ssl.json, metadata.json,
    network.har, html/{rendered,source}.html, screenshots/{full_page,viewport}.png, page_text.txt, storage/."""
    html = [os.path.join(d, "html", n) for n in ("rendered.html", "source.html") if os.path.exists(os.path.join(d, "html", n))]
    har = [os.path.join(d, n) for n in ("network.har",) if os.path.exists(os.path.join(d, n))] + sorted(glob.glob(os.path.join(d, "*.har")))
    shots = [os.path.join(d, "screenshots", n) for n in ("full_page.png", "viewport.png") if os.path.exists(os.path.join(d, "screenshots", n))]
    ad_shots = sorted(p for p in glob.glob(os.path.join(d, "*.png")) + glob.glob(os.path.join(d, "*.jpg")))
    return {"har": har[:1], "html": html[:1], "screenshot": ad_shots[:1], "landing_screenshot": shots[:1], "archive": d,
            "files_dirs": [], "other": []}


def is_bundle(d: str) -> bool:
    return os.path.exists(os.path.join(d, "archive_info.json"))


def _saved_from(raw_html: str) -> str | None:
    m = re.search(r"saved from url=\(\d+\)(\S+)", raw_html[:3000])
    return m.group(1).rstrip("-->").strip() if m else None


def extract_incident(d: str, inc_id: str | None = None, drop: set[str] | None = None) -> dict:
    """Build the Incident dict for one sample directory. `drop` simulates missing inputs: {'har','html','screenshot','archive'}."""
    drop = drop or set()
    inc_id = inc_id or os.path.basename(d.rstrip("/\\"))
    files = find_bundle_files(d) if is_bundle(d) else find_files(d)
    for k in ("har", "html", "screenshot"):
        if k in drop:
            files[k] = []
    if "archive" in drop:
        files["archive"] = None
    if "html" in drop:
        files["files_dirs"] = []

    inc: dict = {
        "id": inc_id,
        "source": {"type": "archive_bundle" if is_bundle(d) else "sample_dir", "path": d, "captured_at": None},
        "ad": {"screenshot_path": files["screenshot"][0] if files["screenshot"] else None},
        "landing": {"screenshot_path": (files.get("landing_screenshot") or [None])[0]},
        "tracking": {},
        "infra": {"domains": [], "ips": [], "cdn": []},
        "content": {},
        "quality": {"available": [k for k in ("har", "html", "screenshot") if files[k]] + (["archive"] if files["archive"] else []),
                    "missing": [k for k in ("har", "html", "screenshot") if not files[k]], "errors": []},
    }

    raw_html = ""
    if files["html"]:
        raw_html = open(files["html"][0], encoding="utf-8", errors="replace").read()
    har = None
    for hp in files["har"]:
        try:
            h = parse_har(hp)
        except Exception as ex:  # noqa: BLE001
            inc["quality"]["errors"].append(f"har:{os.path.basename(hp)}:{ex}")
            continue
        fd = next((r["url"] for r in h["requests"] if "html" in r["mime"] and r["status"] == 200), None)
        inc["landing"].setdefault("chain_urls", []).append(fd or (h["requests"][0]["url"] if h["requests"] else None))
        if har is None:
            har = h
        else:
            har["requests"] += h["requests"]
            har["n_entries"] += h["n_entries"]
    inc["landing"]["n_hars"] = len(files["har"])
    inc["landing"]["n_pages"] = 1 + len(files.get("pages", []))
    # extra HTML pages of a chain: titles + text contribute to content, hosts to infra
    extra_pages = [x for x in files.get("page_html", []) if x not in files["html"]]
    inc["landing"]["chain_titles"] = []
    for xp in extra_pages[:5]:
        try:
            ph = parse_html(open(xp, encoding="utf-8", errors="replace").read())
            inc["landing"]["chain_titles"].append(ph["title"])
        except Exception:  # noqa: BLE001
            pass
    archive = {}
    if files["archive"]:
        a = files["archive"]
        for name in ("archive_info.json", "dns_ssl.json", "metadata.json"):
            fp = os.path.join(a, name)
            if os.path.exists(fp):
                archive[name] = json.load(open(fp, encoding="utf-8", errors="replace"))
        pt = os.path.join(a, "page_text.txt")
        if os.path.exists(pt):
            archive["page_text"] = open(pt, encoding="utf-8", errors="replace").read()
        if har is None and os.path.exists(os.path.join(a, "network.har")):
            har = parse_har(os.path.join(a, "network.har"))

    if files.get("video_info"):
        try:
            vj = json.load(open(files["video_info"][0], encoding="utf-8"))
            inc["ad"].update({"library_id": str(vj.get("playlist_id") or vj.get("id", "")).split("_")[0],
                              "advertiser": vj.get("playlist_uploader") or vj.get("uploader"),
                              "page_id": vj.get("playlist_uploader_id") or vj.get("uploader_id"),
                              "video_title": vj.get("title"), "n_creatives": vj.get("n_entries")})
        except Exception as ex:  # noqa: BLE001
            inc["quality"]["errors"].append(f"info.json:{ex}")
    inc["ad"]["video_path"] = (files.get("video") or [None])[0]
    inc["ad"]["screenshots"] = files["screenshot"]
    if files.get("video"):
        inc["quality"]["available"].append("video")

    # ---------------- entry URL / landing host
    entry_url = (archive.get("archive_info.json") or {}).get("url") or (_saved_from(raw_html) if raw_html else None)
    if not entry_url and har:
        docs = [r for r in har["requests"] if "html" in r["mime"] and r["status"] == 200]
        entry_url = (docs[0]["url"] if docs else har["requests"][0]["url"]) if har["requests"] else None
    if not entry_url and archive.get("archive_info.json"):
        entry_url = archive["archive_info.json"].get("url")
    host = urlsplit(entry_url).hostname if entry_url else None
    land_e1 = etld1(host) if host else ""
    inc["landing"]["entry_url"] = entry_url
    inc["landing"]["host"] = host
    inc["landing"]["etld1"] = land_e1
    inc["tracking"]["url_param_schema"] = url_schema(entry_url) if entry_url else ""
    chain = [u for u in ([entry_url] + (inc["landing"].get("chain_urls") or [])) if u]
    inc["tracking"]["path_shapes"] = sorted({ps for u in chain if (ps := path_shape(urlsplit(u).path))})
    inc["tracking"]["chain_param_schemas"] = sorted({url_schema(u) for u in chain if urlsplit(u).query})
    inc["tracking"]["entry_path_template"] = path_template(urlsplit(entry_url).path) if entry_url else ""
    if archive.get("archive_info.json"):
        inc["source"]["captured_at"] = archive["archive_info.json"].get("timestamp_utc")
    elif har and har["requests"]:
        inc["source"]["captured_at"] = min(r["t"] for r in har["requests"] if r["t"])

    # ---------------- page content: prefer saved HTML, else HAR document body, else archive text
    page_html = raw_html
    if not page_html and har:
        for r in har["requests"]:
            if r["body_text"] and urlsplit(r["url"]).hostname == host:
                page_html = r["body_text"]
                break
    parsed = parse_html(page_html) if page_html else None
    if parsed:
        inc["landing"]["title"] = parsed["title"]
        inc["landing"]["text"] = parsed["text"][:20000]
        inc["landing"]["h1"] = parsed["h1"][:3]
        inc["landing"]["dom_paths"] = parsed["dom_paths"]
        inc["landing"]["css_classes"] = [c for c, _ in parsed["classes"].most_common(300)]
    elif archive.get("page_text"):
        inc["landing"]["title"] = (archive.get("archive_info.json") or {}).get("title", "")
        inc["landing"]["text"] = archive["page_text"]
    title = inc["landing"].get("title") or ""
    # error / parked page detection (M5-lite): low-information pages must not drive content links
    blob = (title + " " + (inc["landing"].get("text") or "")[:500]).lower()
    inc["landing"]["page_role"] = "error" if re.search(r"502|bad gateway|error code 5\d\d|not found|404|suspended", blob) and len(blob) < 1500 else "content"

    # ---------------- tracking IDs from HTML + HAR
    hay = page_html or ""
    har_urls = [r["url"] for r in har["requests"]] if har else []
    har_posts = [r["post"] for r in har["requests"]] if har else []
    files_names = []
    for fd in files["files_dirs"]:
        files_names += os.listdir(fd)
    blob_all = "\n".join([hay] + har_urls + har_posts + files_names)
    px = set(re.findall(r"fbq\(\s*['\"]init['\"]\s*,\s*['\"]?(\d{14,17})", blob_all))
    px |= set(re.findall(r"(?:pixel|fbpx|fb\.pixel_id|pixelId|pixel_id)[\"']?\s*[:=]\s*[\"']?(\d{14,17})", blob_all, re.I))
    px |= set(re.findall(r"facebook\.com/tr\?[^\"'\s]*\bid=(\d{14,17})", blob_all))
    px |= set(re.findall(r"signals/config/(\d{14,17})", blob_all))
    px |= {n for n in files_names if re.fullmatch(r"\d{15,16}", n)}   # Chrome 'save complete' names pixel config files by id
    inc["tracking"]["fb_pixels"] = sorted(px)
    inc["tracking"]["google_ads"] = sorted(set(re.findall(r"\bAW-\d{9,12}\b", blob_all)))
    inc["tracking"]["ga4"] = sorted(set(re.findall(r"\bG-[A-Z0-9]{8,12}\b", blob_all)))
    inc["tracking"]["gtm"] = sorted(set(re.findall(r"\bGTM-[A-Z0-9]{5,8}\b", blob_all)))
    inc["tracking"]["tiktok_pixels"] = sorted(set(re.findall(r"ttq\.load\(['\"]([A-Z0-9]{15,25})", blob_all)))
    inc["tracking"]["snap_pixels"] = sorted(set(re.findall(r"snaptr\(['\"]init['\"],\s*['\"]([0-9a-f-]{36})", blob_all)))
    inc["tracking"]["kit_tenants"] = sorted(set(re.findall(r"landing-cdn/([0-9a-f-]{36})/", blob_all)))
    lid = set(re.findall(r"landing-cdn/[0-9a-f-]{36}/([0-9a-f-]{36})", blob_all))
    lid |= set(re.findall(r"landed_on_landings_uuid=([0-9a-f-]{36})", blob_all))
    lid |= set(re.findall(r"/l/([0-9a-f-]{36})/", blob_all))
    lid |= set(re.findall(r"/lander/([^/\"'?]+)/", blob_all))
    lid |= set(re.findall(r"/landers/([^/\"'?]+)/", blob_all))
    inc["tracking"]["lander_ids"] = sorted(lid)
    inc["tracking"]["landing_type_ids"] = sorted(set(re.findall(r"landing_types?_uuid=([0-9a-f-]{36})", blob_all)))
    inc["tracking"]["video_hosts"] = sorted(set(re.findall(r"(vz-[0-9a-f]{8}-[0-9a-f]{3})", blob_all)))
    inc["tracking"]["kmnr_key"] = sorted(set(re.findall(r"kmnrKey=([^\"'&\s]*)", blob_all)))

    # ---------------- requests: endpoints, gateways, third parties, assets, infra
    kit_endpoints, capi, third, asset_hashes, ips, cdns, hosts_seen = set(), set(), set(), set(), set(), set(), Counter()
    brand_assets, tracker_hosts = set(), set()
    if har:
        for r in har["requests"]:
            u = urlsplit(r["url"])
            h = (u.hostname or "").lower()
            hosts_seen[h] += 1
            e1 = etld1(h)
            if r["ip"]:
                ips.add((h, r["ip"]))
            if re.search(r"\.(on\.aws|run\.app|amazonaws\.com|herokuapp\.com|workers\.dev)$", h) and u.path.rstrip("/").endswith("events"):
                capi.add(h)
            first_party = (e1 == land_e1)
            tpl = path_template(u.path)
            if first_party and (r["method"] == "POST" or "/api/" in u.path or re.search(r"/(click|events|track|postback|lead|order)\b", u.path)) and not STATIC_EXT.search(u.path):
                kit_endpoints.add(f"{r['method']} {tpl}")
            if first_party and re.search(r"/(aio-static|include|catch)/", u.path) and STATIC_EXT.search(u.path):
                kit_endpoints.add(f"ASSET {re.sub(r'/[0-9a-f-]{36}', '/{uuid}', tpl)}")
            if not first_party and h and h not in COMMON_HOSTS and e1 not in COMMON_ETLD1 and not SERVERLESS.search(h):
                third.add(e1)
            if r["location"] or re.search(r"/(click|go|redirect|track|postback)\b", u.path):
                if not SERVERLESS.search(h) and e1 not in COMMON_ETLD1:
                    tracker_hosts.add(h)
            if r["body_sha256"] and (r["size"] or 0) >= 256 and h not in COMMON_HOSTS and e1 not in COMMON_ETLD1 and "html" not in r["mime"]:
                (brand_assets if BRAND_ASSET.search(u.path) else asset_hashes).add(r["body_sha256"])
    for fd in files["files_dirs"]:   # saved '_files' assets (byte-identical for images; html/css may be rewritten)
        for f in os.listdir(fd):
            fp = os.path.join(fd, f)
            if os.path.isfile(fp) and os.path.getsize(fp) >= 256 and not f.endswith((".html", ".htm")):
                low = f.lower()
                if any(k in low for k in ("fbevents", "jquery", "moment.min", "analytics.js", "clarity", "gtag", "hls.js")):
                    continue
                (brand_assets if BRAND_ASSET.search(f) else asset_hashes).add(sha256(open(fp, "rb").read()))
    # third parties + gateways visible only in HTML
    for m in re.findall(r"https?://([a-z0-9.-]+\.[a-z]{2,})", hay, re.I):
        m = m.lower()
        e1 = etld1(m)
        if e1 != land_e1 and m not in COMMON_HOSTS and e1 not in COMMON_ETLD1 and not SERVERLESS.search(m):
            third.add(e1)
        if re.search(r"\.(on\.aws|run\.app)$", m):
            capi.add(m)
    third.discard("")
    inc["tracking"]["kit_endpoints"] = sorted(kit_endpoints)
    inc["tracking"]["capi_gateways"] = sorted(capi)
    inc["tracking"]["third_party"] = sorted(third)
    inc["tracking"]["asset_hashes"] = sorted(asset_hashes - brand_assets)
    inc["tracking"]["brand_asset_hashes"] = sorted(brand_assets)

    # ---------------- infra
    dom_hosts = {host} if host else set()
    for h in tracker_hosts | {urlsplit(u).hostname for u in chain if urlsplit(u).hostname}:
        if etld1(h) != land_e1 and h not in COMMON_HOSTS and etld1(h) not in COMMON_ETLD1:
            dom_hosts.add(h)
    dns = archive.get("dns_ssl.json") or {}
    for h in sorted(dom_hosts):
        dd = {"fqdn": h, "etld1": etld1(h), "tld": h.rsplit(".", 1)[-1], "sld_label": etld1(h).split(".")[0],
              "ips": sorted({ip for hh, ip in ips if hh == h})}
        if dns and dns.get("hostname") == h:
            dd["ips"] = sorted(set(dd["ips"]) | set(dns.get("all_addresses") or []))
            ssl = dns.get("ssl") or {}
            iss = {k: v for part in ssl.get("issuer", []) for k, v in part}
            dd["cert"] = {"issuer": f"{iss.get('organizationName','')}/{iss.get('commonName','')}",
                          "not_before": ssl.get("notBefore"), "san": [v for _, v in ssl.get("subjectAltName", [])],
                          "serial": ssl.get("serialNumber")}
        dd["cdn"] = sorted({c for c in (cdn_of(ip) for ip in dd["ips"]) if c})
        inc["infra"]["domains"].append(dd)
    inc["infra"]["ips"] = sorted({ip for h, ip in ips if etld1(h) in {etld1(x) for x in dom_hosts}})
    inc["infra"]["origin_ips"] = sorted({ip for ip in inc["infra"]["ips"] if not cdn_of(ip)})
    inc["infra"]["cdn"] = sorted({c for ip in inc["infra"]["ips"] if (c := cdn_of(ip))})

    # ---------------- content
    tpl, persons = mask_persons(title) if title else ("", [])
    body = inc["landing"].get("text") or ""
    _, body_persons = mask_persons(body[:6000])
    inc["content"]["headline_template"] = tpl
    inc["content"]["h1_template"] = mask_persons((inc["landing"].get("h1") or [""])[0])[0] if inc["landing"].get("h1") else ""
    blob_txt = title + " " + " ".join(inc["landing"].get("h1") or []) + " " + body[:8000]
    inc["content"]["persons"] = public_figures(blob_txt)
    inc["content"]["comment_names"] = sorted({p for p in body_persons if p.split()[-1][:5] not in {g.split()[-1][:5] for g in inc["content"]["persons"]}
                                              and not re.search(r"(ł|ę|am|em|ła|ił|ia)$", p.split()[-1])})
    low = (title + " " + body).lower()
    inc["content"]["brands"] = sorted(b for b, rx in BRANDS.items() if re.search(rx, low, re.I))
    vscore = {v: len(re.findall(rx, low)) for v, rx in VERTICAL_KW.items()}
    inc["content"]["vertical_scores"] = vscore
    inc["content"]["vertical"] = max(("investment", "health"), key=lambda v: vscore[v]) if (vscore["investment"] + vscore["health"]) >= 3 else "other"
    inc["content"]["lang"] = "pl" if re.search(r"[ąęłńśźż]", low) else ("en" if re.search(r"\b(the|and|you)\b", low) else "unk")
    prods = set(re.findall(r"/lander/([a-z]+)---", blob_all))
    if title and re.fullmatch(r"[A-Z][a-zA-Z]{3,15}", title.strip()):
        prods.add(title.strip().lower())
    inc["content"]["products"] = sorted(prods)
    m = re.search(r"ad_name=([^&]+)", entry_url or "")
    inc["content"]["ad_name"] = unquote(m.group(1)).replace("+", " ") if m else None
    return inc


def load_sample_dir(root: str, drop: set[str] | None = None) -> list[dict]:
    dirs = sorted((p for p in glob.glob(os.path.join(root, "*")) if os.path.isdir(p)),
                  key=lambda x: (len(os.path.basename(x)), os.path.basename(x)))
    return [extract_incident(d, drop=drop) for d in dirs]
