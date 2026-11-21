"""Content fingerprints: sha256, perceptual image hashes, favicon mmh3, SimHash, MinHash + LSH bands.

pHash/dHash reproduce imagehash's bit order (phash: 32x32 grey LANCZOS, 2-D DCT-II, top-left 8x8 > median;
dhash: 9x8 horizontal gradient) without numpy/scipy, so values match the experiments session's imagehash.
"""
from __future__ import annotations

import base64
import hashlib
import io
import math
import re
from functools import lru_cache

import warnings

import mmh3
from PIL import Image

MASK64 = (1 << 64) - 1
warnings.filterwarnings("ignore", message="Palette images with Transparency")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def to_signed64(x: int) -> int:
    x &= MASK64
    return x - (1 << 64) if x >= (1 << 63) else x


def bits_to_int(bits: list[bool]) -> int:
    v = 0
    for b in bits:
        v = (v << 1) | int(b)
    return v


@lru_cache(maxsize=1)
def _dct_matrix(n: int = 32, k: int = 8) -> list[list[float]]:
    # unnormalized DCT-II basis (scipy.fftpack.dct default); the scale does not affect the median test
    return [[2.0 * math.cos(math.pi * kk * (2 * nn + 1) / (2 * n)) for nn in range(n)] for kk in range(k)]


def _median(vals: list[float]) -> float:
    s = sorted(vals)
    m = len(s) // 2
    return (s[m - 1] + s[m]) / 2 if len(s) % 2 == 0 else s[m]


def image_hashes(data: bytes) -> dict | None:
    """-> {'phash': signed64, 'dhash': signed64, 'width':, 'height':} or None if not an image."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return None
    w, h = img.size
    try:
        g = img.convert("L").resize((32, 32), Image.Resampling.LANCZOS)
        px = list(g.getdata())
        x = [px[r * 32:(r + 1) * 32] for r in range(32)]
        c = _dct_matrix()
        # A = C (8x32) @ X (32x32) ; B = A (8x32) @ C^T (32x8)
        a = [[sum(c[k][n] * x[n][j] for n in range(32)) for j in range(32)] for k in range(8)]
        b = [[sum(a[i][n] * c[k][n] for n in range(32)) for k in range(8)] for i in range(8)]
        flat = [v for row in b for v in row]
        med = _median(flat)
        phash = bits_to_int([v > med for v in flat])

        d = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        dp = list(d.getdata())
        dbits = [dp[r * 9 + col + 1] > dp[r * 9 + col] for r in range(8) for col in range(8)]
        dhash = bits_to_int(dbits)
    except Exception:
        return {"phash": None, "dhash": None, "width": w, "height": h}
    return {"phash": to_signed64(phash), "dhash": to_signed64(dhash), "width": w, "height": h}


def favicon_mmh3(data: bytes) -> int:
    """Shodan http.favicon.hash: mmh3 of the base64 (with newlines every 76 chars) encoding."""
    return mmh3.hash(base64.encodebytes(data))


_WORD = re.compile(r"\w+", re.UNICODE)


def words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def shingles(tokens: list[str], k: int = 3) -> set[str]:
    if len(tokens) < k:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i:i + k]) for i in range(len(tokens) - k + 1)}


def simhash64(text: str) -> int | None:
    sh = shingles(words(text), 3)
    if not sh:
        return None
    acc = [0] * 64
    for s in sh:
        h = mmh3.hash64(s, signed=False)[0]
        for i in range(64):
            acc[i] += 1 if (h >> i) & 1 else -1
    v = 0
    for i in range(64):
        if acc[i] > 0:
            v |= 1 << i
    return to_signed64(v)


N_PERM = 128
LSH_BANDS, LSH_ROWS = 16, 8          # threshold ≈ (1/16)^(1/8) ≈ 0.71 Jaccard


def minhash(items: set[str], n_perm: int = N_PERM) -> list[int] | None:
    if not items:
        return None
    mins = [0x7FFFFFFF] * n_perm
    for it in items:
        b = it.encode("utf-8", "ignore")
        for i in range(n_perm):
            h = mmh3.hash(b, seed=i, signed=True)
            if h < mins[i]:
                mins[i] = h
    return mins


def lsh_bands(sig: list[int], bands: int = LSH_BANDS, rows: int = LSH_ROWS) -> list[str]:
    out = []
    for b in range(bands):
        chunk = sig[b * rows:(b + 1) * rows]
        out.append(f"b{b}:{hashlib.md5(repr(chunk).encode()).hexdigest()[:16]}")
    return out


def jaccard_from_minhash(a: list[int], b: list[int]) -> float:
    return sum(x == y for x, y in zip(a, b)) / len(a)
