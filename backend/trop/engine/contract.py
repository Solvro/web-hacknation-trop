"""Engine CONTRACT (implemented by WS1; used by WS2 worker/api, WS6, WS7).

    from trop.engine import service
    service.analyze_incident(inc: Incident, corpus) -> tuple[Decision, list[Finding]]
    service.explain(a_id, b_id, corpus) -> LinkExplanation            # b may be an incident or KMP id
    service.cluster(incidents) -> {incident_id: {campaign, variant, operator, operation}}
    corpus = service.Corpus.load()      # labelled/known incidents + df stats + campaign assignments (from DB or JSON)

Thresholds (RESULTS §4, do not change): tau=5, delta=1, confirm band [1,5), operator flag score_operator>=3,
operator-only evidence capped at +4 and counted only when content/ad agreement >= 2.5.
"""
