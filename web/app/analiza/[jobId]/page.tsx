'use client';
// Boards 2 → 3 → 4 (+ 4a–4d, 11, 12, 13): one route per analysis. /analiza/<jobId> streams the job;
// /analiza/INC-… opens the report of an existing incident; ?replay=demo plays the recorded stream.
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useMemo, useState } from 'react';
import type { Campaign, CampaignSummary, Decision, GraphPayload, IncidentSummary } from '@/lib/contracts';
import { useApi } from '@/lib/api';
import { useJob } from '@/lib/use-job';
import { JellyRoot } from '@/components/jelly';
import { BotStrip, CapturedPage, FoundList, MaterialBar, Ranking, StatusPill, useElapsed } from '@/components/analysis/live';
import { Report } from '@/components/analysis/report';
import { OutcomeError, OutcomeNew, OutcomeUnsure } from '@/components/analysis/outcomes';
import { FocusView } from '@/components/graph/focus';
import { SCENARIO_INCIDENT, scenarioFromJobId } from '@/lib/mock/jobs';
import { INCIDENTS } from '@/lib/mock/universe';
import { campaignTitle, neighbourhood, normalizePanel } from '@/lib/graph';
import { resolveGet } from '@/lib/mock/router';

function useNames() {
  const list = useApi<CampaignSummary[]>('/campaigns').data;
  return useMemo(() => {
    const names: Record<string, string> = {};
    const descs: Record<string, string> = {};
    for (const c of list ?? []) { names[c.id] = `${c.id} ${campaignTitle(c)}`; descs[c.id] = c.narrative ?? ''; }
    return { names, descs };
  }, [list]);
}

function Analysis() {
  const { jobId: raw } = useParams<{ jobId: string }>();
  const jobId = decodeURIComponent(raw);
  const sp = useSearchParams();
  const router = useRouter();
  const replay = sp.get('replay') === 'demo';
  const direct = /^INC-/i.test(jobId);
  const view = (sp.get('view') as 'raport' | 'graf' | null) ?? null;
  const focus = sp.get('focus');

  const job = useJob(jobId, { replay, enabled: !direct });
  const { names, descs } = useNames();
  const directDecision = useApi<Decision>(direct ? `/incidents/${encodeURIComponent(jobId)}/decision` : null).data;
  const decision = direct ? directDecision ?? null : job.decision;
  const incidentId = direct ? jobId : (job.incidentId ?? sp.get('inc') ?? (scenarioFromJobId(jobId) ? SCENARIO_INCIDENT[scenarioFromJobId(jobId)!] : null));
  const incident = useApi<IncidentSummary>(incidentId ? `/incidents/${encodeURIComponent(incidentId)}` : null).data;
  const cid = decision?.campaign_id ?? decision?.candidate_campaign_id ?? null;
  const campaign = useApi<Campaign>(cid ? `/campaigns/${encodeURIComponent(cid)}` : null).data;

  // Analiza → Raport 900 ms after job.done (as on the prototype board)
  const [shown, setShown] = useState(direct);
  useEffect(() => {
    if (direct || !job.done) return;
    const t = setTimeout(() => setShown(true), 900);
    return () => clearTimeout(t);
  }, [job.done, direct]);

  const elapsed = useElapsed(job.startedAt, job.done || direct);
  const total = job.steps.reduce((a, s) => a + (s.duration_ms ?? 0), 0);
  const input = sp.get('in') ?? (incident as { input?: string } | undefined)?.input ?? INCIDENTS[incidentId ?? '']?.input ?? incident?.domain ?? jobId;

  const setQuery = (patch: Record<string, string | null>) => {
    const q = new URLSearchParams(sp.toString());
    for (const [k, v] of Object.entries(patch)) { if (v == null) q.delete(k); else q.set(k, v); }
    router.replace(`/analiza/${encodeURIComponent(jobId)}?${q}`, { scroll: false });
  };
  const focusRaw = useApi<GraphPayload>(focus ? `/graph?focus=${encodeURIComponent(focus)}&origin=${encodeURIComponent(decision?.incident_id ?? '')}` : null);
  const focusData = useMemo(() => {
    if (!focus) return { data: undefined, error: undefined };
    const origin = decision?.incident_id ?? 'INC-24817';
    let g = focusRaw.data;
    // API answered with nothing useful → offline fixture for the same node, if we have one
    // …or when the API's panel is the generic one (no description) and a board-quality fixture exists for this node
    // (see CONTRACT-REQUEST.md: WS2 should serve these panels itself).
    const fx = (focusRaw.data || focusRaw.error) ? resolveGet('graph', new URLSearchParams({ focus, origin })) as GraphPayload | undefined : undefined;
    if (fx && (!g || !g.nodes?.length || !(g.panel as { description?: string } | null)?.description)) g = fx;
    if (!g) return { data: undefined, error: focusRaw.error ?? (focusRaw.data ? new Error('empty') : undefined) };
    if (!g.focus || g.nodes.length > 9) g = neighbourhood(g, focus, origin) ?? g;
    const center = g.nodes.find((n) => n.id === focus);
    return { data: { ...g, focus, panel: normalizePanel(g.panel as Record<string, unknown>, center) as Record<string, unknown> }, error: undefined };
  }, [focus, focusRaw.data, focusRaw.error, decision?.incident_id]);

  const reportReady = shown && decision;
  const outcome = !decision ? null : job.error || decision.decision === 'insufficient' ? 'error' : decision.decision === 'new' ? 'new' : decision.decision === 'ambiguous' ? 'unsure' : 'report';

  if (reportReady && outcome === 'new') return <OutcomeNew d={decision} incident={incident} names={names} />;
  if (reportReady && outcome === 'unsure') return <OutcomeUnsure d={decision} incident={incident} names={names} descs={descs} />;
  if (reportReady && outcome === 'error') return <OutcomeError d={decision} incident={incident} steps={job.steps} error={job.error} names={names} />;
  if (reportReady && outcome === 'report') {
    return (
      <Report
        decision={decision} campaign={campaign} incident={incident} steps={direct ? undefined : job.steps} names={names}
        view={view ?? (focus ? 'graf' : 'raport')}
        onView={(v) => setQuery({ view: v, focus: v === 'raport' ? null : focus })}
        onFocus={(id) => setQuery({ view: 'graf', focus: id })}
        focusView={focus ? (
          focusData.data ? <FocusView data={focusData.data} originId={decision.incident_id} onFocus={(id) => setQuery({ focus: id })} onBack={() => setQuery({ focus: null })} />
            : focusData.error ? <div className="text-[14px] text-tx3">Ten węzeł nie ma jeszcze widoku. <button type="button" className="underline" onClick={() => setQuery({ focus: null })}>Wróć do grafu</button></div>
              : <div className="h-[420px] flex items-center justify-center"><span className="spin" /></div>
        ) : undefined}
      />
    );
  }
  if (direct) return <main className="flex-1 flex items-center justify-center"><span className="spin" /></main>;

  const capture = job.steps.find((s) => s.key === 'capture');
  const compare = job.steps.find((s) => s.key === 'compare');
  const topScore = [...job.scores].sort((a, b) => (b.p ?? 0) - (a.p ?? 0))[0];
  const joined = compare && compare.status !== 'run' && compare.status !== 'pending' && topScore && (topScore.p ?? 0) >= 0.5 ? topScore.campaign_id : null;
  const headline = job.evidence.find((e) => e.type === 'content' && e.state !== 'missing')?.value?.replace('{PER}', 'Jan Kowalski');

  return (
    <main className="relative z-[1] w-full max-w-[1240px] mx-auto px-4 sm:px-6 pt-[22px] pb-8 box-border flex flex-col gap-4">
      <MaterialBar
        input={input} incidentId={incidentId} note={(incident as { note?: string } | undefined)?.note}
        status={<StatusPill live={!job.done} text={`${job.done ? 'Raport gotowy' : job.error ? 'Problem ze stroną' : 'Analiza trwa'} · ${job.done && total ? (total / 1000).toFixed(1).replace('.', ',') : elapsed.toFixed(1).replace('.', ',')} s${job.source === 'replay' ? ' · nagranie' : job.source === 'simulated' ? ' · demo' : ''}`} />}
        onCancel={() => router.push('/')}
      />
      <BotStrip steps={job.steps} />
      <div className="grid grid-cols-1 lg:grid-cols-[300px_minmax(0,1fr)_280px] xl:grid-cols-[340px_minmax(0,1fr)_300px] gap-5 items-start">
        <section aria-labelledby="an-page">
          <div className="colh"><h2 id="an-page">Strona po przechwyceniu</h2></div>
          <CapturedPage url={input} headline={headline} evidence={job.evidence} capturing={!capture || capture.status === 'pending' || capture.status === 'run'} failed={capture?.status === 'error'} />
        </section>
        <FoundList state={job} />
        <Ranking scores={job.scores} names={names} evidence={job.evidence} joined={joined} />
      </div>
    </main>
  );
}

export default function Page() {
  return (
    <JellyRoot mode="plain" className="flex-1 flex flex-col">
      <Suspense fallback={<main className="flex-1" />}>
        <Analysis />
      </Suspense>
    </JellyRoot>
  );
}
