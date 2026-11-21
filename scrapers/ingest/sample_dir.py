"""Adapter for the organizer's per-incident folder layout (sample_v1 p1…p15, DANE 1…61).

<N>/
  Zrzut ekranu YYYY-MM-DD HHMMSS.png | reklama_*.png   ad screenshot                          → ad_screenshot
  IMG_####.PNG                                         phone screenshots (feed, funnel)       → device_screenshot
  <domain>.har                                         DevTools HAR of the landing visit      → capture (devtools-har)
  <title>.html + <title>_files/                        'Save page as… complete'               → same capture (merged)
  archive_<domain>_<ts>/ (+ .zip, .zip.sha256)         organizer bundle                       → extra capture
  <name>/<name>/{manifest.json,dom.html,page.har,…}    'page-capture' tool (DANE)              → extra capture
  strona_1/ strona_2/ …                                funnel steps, each HAR + saved page    → ordered captures
  <title> [<ad_archive_id>_<n>].mp4 + .info.json       ad video downloaded with yt-dlp        → ad (library id) + video
  ScreenRecording… .MP4 | Nagrywanie ekranu… .mp4      screen recording of the journey        → screen_recording
  *.txt                                                notes, e.g. video_deleted.txt          → quality flags
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from ..util.hashing import sha256_bytes
from ..util.text import (classify_narrative, find_brands, find_contacts, find_persons, guess_lang,
                         headline_template, product_from_title)
from ..util.urls import etld1_of, host_of
from .bundle import is_bundle, load_bundle
from .capture_builder import build_capture
from .har import load_har
from .html import parse_html
from .model import AdDraft, ArtifactDraft, IncidentDraft, ObsHit, RelationDraft
from .page_capture import find_page_captures, load_page_capture

SHOT_RE = re.compile(r"(?:Zrzut ekranu|Screenshot)[ _-]*(\d{4}-\d{2}-\d{2})[ _-]*(\d{2})[.:]?(\d{2})[.:]?(\d{2})", re.I)
REC_RE = re.compile(r"(?:Nagrywanie ekranu|ScreenRecording)[ _-]*(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4})[ _-]*(\d{2})[.:-]?(\d{2})[.:-]?(\d{2})", re.I)
WARSAW = ZoneInfo("Europe/Warsaw")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".heic"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v", ".mkv"}
AD_SHOT_RE = re.compile(r"(zrzut ekranu|screenshot|reklama|^ad[_ -])", re.I)
DEVICE_SHOT_RE = re.compile(r"^(IMG|Screenshot_\d{8})[_-]?\d+", re.I)
SCREEN_REC_RE = re.compile(r"(screen ?recording|nagrywanie ekranu|nagranie ekranu)", re.I)
LIBRARY_ID_RE = re.compile(r"\[(\d{13,17})(?:_\d+)?\]")
FUNNEL_RE = re.compile(r"^(?:strona|step|krok|page)[ _-]?(\d+)$", re.I)
INCIDENT_FILE_EXT = {".har", ".html", ".htm", ".mp4", ".mov", ".json"} | IMAGE_EXT


def _looks_like_incident(d: Path) -> bool:
    files = [f for f in d.iterdir() if f.is_file()]
    if any(f.suffix.lower() in INCIDENT_FILE_EXT for f in files) or any(is_bundle(c) for c in d.iterdir()):
        return True
    return any(c.is_dir() and not c.name.endswith("_files") and any(x.suffix.lower() in (".har", ".html", ".htm") for x in c.iterdir() if x.is_file())
               for c in d.iterdir())


def discover(root: Path) -> list[Path]:
    """Incident folders = subdirectories holding landing material, ad media or funnel/capture subfolders."""
    out = [d for d in root.iterdir() if d.is_dir() and _looks_like_incident(d)]
    return sorted(out, key=lambda p: (len(p.name), p.name))


def _date_time(m: re.Match | None) -> datetime | None:
    if not m:
        return None
    day = m.group(1)
    if re.match(r"\d{2}-\d{2}-\d{4}", day):          # ScreenRecording_08-12-2026 = MM-DD-YYYY (iOS)
        mm, dd, yyyy = day.split("-")
        day = f"{yyyy}-{mm}-{dd}"
    try:
        return datetime.strptime(f"{day} {m.group(2)}{m.group(3)}{m.group(4)}", "%Y-%m-%d %H%M%S").replace(tzinfo=WARSAW)
    except ValueError:
        return None


def _landing_captures(folder: Path, ci: int, fallback_time: datetime | None, rel_base: Path,
                      step: int | None = None) -> tuple[list, list, list, int, int, int]:
    """HAR + saved-page pairing inside one directory (top level or one funnel step)."""
    files = [f for f in folder.iterdir() if f.is_file()]
    hars = sorted(f for f in files if f.name.lower().endswith(".har"))   # incl. a bare ".har" (dotfile, no suffix)
    htmls = sorted(f for f in files if f.suffix.lower() in (".html", ".htm"))
    rel = lambda p: p.relative_to(rel_base).as_posix()
    caps, hits, rels = [], [], []
    parsed = {h: parse_html(h.read_bytes()) for h in htmls}
    used: set[Path] = set()
    for har_path in hars:
        har = load_har(har_path)
        site = etld1_of(host_of(next((e.url for e in har.entries if e.resource_type == "document"), "")))
        match = next((h for h in htmls if h not in used and parsed[h].saved_from
                      and etld1_of(host_of(parsed[h].saved_from)) == site), None)
        if match is None and len(htmls) == 1 and len(hars) == 1 and htmls[0] not in used:
            match = htmls[0]
        if match:
            used.add(match)
        cap, h, r = build_capture(
            har=har, har_artifact=ArtifactDraft(role="landing_har", path=har_path, rel_path=rel(har_path), mime="application/json"),
            html=match.read_bytes() if match else None, html_role="landing_html_saved",
            html_rel=rel(match) if match else None, files_dir=_files_dir(match) if match else None, fallback_url=None,
            fallback_time=fallback_time, cap_ref=f"c{ci}", tool=har.tool + ("+save-as" if match else ""))
        caps.append(cap); hits += h; rels += r; ci += 1
    for hp in htmls:
        if hp in used:
            continue
        cap, h, r = build_capture(
            har=None, har_artifact=None, html=hp.read_bytes(), html_role="landing_html_saved", html_rel=rel(hp),
            files_dir=_files_dir(hp), fallback_url=None, fallback_time=fallback_time, cap_ref=f"c{ci}",
            tool="browser-save-as")
        caps.append(cap); hits += h; rels += r; ci += 1
    if step is not None:
        for c in caps:
            c.meta["funnel_step"] = step
    return caps, hits, rels, ci, len(hars), len(htmls)


def _shot_time(name: str) -> datetime | None:
    m = SHOT_RE.search(name)
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)}{m.group(3)}{m.group(4)}", "%Y-%m-%d %H%M%S").replace(tzinfo=WARSAW)
    except ValueError:
        return None


def load_incident(folder: Path, source_key: str = "sample_v1", ref_prefix: str = "sample_v1") -> IncidentDraft:
    files = [f for f in folder.iterdir() if f.is_file()]
    images = sorted(f for f in files if f.suffix.lower() in IMAGE_EXT)
    ad_shots = [f for f in images if AD_SHOT_RE.search(f.name) or not DEVICE_SHOT_RE.search(f.name)]
    device_shots = [f for f in images if f not in ad_shots]
    videos = sorted(f for f in files if f.suffix.lower() in VIDEO_EXT)
    infos = sorted(f for f in files if f.name.endswith(".info.json"))
    notes = sorted(f for f in files if f.suffix.lower() == ".txt")
    bundle_dirs = sorted(d for d in folder.iterdir() if d.is_dir() and is_bundle(d))
    bundle_zips = sorted(f for f in files if f.suffix.lower() == ".zip" and is_bundle(f))
    page_caps = find_page_captures(folder)
    funnel = sorted(((int(FUNNEL_RE.match(d.name).group(1)), d) for d in folder.iterdir()
                     if d.is_dir() and FUNNEL_RE.match(d.name)), key=lambda t: t[0])
    rel = lambda p: p.relative_to(folder).as_posix()

    inc = IncidentDraft(source_key=source_key, source_ref=f"{ref_prefix}/{folder.name}", kind="landing_only")
    q = inc.quality
    shot_time = next((t for t in (_date_time(SHOT_RE.search(f.name)) for f in ad_shots) if t), None)
    rec_time = next((t for t in (_date_time(REC_RE.search(f.name)) for f in videos) if t), None)
    fallback_time = shot_time or rec_time

    # --- ad: screenshot(s), downloaded ad video (+ yt-dlp info.json carrying the Ad Library id) ---
    ad_arts: list[ArtifactDraft] = [ArtifactDraft(role="ad_screenshot", path=p, rel_path=rel(p)) for p in ad_shots]
    library_id, ad_raw = None, {}
    for info in infos:
        try:
            d = json.loads(info.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        m = re.search(r"[?&]id=(\d{13,17})", str(d.get("webpage_url") or "")) or re.match(r"(\d{13,17})", str(d.get("id") or ""))
        library_id = library_id or (m.group(1) if m else None)
        ad_raw = {k: d.get(k) for k in ("id", "title", "fulltitle", "webpage_url", "extractor", "duration", "uploader",
                                        "playlist_title", "thumbnail") if d.get(k) is not None}
        ad_arts.append(ArtifactDraft(role="ad_info_json", path=info, rel_path=rel(info), mime="application/json"))
    for v in videos:
        if SCREEN_REC_RE.search(v.name):
            inc.artifacts.append(ArtifactDraft(role="screen_recording", path=v, rel_path=rel(v), mime="video/mp4"))
            q["available"].append("screen_recording")
            continue
        m = LIBRARY_ID_RE.search(v.name)
        library_id = library_id or (m.group(1) if m else None)
        ad_arts.append(ArtifactDraft(role="ad_creative_video", path=v, rel_path=rel(v), mime="video/mp4"))
    for d in device_shots:
        inc.artifacts.append(ArtifactDraft(role="device_screenshot", path=d, rel_path=rel(d)))
    if device_shots:
        q["available"].append("device_screenshots")
    if ad_arts or library_id:
        inc.ad = AdDraft(platform="meta", library_id=library_id, artifacts=ad_arts, raw={"yt_dlp": ad_raw} if ad_raw else {},
                         title=ad_raw.get("title"))
        q["available"].append("ad_screenshot" if ad_shots else "ad_media")
        if library_id:
            inc.observables.append(ObsHit("meta_ad_id", library_id, "ad.library_id", context={"source": "filename/info.json"}))
    else:
        q["missing"].append("ad_screenshot")

    # --- landing captures: top level, then funnel steps, page-capture dirs, organizer bundles ---
    caps, hits, rels, ci, n_har, n_html = _landing_captures(folder, 0, fallback_time, folder)
    prev_final: str | None = None
    for step, d in funnel:
        c2, h2, r2, ci, a, b = _landing_captures(d, ci, fallback_time, folder, step=step)
        n_har += a; n_html += b
        if c2:
            first = host_of(c2[0].hops[0].url if c2[0].hops else c2[0].entry_url)
            if prev_final and first and prev_final != first:
                r2.append(RelationDraft(("fqdn", prev_final), "redirects_to", ("fqdn", first), "funnel", {"step": step}))
            prev_final = host_of(c2[-1].final_url or c2[-1].entry_url) or prev_final
        caps += c2; hits += h2; rels += r2
    if funnel:
        q["available"].append(f"funnel_steps:{len(funnel)}")
    for d in page_caps:
        cap, h, r = load_page_capture(d, f"c{ci}", rel_base=folder)
        caps.append(cap); hits += h; rels += r; ci += 1
        q["available"].append("page_capture")
        n_har += 1 if (d / "page.har").is_file() else 0
    inc.captures += caps
    inc.observables += hits
    inc.relations += rels
    q["available" if n_har else "missing"].append("landing_har")
    q["available" if n_html else "missing"].append("landing_html_saved")

    seen_bundles = {d.name for d in bundle_dirs}
    for b in bundle_dirs + [z for z in bundle_zips if z.stem not in seen_bundles]:
        cap, h, r, bq = load_bundle(b, cap_ref=f"c{ci}")
        inc.captures.append(cap)
        inc.observables += h
        inc.relations += r
        q["errors"] += bq["errors"]
        q["available"].append("archive_bundle")
        ci += 1
    for z in bundle_zips:
        side = z.with_name(z.name + ".sha256")
        if side.is_file():
            want = side.read_text(errors="ignore").split()[0].lower()
            if sha256_bytes(z.read_bytes()) != want:
                q["errors"].append({"bundle_zip_sha256_mismatch": z.name})
            inc.artifacts.append(ArtifactDraft(role="note", path=side, rel_path=side.name))
        if z.stem in seen_bundles:  # keep the original zip as evidence even when the dir was used
            inc.artifacts.append(ArtifactDraft(role="bundle_zip", path=z, rel_path=z.name))

    for n in notes:
        inc.artifacts.append(ArtifactDraft(role="note", path=n, rel_path=n.name, mime="text/plain"))
        q["errors"].append({"note": n.stem})  # e.g. video_deleted

    has_ad, has_landing = inc.ad is not None, bool(inc.captures)
    inc.kind = "ad+landing" if has_ad and has_landing else ("ad_only" if has_ad else "landing_only")

    times = [c.captured_at for c in inc.captures if c.meta.get("captured_at_source") != "ingest_time"]         + [t for t in (shot_time, rec_time) if t]
    inc.observed_at = min(times) if times else None
    if inc.observed_at is None:
        q["missing"].append("observed_at")
    finalize_content(inc)
    return inc


def _files_dir(html: Path) -> Path | None:
    d = html.with_name(html.stem + "_files")
    return d if d.is_dir() else None


def finalize_content(inc: IncidentDraft) -> None:
    """Incident-level content fields from the best capture (served page with the most text)."""
    if not inc.captures:
        return
    served = [c for c in inc.captures if c.cloak_verdict not in ("error", "blocked")] or inc.captures
    best = max(served, key=lambda c: len(c.page_text or ""))
    web = [c for c in inc.captures if (c.entry_url or '').startswith(('http://', 'https://'))]
    # entry = first real web URL of the journey (funnel step order, then capture order), not a local about: page
    first = min(web, key=lambda c: (c.meta.get('funnel_step') or 0)) if web else best
    inc.entry_url = inc.entry_url or (first.entry_url if web else None)
    inc.title = best.title
    inc.headline = best.title
    inc.headline_template = headline_template(best.title)
    text = (best.title or "") + "\n" + (best.page_text or "")
    inc.lang = guess_lang(text)
    inc.narrative, inc.vertical = classify_narrative(text)
    ctx = {"capture": "best", "title": best.title}
    if inc.headline_template and best.cloak_verdict not in ("error", "blocked"):
        # short generic titles still link incidents (p8↔p11); rarity decides how much that is worth
        conf = 1.0 if len(inc.headline_template) > 25 else 0.5
        inc.observables.append(ObsHit("headline_template", inc.headline_template, "content.title",
                                      display=best.title, context=ctx, confidence=conf))
    for name, role, conf, _ in find_persons(text[:20000]):
        inc.observables.append(ObsHit("person", name, "content.text", confidence=conf, context=ctx, attrs={"role": role}))
    for b in find_brands(text[:20000]):
        inc.observables.append(ObsHit("brand", b.lower(), "content.text", display=b, context=ctx))
    p = product_from_title(best.title)
    if p:
        inc.observables.append(ObsHit("product", p.lower(), "content.title", display=p, context=ctx))
    for typ, val, disp in find_contacts(best.page_text or ""):
        inc.observables.append(ObsHit(typ, val, "content.text", display=disp, context=ctx, confidence=0.8))
    if not inc.observed_at and best.meta.get("captured_at_source") != "ingest_time":
        inc.observed_at = best.captured_at
