"""Input shapes -> item directories the extractor understands (DATA_NOTES.md §1–2).

Handled: sample_v1 dirs (HTML + `_files` + HAR + screenshot), organizer capture bundle (`archive_*/archive_info.json`),
capture-tool dir (`manifest.json` + dom.html + page.har), multi-HAR click chains, `strona_N` funnels, iPhone
screenshots, video + yt-dlp `.info.json`, a single URL (url.txt / .url / argument), loose single files (HAR, HTML,
screenshot, video), and zip uploads (safe extraction: no absolute paths, no `..`, size cap).
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

MAX_UNZIP_BYTES = 4 * 1024 ** 3
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)
SKIP_NAMES = {"__MACOSX", ".DS_Store", "Thumbs.db", "desktop.ini"}


@dataclass
class Item:
    name: str          # item id candidate (folder name)
    path: Path         # directory with the material
    kind: str          # sample_dir | bundle | capture_tool | url | har | screenshot | video | upload
    url: str | None = None


def safe_unzip(zp: str | Path, dest: str | Path) -> Path:
    """Extract a zip without path traversal (experiments/safe_unzip.py rules). Polish names in cp437/cp852 mojibake
    are kept as stored (the extractor always lists, never reconstructs names)."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    total = 0
    with zipfile.ZipFile(zp) as z:
        for info in z.infolist():
            name = info.filename
            if not (info.flag_bits & 0x800):          # not UTF-8 flagged: try cp852 (Windows PL zips)
                try:
                    name = name.encode("cp437").decode("cp852") if any(ord(c) > 127 for c in name) else name
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass
            parts = [p for p in re.split(r"[\\/]+", name) if p not in ("", ".")]
            if not parts or any(p == ".." for p in parts) or name.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", name):
                continue
            if parts[0] in SKIP_NAMES:
                continue
            target = dest.joinpath(*parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            total += info.file_size
            if total > MAX_UNZIP_BYTES:
                raise ValueError("zip too large")
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
    return dest


def _visible(p: Path) -> list[Path]:
    return sorted(x for x in p.iterdir() if x.name not in SKIP_NAMES and not x.name.startswith("."))


def descend(root: Path) -> Path:
    """Skip wrapper folders: while the root holds exactly one directory and no files, go into it."""
    while True:
        kids = _visible(root)
        dirs = [k for k in kids if k.is_dir()]
        files = [k for k in kids if k.is_file()]
        if len(dirs) == 1 and not files and not _is_item_dir(dirs[0], strict=True):
            root = dirs[0]
            continue
        return root


def _is_item_dir(d: Path, strict: bool = False) -> bool:
    """A directory that is itself one incident (has material at top level)."""
    if (d / "archive_info.json").is_file() or (d / "manifest.json").is_file():
        return True
    names = [x.name.lower() for x in _visible(d) if x.is_file()]
    material = any(n.endswith((".har", ".html", ".htm", ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".webm"))
                   or n.endswith(".info.json") for n in names)
    if strict:
        return material
    return material or any(x.is_dir() and x.name.endswith("_files") for x in _visible(d))


def classify(d: Path) -> str:
    from trop.extract.rules import is_bundle, is_capture_tool
    if is_bundle(str(d)):
        return "bundle"
    if is_capture_tool(str(d)):
        return "capture_tool"
    names = [x.name.lower() for x in _visible(d) if x.is_file()]
    if any(n.endswith(".info.json") for n in names) or (any(n.endswith((".mp4", ".mov", ".webm")) for n in names)
                                                        and not any(n.endswith((".har", ".html", ".htm")) for n in names)):
        return "video"
    if not any(n.endswith((".har", ".html", ".htm", ".png", ".jpg", ".jpeg", ".webp")) for n in names) and _url_in(d):
        return "url"
    if names and all(n.endswith((".png", ".jpg", ".jpeg", ".webp")) for n in names) and not any(x.is_dir() for x in _visible(d)):
        return "screenshot"
    return "sample_dir"


def _url_in(d: Path) -> str | None:
    for x in _visible(d):
        if x.is_file() and x.suffix.lower() in (".txt", ".url", ".webloc") and x.stat().st_size < 65536:
            m = URL_RE.search(x.read_text(encoding="utf-8", errors="replace"))
            if m:
                return m.group(0)
    return None


def wrap_file(f: Path, workdir: Path) -> Path:
    """A loose file becomes a one-file item directory (symlink, so nothing is copied)."""
    d = workdir / re.sub(r"[^\w.-]+", "_", f.stem)[:60]
    d.mkdir(parents=True, exist_ok=True)
    link = d / f.name
    if not link.exists():
        try:
            link.symlink_to(f.resolve())
        except OSError:
            shutil.copy2(f, link)
    return d


def url_item(url: str, workdir: Path) -> Path:
    d = workdir / (re.sub(r"[^\w.-]+", "_", re.sub(r"^https?://", "", url))[:60] or "url")
    d.mkdir(parents=True, exist_ok=True)
    (d / "url.txt").write_text(url, encoding="utf-8")
    return d


def single_item(path: str | Path, workdir: Path | None = None) -> Item:
    """One analysis input (`trop analyze`/`ingest`): a dir, a zip of one incident, a loose file or a URL."""
    workdir = Path(workdir or tempfile.mkdtemp(prefix="trop-ingest-"))
    s = str(path)
    if URL_RE.fullmatch(s.strip()):
        d = url_item(s.strip(), workdir)
        return Item(d.name, d, "url", url=s.strip())
    p = Path(path)
    if p.is_file() and p.suffix.lower() == ".zip":
        root = descend(safe_unzip(p, workdir / p.stem))
        return Item(p.stem, root, "upload")
    if p.is_file():
        d = wrap_file(p, workdir)
        kind = {".har": "har", ".mp4": "video", ".mov": "video", ".webm": "video"}.get(p.suffix.lower(),
                                                                                        "screenshot" if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") else "upload")
        return Item(p.stem, d, kind)
    k = classify(p)
    return Item(p.name, p, k, url=_url_in(p) if k == "url" else None)


def batch_items(path: str | Path, workdir: Path | None = None) -> list[Item]:
    """Every immediate sub-folder (or zip member folder) is one item; loose files are one item each."""
    workdir = Path(workdir or tempfile.mkdtemp(prefix="trop-batch-"))
    p = Path(path)
    if p.is_file() and p.suffix.lower() == ".zip":
        p = safe_unzip(p, workdir / "unzipped")
    root = descend(p)
    items = []
    for x in _visible(root):
        if x.is_dir():
            if x.name.endswith("_files"):
                continue
            items.append(Item(x.name, x, classify(x)))
        elif x.is_file():
            if x.suffix.lower() == ".zip":
                sub = descend(safe_unzip(x, workdir / x.stem))
                items.append(Item(x.stem, sub, "upload"))
            elif x.suffix.lower() in (".har", ".html", ".htm", ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".webm"):
                items.append(Item(x.stem, wrap_file(x, workdir / "files"), "upload"))
    if not items and _is_item_dir(root):
        items.append(Item(root.name, root, classify(root)))
    return items


def natural_key(name: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]


def cleanup(workdir: str | Path) -> None:
    if workdir and os.path.isdir(workdir):
        shutil.rmtree(workdir, ignore_errors=True)
