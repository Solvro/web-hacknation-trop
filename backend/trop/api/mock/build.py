"""Generate the JSON fixtures: `cd backend && uv run python -m trop.api.mock.build`. Output: trop/api/mock/*.json.

Each fixture is `{"model": "<schema name>", "data": ...}` so tests can validate against the pydantic models.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from trop.api.mock import universe as U
from trop.api.mock import universe2 as V
from trop.schema import (
    ActPackage, Campaign, CampaignDNA, Decision, EvidenceValue, GraphPayload, HunterRun, HunterSource, IncidentSummary,
    Investigation, LinkExplanation, MergePreview, Member, Operation, Operator, OracleMetrics, OraclePrediction, DomainDNA,
    Rule, RuleTest, StatsOverview, TemplateDiff, Timeline, TriageItem, Indicators, Variant,
)

OUT = Path(__file__).parent


def dump(x):
    if isinstance(x, BaseModel):
        return x.model_dump(mode="json", by_alias=True)
    if isinstance(x, list):
        return [dump(i) for i in x]
    if isinstance(x, dict):
        return {k: dump(v) for k, v in x.items()}
    return x


def build() -> dict[str, dict]:
    camps = U.campaigns()
    ids = [c.id for c in camps]
    files: dict[str, dict] = {
        "campaigns": {"model": "list[Campaign]", "data": camps},
        "dna": {"model": "dict[str,CampaignDNA]", "data": {c: U.dna(c) for c in ids}},
        "timeline": {"model": "dict[str,Timeline]", "data": {c: V.timeline(c) for c in ids}},
        "members": {"model": "dict[str,list[Member]]", "data": {c: U.members(c) for c in ids}},
        "indicators": {"model": "dict[str,Indicators]", "data": {c: V.indicators(c) for c in ids}},
        "variants": {"model": "dict[str,list[Variant]]", "data": {c: V.variants(c) for c in ids}},
        "campaign_extra": {"model": "dict", "data": {"phylogeny": {c: V.phylogeny(c) for c in ids}, "summary": {c: V.summary_text(c) for c in ids}}},
        "incident_summaries": {"model": "list[IncidentSummary]", "data": U.incident_summaries()},
        "incident_details": {"model": "dict[str,dict]", "data": U.incident_details()},
        "decisions": {"model": "dict[str,Decision]", "data": U.decisions()},
        "links": {"model": "dict", "data": {"explain_kmp017": U.link("INC-24817", "KMP-017"), "explain_kmp034": U.link("INC-24817", "KMP-034"), "diff": U.template_diff()}},
        "operators": {"model": "list[Operator]", "data": V.operators()},
        "operations": {"model": "list[Operation]", "data": V.operations()},
        "merge_preview": {"model": "MergePreview", "data": V.merge_preview()},
        "graph": {"model": "GraphPayload", "data": V.graph()},
        "investigations": {"model": "list[Investigation]", "data": [V.investigation(), V.investigation_old()]},
        "oracle": {"model": "dict", "data": {"predictions": V.oracle_predictions(), "dna": V.oracle_dna(), "metrics": V.oracle_metrics()}},
        "act": {"model": "dict", "data": {"packages": V.act_packages(), "rules": V.act_rules(), "rule_test": V.RULE_TEST}},
        "triage": {"model": "list[TriageItem]", "data": V.triage()},
        "hunter": {"model": "dict", "data": {"sources": V.hunter_sources(), "runs": V.hunter_runs()}},
        "lab": {"model": "dict", "data": {"views": V.lab(), "ablation": V.ablation()}},
        "misc": {"model": "dict", "data": {"persons": V.persons(), "brands": V.brands(), "alerts": V.alerts(), "stats": V.stats()}},
    }
    return files


def main() -> None:
    for name, payload in build().items():
        (OUT / f"{name}.json").write_text(json.dumps(dump(payload), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
