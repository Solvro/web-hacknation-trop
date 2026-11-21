'use client';
// State machine for one Sprawdź analysis, fed by GET /jobs/{id}/stream (CONTRACTS §4.1).
import { useCallback, useReducer } from 'react';
import type { CampaignScore, Decision, Event, EvidenceItem, Finding, JobStep, StepKey } from './contracts';
import { BOTS } from './copy';
import { useEventStream } from './stream';
import { scenarioEvents, scenarioFromJobId, type Scenario } from './mock/jobs';

export interface JobState {
  steps: JobStep[];
  evidence: EvidenceItem[];
  findings: Finding[];
  scores: CampaignScore[];
  decision: Decision | null;
  incidentId: string | null;
  error: { step: string; message: string } | null;
  done: boolean;
  source: 'live' | 'replay' | 'simulated' | null;
  startedAt: number;
}

const initial = (): JobState => ({
  steps: BOTS.map((b) => ({ key: b.step, bot: b.key, label: b.stepName, status: 'pending' as const })),
  evidence: [], findings: [], scores: [], decision: null, incidentId: null, error: null, done: false, source: null, startedAt: Date.now(),
});

type Action = { t: 'ev'; ev: Event } | { t: 'src'; src: JobState['source'] } | { t: 'reset' };

function reducer(s: JobState, a: Action): JobState {
  if (a.t === 'reset') return initial();
  if (a.t === 'src') return { ...s, source: a.src, startedAt: Date.now() };
  const { type, data } = a.ev as { type: string; data: Record<string, unknown> };
  switch (type) {
    case 'job.step': {
      const st = data.step as JobStep;
      return { ...s, steps: s.steps.map((x) => (x.key === st.key ? { ...x, ...st } : x)) };
    }
    case 'job.evidence': {
      const item = { ...(data.item as EvidenceItem) };
      if (!item.bot && data.bot) item.bot = data.bot as EvidenceItem['bot'];
      if (s.evidence.some((e) => e.field === item.field && e.value === item.value && e.display === item.display)) return s;
      return { ...s, evidence: [...s.evidence, item] };
    }
    case 'job.finding':
      return { ...s, findings: [...s.findings, data.finding as Finding] };
    case 'job.ranking':
      return { ...s, scores: (data.scores as CampaignScore[]) ?? s.scores };
    case 'job.done': {
      const d = data.decision as Decision;
      return { ...s, decision: d, incidentId: (data.incident_id as string) ?? d?.incident_id ?? s.incidentId, done: true, scores: d?.scores?.length ? d.scores : s.scores };
    }
    case 'job.error':
      return { ...s, error: { step: String(data.step ?? ''), message: String(data.message ?? 'Błąd analizy') } };
  }
  return s;
}

export function useJob(jobId: string, opts: { replay?: boolean; enabled?: boolean; fallback?: Scenario } = {}) {
  const [state, dispatch] = useReducer(reducer, undefined, initial);
  const local = scenarioFromJobId(jobId);
  const sc: Scenario = local ?? opts.fallback ?? 'zamach';
  const onEvent = useCallback((ev: Event) => dispatch({ t: 'ev', ev }), []);
  const onSource = useCallback((src: JobState['source']) => dispatch({ t: 'src', src }), []);
  useEventStream({
    path: opts.enabled === false ? null : `/jobs/${encodeURIComponent(jobId)}/stream`,
    replay: opts.replay,
    local: !!local,
    simulate: () => scenarioEvents(jobId, sc),
    onEvent, onSource,
  });
  const current = state.steps.find((x) => x.status === 'run') ?? null;
  const stepIndex = (k: StepKey) => state.steps.findIndex((x) => x.key === k);
  return { ...state, current, stepIndex };
}
