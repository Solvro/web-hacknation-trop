'use client';
// State machine for one Sprawdź analysis, fed by GET /jobs/{id}/stream (CONTRACTS §4.1).
// The real engine answers in well under a second, so events are *paced* on the client (one bot wakes at a time,
// evidence cards drop in one by one). Pacing only delays real events; it never invents any.
import { useCallback, useEffect, useReducer, useRef, useState } from 'react';
import type { CampaignScore, Decision, Event, EvidenceItem, Finding, JobStep, StepKey } from './contracts';
import { BOTS, prettyEv } from './copy';
import { isOffline } from './api';
import { useEventStream } from './stream';
import { scenarioEvents, scenarioFromJobId } from './mock/jobs';

export interface JobState {
  steps: JobStep[];
  evidence: EvidenceItem[];
  findings: Finding[];
  scores: CampaignScore[];
  decision: Decision | null;
  incidentId: string | null;
  error: { step: string; message: string } | null;
  done: boolean;
  failed: boolean;
  source: 'live' | 'replay' | 'simulated' | null;
  startedAt: number;
}

const initial = (): JobState => ({
  steps: BOTS.map((b) => ({ key: b.step, bot: b.key, label: b.stepName, status: 'pending' as const })),
  evidence: [], findings: [], scores: [], decision: null, incidentId: null, error: null, done: false, failed: false, source: null, startedAt: Date.now(),
});

type Action = { t: 'ev'; ev: Event } | { t: 'src'; src: JobState['source'] } | { t: 'fail' };

function reducer(s: JobState, a: Action): JobState {
  if (a.t === 'fail') return { ...s, failed: true };
  if (a.t === 'src') return { ...s, source: a.src, startedAt: Date.now() };
  const { type, data } = a.ev as { type: string; data: Record<string, unknown> };
  switch (type) {
    case 'job.step': {
      const st = data.step as JobStep;
      return { ...s, steps: s.steps.map((x) => (x.key === st.key ? { ...x, ...st, started_at: st.started_at ?? x.started_at } : x)) };
    }
    case 'job.evidence': {
      const item = prettyEv({ ...(data.item as EvidenceItem) });
      if (!item.bot && data.bot) item.bot = data.bot as EvidenceItem['bot'];
      if (s.evidence.some((e) => e.field === item.field && e.value === item.value)) return s;
      return { ...s, evidence: [...s.evidence, item] };
    }
    case 'job.finding':
      return { ...s, findings: [...s.findings, data.finding as Finding] };
    case 'job.ranking':
      return { ...s, scores: (data.scores as CampaignScore[]) ?? s.scores };
    case 'job.done': {
      const raw = data.decision as Decision;
      const d = raw ? { ...raw, evidence: (raw.evidence ?? []).map(prettyEv) } : raw;
      return { ...s, decision: d, incidentId: (data.incident_id as string) ?? d?.incident_id ?? s.incidentId, done: true, scores: d?.scores?.length ? d.scores : s.scores };
    }
    case 'job.error':
      return { ...s, error: { step: String(data.step ?? ''), message: String(data.message ?? 'Błąd analizy') } };
  }
  return s;
}

/** How long to hold the screen after an event before showing the next one (ms). */
function pace(ev: Event): number {
  const d = ev.data as { step?: JobStep };
  if (ev.type === 'job.step') return d.step?.status === 'run' ? 700 : 350;
  if (ev.type === 'job.evidence') return 160;
  if (ev.type === 'job.ranking') return 300;
  return 0;
}

export function useJob(jobId: string, opts: { replay?: boolean | string; enabled?: boolean } = {}) {
  const [state, dispatch] = useReducer(reducer, undefined, initial);
  const local = scenarioFromJobId(jobId);
  const queue = useRef<Event[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [, kick] = useState(0);

  const drain = useCallback(() => {
    if (timer.current) return;
    const next = () => {
      const ev = queue.current.shift();
      if (!ev) { timer.current = null; return; }
      dispatch({ t: 'ev', ev });
      timer.current = setTimeout(next, pace(ev));
    };
    next();
  }, []);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const onEvent = useCallback((ev: Event) => {
    if (local) { dispatch({ t: 'ev', ev }); return; } // simulated streams are already timed
    queue.current.push(ev);
    drain();
    kick((k) => k + 1);
  }, [drain, local]);
  const onSource = useCallback((src: JobState['source']) => dispatch({ t: 'src', src }), []);
  const onFail = useCallback(() => dispatch({ t: 'fail' }), []);
  useEventStream({
    path: opts.enabled === false ? null : `/jobs/${encodeURIComponent(jobId)}/stream`,
    replay: opts.replay,
    local: !!local || (isOffline() && !opts.replay),
    simulate: () => scenarioEvents(jobId, local ?? 'zamach'),
    onEvent, onSource, onFail,
  });
  const current = state.steps.find((x) => x.status === 'run') ?? null;
  const stepIndex = (k: StepKey) => state.steps.findIndex((x) => x.key === k);
  return { ...state, current, stepIndex };
}
