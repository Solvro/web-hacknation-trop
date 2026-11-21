"""LLM adjudicator for borderline pair decisions (RESULTS §2a/h). VETO / ANNOTATE ONLY: its answer can cancel or annotate a
candidate link, it never creates one. Input is a dossier of extracted FEATURES (no raw page text / screenshots).

dossier = {"prompt": str}                              # as exported by experiments/run_h_adjudicator.py, or
          {"a": {...features}, "b": {...features}, "evidence": [{"type","value","weight"}], "engine_score": float?}
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from trop.config import settings
from trop.media.gateway import gateway
from trop.schema import Adjudication

SYSTEM = ("You are a CERT analyst attributing online scam ads to campaigns. A 'campaign' = one scam operation: the same "
          "operator infrastructure AND the same narrative/offer family (variants with swapped persons/domains/headlines are "
          "the same campaign). Shared commercial tooling (a multi-tenant landing kit, Cloudflare IPs, jQuery, Facebook SDK) "
          "is NOT evidence. Same operator account (kit tenant id, Cloudflare nameserver pair) running a different product "
          "or story is the same OPERATOR but a DIFFERENT campaign. Missing data is not evidence of difference. Be precise: "
          "a wrong link is worse than a missed one.")
SCHEMA = {"type": "object",
          "properties": {"same_campaign": {"type": "boolean"}, "same_operator": {"type": "boolean"},
                         "confidence": {"type": "number"}, "rationale": {"type": "string"}},
          "required": ["same_campaign", "same_operator", "confidence", "rationale"]}
VETO_CONF = 0.8


# Production (Raport) asks for the rationale in Polish as 2–3 short bullets; the decision part of the prompt (system
# text, features, evidence, question, verdict/confidence fields) is identical to the benchmarked English prompt.
SCHEMA_PL = {"type": "object",
             "properties": {"same_campaign": {"type": "boolean"}, "same_operator": {"type": "boolean"},
                            "confidence": {"type": "number"},
                            "rationale": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3}},
             "required": ["same_campaign", "same_operator", "confidence", "rationale"]}
RATIONALE_PL = ('Answer ONLY with JSON: {"same_campaign": bool, "same_operator": bool, "confidence": 0..1, '
                '"rationale": ["2-3 short bullets IN POLISH, plain words for a non-technical reader, no jargon '
                '(say e.g. \'te same pliki strony\' not \'asset hash\'); identifiers such as domains or pixel ids may stay '
                'as they are; each bullet <= 20 words"]}')


def build_prompt(d: dict, lang: str = "en") -> str:
    if d.get("prompt"):
        return d["prompt"]
    evs = sorted(d.get("evidence") or [], key=lambda e: -abs(e.get("weight", 0)))[:14]
    tail = (RATIONALE_PL if lang == "pl" else
            'Answer ONLY with JSON: {"same_campaign": bool, "same_operator": bool, "confidence": 0..1, "rationale": "<=40 words"}')
    return (f"{SYSTEM}\n\nIncident A features:\n{json.dumps(d.get('a'), ensure_ascii=False)}\n\nIncident B features:\n"
            f"{json.dumps(d.get('b'), ensure_ascii=False)}\n\nAutomatically computed shared evidence (type, value, weight):\n"
            f"{json.dumps(evs, ensure_ascii=False)}\n\nAre A and B the same campaign? {tail}")


def adjudicate_raw(dossier: dict, model: str = "flash", task: str = "adjudicate", lang: str = "en") -> dict[str, Any]:
    return gateway.llm(task, [{"role": "user", "content": build_prompt(dossier, lang)}],
                       json_schema=SCHEMA_PL if lang == "pl" else SCHEMA, model=model)


def _rationale(j: dict) -> list[str]:
    r = j.get("rationale")
    items = r if isinstance(r, list) else [r]
    return [str(x).strip()[:300] for x in items if x and str(x).strip()][:3]


def to_adjudication(r: dict, dossier: dict | None = None) -> Adjudication:
    j = r.get("json") or {}
    model = r.get("model") or "none"
    if r.get("missing") or "same_campaign" not in j:
        return Adjudication(model=model, verdict="unsure", confidence=0.0,
                            rationale=["adjudicator unavailable: " + str(r.get("error", "no answer"))[:120]])
    conf = max(0.0, min(1.0, float(j.get("confidence") or 0.0)))
    same_op = ("ten sam operator" if isinstance(j.get("rationale"), list) else "same operator")
    rat = _rationale(j) + ([same_op] if j.get("same_operator") else [])
    if j["same_campaign"]:
        verdict = "same" if conf >= 0.5 else "unsure"
    else:
        # a different-campaign answer on a link the engine proposed (engine_score given) is a veto when confident
        verdict = "veto" if (dossier or {}).get("engine_score") is not None and conf >= VETO_CONF else "different"
    return Adjudication(model=model, verdict=verdict, confidence=conf, rationale=[x for x in rat if x])


def adjudicate(dossier: dict, model: str = "flash", lang: str = "pl") -> Adjudication:
    """Production entry point (engine confirm band): Polish rationale bullets. Verdict/confidence parsing unchanged."""
    return to_adjudication(adjudicate_raw(dossier, model, lang=lang), dossier)


def benchmark(model: str = "flash", workers: int = 6, dossiers: Path | None = None, out: Path | None = None) -> dict:
    d = Path(settings.data_dir) / "experiments" / "sample_v1"
    dossiers = dossiers or d / "adjudicator_dossiers.jsonl"
    tag = {"flash": "gemini_flash", "pro": "gemini_pro"}.get(model, model.replace("/", "_"))
    out = out or d / f"adj_{tag}.jsonl"
    jobs = [json.loads(x) for x in dossiers.read_text(encoding="utf-8").splitlines() if x.strip()]
    t0 = time.time()

    def one(jb: dict) -> dict:
        r = adjudicate_raw(jb, model, task="adjudicate-bench")
        j = r.get("json") or {}
        return {"a": jb["a"], "b": jb["b"], "gold_same": jb["gold_same"], "score": jb["score"], "verdict": j,
                "model": r.get("model"), "cost_usd": r.get("cost_usd"), "cached": r.get("cached"), "error": r.get("error")}

    with ThreadPoolExecutor(workers) as ex:
        rows = list(ex.map(one, jobs))
    with open(out, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    ok = [r for r in rows if "same_campaign" in r["verdict"]]
    fp = [r for r in ok if r["verdict"]["same_campaign"] and not r["gold_same"]]
    fn = [r for r in ok if not r["verdict"]["same_campaign"] and r["gold_same"]]
    acc = (len(ok) - len(fp) - len(fn)) / len(ok) if ok else 0.0
    band = [r for r in ok if 1.0 <= r["score"] < 10.0]
    acc_band = sum(r["verdict"]["same_campaign"] == r["gold_same"] for r in band) / len(band) if band else None
    return {"model": model, "pairs": len(rows), "parsed": len(ok), "accuracy": round(acc, 4), "FP": len(fp), "FN": len(fn),
            "band_1_10": {"n": len(band), "acc": acc_band}, "cost_usd": round(sum(r.get("cost_usd") or 0 for r in rows), 4),
            "wall_s": round(time.time() - t0), "out": str(out),
            "fp_pairs": [(r["a"], r["b"], r["score"], r["verdict"].get("rationale", "")[:160]) for r in fp],
            "fn_pairs": [(r["a"], r["b"], r["score"], r["verdict"].get("rationale", "")[:160]) for r in fn]}
