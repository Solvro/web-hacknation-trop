'use client';
// Boards 3 (Raport) and 4 (Graf): the same finding cards move from a list into a graph.
import Link from 'next/link';
import { useMemo, useState } from 'react';
import type { Campaign, Decision, EvidenceItem, GraphPayload, IncidentSummary, JobStep } from '@/lib/contracts';
import { prettyEv, BOT_BY_KEY, BOT_BY_STEP, LAYER_LABEL, botColor, botName, evidenceMeta, evidenceSentence, n, p2, secs, w1 } from '@/lib/copy';
import { apiPost, useApi } from '@/lib/api';
import { campaignTitle, focusIdOf as fid } from '@/lib/graph';
import { Bot } from '../jelly';
import { EvidenceChip } from '../evidence-chip';
import { GraphCloud } from '../graph/cloud';
import { IArrow, ICheck, IChev, IGraph, IList } from '../icons';

export function storyOf(c?: Campaign | null): { h1: string; p: string } {
  const d = c?.description ?? '';
  if (d.includes('\n')) { const [h1, ...rest] = d.split('\n'); return { h1, p: rest.join(' ') }; }
  // real mode: Polish descriptive name, English engine narrative → headline from the name, no English lead
  const pl = (t: string) => /[ąćęłńóśźż]|\b(i|w|z|na|do|się|nie|przez)\b/i.test(t);
  const narrative = (c?.narrative ?? '').replace(/\.$/, '');
  if (narrative && pl(narrative)) return { h1: narrative, p: d && d !== c?.narrative && pl(d) ? d : '' };
  return { h1: c?.name ?? narrative, p: d && pl(d) && d !== c?.name ? d : '' };
}

export function ReportHeader({ title, lead, meta, primary, secondary }: { title: string; lead?: string; meta: string; primary?: React.ReactNode; secondary?: React.ReactNode }) {
  return (
    <section aria-labelledby="rp-verdict" className="flex flex-wrap items-end justify-between gap-x-7 gap-y-5">
      <div className="flex-[1_1_560px] min-w-0 flex flex-col gap-2.5">
        <h1 id="rp-verdict" className="m-0 text-[30px] sm:text-[42px] leading-[1.05] tracking-[-0.04em] font-semibold">{title}</h1>
        {lead && <p className="m-0 max-w-[720px] text-[17px] leading-normal text-tx2">{lead}</p>}
        <span className="font-mono text-[12.5px] text-tx4 break-words">{meta}</span>
      </div>
      {(primary || secondary) && <div className="flex flex-col items-start sm:items-end gap-1">{primary}{secondary}</div>}
    </section>
  );
}

const SHORT: (e: EvidenceItem) => string = (e) => (e.state === 'zero' ? `${e.display} · pominięty` : e.display);

function FindCard({ e, graph, onClick }: { e: EvidenceItem; graph: boolean; onClick?: () => void }) {
  const zero = e.state === 'zero';
  const cls = 'w-full h-16 flex items-center gap-3 pl-3.5 pr-4 border rounded-[18px] text-left ' +
    (zero ? 'border-dashed border-line1 bg-bg2' : 'border-line1 bg-bg1 shadow-soft') + (onClick ? ' hover:border-line3 transition-colors' : '');
  const inner = (
    <>
      <Bot color={botColor(e.bot)} master={e.bot === 'sedzia'} size={34} />
      <span className="flex-1 min-w-0 flex flex-col gap-0.5">
        {graph
          ? <><span className="font-mono text-[13px] font-medium truncate">{SHORT(e)}</span><span className="text-[12.5px] text-tx3 truncate">{botName(e.bot)}</span></>
          : <><span className={'text-[15px] font-semibold tracking-[-0.01em] truncate ' + (zero ? 'text-tx3' : '')}>{evidenceSentence(e)}</span><span className="text-[12.5px] text-tx3 truncate">{evidenceMeta(e)}</span></>}
      </span>
      <b className={'flex-none font-mono text-[15px] font-semibold ' + (zero ? 'text-line3' : '')}>{w1(e.weight)}</b>
    </>
  );
  return onClick ? <button type="button" className={cls} onClick={onClick} aria-label={`${evidenceSentence(e)}: rozwiń w grafie`}>{inner}</button> : <div className={cls}>{inner}</div>;
}

function Feedback({ incidentId }: { incidentId: string }) {
  const [sent, setSent] = useState<string | null>(null);
  const opts = ['Tak', 'Inna kampania', 'Nowa kampania', 'To nie oszustwo'];
  async function send(v: string) {
    setSent(v);
    await apiPost('/feedback', { incident_id: incidentId, verdict_ok: v === 'Tak', correction: v === 'Tak' ? null : v }, () => ({ ok: true })).catch(() => null);
  }
  return (
    <div role="group" aria-label="Ocena werdyktu" className="flex flex-wrap items-center gap-1.5">
      <span className="text-[14px] font-semibold mr-1.5">Werdykt trafny?</span>
      {opts.map((o) => <button key={o} type="button" className="chip" aria-pressed={sent === o} onClick={() => send(o)}>{o}</button>)}
      {sent && <span role="status" className="basis-full text-[13px] text-tx3 pt-1">{sent === 'Tak' ? 'Dziękujemy, zapisane.' : 'Zapisane jako „To błąd — popraw”: trafi do triage i do kolejnego treningu.'}</span>}
    </div>
  );
}

function StepsPanel({ steps, total }: { steps: JobStep[]; total?: number }) {
  const [sel, setSel] = useState<string | null>(steps.find((s) => s.status === 'warn')?.key ?? null);
  const doneN = steps.filter((s) => s.status && s.status !== 'pending').length;
  return (
    <aside aria-labelledby="rp-sum" className="bg-[#F6F6F6] rounded-panel p-5 flex flex-col gap-1">
      <div className="flex items-center gap-3 px-1 pb-2.5 pt-0.5">
        <Bot color="#0A0A0A" master size={42} />
        <div className="flex-1 flex flex-col gap-px">
          <h2 id="rp-sum" className="m-0 text-[18px] font-semibold tracking-[-0.015em]">Jak pracowały boty</h2>
          <span className="text-[13px] text-tx3">{doneN} z {steps.length} kroków{total ? ` · ${secs(total)}` : ''}</span>
        </div>
      </div>
      {steps.map((s) => {
        const open = sel === s.key;
        const b = BOT_BY_STEP[s.key];
        const [out, ...notes] = (s.detail ?? '').split('\n');
        const warn = s.status === 'warn' || s.status === 'error';
        return (
          <div key={s.key} className={'rounded-[18px] overflow-hidden ' + (open ? 'bg-bg1' : '')}>
            <button type="button" onClick={() => setSel(open ? null : s.key)} aria-expanded={open}
              className="flex items-center gap-3 w-full min-h-[54px] px-3.5 py-2 text-left">
              {warn ? <span className="okc !bg-[#EA580C]">!</span> : s.status === 'skip' ? <span className="okc !bg-line3">–</span> : <span className="okc"><ICheck width={11} height={11} /></span>}
              <span className="flex-1 min-w-0 flex flex-col gap-0.5">
                <span className="text-[15px] font-semibold">{b.stepName}</span>
                <span className={'text-[13px] ' + (warn ? 'text-[#9A3412]' : 'text-tx2')}>{out || '—'}</span>
              </span>
              <span className="font-mono text-[12px] text-tx4">{secs(s.duration_ms)}</span>
              <IChev className={'text-tx4 flex-none transition-transform ' + (open ? 'rotate-180' : '')} />
            </button>
            {open && (
              <div className="px-3.5 pb-3.5 flex gap-2.5 items-start">
                <Bot color={b.color} master={b.master} size={30} />
                <span className="flex flex-col gap-1 min-w-0">
                  <span className="text-[12px] text-tx3">{b.name}</span>
                  {(notes.length ? notes : [s.detail ?? 'Bez uwag.']).map((t, i) => <span key={i} className="text-[14px] leading-[1.45] text-[#262626]">{t}</span>)}
                  {s.warnings?.map((w, i) => <span key={'w' + i} className="text-[12.5px] text-[#9A3412]">{w}</span>)}
                </span>
              </div>
            )}
          </div>
        );
      })}
    </aside>
  );
}

function Layers({ d }: { d: Decision }) {
  if (!d.layers?.length) return null;
  const T: Record<string, string> = { available: 'jest', partial: 'częściowo', missing: 'brak', error: 'błąd' };
  return (
    <div className="card !rounded-[18px] p-4">
      <h3 className="text-[15px] font-semibold pb-2">Szczegóły warstwa po warstwie <span className="font-normal text-tx3 text-[13px]">· pokrycie {p2(d.coverage)}</span></h3>
      <ul className="grid grid-cols-2 sm:grid-cols-4 gap-2 m-0 p-0 list-none">
        {d.layers.map((l) => (
          <li key={l.layer} className={'rounded-xl border px-3 py-2 text-[13px] ' + (l.state === 'available' ? 'border-line1' : 'border-dashed border-line2 bg-bg2')}>
            <b className={`block t-${l.layer}`} style={{ color: 'var(--c)' }}>{LAYER_LABEL[l.layer]}</b>
            <span className="text-tx2">{T[l.state]}{l.reason ? `: ${l.reason}` : ''}</span>
          </li>
        ))}
      </ul>
      <p className="text-[12.5px] text-tx3 pt-2">Brak wartości nie jest dowodem różnicy: brakujące warstwy nie obniżają wyniku.</p>
    </div>
  );
}

export interface ReportProps {
  decision: Decision;
  campaign?: Campaign | null;
  incident?: IncidentSummary | null;
  steps?: JobStep[];
  names: Record<string, string>;
  view: 'raport' | 'graf';
  onView: (v: 'raport' | 'graf') => void;
  onFocus: (id: string) => void;
  focusView?: React.ReactNode;
}


export function Report({ decision: d, campaign, incident, steps, names, view, onView, onFocus, focusView }: ReportProps) {
  const cid = d.campaign_id ?? d.candidate_campaign_id ?? '';
  const story = storyOf(campaign);
  const ev = (d.evidence ?? []).map(prettyEv).sort((a, b) => (b.state === 'zero' ? -1 : 0) - (a.state === 'zero' ? -1 : 0) || Math.abs(b.weight) - Math.abs(a.weight));
  const cards = ev.slice(0, 6);
  const isGraf = view === 'graf';
  const total = steps?.reduce((a, s) => a + (s.duration_ms ?? 0), 0);
  const cloudRaw = useApi<GraphPayload>(isGraf && cid ? `/graph?scope=campaign&campaign=${encodeURIComponent(cid)}` : null).data;
  const cloud = useMemo(() => {
    if (!cloudRaw) return undefined;
    const members = cloudRaw.nodes.filter((x) => x.kind === 'incident' && (x.campaign_id === cid || cloudRaw.edges.some((e) => (e.a === cid && e.b === x.id) || (e.b === cid && e.a === x.id))));
    if (!members.length) return undefined;
    return { ...cloudRaw, nodes: [{ id: cid, kind: 'campaign' as const, label: cid }, ...members], edges: members.map((m) => ({ a: cid, b: m.id, type: 'member' as const })) };
  }, [cloudRaw, cid]);
  const op = d.operator_id ?? campaign?.operator_id;
  const ru = d.runner_up;
  const stageH = Math.max(isGraf ? 600 : 620, 36 + cards.length * 76 + 90, isGraf ? 20 + cards.length * 96 + 20 : 0);
  const metaLine = [cid, campaign && `${n(campaign.n_incidents)} materiałów`, campaign && `${n(campaign.n_domains)} domen`, d.incident_id, incident?.domain].filter(Boolean).join(' · ');

  return (
    <main className="relative z-[1] w-full max-w-[1240px] mx-auto px-4 sm:px-6 pt-[30px] pb-8 box-border">
      <ReportHeader
        title={story.h1 || (names[cid] ?? cid)}
        lead={story.p}
        meta={metaLine}
        primary={<Link className="btn-pri" href={`/kampanie/${encodeURIComponent(cid)}`}>Otwórz kampanię<IArrow /></Link>}
        secondary={<Link className="lnk" href={incident?.domain ? `/sledztwa?seed=${encodeURIComponent(incident.domain)}&kampania=${encodeURIComponent(cid)}` : `/sledztwa?kampania=${encodeURIComponent(cid)}`}>albo szukaj reszty z agentem</Link>}
      />
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="pill bg-state-gdim text-state-g !h-8 !text-[13.5px]"><ICheck width={12} height={12} />{d.decision === 'confirm' ? 'Dołącza do kampanii (do potwierdzenia)' : 'Dołącza do kampanii'} {cid} · pewność {p2(d.p)}</span>
        {op && <span className="pill bg-bg3 text-tx1 !h-8">operator {op}</span>}
        {ru && <span className="pill bg-bg3 text-tx2 !h-8">następna: {ru.campaign_id} {p2(ru.p)}{ru.same_operator ? ' · ten sam operator' : ''}</span>}
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <div className="seg" role="group" aria-label="Widok wyniku">
          <button type="button" aria-pressed={!isGraf} onClick={() => onView('raport')}><IList width={15} height={15} />Raport</button>
          <button type="button" aria-pressed={isGraf} onClick={() => onView('graf')}><IGraph width={15} height={15} />Graf</button>
        </div>
        {isGraf && !focusView && <span className="text-[13px] text-tx3">Kliknij węzeł, żeby go rozwinąć</span>}
      </div>

      {isGraf && focusView ? <div className="mt-5">{focusView}</div> : (
        <>
          {/* desktop stage: cards move between list and graph */}
          <div className="hidden lg:block relative mt-[18px]" role="group" aria-label={isGraf ? 'Graf: materiał, dowody i dopasowane kampanie' : 'Raport botów'} style={{ height: stageH }}>
            <span className="mv absolute left-0 top-1.5 text-[13px] font-medium text-tx3" style={{ opacity: isGraf ? 0 : 1 }}>Co znalazły boty</span>
            <svg className="fadeN absolute left-0 top-0 pointer-events-none" width={1192} height={stageH} aria-hidden="true" style={{ opacity: isGraf ? 1 : 0, transitionDelay: isGraf ? '.3s' : '0s' }}>
              <g fill="none" strokeLinecap="round">
                {cards.map((e, k) => {
                  const y = 20 + 96 * k + 32;
                  const zero = e.state === 'zero';
                  const c = zero ? '#D4D4D4' : k < 3 ? '#171717' : '#A3A3A3';
                  return (
                    <g key={k}>
                      <path d={`M240 300 C270 300 270 ${y} 300 ${y}`} stroke={c} strokeWidth={zero ? 1.2 : 3 - k * 0.4} strokeDasharray={zero ? '4 5' : undefined} />
                      {!zero && <path d={`M560 ${y} C610 ${y} 610 300 660 300`} stroke={c} strokeWidth={3 - k * 0.4} />}
                    </g>
                  );
                })}
                {ru && <path d="M810 410 L810 476" stroke="#6D28D9" strokeWidth={1.5} strokeDasharray="6 6" />}
              </g>
              <g fill="#FFFFFF" stroke="#171717" strokeWidth={1.5}><circle cx={240} cy={300} r={4} /><circle cx={660} cy={300} r={4} /></g>
            </svg>
            {/* this material */}
            <div className="mv absolute bg-bg1 border border-line1 rounded-[18px] p-3.5 flex flex-col gap-2 shadow-soft" style={{ left: 0, top: 215, width: 240, height: 170, opacity: isGraf ? 1 : 0, pointerEvents: isGraf ? 'auto' : 'none', transitionDelay: isGraf ? '.3s' : '0s' }}>
              <span className="text-[12px] font-medium text-tx3">Ten materiał</span>
              <span className="ph-img h-14 text-[11px]">zrzut</span>
              <b className="text-[18px] font-semibold tracking-[-0.02em]">{d.incident_id}</b>
              <span className="font-mono text-[12px] text-tx3 truncate">{incident?.domain ?? ''}</span>
            </div>
            {cards.map((e, k) => (
              <div key={k} className="mv absolute" style={{ left: isGraf ? 300 : 0, top: isGraf ? 20 + 96 * k : 36 + 76 * k, width: isGraf ? 260 : 700 }}>
                <FindCard e={e} graph={isGraf} onClick={() => { onView('graf'); onFocus(fid(e, incident?.domain)); }} />
              </div>
            ))}
            {/* campaign */}
            <article aria-label={`Kampania ${cid}`} className="mv absolute bg-tx1 text-[#FAFAFA] rounded-[22px] p-5 flex flex-col gap-2.5 shadow-dark" style={{ left: 660, top: 190, width: 300, height: 220, opacity: isGraf ? 1 : 0, pointerEvents: isGraf ? 'auto' : 'none', transitionDelay: isGraf ? '.3s' : '0s' }}>
              <span className="text-[12px] font-medium text-line3">Kampania · dopasowanie {p2(d.p)}</span>
              {campaignTitle(campaign).length > 24
                ? <h2 className="m-0 flex flex-col gap-1.5"><span className="text-[30px] leading-none tracking-[-0.045em] font-semibold">{cid}</span><span className="text-[15px] leading-snug font-semibold line-clamp-2">{campaignTitle(campaign)}</span></h2>
                : <h2 className="m-0 text-[30px] leading-none tracking-[-0.045em] font-semibold">{cid}<br />{campaignTitle(campaign)}</h2>}
              {campaignTitle(campaign).length <= 24 && <p className="m-0 text-[13.5px] leading-[1.45] text-line2 line-clamp-2">{campaign?.narrative}</p>}
              <div className="mt-auto flex flex-wrap gap-1.5">
                {op && <button type="button" className="tag" onClick={() => onFocus(op)}>{op}</button>}
                <Link className="tag !bg-white !text-tx1" href={`/kampanie/${encodeURIComponent(cid)}`}>Otwórz kampanię</Link>
              </div>
            </article>
            {ru && (
              <div className="mv absolute bg-bg1 border-[1.5px] border-dashed border-[#C4B5FD] rounded-[18px] px-3.5 py-3 flex flex-col gap-1" style={{ left: 690, top: 476, width: 240, minHeight: 92, opacity: isGraf ? 1 : 0, pointerEvents: isGraf ? 'auto' : 'none', transitionDelay: isGraf ? '.3s' : '0s' }}>
                <span className="flex justify-between items-center"><span className="text-[12px] font-medium text-[#6D28D9]">Inna kampania</span><b className="font-mono text-[14px] font-semibold">{p2(ru.p)}</b></span>
                <Link href={`/kampanie/${ru.campaign_id}`} className="text-[14px] leading-snug font-semibold tracking-[-0.01em] hover:underline line-clamp-2">{names[ru.campaign_id] ?? ru.campaign_id}</Link>
                <span className="text-[12.5px] text-tx3">{ru.same_operator ? `ten sam operator ${op ?? ''}` : 'inny operator'}</span>
              </div>
            )}
            {isGraf && (
              <>
                <GraphCloud data={cloud} onPick={onFocus} className="!absolute left-[970px] top-[110px] w-[222px] h-[340px]" label={`Materiały kampanii ${cid}`} />
                <span className="absolute left-[1000px] top-[462px] w-[190px] text-[12px] leading-[1.4] text-tx3">{campaign ? `${n(campaign.n_incidents)} materiałów i ${n(campaign.n_domains)} domen tej kampanii` : ''}</span>
              </>
            )}
            {/* feedback + steps panel */}
            <div className="mv absolute" style={{ left: 0, top: 36 + cards.length * 76 + 26, width: 700, opacity: isGraf ? 0 : 1, pointerEvents: isGraf ? 'none' : 'auto' }}>
              <Feedback incidentId={d.incident_id} />
            </div>
            {steps && (
              <div className="mv absolute" style={{ left: isGraf ? 800 : 740, top: 0, width: 452, opacity: isGraf ? 0 : 1, pointerEvents: isGraf ? 'none' : 'auto' }}>
                <StepsPanel steps={steps} total={total} />
              </div>
            )}
          </div>

          {/* phone / tablet: plain flow */}
          <div className="lg:hidden mt-5 flex flex-col gap-3">
            {!isGraf && <span className="text-[13px] font-medium text-tx3">Co znalazły boty</span>}
            {isGraf && (
              <div className="rounded-[18px] border border-line1 p-3.5 flex items-center gap-3"><span className="ph-img w-12 h-12" /><span><b className="block">{d.incident_id}</b><span className="font-mono text-[12px] text-tx3">{incident?.domain}</span></span></div>
            )}
            {cards.map((e, k) => <FindCard key={k} e={e} graph={isGraf} onClick={() => { onView('graf'); onFocus(fid(e, incident?.domain)); }} />)}
            {isGraf ? (
              <article className="bg-tx1 text-[#FAFAFA] rounded-[22px] p-5 flex flex-col gap-2">
                <span className="text-[12px] text-line3">Kampania · dopasowanie {p2(d.p)}</span>
                <h2 className="text-[26px] font-semibold tracking-[-0.04em] leading-none">{cid} {campaignTitle(campaign)}</h2>
                <Link className="tag !bg-white !text-tx1 self-start" href={`/kampanie/${cid}`}>Otwórz kampanię</Link>
              </article>
            ) : (
              <>
                <Feedback incidentId={d.incident_id} />
                {steps && <StepsPanel steps={steps} total={total} />}
              </>
            )}
          </div>

          {!isGraf && (
            <div className="mt-8 flex flex-col gap-4">
              <div>
                <h3 className="text-[15px] font-semibold pb-2">Dowody</h3>
                <div className="flex flex-wrap gap-1.5">{ev.map((e, i) => <EvidenceChip key={i} e={e} onClick={() => { onView('graf'); onFocus(fid(e, incident?.domain)); }} />)}</div>
              </div>
              <Layers d={d} />
            </div>
          )}
        </>
      )}
    </main>
  );
}

export { BOT_BY_KEY };
