"""Speaker embedding -> `voice_id` (same synthetic/real voice across ads). CPU only, no torch.

Model: WeSpeaker ResNet34-LM (ONNX, ~25 MB, VoxCeleb-trained) via onnxruntime, with a numpy Kaldi-style 80-bin fbank front end
(no torchaudio). Chosen over SpeechBrain ECAPA because that needs torch (~2 GB) which does not fit the shared CPU box.
Registry: models_dir/voice_registry.json  {voice_id: {"centroid": [...], "members": [path-hash, ...]}}; a clip joins the
nearest centroid when cosine >= THRESH, else founds a new voice. Evidence weight is meant to be strength 4, rarity-weighted.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from trop.config import settings
from trop.media import video as V

URL = "https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM/resolve/main/voxceleb_resnet34_LM.onnx"
THRESH = 0.65
SR = 16000


def _model_path() -> Path:
    p = Path(settings.models_dir) / "wespeaker_resnet34_lm.onnx"
    if not p.exists():
        import httpx
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(httpx.get(URL, follow_redirects=True, timeout=300).content)
    return p


def _pcm(path: Path, max_s: float = 120.0) -> np.ndarray:
    """mono 16 kHz float32 via ffmpeg (first max_s seconds)."""
    r = subprocess.run([V.FFMPEG, "-hide_banner", "-nostdin", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-t", str(max_s),
                        "-f", "s16le", "-"], capture_output=True, timeout=300)
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32)


def _mel_fb(n_mels=80, n_fft=512, low=20.0, high=SR / 2) -> np.ndarray:
    mel = lambda f: 1127.0 * np.log(1.0 + f / 700.0)
    pts = np.linspace(mel(low), mel(high), n_mels + 2)
    hz = 700.0 * (np.exp(pts / 1127.0) - 1.0)
    bins = np.fft.rfftfreq(n_fft, 1.0 / SR)
    fb = np.zeros((n_mels, len(bins)), dtype=np.float32)
    for i in range(n_mels):
        l, c, r = hz[i], hz[i + 1], hz[i + 2]
        fb[i] = np.maximum(0.0, np.minimum((bins - l) / (c - l), (r - bins) / (r - c)))
    return fb


def fbank(x: np.ndarray) -> np.ndarray:
    """Kaldi-like: 25 ms / 10 ms frames, pre-emphasis 0.97, povey window, 512 FFT, 80 mels, log, per-utterance mean norm."""
    fl, fs = 400, 160
    if len(x) < fl:
        x = np.pad(x, (0, fl - len(x)))
    n = 1 + (len(x) - fl) // fs
    idx = np.arange(fl)[None, :] + fs * np.arange(n)[:, None]
    fr = x[idx]
    fr = fr - fr.mean(axis=1, keepdims=True)
    fr = np.concatenate([fr[:, :1], fr[:, 1:] - 0.97 * fr[:, :-1]], axis=1)
    fr = fr * (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(fl) / (fl - 1))) ** 0.85
    spec = np.abs(np.fft.rfft(fr, 512, axis=1)) ** 2
    feat = np.log(np.maximum(spec @ _mel_fb().T, np.finfo(np.float32).eps))
    return (feat - feat.mean(axis=0, keepdims=True)).astype(np.float32)


_sess = None


def embed(path: str | Path) -> np.ndarray | None:
    """Unit-norm 256-d speaker embedding of the clip's speech, None when there is no audio."""
    global _sess
    import onnxruntime as ort
    x = _pcm(Path(path))
    if len(x) < SR * 2:
        return None
    if _sess is None:
        so = ort.SessionOptions()
        so.intra_op_num_threads = 2
        _sess = ort.InferenceSession(str(_model_path()), so, providers=["CPUExecutionProvider"])
    f = fbank(x)  # model was trained on int16-scale waveforms
    e = _sess.run(None, {_sess.get_inputs()[0].name: f[None]})[0][0]
    return (e / np.linalg.norm(e)).astype(np.float32)


def _registry() -> Path:
    return Path(settings.models_dir) / "voice_registry.json"


def voice_id(path: str | Path, register: bool = True) -> dict | None:
    """{"voice_id", "ref", "best_cos", "n_members"} — clusters the clip into the registry (see module doc)."""
    e = embed(path)
    if e is None:
        return None
    reg = json.loads(_registry().read_text()) if _registry().exists() else {}
    me = hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest()[:12]
    best, best_cos = None, -1.0
    for vid, r in reg.items():
        c = float(np.dot(e, np.asarray(r["centroid"], dtype=np.float32)) / (np.linalg.norm(r["centroid"]) or 1.0))
        if c > best_cos:
            best, best_cos = vid, c
    if best is not None and best_cos >= THRESH:
        vid = best
        if register and me not in reg[vid]["members"]:
            n = len(reg[vid]["members"])
            cen = (np.asarray(reg[vid]["centroid"]) * n + e) / (n + 1)
            reg[vid] = {"centroid": cen.tolist(), "members": reg[vid]["members"] + [me]}
    else:
        vid = "VOICE-" + hashlib.sha256(e.tobytes()).hexdigest()[:8]
        if register:
            reg[vid] = {"centroid": e.tolist(), "members": [me]}
    if register:
        _registry().parent.mkdir(parents=True, exist_ok=True)
        _registry().write_text(json.dumps(reg))
    return {"voice_id": vid, "ref": f"{_registry().name}#{vid}", "best_cos": round(best_cos, 4),
            "n_members": len(reg.get(vid, {}).get("members", [1]))}


def pairwise(paths: list[str | Path]) -> dict:
    """Cosine matrix between clips (no registry writes) — used to report whether any two videos share a voice."""
    es = {str(p): embed(p) for p in paths}
    ks = [k for k, v in es.items() if v is not None]
    return {a: {b: round(float(np.dot(es[a], es[b])), 3) for b in ks} for a in ks}
