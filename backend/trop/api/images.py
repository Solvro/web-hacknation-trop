"""Downscaled screenshots of incidents: bundle for the corpus, stored at analysis time for fresh uploads/captures.

Layout: <DATA_DIR>/images/<incident_id>/meta.json + <role>-<n>.webp  (max 1200 px wide, WebP q75).
Served by GET /incidents/{id}/artifacts (roles ad_screenshot | landing_screenshot | video_keyframe) and GET /artifacts/{id}; the API never
exposes local paths. Build for the bundle: `cd backend && uv run python -m trop.api.images <DATA_DIR> <OUT_DIR>` (called by deploy/make_bundle.sh).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MAX_W = 1200
KF_W = 800
MAX_KEYFRAMES = 3


def images_dir() -> Path:
    from trop.config import settings
    return Path(settings.data_dir) / "images"


def _safe_id(iid: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", iid)[:80]


def downscale(src: str | Path, dst: Path, max_w: int = MAX_W) -> tuple[int, int] | None:
    from PIL import Image
    try:
        with Image.open(src) as im:
            im.load()
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            if im.width > max_w:
                im = im.resize((max_w, max(1, round(im.height * max_w / im.width))), Image.LANCZOS)
            dst.parent.mkdir(parents=True, exist_ok=True)
            im.save(dst, "WEBP", quality=75, method=4)
            return im.width, im.height
    except Exception:  # noqa: BLE001 - a broken screenshot must not break an analysis
        return None


def _fix(p: str | None) -> str | None:
    if not p:
        return None
    try:
        from trop.eval.data import fix_path
        return fix_path(p)
    except Exception:  # noqa: BLE001
        return p


def collect(inc: dict) -> list[tuple[str, str, int]]:
    """-> [(role, source path, max width)] of the screenshots that exist on disk."""
    ad, lan, med = inc.get("ad") or {}, inc.get("landing") or {}, inc.get("media") or {}
    out, seen = [], set()

    def add(role: str, p: str | None, w: int = MAX_W) -> None:
        fp = _fix(p)
        if fp and fp not in seen and Path(fp).is_file():
            seen.add(fp)
            out.append((role, fp, w))
    add("ad_screenshot", ad.get("screenshot_path"))
    for p in (ad.get("screenshots") or [])[:3]:
        add("ad_screenshot", p)
    add("landing_screenshot", lan.get("screenshot_path"))
    for p in ((med.get("video") or {}).get("keyframes") or [])[:MAX_KEYFRAMES]:
        add("video_keyframe", p, KF_W)
    return out


def _video_path(inc: dict) -> str | None:
    ad, med = inc.get("ad") or {}, inc.get("media") or {}
    for p in (((med.get("video") or {}).get("path")), ad.get("video_path")):
        fp = _fix(p)
        if fp and Path(fp).is_file():
            return fp
    return None


def extract_keyframes(video: str, tmp: Path, duration: float | None = None, n: int = MAX_KEYFRAMES) -> list[str]:
    """A few frames of a video with the ffmpeg binary bundled in imageio-ffmpeg (no system ffmpeg needed)."""
    import subprocess
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return []
    tmp.mkdir(parents=True, exist_ok=True)
    out = []
    for i, t in enumerate((2.0, 10.0, 30.0)[:n]):
        if duration and t >= duration:
            continue
        f = tmp / f"kf_{i}.png"
        try:
            subprocess.run([exe, "-y", "-loglevel", "error", "-ss", str(t), "-i", video, "-frames:v", "1", str(f)], timeout=60, check=True)
        except Exception:  # noqa: BLE001
            continue
        if f.is_file():
            out.append(str(f))
    return out


def store(iid: str, inc: dict, base: Path | None = None, src: str | Path | None = None) -> list[dict]:
    """Write the downscaled images of one incident; returns the meta list (also saved as meta.json)."""
    d = (base or images_dir()) / _safe_id(iid)
    meta, n = [], {}
    items = collect(inc)
    if not any(r == "video_keyframe" for r, _, _ in items):
        v = _video_path(inc)
        if v:
            import tempfile
            dur = ((inc.get("media") or {}).get("video") or {}).get("duration_s")
            items += [("video_keyframe", f, KF_W) for f in extract_keyframes(v, Path(tempfile.mkdtemp(prefix="trop-kf-")), dur)]
    lb = (inc.get("landing") or {}).get("boxes")
    if not lb and src:                           # live capture: screenshots/full_page.boxes.json (page px, same size as the png before downscale)
        for bj in Path(src).rglob("full_page.boxes.json"):
            try:
                b = json.loads(bj.read_text(encoding="utf-8"))
                lb = b.get("boxes") if isinstance(b, dict) else b
            except (OSError, ValueError):
                pass
            break
    for role, src, w in items:
        k = n.get(role, 0)
        n[role] = k + 1
        fn = f"{role}-{k}.webp"
        size = downscale(src, d / fn, w)
        if size:
            meta.append({"role": role, "n": k, "file": fn, "w": size[0], "h": size[1], "bytes": (d / fn).stat().st_size,
                         **({"boxes": _scaled(lb, src, size[0])} if lb and role == "landing_screenshot" else {})})
    if meta:
        (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return meta


def _scaled(boxes: list, src: str, new_w: int) -> list:
    try:
        from PIL import Image
        with Image.open(src) as im:
            k = new_w / im.width
    except Exception:  # noqa: BLE001
        return boxes
    if abs(k - 1) < 1e-3:
        return boxes
    return [{**b, **{a: round(b[a] * k) for a in ("x", "y", "w", "h") if isinstance(b.get(a), (int, float))}} for b in boxes]


def listing(iid: str) -> list[dict]:
    f = images_dir() / _safe_id(iid) / "meta.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    except (OSError, ValueError):
        return []


RENDERED_N = 100


def _rendered(iid: str) -> tuple[Path, list | None] | None:
    """WS5's rendered landing page (<incident>.webp + .boxes.json) from data/artifacts/rendered or the bundle's images/rendered."""
    from trop.config import settings
    sid = _safe_id(iid)
    for d in (Path(settings.data_dir) / "artifacts" / "rendered", images_dir() / "rendered"):
        f = d / f"{sid}.webp"
        if f.is_file():
            boxes = None
            try:
                b = json.loads((d / f"{sid}.boxes.json").read_text(encoding="utf-8"))
                boxes = b.get("boxes") if isinstance(b, dict) else b
            except (OSError, ValueError):
                pass
            return f, boxes
    return None


def file_for(artifact_id: str) -> Path | None:
    """Artifact id = `<incident>--<role>--<n>` -> file path (None if unknown). Path traversal impossible: the id is looked up in meta.json."""
    try:
        iid, role, n = artifact_id.rsplit("--", 2)
        n = int(n)
    except ValueError:
        return None
    if role == "landing_screenshot" and n == RENDERED_N:
        r = _rendered(iid)
        return r[0] if r else None
    for m in listing(iid):
        if m["role"] == role and m["n"] == n:
            p = images_dir() / _safe_id(iid) / m["file"]
            return p if p.is_file() else None
    return None


_LOCAL = ("file:", "/home/", "/data/", "/tmp/", "c:\\")


def _clean_boxes(boxes: list | None) -> list:
    """Boxes go to the public API: drop any value that points at a local file (render hrefs, saved-page paths)."""
    out = []
    for b in boxes or []:
        if not isinstance(b, dict):
            continue
        out.append({k: v for k, v in b.items() if not (isinstance(v, str) and v.lower().startswith(_LOCAL))})
    return out


def artifact_refs(iid: str) -> list[dict]:
    out = []
    for m in listing(iid):
        a = f"{iid}--{m['role']}--{m['n']}"
        r = {"id": a, "role": m["role"], "url": f"/api/v1/artifacts/{a}", "w": m["w"], "h": m["h"], "mime": "image/webp", "size": m.get("bytes", 0)}
        if m.get("boxes"):
            r["boxes"] = _clean_boxes(m["boxes"])
        out.append(r)
    rd = _rendered(iid)
    if rd:                                       # rendered landing page first: it is the faithful one
        try:
            from PIL import Image
            with Image.open(rd[0]) as im:
                w, h = im.size
        except Exception:  # noqa: BLE001
            w = h = 0
        a = f"{iid}--landing_screenshot--{RENDERED_N}"
        r = {"id": a, "role": "landing_screenshot", "url": f"/api/v1/artifacts/{a}", "w": w, "h": h, "mime": "image/webp", "size": rd[0].stat().st_size}
        if rd[1]:
            r["boxes"] = _clean_boxes(rd[1])
        li = next((k for k, x in enumerate(out) if x["role"] == "landing_screenshot"), len(out))
        out.insert(li, r)
    return out


def build(data: Path, out: Path) -> None:
    """Bundle: images for every corpus incident (known.json) and the DANE incidents. Prints the total size."""
    import os
    os.environ["DATA_DIR"] = str(data)
    from trop.config import settings
    settings.data_dir = data
    incs = []
    for p in (data / "corpus" / "known.json", ):
        if p.exists():
            incs += json.loads(p.read_text(encoding="utf-8")).get("incidents", [])
    for p in (data / "experiments" / "dane" / "incidents_q36.json", data / "experiments" / "dane" / "incidents.json"):
        if p.exists():
            have = {i["id"] for i in incs}
            incs += [i for i in json.loads(p.read_text(encoding="utf-8")) if i["id"] not in have]
            break
    total = 0
    rd = data / "artifacts" / "rendered"
    if rd.is_dir():
        import shutil
        (out / "rendered").mkdir(parents=True, exist_ok=True)
        for f in rd.iterdir():
            if f.suffix in (".webp", ".json"):
                shutil.copy2(f, out / "rendered" / f.name)
                total += f.stat().st_size
    for inc in incs:
        for m in store(inc["id"], inc, out):
            total += m["bytes"]
    print(f"images: {len(incs)} incidents, {total/1e6:.1f} MB -> {out}")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
