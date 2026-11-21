"""Ingest + extract one item -> Incident dict (the shape `schema.Incident` describes and the engine consumes).

    build_incident(path_or_item, inc_id=None, *, emit=None, opts=IngestOptions()) -> dict

Steps (each reported through `emit`, see trop.engine.progress): capture -> tracking (rules extractor: tracking, kit,
content, infra skeleton) -> content (ad screenshot VLM fields + faces) -> infra (enrichment cache).
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from trop.extract import cache, layers
from trop.extract.rules import etld1, extract_incident, path_shape, path_template, url_schema

from .adapters import Item, single_item

log = logging.getLogger(__name__)

SOURCE_TYPE = {"archive_bundle": "bundle", "sample_dir": "sample_dir", "capture_tool": "capture_tool"}


@dataclass
class IngestOptions:
    ad_model: str = cache.AD_MODEL
    ad_layer: bool = True          # VLM ad fields (cache / live gateway)
    phash: str = "compute"         # compute | cache_only (cache_only = exact experiments reproduction)
    faces: str = "gallery"         # gallery | none
    infra: bool = True             # enrichment cache
    live: bool | None = None       # None = settings.trop_mode; False forces offline


def _url_only(inc: dict, url: str) -> None:
    """A bare URL that could not be captured: entry URL features only (no content -> usually 'insufficient')."""
    host = urlsplit(url).hostname
    inc["landing"].update({"entry_url": url, "host": host, "etld1": etld1(host) if host else ""})
    inc["tracking"].update({"url_param_schema": url_schema(url), "entry_path_template": path_template(urlsplit(url).path),
                            "path_shapes": sorted({ps for ps in [path_shape(urlsplit(url).path)] if ps})})
    if host:
        inc["infra"]["domains"] = [{"fqdn": host, "etld1": etld1(host), "tld": host.rsplit(".", 1)[-1],
                                    "sld_label": etld1(host).split(".")[0], "ips": [], "cdn": []}]


def _try_capture(url: str, workdir: Path) -> Path | None:
    """WS5's capture (trop.capture) when available and live; returns an organizer-compatible bundle dir."""
    from trop.config import settings
    if settings.trop_mode != "live" or os.environ.get("TROP_NO_LIVE") == "1":
        return None
    try:
        from trop.capture import capture as cap  # type: ignore
    except ImportError:
        return None
    for fn in ("capture_url", "capture"):
        f = getattr(cap, fn, None)
        if callable(f):
            try:
                out = f(url, out_dir=str(workdir))
                p = Path(out if isinstance(out, (str, Path)) else getattr(out, "path", ""))
                return p if p.is_dir() else None
            except Exception as e:  # noqa: BLE001
                log.warning("capture failed for %s: %s", url, e)
                return None
    return None


def build_incident(src: str | Path | Item, inc_id: str | None = None, *, emit=None,
                   opts: IngestOptions | None = None, workdir: Path | None = None) -> dict:
    from trop.engine.progress import Steps
    opts = opts or IngestOptions()
    steps = Steps(emit)
    old_live = os.environ.get("TROP_NO_LIVE")
    if opts.live is False:
        os.environ["TROP_NO_LIVE"] = "1"
    try:
        # ---------------- capture (zwiadowca)
        steps.start("capture")
        item = src if isinstance(src, Item) else single_item(src, workdir)
        path = item.path
        if item.kind == "url" and item.url:
            cap_dir = _try_capture(item.url, Path(workdir or path))
            if cap_dir:
                path, item.kind = cap_dir, "bundle"
        # ---------------- tracking (tropiciel): deterministic extractor
        t0 = time.time()
        inc = extract_incident(str(path), inc_id=inc_id or item.name)
        inc["landing"].pop("dom_paths_full", None)
        inc["source"]["type"] = SOURCE_TYPE.get(inc["source"]["type"], inc["source"]["type"])
        if item.kind in ("url", "video", "screenshot", "har", "upload") and inc["source"]["type"] == "sample_dir":
            inc["source"]["type"] = item.kind
        inc["source"]["ref"] = item.name
        if item.kind == "url" and item.url and not inc["landing"].get("entry_url"):
            _url_only(inc, item.url)
        q = inc["quality"]
        q.setdefault("provenance", {})
        steps.done("capture", detail=f"HAR {inc['landing'].get('n_hars', 0)} · HTML {int('html' in q['available'])} · "
                                     f"zrzuty {len(inc['ad'].get('screenshots') or [])}"
                                     + (" · wideo" if inc["ad"].get("video_path") else ""),
                   status="done" if (q["available"] or inc["landing"].get("entry_url")) else "warn")
        steps.start("tracking")
        steps.material(inc, "tracking")
        steps.done("tracking", detail=f"{time.time() - t0:.1f} s")

        # ---------------- content (czytelnik): ad layer (VLM fields + creative pHash) + faces
        steps.start("content")
        shot = inc["ad"].get("screenshot_path")
        warn = []
        if shot and opts.ad_layer:
            fields, prov = cache.ad_fields(shot, opts.ad_model)
            q["provenance"]["ad_fields"] = prov
            ph = None
            if fields and not fields.get("is_decoy"):
                if opts.phash == "compute":
                    ph = cache.screenshot_media(shot, fields.get("screenshot_kind")).get("creative_phash")
                else:
                    from trop.extract.cache import _experiment_index, _exp_file, sha256_file
                    ref = _experiment_index().get(sha256_file(shot) or "")
                    ph = (_exp_file(ref["corpus"], "media_ocr.json").get(ref["id"]) or {}).get("creative_phash") if ref else None
            if fields:
                layers.apply_ad_fields(inc, fields, ph)
            else:
                warn.append("brak pól reklamy (VLM niedostępny / brak w cache)")
        if shot and opts.faces == "gallery":
            hits, prov = cache.face_hits(shot)
            q["provenance"]["faces"] = prov
            if hits is not None:
                inc.setdefault("media", {})["faces"] = layers.face_hits_to_faces(hits)
        inc.setdefault("media", {}).setdefault("faces", [])
        if inc["ad"].get("video_path"):
            inc["media"]["video"] = {"path": inc["ad"]["video_path"]}
        steps.material(inc, "content")
        steps.done("content", status="warn" if warn else "done", warnings=warn)

        # ---------------- infra (notariusz): enrichment cache (DNS/RDAP/crt.sh)
        steps.start("infra")
        n = layers.apply_infra(inc, cache.infra_record) if opts.infra else 0
        q["provenance"]["infra_enriched"] = n
        steps.material(inc, "infra")
        steps.done("infra", detail=f"wzbogacone domeny: {n}/{len(inc['infra']['domains'])}",
                   status="done" if n or not inc["infra"]["domains"] else "warn")
        return inc
    finally:
        if opts.live is False:
            if old_live is None:
                os.environ.pop("TROP_NO_LIVE", None)
            else:
                os.environ["TROP_NO_LIVE"] = old_live


def validate(inc: dict) -> list[str]:
    """Check against schema.Incident; returns error strings (empty = valid)."""
    from pydantic import ValidationError

    from trop.schema import Incident
    try:
        Incident.model_validate({k: v for k, v in inc.items() if not k.startswith("_")})
        return []
    except ValidationError as e:
        return [f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()][:20]
