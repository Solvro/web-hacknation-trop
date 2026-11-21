"""Video + speech pipeline: Gemini video pass (primary) -> keyframes -> faces; transcript -> Incident.media.asr_text + content hints.

`analyze_video(path)` returns {"media": schema.Media (dict), "content_hints": {...}, "ad_hints": {...}} — everything WS1's
ingest needs to fold a video into an Incident (`incident.media`, `content.transcript` etc.). Persons stay in `persons_hint`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from trop.config import settings
from trop.media import faces
from trop.media import video as V
from trop.media.gateway import file_sha256, gateway
from trop.schema import Media, VideoInfo

MEDIA_GEMINI = "experiments/dane/media_gemini.json"


def incident_id_for(path: str | Path) -> str | None:
    """.../do_udostępnienia/<N>/<file> -> 'd<N>' (organizer DANE layout); p<N> for sample_v1."""
    parts = Path(path).resolve().parts
    for marker, pre in (("do_udostępnienia", "d"), ("sample_v1", "p")):
        if marker in parts:
            i = parts.index(marker)
            if i + 1 < len(parts) - 1 and re.fullmatch(r"\d+", parts[i + 1]):
                return f"{pre}{parts[i + 1]}"
    return None


def analyze_video(path: str | Path, *, model: str = "flash", with_faces: bool = True, with_voice: bool = True) -> dict:
    p = Path(path)
    gem = gateway.video_pass(str(p), model=model)
    info = V.probe(p)
    frames: list[str] = []
    hits = []
    if with_faces:
        kdir = Path(settings.artifact_dir) / "keyframes" / file_sha256(p)[:12]
        try:
            frames = gem.get("keyframes") or V.keyframes(p, kdir, n=12)
            hits = faces.match_frames(frames)
        except Exception as e:  # noqa: BLE001
            gem = {**gem, "keyframe_error": str(e)[:200]}
    voice = None
    if with_voice:
        try:
            from trop.media import voice as VO
            voice = VO.voice_id(p)
        except Exception:  # noqa: BLE001
            voice = None
    gem_clean = {k: v for k, v in gem.items() if k not in ("keyframes",)}
    media = Media(
        faces=hits,
        video=VideoInfo(path=str(p), duration_s=info["duration_s"], keyframes=frames, gemini=gem_clean),
        asr_text=gem.get("transcript") or None,
        asr_model=gem.get("_model"),
        voice_id=(voice or {}).get("voice_id"),
        voice_embedding_ref=(voice or {}).get("ref"),
    )
    hints = {
        "transcript": gem.get("transcript"), "on_screen_text": gem.get("on_screen_text", []),
        "product": gem.get("product"), "brand": gem.get("brand"), "vertical": gem.get("vertical"),
        "language": gem.get("language"), "narrative": gem.get("narrative"), "ctas": gem.get("ctas", []),
        "urls": gem.get("urls", []), "phones": gem.get("phones", []),
        "persons_hint": gem.get("persons_hint", []),      # unverified model output: engine must ignore
    }
    ad_hints = {"video_path": str(p), "narrative": gem.get("narrative"), "cta": (gem.get("ctas") or [None])[0],
                "kind": "video"}
    return {"incident_id": incident_id_for(p), "media": media.model_dump(mode="json"), "content_hints": hints,
            "ad_hints": ad_hints, "missing": bool(gem.get("missing"))}


def write_media_gemini(result: dict, out: Path | None = None) -> Path | None:
    """Merge one analysis into data/experiments/dane/media_gemini.json (keyed by incident id) for WS1."""
    iid = result.get("incident_id")
    if not iid or result.get("missing"):
        return None
    out = Path(out or Path(settings.data_dir) / MEDIA_GEMINI)
    out.parent.mkdir(parents=True, exist_ok=True)
    cur = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    cur[iid] = {k: result[k] for k in ("media", "content_hints", "ad_hints")}
    out.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
