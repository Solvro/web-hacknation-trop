"""Adapter for the organizer archive-bundle layout (also the layout our own capture worker writes).

archive_<host>_<YYYYMMDD_HHMMSS>/          (directory or .zip, optional sibling .zip.sha256)
  archive_info.json   {url, timestamp_utc, title, user_agent, [+ redpill extras]}
  dns_ssl.json        {hostname, ip, all_addresses, ssl: <python ssl.getpeercert() dict>}
  metadata.json       {title, meta_tags, links, scripts, images}
  page_text.txt · html/rendered.html · html/source.html · network.har
  screenshots/full_page.png · screenshots/viewport.png · page.pdf · page.mhtml
  storage/cookies.json · storage/localStorage.json · storage/sessionStorage.json
  sha256.json         {relative path (\\ or /): sha256}
  RED PILL extensions (optional, ignored by other tools): redirects.json, favicon.json + favicon.*,
  forms.json, outlinks.json, console.json, media/manifest.json + media/*
"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from ..util.hashing import favicon_mmh3, sha256_bytes
from .capture_builder import build_capture
from .extract import cdn_of, tls_hits
from .har import load_har
from .model import ArtifactDraft, CaptureDraft, HopDraft, IncidentDraft, ObsHit, RelationDraft

ROLE_BY_PATH = {
    "archive_info.json": "archive_info_json", "dns_ssl.json": "dns_ssl_json", "metadata.json": "metadata_json",
    "page_text.txt": "landing_text", "html/rendered.html": "landing_html_rendered",
    "html/source.html": "landing_html_source", "network.har": "landing_har",
    "screenshots/full_page.png": "landing_screenshot_full", "screenshots/viewport.png": "landing_screenshot_viewport",
    "page.pdf": "landing_pdf", "page.mhtml": "landing_mhtml", "storage/cookies.json": "storage_cookies",
    "storage/localStorage.json": "storage_local", "storage/sessionStorage.json": "storage_session",
    "sha256.json": "sha256_manifest",
}


class BundleFS:
    """Uniform read access to a bundle directory or zip."""

    def __init__(self, path: Path):
        self.path = path
        self.zip: zipfile.ZipFile | None = None
        self.prefix = ""
        if path.is_file() and path.suffix.lower() == ".zip":
            self.zip = zipfile.ZipFile(path)
            names = self.zip.namelist()
            info = next((n for n in names if n.endswith("archive_info.json")), None)
            self.prefix = info[: -len("archive_info.json")] if info else ""

    def list(self) -> list[str]:
        if self.zip:
            return [n[len(self.prefix):] for n in self.zip.namelist() if n.startswith(self.prefix) and not n.endswith("/")]
        return [p.relative_to(self.path).as_posix() for p in self.path.rglob("*") if p.is_file()]

    def read(self, rel: str) -> bytes | None:
        rel = rel.replace("\\", "/")
        try:
            if self.zip:
                return self.zip.read(self.prefix + rel)
            p = self.path / rel
            return p.read_bytes() if p.is_file() else None
        except KeyError:
            return None

    def json(self, rel: str):
        b = self.read(rel)
        if b is None:
            return None
        try:
            return json.loads(b.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return None


def is_bundle(path: Path) -> bool:
    if path.is_dir():
        return (path / "archive_info.json").is_file()
    if path.is_file() and path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(path) as z:
                return any(n.endswith("archive_info.json") for n in z.namelist())
        except zipfile.BadZipFile:
            return False
    return False


def _ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def load_bundle(path: Path, cap_ref: str) -> tuple[CaptureDraft, list[ObsHit], list[RelationDraft], dict]:
    fs = BundleFS(path)
    files = fs.list()
    info = fs.json("archive_info.json") or {}
    dns_ssl = fs.json("dns_ssl.json") or {}
    manifest = fs.json("sha256.json") or {}
    quality: dict = {"available": [], "missing": [], "errors": []}

    # integrity: verify the bundle's own sha256 manifest
    bad = []
    for rel, sha in manifest.items():
        b = fs.read(rel)
        if b is None:
            bad.append(f"missing:{rel}")
        elif sha256_bytes(b) != sha:
            bad.append(f"sha_mismatch:{rel}")
    if bad:
        quality["errors"].append({"bundle_integrity": bad})

    har_bytes = fs.read("network.har")
    har = load_har(data=har_bytes) if har_bytes else None
    html = fs.read("html/rendered.html") or fs.read("html/source.html")
    html_role = "landing_html_rendered" if fs.read("html/rendered.html") else "landing_html_source"
    # the rendered DOM is the authoritative text source for bundles
    cap, hits, rels = build_capture(
        har=har, har_artifact=None, html=html, html_role=html_role,
        html_rel="html/rendered.html" if html_role == "landing_html_rendered" else "html/source.html",
        files_dir=None, fallback_url=info.get("url"), fallback_time=_ts(info.get("timestamp_utc")),
        cap_ref=cap_ref, tool=info.get("tool") or "organizer-bundle")
    cap.title = cap.title or info.get("title")
    cap.user_agent = info.get("user_agent") or cap.user_agent
    cap.tool_version = info.get("tool_version") or cap.tool_version
    cap.profile = info.get("profile")
    cap.referer = info.get("referer") or cap.referer
    cap.captured_at = _ts(info.get("timestamp_utc")) or cap.captured_at
    if info.get("final_url"):
        cap.final_url = info["final_url"]
    if info.get("status"):
        cap.final_status = info["status"]
    redirects = fs.json("redirects.json")
    if redirects:  # our capture's chain is authoritative (it saw JS/meta hops the HAR cannot show)
        cap.hops = [HopDraft(url=h["url"], kind=h.get("kind", "js_navigation"), status=h.get("status"),
                             ip=h.get("ip"), at=_ts(h.get("at"))) for h in redirects
                    if h.get("url", "").startswith(("http://", "https://"))]
    hint = info.get("page_role_hint")
    if hint in ("error", "blocked"):
        cap.page_role, cap.cloak_verdict = hint, ("blocked" if hint == "blocked" else "error")
        cap.error = info.get("error")
    if info.get("challenge_detected"):
        cap.meta["challenge_detected"] = True

    # TLS + DNS from dns_ssl.json
    host = dns_ssl.get("hostname")
    if dns_ssl.get("ssl"):
        cap.tls = dns_ssl["ssl"]
        th, tr = tls_hits(dns_ssl["ssl"], host, {"capture": cap_ref}, "bundle.dns_ssl")
        hits += th
        rels += tr
    for ip in dns_ssl.get("all_addresses") or ([dns_ssl["ip"]] if dns_ssl.get("ip") else []):
        cdn = cdn_of(ip)
        hits.append(ObsHit("ip", ip, "bundle.dns", context={"capture": cap_ref, "host": host},
                           noise_reason=f"cdn:{cdn}" if cdn else None, attrs={"cdn": cdn}))
        if host:
            rels.append(RelationDraft(("fqdn", host), "resolves_to", ("ip", ip), "bundle",
                                      {"at": info.get("timestamp_utc")}))

    fav = fs.json("favicon.json")
    if fav and fav.get("mmh3") is not None:
        hits.append(ObsHit("favicon_mmh3", str(fav["mmh3"]), "bundle.favicon", context={"capture": cap_ref, "url": fav.get("url")}))

    # artifacts: every file in the bundle, with a role
    for rel in files:
        role = ROLE_BY_PATH.get(rel)
        if role is None:
            if rel.startswith("favicon."):
                role = "favicon"
            elif rel.startswith("media/") and not rel.endswith(".json"):
                role = "media_video" if rel.lower().endswith((".mp4", ".webm", ".ts", ".m3u8")) else "media_audio"
            elif rel.startswith("screenshots/"):
                role = "landing_screenshot_full"
            else:
                role = "other"
        data = fs.read(rel)
        if data is None:
            continue
        cap.artifacts.append(ArtifactDraft(role=role, data=data, rel_path=rel))
        if role == "favicon" and not fav:
            hits.append(ObsHit("favicon_mmh3", str(favicon_mmh3(data)), "bundle.favicon", context={"capture": cap_ref}))
    if path.is_file():
        cap.artifacts.append(ArtifactDraft(role="bundle_zip", path=path, rel_path=path.name))

    cap.meta.update({"bundle": path.name, "files": sorted(files), "archive_info": info})
    quality["available"] = sorted({ROLE_BY_PATH.get(f, f) for f in files})
    if cap.cloak_verdict in ("error", "blocked"):
        quality["errors"].append({"landing": cap.page_role, "title": cap.title})
    return cap, hits, rels, quality


def _etld1(url: str) -> str:
    from ..util.urls import etld1_of, host_of
    return etld1_of(host_of(url))


def bundle_incident(path: Path, source_key: str, source_ref: str | None = None) -> IncidentDraft:
    """A standalone bundle (our capture, a hunter hit, DANE if it ships bundles) → one incident."""
    ref = source_ref or path.stem
    cap, hits, rels, quality = load_bundle(path, cap_ref="c0")
    from .sample_dir import finalize_content
    inc = IncidentDraft(source_key=source_key, source_ref=ref, kind="landing_only",
                        observed_at=cap.captured_at, entry_url=cap.entry_url, captures=[cap],
                        observables=hits, relations=rels, quality=quality)
    finalize_content(inc)
    return inc
