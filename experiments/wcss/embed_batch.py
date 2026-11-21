"""Batch embeddings on WCSS (CPU or GPU): text models x landing/ad text, SigLIP x screenshot + creative crop.
Input: texts.jsonl  {"id", "text", "ad_text", "shot", "crop":[x0,y0,x1,y1]|null}
Output: <out_dir>/emb_<model>_<field>.npy + ids.json + timings.json
Usage: python embed_batch.py texts.jsonl shots_dir out_dir [--models mmlw,bgem3,qwen3emb] [--siglip]"""
import argparse
import json
import os
import time

import numpy as np
import torch

ap = argparse.ArgumentParser()
ap.add_argument("texts")
ap.add_argument("shots")
ap.add_argument("out")
ap.add_argument("--models", default="mmlw,bgem3,qwen3emb")
ap.add_argument("--siglip", action="store_true")
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
dev = "cuda" if torch.cuda.is_available() else "cpu"
rows = [json.loads(x) for x in open(a.texts, encoding="utf-8")]
ids = [r["id"] for r in rows]
json.dump(ids, open(os.path.join(a.out, "ids.json"), "w"))
NAMES = {"mmlw": "sdadas/mmlw-roberta-base", "bgem3": "BAAI/bge-m3", "qwen3emb": "Qwen/Qwen3-Embedding-0.6B"}
timings = {"device": dev, "n": len(rows)}
from sentence_transformers import SentenceTransformer  # noqa: E402

for key in [k for k in a.models.split(",") if k in NAMES]:
    t0 = time.time()
    m = SentenceTransformer(NAMES[key], device=dev)
    m.max_seq_length = 512
    pre = "zapytanie: " if key == "mmlw" else ""
    for field in ("text", "ad_text"):
        X = m.encode([pre + (r.get(field) or "(brak)") for r in rows], batch_size=32, normalize_embeddings=True, show_progress_bar=False)
        np.save(os.path.join(a.out, f"emb_{key}_{field}.npy"), np.asarray(X, dtype=np.float32))
    timings[key] = round(time.time() - t0, 2)
    print(key, timings[key], "s", flush=True)
    del m

if a.siglip:
    from PIL import Image
    from transformers import AutoModel, AutoProcessor
    t0 = time.time()
    name = "google/siglip-base-patch16-224"
    model = AutoModel.from_pretrained(name).to(dev).eval()
    proc = AutoProcessor.from_pretrained(name)
    for field in ("shot", "crop"):
        feats = []
        for r in rows:
            p = os.path.join(a.shots, f"{r['id']}.png")
            if not os.path.exists(p):
                feats.append(np.full(768, np.nan, dtype=np.float32))
                continue
            img = Image.open(p).convert("RGB")
            if field == "crop" and r.get("crop"):
                img = img.crop(tuple(r["crop"]))
            with torch.no_grad():
                f = model.get_image_features(**proc(images=img, return_tensors="pt").to(dev))
            f = f.pooler_output if hasattr(f, "pooler_output") else f
            feats.append(torch.nn.functional.normalize(f, dim=-1)[0].float().cpu().numpy())
        np.save(os.path.join(a.out, f"emb_siglip_{field}.npy"), np.stack(feats))
    timings["siglip"] = round(time.time() - t0, 2)
    print("siglip", timings["siglip"], "s", flush=True)
json.dump(timings, open(os.path.join(a.out, "timings.json"), "w"), indent=1)
print("DONE", timings)
