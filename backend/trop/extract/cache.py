"""Pluggable sources for the model / enrichment layers (offline-first).

Lookup order for an ad screenshot (key = sha256 of the file bytes, so it works for any folder name):
  1. settings.cache_dir/ad_fields/<sha>.json, faces/<sha>.json     (written by live calls; replayable offline)
  2. the experiments' precomputed outputs in data/experiments/{sample_v1,dane,joint} (indexed by screenshot sha256)
  3. live: only if settings.trop_mode == 'live' and WS4's trop.media.gateway / trop.media.faces import
Infra enrichment: data/experiments/*/infra_enrich.json + settings.cache_dir/infra_enrich.json, keyed by eTLD+1.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from functools import lru_cache
from pathlib import Path

from trop.config import settings

log = logging.getLogger(__name__)
AD_MODEL = "qwen36-35b-a3b"          # RESULTS §0.4: the VLM that scored 14/14


def _data() -> Path:
    return Path(os.environ.get("DATA_DIR") or settings.data_dir)


def _cache() -> Path:
    return Path(os.environ.get("TROP_CACHE_DIR") or settings.cache_dir)


def sha256_file(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _load(p: Path):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return None


@lru_cache(maxsize=1)
def _experiment_index() -> dict:
    """sha256(first ad screenshot) -> {corpus, id} for every incident the experiments extracted."""
    from trop.eval.data import fix_path
    idx_p = _cache() / "screenshot_index.json"
    cached = _load(idx_p)
    if isinstance(cached, dict) and cached.get("_v") == 1:
        return cached
    idx: dict = {"_v": 1}
    for corpus in ("sample_v1", "dane"):
        incs = _load(_data() / "experiments" / corpus / "incidents.json") or []
        for inc in incs:
            ad = inc.get("ad") or {}
            for p in ([ad.get("screenshot_path")] + list(ad.get("screenshots") or []))[:1]:
                s = sha256_file(fix_path(p)) if p else None
                if s:
                    idx[s] = {"corpus": corpus, "id": inc["id"]}
    try:
        idx_p.parent.mkdir(parents=True, exist_ok=True)
        json.dump(idx, open(idx_p, "w"), indent=0)
    except OSError:
        pass
    return idx


@lru_cache(maxsize=8)
def _exp_file(corpus: str, name: str):
    return _load(_data() / "experiments" / corpus / name) or {}


def _live_enabled() -> bool:
    return settings.trop_mode == "live" and os.environ.get("TROP_NO_LIVE") != "1"


# ------------------------------------------------------------------------------------------------ ad fields
def ad_fields(path: str, model: str = AD_MODEL) -> tuple[dict | None, str]:
    """-> (fields in ad_fields_*.json shape, provenance 'cache'|'experiments'|'live'|'none')."""
    from .layers import normalise_vlm
    sha = sha256_file(path)
    if not sha:
        return None, "none"
    hit = _load(_cache() / "ad_fields" / f"{sha}.json")
    if isinstance(hit, dict) and hit.get("fields"):
        return hit["fields"], "cache"
    ref = _experiment_index().get(sha)
    if ref:
        p = _exp_file(ref["corpus"], f"ad_fields_{model}.json").get(ref["id"])
        if p:
            return p, "experiments"
    if _live_enabled():
        try:
            from trop.media.gateway import gateway  # WS4
        except ImportError:
            return None, "none"
        try:
            p = normalise_vlm(gateway.ad_fields(path))
            (_cache() / "ad_fields").mkdir(parents=True, exist_ok=True)
            json.dump({"model": "gateway", "fields": p}, open(_cache() / "ad_fields" / f"{sha}.json", "w"), ensure_ascii=False)
            return p, "live"
        except Exception as e:  # noqa: BLE001 - live model failure must not break ingest
            log.warning("gateway.ad_fields failed for %s: %s", path, e)
    return None, "none"


def screenshot_media(path: str, kind: str | None) -> dict:
    """creative pHash: experiments' media_ocr.json when indexed (exact reproduction), else computed (rp/media.py)."""
    from .layers import screenshot_phashes
    sha = sha256_file(path)
    ref = _experiment_index().get(sha or "")
    if ref:
        m = _exp_file(ref["corpus"], "media_ocr.json").get(ref["id"])
        if m and m.get("creative_phash"):
            return m
    try:
        return screenshot_phashes(path, kind)
    except Exception as e:  # noqa: BLE001
        log.warning("phash failed for %s: %s", path, e)
        return {}


# ------------------------------------------------------------------------------------------------ faces
def face_hits(path: str) -> tuple[list | None, str]:
    """Gallery hits [[name, cos, runner_up], ...] for the ad screenshot."""
    sha = sha256_file(path)
    if not sha:
        return None, "none"
    hit = _load(_cache() / "faces" / f"{sha}.json")
    if isinstance(hit, dict) and "hits" in hit:
        return hit["hits"], "cache"
    ref = _experiment_index().get(sha)
    if ref:
        hits = (_exp_file("joint", "faces_gallery_id.json").get("hits") or {}).get(ref["id"])
        if hits is not None:
            return hits, "experiments"
    if _live_enabled():
        try:
            from trop.media import faces as wfaces  # WS4
        except ImportError:
            return None, "none"
        try:
            res = wfaces.match(path)
            hits = []
            for f in res:
                d = f.model_dump() if hasattr(f, "model_dump") else dict(f)
                if d.get("identity"):
                    hits.append([d["identity"], d.get("score", 0.0), d.get("score", 0.0) - (d.get("lead") or 0.0)])
            (_cache() / "faces").mkdir(parents=True, exist_ok=True)
            json.dump({"hits": hits}, open(_cache() / "faces" / f"{sha}.json", "w"), ensure_ascii=False)
            return hits, "live"
        except Exception as e:  # noqa: BLE001
            log.warning("faces.match failed for %s: %s", path, e)
    return None, "none"


# ------------------------------------------------------------------------------------------------ infra
@lru_cache(maxsize=1)
def _infra_table() -> dict:
    out: dict = {}
    for p in [_data() / "experiments" / c / "infra_enrich.json" for c in ("sample_v1", "dane")] + [_cache() / "infra_enrich.json"]:
        t = _load(p)
        if isinstance(t, dict):
            out.update(t)
    return out


def infra_record(etld1: str) -> dict | None:
    return _infra_table().get(etld1)


def clear() -> None:
    _experiment_index.cache_clear()
    _exp_file.cache_clear()
    _infra_table.cache_clear()
