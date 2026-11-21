"""Extract Incident JSON for a sample_dir corpus. Usage: uv run python run_extract.py <root> <out.json>"""
import json, sys, time
from rp.extract import load_sample_dir
t = time.time()
incs = load_sample_dir(sys.argv[1])
for i in incs:
    i["landing"].pop("dom_paths_full", None)
json.dump(incs, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=list)
print(f"{len(incs)} incidents in {time.time()-t:.1f}s -> {sys.argv[2]}")
