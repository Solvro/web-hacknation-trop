"""TROP contracts — THE shared data model (owned by the integrator; change only via the lead).

Mirrors docs/design/README.md §7.3 (API resource shapes) and PLAN §4 + RESULTS §4 (the Incident).

Conventions
- `Incident` is the nested dict the evidence engine (experiments/rp/evidence.py) consumes:
  sections source / ad / landing / tracking / infra / content / media / quality. Sections allow extra keys so the
  engine port keeps working when extractors add fields; the named fields below are the stable contract.
- Every API response model lives here. Routers return these; the web types are generated from
  docs/contracts/schema.json (`uv run python -m trop.schema > ../docs/contracts/schema.json`).
- Ids: incidents `INC-<n>` (or source ids like `p1`, `d3` for organizer data), campaigns `KMP-<nnn>`,
  operators `OP-<nn>`, operations `OPN-<nn>`, jobs `JOB-<ulid>`, investigations `INV-<n>`, packages `ACT-<n>`,
  triage `TRI-<n>`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------------------------- enums
Layer = Literal["tracking", "kit", "infra", "content", "persons", "visual", "ad", "media"]
Level = Literal["L0", "L1", "L2", "L3"]          # duplicate / variant / campaign / operator
GroupLevel = Literal["campaign", "variant", "operator", "operation"]
EvidenceLevel = Literal["campaign", "operator_only", "platform"]
Strength = Literal["H", "M", "L"]
DecisionState = Literal["assign", "confirm", "ambiguous", "new", "insufficient"]
SourceType = Literal[
    "sample_dir", "bundle", "capture_tool", "url", "upload", "har", "screenshot", "video",
    "adlibrary", "urlscan", "extension", "hunter", "manual",
]
BotName = Literal["zwiadowca", "tropiciel", "czytelnik", "notariusz", "archiwista", "sedzia"]
StepStatus = Literal["pending", "run", "done", "warn", "skip", "error"]


class _Open(BaseModel):
    """Section that tolerates extra keys (extractor-added features)."""
    model_config = ConfigDict(extra="allow")


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ======================================================================================== INCIDENT
class IncidentSource(_Open):
    type: SourceType = "manual"
    path: str | None = None                 # local path of the material (never exposed publicly)
    ref: str | None = None                  # source-specific ref: folder name, library id, urlscan uuid, report id
    captured_at: datetime | str | None = None


class AdLayer(_Open):
    platform: str | None = None             # meta | google | tiktok | unknown
    kind: str | None = None                 # feed | adlibrary_modal | display | phone | video
    library_id: str | None = None
    advertiser: str | None = None
    page_id: str | None = None
    text: str | None = None                 # caption / primary text
    overlay: str | None = None              # text on the creative
    display_link: str | None = None
    cta: str | None = None
    narrative: str | None = None            # short VLM summary (hint, never identity)
    persons: list[str] = []                 # NAMES FROM FACE GALLERY ONLY (never from a VLM)
    is_decoy: bool | None = None
    vertical: str | None = None
    creative_phash: str | None = None
    screenshot_path: str | None = None
    screenshots: list[str] = []
    video_path: str | None = None
    video_title: str | None = None
    n_creatives: int | None = None
    delivery: dict[str, Any] = {}


class Landing(_Open):
    entry_url: str | None = None
    final_url: str | None = None
    host: str | None = None
    etld1: str | None = None
    status: int | None = None
    title: str | None = None
    text: str | None = None
    lang: str | None = None
    h1: list[str] = []
    dom_paths: list[str] = []
    css_classes: list[str] = []
    page_role: str | None = None            # content | prelander | lander | error | unknown
    redirect_chain: list[str] = []
    chain_urls: list[str] = []              # NEW: first document of every HAR in a click chain
    chain_titles: list[str] = []
    n_hars: int = 0
    n_pages: int = 0
    screenshot_path: str | None = None
    screenshot_phash: str | None = None
    favicon_mmh3: int | None = None
    forms: list[dict[str, Any]] = []
    outlinks: list[str] = []


class Tracking(_Open):
    fb_pixels: list[str] = []
    capi_gateways: list[str] = []
    google_ads: list[str] = []
    ga4: list[str] = []
    gtm: list[str] = []
    tiktok_pixels: list[str] = []
    snap_pixels: list[str] = []
    kit_tenants: list[str] = []             # NEW (operator-level)
    lander_ids: list[str] = []              # NEW
    landing_type_ids: list[str] = []        # NEW (operator-level)
    video_hosts: list[str] = []
    kit_endpoints: list[str] = []           # platform-level
    url_param_schema: str | None = None
    chain_param_schemas: list[str] = []
    entry_path_template: str | None = None
    path_shapes: list[str] = []             # NEW (operator-level)
    third_party: list[str] = []
    asset_hashes: list[str] = []
    brand_asset_hashes: list[str] = []      # NEW (subtracted from asset_hashes)


class DomainInfo(_Open):
    fqdn: str
    etld1: str | None = None
    tld: str | None = None
    sld_label: str | None = None
    ips: list[str] = []
    cdn: list[str] = []
    asn: str | None = None
    cert: dict[str, Any] | None = None
    enrich: dict[str, Any] = {}             # ns, registrar, created, certs[], certpl, ... (cached enrichment)


class Infra(_Open):
    domains: list[DomainInfo] = []
    ips: list[str] = []
    cdn: list[str] = []
    origin_ips: list[str] = []
    on_certpl_list: bool | None = None


class Content(_Open):
    headline_template: str | None = None
    h1_template: str | None = None
    persons: list[str] = []                 # gazetteer NER on landing text
    comment_names: list[str] = []           # NEW: fake-commenter roster
    brands: list[str] = []
    products: list[str] = []
    vertical: str | None = None
    vertical_scores: dict[str, float] = {}
    lang: str | None = None
    ad_name: str | None = None
    narrative: str | None = None
    keywords: list[str] = []
    contacts: dict[str, list[str]] = {}     # phones, ibans, telegram


class FaceHit(_Open):
    identity: str | None = None             # gallery person name, only when cos >= 0.45 and lead >= 0.10
    person_id: str | None = None            # wikidata QID
    score: float = 0.0
    lead: float | None = None
    source: str | None = None               # ad_screenshot | landing | video_frame
    deepfake: float | None = None


class VideoInfo(_Open):
    path: str | None = None
    duration_s: float | None = None
    keyframes: list[str] = []
    gemini: dict[str, Any] = {}             # structured Gemini video pass (transcript, on_screen_text, scenes, ...)


class Media(_Open):
    faces: list[FaceHit] = []
    video: VideoInfo | None = None
    asr_text: str | None = None
    asr_model: str | None = None
    voice_id: str | None = None             # speaker-embedding cluster id (evidence `voice_id`)
    voice_embedding_ref: str | None = None


class Quality(_Open):
    available: list[str] = []
    missing: list[str] = []
    errors: list[str] = []


class Incident(_Open):
    """The engine's unit. `IncidentDraft` is the same shape before it has a DB id."""
    id: str
    source: IncidentSource = IncidentSource()
    ad: AdLayer = AdLayer()
    landing: Landing = Landing()
    tracking: Tracking = Tracking()
    infra: Infra = Infra()
    content: Content = Content()
    media: Media = Media()
    quality: Quality = Quality()
    emb: dict[str, Any] = {}                # optional embeddings (support only)


class IncidentDraft(Incident):
    id: str = ""                            # assigned by the store


class IncidentSummary(_Closed):
    id: str
    captured_at: datetime | str | None = None
    source: str
    domain: str | None = None
    title: str | None = None
    person: str | None = None
    campaign_id: str | None = None
    decision: DecisionState | None = None
    p: float | None = None
    coverage: float | None = None


# ======================================================================================== EVIDENCE
class EvidenceItem(_Closed):
    """One chip. `type` is the UI layer; `field` the engine feature type (e.g. 'fb_pixel', 'kit_tenant')."""
    type: Layer
    field: str
    value: str
    display: str
    strength: Strength
    weight: float                           # strength x rarity (negative for conflicts)
    level: EvidenceLevel = "campaign"
    df: int = 0
    N: int = 0
    idf: float = 0.0
    state: Literal["match", "conflict", "missing", "zero"] = "match"
    sides: dict[str, str] | None = None     # {a, b} values on each side (conflicts)
    bot: BotName | None = None              # which bot "found" it (UI)
    shap: float | None = None


class LayerCoverage(_Closed):
    layer: Layer
    state: Literal["available", "partial", "missing", "error"]
    reason: str | None = None


class CampaignScore(_Closed):
    campaign_id: str
    score: float                            # max-linkage score_campaign
    score_operator: float = 0.0
    p: float = 0.0                          # calibrated P(same campaign)
    p_value: float | None = None            # conformal (lab only)
    in_set: bool = False


class RunnerUp(_Closed):
    campaign_id: str
    score: float
    p: float = 0.0
    same_operator: bool = False


class WhyNot(_Closed):
    campaign_id: str
    bullets: list[str]


class Adjudication(_Closed):
    model: str
    verdict: Literal["same", "different", "unsure", "veto"]
    confidence: float
    rationale: list[str] = []


class Decision(_Closed):
    """GET /incidents/{id}/decision. RESULTS §4 states; p = isotonic/Platt calibration of score_campaign."""
    incident_id: str
    decision: DecisionState
    campaign_id: str | None = None          # assign
    candidate_campaign_id: str | None = None  # confirm / ambiguous best
    score: float = 0.0                      # best score_campaign (max-linkage)
    margin: float = 0.0
    p: float = 0.0                          # "pewność" shown in the UI
    tau: float = 5.0                        # assignment threshold on score_campaign
    delta: float = 1.0                      # required margin
    confirm_floor: float = 1.0              # confirm band = [1, 5)
    operator_id: str | None = None
    operation_id: str | None = None
    same_operator_as: str | None = None     # 'new' + score_operator >= 3 -> "ten sam operator co …"
    duplicate_of: str | None = None         # L0
    scores: list[CampaignScore] = []
    runner_up: RunnerUp | None = None
    coverage: float = 0.0
    layers: list[LayerCoverage] = []
    evidence: list[EvidenceItem] = []
    why_not: list[WhyNot] = []
    adjudicator: Adjudication | None = None
    # lab-only conformal fields (never shown in the main UI)
    alpha: float | None = None
    conformal_tau: float | None = None
    set: list[str] = []
    calibration: dict[str, float] | None = None
    model_version: str = "engine@1"


class Counterfactual(_Closed):
    change: str
    p_new: float
    decision_new: str


class LinkExplanation(_Closed):
    a: str
    b: str
    score_campaign: float
    score_operator: float
    p: float
    tau: float = 5.0
    delta: float = 1.0
    decision: Literal["linked", "not_linked", "triage"]
    shared_level: Level | None = None
    operator_id: str | None = None
    layers_independent: int = 0
    layers_required: int = 2
    coverage: float = 0.0
    summary: str = ""
    contributions: list[dict[str, Any]] = []   # {layer, value}
    evidence: list[EvidenceItem] = []
    missing: list[EvidenceItem] = []
    conflicts: list[EvidenceItem] = []
    zeroed: list[EvidenceItem] = []
    counterfactuals: list[Counterfactual] = []
    adjudicator: Adjudication | None = None


class Tok(_Closed):
    t: str
    kind: Literal["same", "ins", "del", "slot"]
    slot: str | None = None


class TemplateDiff(_Closed):
    text: dict[str, list[Tok]]              # {a_tokens, b_tokens}
    dom: dict[str, Any] = {}
    assets: list[dict[str, Any]] = []       # {url, sha256, same, third_party}
    visual: dict[str, Any] = {}             # {phash_distance, regions}
    metrics: dict[str, Any] = {}


class EvidenceValue(_Closed):
    type: Layer
    field: str
    value: str
    df: int
    N: int
    idf: float
    first_seen: str | None = None
    last_seen: str | None = None
    weekly: list[int] = []
    campaigns: list[dict[str, Any]] = []    # {id, n}
    operator_hint: str | None = None
    incidents: list[IncidentSummary] = []


# ======================================================================================== CAMPAIGNS
class Heat(_Closed):
    series_48h: list[int] = []
    series_14d: list[int] = []
    trend_pct: float = 0.0


class CampaignSummary(_Closed):
    id: str
    name: str
    narrative: str = ""
    vertical: str | None = None
    status: Literal["active", "fading", "candidate", "closed"] = "active"
    operator_id: str | None = None
    operation_id: str | None = None
    heat: Heat = Heat()
    n_incidents: int = 0
    n_domains: int = 0
    new_domains_24h: int = 0
    predicted_domains: int = 0
    persons: list[str] = []
    report_status: Literal["none", "draft", "sent", "needs_update"] = "none"
    merge_hint: str | None = None           # "może to KMP-017?"


class CampaignCounts(_Closed):
    incidents: int = 0
    incidents_24h: int = 0
    domains: int = 0
    certs_tonight: int = 0
    advertisers: int = 0
    advertisers_removed: int = 0
    persons: int = 0
    certpl_listed: int = 0


class Campaign(CampaignSummary):
    description: str = ""
    level: Literal["L2"] = "L2"
    counts: CampaignCounts = CampaignCounts()
    first_seen: str | None = None
    last_seen: str | None = None
    brands: list[str] = []


class DnaRow(_Closed):
    layer: Layer
    field: str
    value: str
    display: str | None = None
    members_with: int
    members_total: int
    strength: Strength
    bot: BotName | None = None


class CampaignDNA(_Closed):
    campaign_id: str
    signature: list[DnaRow]


class TimelineEvent(_Closed):
    at: str
    kind: Literal["domain_registered", "cert_batch", "oracle_predicted", "act_sent", "incident", "hunter_capture"]
    ref: str


class Timeline(_Closed):
    days: list[dict[str, Any]]              # {date, incidents}
    events: list[TimelineEvent] = []


class Member(_Closed):
    incident_id: str
    captured_at: str | None = None
    source: str
    domain: str | None = None
    person: str | None = None
    level: Level = "L2"
    variant_id: str | None = None
    parent_id: str | None = None
    score: float = 0.0
    p: float = 0.0
    top_evidence: list[EvidenceItem] = []
    layers: list[LayerCoverage] = []


class DomainIndicator(_Closed):
    fqdn: str
    cert_issued_at: str | None = None
    registered_at: str | None = None
    oracle_predicted_at: str | None = None
    on_certpl: bool = False
    online: bool | Literal["502", "unknown"] = "unknown"
    ads_seen: int = 0


class Indicators(_Closed):
    domains: list[DomainIndicator] = []
    tracking: list[EvidenceItem] = []
    kit: list[EvidenceItem] = []
    persons: list[dict[str, Any]] = []      # {id, name, count}
    advertisers: list[dict[str, Any]] = []  # {name, page_id, removed}


class Variant(_Closed):
    id: str
    campaign_id: str
    label: str
    members: list[str]
    template: str | None = None


class Operator(_Closed):
    id: str
    codename: str
    campaigns: list[dict[str, Any]] = []    # {id, name, incidents}
    shared: list[EvidenceItem] = []         # "Rozpoznajemy go po"
    narratives: list[str] = []
    operation_id: str | None = None


class Operation(_Closed):
    """Shared funnel across operators/campaigns (DANE finding: A + C + K)."""
    id: str
    name: str
    campaigns: list[str]
    operators: list[str] = []
    funnel: list[str] = []                  # e.g. ['pre-lander A', 'lander C (healthlinkq.pro)']
    shared: list[EvidenceItem] = []


class MergeRequest(_Closed):
    other_id: str
    keep: Literal["self", "other"] = "self"


class MergePreview(_Closed):
    a: CampaignSummary
    b: CampaignSummary
    shared: list[EvidenceItem]
    before: dict[str, int]
    after: dict[str, int]
    undo_token: str | None = None


# ======================================================================================== GRAPH
class GraphNode(_Closed):
    id: str
    kind: Literal["incident", "domain", "campaign", "operator", "operation", "person", "trace", "cert", "advertiser"]
    label: str
    campaign_id: str | None = None
    size: float = 1.0
    first_seen: str | None = None
    meta: dict[str, Any] = {}


class GraphEdge(_Closed):
    a: str
    b: str
    type: Layer | Literal["member", "operator", "operation"]
    weight: float = 1.0
    level: Level | None = None
    label: str | None = None


class GraphPayload(_Closed):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    hulls: list[dict[str, Any]] = []        # {id, kind, members[], label}
    focus: str | None = None                # node the view is centred on (boards 4a–4d)
    panel: dict[str, Any] | None = None     # side panel: facts, bot sentence, primary action


# ======================================================================================== JOBS (Sprawdź)
BOT_STEPS: list[tuple[str, BotName, str]] = [
    ("capture", "zwiadowca", "Zwiadowca · przechwycenie strony"),
    ("tracking", "tropiciel", "Tropiciel · tracking i kit"),
    ("content", "czytelnik", "Czytelnik · treść i osoby"),
    ("infra", "notariusz", "Notariusz · domena i certyfikaty"),
    ("compare", "archiwista", "Archiwista · porównanie z bazą"),
    ("verdict", "sedzia", "Sędzia · werdykt"),
]


class JobStep(_Closed):
    key: Literal["capture", "tracking", "content", "infra", "compare", "verdict"]
    bot: BotName
    label: str
    status: StepStatus = "pending"
    started_at: str | None = None
    duration_ms: int | None = None
    detail: str | None = None
    warnings: list[str] = []


class JobInput(_Closed):
    kind: Literal["url", "file", "zip", "folder", "trace", "batch"]
    name: str


class Job(_Closed):
    id: str
    status: Literal["queued", "running", "done", "error"] = "queued"
    input: JobInput
    incident_id: str | None = None
    decision: DecisionState | None = None
    campaign_id: str | None = None
    total_ms: int | None = None
    steps: list[JobStep] = Field(default_factory=lambda: [JobStep(key=k, bot=b, label=lbl) for k, b, lbl in BOT_STEPS])
    error: str | None = None


class AnalyzeAccepted(_Closed):
    job_id: str | None = None             # None for a typed trace (UI opens /slad/...)
    trace: dict[str, str] | None = None   # {type, value} when the input was a trace
    incident_id: str | None = None


class Finding(_Closed):
    """A finding outlined on the captured page (Sprawdź-2 left column)."""
    evidence: EvidenceItem
    where: str | None = None                # 'html' | 'har' | 'screenshot' | 'ad'
    selector: str | None = None
    bbox: list[float] | None = None         # x, y, w, h (0..1 of the screenshot)


class BatchRow(_Closed):
    """One row of results.csv (hidden-test hedge)."""
    item: str
    incident_id: str
    decision: DecisionState
    campaign: str                           # campaign cluster id (known KMP-… or NEW-…)
    campaign_score: float
    campaign_p: float
    operator: str | None = None
    operation: str                          # operation-level cluster id
    variant: str | None = None
    same_operator_as: str | None = None
    duplicate_of: str | None = None
    coverage: float
    top_evidence: str                       # "type:value(+w); …"


class BatchResult(_Closed):
    job_id: str
    n_items: int
    rows: list[BatchRow]
    csv_url: str | None = None
    json_url: str | None = None


# ======================================================================================== WHITE RABBIT
class InvestigationNode(_Closed):
    id: str
    kind: Literal["domain", "cert", "ip", "query_result", "ad", "list_status", "oracle_flag", "incident", "source"]
    label: str
    meta: dict[str, Any] = {}
    status: Literal["new", "in_campaign", "to_decide", "in_progress", "skipped"] | None = None
    is_new: bool | None = None
    branch: str | None = None               # crtsh | urlscan | adlib | certpl | db | content


class InvestigationStep(_Closed):
    n: int
    tool: str
    query: str
    result_summary: str
    why: str = ""
    produced: list[str] = []
    at: str
    bot: BotName | None = None
    cost_usd: float = 0.0


class Investigation(_Closed):
    id: str
    seed: str
    campaign_id: str | None = None
    status: Literal["running", "paused", "done", "stopped", "error"] = "running"
    budget: dict[str, float] = {"steps": 20, "used": 0, "usd": 0.5, "usd_used": 0.0}
    model: str = "gemini-pro-latest"
    tools: list[str] = []
    started_at: str
    nodes: list[InvestigationNode] = []
    edges: list[dict[str, Any]] = []
    steps: list[InvestigationStep] = []
    conclusions: list[dict[str, Any]] = []  # {text, evidence_refs[]}
    pending_decision: dict[str, Any] | None = None   # Sędzia card: {node_id, question, options}


class InvestigationCreate(_Closed):
    seed: str
    campaign_id: str | None = None
    budget_steps: int = 20
    offline: bool = False


class PromoteRequest(_Closed):
    campaign_id: str
    node_ids: list[str]


# ======================================================================================== ORACLE
class OraclePrediction(_Closed):
    domain: str
    issued_at: str
    issuer: str | None = None
    dna_score: float
    campaign_id: str | None = None
    status: Literal["predicted", "confirmed", "below_threshold", "dismissed"] = "predicted"
    first_ad_at: str | None = None
    lead_time_h: float | None = None
    reasons: list[str] = []


class DomainDNA(_Closed):
    campaign_id: str
    grammar: str
    examples: list[str] = []
    tld_dist: dict[str, float] = {}
    length_hist: dict[str, int] = {}
    registrars: list[str] = []
    issuance_hours: list[int] = []
    asns: list[str] = []
    model: dict[str, Any] = {}              # {name, auc}
    threshold: float = 0.6


class OracleMetrics(_Closed):
    flagged_24h: int = 0
    confirmed: int = 0
    precision_at_20: float | None = None
    median_lead_h: float | None = None
    ct_rate_per_h: float | None = None
    false_alarms_24h: int = 0
    backtest: list[dict[str, Any]] = []     # {domain, flagged_at, first_ad_at, lead_h}


# ======================================================================================== ACT
class ActPackageCreate(_Closed):
    campaign_id: str
    kind: Literal["dsa", "certpl", "stix", "misp", "rules", "bundle"] = "bundle"
    recipients: list[Literal["meta_dsa", "certpl", "google", "registrar"]] = ["meta_dsa", "certpl", "google"]


class ActPackage(_Closed):
    id: str
    kind: Literal["dsa", "certpl", "stix", "misp", "rules", "bundle"]
    campaign_id: str
    status: Literal["draft", "ready", "sent", "exported"] = "draft"   # "sent" = prepared+exported+logged, NEVER sent
    contents: dict[str, int] = {}           # {ads, advertisers, domains, evidence_items}
    recipients: list[dict[str, Any]] = []   # {id, label, enabled, progress: {done, total}, status}
    parts: list[dict[str, Any]] = []        # {key, label, bot, ready}
    notice_text: str = ""
    formats: list[str] = ["pdf", "json", "stix"]
    created_at: str
    sent_at: str | None = None
    outcome: dict[str, int] | None = None   # {removed, total}
    disclaimer: str = "Nic nie zostało wysłane — pakiet przygotowany i wyeksportowany."


class Rule(_Closed):
    id: str
    campaign_id: str
    kind: Literal["urlscan", "url_regex", "html_signature", "yara"]
    body: str


class RuleTest(_Closed):
    hits: int
    tp: int
    needs_review: int
    benign_hits: int
    benign_total: int
    precision: float


# ======================================================================================== TRIAGE / HUNTER / PUBLIC
class TriageCandidate(_Closed):
    campaign_id: str
    score: float
    p: float = 0.0
    for_: list[EvidenceItem] = Field(default=[], alias="for")
    against: list[EvidenceItem] = []
    missing: list[EvidenceItem] = []
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class TriageItem(_Closed):
    id: str
    type: Literal["uncertain", "new_campaign", "oracle", "hunter", "extension", "merge"]
    subject_id: str
    suggestion: str
    score: float = 0.0
    priority: int = 0
    status: Literal["open", "closed"] = "open"
    version: int = 1
    created_at: str
    candidates: list[TriageCandidate] = []
    adjudicator: Adjudication | None = None


class TriageDecision(_Closed):
    action: Literal["accept", "reassign", "reject", "new_campaign", "skip"]
    campaign_id: str | None = None
    note: str | None = None


class HunterSource(_Closed):
    id: str
    kind: Literal["meta_adlibrary", "google_ads_transparency", "certpl", "urlscan", "ct", "extension", "manual"]
    label: str = ""
    schedule: str = "manual"
    status: Literal["ok", "degraded", "error", "disabled"] = "ok"
    last_run_at: str | None = None
    new_24h: int = 0
    errors_24h: int = 0
    enabled: bool = True
    credentials_status: Literal["set", "missing", "not_needed"] = "not_needed"
    config: dict[str, Any] = {}             # phrases, persons, advertisers, country


class HunterRun(_Closed):
    id: str
    source_id: str
    started_at: str
    finished_at: str | None = None
    status: Literal["running", "ok", "error"] = "running"
    found: int = 0
    captured: int = 0
    attributed: int = 0
    incident_ids: list[str] = []
    error: str | None = None


class PublicCampaign(_Closed):
    name: str                               # public name, never KMP-… or raw indicators
    seen_count: int
    since: str
    reasons: list[str]                      # coarse only


class CheckResult(_Closed):
    verdict: Literal["scam", "unknown"]     # never "bezpieczna"
    public_campaign: PublicCampaign | None = None
    advice: list[str] = []


class ExtensionPost(_Closed):
    advertiser: str | None = None
    caption: str | None = None
    cta_url: str | None = None
    creative_phash: str | None = None
    page_url: str | None = None
    install_id: str | None = None


class ExtensionMatch(_Closed):
    match: bool
    label: str | None = None                # "Pasuje do znanej kampanii oszustwa"
    public_campaign: PublicCampaign | None = None
    reasons: list[str] = []


class PublicReport(_Closed):
    url: str | None = None
    post: ExtensionPost | None = None
    note: str | None = None


# ======================================================================================== DASHBOARD / LAB / EVENTS
class StatsOverview(_Closed):
    window: str = "24h"
    incidents: int = 0
    incidents_new: int = 0
    campaigns_active: int = 0
    operators: int = 0
    domains_new: int = 0
    oracle_flagged: int = 0
    triage_open: int = 0
    N: int = 0


class LabMetrics(_Closed):
    view: str = "summary"
    model_version: str = "engine@1"
    data: dict[str, Any] = {}               # shape per view; numbers come from trop eval (G-ENGINE)


class Event(_Closed):
    """SSE envelope. `event:` line = type, `data:` line = this JSON."""
    type: Literal[
        "incident.created", "incident.attributed", "campaign.updated", "alert.created", "triage.created",
        "triage.updated", "job.step", "job.evidence", "job.finding", "job.ranking", "job.done", "job.error", "agent.step",
        "graph.node_added", "graph.edge_added", "casefile.delta", "investigation.decision", "investigation.done",
        "oracle.match", "hunter.capture", "extension.report", "act.submitted", "model.updated",
    ]
    at: str
    data: dict[str, Any]


class SearchHit(_Closed):
    kind: Literal["incident", "campaign", "operator", "domain", "tracking", "person", "trace"]
    id: str
    label: str
    href: str


class Page(_Open):
    items: list[Any]
    next: str | None = None


ALL_MODELS: list[type[BaseModel]] = [
    Incident, IncidentDraft, IncidentSummary, EvidenceItem, LayerCoverage, CampaignScore, Decision, LinkExplanation,
    TemplateDiff, EvidenceValue, CampaignSummary, Campaign, CampaignDNA, Timeline, Member, Indicators, Variant,
    Operator, Operation, MergeRequest, MergePreview, GraphPayload, Job, JobStep, AnalyzeAccepted, Finding, BatchRow,
    BatchResult, Investigation, InvestigationCreate, InvestigationStep, InvestigationNode, PromoteRequest,
    OraclePrediction, DomainDNA, OracleMetrics, ActPackageCreate, ActPackage, Rule, RuleTest, TriageItem,
    TriageDecision, HunterSource, HunterRun, CheckResult, ExtensionPost, ExtensionMatch, PublicReport, StatsOverview,
    LabMetrics, Event, SearchHit,
]


def json_schema() -> dict:
    from pydantic.json_schema import models_json_schema
    _, top = models_json_schema([(m, "serialization") for m in ALL_MODELS], title="TROP contracts")
    return top


if __name__ == "__main__":  # uv run python -m trop.schema > ../docs/contracts/schema.json
    import json
    import sys
    json.dump(json_schema(), sys.stdout, ensure_ascii=False, indent=1)
