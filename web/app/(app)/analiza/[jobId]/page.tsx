'use client';
// Boards 2 → 3 → 4 (+ 4a–4d, 11, 12, 13): one route per analysis. /analiza/<jobId> streams the job;
// /analiza/<incident id> opens the report of an existing incident; ?replay=<name> plays a recorded stream.
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useMemo, useState } from 'react';
import type { Campaign, CampaignSummary, Decision, GraphPayload, IncidentSummary } from '@/lib/contracts';
import { isOffline, useApi } from '@/lib/api';
import { plOnly, prettyDisplay } from '@/lib/copy';
import { toMaterial, useArtifacts } from '@/lib/artifacts';
import { useJob } from '@/lib/use-job';
import { JellyRoot } from '@/components/jelly';
import { BotStrip, CapturedPage, FoundList, MaterialBar, Ranking, StatusPill, useElapsed } from '@/components/analysis/live';
import { Report } from '@/components/analysis/report';
import { OutcomeError, OutcomeNew, OutcomeUnsure } from '@/components/analysis/outcomes';
import { FocusView } from '@/components/graph/focus';
import { SCENARIO_INCIDENT, scenarioFromJobId } from '@/lib/mock/jobs';
import { campaignTitle, neighbourhood, normalizePanel, resolveNodeId } from '@/lib/graph';

function useNames() {
  const list = useApi<CampaignSummary[]>('/campaigns').data;
  return useMemo(() => {
    const names: Record<string, string> = {};
    const descs: Record<string, string> = {};
    for (const c of list ?? []) { names[c.id] = `${c.id} ${campaignTitle(c)}`; descs[c.id] = plOnly(c.narrative); }
    return { names, descs };
  }, [list]);
}

function Analysis() {
  const { jobId: raw } = useParams<{ jobId: string }>();
  const jobId = decodeURIComponent(raw);
  const sp = useSearchParams();
  const router = useRouter();
  const replay = sp.get('replay') || undefined;
  // job ids are JOB-…; local-… and demo are the offline / replay ids; anything else is an incident id
  const direct = !/^(JOB-|local-|demo$)/i.test(jobId);
  const view = (sp.get('view') as 'raport' | 'graf' | null) ?? null;
  const focus = sp.get('focus');

  const job = useJob(jobId, { replay, enabled: !direct });
  const { names, descs } = useNames();
  const directDecision = useApi<Decision>(direct ? `/incidents/${encodeURIComponent(jobId)}/decision` : null).data;
  const decision = direct ? directDecision ?? null : job.decision;
  const incidentId = direct ? jobId : (job.incidentId ?? sp.get('inc') ?? (scenarioFromJobId(jobId) ? SCENARIO_INCIDENT[scenarioFromJobId(jobId)!] : null));
  const directError = useApi<Decision>(direct ? `/incidents/${encodeURIComponent(jobId)}/decision` : null).error;
  const art = useArtifacts(incidentId);
  const incidentRaw = useApi<unknown>(incidentId ? `/incidents/${encodeURIComponent(incidentId)}` : null).data;
  const incident = useMemo(() => toMaterial(incidentRaw, incidentId), [incidentRaw, incidentId]);
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
  const input = sp.get('in') ?? (incident as { input?: string } | undefined)?.input ?? incident?.domain ?? incident?.title ?? incidentId ?? 'materiał';

  const setQuery = (patch: Record<string, string | null>) => {
    const q = new URLSearchParams(sp.toString());
    for (const [k, v] of Object.entries(patch)) { if (v == null) q.delete(k); else q.set(k, v); }
    router.replace(`/analiza/${encodeURIComponent(jobId)}?${q}`, { scroll: false });
  };
  // chip / card ids (`ev:<field>:<value>`) are resolved against the real graph before asking for the focus view
  const full = useApi<GraphPayload>(focus && !isOffline() ? '/graph' : null);
  const incList = useApi<IncidentSummary[] | { items: IncidentSummary[] }>(focus && !isOffline() ? '/incidents?limit=1000' : null).data;
  const incById = useMemo(() => new Map((Array.isArray(incList) ? incList : incList?.items ?? []).map((i) => [i.id, i])), [incList]);
  const resolved = !focus ? null : isOffline() ? focus : full.data ? resolveNodeId(full.data, focus, incident?.domain) : null;
  const focusRaw = useApi<GraphPayload>(resolved ? `/graph?focus=${encodeURIComponent(resolved)}&origin=${encodeURIComponent(decision?.incident_id ?? '')}` : null);
  const focusData = useMemo(() => {
    if (!focus) return { data: undefined, error: undefined };
    if (full.data && !resolved) return { data: undefined, error: new Error('not in graph') };
    if (full.error) return { data: undefined, error: full.error };
    const origin = decision?.incident_id ?? '';
    let g = focusRaw.data;
    if (!g) return { data: undefined, error: focusRaw.error };
    if (!g.nodes?.length) return { data: undefined, error: new Error('empty') };
    if (!g.focus || g.nodes.length > 9) g = neighbourhood(g, resolved!, origin) ?? g;
    if (origin && !g.nodes.some((n) => n.id === origin)) g = { ...g, nodes: [{ id: origin, kind: 'incident', label: origin, meta: { sub: 'ten materiał', thumb: true } }, ...g.nodes] };
    const nodes = g.nodes.map((n) => ({ ...n, label: prettyDisplay(n.label), meta: { ...(n.meta ?? {}), title: n.kind === 'incident' ? ((n.id === origin ? incident?.title : null) ?? incById.get(n.id)?.title ?? incById.get(n.id)?.domain ?? undefined) : undefined, sub: (n.meta as { sub?: string } | undefined)?.sub === 'incydent' ? 'materiał' : (n.meta as { sub?: string } | undefined)?.sub } }));
    const center = nodes.find((n) => n.id === resolved);
    const panel = normalizePanel(g.panel as Record<string, unknown>, center);
    panel.title = prettyDisplay(panel.title); panel.description = prettyDisplay(panel.description); panel.bot_text = prettyDisplay(panel.bot_text);
    return { data: { ...g, nodes, focus: resolved, panel: panel as Record<string, unknown> }, error: undefined };
  }, [focus, resolved, full.data, full.error, focusRaw.data, focusRaw.error, decision?.incident_id, incById, incident?.title]);

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
          focusData.data ? <FocusView data={focusData.data} originId={decision.incident_id} originThumb={art.any} onFocus={(id) => setQuery({ focus: id })} onBack={() => setQuery({ focus: null })} />
            : focusData.error ? (
              <div className="rounded-[22px] border border-dashed border-line2 bg-bg2 p-8 text-center flex flex-col items-center gap-2">
                <b className="text-[16px]">Ten ślad nie ma jeszcze własnego widoku w grafie</b>
                <span className="text-[14px] text-tx3 max-w-[520px]">Graf pokazuje materiały, kampanie, domeny i najważniejsze ślady techniczne. Ten ślad liczy się do wyniku, ale nie jest osobnym węzłem.</span>
                <button type="button" className="btn-sec btn-sm mt-2" onClick={() => setQuery({ focus: null })}>Wróć do grafu</button>
              </div>
            )
              : <div className="h-[420px] flex items-center justify-center"><span className="spin" /></div>
        ) : undefined}
      />
    );
  }
  if (direct && directError) {
    return (
      <main className="flex-1 flex flex-col items-center justify-center gap-3 px-6 py-24 text-center">
        <h1 className="text-[28px] font-semibold tracking-[-0.03em]">Nie znamy materiału {jobId}</h1>
        <p className="text-[15px] text-tx2 max-w-[520px]">Może został usunięty albo link jest niepełny. Sprawdź materiał jeszcze raz albo wybierz go z listy kampanii.</p>
        <a href="/" className="btn-pri mt-2">Sprawdź materiał</a>
      </main>
    );
  }
  if (direct) return <main className="flex-1 flex items-center justify-center" role="status" aria-label="Ładowanie raportu"><span className="spin" /></main>;
  if (job.failed && !job.steps.some((x) => x.status !== 'pending')) {
    return (
      <main className="flex-1 flex flex-col items-center justify-center gap-3 px-6 py-24 text-center">
        <h1 className="text-[28px] font-semibold tracking-[-0.03em]">Nie udało się połączyć z analizą</h1>
        <p className="text-[15px] text-tx2 max-w-[520px]">Serwer nie odpowiada albo ta analiza już wygasła. Spróbuj jeszcze raz za chwilę.</p>
        <div className="flex gap-2 mt-2"><button type="button" className="btn-sec" onClick={() => location.reload()}>Spróbuj ponownie</button><a href="/" className="btn-pri">Nowe sprawdzenie</a></div>
      </main>
    );
  }

  const capture = job.steps.find((s) => s.key === 'capture');
  const compare = job.steps.find((s) => s.key === 'compare');
  const topScore = [...job.scores].sort((a, b) => (b.p ?? 0) - (a.p ?? 0))[0];
  const joined = compare && compare.status !== 'run' && compare.status !== 'pending' && topScore && (topScore.p ?? 0) >= 0.5 ? topScore.campaign_id : null;
  // never re-fill a masked template ({PER}): only the page's own h1 / title as captured, original casing
  const headline = incident?.h1 || incident?.title || null;
  // evidence outlines: the render's own boxes, else the bboxes the bots reported in job.finding
  const KIND: Record<string, string> = { content: 'headline', kit: 'form', tracking: 'tracking', persons: 'face', visual: 'logo', infra: 'domain' };
  const shot = art.landing && !art.landing.boxes.length
    ? { ...art.landing, boxes: job.findings.filter((f) => f.bbox?.length === 4).map((f) => ({ kind: KIND[f.evidence.type] ?? 'headline', x: f.bbox![0], y: f.bbox![1], w: f.bbox![2], h: f.bbox![3], text: f.evidence.display })) }
    : art.landing;

  return (
    <main className="relative z-[1] w-full max-w-[1240px] mx-auto px-4 sm:px-6 pt-[22px] pb-8 box-border flex flex-col gap-4">
      <MaterialBar
        input={input} incidentId={incidentId} thumb={art.ad} note={(incident as { note?: string } | undefined)?.note}
        status={<StatusPill live={!job.done} text={`${job.done ? 'Raport gotowy' : job.error ? 'Problem ze stroną' : 'Analiza trwa'} · ${job.done && total ? (total / 1000).toFixed(1).replace('.', ',') : elapsed.toFixed(1).replace('.', ',')} s${job.source === 'replay' ? ' · nagranie' : job.source === 'simulated' ? ' · demo offline' : ''}`} />}
        onCancel={() => router.push('/')}
      />
      <BotStrip steps={job.steps} />
      <div className="grid grid-cols-1 lg:grid-cols-[300px_minmax(0,1fr)_280px] xl:grid-cols-[340px_minmax(0,1fr)_300px] gap-5 items-start">
        <section aria-labelledby="an-page">
          <div className="colh"><h2 id="an-page">Strona po przechwyceniu</h2></div>
          <CapturedPage shot={shot} url={input} headline={headline} evidence={job.evidence} captureNote={capture?.detail ?? null} capturing={!capture || capture.status === 'pending' || capture.status === 'run'} failed={capture?.status === 'error'} />
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
