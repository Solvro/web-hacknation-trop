/* AUTO-GENERATED from docs/contracts/schema.json by web/scripts/gen-types.mjs. Do not edit. */

export interface TropContracts {
  ActPackage?: ActPackage;
  ActPackageCreate?: ActPackageCreate;
  AdLayer?: AdLayer;
  Adjudication?: Adjudication;
  AnalyzeAccepted?: AnalyzeAccepted;
  BatchResult?: BatchResult;
  BatchRow?: BatchRow;
  Campaign?: Campaign;
  CampaignCounts?: CampaignCounts1;
  CampaignDNA?: CampaignDNA;
  CampaignScore?: CampaignScore;
  CampaignSummary?: CampaignSummary;
  CheckResult?: CheckResult;
  Content?: Content;
  Counterfactual?: Counterfactual;
  Decision?: Decision;
  DnaRow?: DnaRow;
  DomainDNA?: DomainDNA;
  DomainIndicator?: DomainIndicator;
  DomainInfo?: DomainInfo;
  Event?: Event;
  EvidenceItem?: EvidenceItem;
  EvidenceValue?: EvidenceValue;
  ExtensionMatch?: ExtensionMatch;
  ExtensionPost?: ExtensionPost;
  FaceHit?: FaceHit;
  Finding?: Finding;
  GraphEdge?: GraphEdge;
  GraphNode?: GraphNode;
  GraphPayload?: GraphPayload;
  Heat?: Heat2;
  HunterRun?: HunterRun;
  HunterSource?: HunterSource;
  Incident?: Incident;
  IncidentDraft?: IncidentDraft;
  IncidentSource?: IncidentSource2;
  IncidentSummary?: IncidentSummary;
  Indicators?: Indicators;
  Infra?: Infra2;
  Investigation?: Investigation;
  InvestigationCreate?: InvestigationCreate;
  InvestigationNode?: InvestigationNode;
  InvestigationStep?: InvestigationStep;
  Job?: Job;
  JobInput?: JobInput;
  JobStep?: JobStep;
  LabMetrics?: LabMetrics;
  Landing?: Landing2;
  LayerCoverage?: LayerCoverage;
  LinkExplanation?: LinkExplanation;
  Media?: Media2;
  Member?: Member;
  MergePreview?: MergePreview;
  MergeRequest?: MergeRequest;
  Operation?: Operation;
  Operator?: Operator;
  OracleMetrics?: OracleMetrics;
  OraclePrediction?: OraclePrediction;
  PromoteRequest?: PromoteRequest;
  PublicCampaign?: PublicCampaign;
  PublicReport?: PublicReport;
  Quality?: Quality2;
  Rule?: Rule;
  RuleTest?: RuleTest;
  RunnerUp?: RunnerUp;
  SearchHit?: SearchHit;
  StatsOverview?: StatsOverview;
  TemplateDiff?: TemplateDiff;
  Timeline?: Timeline;
  TimelineEvent?: TimelineEvent;
  Tok?: Tok;
  Tracking?: Tracking2;
  TriageCandidate?: TriageCandidate;
  TriageDecision?: TriageDecision;
  TriageItem?: TriageItem;
  Variant?: Variant;
  VideoInfo?: VideoInfo;
  WhyNot?: WhyNot;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "ActPackage".
 */
export interface ActPackage {
  id: string;
  kind: "dsa" | "certpl" | "stix" | "misp" | "rules" | "bundle";
  campaign_id: string;
  status?: "draft" | "ready" | "sent" | "exported";
  contents?: {
    [k: string]: number;
  };
  recipients?: {
    [k: string]: unknown;
  }[];
  parts?: {
    [k: string]: unknown;
  }[];
  notice_text?: string;
  formats?: string[];
  created_at: string;
  sent_at?: string | null;
  outcome?: {
    [k: string]: number;
  } | null;
  disclaimer?: string;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "ActPackageCreate".
 */
export interface ActPackageCreate {
  campaign_id: string;
  kind?: "dsa" | "certpl" | "stix" | "misp" | "rules" | "bundle";
  recipients?: ("meta_dsa" | "certpl" | "google" | "registrar")[];
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "AdLayer".
 */
export interface AdLayer {
  platform?: string | null;
  kind?: string | null;
  library_id?: string | null;
  advertiser?: string | null;
  page_id?: string | null;
  text?: string | null;
  overlay?: string | null;
  display_link?: string | null;
  cta?: string | null;
  narrative?: string | null;
  persons?: string[];
  is_decoy?: boolean | null;
  vertical?: string | null;
  creative_phash?: string | null;
  screenshot_path?: string | null;
  screenshots?: string[];
  video_path?: string | null;
  video_title?: string | null;
  n_creatives?: number | null;
  delivery?: {
    [k: string]: unknown;
  };
  [k: string]: unknown;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Adjudication".
 */
export interface Adjudication {
  model: string;
  verdict: "same" | "different" | "unsure" | "veto";
  confidence: number;
  rationale?: string[];
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "AnalyzeAccepted".
 */
export interface AnalyzeAccepted {
  job_id: string;
  incident_id?: string | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "BatchResult".
 */
export interface BatchResult {
  job_id: string;
  n_items: number;
  rows: BatchRow[];
  csv_url?: string | null;
  json_url?: string | null;
}
/**
 * One row of results.csv (hidden-test hedge).
 *
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "BatchRow".
 */
export interface BatchRow {
  item: string;
  incident_id: string;
  decision: "assign" | "confirm" | "ambiguous" | "new" | "insufficient";
  campaign: string;
  campaign_score: number;
  campaign_p: number;
  operator?: string | null;
  operation: string;
  variant?: string | null;
  same_operator_as?: string | null;
  duplicate_of?: string | null;
  coverage: number;
  top_evidence: string;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Campaign".
 */
export interface Campaign {
  id: string;
  name: string;
  narrative?: string;
  vertical?: string | null;
  status?: "active" | "fading" | "candidate" | "closed";
  operator_id?: string | null;
  operation_id?: string | null;
  heat?: Heat;
  n_incidents?: number;
  n_domains?: number;
  new_domains_24h?: number;
  predicted_domains?: number;
  persons?: string[];
  report_status?: "none" | "draft" | "sent" | "needs_update";
  merge_hint?: string | null;
  description?: string;
  level?: "L2";
  counts?: CampaignCounts;
  first_seen?: string | null;
  last_seen?: string | null;
  brands?: string[];
}
export interface Heat {
  series_48h?: number[];
  series_14d?: number[];
  trend_pct?: number;
}
export interface CampaignCounts {
  incidents?: number;
  incidents_24h?: number;
  domains?: number;
  certs_tonight?: number;
  advertisers?: number;
  advertisers_removed?: number;
  persons?: number;
  certpl_listed?: number;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "CampaignCounts".
 */
export interface CampaignCounts1 {
  incidents?: number;
  incidents_24h?: number;
  domains?: number;
  certs_tonight?: number;
  advertisers?: number;
  advertisers_removed?: number;
  persons?: number;
  certpl_listed?: number;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "CampaignDNA".
 */
export interface CampaignDNA {
  campaign_id: string;
  signature: DnaRow[];
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "DnaRow".
 */
export interface DnaRow {
  layer: "tracking" | "kit" | "infra" | "content" | "persons" | "visual" | "ad" | "media";
  field: string;
  value: string;
  display?: string | null;
  members_with: number;
  members_total: number;
  strength: "H" | "M" | "L";
  bot?: ("zwiadowca" | "tropiciel" | "czytelnik" | "notariusz" | "archiwista" | "sedzia") | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "CampaignScore".
 */
export interface CampaignScore {
  campaign_id: string;
  score: number;
  score_operator?: number;
  p?: number;
  p_value?: number | null;
  in_set?: boolean;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "CampaignSummary".
 */
export interface CampaignSummary {
  id: string;
  name: string;
  narrative?: string;
  vertical?: string | null;
  status?: "active" | "fading" | "candidate" | "closed";
  operator_id?: string | null;
  operation_id?: string | null;
  heat?: Heat1;
  n_incidents?: number;
  n_domains?: number;
  new_domains_24h?: number;
  predicted_domains?: number;
  persons?: string[];
  report_status?: "none" | "draft" | "sent" | "needs_update";
  merge_hint?: string | null;
}
export interface Heat1 {
  series_48h?: number[];
  series_14d?: number[];
  trend_pct?: number;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "CheckResult".
 */
export interface CheckResult {
  verdict: "scam" | "unknown";
  public_campaign?: PublicCampaign | null;
  advice?: string[];
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "PublicCampaign".
 */
export interface PublicCampaign {
  name: string;
  seen_count: number;
  since: string;
  reasons: string[];
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Content".
 */
export interface Content {
  headline_template?: string | null;
  h1_template?: string | null;
  persons?: string[];
  comment_names?: string[];
  brands?: string[];
  products?: string[];
  vertical?: string | null;
  vertical_scores?: {
    [k: string]: number;
  };
  lang?: string | null;
  ad_name?: string | null;
  narrative?: string | null;
  keywords?: string[];
  contacts?: {
    [k: string]: string[];
  };
  [k: string]: unknown;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Counterfactual".
 */
export interface Counterfactual {
  change: string;
  p_new: number;
  decision_new: string;
}
/**
 * GET /incidents/{id}/decision. RESULTS §4 states; p = isotonic/Platt calibration of score_campaign.
 *
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Decision".
 */
export interface Decision {
  incident_id: string;
  decision: "assign" | "confirm" | "ambiguous" | "new" | "insufficient";
  campaign_id?: string | null;
  candidate_campaign_id?: string | null;
  score?: number;
  margin?: number;
  p?: number;
  tau?: number;
  delta?: number;
  confirm_floor?: number;
  operator_id?: string | null;
  operation_id?: string | null;
  same_operator_as?: string | null;
  duplicate_of?: string | null;
  scores?: CampaignScore[];
  runner_up?: RunnerUp | null;
  coverage?: number;
  layers?: LayerCoverage[];
  evidence?: EvidenceItem[];
  why_not?: WhyNot[];
  adjudicator?: Adjudication | null;
  alpha?: number | null;
  conformal_tau?: number | null;
  set?: string[];
  calibration?: {
    [k: string]: number;
  } | null;
  model_version?: string;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "RunnerUp".
 */
export interface RunnerUp {
  campaign_id: string;
  score: number;
  p?: number;
  same_operator?: boolean;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "LayerCoverage".
 */
export interface LayerCoverage {
  layer: "tracking" | "kit" | "infra" | "content" | "persons" | "visual" | "ad" | "media";
  state: "available" | "partial" | "missing" | "error";
  reason?: string | null;
}
/**
 * One chip. `type` is the UI layer; `field` the engine feature type (e.g. 'fb_pixel', 'kit_tenant').
 *
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "EvidenceItem".
 */
export interface EvidenceItem {
  type: "tracking" | "kit" | "infra" | "content" | "persons" | "visual" | "ad" | "media";
  field: string;
  value: string;
  display: string;
  strength: "H" | "M" | "L";
  weight: number;
  level?: "campaign" | "operator_only" | "platform";
  df?: number;
  N?: number;
  idf?: number;
  state?: "match" | "conflict" | "missing" | "zero";
  sides?: {
    [k: string]: string;
  } | null;
  bot?: ("zwiadowca" | "tropiciel" | "czytelnik" | "notariusz" | "archiwista" | "sedzia") | null;
  shap?: number | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "WhyNot".
 */
export interface WhyNot {
  campaign_id: string;
  bullets: string[];
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "DomainDNA".
 */
export interface DomainDNA {
  campaign_id: string;
  grammar: string;
  examples?: string[];
  tld_dist?: {
    [k: string]: number;
  };
  length_hist?: {
    [k: string]: number;
  };
  registrars?: string[];
  issuance_hours?: number[];
  asns?: string[];
  model?: {
    [k: string]: unknown;
  };
  threshold?: number;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "DomainIndicator".
 */
export interface DomainIndicator {
  fqdn: string;
  cert_issued_at?: string | null;
  registered_at?: string | null;
  oracle_predicted_at?: string | null;
  on_certpl?: boolean;
  online?: boolean | ("502" | "unknown");
  ads_seen?: number;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "DomainInfo".
 */
export interface DomainInfo {
  fqdn: string;
  etld1?: string | null;
  tld?: string | null;
  sld_label?: string | null;
  ips?: string[];
  cdn?: string[];
  asn?: string | null;
  cert?: {
    [k: string]: unknown;
  } | null;
  enrich?: {
    [k: string]: unknown;
  };
  [k: string]: unknown;
}
/**
 * SSE envelope. `event:` line = type, `data:` line = this JSON.
 *
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Event".
 */
export interface Event {
  type:
    | "incident.created"
    | "incident.attributed"
    | "campaign.updated"
    | "alert.created"
    | "triage.created"
    | "triage.updated"
    | "job.step"
    | "job.evidence"
    | "job.finding"
    | "job.ranking"
    | "job.done"
    | "job.error"
    | "agent.step"
    | "graph.node_added"
    | "graph.edge_added"
    | "casefile.delta"
    | "investigation.decision"
    | "investigation.done"
    | "oracle.match"
    | "hunter.capture"
    | "extension.report"
    | "act.submitted"
    | "model.updated";
  at: string;
  data: {
    [k: string]: unknown;
  };
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "EvidenceValue".
 */
export interface EvidenceValue {
  type: "tracking" | "kit" | "infra" | "content" | "persons" | "visual" | "ad" | "media";
  field: string;
  value: string;
  df: number;
  N: number;
  idf: number;
  first_seen?: string | null;
  last_seen?: string | null;
  weekly?: number[];
  campaigns?: {
    [k: string]: unknown;
  }[];
  operator_hint?: string | null;
  incidents?: IncidentSummary[];
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "IncidentSummary".
 */
export interface IncidentSummary {
  id: string;
  captured_at?: string | null;
  source: string;
  domain?: string | null;
  title?: string | null;
  person?: string | null;
  campaign_id?: string | null;
  decision?: ("assign" | "confirm" | "ambiguous" | "new" | "insufficient") | null;
  p?: number | null;
  coverage?: number | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "ExtensionMatch".
 */
export interface ExtensionMatch {
  match: boolean;
  label?: string | null;
  public_campaign?: PublicCampaign | null;
  reasons?: string[];
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "ExtensionPost".
 */
export interface ExtensionPost {
  advertiser?: string | null;
  caption?: string | null;
  cta_url?: string | null;
  creative_phash?: string | null;
  page_url?: string | null;
  install_id?: string | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "FaceHit".
 */
export interface FaceHit {
  identity?: string | null;
  person_id?: string | null;
  score?: number;
  lead?: number | null;
  source?: string | null;
  deepfake?: number | null;
  [k: string]: unknown;
}
/**
 * A finding outlined on the captured page (Sprawdź-2 left column).
 *
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Finding".
 */
export interface Finding {
  evidence: EvidenceItem;
  where?: string | null;
  selector?: string | null;
  bbox?: number[] | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "GraphEdge".
 */
export interface GraphEdge {
  a: string;
  b: string;
  type:
    | ("tracking" | "kit" | "infra" | "content" | "persons" | "visual" | "ad" | "media")
    | ("member" | "operator" | "operation");
  weight?: number;
  level?: ("L0" | "L1" | "L2" | "L3") | null;
  label?: string | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "GraphNode".
 */
export interface GraphNode {
  id: string;
  kind: "incident" | "domain" | "campaign" | "operator" | "operation" | "person" | "trace" | "cert" | "advertiser";
  label: string;
  campaign_id?: string | null;
  size?: number;
  first_seen?: string | null;
  meta?: {
    [k: string]: unknown;
  };
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "GraphPayload".
 */
export interface GraphPayload {
  nodes: GraphNode[];
  edges: GraphEdge[];
  hulls?: {
    [k: string]: unknown;
  }[];
  focus?: string | null;
  panel?: {
    [k: string]: unknown;
  } | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Heat".
 */
export interface Heat2 {
  series_48h?: number[];
  series_14d?: number[];
  trend_pct?: number;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "HunterRun".
 */
export interface HunterRun {
  id: string;
  source_id: string;
  started_at: string;
  finished_at?: string | null;
  status?: "running" | "ok" | "error";
  found?: number;
  captured?: number;
  attributed?: number;
  incident_ids?: string[];
  error?: string | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "HunterSource".
 */
export interface HunterSource {
  id: string;
  kind: "meta_adlibrary" | "google_ads_transparency" | "certpl" | "urlscan" | "ct" | "extension" | "manual";
  label?: string;
  schedule?: string;
  status?: "ok" | "degraded" | "error" | "disabled";
  last_run_at?: string | null;
  new_24h?: number;
  errors_24h?: number;
  enabled?: boolean;
  credentials_status?: "set" | "missing" | "not_needed";
  config?: {
    [k: string]: unknown;
  };
}
/**
 * The engine's unit. `IncidentDraft` is the same shape before it has a DB id.
 *
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Incident".
 */
export interface Incident {
  id: string;
  source?: IncidentSource;
  ad?: AdLayer1;
  landing?: Landing;
  tracking?: Tracking;
  infra?: Infra;
  content?: Content1;
  media?: Media;
  quality?: Quality;
  emb?: {
    [k: string]: unknown;
  };
  [k: string]: unknown;
}
export interface IncidentSource {
  type?:
    | "sample_dir"
    | "bundle"
    | "capture_tool"
    | "url"
    | "upload"
    | "har"
    | "screenshot"
    | "video"
    | "adlibrary"
    | "urlscan"
    | "extension"
    | "hunter"
    | "manual";
  path?: string | null;
  ref?: string | null;
  captured_at?: string | null;
  [k: string]: unknown;
}
export interface AdLayer1 {
  platform?: string | null;
  kind?: string | null;
  library_id?: string | null;
  advertiser?: string | null;
  page_id?: string | null;
  text?: string | null;
  overlay?: string | null;
  display_link?: string | null;
  cta?: string | null;
  narrative?: string | null;
  persons?: string[];
  is_decoy?: boolean | null;
  vertical?: string | null;
  creative_phash?: string | null;
  screenshot_path?: string | null;
  screenshots?: string[];
  video_path?: string | null;
  video_title?: string | null;
  n_creatives?: number | null;
  delivery?: {
    [k: string]: unknown;
  };
  [k: string]: unknown;
}
export interface Landing {
  entry_url?: string | null;
  final_url?: string | null;
  host?: string | null;
  etld1?: string | null;
  status?: number | null;
  title?: string | null;
  text?: string | null;
  lang?: string | null;
  h1?: string[];
  dom_paths?: string[];
  css_classes?: string[];
  page_role?: string | null;
  redirect_chain?: string[];
  chain_urls?: string[];
  chain_titles?: string[];
  n_hars?: number;
  n_pages?: number;
  screenshot_path?: string | null;
  screenshot_phash?: string | null;
  favicon_mmh3?: number | null;
  forms?: {
    [k: string]: unknown;
  }[];
  outlinks?: string[];
  [k: string]: unknown;
}
export interface Tracking {
  fb_pixels?: string[];
  capi_gateways?: string[];
  google_ads?: string[];
  ga4?: string[];
  gtm?: string[];
  tiktok_pixels?: string[];
  snap_pixels?: string[];
  kit_tenants?: string[];
  lander_ids?: string[];
  landing_type_ids?: string[];
  video_hosts?: string[];
  kit_endpoints?: string[];
  url_param_schema?: string | null;
  chain_param_schemas?: string[];
  entry_path_template?: string | null;
  path_shapes?: string[];
  third_party?: string[];
  asset_hashes?: string[];
  brand_asset_hashes?: string[];
  [k: string]: unknown;
}
export interface Infra {
  domains?: DomainInfo[];
  ips?: string[];
  cdn?: string[];
  origin_ips?: string[];
  on_certpl_list?: boolean | null;
  [k: string]: unknown;
}
export interface Content1 {
  headline_template?: string | null;
  h1_template?: string | null;
  persons?: string[];
  comment_names?: string[];
  brands?: string[];
  products?: string[];
  vertical?: string | null;
  vertical_scores?: {
    [k: string]: number;
  };
  lang?: string | null;
  ad_name?: string | null;
  narrative?: string | null;
  keywords?: string[];
  contacts?: {
    [k: string]: string[];
  };
  [k: string]: unknown;
}
export interface Media {
  faces?: FaceHit[];
  video?: VideoInfo | null;
  asr_text?: string | null;
  asr_model?: string | null;
  voice_id?: string | null;
  voice_embedding_ref?: string | null;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "VideoInfo".
 */
export interface VideoInfo {
  path?: string | null;
  duration_s?: number | null;
  keyframes?: string[];
  gemini?: {
    [k: string]: unknown;
  };
  [k: string]: unknown;
}
export interface Quality {
  available?: string[];
  missing?: string[];
  errors?: string[];
  [k: string]: unknown;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "IncidentDraft".
 */
export interface IncidentDraft {
  id?: string;
  source?: IncidentSource1;
  ad?: AdLayer2;
  landing?: Landing1;
  tracking?: Tracking1;
  infra?: Infra1;
  content?: Content2;
  media?: Media1;
  quality?: Quality1;
  emb?: {
    [k: string]: unknown;
  };
  [k: string]: unknown;
}
export interface IncidentSource1 {
  type?:
    | "sample_dir"
    | "bundle"
    | "capture_tool"
    | "url"
    | "upload"
    | "har"
    | "screenshot"
    | "video"
    | "adlibrary"
    | "urlscan"
    | "extension"
    | "hunter"
    | "manual";
  path?: string | null;
  ref?: string | null;
  captured_at?: string | null;
  [k: string]: unknown;
}
export interface AdLayer2 {
  platform?: string | null;
  kind?: string | null;
  library_id?: string | null;
  advertiser?: string | null;
  page_id?: string | null;
  text?: string | null;
  overlay?: string | null;
  display_link?: string | null;
  cta?: string | null;
  narrative?: string | null;
  persons?: string[];
  is_decoy?: boolean | null;
  vertical?: string | null;
  creative_phash?: string | null;
  screenshot_path?: string | null;
  screenshots?: string[];
  video_path?: string | null;
  video_title?: string | null;
  n_creatives?: number | null;
  delivery?: {
    [k: string]: unknown;
  };
  [k: string]: unknown;
}
export interface Landing1 {
  entry_url?: string | null;
  final_url?: string | null;
  host?: string | null;
  etld1?: string | null;
  status?: number | null;
  title?: string | null;
  text?: string | null;
  lang?: string | null;
  h1?: string[];
  dom_paths?: string[];
  css_classes?: string[];
  page_role?: string | null;
  redirect_chain?: string[];
  chain_urls?: string[];
  chain_titles?: string[];
  n_hars?: number;
  n_pages?: number;
  screenshot_path?: string | null;
  screenshot_phash?: string | null;
  favicon_mmh3?: number | null;
  forms?: {
    [k: string]: unknown;
  }[];
  outlinks?: string[];
  [k: string]: unknown;
}
export interface Tracking1 {
  fb_pixels?: string[];
  capi_gateways?: string[];
  google_ads?: string[];
  ga4?: string[];
  gtm?: string[];
  tiktok_pixels?: string[];
  snap_pixels?: string[];
  kit_tenants?: string[];
  lander_ids?: string[];
  landing_type_ids?: string[];
  video_hosts?: string[];
  kit_endpoints?: string[];
  url_param_schema?: string | null;
  chain_param_schemas?: string[];
  entry_path_template?: string | null;
  path_shapes?: string[];
  third_party?: string[];
  asset_hashes?: string[];
  brand_asset_hashes?: string[];
  [k: string]: unknown;
}
export interface Infra1 {
  domains?: DomainInfo[];
  ips?: string[];
  cdn?: string[];
  origin_ips?: string[];
  on_certpl_list?: boolean | null;
  [k: string]: unknown;
}
export interface Content2 {
  headline_template?: string | null;
  h1_template?: string | null;
  persons?: string[];
  comment_names?: string[];
  brands?: string[];
  products?: string[];
  vertical?: string | null;
  vertical_scores?: {
    [k: string]: number;
  };
  lang?: string | null;
  ad_name?: string | null;
  narrative?: string | null;
  keywords?: string[];
  contacts?: {
    [k: string]: string[];
  };
  [k: string]: unknown;
}
export interface Media1 {
  faces?: FaceHit[];
  video?: VideoInfo | null;
  asr_text?: string | null;
  asr_model?: string | null;
  voice_id?: string | null;
  voice_embedding_ref?: string | null;
  [k: string]: unknown;
}
export interface Quality1 {
  available?: string[];
  missing?: string[];
  errors?: string[];
  [k: string]: unknown;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "IncidentSource".
 */
export interface IncidentSource2 {
  type?:
    | "sample_dir"
    | "bundle"
    | "capture_tool"
    | "url"
    | "upload"
    | "har"
    | "screenshot"
    | "video"
    | "adlibrary"
    | "urlscan"
    | "extension"
    | "hunter"
    | "manual";
  path?: string | null;
  ref?: string | null;
  captured_at?: string | null;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Indicators".
 */
export interface Indicators {
  domains?: DomainIndicator[];
  tracking?: EvidenceItem[];
  kit?: EvidenceItem[];
  persons?: {
    [k: string]: unknown;
  }[];
  advertisers?: {
    [k: string]: unknown;
  }[];
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Infra".
 */
export interface Infra2 {
  domains?: DomainInfo[];
  ips?: string[];
  cdn?: string[];
  origin_ips?: string[];
  on_certpl_list?: boolean | null;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Investigation".
 */
export interface Investigation {
  id: string;
  seed: string;
  campaign_id?: string | null;
  status?: "running" | "paused" | "done" | "stopped" | "error";
  budget?: {
    [k: string]: number;
  };
  model?: string;
  tools?: string[];
  started_at: string;
  nodes?: InvestigationNode[];
  edges?: {
    [k: string]: unknown;
  }[];
  steps?: InvestigationStep[];
  conclusions?: {
    [k: string]: unknown;
  }[];
  pending_decision?: {
    [k: string]: unknown;
  } | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "InvestigationNode".
 */
export interface InvestigationNode {
  id: string;
  kind: "domain" | "cert" | "ip" | "query_result" | "ad" | "list_status" | "oracle_flag" | "incident" | "source";
  label: string;
  meta?: {
    [k: string]: unknown;
  };
  status?: ("new" | "in_campaign" | "to_decide" | "in_progress" | "skipped") | null;
  is_new?: boolean | null;
  branch?: string | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "InvestigationStep".
 */
export interface InvestigationStep {
  n: number;
  tool: string;
  query: string;
  result_summary: string;
  why?: string;
  produced?: string[];
  at: string;
  bot?: ("zwiadowca" | "tropiciel" | "czytelnik" | "notariusz" | "archiwista" | "sedzia") | null;
  cost_usd?: number;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "InvestigationCreate".
 */
export interface InvestigationCreate {
  seed: string;
  campaign_id?: string | null;
  budget_steps?: number;
  offline?: boolean;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Job".
 */
export interface Job {
  id: string;
  status?: "queued" | "running" | "done" | "error";
  input: JobInput;
  incident_id?: string | null;
  decision?: ("assign" | "confirm" | "ambiguous" | "new" | "insufficient") | null;
  campaign_id?: string | null;
  total_ms?: number | null;
  steps?: JobStep[];
  error?: string | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "JobInput".
 */
export interface JobInput {
  kind: "url" | "file" | "zip" | "folder" | "trace" | "batch";
  name: string;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "JobStep".
 */
export interface JobStep {
  key: "capture" | "tracking" | "content" | "infra" | "compare" | "verdict";
  bot: "zwiadowca" | "tropiciel" | "czytelnik" | "notariusz" | "archiwista" | "sedzia";
  label: string;
  status?: "pending" | "run" | "done" | "warn" | "skip" | "error";
  started_at?: string | null;
  duration_ms?: number | null;
  detail?: string | null;
  warnings?: string[];
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "LabMetrics".
 */
export interface LabMetrics {
  view?: string;
  model_version?: string;
  data?: {
    [k: string]: unknown;
  };
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Landing".
 */
export interface Landing2 {
  entry_url?: string | null;
  final_url?: string | null;
  host?: string | null;
  etld1?: string | null;
  status?: number | null;
  title?: string | null;
  text?: string | null;
  lang?: string | null;
  h1?: string[];
  dom_paths?: string[];
  css_classes?: string[];
  page_role?: string | null;
  redirect_chain?: string[];
  chain_urls?: string[];
  chain_titles?: string[];
  n_hars?: number;
  n_pages?: number;
  screenshot_path?: string | null;
  screenshot_phash?: string | null;
  favicon_mmh3?: number | null;
  forms?: {
    [k: string]: unknown;
  }[];
  outlinks?: string[];
  [k: string]: unknown;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "LinkExplanation".
 */
export interface LinkExplanation {
  a: string;
  b: string;
  score_campaign: number;
  score_operator: number;
  p: number;
  tau?: number;
  delta?: number;
  decision: "linked" | "not_linked" | "triage";
  shared_level?: ("L0" | "L1" | "L2" | "L3") | null;
  operator_id?: string | null;
  layers_independent?: number;
  layers_required?: number;
  coverage?: number;
  summary?: string;
  contributions?: {
    [k: string]: unknown;
  }[];
  evidence?: EvidenceItem[];
  missing?: EvidenceItem[];
  conflicts?: EvidenceItem[];
  zeroed?: EvidenceItem[];
  counterfactuals?: Counterfactual[];
  adjudicator?: Adjudication | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Media".
 */
export interface Media2 {
  faces?: FaceHit[];
  video?: VideoInfo | null;
  asr_text?: string | null;
  asr_model?: string | null;
  voice_id?: string | null;
  voice_embedding_ref?: string | null;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Member".
 */
export interface Member {
  incident_id: string;
  captured_at?: string | null;
  source: string;
  domain?: string | null;
  person?: string | null;
  level?: "L0" | "L1" | "L2" | "L3";
  variant_id?: string | null;
  parent_id?: string | null;
  score?: number;
  p?: number;
  top_evidence?: EvidenceItem[];
  layers?: LayerCoverage[];
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "MergePreview".
 */
export interface MergePreview {
  a: CampaignSummary;
  b: CampaignSummary;
  shared: EvidenceItem[];
  before: {
    [k: string]: number;
  };
  after: {
    [k: string]: number;
  };
  undo_token?: string | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "MergeRequest".
 */
export interface MergeRequest {
  other_id: string;
  keep?: "self" | "other";
}
/**
 * Shared funnel across operators/campaigns (DANE finding: A + C + K).
 *
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Operation".
 */
export interface Operation {
  id: string;
  name: string;
  campaigns: string[];
  operators?: string[];
  funnel?: string[];
  shared?: EvidenceItem[];
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Operator".
 */
export interface Operator {
  id: string;
  codename: string;
  campaigns?: {
    [k: string]: unknown;
  }[];
  shared?: EvidenceItem[];
  narratives?: string[];
  operation_id?: string | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "OracleMetrics".
 */
export interface OracleMetrics {
  flagged_24h?: number;
  confirmed?: number;
  precision_at_20?: number | null;
  median_lead_h?: number | null;
  ct_rate_per_h?: number | null;
  false_alarms_24h?: number;
  backtest?: {
    [k: string]: unknown;
  }[];
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "OraclePrediction".
 */
export interface OraclePrediction {
  domain: string;
  issued_at: string;
  issuer?: string | null;
  dna_score: number;
  campaign_id?: string | null;
  status?: "predicted" | "confirmed" | "below_threshold" | "dismissed";
  first_ad_at?: string | null;
  lead_time_h?: number | null;
  reasons?: string[];
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "PromoteRequest".
 */
export interface PromoteRequest {
  campaign_id: string;
  node_ids: string[];
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "PublicReport".
 */
export interface PublicReport {
  url?: string | null;
  post?: ExtensionPost | null;
  note?: string | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Quality".
 */
export interface Quality2 {
  available?: string[];
  missing?: string[];
  errors?: string[];
  [k: string]: unknown;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Rule".
 */
export interface Rule {
  id: string;
  campaign_id: string;
  kind: "urlscan" | "url_regex" | "html_signature" | "yara";
  body: string;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "RuleTest".
 */
export interface RuleTest {
  hits: number;
  tp: number;
  needs_review: number;
  benign_hits: number;
  benign_total: number;
  precision: number;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "SearchHit".
 */
export interface SearchHit {
  kind: "incident" | "campaign" | "operator" | "domain" | "tracking" | "person" | "trace";
  id: string;
  label: string;
  href: string;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "StatsOverview".
 */
export interface StatsOverview {
  window?: string;
  incidents?: number;
  incidents_new?: number;
  campaigns_active?: number;
  operators?: number;
  domains_new?: number;
  oracle_flagged?: number;
  triage_open?: number;
  N?: number;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "TemplateDiff".
 */
export interface TemplateDiff {
  text: {
    [k: string]: Tok[];
  };
  dom?: {
    [k: string]: unknown;
  };
  assets?: {
    [k: string]: unknown;
  }[];
  visual?: {
    [k: string]: unknown;
  };
  metrics?: {
    [k: string]: unknown;
  };
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Tok".
 */
export interface Tok {
  t: string;
  kind: "same" | "ins" | "del" | "slot";
  slot?: string | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Timeline".
 */
export interface Timeline {
  days: {
    [k: string]: unknown;
  }[];
  events?: TimelineEvent[];
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "TimelineEvent".
 */
export interface TimelineEvent {
  at: string;
  kind: "domain_registered" | "cert_batch" | "oracle_predicted" | "act_sent" | "incident" | "hunter_capture";
  ref: string;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Tracking".
 */
export interface Tracking2 {
  fb_pixels?: string[];
  capi_gateways?: string[];
  google_ads?: string[];
  ga4?: string[];
  gtm?: string[];
  tiktok_pixels?: string[];
  snap_pixels?: string[];
  kit_tenants?: string[];
  lander_ids?: string[];
  landing_type_ids?: string[];
  video_hosts?: string[];
  kit_endpoints?: string[];
  url_param_schema?: string | null;
  chain_param_schemas?: string[];
  entry_path_template?: string | null;
  path_shapes?: string[];
  third_party?: string[];
  asset_hashes?: string[];
  brand_asset_hashes?: string[];
  [k: string]: unknown;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "TriageCandidate".
 */
export interface TriageCandidate {
  campaign_id: string;
  score: number;
  p?: number;
  for?: EvidenceItem[];
  against?: EvidenceItem[];
  missing?: EvidenceItem[];
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "TriageDecision".
 */
export interface TriageDecision {
  action: "accept" | "reassign" | "reject" | "new_campaign" | "skip";
  campaign_id?: string | null;
  note?: string | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "TriageItem".
 */
export interface TriageItem {
  id: string;
  type: "uncertain" | "new_campaign" | "oracle" | "hunter" | "extension" | "merge";
  subject_id: string;
  suggestion: string;
  score?: number;
  priority?: number;
  status?: "open" | "closed";
  version?: number;
  created_at: string;
  candidates?: TriageCandidate[];
  adjudicator?: Adjudication | null;
}
/**
 * This interface was referenced by `TropContracts`'s JSON-Schema
 * via the `definition` "Variant".
 */
export interface Variant {
  id: string;
  campaign_id: string;
  label: string;
  members: string[];
  template?: string | null;
}
