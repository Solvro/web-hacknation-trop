"""HAR 1.2 parsing for both Chrome DevTools exports ('WebInspector') and Playwright record_har.

Gives: entries with decoded bodies, inferred resource types, and the full navigation chain
(HTTP 3xx, meta refresh, JS navigations, frames) for the top document.
"""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..util.urls import host_of
from .model import HopDraft


@dataclass
class HarEntry:
    seq: int
    started: datetime | None
    method: str
    url: str
    host: str
    status: int | None
    status_text: str
    mime: str | None
    resource_type: str
    server_ip: str | None
    body: bytes | None
    body_size: int | None
    redirect_url: str | None
    initiator_type: str | None
    initiator_url: str | None
    pageref: str | None
    req_headers: dict[str, str] = field(default_factory=dict)
    resp_headers: dict[str, str] = field(default_factory=dict)
    post_data: str | None = None


@dataclass
class Har:
    creator: str
    creator_version: str | None
    browser: str | None
    pages: list[dict]
    entries: list[HarEntry]

    @property
    def tool(self) -> str:
        c = self.creator.lower()
        if "playwright" in c:
            return "playwright-har"
        if "webinspector" in c:
            return "devtools-har"
        return c or "har"


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _headers(lst: list[dict] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for h in lst or []:
        k = str(h.get("name", "")).lower()
        if k and k not in out:
            out[k] = str(h.get("value", ""))
    return out


_DEST_MAP = {"document": "document", "iframe": "frame", "frame": "frame", "script": "script",
             "style": "stylesheet", "image": "image", "font": "font", "video": "media", "audio": "media",
             "track": "media", "manifest": "manifest", "worker": "script", "serviceworker": "script",
             "empty": "fetch"}


def _resource_type(e: dict, req_h: dict, mime: str | None) -> str:
    rt = e.get("_resourceType")
    dest = req_h.get("sec-fetch-dest")
    if rt:
        rt = str(rt).lower()
        # DevTools labels iframe navigations 'document' too; the fetch metadata tells them apart
        if rt == "document" and dest and dest.lower() in ("iframe", "frame"):
            return "frame"
        return rt
    if dest:
        return _DEST_MAP.get(dest.lower(), dest.lower())
    m = (mime or "").lower()
    if "html" in m:
        return "document"
    if "javascript" in m:
        return "script"
    if "css" in m:
        return "stylesheet"
    if m.startswith("image/"):
        return "image"
    if m.startswith(("video/", "audio/")) or "mpegurl" in m:
        return "media"
    if "json" in m:
        return "fetch"
    return "other"


def load_har(path: Path | str | None = None, data: bytes | None = None) -> Har:
    raw = data if data is not None else Path(path).read_bytes()  # type: ignore[arg-type]
    doc = json.loads(raw.decode("utf-8", errors="replace"))
    log = doc.get("log", doc)
    creator = log.get("creator") or {}
    browser = log.get("browser") or {}
    entries: list[HarEntry] = []
    raw_entries = sorted(log.get("entries", []), key=lambda e: e.get("startedDateTime") or "")
    for i, e in enumerate(raw_entries):
        req, resp = e.get("request", {}), e.get("response", {})
        content = resp.get("content", {}) or {}
        body = None
        txt = content.get("text")
        if txt is not None:
            if content.get("encoding") == "base64":
                try:
                    body = base64.b64decode(txt)
                except (ValueError, TypeError):
                    body = None
            else:
                body = txt.encode("utf-8", errors="surrogatepass") if isinstance(txt, str) else None
        req_h, resp_h = _headers(req.get("headers")), _headers(resp.get("headers"))
        mime = (content.get("mimeType") or resp_h.get("content-type") or "").split(";")[0].strip() or None
        ip = e.get("serverIPAddress")
        if ip:
            ip = ip.strip("[]")
        init = e.get("_initiator") or {}
        entries.append(HarEntry(
            seq=i, started=_dt(e.get("startedDateTime")), method=req.get("method", "GET"),
            url=req.get("url", ""), host=host_of(req.get("url", "")),
            status=resp.get("status") or None, status_text=resp.get("statusText", ""),
            mime=mime, resource_type=_resource_type(e, req_h, mime), server_ip=ip or None,
            body=body, body_size=len(body) if body is not None else (content.get("size") or None),
            redirect_url=resp.get("redirectURL") or resp_h.get("location") or None,
            initiator_type=init.get("type"), initiator_url=init.get("url"),
            pageref=e.get("pageref"), req_headers=req_h, resp_headers=resp_h,
            post_data=(req.get("postData") or {}).get("text"),
        ))
    return Har(creator=creator.get("name", ""), creator_version=creator.get("version"),
               browser=(browser.get("name", "") + " " + browser.get("version", "")).strip() or None,
               pages=log.get("pages", []), entries=entries)


_META_REFRESH = re.compile(rb"""<meta[^>]+http-equiv\s*=\s*["']?refresh["']?[^>]*content\s*=\s*["']?\s*\d+\s*;\s*url\s*=\s*([^"'>\s]+)""", re.I)
_JS_LOC = re.compile(rb"""(?:window\.|document\.|top\.|self\.)?location(?:\.href)?\s*(?:=|\.replace\(|\.assign\()\s*["']([^"']+)""", re.I)


def navigation_chain(har: Har) -> list[HopDraft]:
    """Reconstruct the top-level navigation chain incl. client-side hops."""
    docs = [e for e in har.entries if e.resource_type == "document" and e.method in ("GET", "POST")]
    if not docs:
        return []
    chain: list[HopDraft] = []
    prev: HarEntry | None = None
    for d in docs:
        if prev is None:
            kind = "entry"
        elif prev.redirect_url and prev.status and 300 <= prev.status < 400:
            kind = "http_redirect"
        elif prev.body and (m := _META_REFRESH.search(prev.body)) and m.group(1).decode(errors="ignore") in d.url:
            kind = "meta_refresh"
        elif d.initiator_type == "script" or (prev.body and _JS_LOC.search(prev.body)):
            kind = "js_navigation"
        else:
            kind = "js_navigation" if prev.status and prev.status < 300 else "http_redirect"
        chain.append(HopDraft(url=d.url, kind=kind, status=d.status, ip=d.server_ip, at=d.started))
        prev = d
    # frames are recorded separately so the top chain stays clean
    for f in (e for e in har.entries if e.resource_type == "frame"):
        chain.append(HopDraft(url=f.url, kind="frame", status=f.status, ip=f.server_ip, at=f.started))
    if chain:
        last_top = max((i for i, h in enumerate(chain) if h.kind != "frame"), default=0)
        if last_top > 0:
            chain[last_top].kind = chain[last_top].kind if chain[last_top].kind != "entry" else "final"
    return chain


def main_document(har: Har) -> HarEntry | None:
    """The last successful top-level document (what the visitor ended up seeing)."""
    docs = [e for e in har.entries if e.resource_type == "document" and e.status and e.status < 300 and e.body]
    return docs[-1] if docs else next((e for e in har.entries if e.resource_type == "document"), None)
