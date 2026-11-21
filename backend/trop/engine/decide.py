"""Open-set decision for one incident against the known corpus (RESULTS §4 DECIDE), and pair explanations.

States (thresholds fixed, docs/CONTRACTS.md §1):
  L0 duplicate  same entry URL with a visit/click id, or text MinHash >= 0.9 and creative pHash <= 6 -> duplicate_of
  assign        max-linkage score_campaign >= tau (5) and margin >= delta (1)
  ambiguous     best >= 5 but a second campaign within the margin
  insufficient  (not assignable and) no landing content and no ad layer
  confirm       1 <= best < 5 (adjudicator may veto/annotate)
  new           best < 1; flag same_operator_as when score_operator >= 3
"""
from __future__ import annotations

import re
from collections import defaultdict

from trop.schema import (CampaignScore, Counterfactual, Decision, EvidenceItem, LayerCoverage, LinkExplanation, RunnerUp,
                         WhyNot)

from . import calibration, cluster, evidence
from .items import LABEL, to_item

TAU, DELTA, CONFIRM_FLOOR, OP_TAU = 5.0, 1.0, 1.0, 3.0
CONTRAST_TYPES = ["fb_pixel", "capi_gateway", "google_ads", "ga4", "gtm", "tiktok_pixel", "kit_tenant", "lander_id",
                  "landing_type_id", "video_host", "etld1", "advertiser", "headline_template", "products"]
CONTENT_LAYERS = ("content", "ad", "persons", "visual")


# ------------------------------------------------------------------------------------------------ scoring
def score_against(q: dict, known: list[dict]) -> tuple[list[tuple[dict, list, dict]], dict, int]:
    """Pair evidence of q vs every known incident (df over known + q, exactly as the experiments' decide())."""
    known = [k for k in known if k["id"] != q["id"]]
    sub = known + [q]
    evidence.prepare(sub)
    df = evidence.doc_freq(sub)
    n = len(sub)
    rows = []
    for k in known:
        ev, s = evidence.pair_evidence(q, k, df, n)
        rows.append((k, ev, s))
    return rows, df, n


def is_duplicate(q: dict, k: dict, ev: list[dict]) -> bool:
    if any(e["type"] == "entry_url" for e in ev):
        return True
    va, vb = q.get("_v") or {}, k.get("_v") or {}
    if va.get("text_mh") is not None and vb.get("text_mh") is not None and va.get("creative_phash") and vb.get("creative_phash"):
        return va["text_mh"].jaccard(vb["text_mh"]) >= 0.9 and evidence._hamming(va["creative_phash"], vb["creative_phash"]) <= 6
    return False


def has_content(inc: dict) -> bool:
    la = inc.get("landing") or {}
    return bool(la.get("page_role") != "error" and len((la.get("text") or "").strip()) >= 80)


def has_ad(inc: dict) -> bool:
    ad = inc.get("ad") or {}
    return bool(ad.get("advertiser") or ad.get("text") or ad.get("library_id") or ad.get("creative_phash")
                or (inc.get("media") or {}).get("faces"))


def layer_coverage(inc: dict) -> tuple[list[LayerCoverage], float]:
    t, la, ad = inc.get("tracking") or {}, inc.get("landing") or {}, inc.get("ad") or {}
    media = inc.get("media") or {}
    st = {
        "tracking": any(t.get(k) for k in ("fb_pixels", "capi_gateways", "google_ads", "ga4", "gtm", "tiktok_pixels")),
        "kit": any(t.get(k) for k in ("kit_tenants", "lander_ids", "asset_hashes", "path_shapes", "kit_endpoints")),
        "infra": bool((inc.get("infra") or {}).get("domains")),
        "content": has_content(inc),
        "ad": bool(ad.get("advertiser") or ad.get("text") or ad.get("library_id")),
        "visual": bool(ad.get("creative_phash") or ad.get("screenshot_path")),
        "persons": bool(media.get("faces") or (inc.get("content") or {}).get("persons")),
        "media": bool(ad.get("video_path") or media.get("video")),
    }
    reasons = {"content": "strona błędu / brak treści" if la.get("page_role") == "error" else "brak HTML/HAR",
               "ad": "brak zrzutu reklamy lub pól VLM", "tracking": "brak identyfikatorów śledzących",
               "kit": "brak śladów kitu", "infra": "brak domeny", "visual": "brak zrzutu reklamy",
               "persons": "brak rozpoznanych osób", "media": "brak wideo"}
    out = [LayerCoverage(layer=k, state="available" if v else "missing", reason=None if v else reasons[k]) for k, v in st.items()]
    if inc.get("landing", {}).get("enrich_partial"):
        pass
    core = ["tracking", "kit", "infra", "content", "ad"]
    return out, round(sum(st[k] for k in core) / len(core), 3)


# ------------------------------------------------------------------------------------------------ contrast
def contrast(q: dict, k: dict, df: dict | None = None, n: int = 0) -> tuple[list[EvidenceItem], list[EvidenceItem]]:
    """(missing, conflicts): identifiers present on one side only / present on both sides with different values."""
    va, vb = q["_v"], k["_v"]
    missing, conflicts = [], []
    for ftype in CONTRAST_TYPES:
        a, b = va.get(ftype) or set(), vb.get(ftype) or set()
        if a and b and not (a & b):
            sa, sb = sorted(a)[0], sorted(b)[0]
            conflicts.append(to_item({"type": ftype, "value": f"{str(sa)[:40]} ≠ {str(sb)[:40]}", "raw": [sa], "weight": 0.0},
                                     df, n, state="conflict", sides={"a": str(sa)[:120], "b": str(sb)[:120]}))
        elif bool(a) != bool(b):
            side = sorted(a or b)[0]
            missing.append(to_item({"type": ftype, "value": f"{str(side)[:60]} (tylko po stronie {'A' if a else 'B'})",
                                    "raw": [side], "weight": 0.0}, df, n, state="missing",
                                   sides={"a": str(sorted(a)[0])[:120] if a else "", "b": str(sorted(b)[0])[:120] if b else ""}))
    return missing, conflicts


def split_evidence(ev: list[dict], df: dict, n: int) -> tuple[list[EvidenceItem], list[EvidenceItem], list[EvidenceItem]]:
    """(counted, conflicts, zeroed). Operator-only items are 'zero' at campaign level unless the conjunction rule
    (content/ad agreement >= 2.5) let them in (capped at +4)."""
    content_agree = sum(e["weight"] for e in ev if e["weight"] > 0 and e["layer"] in CONTENT_LAYERS and e["type"] != "vertical")
    conj = evidence.CONJUNCTION and content_agree >= 2.5
    counted, conflicts, zeroed = [], [], []
    for e in sorted(ev, key=lambda e: -abs(e["weight"])):
        if e["weight"] < 0:
            conflicts.append(to_item(e, df, n))
        elif e["type"] in evidence.OPERATOR_ONLY and not conj:
            zeroed.append(to_item(e, df, n, state="zero"))
        else:
            counted.append(to_item(e, df, n))
    return counted, conflicts, zeroed


# ------------------------------------------------------------------------------------------------ decide
def decide(q: dict, corpus, *, tau: float = TAU, delta: float = DELTA) -> tuple[Decision, dict]:
    """-> (Decision, ctx) where ctx = {rows, df, n, per_campaign} for explanations / progress events."""
    known = [k for k in corpus.incidents if k["id"] != q["id"]]
    rows, df, n = score_against(q, known)
    per_c, per_o, per_n = defaultdict(list), defaultdict(list), defaultdict(list)
    for k, ev, s in rows:
        cid = corpus.campaign_of.get(k["id"], k["id"])
        per_c[cid].append(s["score_campaign"])
        per_o[corpus.operator_of.get(k["id"], f"?{cid}")].append(s["score_operator"])
        per_n[corpus.operation_of.get(k["id"], f"?{cid}")].append(s["score_operator"])
    c, top, margin = cluster.assign_open_set(per_c, tau, delta)
    ranked = sorted(((cluster.campaign_score(v), cid) for cid, v in per_c.items()), reverse=True)
    best_c = ranked[0][1] if ranked else None
    op_id, op_score, _ = cluster.assign_open_set(per_o, OP_TAU, 0.0)
    opn_id, _, _ = cluster.assign_open_set(per_n, OP_TAU, 0.0)
    op_id = op_id if op_id and not op_id.startswith("?") else None
    opn_id = opn_id if opn_id and not opn_id.startswith("?") else None

    # best pair overall (for evidence chips) and inside the best campaign
    rows_sorted = sorted(rows, key=lambda r: (-r[2]["score_campaign"], -r[2]["score_operator"]))
    best_row = next((r for r in rows_sorted if corpus.campaign_of.get(r[0]["id"]) == (c or best_c)), rows_sorted[0] if rows_sorted else None)
    dup = next((k["id"] for k, ev, s in rows_sorted if is_duplicate(q, k, ev)), None)

    if c is not None:
        state = "assign"
    elif top >= tau:
        state = "ambiguous"
    elif not has_content(q) and not has_ad(q):
        state = "insufficient"
    elif top >= CONFIRM_FLOOR:
        state = "confirm"
    else:
        state = "new"
    if dup and state != "assign":
        dc = corpus.campaign_of.get(dup)
        state, c = "assign", dc            # L0: the same visit captured twice is always the same campaign

    # same operator as … (new/confirm/insufficient with score_operator >= 3)
    best_op = max(rows, key=lambda r: r[2]["score_operator"]) if rows else None
    same_op_as = None
    if state in ("new", "confirm", "insufficient") and best_op and best_op[2]["score_operator"] >= OP_TAU:
        same_op_as = corpus.campaign_of.get(best_op[0]["id"])

    scores = []
    for sc, cid in ranked[:10]:
        mem_op = max((r[2]["score_operator"] for r in rows if corpus.campaign_of.get(r[0]["id"]) == cid), default=0.0)
        scores.append(CampaignScore(campaign_id=cid, score=round(sc, 3), score_operator=round(mem_op, 3),
                                    p=calibration.prob(sc), in_set=(c == cid)))
    runner = None
    if len(ranked) > 1:
        r_sc, r_c = ranked[1] if ranked[0][1] == (c or best_c) else ranked[0]
        runner = RunnerUp(campaign_id=r_c, score=round(r_sc, 3), p=calibration.prob(r_sc),
                          same_operator=bool(corpus.campaigns.get(r_c, {}).get("operator_id")
                                             and corpus.campaigns.get(r_c, {}).get("operator_id") == (op_id or corpus.campaigns.get(c or best_c, {}).get("operator_id"))))

    layers, coverage = layer_coverage(q)
    ev_items: list[EvidenceItem] = []
    if best_row is not None:
        counted, conflicts, zeroed = split_evidence(best_row[1], df, n)
        ev_items = counted + conflicts + zeroed
    why_not = []
    for sc, cid in ranked[:3]:
        if cid == c:
            continue
        why_not.append(WhyNot(campaign_id=cid, bullets=why_not_bullets(q, cid, sc, rows, corpus, df, n, tau, delta, top)))

    d = Decision(
        incident_id=q["id"], decision=state,
        campaign_id=c if state == "assign" else None,
        candidate_campaign_id=best_c if state in ("confirm", "ambiguous") else None,
        score=round(top, 3), margin=round(margin, 3), p=calibration.prob(top) if ranked else 0.0,
        tau=tau, delta=delta, confirm_floor=CONFIRM_FLOOR,
        # operator: the assigned campaign's operator; for unassigned items only the flag same_operator_as (score_operator
        # >= 3 says "same operator OR same operation", RESULTS §2b — never an operator id on its own)
        operator_id=(corpus.campaigns.get(c, {}).get("operator_id") if state == "assign" and c else None),
        operation_id=opn_id or (corpus.campaigns.get(c, {}).get("operation_id") if c else None),
        same_operator_as=same_op_as, duplicate_of=dup, scores=scores, runner_up=runner, coverage=coverage,
        layers=layers, evidence=ev_items[:40], why_not=why_not, model_version=calibration.MODEL_VERSION,
    )
    return d, {"rows": rows, "df": df, "n": n, "per_campaign": per_c, "best_row": best_row}


def why_not_bullets(q, cid, sc, rows, corpus, df, n, tau, delta, top) -> list[str]:
    mem = [r for r in rows if corpus.campaign_of.get(r[0]["id"]) == cid]
    if not mem:
        return []
    k, ev, s = max(mem, key=lambda r: r[2]["score_campaign"])
    out = []
    if sc < tau:
        out.append(f"najlepsze powiązanie {sc:.1f} < próg {tau:.0f} (najbliższy: {k['id']})")
    elif top - sc < delta:
        out.append(f"wynik {sc:.1f} zbyt bliski innej kampanii (margines < {delta:.0f})")
    missing, conflicts = contrast(q, k, df, n)
    for c in conflicts[:3]:
        out.append(f"{LABEL.get(c.field, c.field)} różni się: {c.sides['a'][:24]} ≠ {c.sides['b'][:24]}")
    for e in ev:
        if e["weight"] < 0:
            out.append(f"{LABEL.get(e['type'], e['type'])}: {e['value']} ({e['weight']:+.1f})")
    _, _, zeroed = split_evidence(ev, df, n)
    if zeroed:
        w = sum(z.weight for z in zeroed)
        out.append(f"wspólna infrastruktura operatora (+{w:.1f}: {', '.join(LABEL.get(z.field, z.field) for z in zeroed[:3])}) "
                   f"nie liczy się bez zgodnej treści/reklamy")
    if s["score_operator"] >= OP_TAU and sc < tau:
        out.append(f"ten sam operator możliwy (score_operator {s['score_operator']:.1f} ≥ 3), inna kampania/narracja")
    for m in missing[:2]:
        out.append(f"brak po drugiej stronie: {LABEL.get(m.field, m.field)}")
    return out[:8]


# ------------------------------------------------------------------------------------------------ explain
def explain_pair(a: dict, b: dict, corpus=None, *, tau: float = TAU, delta: float = DELTA) -> LinkExplanation:
    known = [x for x in (corpus.incidents if corpus else []) if x["id"] not in (a["id"], b["id"])]
    sub = known + [a, b]
    evidence.prepare(sub)
    df = evidence.doc_freq(sub)
    n = len(sub)
    ev, s = evidence.pair_evidence(a, b, df, n)
    counted, conflicts, zeroed = split_evidence(ev, df, n)
    missing, id_conflicts = contrast(a, b, df, n)
    sc, so = s["score_campaign"], s["score_operator"]
    dup = is_duplicate(a, b, ev)
    decision = "linked" if sc >= tau or dup else ("triage" if sc >= CONFIRM_FLOOR else "not_linked")
    level = "L0" if dup else ("L2" if sc >= tau else ("L3" if so >= OP_TAU else None))
    contrib = defaultdict(float)
    for e in counted:
        contrib[e.type] += e.weight
    top = sorted(counted, key=lambda e: -e.weight)[:3]
    summary = (f"Wynik kampanii {sc:.1f} (próg {tau:.0f}), operatora {so:.1f}. "
               + ("Najsilniejsze: " + ", ".join(f"{LABEL.get(e.field, e.field)} (+{e.weight:.1f})" for e in top) + "." if top else "Brak wspólnych śladów."))
    cfs = []
    for layer, w in sorted(contrib.items(), key=lambda kv: -kv[1])[:2]:
        new = sc - w
        cfs.append(Counterfactual(change=f"bez warstwy {layer}", p_new=calibration.prob(new),
                                  decision_new="linked" if new >= tau else ("triage" if new >= CONFIRM_FLOOR else "not_linked")))
    op_id = None
    if corpus is not None:
        oa, ob = corpus.operator_of.get(a["id"]), corpus.operator_of.get(b["id"])
        op_id = oa if oa and oa == ob else None
    return LinkExplanation(
        a=a["id"], b=b["id"], score_campaign=round(sc, 3), score_operator=round(so, 3), p=calibration.prob(sc),
        tau=tau, delta=delta, decision=decision, shared_level=level, operator_id=op_id,
        layers_independent=s["n_layers"], layers_required=2, coverage=s["coverage"], summary=summary,
        contributions=[{"layer": k, "value": round(v, 3)} for k, v in sorted(contrib.items(), key=lambda kv: -kv[1])],
        evidence=counted, missing=missing, conflicts=conflicts + id_conflicts, zeroed=zeroed, counterfactuals=cfs)


def best_member(q: dict, campaign_id: str, corpus) -> dict | None:
    mem = corpus.members(campaign_id)
    if not mem:
        return None
    rows, _, _ = score_against(q, mem)
    return max(rows, key=lambda r: r[2]["score_campaign"])[0] if rows else None


def strip(inc: dict) -> dict:
    return {k: v for k, v in inc.items() if not k.startswith("_")}


_ID_RE = re.compile(r"^KMP-\d+$")
