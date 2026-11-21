"""Score adjudicator outputs (WCSS jsonl or cloud json): accuracy overall, in the uncertain band, FP/FN."""
import json, re, sys
import numpy as np
for path in sys.argv[1:]:
    rows = [json.loads(x) for x in open(path, encoding="utf-8")] if path.endswith(".jsonl") else json.load(open(path, encoding="utf-8"))
    ok = []
    for r in rows:
        v = r.get("verdict")
        if v is None:
            m = re.search(r"\{.*\}", r.get("raw", ""), re.S)
            try:
                v = json.loads(m.group(0)) if m else {}
            except Exception:
                v = {}
        if "same_campaign" in v:
            r["v"] = v
            ok.append(r)
    acc = np.mean([r["v"]["same_campaign"] == r["gold_same"] for r in ok])
    band = [r for r in ok if 1.0 <= r["score"] < 10.0]
    fp = [f"{r['a']}-{r['b']}" for r in ok if r["v"]["same_campaign"] and not r["gold_same"]]
    fn = [f"{r['a']}-{r['b']}" for r in ok if not r["v"]["same_campaign"] and r["gold_same"]]
    tok = [((r.get("usage") or {}).get("prompt_tokens") or (r.get("usage") or {}).get("input_tokens") or 0, (r.get("usage") or {}).get("completion_tokens") or (r.get("usage") or {}).get("output_tokens") or 0) for r in ok]
    print(f"{path.split('/')[-1]}: parsed {len(ok)}/{len(rows)} acc={acc:.3f} | band n={len(band)} acc={np.mean([r['v']['same_campaign']==r['gold_same'] for r in band]) if band else None} | FP {len(fp)} {fp[:8]} | FN {len(fn)} {fn[:8]} | mean tokens in/out {np.mean([t[0] for t in tok]):.0f}/{np.mean([t[1] for t in tok]):.0f} | mean {np.mean([r.get('secs',0) for r in ok]):.1f}s")
