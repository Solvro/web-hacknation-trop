"""Where the evaluation inputs live (all under DATA_DIR, git-ignored) + loaders for the experiments' precomputed JSON.

Labels (`labels.yaml`, `labels_dane.yaml`) contain organizer identifiers, so they are never committed. They are looked
up, in order: $TROP_LABELS_DIR, DATA_DIR/labels/, <repo>/experiments/, <real DATA_DIR>/../experiments/ (the main
checkout when DATA_DIR is a symlink from a worktree).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import yaml

from trop.config import REPO, settings


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR") or settings.data_dir)


def exp_dir(corpus: str) -> Path:
    """data/experiments/<corpus> (sample_v1 | dane | joint)."""
    return data_dir() / "experiments" / corpus


def raw_dir(corpus: str) -> Path:
    return {"sample_v1": data_dir() / "raw" / "sample_v1",
            "dane": data_dir() / "raw" / "dane" / "unpacked" / "do_udostępnienia"}[corpus]


def _label_dirs() -> list[Path]:
    out = []
    if os.environ.get("TROP_LABELS_DIR"):
        out.append(Path(os.environ["TROP_LABELS_DIR"]))
    out += [data_dir() / "labels", REPO / "experiments"]
    try:
        out.append(data_dir().resolve().parent / "experiments")
    except OSError:
        pass
    return out


def labels_path(name: str = "labels.yaml") -> Path | None:
    for d in _label_dirs():
        if (d / name).is_file():
            return d / name
    return None


def have(*paths: Path | None) -> bool:
    return all(p is not None and Path(p).exists() for p in paths)


def load_yaml(name: str) -> dict:
    p = labels_path(name)
    if p is None:
        raise FileNotFoundError(f"{name} not found in {[str(d) for d in _label_dirs()]}")
    return yaml.safe_load(open(p, encoding="utf-8"))


_WIN_DATA = re.compile(r"^(?:\.\./)?data[\\/]")


def fix_path(p: str | None) -> str | None:
    """'../data/raw/sample_v1\\p1\\x.png' (experiments ran on Windows) -> absolute path under DATA_DIR."""
    if not p or not isinstance(p, str):
        return p
    q = p.replace("\\", "/")
    if _WIN_DATA.match(q):
        return str(data_dir() / _WIN_DATA.sub("", q))
    return q


def _fix_paths(inc: dict) -> dict:
    src = inc.get("source") or {}
    src["path"] = fix_path(src.get("path"))
    ad = inc.get("ad") or {}
    for k in ("screenshot_path", "video_path"):
        ad[k] = fix_path(ad.get(k))
    if ad.get("screenshots"):
        ad["screenshots"] = [fix_path(x) for x in ad["screenshots"]]
    la = inc.get("landing") or {}
    la["screenshot_path"] = fix_path(la.get("screenshot_path"))
    return inc


def load_precomputed(corpus: str, name: str) -> list[dict]:
    """Load data/experiments/<corpus>/<name> (the exact inputs the RESULTS rows were computed from)."""
    incs = json.load(open(exp_dir(corpus) / name, encoding="utf-8"))
    return [_fix_paths(i) for i in incs]


def extract_corpus(corpus: str, *, ad_model: str = "qwen36-35b-a3b", phash: str = "cache_only", faces: str = "none",
                   live: bool = False) -> list[dict]:
    """Re-extract a labelled corpus from the raw folders with the TROP ingest pipeline (ids p<N> / d<N> as labels)."""
    from trop.ingest.adapters import natural_key
    from trop.ingest.pipeline import IngestOptions, build_incident
    root = raw_dir(corpus)
    pref = "d" if corpus == "dane" else ""
    names = sorted((x.name for x in root.iterdir() if x.is_dir()), key=lambda n: (len(n), natural_key(n)))
    opts = IngestOptions(ad_model=ad_model, phash=phash, faces=faces, live=live)
    return [build_incident(root / n, inc_id=f"{pref}{n}", opts=opts) for n in names]
