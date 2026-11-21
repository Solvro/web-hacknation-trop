"""Screenshot layer: kind detection, creative crop, pHash, OCR (EasyOCR, CPU) -> ad.* fields.

Two screenshot kinds exist in sample_v1:
  * 'adlibrary' — Meta Ad Library "Szczegóły reklamy" modal (has 'Identyfikator biblioteki', status, start date)
  * 'feed'      — feed-style capture of the sponsored post (advertiser, 'Sponsorowane', creative, CTA, caption)
"""
from __future__ import annotations

import re

import imagehash
import numpy as np
from PIL import Image

_OCR = None


def ocr_reader():
    global _OCR
    if _OCR is None:
        import easyocr
        _OCR = easyocr.Reader(["pl", "en"], gpu=False, verbose=False)
    return _OCR


def creative_bbox(img: Image.Image) -> tuple[int, int, int, int]:
    """Largest 'busy' block = the creative (photo/video still). Row/col variance projection, no learned model."""
    g = np.asarray(img.convert("L"), dtype=np.float32)
    h, w = g.shape
    # local busy-ness: absolute horizontal gradient
    grad = np.abs(np.diff(g, axis=1))
    row_busy = (grad > 12).mean(axis=1)
    rows = row_busy > 0.25
    # longest run of busy rows
    best, cur, start, bstart = 0, 0, 0, 0
    for i, r in enumerate(rows):
        if r:
            if cur == 0:
                start = i
            cur += 1
            if cur > best:
                best, bstart = cur, start
        else:
            cur = 0
    if best < h * 0.15:
        return (0, 0, w, h)
    y0, y1 = bstart, bstart + best
    col_busy = (np.abs(np.diff(g[y0:y1], axis=0)) > 12).mean(axis=0)
    cols = np.where(col_busy > 0.2)[0]
    x0, x1 = (int(cols.min()), int(cols.max())) if len(cols) else (0, w)
    return (x0, y0, x1, y1)


def phash_hex(img: Image.Image) -> str:
    return str(imagehash.phash(img, hash_size=8))


def parse_ocr(lines: list[tuple], kind: str) -> dict:
    """lines: [(bbox, text, conf)] in reading order. Heuristic field extraction (the VLM does this better)."""
    texts = [t.strip() for _, t, c in lines if t.strip()]
    full = " \n".join(texts)
    out = {"ocr_text": full}
    m = re.search(r"Identyfikator biblioteki[:\s]*([0-9]{12,17})", full)
    out["library_id"] = m.group(1) if m else None
    m = re.search(r"\b([A-Z0-9-]+\.(?:COM|PL|NET|ORG|SHOP|STORE))\b", full)
    out["display_link"] = m.group(1) if m else None
    # advertiser = the line right above 'Sponsorowane'
    adv = None
    for i, t in enumerate(texts):
        if t.lower().startswith("sponsorowan") and i > 0:
            adv = texts[i - 1]
            break
    out["advertiser"] = adv
    m = re.search(r"(Dowiedz się więcej|Wyświetl szczegóły|Learn More|Kup teraz|Zarejestruj się|Poznaj szczegóły|Shop now)", full, re.I)
    out["cta"] = m.group(1) if m else None
    # caption: text after the CTA (feed) or after 'Sponsorowane'/library id line (adlibrary)
    cap = ""
    if kind == "feed" and out["cta"]:
        idx = next((i for i, t in enumerate(texts) if out["cta"].lower() in t.lower()), None)
        if idx is not None:
            cap = " ".join(t for t in texts[idx + 1:] if not re.fullmatch(r"[\d\s]+|więcej", t, re.I))
    elif kind == "adlibrary":
        idx = next((i for i, t in enumerate(texts) if t.lower().startswith("identyfikator biblioteki")), None)
        rest = texts[idx + 1:] if idx is not None else texts
        rest = [t for t in rest if not re.search(r"identyfikator|sponsorowan|transparentno|reklamodaw|płatnik|informacje o", t, re.I)]
        cap = " ".join(rest[:3])
    out["text"] = re.sub(r"\s+", " ", cap).strip()[:400]
    m = re.search(r"(?:Data zamieszczenia|Rozpoczęcie wyświetlania)[:\s]*([0-9]{1,2} \w+ 20\d\d)", full)
    out["start_date"] = m.group(1) if m else None
    return out


def analyze_screenshot(path: str, do_ocr: bool = True) -> dict:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    res = {"screenshot_w": w, "screenshot_h": h}
    lines = []
    if do_ocr:
        r = ocr_reader().readtext(np.asarray(img), detail=1, paragraph=False)
        lines = sorted(r, key=lambda x: (round(x[0][0][1] / 12), x[0][0][0]))
    blob = " ".join(t for _, t, _ in lines).lower()
    kind = "adlibrary" if ("szczegóły reklamy" in blob or "identyfikator biblioteki" in blob or (w > 1.8 * h)) else "feed"
    res["screenshot_kind"] = kind
    x0, y0, x1, y1 = creative_bbox(img if kind == "feed" else img.crop((0, 0, int(w * 0.36), h)))
    crop = (img if kind == "feed" else img.crop((0, 0, int(w * 0.36), h))).crop((x0, y0, x1, y1))
    res["creative_bbox"] = [x0, y0, x1, y1]
    res["creative_phash"] = phash_hex(crop)
    res["screenshot_phash"] = phash_hex(img)
    if do_ocr:
        res.update(parse_ocr(lines, kind))
    return res
