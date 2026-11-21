from __future__ import annotations

import re
from urllib.parse import urlsplit

import tldextract

_EX = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)


def host_of(x: str) -> str:
    x = x.strip().lower()
    if "://" in x or "/" in x:
        try:
            x = urlsplit(x if "://" in x else "//" + x).hostname or ""
        except ValueError:
            return ""
    return x.strip(".")


def etld1(x: str) -> str:
    h = host_of(x)
    e = _EX(h)
    return f"{e.domain}.{e.suffix}" if e.domain and e.suffix else h


def tld(x: str) -> str:
    return _EX(host_of(x)).suffix


def norm_registrar(name: str | None) -> str | None:
    if not name:
        return None
    n = re.sub(r"[,.]", " ", name.lower())
    n = re.sub(r"\b(inc|llc|ltd|limited|corp|co|gmbh|uab|operations|group|international|s a|sa)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip() or name.lower()


def parse_ts(s: str | None):
    from datetime import datetime, timezone
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
