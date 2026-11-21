"""Adapter for the third capture layout seen in DANE ('page-capture 0.1.0'):

<dir>/manifest.json   {tool, captured_at, page_url, title, user_agent, settings{autoscroll,…}, stats{…}}
<dir>/dom.html        rendered DOM
<dir>/page.har        HAR of the visit
<dir>/page.mhtml      MHTML snapshot
<dir>/screenshot.png  full-page screenshot
<dir>/resources/{document,image,media,script,stylesheet}/…   response bodies by type
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .capture_builder import build_capture
from .har import load_har
from .model import ArtifactDraft, CaptureDraft, ObsHit, RelationDraft


def is_page_capture(d: Path) -> bool:
    m = d / "manifest.json"
    if not (d.is_dir() and m.is_file()):
        return False
    try:
        return str(json.loads(m.read_text(encoding="utf-8", errors="replace")).get("tool", "")).startswith("page-capture")
    except (json.JSONDecodeError, OSError):
        return False


def find_page_captures(root: Path, max_depth: int = 3) -> list[Path]:
    out = []
    for m in root.rglob("manifest.json"):
        if len(m.relative_to(root).parts) <= max_depth + 1 and is_page_capture(m.parent):
            out.append(m.parent)
    return sorted(out)


def _ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def load_page_capture(d: Path, cap_ref: str, rel_base: Path | None = None) -> tuple[CaptureDraft, list[ObsHit], list[RelationDraft]]:
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8", errors="replace"))
    rel = (lambda p: p.relative_to(rel_base).as_posix()) if rel_base else (lambda p: p.name)
    har_p, dom_p = d / "page.har", d / "dom.html"
    har = load_har(har_p) if har_p.is_file() else None
    cap, hits, rels = build_capture(
        har=har, har_artifact=ArtifactDraft(role="landing_har", path=har_p, rel_path=rel(har_p), mime="application/json") if har else None,
        html=dom_p.read_bytes() if dom_p.is_file() else None, html_role="landing_html_rendered",
        html_rel=rel(dom_p), files_dir=(d / "resources") if (d / "resources").is_dir() else None,
        fallback_url=m.get("page_url"), fallback_time=_ts(m.get("captured_at")), cap_ref=cap_ref,
        tool="page-capture")
    cap.tool_version = m.get("tool")
    cap.user_agent = m.get("user_agent") or cap.user_agent
    cap.title = cap.title or m.get("title")
    if _ts(m.get("captured_at")):
        cap.captured_at = _ts(m.get("captured_at"))
        cap.meta["captured_at_source"] = "manifest"
    cap.meta["page_capture"] = {"settings": m.get("settings"), "stats": m.get("stats")}
    for name, role in (("screenshot.png", "landing_screenshot_full"), ("page.mhtml", "landing_mhtml"),
                       ("manifest.json", "capture_manifest")):
        p = d / name
        if p.is_file():
            cap.artifacts.append(ArtifactDraft(role=role, path=p, rel_path=rel(p)))
    return cap, hits, rels
