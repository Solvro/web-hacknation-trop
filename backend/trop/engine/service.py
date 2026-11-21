"""Engine service API (contract: trop/engine/contract.py). Used by WS2 (worker/api), WS6, WS7.

    from trop.engine import service
    corpus = service.Corpus.load()                                      # JSON corpus now, DB later (source="db")
    decision, findings = service.analyze_incident(inc, corpus, emit=None)
    expl = service.explain(a_id_or_inc, b_id_or_KMP, corpus)            # LinkExplanation
    labels = service.cluster(incidents)                                 # {id: {campaign, variant, operator, operation}}
    decision, inc = service.analyze_path(path_or_url, corpus, emit=cb)  # ingest + extract + decide, six bot steps

`emit(event_type, data)` — see trop/engine/progress.py for the event catalogue (= SSE job.* events without job_id).
"""
from __future__ import annotations

import copy
from pathlib import Path

from trop.schema import Decision, Finding, Incident, LinkExplanation

from . import batch as _batch
from . import decide as _decide
from .corpus import Corpus
from .progress import Steps

__all__ = ["Corpus", "analyze_incident", "analyze_path", "explain", "cluster", "cluster_joint", "findings_for"]


def _as_dict(inc) -> dict:
    if isinstance(inc, Incident):
        return inc.model_dump(mode="json")
    return inc


def findings_for(decision: Decision) -> list[Finding]:
    """Where each chip was found (Sprawdź-2 left column). Coarse: tracking/kit -> har|html, content -> html, ad -> ad."""
    where = {"tracking": "har", "kit": "har", "infra": "har", "content": "html", "ad": "ad", "visual": "screenshot",
             "persons": "ad", "media": "ad"}
    return [Finding(evidence=e, where=where.get(e.type)) for e in decision.evidence if e.state == "match"][:20]


def analyze_incident(inc, corpus: Corpus | None = None, *, emit=None, steps: Steps | None = None,
                     adjudicate: bool = True) -> tuple[Decision, list[Finding]]:
    """Steps compare (archiwista) + verdict (sedzia) for an already extracted incident."""
    corpus = corpus or Corpus.load()
    q = copy.deepcopy(_as_dict(inc))
    st = steps or Steps(emit)
    st.start("compare")
    d, ctx = _decide.decide(q, corpus)
    st.ranking(d.scores)
    best = ctx.get("best_row")
    if best is not None:
        counted, conflicts, _ = _decide.split_evidence(best[1], ctx["df"], ctx["n"])
        for it in (counted + conflicts)[:12]:
            it.bot = "archiwista"
            st.evidence("compare", it)
    st.done("compare", detail=f"{len(corpus.incidents)} znanych incydentów · najlepszy wynik {d.score:.1f}")
    st.start("verdict")
    note = ""
    if adjudicate and d.decision == "confirm":
        from . import adjudicate as _adj
        before = d.decision
        note = _adj.apply(d, ctx, corpus)
        assert d.decision == before and d.campaign_id is None        # veto/annotate only, never a link
    findings = findings_for(d)
    detail = _verdict_line(d, corpus) + (f" · {note}" if note else "")
    st.done("verdict", detail=detail, status="done" if d.decision in ("assign", "new") else "warn",
            warnings=[note] if note and d.adjudicator is None else [])
    st.emit("job.done", {"incident_id": d.incident_id, "decision": d.model_dump(mode="json")})
    return d, findings


def _verdict_line(d: Decision, corpus: Corpus) -> str:
    name = lambda c: f"{c} «{corpus.campaigns.get(c, {}).get('name', '')[:40]}»" if c else "?"  # noqa: E731
    if d.decision == "assign":
        return f"Dołącza do {name(d.campaign_id)} · pewność {d.p:.2f}" + (f" · duplikat {d.duplicate_of}" if d.duplicate_of else "")
    if d.decision == "ambiguous":
        return f"Niejednoznaczne: {d.candidate_campaign_id} vs {d.runner_up.campaign_id if d.runner_up else '?'} — do analityka"
    if d.decision == "confirm":
        return f"Do potwierdzenia: kandydat {name(d.candidate_campaign_id)} (wynik {d.score:.1f} < 5)"
    if d.decision == "insufficient":
        return "Za mało materiału (brak treści strony i warstwy reklamy)"
    return "Nowa kampania (kandydat)" + (f" · ten sam operator co {d.same_operator_as}" if d.same_operator_as else "")


def analyze_path(src: str | Path, corpus: Corpus | None = None, *, emit=None, inc_id: str | None = None,
                 opts=None, workdir: Path | None = None) -> tuple[Decision, dict, list[Finding]]:
    """Full Sprawdź flow for a folder / file / zip / URL: the six bot steps, streamed through `emit`."""
    from trop.ingest.pipeline import build_incident
    from .evidence import doc_freq, prepare
    corpus = corpus or Corpus.load()
    df, n = None, len(corpus.incidents)
    if emit is not None and corpus.incidents:
        prepare(corpus.incidents)
        df = doc_freq(corpus.incidents)
    steps = Steps(emit, df, n)
    inc = build_incident(src, inc_id=inc_id, emit=None, opts=opts, workdir=workdir) if emit is None else \
        _build_with_steps(src, inc_id, steps, opts, workdir)
    d, findings = analyze_incident(inc, corpus, steps=steps)
    return d, inc, findings


def _build_with_steps(src, inc_id, steps: Steps, opts, workdir):
    from trop.ingest.pipeline import build_incident
    return build_incident(src, inc_id=inc_id, emit=steps.emit_fn, opts=opts, workdir=workdir, df=steps.df, n=steps.n)


def explain(a, b, corpus: Corpus | None = None) -> LinkExplanation:
    """a, b: incident ids (in the corpus), incident dicts, or b = a campaign id (KMP-…: its best-matching member)."""
    corpus = corpus or Corpus.load()

    def resolve(x):
        if isinstance(x, (dict, Incident)):
            return copy.deepcopy(_as_dict(x))
        inc = corpus.get(str(x))
        if inc is None:
            raise KeyError(f"unknown incident {x}")
        return copy.deepcopy(inc)

    A = resolve(a)
    if isinstance(b, str) and b in corpus.campaigns:
        B = _decide.best_member(A, b, corpus)
        if B is None:
            raise KeyError(f"campaign {b} has no members")
        B = copy.deepcopy(B)
    else:
        B = resolve(b)
    return _decide.explain_pair(A, B, corpus)


def cluster(incidents: list) -> dict[str, dict]:
    return _batch.cluster([copy.deepcopy(_as_dict(i)) for i in incidents])


def cluster_joint(incidents: list, corpus: Corpus | None = None):
    return _batch.cluster_joint([copy.deepcopy(_as_dict(i)) for i in incidents], corpus)
