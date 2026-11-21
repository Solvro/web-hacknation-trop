"""ffmpeg helpers (imageio-ffmpeg binary, no system install needed): probe, trim/compress, keyframes, audio extract."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def _run(args: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run([FFMPEG, "-hide_banner", "-nostdin", *args], capture_output=True, text=True, timeout=timeout)


def probe(path: str | Path) -> dict:
    """{duration_s, width, height, has_audio} parsed from `ffmpeg -i` stderr."""
    err = _run(["-i", str(path)]).stderr
    out: dict = {"duration_s": None, "width": None, "height": None, "has_audio": "Audio:" in err}
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", err)
    if m:
        out["duration_s"] = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    m = re.search(r"Video:.*?, (\d{2,5})x(\d{2,5})", err)
    if m:
        out["width"], out["height"] = int(m[1]), int(m[2])
    return out


def proxy(path: str | Path, out: str | Path, *, start: float = 0.0, max_s: float | None = None, width: int = 540,
          fps: int = 10) -> Path:
    """Small, fast-to-upload copy (optionally trimmed to [start, start+max_s]) with mono 64k audio."""
    args = ["-y"]
    if start:
        args += ["-ss", f"{start:.2f}"]
    args += ["-i", str(path)]
    if max_s:
        args += ["-t", f"{max_s:.2f}"]
    args += ["-vf", f"scale='min({width},iw)':-2,fps={fps}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "64k", "-ac", "1", "-movflags", "+faststart", str(out)]
    r = _run(args, timeout=1800)
    if r.returncode != 0 or not Path(out).exists():
        raise RuntimeError("ffmpeg proxy failed: " + r.stderr[-300:])
    return Path(out)


def extract_audio(path: str | Path, out: str | Path, *, max_s: float | None = None) -> Path | None:
    args = ["-y", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k"]
    if max_s:
        args += ["-t", f"{max_s:.2f}"]
    r = _run(args + [str(out)])
    return Path(out) if r.returncode == 0 and Path(out).exists() and Path(out).stat().st_size > 1000 else None


def keyframes(path: str | Path, out_dir: str | Path, n: int = 12, scene: float = 0.25, width: int = 960) -> list[str]:
    """<= n frames: scene-change frames first; if fewer than n//2 found, top up with evenly spaced ones."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("kf_*.jpg"):
        f.unlink()
    vf = f"select='gt(scene,{scene})',scale='min({width},iw)':-2"
    _run(["-y", "-i", str(path), "-vf", vf, "-vsync", "vfr", "-frames:v", "60", "-q:v", "3", str(out_dir / "kf_%03d.jpg")])
    frames = sorted(out_dir.glob("kf_*.jpg"))
    if len(frames) < max(2, n // 2):
        dur = probe(path)["duration_s"] or 0
        if dur:
            for f in frames:
                f.unlink()
            fps = n / dur
            _run(["-y", "-i", str(path), "-vf", f"fps={fps:.5f},scale='min({width},iw)':-2", "-frames:v", str(n), "-q:v", "3",
                  str(out_dir / "kf_%03d.jpg")])
            frames = sorted(out_dir.glob("kf_*.jpg"))
    if len(frames) > n:  # thin evenly
        step = len(frames) / n
        keep = {int(i * step) for i in range(n)}
        for i, f in enumerate(frames):
            if i not in keep:
                f.unlink()
        frames = sorted(out_dir.glob("kf_*.jpg"))
    return [str(f) for f in frames]
