"""URL / host helpers: eTLD+1, normalization, path templating, parameter-grammar shapes."""
from __future__ import annotations

import ipaddress
import re
from functools import lru_cache
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

import tldextract

# Bundled Public Suffix List snapshot: deterministic and offline (no network on first use).
_EXTRACT = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)

# Click ids / tracking params that identify the *visit*, not the campaign. Stripped for url_norm.
CLICK_IDS = {
    "fbclid", "gclid", "gbraid", "wbraid", "dclid", "msclkid", "ttclid", "yclid", "igshid",
    "mc_eid", "_ga", "gad_source", "gad_campaignid", "twclid", "li_fat_id", "epik",
}

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-([0-9a-f])[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
UUID_ANY = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
HEX_RE = re.compile(r"^[0-9a-f]{12,}$", re.I)
INT_RE = re.compile(r"^\d{3,}$")
B64ISH_RE = re.compile(r"^[A-Za-z0-9_\-+/=]{16,}$")


def host_of(url: str) -> str:
    try:
        h = urlsplit(url).hostname or ""
    except ValueError:
        return ""
    h = h.strip(".").lower()
    try:
        return h.encode("idna").decode("ascii") if h and not h.isascii() else h
    except UnicodeError:
        return h


def is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


@lru_cache(maxsize=65536)
def split_host(host: str) -> tuple[str, str, str]:
    """-> (etld1, sld, suffix). For IPs: (ip, ip, '')."""
    host = host.lower().strip(".")
    if not host or is_ip(host):
        return host, host, ""
    ext = _EXTRACT(host)
    if not ext.suffix:
        return host, ext.domain or host, ""
    etld1 = f"{ext.domain}.{ext.suffix}" if ext.domain else ext.suffix
    return etld1, ext.domain, ext.suffix


def etld1_of(host_or_url: str) -> str:
    host = host_of(host_or_url) if "://" in host_or_url else host_or_url
    return split_host(host)[0]


def normalize_url(url: str) -> str:
    """Canonical form used for dedupe of capture targets: lower host, no fragment, no click ids,
    no utm_* (all of which vary per click), sorted query."""
    try:
        p = urlsplit(url.strip())
    except ValueError:
        return url
    host = host_of(url)
    port = f":{p.port}" if p.port and p.port not in (80, 443) else ""
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
         if k.lower() not in CLICK_IDS and not k.lower().startswith("utm_")]
    q.sort()
    path = p.path or "/"
    return urlunsplit((p.scheme.lower(), host + port, path, urlencode(q), ""))


def templatize_segment(seg: str) -> str:
    s = unquote(seg)
    if not s:
        return s
    if UUID_RE.match(s):
        return "{uuid}"
    if UUID_ANY.search(s):
        return re.sub(r"\d{6,}", "{int}", UUID_ANY.sub("{uuid}", s))
    if INT_RE.match(s):
        return "{int}"
    if HEX_RE.match(s):
        return "{hex}"
    stem, dot, ext = s.rpartition(".")
    if dot and 1 <= len(ext) <= 5 and ext.isalnum() and stem:
        t = templatize_segment(stem)
        return f"{t}.{ext}" if t != stem else s
    has_digit = any(c.isdigit() for c in s)
    has_alpha = any(c.isalpha() for c in s)
    mixed_case = any(c.isupper() for c in s) and any(c.islower() for c in s)
    if B64ISH_RE.match(s) and has_digit and has_alpha:
        return "{tok}"
    # short random slugs like /5LGL36dD or /kT5VPccV (TDS campaign paths)
    if 6 <= len(s) <= 15 and s.isalnum() and has_digit and has_alpha and mixed_case:
        return "{tok}"
    # Keitaro-like /L64823125fl-448t584-fkf697Y/
    if len(s) >= 12 and has_digit and has_alpha and re.fullmatch(r"[A-Za-z0-9\-_]+", s) and sum(c.isdigit() for c in s) >= 4:
        return "{tok}"
    return s


def templatize_path(path: str) -> str:
    segs = path.split("/")
    return "/".join(templatize_segment(s) for s in segs)


def value_shape(v: str) -> str:
    """Shape of a parameter value: what kind of thing it is, not what it is."""
    if v == "":
        return "empty"
    v = unquote(v)
    m = UUID_RE.match(v)
    if m:
        return f"uuid{m.group(1)}"
    if v.isdigit():
        return f"int{len(v)}"
    if HEX_RE.match(v):
        return f"hex{len(v)}"
    if v.startswith(("http://", "https://")):
        return "url"
    if re.fullmatch(r"[A-Za-z0-9]+", v):
        return f"alnum{len(v)}"
    if re.fullmatch(r"[A-Za-z0-9_\-+/=]+", v):
        return "b64"
    return "text"


def param_schema(url: str) -> str | None:
    """Parameter grammar of a landing URL, e.g. 'utm_campaign:alnum10|…|utm_visit:uuid7'."""
    try:
        q = parse_qsl(urlsplit(url).query, keep_blank_values=True)
    except ValueError:
        return None
    if not q:
        return None
    parts = sorted({f"{k.lstrip('?').lower()}:{value_shape(v)}" for k, v in q})
    return "|".join(parts)


def query_params(url: str) -> dict[str, str]:
    try:
        return {k.lstrip("?"): v for k, v in parse_qsl(urlsplit(url).query, keep_blank_values=True)}
    except ValueError:
        return {}
