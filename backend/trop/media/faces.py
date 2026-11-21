"""Faces: YuNet detector + SFace embedder (OpenCV, CPU, ~70 ms/screenshot) against the 6,305-person public-figure gallery.

Identity comes ONLY from here (never from a VLM/LLM). Rule (RESULTS §2c): name a person only if
cosine >= 0.45 AND (top-1 person - top-2 person) >= 0.10.  Index: models_dir/index_sface.npz (emb, qid, label, sitelinks);
a person's score = max cosine over that person's photos (several photos per person restore recall).
"""
from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path
from typing import Any

import numpy as np

from trop.config import settings
from trop.schema import FaceHit

COS_MIN = 0.45
LEAD_MIN = 0.10
DET_SCORE = 0.75
MAX_SIDE = 1600
ZOO = {
    "yunet.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "sface.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}
INDEX = "index_sface.npz"


def models_dir() -> Path:
    p = Path(settings.models_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _exp_dir() -> Path:
    return Path(settings.data_dir) / "experiments"


def ensure_models(download: bool = True) -> dict[str, Path]:
    """Make yunet/sface/index available in models_dir: copy from data/experiments (earlier runs), else download the ONNX files."""
    d = models_dir()
    src = {"yunet.onnx": _exp_dir() / "models" / "yunet.onnx", "sface.onnx": _exp_dir() / "models" / "sface.onnx",
           INDEX: _exp_dir() / "face_gallery" / INDEX}
    for name, s in src.items():
        if not (d / name).exists() and s.exists():
            shutil.copy2(s, d / name)
    for name, url in ZOO.items():
        if not (d / name).exists() and download:
            import httpx
            (d / name).write_bytes(httpx.get(url, follow_redirects=True, timeout=120).content)
    return {n: d / n for n in (*ZOO, INDEX)}


class FaceMatcher:
    def __init__(self) -> None:
        import cv2
        paths = ensure_models()
        for n in ZOO:
            if not paths[n].exists():
                raise FileNotFoundError(f"{paths[n]} missing (run `trop gallery install`)")
        self.cv2 = cv2
        self.det = cv2.FaceDetectorYN.create(str(paths["yunet.onnx"]), "", (320, 320), score_threshold=DET_SCORE)
        self.rec = cv2.FaceRecognizerSF.create(str(paths["sface.onnx"]), "")
        self.lock = threading.Lock()
        self.G = np.zeros((0, 128), dtype=np.float32)
        self.names: list[str] = []
        self.qids: dict[str, str] = {}
        self.inv = np.zeros(0, dtype=int)
        if paths[INDEX].exists():
            idx = np.load(paths[INDEX])
            self.G = idx["emb"].astype(np.float32)
            labels = [str(x) for x in idx["label"]]
            qids = [str(x) for x in idx["qid"]]
            low = np.array([x.lower() for x in labels])
            names, self.inv = np.unique(low, return_inverse=True)
            self.names = list(names)
            self.display: dict[str, str] = {}
            for lab, q, l in zip(labels, qids, low):
                self.display.setdefault(l, lab)
                if q.startswith("Q") and not self.qids.get(l, "").startswith("Q"):
                    self.qids[l] = q

    @property
    def n_people(self) -> int:
        return len(self.names)

    def embed(self, image_path: str) -> list[tuple[float, np.ndarray, list[float]]]:
        """[(det_score, unit embedding, [x,y,w,h])] for every face in the image."""
        cv2 = self.cv2
        img = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return []
        h, w = img.shape[:2]
        sc = 1.0 if max(h, w) <= MAX_SIDE else MAX_SIDE / max(h, w)
        im = cv2.resize(img, (int(w * sc), int(h * sc))) if sc != 1 else img
        with self.lock:
            self.det.setInputSize((im.shape[1], im.shape[0]))
            _, f = self.det.detect(im)
            out = []
            for row in (f if f is not None else []):
                v = self.rec.feature(self.rec.alignCrop(im, row))[0]
                out.append((float(row[-1]), v / np.linalg.norm(v), [float(x) / sc for x in row[:4]]))
        return out

    def person_scores(self, v: np.ndarray) -> np.ndarray:
        out = np.full(len(self.names), -1.0)
        np.maximum.at(out, self.inv, self.G @ v)
        return out

    def match(self, image_path: str, source: str = "ad_screenshot", *, all_faces: bool = False) -> list[FaceHit]:
        if not len(self.names):
            return []
        hits: list[FaceHit] = []
        for det_score, v, box in self.embed(image_path):
            s = self.person_scores(v)
            o = np.argsort(-s)
            top, second = float(s[o[0]]), float(s[o[1]]) if len(o) > 1 else -1.0
            lead = top - second
            named = top >= COS_MIN and lead >= LEAD_MIN
            if named or all_faces:
                n = self.names[o[0]]
                hits.append(FaceHit(identity=n if named else None, person_id=self.qids.get(n) if named else None,
                                    score=round(top, 4), lead=round(lead, 4), source=source,
                                    candidate=self.display.get(n) if not named else None, box=box,
                                    det_score=round(det_score, 3)))
        return hits


_matcher: FaceMatcher | None = None
_mlock = threading.Lock()


def matcher() -> FaceMatcher:
    global _matcher
    with _mlock:
        if _matcher is None:
            _matcher = FaceMatcher()
        return _matcher


def match(image_path: str, source: str = "ad_screenshot") -> list[FaceHit]:
    """Named faces only (cos >= 0.45 and lead >= 0.10). Returns [] when the models/index are unavailable."""
    try:
        return matcher().match(image_path, source)
    except (FileNotFoundError, OSError):
        return []


def match_frames(frames: list[str], source: str = "video_frame") -> list[FaceHit]:
    """Best hit per identity over several frames (keyframes of a video)."""
    best: dict[str, FaceHit] = {}
    for f in frames:
        for h in match(f, source):
            if h.identity and (h.identity not in best or h.score > best[h.identity].score):
                best[h.identity] = h
    return list(best.values())


# ------------------------------------------------------------------------------------ gallery build (offline)
def build(per: int = 3, gal: Path | None = None, out: Path | None = None) -> dict[str, Any]:
    """Port of rp/gallery.py:build — detect the main face in every gallery photo, SFace-embed, add vetted extra photos.
    Needs the fetched photos (data/experiments/face_gallery/{wd,extra,meta.jsonl,...}); writes models_dir/index_sface.npz."""
    import time

    import cv2

    gal = Path(gal or _exp_dir() / "face_gallery")
    out = Path(out or models_dir() / INDEX)
    paths = ensure_models()
    det = cv2.FaceDetectorYN.create(str(paths["yunet.onnx"]), "", (320, 320), score_threshold=0.8)
    rec = cv2.FaceRecognizerSF.create(str(paths["sface.onnx"]), "")
    meta = [json.loads(x) for x in (gal / "meta.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    for x in meta:
        x["path"] = str(gal / "wd" / (x["qid"] + ".jpg"))
    for jp in sorted(gal.glob("*.jpg")):  # curated hand-picked portraits: <First_Last>.jpg
        meta.append({"qid": "cur:" + jp.stem, "label": jp.stem.replace("_", " ").lower().title(), "sitelinks": 0,
                     "source": "curated", "path": str(jp)})
    embs, keep, t0, nofc = [], [], time.time(), 0

    def read(p: str):
        return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)

    for x in meta:
        if not Path(x["path"]).exists():
            continue
        img = read(x["path"])
        if img is None:
            continue
        det.setInputSize((img.shape[1], img.shape[0]))
        _, f = det.detect(img)
        if f is None or not len(f):
            nofc += 1
            continue
        row = max(f, key=lambda r: r[2] * r[3])
        v = rec.feature(rec.alignCrop(img, row))[0]
        embs.append(v / np.linalg.norm(v))
        keep.append(x)
    n_extra = n_rej = 0
    ex = gal / "extra.jsonl"
    if ex.exists():
        E = np.asarray(embs, dtype=np.float32)
        qids = [x["qid"] for x in keep]
        labels = [(x["label"] or "").lower() for x in keep]
        for line in ex.read_text(encoding="utf-8").splitlines():
            x = json.loads(line)
            lab = (x.get("label") or "").lower()
            rows = [i for i, (q, l) in enumerate(zip(qids, labels)) if q == x["qid"] or (lab and l == lab)]
            if not rows:
                continue
            ref, added = E[rows], 0
            for fn in x["files"]:
                if added >= per:
                    break
                img = read(str(gal / "extra" / fn))
                if img is None:
                    continue
                det.setInputSize((img.shape[1], img.shape[0]))
                _, f = det.detect(img)
                if f is None or not len(f):
                    continue
                cand = []
                for row in f:
                    v = rec.feature(rec.alignCrop(img, row))[0]
                    v = v / np.linalg.norm(v)
                    cand.append((float((ref @ v).max()), v))
                sim, v = max(cand, key=lambda c: c[0])
                if 0.45 <= sim <= 0.97:
                    embs.append(v)
                    keep.append({"qid": x["qid"], "label": keep[rows[0]]["label"], "sitelinks": keep[rows[0]]["sitelinks"],
                                 "source": "extra"})
                    added += 1
                    n_extra += 1
                else:
                    n_rej += 1
    np.savez_compressed(out, emb=np.asarray(embs, dtype=np.float32), qid=np.array([x["qid"] for x in keep]),
                        label=np.array([x["label"] or x["qid"] for x in keep]),
                        sitelinks=np.array([x["sitelinks"] for x in keep]))
    global _matcher
    _matcher = None
    return {"photos": len(keep), "people": len({(x["label"] or x["qid"]).lower() for x in keep}), "no_face": nofc,
            "extra_kept": n_extra, "extra_rejected": n_rej, "secs": round(time.time() - t0), "index": str(out)}
