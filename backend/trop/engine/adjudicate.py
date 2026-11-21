"""LLM adjudicator in the confirm band (RESULTS §4: 1 <= best score_campaign < 5). VETO / ANNOTATE ONLY.

The dossier is the one experiments/run_h_adjudicator.py built (extracted FEATURES only: ids, templates, infra metadata,
evidence list — no raw page text, captions or screenshots), sent through WS4's `trop.media.adjudicator.adjudicate`
(Gemini Flash, cached by sha256; offline replays the cache). The answer is attached to `Decision.adjudicator`; it can
never create a link or move a decision to `assign`. Unavailable (no key, cache miss offline, import error) -> None
plus a note, silently.
"""
from __future__ import annotations

import contextlib
import logging

from trop.schema import Adjudication

log = logging.getLogger(__name__)


def dossier(inc: dict) -> dict:
    t, c, la, ad = inc.get("tracking") or {}, inc.get("content") or {}, inc.get("landing") or {}, inc.get("ad") or {}
    inf = inc.get("infra") or {}
    dom = (inf.get("domains") or [{}])[0]
    e = dom.get("enrich") or {}
    return {
        "landing_domain": la.get("etld1"), "tld": dom.get("tld"), "registrar": e.get("registrar"),
        "domain_created": (e.get("created") or "")[:16], "nameservers": e.get("ns"), "cdn": inf.get("cdn"),
        "origin_ips": inf.get("origin_ips"), "fb_pixels": t.get("fb_pixels"), "capi_gateways": t.get("capi_gateways"),
        "google_ads": (t.get("google_ads") or []) + (t.get("ga4") or []), "kit_tenant_ids": t.get("kit_tenants"),
        "lander_ids": t.get("lander_ids"), "url_param_schema": t.get("url_param_schema"),
        "entry_path_template": t.get("entry_path_template"),
        "kit_endpoints": [k for k in t.get("kit_endpoints") or [] if not k.startswith("ASSET /_cdn")][:6],
        "third_party_services": t.get("third_party"), "n_asset_hashes": len(t.get("asset_hashes") or []),
        "headline_template": c.get("headline_template"), "impersonated_public_figures": c.get("persons"),
        "brands": c.get("brands"), "vertical": c.get("vertical"), "language": c.get("lang"), "products": c.get("products"),
        "ad_advertiser_page": ad.get("advertiser"), "ad_creative_is_decoy": ad.get("is_decoy"),
        "page_status": la.get("page_role"),
    }


@contextlib.contextmanager
def _respect_offline():
    """TROP_NO_LIVE=1 (`--offline`) -> gateway in offline mode for the call: cache replay only, no spend."""
    from trop.config import settings
    from trop.extract import cache
    old = settings.trop_mode
    if cache.offline():
        settings.trop_mode = "offline"
    try:
        yield
    finally:
        settings.trop_mode = old


def adjudicate_pair(q: dict, k: dict, ev: list[dict], score: float) -> tuple[Adjudication | None, str]:
    try:
        from trop.media.adjudicator import adjudicate  # WS4
    except ImportError as e:
        return None, f"adjudicator unavailable ({e.__class__.__name__})"
    evs = [{x: e[x] for x in ("type", "value", "weight")} for e in ev]
    d = {"a": dossier(q), "b": dossier(k), "evidence": evs, "engine_score": round(float(score), 3)}
    try:
        with _respect_offline():
            a = adjudicate(d)
    except Exception as e:  # noqa: BLE001 - never break a decision on the adjudicator
        log.warning("adjudicator failed: %s", e)
        return None, f"adjudicator error: {str(e)[:80]}"
    if a.model == "none" or (a.verdict == "unsure" and a.confidence == 0.0 and any("unavailable" in r for r in a.rationale)):
        return None, "adjudicator: no cached answer / no key (skipped)"
    return a, ""


def apply(decision, ctx: dict, corpus) -> str:
    """Confirm band only. Mutates `decision` (adjudicator + why_not annotation); returns a one-line note."""
    if decision.decision != "confirm" or not decision.candidate_campaign_id:
        return ""
    rows = [r for r in ctx["rows"] if corpus.campaign_of.get(r[0]["id"]) == decision.candidate_campaign_id]
    if not rows:
        return ""
    k, ev, s = max(rows, key=lambda r: r[2]["score_campaign"])
    q = ctx["query"]
    a, note = adjudicate_pair(q, k, ev, s["score_campaign"])
    if a is None:
        return note
    decision.adjudicator = a
    why = next((w for w in decision.why_not if w.campaign_id == decision.candidate_campaign_id), None)
    line = {"veto": "Sędzia (LLM): WETO — to nie ta sama kampania", "different": "Sędzia (LLM): raczej inna kampania",
            "same": "Sędzia (LLM): możliwe to samo — wymaga potwierdzenia analityka (LLM nie tworzy powiązań)",
            "unsure": "Sędzia (LLM): niepewne"}[a.verdict]
    line += f" ({a.confidence:.2f}): {(a.rationale or [''])[0][:160]}"
    if why is not None:
        why.bullets = [line] + why.bullets
    assert decision.decision != "assign"          # the adjudicator never links
    return line
