"""Oracle service: train the campaign DNA, score certificate sightings, persist/list predictions, confirm, metrics.

API/worker entry points
    list_predictions(status=None, limit=50) -> list[OraclePrediction]
    get_dna(campaign_id=None) -> DomainDNA | None            get_metrics() -> OracleMetrics
    poll_once() -> dict   (scheduler job; emits `oracle.match` via set_notifier)
    score_domain(domain, enrich=None, issuer=None) -> OraclePrediction | None
Persistence: <data_dir>/oracle/{model.pkl, dna.json, predictions.json, backtest.json, poll_state.json}
"""
from __future__ import annotations

import json
import pickle
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Callable

import numpy as np

from trop.enrich import dns, rdap
from trop.enrich.util import etld1, parse_ts
from trop.schema import DomainDNA, OracleMetrics, OraclePrediction

from . import backtest as bt
from . import ct, data
from .model import DomainModel, build_dna, logit, meta_bonus, sigmoid, split_domain

CAMPAIGN_ID = "KIT-A"          # replaced by the engine's KMP id when the campaign is promoted
_notifier: Callable[[OraclePrediction], None] | None = None
_cache: dict[str, Any] = {}


def set_notifier(fn: Callable[[OraclePrediction], None] | None) -> None:
    """The worker registers a function that publishes `oracle.match` SSE events."""
    global _notifier
    _notifier = fn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------------------------------ training
def train(campaign_id: str = CAMPAIGN_ID, refresh: bool = False, run_backtest: bool = True, fpr: float = 0.02) -> dict[str, Any]:
    recs = data.load_training(refresh)
    neg = data.load_negatives()
    pos = [r for r in recs if r.get("domain")]
    cv_auc = bt.cross_val_auc(pos, neg)
    out: dict[str, Any] = {"n_pos": len(pos), "n_neg": len(neg), "cv_auc": cv_auc}
    if run_backtest:
        res = bt.run_backtest(pos, neg, fpr=fpr)
        res["summary"]["cv_auc_5fold"] = cv_auc
        (data.oracle_dir() / "backtest.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        out["backtest"] = res["summary"]
    # final model on everything; threshold: FPR budget on out-of-sample negatives (half/half)
    import random
    rng = random.Random(5)
    N = neg[:]
    rng.shuffle(N)
    half = len(N) // 2
    m_thr = DomainModel().fit([r["domain"] for r in pos], [r["domain"] for r in N[:half]])
    thr = bt.threshold_for_fpr(m_thr.p_lex([r["domain"] for r in N[half:]]), fpr)
    model = DomainModel().fit([r["domain"] for r in pos], [r["domain"] for r in neg])
    dna = build_dna(campaign_id, pos, cv_auc, round(float(thr), 3))
    d = data.oracle_dir()
    (d / "model.pkl").write_bytes(pickle.dumps(model))
    (d / "dna.json").write_text(dna.model_dump_json(indent=1), encoding="utf-8")
    _cache.clear()
    out["threshold"] = dna.threshold
    out["dna"] = dna.model_dump()
    return out


def load_model() -> tuple[DomainModel, DomainDNA]:
    if "model" not in _cache:
        d = data.oracle_dir()
        if not (d / "model.pkl").is_file():
            train(run_backtest=False)
        _cache["model"] = pickle.loads((d / "model.pkl").read_bytes())
        _cache["dna"] = DomainDNA.model_validate_json((d / "dna.json").read_text(encoding="utf-8"))
    return _cache["model"], _cache["dna"]


def get_dna(campaign_id: str | None = None) -> DomainDNA | None:
    try:
        return load_model()[1]
    except Exception:
        return None


# ------------------------------------------------------------------------------------------ scoring
def score_domain(domain: str, enrich: dict | None = None, issuer: str | None = None, issued_at: str | None = None,
                 use_meta: bool = True) -> tuple[float, list[str]]:
    """-> (dna_score 0..1, reasons). Stage 1: lexical LR on label + TLD. Stage 2 (when `enrich` given): NS pair / registrar / ASN."""
    model, dna = load_model()
    p = float(model.p_lex([etld1(domain)])[0])
    reasons = [f"lexical {p:.2f}: " + ", ".join(model.explain(etld1(domain)))] if p > 0.2 else [f"lexical {p:.2f}"]
    lo = logit(p)
    if use_meta and enrich:
        b, why = meta_bonus(dna, enrich, issuer)
        lo += b
        reasons += why
    return round(sigmoid(lo), 3), reasons


def _preds() -> dict[str, dict]:
    p = data.oracle_dir() / "predictions.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def _save_preds(d: dict[str, dict]) -> None:
    (data.oracle_dir() / "predictions.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def predict(entries: list[dict], enrich_hits: bool = True, notify: bool = True, issuer_default: str | None = None) -> list[OraclePrediction]:
    """Score cert sightings; hits above the campaign threshold become (stored) predictions."""
    model, dna = load_model()
    tl = set(dna.tld_dist)
    cand = [e for e in entries if split_domain(e["domain"])[1] in tl]
    if not cand:
        return []
    p1 = model.p_lex([etld1(e["domain"]) for e in cand])
    store = _preds()
    out: list[OraclePrediction] = []
    for e, p in zip(cand, p1):
        if p < dna.threshold * 0.6:                     # cheap gate before resolving anything
            continue
        dom = etld1(e["domain"])
        if dom in store:
            continue
        enr = None
        if enrich_hits:
            try:
                rd, rec = rdap.lookup(dom), dns.records(dom)
                enr = {"ns": dns.ns_of(dom), "registrar": rd.get("registrar"), "created": rd.get("created")}
            except Exception:
                enr = None
        score, reasons = score_domain(dom, enr, e.get("issuer"))
        if score < dna.threshold:
            continue
        pred = OraclePrediction(domain=dom, issued_at=str(e.get("not_before") or _now()), issuer=e.get("issuer"), dna_score=score,
                                campaign_id=dna.campaign_id, status="predicted", reasons=reasons[:6])
        store[dom] = pred.model_dump()
        out.append(pred)
        if notify and _notifier:
            _notifier(pred)
    if out:
        _save_preds(store)
    return out


def list_predictions(status: str | None = None, limit: int = 50) -> list[OraclePrediction]:
    rows = [OraclePrediction(**v) for v in _preds().values()]
    if status:
        rows = [r for r in rows if r.status == status]
    return sorted(rows, key=lambda r: r.issued_at, reverse=True)[:limit]


def confirm(domain: str, first_ad_at: str | None = None) -> OraclePrediction | None:
    store = _preds()
    v = store.get(etld1(domain))
    if not v:
        return None
    v["status"], v["first_ad_at"] = "confirmed", first_ad_at or _now()
    a, b = parse_ts(v["issued_at"]), parse_ts(v["first_ad_at"])
    if a and b:
        v["lead_time_h"] = round((b - a).total_seconds() / 3600, 1)
    _save_preds(store)
    return OraclePrediction(**v)


def reconcile() -> int:
    """Confirm predictions whose domain later shows up in a Hunter draft / the corpus (landing etld1)."""
    store = _preds()
    open_ = {k for k, v in store.items() if v["status"] == "predicted"}
    if not open_:
        return 0
    hits: dict[str, str] = {}
    for p in sorted((Path(data.settings.data_dir) / "hunter").glob("HR-*/draft_*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        dom = (d.get("landing") or {}).get("etld1")
        if dom in open_:
            hits[dom] = (d.get("source") or {}).get("captured_at") or _now()
    for dom, at in hits.items():
        confirm(dom, at)
    return len(hits)


# ------------------------------------------------------------------------------------------ polling
def poll_once(use_urlscan: bool = True, certstream_s: float = 20.0) -> dict[str, Any]:
    """One poll: certstream (if a server listens) + urlscan-recent on the campaign TLDs -> predictions."""
    _, dna = load_model()
    tlds = list(dna.tld_dist)[:8]
    entries = ct.certstream_collect(tlds, certstream_s) if certstream_s else []
    n_stream = len(entries)
    if use_urlscan:
        entries += ct.urlscan_recent(tlds, hours=24)
    preds = predict(entries)
    confirmed = reconcile()
    st = {"at": _now(), "seen": len(entries), "from_certstream": n_stream, "new_predictions": len(preds), "confirmed": confirmed,
          "ct_rate_per_h": round(n_stream / max(certstream_s, 1) * 3600, 1) if n_stream else None}
    (data.oracle_dir() / "poll_state.json").write_text(json.dumps(st))
    return st


def get_metrics() -> OracleMetrics:
    preds = list_predictions(limit=10000)
    day = datetime.now(timezone.utc) - timedelta(hours=24)
    flagged = [p for p in preds if (parse_ts(p.issued_at) or day) >= day]
    leads = [p.lead_time_h for p in preds if p.lead_time_h is not None]
    bpath = data.oracle_dir() / "backtest.json"
    pk20, back, med = None, [], None
    if bpath.is_file():
        b = json.loads(bpath.read_text(encoding="utf-8"))
        s = b["summary"]
        pk20 = (s.get("precision_at_k", {}).get("1:10") or {}).get("p@20")
        med = s.get("median_lead_h_positive")
        back = [{"domain": r["domain"], "flagged_at": r["flagged_at"], "first_ad_at": r["first_ad_at"], "lead_h": r["lead_h"]}
                for r in b["rows"] if r["flagged"] and r["lead_h"] is not None][:30]
    rate = None
    sp = data.oracle_dir() / "poll_state.json"
    if sp.is_file():
        rate = json.loads(sp.read_text()).get("ct_rate_per_h")
    return OracleMetrics(flagged_24h=len(flagged), confirmed=sum(p.status == "confirmed" for p in preds), precision_at_20=pk20,
                         median_lead_h=round(median(leads), 1) if leads else med, ct_rate_per_h=rate,
                         false_alarms_24h=sum(p.status == "dismissed" for p in flagged), backtest=back)
