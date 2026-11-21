"""Multipart uploads of whole folders: sanitised relative paths, the tree rebuilt on disk, and the decision single item vs batch.

The web sends a dropped folder as many `files` parts whose filename is a relative path (`1/Zrzut ekranu ….png`, `1/x_files/a.js`).
`plan()` mirrors trop.ingest.adapters (`descend` / `_is_item_dir`) on a plain list of relative paths, so the same decision is made for a
multipart tree and for the member list of a zip:
  * one incident folder (material at its top level, possibly inside wrapper folders)  -> "single"
  * a folder of >= 2 item folders (e.g. do_udostępnienia/1..61)                         -> "batch"
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import PurePosixPath

MATERIAL_EXT = (".har", ".html", ".htm", ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".webm")
MAX_FILES = 20000
MAX_DEPTH = 14
SKIP = {"__macosx", ".ds_store", "thumbs.db", "desktop.ini"}
_CTRL = re.compile(r"[\x00-\x1f\x7f]")


class BadPath(ValueError):
    pass


def clean_rel(name: str) -> list[str]:
    """Relative upload path -> safe segments (NFC). Raises BadPath for traversal / absolute / empty paths."""
    n = unicodedata.normalize("NFC", (name or "").replace("\\", "/"))
    n = _CTRL.sub("", n)
    n = re.sub(r"^[A-Za-z]:", "", n)                      # windows drive letter
    parts = []
    for seg in n.split("/"):
        seg = seg.strip()
        if seg in ("", "."):
            continue
        if seg == "..":
            raise BadPath(f"path traversal in {name!r}")
        parts.append(seg[:200])
    if n.startswith("/") and not parts:
        raise BadPath(f"absolute path {name!r}")
    if not parts or len(parts) > MAX_DEPTH:
        raise BadPath(f"bad path {name!r}")
    if parts[0].lower() in SKIP or any(p.lower() in SKIP for p in parts):
        return []
    return parts


class _Node:
    def __init__(self) -> None:
        self.files: list[str] = []
        self.dirs: dict[str, "_Node"] = {}


def _tree(paths: list[list[str]]) -> _Node:
    root = _Node()
    for parts in paths:
        n = root
        for seg in parts[:-1]:
            n = n.dirs.setdefault(seg, _Node())
        n.files.append(parts[-1])
    return root


def _is_item(n: _Node) -> bool:
    names = [f.lower() for f in n.files]
    if "archive_info.json" in names or "manifest.json" in names:
        return True
    if any(x.endswith(MATERIAL_EXT) or x.endswith(".info.json") for x in names):
        return True
    return any(d.endswith("_files") for d in n.dirs)


def plan(paths: list[list[str]]) -> tuple[str, list[str]]:
    """-> ("single" | "batch", relative dir segments of the folder to analyse / batch).  [] = the upload root itself."""
    node, at = _tree(paths), []
    while len(node.dirs) == 1 and not node.files and not _is_item(next(iter(node.dirs.values()))):
        k = next(iter(node.dirs))
        node, at = node.dirs[k], at + [k]
    if _is_item(node):
        return "single", at
    items = {k: d for k, d in node.dirs.items()}
    if len(items) >= 2:
        return "batch", at
    if len(items) == 1:
        k = next(iter(items))
        return "single", at + [k]
    return "single", at


def zip_plan(names: list[str]) -> tuple[str, list[str]]:
    paths = []
    for n in names:
        if n.endswith("/"):
            continue
        try:
            p = clean_rel(n)
        except BadPath:
            continue
        if p:
            paths.append(p)
    return plan(paths) if paths else ("single", [])
