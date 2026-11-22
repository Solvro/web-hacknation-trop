'use client';
// Other Sprawdź outcomes: board 11 (new campaign), 12 (uncertain), 13 (page does not respond).
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import type { CampaignSummary, Decision, EvidenceItem, JobStep, LinkExplanation } from '@/lib/contracts';
import { restoreTemplateCase, useArtifacts, type Material } from '@/lib/artifacts';
import { botColor, botName, LAYER_LABEL, n, p2, plOnly, plural, prettyDisplay } from "@/lib/copy";
import { apiPost, useApi } from '@/lib/api';
import { campaignTitle } from '@/lib/graph';
import { Bot } from '../jelly';
import { IArrow, ICheck } from '../icons';
import { MaterialImages, MaterialStrip, ReportHeader, hasImages } from './report';
import { FollowButton } from '../follow-button';

/** The material itself: title strip + its real page / ad images (nothing drawn when the API has none). */
function MaterialBlock({ incident, incidentId }: { incident?: Material | null; incidentId?: string | null }) {
  const art = useArtifacts(incidentId);
  if (!incidentId) return null;
  return (
    <div className="flex flex-col gap-4">
      <div className="-mt-5"><MaterialStrip incident={incident} incidentId={incidentId} art={art} /></div>
      {hasImages(art) && <div className="max-w-[760px]"><MaterialImages art={art} url={incident?.domain ?? incidentId} height={420} adMax="max-h-[220px]" /></div>}
    </div>
  );
}

function FollowRow(p: { incidentId?: string | null; evidence: import('@/lib/contracts').EvidenceItem[]; domain?: string | null }) {
  return <div className="pt-5 border-t border-bg4 flex flex-wrap items-center gap-2"><FollowButton variant="sec" {...p} /></div>;
}

function Row({ e, badge, tone = 'cyan', dashed }: { e: { bot?: string | null; title: string; meta: string }; badge?: string; tone?: 'cyan' | 'g' | 'red' | 'neutral'; dashed?: boolean }) {
  const T = { cyan: 'bg-state-cdim text-state-cyan', g: 'bg-state-gdim text-state-g', red: 'bg-state-rdim text-state-red', neutral: 'bg-bg3 text-tx2' }[tone];
  return (
    <div className={'min-h-16 flex items-center gap-3 pl-3.5 pr-4 py-2.5 border rounded-[18px] ' + (dashed ? 'border-dashed border-line1 bg-bg2' : 'border-line1 bg-bg1 shadow-soft')}>
      <Bot color={botColor(e.bot)} size={34} state={dashed ? 'asleep' : 'awake'} />
      <span className="flex-1 min-w-0 flex flex-col gap-0.5">
        <span className={'text-[15px] font-semibold tracking-[-0.01em] break-words line-clamp-2 ' + (dashed ? 'text-tx2' : '')} title={e.title}>{e.title}</span>
        <span className="text-[12.5px] text-tx3">{e.meta}</span>
      </span>
      {badge && <span className={'pill flex-none whitespace-nowrap ' + T}>{badge}</span>}
    </div>
  );
}

const meta = (e: EvidenceItem, extra?: string) => [botName(e.bot), LAYER_LABEL[e.type].toLowerCase(), extra].filter(Boolean).join(' · ');

// ------------------------------------------------------------------------------------------- 11 · Nowa
export function OutcomeNew({ d, incident, names }: { d: Decision; incident?: Material | null; names: Record<string, string> }) {
  const router = useRouter();
  const cand = d.candidate_campaign_id ?? '';
  const c = useApi<CampaignSummary>(cand ? `/campaigns/${encodeURIComponent(cand)}` : null).data;
  const [name, setName] = useState('');
  // the verdict is "new": the nearest campaign is NOT this material's campaign, so neither its name nor its headline is used
  const shown = name.trim() || incident?.title || 'Nowa kampania';
  const noSignals = (d as Decision & { signals?: string | null }).signals === 'none';
  const total = useApi<CampaignSummary[]>('/campaigns').data;
  const [busy, setBusy] = useState(false);
  async function create() {
    setBusy(true);
    const r = await apiPost<{ id: string }>('/campaigns', { seed_incident: d.incident_id, name: shown, status: 'candidate' }, () => ({ id: cand })).catch(() => ({ id: cand }));
    // (if the API refuses, we still go to the candidate campaign page; nothing fictional is shown)
    router.push(r.id || cand ? `/kampanie/${encodeURIComponent(r.id || cand)}` : '/kampanie');
  }
  const badge = (e: EvidenceItem) => (e.state === 'missing' ? undefined : (e.df ?? 0) <= 1 ? (e.type === 'infra' ? 'nowa' : 'nowy') : plural(e.df ?? 0, 'podobny', 'podobne', 'podobnych'));
  return (
    <main className="w-full max-w-[1240px] mx-auto px-4 sm:px-6 pt-[30px] pb-8 flex flex-col gap-6">
      <ReportHeader
        title={incident?.title || (noSignals ? 'Nie pasuje do żadnej znanej kampanii' : 'Nowa kampania')}
        lead={noSignals ? 'Nie pasuje do żadnej znanej kampanii i nie ma typowych śladów oszustwa.' : undefined}
        primary={noSignals ? undefined : <button type="button" className="btn-pri" onClick={create} disabled={busy}>Załóż nową kampanię<IArrow /></button>}
        secondary={noSignals ? undefined : <Link className="lnk" href="/kampanie">albo przypisz do istniejącej</Link>}
      />
      <MaterialBlock incident={incident} incidentId={d.incident_id} />
      {!noSignals && <section className="rounded-[22px] border border-[#BFDBFE] bg-state-cdim px-5 py-5 flex flex-wrap gap-5 items-center justify-between">
        <div className="flex-[1_1_480px]">
          <h2 className="text-[17px] font-semibold">{total?.length ? `Nie pasuje do żadnej z ${n(total.length)} kampanii` : 'Nie pasuje do żadnej znanej kampanii'}</h2>
          <p className="text-[14px] text-state-cyan pt-1">Ślady są nowe: żadna znana kampania nie ma ich w tym zestawie. To najpewniej początek nowej kampanii.{d.same_operator_as ? ` Ten sam operator co ${d.same_operator_as}.` : ''}</p>
        </div>
        <label className="flex flex-col gap-1.5 flex-[0_1_340px]">
          <span className="text-[13px] font-medium text-state-cyan">Nazwa nowej kampanii</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="np. Fałszywy wywiad o leku na stawy" className="h-12 px-3.5 rounded-xl border border-[#BFDBFE] bg-white text-[15px] placeholder:text-tx4" />
        </label>
      </section>}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_440px] gap-10 items-start">
        <section className="flex flex-col gap-3" aria-labelledby="nw-found">
          <h2 id="nw-found" className="text-[13px] font-medium text-tx3">Co znalazły boty</h2>
          {(d.evidence ?? []).map((e) => restoreTemplateCase(e, incident)).map((e, i) => (
            <Row key={i} e={{ bot: e.bot, title: prettyDisplay(e.display), meta: meta(e, e.state === 'missing' ? 'osoby i marki' : (e.df ?? 0) <= 1 ? 'nie ma go w bazie' : plural(e.df ?? 0, 'podobny materiał', 'podobne materiały', 'podobnych materiałów')) }} badge={badge(e)} dashed={e.state === 'missing'} />
          ))}
        </section>
        <section className="card !rounded-[22px] p-5" aria-labelledby="nw-near">
          <h2 id="nw-near" className="text-[17px] font-semibold">Najbliższe kampanie</h2>
          <p className="text-[13px] text-tx3 pb-2">Żeby dołączyć, potrzeba co najmniej 0.80.</p>
          {[...(d.scores ?? [])].sort((a, b) => (b.p ?? 0) - (a.p ?? 0)).slice(0, 3).map((s) => (
            <div key={s.campaign_id} className="py-2.5 border-b border-bg4 last:border-0 flex flex-col gap-1.5">
              <span className="flex justify-between text-[14px]"><Link href={`/kampanie/${s.campaign_id}`} className="hover:underline">{names[s.campaign_id] ?? s.campaign_id}</Link><b className="font-mono text-[13px]">{p2(s.p)}</b></span>
              <span className="block h-2 rounded-full bg-bg4 overflow-hidden"><i className="block h-full rounded-full bg-line3" style={{ width: `${Math.round((s.p ?? 0) * 100)}%` }} /></span>
            </div>
          ))}
        </section>
      </div>
      <FollowRow incidentId={d.incident_id} evidence={d.evidence ?? []} domain={incident?.domain} />
    </main>
  );
}

// ------------------------------------------------------------------------------------------- 12 · Niepewne
function CandidateCard({ incidentId, s, names, desc }: { incidentId: string; s: { campaign_id: string; p?: number }; names: Record<string, string>; desc?: string }) {
  const link = useApi<LinkExplanation>(`/links/${encodeURIComponent(incidentId)}/${encodeURIComponent(s.campaign_id)}`).data;
  const [chosen, setChosen] = useState(false);
  async function choose() {
    setChosen(true);
    await apiPost(`/triage`, { source: 'sprawdz', subject_id: incidentId, decision: { action: 'accept', campaign_id: s.campaign_id } }, () => ({ ok: true })).catch(() => null);
  }
  return (
    <article className="card !rounded-[22px] p-5 flex flex-col gap-3">
      <div className="flex justify-between gap-3">
        <div><h2 className="text-[19px] font-semibold tracking-[-0.02em]">{names[s.campaign_id] ?? s.campaign_id}</h2>{desc && <p className="text-[13px] text-tx3">{desc}</p>}</div>
        <b className="font-mono text-[26px] font-semibold">{p2(s.p)}</b>
      </div>
      <div>
        <h3 className="text-[12.5px] text-tx3 pb-1">Co pasuje</h3>
        <ul className="m-0 p-0 list-none flex flex-col gap-1.5">
          {(link?.evidence ?? []).map((e, i) => <li key={i} className="flex items-center gap-2.5 text-[14px]"><span className="w-5 h-5 rounded-full bg-state-gdim text-state-g inline-flex items-center justify-center"><ICheck width={10} height={10} /></span>{prettyDisplay(e.display)}</li>)}
          {!link && <li className="text-[13px] text-tx4">Archiwista porównuje…</li>}
        </ul>
      </div>
      {(link?.missing?.length ?? 0) > 0 && (
        <div>
          <h3 className="text-[12.5px] text-tx3 pb-1">Czego nie wiadomo</h3>
          <ul className="m-0 p-0 list-none flex flex-col gap-1.5">
            {(link?.missing ?? []).map((e, i) => <li key={i} className="flex items-center gap-2.5 text-[14px]"><span className="w-5 h-5 rounded-full bg-bg3 text-tx4 inline-flex items-center justify-center">–</span>{prettyDisplay(e.display)}</li>)}
          </ul>
        </div>
      )}
      <button type="button" onClick={choose} aria-pressed={chosen} className={'mt-1 min-h-[46px] rounded-field border-[1.5px] text-[15px] font-semibold ' + (chosen ? 'bg-tx1 text-white border-tx1' : 'border-tx1 hover:bg-bg3')}>
        {chosen ? `Zapisane: to ${s.campaign_id}` : `To ${s.campaign_id}`}
      </button>
    </article>
  );
}

export function OutcomeUnsure({ d, incident, names, descs }: { d: Decision; incident?: Material | null; names: Record<string, string>; descs: Record<string, string> }) {
  const top = [...(d.scores ?? [])].sort((a, b) => (b.p ?? 0) - (a.p ?? 0)).slice(0, 2);
  return (
    <main className="w-full max-w-[1240px] mx-auto px-4 sm:px-6 pt-[30px] pb-8 flex flex-col gap-6">
      <ReportHeader
        title={d.runner_up?.same_operator ? 'Pasuje do dwóch kampanii jednego operatora' : 'Pasuje do dwóch kampanii'}
        lead={`Ślady techniczne pasują do obu kampanii${d.operator_id ? ` operatora ${d.operator_id}` : ''}.${(d.evidence ?? []).some((e) => e.state === 'missing' && (e.type === 'content' || e.type === 'persons')) ? ' Strona nie ma tekstu ani twarzy, więc boty nie rozstrzygną tego same.' : ' Różnica jest za mała, żeby boty rozstrzygnęły to same.'} Wybierz kampanię.`}
        secondary={<Link className="lnk" href="/kampanie">albo załóż nową kampanię</Link>}
      />
      <MaterialBlock incident={incident} incidentId={d.incident_id} />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {top.map((s) => <CandidateCard key={s.campaign_id} incidentId={d.incident_id} s={s} names={names} desc={descs[s.campaign_id]} />)}
      </div>
      <section className="rounded-[22px] bg-bg3 px-5 py-4 flex flex-wrap items-center gap-4">
        <Bot color="#14B8A6" size={34} />
        <div className="flex-1 min-w-[240px]">
          <h2 className="text-[15px] font-semibold">Wrzuć zrzut reklamy, a rozstrzygniemy sami</h2>
          <p className="text-[13px] text-tx2">Czytelnik przeczyta tekst i rozpozna twarz. Przy tych dwóch kampaniach to zwykle wystarcza.</p>
        </div>
        <Link href="/" className="btn-sec btn-sm !min-h-[44px]">Dodaj zrzut ekranu</Link>
      </section>
      <FollowRow incidentId={d.incident_id} evidence={d.evidence ?? []} domain={incident?.domain} />
    </main>
  );
}

// ------------------------------------------------------------------------------------------- 13 · Błąd
export function OutcomeError({ d, incident, steps, error, names }: { d: Decision | null; incident?: Material | null; steps: JobStep[]; error: { message: string } | null; names: Record<string, string> }) {
  const cand = d?.candidate_campaign_id ?? d?.campaign_id;
  const failed = steps.filter((s) => s.status === 'error' || s.status === 'skip');
  return (
    <main className="w-full max-w-[1240px] mx-auto px-4 sm:px-6 pt-[30px] pb-8 flex flex-col gap-6">
      <ReportHeader
        title={error ? 'Strona nie odpowiada' : 'Za mało materiału, żeby przypisać kampanię'}
        lead={error?.message ?? 'Boty ustaliły tylko część śladów. Bez strony docelowej albo zrzutu reklamy nie potwierdzą kampanii, więc materiał nie zostanie do niej dołączony. Dodaj więcej materiału albo puść agenta po śladach, które są.'}
        secondary={<Link className="lnk" href="/">albo wrzuć zrzut ekranu reklamy</Link>}
      />
      <MaterialBlock incident={incident} incidentId={d?.incident_id ?? incident?.id} />
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_400px] gap-10 items-start">
        <section className="flex flex-col gap-3" aria-labelledby="er-found">
          <h2 id="er-found" className="text-[13px] font-medium text-tx3">Co udało się ustalić</h2>
          {(d?.evidence ?? []).map((e) => restoreTemplateCase(e, incident)).map((e, i) => <Row key={i} e={{ bot: e.bot, title: prettyDisplay(e.display), meta: [botName(e.bot), e.bot === 'archiwista' ? 'nasza baza' : 'z rejestru i crt.sh, bez strony'].join(' · ') }} badge="ustalone" tone="g" />)}
          {!(d?.evidence ?? []).length && !failed.length && <p className="text-[14px] text-tx3 py-2">Boty nie znalazły w tym materiale śladów, które łączą go z bazą: brak strony docelowej, pikseli i domen.</p>}
          {failed.map((s) => (
            <Row key={s.key} dashed e={{ bot: s.bot, title: s.status === 'error' ? `Strona: ${(s.detail ?? '').split('\n')[0]}` : `${s.label.split('·').pop()?.trim() ?? s.label}`, meta: `${botName(s.bot)} · ${(s.detail ?? '').split('\n')[0]}` }}
              badge={s.status === 'error' ? 'nie udało się' : 'brak'} tone={s.status === 'error' ? 'red' : 'neutral'} />
          ))}
        </section>
        <div className="flex flex-col gap-4">
          {cand && (
            <section className="card !rounded-[22px] p-5">
              <span className="text-[13px] text-tx3">Wstępnie</span>
              <h2 className="text-[17px] font-semibold">Najpewniej {names[cand] ?? cand}</h2>
              <p className="text-[13.5px] text-tx2 pt-1">Domena i jej historia wskazują na tę kampanię, ale bez strony tego nie potwierdzimy i nie dołączymy materiału.</p>
            </section>
          )}
          <section className="card !rounded-[22px] p-5">
            <h2 className="text-[17px] font-semibold pb-2">Czym jeszcze możemy sprawdzić</h2>
            {[['Kopia z archiwum', 'Wayback może mieć zapis strony', 'sprawdź'], ['Zrzut ekranu reklamy', 'Czytelnik przeczyta tekst i twarz', 'wrzuć plik'], ['Plik HAR', 'jeśli zapisałeś ruch strony wcześniej', 'wrzuć plik']].map(([a, b, c]) => (
              <div key={a} className="flex items-center justify-between gap-3 py-2.5 border-b border-bg4 last:border-0">
                <span><b className="block text-[14px] font-semibold text-tx2">{a}</b><span className="text-[12.5px] text-tx3">{b}</span></span>
                {c === 'sprawdź' ? <a href={`https://web.archive.org/web/*/${incident?.domain ?? ''}`} target="_blank" rel="noopener noreferrer nofollow" className="text-[12.5px] text-tx3 hover:text-tx1">{c}</a> : <Link href="/" className="text-[12.5px] text-tx3 hover:text-tx1">{c}</Link>}
              </div>
            ))}
          </section>
        </div>
      </div>
      <FollowRow incidentId={d?.incident_id ?? incident?.id} evidence={d?.evidence ?? []} domain={incident?.domain} />
    </main>
  );
}

export { n };
