"""Approach (h): LLM adjudicator for pair decisions.

Dossier = EXTRACTED FEATURES ONLY (IDs, templates, infra metadata, evidence list) — no raw page text, no ad captions,
no screenshots — so it may go to a cloud LLM. Backends:
  claude  : `claude -p` headless CLI (cloud; features only)
  wcss    : writes dossiers to JSONL for wcss/adjudicate.py (Qwen3.8-27B / PLLuM on WCSS; may add raw text there)
Usage: uv run python run_h_adjudicator.py <incidents.json> claude|export [model] [n_workers]"""
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations

import numpy as np
from tabulate import tabulate

from rp import evidence, harness

INC, BACKEND = sys.argv[1], sys.argv[2]
MODEL = sys.argv[3] if len(sys.argv) > 3 else "haiku"
WORKERS = int(sys.argv[4]) if len(sys.argv) > 4 else 6
D = os.path.dirname(INC)
incs = json.load(open(INC, encoding="utf-8"))
L = harness.load_labels("labels.yaml")
gold = L["campaign"]
ids = [i["id"] for i in incs]
pairs = evidence.all_pairs(incs)


def dossier(inc):
    t, c, la, ad = inc["tracking"], inc["content"], inc["landing"], inc.get("ad", {})
    dom = (inc["infra"]["domains"] or [{}])[0]
    e = dom.get("enrich") or {}
    return {
        "landing_domain": la.get("etld1"), "tld": dom.get("tld"), "registrar": e.get("registrar"), "domain_created": (e.get("created") or "")[:16],
        "nameservers": e.get("ns"), "cdn": inc["infra"].get("cdn"), "origin_ips": inc["infra"].get("origin_ips"),
        "fb_pixels": t.get("fb_pixels"), "capi_gateways": t.get("capi_gateways"), "google_ads": t.get("google_ads") + t.get("ga4", []),
        "kit_tenant_ids": t.get("kit_tenants"), "lander_ids": t.get("lander_ids"), "url_param_schema": t.get("url_param_schema"),
        "entry_path_template": t.get("entry_path_template"), "kit_endpoints": [k for k in t.get("kit_endpoints", []) if not k.startswith("ASSET /_cdn")][:6],
        "third_party_services": t.get("third_party"), "n_asset_hashes": len(t.get("asset_hashes", [])),
        "headline_template": c.get("headline_template"), "impersonated_public_figures": c.get("persons"), "brands": c.get("brands"),
        "vertical": c.get("vertical"), "language": c.get("lang"), "products": c.get("products"),
        "ad_advertiser_page": ad.get("advertiser"), "ad_creative_is_decoy": ad.get("is_decoy"),
        "page_status": la.get("page_role"),
    }


SYSTEM = ("You are a CERT analyst attributing online scam ads to campaigns. A 'campaign' = one scam operation: the same "
          "operator infrastructure AND the same narrative/offer family (variants with swapped persons/domains/headlines are "
          "the same campaign). Shared commercial tooling (a multi-tenant landing kit, Cloudflare IPs, jQuery, Facebook SDK) "
          "is NOT evidence. Same operator account (kit tenant id, Cloudflare nameserver pair) running a different product "
          "or story is the same OPERATOR but a DIFFERENT campaign. Missing data is not evidence of difference. Be precise: "
          "a wrong link is worse than a missed one.")
SCHEMA = {"type": "object", "properties": {"same_campaign": {"type": "boolean"}, "same_operator": {"type": "boolean"},
                                            "confidence": {"type": "number"}, "rationale": {"type": "string"}},
          "required": ["same_campaign", "same_operator", "confidence", "rationale"]}


def prompt(a, b, ev):
    evs = [{k: e[k] for k in ("type", "value", "weight")} for e in sorted(ev, key=lambda e: -abs(e["weight"]))[:14]]
    return (f"{SYSTEM}\n\nIncident A features:\n{json.dumps(dossier(a), ensure_ascii=False)}\n\nIncident B features:\n"
            f"{json.dumps(dossier(b), ensure_ascii=False)}\n\nAutomatically computed shared evidence (type, value, weight):\n"
            f"{json.dumps(evs, ensure_ascii=False)}\n\nAre A and B the same campaign? Answer ONLY with JSON: "
            '{"same_campaign": bool, "same_operator": bool, "confidence": 0..1, "rationale": "<=40 words"}')


jobs = []
for (i, j), (ev, s) in pairs.items():
    jobs.append({"a": ids[i], "b": ids[j], "gold_same": gold[ids[i]] == gold[ids[j]], "score": s["score_campaign"], "prompt": prompt(incs[i], incs[j], ev)})
json.dump([{k: v for k, v in jb.items()} for jb in jobs], open(os.path.join(D, "adjudicator_dossiers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if BACKEND == "export":
    with open(os.path.join(D, "adjudicator_dossiers.jsonl"), "w", encoding="utf-8") as f:
        for jb in jobs:
            f.write(json.dumps(jb, ensure_ascii=False) + "\n")
    print("exported", len(jobs))
    sys.exit(0)

CWD = os.environ.get("TEMP", ".")


def run_claude(jb):
    t0 = time.time()
    try:
        p = subprocess.run(["claude", "-p", "--model", MODEL, "--output-format", "json", "--no-session-persistence",
                            "--strict-mcp-config", "--system-prompt", SYSTEM, "--json-schema", json.dumps(SCHEMA)],
                           input=jb["prompt"], capture_output=True, text=True, encoding="utf-8", timeout=180, cwd=CWD)
        out = json.loads(p.stdout)
        res = out.get("structured_output") or json.loads(out.get("result", "{}").strip().strip("`").removeprefix("json"))
        jb["cost_usd"] = out.get("total_cost_usd")
        jb["usage"] = out.get("usage")
    except Exception as e:  # noqa: BLE001
        res = {"error": str(e)[:200], "stdout": (p.stdout[:300] if "p" in dir() else "")}
    jb["verdict"] = res
    jb["secs"] = round(time.time() - t0, 1)
    return jb


t0 = time.time()
with ThreadPoolExecutor(WORKERS) as ex:
    done = list(ex.map(run_claude, jobs))
wall = time.time() - t0
ok = [d for d in done if "same_campaign" in d["verdict"]]
acc = np.mean([d["verdict"]["same_campaign"] == d["gold_same"] for d in ok]) if ok else 0
band = [d for d in ok if 1.0 <= d["score"] < 10.0]
acc_band = np.mean([d["verdict"]["same_campaign"] == d["gold_same"] for d in band]) if band else None
fp = sum(d["verdict"]["same_campaign"] and not d["gold_same"] for d in ok)
fn = sum((not d["verdict"]["same_campaign"]) and d["gold_same"] for d in ok)
cost = sum(d.get("cost_usd") or 0 for d in ok)
print(f"model={MODEL} parsed {len(ok)}/{len(done)} | pair accuracy {acc:.3f} | FP {fp} FN {fn} | uncertain band (1<=score<10): n={len(band)} acc={acc_band}")
print(f"wall {wall:.0f}s with {WORKERS} workers, mean {np.mean([d['secs'] for d in done]):.1f}s/call, total cost ${cost:.3f}")
for d in ok:
    if d["verdict"]["same_campaign"] != d["gold_same"] or 1.0 <= d["score"] < 10.0:
        print(f"  {d['a']}-{d['b']} gold={d['gold_same']} score={d['score']} -> {d['verdict']['same_campaign']} (op={d['verdict'].get('same_operator')}, conf={d['verdict'].get('confidence')}) {d['verdict'].get('rationale','')[:140]}")
json.dump(done, open(os.path.join(D, f"adjudicator_{MODEL}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
