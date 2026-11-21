"""Approach (h) on WCSS: local LLM adjudicator (stdlib only). Same feature dossier as the cloud run, optionally + raw
landing/ad excerpts (allowed on WCSS). Run inside the allocation serving the model:
  srun --jobid=<JOB> --overlap -n1 -c4 --mem=4G python3 adjudicate.py dossiers.jsonl out.jsonl name:port [raw|features] [workers]"""
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

KEY = open("/lustre/pd03/hpc-dawlin1140-1773687823/hacknation/.api_key").read().strip()
inp, out, target = sys.argv[1], sys.argv[2], sys.argv[3]
mode = sys.argv[4] if len(sys.argv) > 4 else "features"
workers = int(sys.argv[5]) if len(sys.argv) > 5 else 8
name, port = target.split(":")
jobs = [json.loads(x) for x in open(inp, encoding="utf-8")]


def call(jb):
    content = jb["prompt"]
    if mode == "raw" and jb.get("raw_a"):
        content += ("\n\nRaw excerpts (landing title + start of text + ad caption):\nA: " + jb["raw_a"][:900] +
                    "\nB: " + jb["raw_b"][:900])
    body = {"model": name, "temperature": 0, "max_tokens": 300, "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": content}]}
    req = urllib.request.Request(f"http://localhost:{port}/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    t = time.time()
    try:
        d = json.load(urllib.request.urlopen(req, timeout=300))
        txt = d["choices"][0]["message"].get("content") or ""
        usage = d.get("usage")
    except Exception as e:  # noqa: BLE001
        txt, usage = "ERROR " + str(e)[:200], None
    return {"a": jb["a"], "b": jb["b"], "gold_same": jb["gold_same"], "score": jb["score"], "raw": txt, "usage": usage,
            "secs": round(time.time() - t, 2), "model": name, "mode": mode}


t0 = time.time()
with ThreadPoolExecutor(workers) as ex, open(out, "w", encoding="utf-8") as fo:
    for r in ex.map(call, jobs):
        fo.write(json.dumps(r, ensure_ascii=False) + "\n")
print("done", len(jobs), "in", round(time.time() - t0, 1), "s")
