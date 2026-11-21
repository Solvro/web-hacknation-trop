"""HTML document parsing: title, visible text, forms, outlinks, scripts, meta, DOM shingles, kit signatures."""
from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

SAVED_FROM = re.compile(r"<!--\s*saved from url=\(\d+\)(\S+)\s*-->", re.I)

# Behavioural signatures of scam kits (value = observable 'html_signature')
SIGNATURES: dict[str, re.Pattern] = {
    "hue_rotate_root": re.compile(r"<html[^>]+style=[\"'][^\"']*filter:\s*hue-rotate\(", re.I),
    "back_button_hijack": re.compile(r"history\.pushState[\s\S]{0,400}?(onpopstate|popstate)", re.I),
    "context_menu_block": re.compile(r"oncontextmenu\s*=\s*[\"']\s*return\s+false|addEventListener\(\s*[\"']contextmenu[\"']", re.I),
    "copy_block": re.compile(r"oncopy\s*=\s*[\"']\s*return\s+false|user-select\s*:\s*none", re.I),
    "fake_fb_comments": re.compile(r"class=[\"'][^\"']*(fb-comment|comments?-fb|fb_comments|comment__like)", re.I),
    "countdown_timer": re.compile(r"(countdown|timer)[\w-]*[\"'][^>]*>\s*\d{1,2}\s*:\s*\d{2}", re.I),
    "today_date_js": re.compile(r"new Date\(\)[\s\S]{0,200}?(getDate|toLocaleDateString)", re.I),
    "utm_visit_kit": re.compile(r"utm_visit", re.I),
    "persist_session_record": re.compile(r"persist-session-record", re.I),
    "keitaro_markers": re.compile(r"(_subid|keitaro|kclient|\{subid\})", re.I),
    "noindex": re.compile(r"<meta[^>]+name=[\"']robots[\"'][^>]+noindex", re.I),
    "landing_cdn_path": re.compile(r"/_cdn/production/landing-cdn/", re.I),
}

PIXEL_PATTERNS = [  # (observable type, value prefix, pattern)
    ("fb_pixel", "", re.compile(r"fbq\(\s*['\"]init['\"]\s*,\s*['\"]?(\d{14,17})")),
    ("fb_pixel", "", re.compile(r"facebook\.com/tr/?\?[^\"'\s]*\bid=(\d{14,17})")),
    ("fb_pixel", "", re.compile(r"signals/config/(\d{14,17})")),
    ("fb_pixel", "", re.compile(r"['\"]pixel(?:_?id|Id)?['\"]\s*:\s*['\"](\d{14,17})['\"]")),
    ("google_tag", "", re.compile(r"\b(AW-\d{6,12})\b")),
    ("google_tag", "", re.compile(r"\b(G-[A-Z0-9]{8,12})\b")),
    ("google_tag", "", re.compile(r"\b(GTM-[A-Z0-9]{5,9})\b")),
    ("google_tag", "", re.compile(r"\b(UA-\d{4,10}-\d{1,3})\b")),
    ("tiktok_pixel", "", re.compile(r"ttq\.load\(\s*['\"]([A-Z0-9]{15,25})['\"]")),
    ("tiktok_pixel", "", re.compile(r"analytics\.tiktok\.com/[^\"']*sdkid=([A-Z0-9]{15,25})")),
    ("tracker_id", "ym:", re.compile(r"\bym\(\s*(\d{6,10})\s*,\s*['\"]init")),
    ("tracker_id", "ym:", re.compile(r"mc\.yandex\.ru/watch/(\d{6,10})")),
    ("tracker_id", "hotjar:", re.compile(r"hotjar[\s\S]{0,80}?hjid\s*:\s*(\d{5,9})")),
    ("tracker_id", "clarity:", re.compile(r"clarity\.ms/tag/([a-z0-9]{8,12})")),
]


@dataclass
class ParsedHtml:
    title: str | None = None
    text: str = ""
    saved_from: str | None = None
    forms: list[dict] = field(default_factory=list)
    outlinks: list[str] = field(default_factory=list)
    script_srcs: list[str] = field(default_factory=list)
    resource_srcs: list[str] = field(default_factory=list)
    iframes: list[str] = field(default_factory=list)
    favicon_hrefs: list[str] = field(default_factory=list)
    meta: list[dict] = field(default_factory=list)
    inline_scripts: str = ""
    signatures: list[str] = field(default_factory=list)
    tag_shingles: set[str] = field(default_factory=set)
    lang: str | None = None


def parse_html(raw: bytes | str, base_url: str | None = None) -> ParsedHtml:
    html = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    out = ParsedHtml()
    m = SAVED_FROM.search(html[:4000])
    if m:
        out.saved_from = m.group(1)
    base = base_url or out.saved_from
    soup = BeautifulSoup(html, "lxml")
    if soup.title and soup.title.string:
        out.title = re.sub(r"\s+", " ", soup.title.string).strip()
    if soup.html and soup.html.get("lang"):
        out.lang = str(soup.html.get("lang")).split("-")[0].lower()
    for mt in soup.find_all("meta"):
        out.meta.append({k: (v if isinstance(v, str) else " ".join(v)) for k, v in mt.attrs.items()})
    out.inline_scripts = "\n".join(s.get_text() for s in soup.find_all("script") if not s.get("src"))
    for s in soup.find_all("script", src=True):
        out.script_srcs.append(_abs(base, s["src"]))
    for tag, attr in (("img", "src"), ("link", "href"), ("source", "src"), ("video", "src"), ("audio", "src")):
        for el in soup.find_all(tag):
            v = el.get(attr)
            if v and not str(v).startswith("data:"):
                out.resource_srcs.append(_abs(base, v))
    for link in soup.find_all("link", href=True):
        rel = " ".join(link.get("rel") or []).lower()
        if "icon" in rel:
            out.favicon_hrefs.append(_abs(base, link["href"]))
    for f in soup.find_all("iframe", src=True):
        out.iframes.append(_abs(base, f["src"]))
    for a in soup.find_all("a", href=True):
        h = str(a["href"]).strip()
        if h and not h.startswith(("#", "javascript:", "mailto:", "tel:")):
            out.outlinks.append(_abs(base, h))
    for form in soup.find_all("form"):
        fields = sorted({str(i.get("name") or i.get("id") or i.get("type") or "")
                         for i in form.find_all(["input", "select", "textarea"]) if i.get("type") != "hidden"} - {""})
        hidden = sorted({str(i.get("name")) for i in form.find_all("input", type="hidden") if i.get("name")})
        out.forms.append({"action": _abs(base, form.get("action") or ""), "method": (form.get("method") or "get").lower(),
                          "fields": fields, "hidden": hidden})
    # tag-sequence 5-gram shingles (DOM structure fingerprint, insensitive to text/ids)
    tags = [t.name for t in soup.find_all(True)]
    out.tag_shingles = {" ".join(tags[i:i + 5]) for i in range(max(0, len(tags) - 4))}
    for t in soup(["script", "style", "noscript", "template", "svg"]):
        t.decompose()
    out.text = re.sub(r"[ \t\r\f\v]+", " ", soup.get_text("\n"))
    out.text = re.sub(r"\n\s*\n+", "\n", out.text).strip()
    out.signatures = sorted(k for k, pat in SIGNATURES.items() if pat.search(html))
    return out


def _abs(base: str | None, href: str) -> str:
    href = str(href).strip()
    if base and not href.startswith(("http://", "https://", "//")):
        # saved pages point at ./<name>_files/… — keep those relative (they are local copies)
        if href.startswith("./") or "_files/" in href:
            return href
        try:
            return urljoin(base, href)
        except ValueError:
            return href
    if href.startswith("//"):
        return "https:" + href
    return href


def tracking_ids(text: str) -> list[tuple[str, str]]:
    """(type, value) for analytics/ad account ids in any HTML/JS text."""
    found: set[tuple[str, str]] = set()
    for typ, prefix, pat in PIXEL_PATTERNS:
        for m in pat.finditer(text):
            found.add((typ, prefix + m.group(1)))
    return sorted(found)
