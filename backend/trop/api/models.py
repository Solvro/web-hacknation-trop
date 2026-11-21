"""API-only response models (resources the contract schema does not define). Contract models live in trop.schema."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from trop.schema import Incident


class _C(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Health(_C):
    ok: bool
    mode: str
    capture: str = "off"       # off | sandbox | local (URL input)
    llm: str = "off"           # live when a key is set and the gateway is not offline
    db: str
    redis: str
    version: str
    counts: dict[str, int] = {}


class Alert(_C):
    id: str
    kind: Literal["oracle", "hunter", "campaign", "triage", "extension", "act"]
    severity: Literal["info", "warn", "hot"] = "info"
    title: str
    subject_id: str | None = None
    created_at: str
    status: Literal["open", "closed"] = "open"


class IncidentDetail(Incident):
    """GET /incidents/{id}: the PLAN §4 incident + decision summary + coverage."""
    decision: dict[str, Any] | None = None
    coverage: float = 0.0


class Artifact(_C):
    kind: Literal["screenshot", "har", "html", "video", "creative", "dom", "tls"]
    name: str
    url: str
    size: int = 0
    mime: str | None = None


class FeatureRow(_C):
    field: str
    value: str
    df: int
    N: int
    idf: float


class FeatureGroup(_C):
    layer: str
    features: list[FeatureRow]


class Match(_C):
    kind: Literal["campaign", "incident"]
    id: str
    label: str
    score: float
    p: float = 0.0
    same_operator: bool = False
    top_evidence: list[str] = []


class HistoryEvent(_C):
    at: str
    kind: str
    text: str
    actor: str = "system"


class Phylogeny(_C):
    campaign_id: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class CampaignSummaryText(_C):
    campaign_id: str
    text: str
    bullets: list[str] = []
    generated_by: str = "mock"


class SplitRequest(_C):
    incident_ids: list[str]
    name: str | None = None


class CampaignCreate(_C):
    seed_incident: str
    name: str
    status: Literal["candidate"] = "candidate"


class SteerRequest(_C):
    message: str | None = None
    node_id: str | None = None
    choice: str | None = None


class Ack(_C):
    ok: bool = True
    detail: str | None = None


class PromoteResult(_C):
    campaign_id: str
    added: int


class OracleDnaPatch(_C):
    threshold: float


class PersonSummary(_C):
    id: str
    name: str
    role: str
    count: int
    trend_pct: float = 0.0
    campaigns: list[dict[str, Any]] = []
    face_match: float | None = None
    deepfake_score: float | None = None
    voice_score: float | None = None


class Person(PersonSummary):
    weekly: list[dict[str, Any]] = []
    narratives: list[str] = []
    sample_incidents: list[str] = []


class Brand(_C):
    name: str
    kind: str
    count: int
    campaigns: list[str] = []


class ActSubmit(_C):
    confirm: bool


class RuleTestRequest(_C):
    kind: Literal["urlscan", "url_regex", "html_signature", "yara"]
    body: str


class TriageCreate(_C):
    source: Literal["incident", "prediction", "campaign"] = "incident"
    subject_id: str | None = None
    prediction_id: str | None = None


class TriageList(_C):
    items: list[Any]
    facets: dict[str, dict[str, int]]


class TriageDecided(_C):
    item: Any
    feedback_id: str


class FeedbackIn(_C):
    subject_id: str
    kind: str = "label"
    value: str | None = None
    note: str | None = None


class FeedbackStats(_C):
    window: str
    n: int
    accepted: int
    reassigned: int
    rejected: int
    model_version: str


class StressRun(_C):
    run_id: str
    status: Literal["queued", "running", "done"] = "done"
    kind: str = "perturbation"
    results: dict[str, Any] = {}


class StressCreate(_C):
    kind: Literal["perturbation", "loco", "drop_layer"] = "perturbation"
    params: dict[str, Any] = {}


class HunterSourcePatch(_C):
    enabled: bool | None = None
    schedule: str | None = None
    config: dict[str, Any] | None = None


class RunStarted(_C):
    run_id: str


class CapturePolicy(_C):
    sandbox: bool = True
    follow_redirects: int = 6
    forbid_forms: bool = True
    forbid_login: bool = True
    egress: str = "proxy"
    notes: list[str] = []


class CredStatus(_C):
    source_id: str
    status: Literal["set", "missing", "not_needed"]


class PublicScheme(_C):
    name: str
    seen_count: int
    since: str
    reasons: list[str]


class PublicReportAck(_C):
    ok: bool = True
    report_id: str


class ReportsMine(_C):
    submitted: int
    matched: int


class TraceView(_C):
    value: str
    type: str
    campaigns: list[dict[str, Any]]
    weekly: list[int]
    latest: list[Any]
    usage: list[dict[str, Any]]
    co_traces: list[dict[str, Any]]


class BatchAccepted(_C):
    job_id: str


class AnalyzeOptions(_C):
    kind: str = "url"




class NoticeUpdate(_C):
    text: str
