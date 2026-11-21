"""Tiny dependency-light helpers (this package also runs inside the sandbox container without the rest of `trop`)."""
from __future__ import annotations

import base64
import ipaddress
from urllib.parse import urlsplit

import mmh3
import tldextract

_EXTRACT = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)


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


def etld1_of(host_or_url: str) -> str:
    h = host_of(host_or_url) if "/" in host_or_url or ":" in host_or_url else host_or_url.lower().strip(".")
    try:
        ipaddress.ip_address(h.strip("[]"))
        return h
    except ValueError:
        pass
    e = _EXTRACT(h)
    return f"{e.domain}.{e.suffix}" if e.domain and e.suffix else h


def favicon_mmh3(data: bytes) -> int:
    """Shodan http.favicon.hash."""
    return mmh3.hash(base64.encodebytes(data))
