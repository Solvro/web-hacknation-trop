"""Embeddings (approach b and the emb.* evidence types). CPU locally; same code runs batch on WCSS.

Text models: sdadas/mmlw-roberta-base (PL), BAAI/bge-m3 (multilingual), Qwen/Qwen3-Embedding-0.6B.
Image model: google/siglip-base-patch16-224 on the ad creative crop and the full screenshot.
"""
from __future__ import annotations

import os
import time

import numpy as np

TEXT_MODELS = {
    "mmlw": "sdadas/mmlw-roberta-base",
    "bgem3": "BAAI/bge-m3",
    "qwen3emb": "Qwen/Qwen3-Embedding-0.6B",
}
IMAGE_MODEL = "google/siglip-base-patch16-224"


def landing_text(inc: dict, with_ad: bool = True, max_chars: int = 2000) -> str:
    la, ad = inc.get("landing", {}), inc.get("ad", {})
    if la.get("page_role") == "error":
        parts = []
    else:
        parts = [la.get("title") or "", " ".join(la.get("h1") or []), (la.get("text") or "")[:max_chars]]
    if with_ad:
        parts += [ad.get("text") or "", ad.get("overlay") or ""]
    return "\n".join(p for p in parts if p).strip() or "(brak treści)"


def embed_texts(texts: list[str], model_key: str = "mmlw") -> tuple[np.ndarray, float]:
    from sentence_transformers import SentenceTransformer
    name = TEXT_MODELS[model_key]
    t0 = time.time()
    m = SentenceTransformer(name, device="cpu", trust_remote_code=False)
    m.max_seq_length = 512
    prefix = "zapytanie: " if model_key == "mmlw" else ""
    X = m.encode([prefix + t for t in texts], batch_size=8, normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(X, dtype=np.float32), time.time() - t0


def embed_images(paths: list[str | None], crops: list | None = None) -> tuple[np.ndarray, float]:
    import torch
    from PIL import Image
    from transformers import AutoModel, AutoProcessor
    t0 = time.time()
    model = AutoModel.from_pretrained(IMAGE_MODEL).eval()
    proc = AutoProcessor.from_pretrained(IMAGE_MODEL)
    out = []
    for k, p in enumerate(paths):
        if not p or not os.path.exists(p):
            out.append(None)
            continue
        img = Image.open(p).convert("RGB")
        if crops and crops[k]:
            img = img.crop(tuple(crops[k]))
        with torch.no_grad():
            f = model.get_image_features(**proc(images=img, return_tensors="pt"))
        f = f.pooler_output if hasattr(f, "pooler_output") else f
        f = torch.nn.functional.normalize(f, dim=-1)[0].numpy()
        out.append(f.astype(np.float32))
    dim = next((x.shape[0] for x in out if x is not None), 768)
    X = np.stack([x if x is not None else np.full(dim, np.nan, dtype=np.float32) for x in out])
    return X, time.time() - t0
