// Friendly aliases over the generated contract types (lib/types.ts, from docs/contracts/schema.json).
import type {
  ActPackage, AnalyzeAccepted, BatchResult, BatchRow, Campaign, CampaignDNA, CampaignScore, CampaignSummary, Decision,
  DomainIndicator, Event, EvidenceItem, EvidenceValue, Finding, GraphEdge, GraphNode, GraphPayload, IncidentSummary,
  Indicators, Investigation, InvestigationNode, InvestigationStep, Job, JobStep, LabMetrics, LayerCoverage, LinkExplanation, Member,
  MergePreview, Operation, Operator, OraclePrediction, StatsOverview, Timeline, TimelineEvent,
} from './types';

export type {
  ActPackage, AnalyzeAccepted, BatchResult, BatchRow, Campaign, CampaignDNA, CampaignScore, CampaignSummary, Decision,
  DomainIndicator, Event, EvidenceItem, EvidenceValue, Finding, GraphEdge, GraphNode, GraphPayload, IncidentSummary,
  Indicators, Investigation, InvestigationNode, InvestigationStep, Job, JobStep, LabMetrics, LayerCoverage, LinkExplanation, Member,
  MergePreview, Operation, Operator, OraclePrediction, StatsOverview, Timeline, TimelineEvent,
};

export type Layer = EvidenceItem['type'];
export type BotName = NonNullable<EvidenceItem['bot']>;
export type StepKey = JobStep['key'];
export type StepStatus = NonNullable<JobStep['status']>;
export type DecisionState = Decision['decision'];
export type EventType = Event['type'];

export interface Health {
  ok: boolean;
  mode: 'mock' | 'real' | string;
  db?: unknown;
  redis?: unknown;
  version?: string;
  counts?: Record<string, number>;
}

/** Side panel of a focus view (GET /graph?focus=). `GraphPayload.panel` is an open dict in the contract;
 *  this is the shape the web reads (documented in CONTRACT-REQUEST.md). Every field is optional. */
export interface FocusPanel {
  kind_label?: string;                       // "Domena", "Ślad techniczny", "Osoba", "Materiał"
  badge?: { text: string; tone?: 'g' | 'amber' | 'red' | 'cyan' | 'violet' | 'neutral' };
  tags?: string[];                           // extra pills, e.g. "KMP-017"
  title?: string;
  description?: string;
  facts?: { k: string; v: string }[];
  bot?: BotName;
  bot_text?: string;
  action?: { label: string; href?: string; kind?: 'investigate' | 'trace' | 'incident' | 'campaign'; seed?: string };
  link?: { label: string; href: string };
}

/** Board 14 data: GET /traces/{type}/{value} (CONTRACTS §5). */
export interface TraceData {
  value: string;
  type: string;
  title?: string;
  description?: string;
  campaigns: { id: string; name: string; n: number; operator_id?: string | null; narrative?: string }[];
  weekly: number[];
  latest: IncidentSummary[];
  usage: { label: string; n: number }[];
  co_traces: { type: string; value: string; label?: string; n: number }[];
}
