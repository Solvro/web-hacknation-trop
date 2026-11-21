"""Shared logic that turns raw landing material (HAR and/or HTML) into a CaptureDraft + observables.
Used by every adapter (sample_dir, archive bundle, our own Playwright capture)."""
from __future__ import annotations

import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path

from ..util.hashing import minhash, sha256_bytes, simhash64
from ..util.text import normalize_text
from ..util.urls import etld1_of, host_of
from .extract import domain_hits, extract_from_har, extract_from_html, url_observables
from .har import Har, navigation_chain
from .html import ParsedHtml, parse_html
from .model import ArtifactDraft, CaptureDraft, ObsHit, RelationDraft

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".bmp", ".ico", ".svg"}
SCRIPT_EXT = {".js", ".mjs"}
MEDIA_EXT = {".mp4", ".webm", ".mp3", ".m4a", ".ogg", ".wav", ".m3u8", ".ts"}


def clean_ext(name: str) -> str:
    """Chrome 'save as complete' (Polish locale) appends '.pobrane' ('downloaded') to scripts."""
    n = name.lower()
    for junk in (".pobrane", ".pobierz", ".download", ".descarga", ".téléchargement"):
        if n.endswith(junk):
            n = n[: -len(junk)]
    return Path(n).suffix


def classify_page(status: int | None, title: str | None, text: str, forms: list[dict]) -> tuple[str, str]:
    """-> (page_role, cloak_verdict)"""
    t = (title or "").lower()
    body = text[:3000].lower()
    if status and status >= 500 or re.search(r"\b(502|503|504|bad gateway|origin error)\b", t):
        return "error", "error"
    if "just a moment" in t or "attention required" in t or "cf-chl" in body or "verify you are human" in body:
        return "blocked", "blocked"
    if status and status in (404, 410):
        return "error", "error"        # gone / taken down; whether it is cloaking is decided by victim-vs-bot pairs
    if status and status in (403, 451):
        return "blocked", "blocked"
    if re.search(r"(domain|this site) (is )?(for sale|parked)|parking", body):
        return "parked", "unknown"
    phoneish = any(any(re.search(r"phone|tel|telefon|name|imie|imię|email", f.lower()) for f in fm.get("fields", []))
                   for fm in forms)
    if phoneish:
        return "order_form", "served"
    if len(body) < 200:
        return "unknown", "unknown"
    return "prelander", "served"


def text_fingerprints(cap: CaptureDraft, doc: ParsedHtml | None, rendered: bytes | None) -> None:
    if doc:
        cap.page_text = doc.text
        norm = normalize_text(doc.text)
        cap.text_sha256 = sha256_bytes(norm.encode()) if norm else None
        cap.text_simhash = simhash64(norm) if norm else None
        cap.dom_minhash = minhash(doc.tag_shingles)
        cap.forms = doc.forms
        cap.outlinks = list(dict.fromkeys(doc.outlinks))[:500]
        cap.meta.setdefault("meta_tags", doc.meta[:50])
        cap.meta.setdefault("signatures", doc.signatures)
    if rendered:
        cap.dom_sha256 = sha256_bytes(rendered)


def build_capture(
    *, har: Har | None, har_artifact: ArtifactDraft | None, html: bytes | None, html_role: str,
    html_rel: str | None, files_dir: Path | None, fallback_url: str | None, fallback_time: datetime | None,
    cap_ref: str, tool: str | None = None,
) -> tuple[CaptureDraft, list[ObsHit], list[RelationDraft]]:
    hits: list[ObsHit] = []
    rels: list[RelationDraft] = []
    chain = navigation_chain(har) if har else []
    doc = parse_html(html, base_url=fallback_url) if html else None
    entry_url = (chain[0].url if chain else None) or (doc.saved_from if doc else None) or fallback_url or ""
    top = [h for h in chain if h.kind != "frame"]
    final = top[-1] if top else None
    captured_at = (chain[0].at if chain and chain[0].at else None) or fallback_time
    time_source = "har" if chain and chain[0].at else ("fallback" if fallback_time else "ingest_time")
    # captures.captured_at is NOT NULL (partition key): an unknown time is stored as ingest time and flagged,
    # and the incident's observed_at stays NULL (missing ≠ "now")
    captured_at = captured_at or datetime.now(timezone.utc)

    cap = CaptureDraft(
        tool=tool or (har.tool if har else "browser-save-as"),
        tool_version=(har.creator_version if har else None),
        entry_url=entry_url, captured_at=captured_at,
        final_url=final.url if final else (doc.saved_from if doc else entry_url),
        final_status=final.status if final else None,
        hops=chain,
    )
    cap.meta["captured_at_source"] = time_source
    if har:
        cap.meta["har_browser"] = har.browser
        ua = next((e.req_headers.get("user-agent") for e in har.entries if e.req_headers.get("user-agent")), None)
        cap.user_agent = ua
        cap.locale = next((e.req_headers.get("accept-language") for e in har.entries if e.req_headers.get("accept-language")), None)
        cap.referer = next((e.req_headers.get("referer") for e in har.entries[:1] if e.req_headers.get("referer")), None)

    landing = {etld1_of(host_of(h.url)) for h in top if h.url.startswith("http")}
    if not landing and entry_url.startswith("http"):
        landing = {etld1_of(host_of(entry_url))}
    landing.discard("")

    # landing chain domains + URL-leaked campaign ids
    for i, h in enumerate(top):
        f = "landing.entry_url" if i == 0 else ("landing.final_url" if i == len(top) - 1 else "landing.redirect_hop")
        hits += domain_hits(host_of(h.url), f, {"capture": cap_ref, "hop": i, "url": h.url[:300]})
        hits += url_observables(h.url, f, {"capture": cap_ref, "hop": i})
    if not top and entry_url.startswith("http"):
        hits += domain_hits(host_of(entry_url), "landing.entry_url", {"capture": cap_ref, "url": entry_url[:300]})
        hits += url_observables(entry_url, "landing.entry_url", {"capture": cap_ref})
    for a, b in zip(top, top[1:]):
        ha, hb = host_of(a.url), host_of(b.url)
        if ha and hb and ha != hb:
            rels.append(RelationDraft(("fqdn", ha), "redirects_to", ("fqdn", hb), "har", {"kind": b.kind}))

    if har:
        h2, r2, reqs = extract_from_har(har, landing, cap_ref)
        hits += h2
        rels += r2
        cap.requests = reqs
        if har_artifact:
            cap.artifacts.append(har_artifact)

    rendered_bytes = html
    if doc is None and har:
        # no saved page: use the final document body from the HAR
        from .har import main_document
        md = main_document(har)
        if md and md.body:
            doc = parse_html(md.body, base_url=md.url)
            rendered_bytes = md.body
            html_role = "landing_html_source"
    if doc:
        hits += extract_from_html(doc, "html", {"capture": cap_ref}, landing)
        if rendered_bytes:
            from .extract import kit_ids_all
            for typ, val in sorted(kit_ids_all(rendered_bytes.decode("utf-8", errors="ignore"))):
                hits.append(ObsHit(typ, val, "html.kit_path", context={"capture": cap_ref}))
        cap.title = doc.title
        if html is not None:
            cap.artifacts.append(ArtifactDraft(role=html_role, data=html, rel_path=html_rel, mime="text/html"))
    text_fingerprints(cap, doc, rendered_bytes)
    cap.page_role, cap.cloak_verdict = classify_page(cap.final_status, cap.title, cap.page_text or "", cap.forms)

    # saved-page resource folder: assets keep their bytes → hashes match HAR bodies of other incidents
    if files_dir and files_dir.is_dir():
        for f in sorted(files_dir.rglob("*")):
            if not f.is_file():
                continue
            ext = clean_ext(f.name)
            rel = f"{files_dir.name}/{f.relative_to(files_dir).as_posix()}"
            data = f.read_bytes()
            if ext in (".html", ".htm", ".css") or len(data) < 256:
                continue  # browsers rewrite these when saving
            sha = sha256_bytes(data)
            hits.append(ObsHit("asset_sha256", sha, "saved_files", display=rel, context={"capture": cap_ref, "file": rel}))
            if ext in SCRIPT_EXT or ext == "" and data[:200].lstrip().startswith((b"/*", b"!function", b"(function", b"var ", b"window")):
                txt = data.decode("utf-8", errors="ignore")
                from .html import tracking_ids
                for typ, val in tracking_ids(txt):
                    hits.append(ObsHit(typ, val, "saved_files.script", context={"capture": cap_ref, "file": rel}))
            if re.fullmatch(r"\d{14,17}", f.name):  # connect.facebook.net/signals/config/<pixel> saved as <pixel>
                hits.append(ObsHit("fb_pixel", f.name, "saved_files.pixel_config", confidence=0.9,
                                   context={"capture": cap_ref, "file": rel}))
            if ext in IMAGE_EXT:
                mime = mimetypes.types_map.get(ext, "image/" + ext.lstrip("."))
                cap.artifacts.append(ArtifactDraft(role="asset_image", data=data, rel_path=rel, mime=mime))
            elif ext in MEDIA_EXT:
                cap.artifacts.append(ArtifactDraft(role="media_video", data=data, rel_path=rel))
    return cap, hits, rels
