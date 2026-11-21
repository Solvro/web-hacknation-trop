'use client';
// Boards 3 (Raport) and 4 (Graf): the same finding cards move from a list into a graph.
// Raport = verdict (campaign links to its page) + the evidence that links it (with weights) + the real page / ad images
// + the Graf switch + one quiet "Śledź dalej". Nothing else.
import Link from 'next/link';
import { useMemo } from 'react';
import type { Campaign, Decision, EvidenceItem, GraphPayload, JobStep } from '@/lib/contracts';
import { isPolish, prettyEv, BOT_BY_KEY, botColor, botName, evidenceMeta, evidenceSentence, fmtDate, p2, w1 } from '@/lib/copy';
import { useApi } from '@/lib/api';
import { campaignTitle, focusIdOf as fid } from '@/lib/graph';
import { Bot } from '../jelly';
import { EvidenceChip } from '../evidence-chip';
import { FollowButton } from '../follow-button';
import { materialTitle, restoreTemplateCase, useArtifacts, type Artifacts, type Material } from '@/lib/artifacts';
import { GraphCloud } from '../graph/cloud';
import { RealShot } from './live';
import { ICheck, IGraph, IList } from '../icons';

export function storyOf(c?: Campaign | null): { h1: string; p: string } {
  const d = c?.description ?? '';
  if (d.includes('\n')) { const [h1, ...rest] = d.split('\n'); return { h1, p: rest.join(' ') }; }
  // real mode: Polish descriptive name, English engine narrative → headline from the name, no English lead
  const pl = (t: string) => isPolish(t);
  const narrative = (c?.narrative ?? '').replace(/\.$/, '');
  if (narrative && pl(narrative)) return { h1: narrative, p: d && d !== c?.narrative && pl(d) ? d : '' };
  return { h1: c?.name ?? narrative, p: d && pl(d) && d !== c?.name ? d : '' };
}

export function ReportHeader({ title, lead, meta, primary, secondary }: { title: React.ReactNode; lead?: string; meta?: string; primary?: React.ReactNode; secondary?: React.ReactNode }) {
  return (
    <section aria-labelledby="rp-verdict" className="flex flex-wrap items-end justify-between gap-x-7 gap-y-5">
      <div className="flex-[1_1_560px] min-w-0 flex flex-col gap-2.5">
        <h1 id="rp-verdict" className="m-0 text-[30px] sm:text-[42px] leading-[1.05] tracking-[-0.04em] font-semibold break-words">{title}</h1>
        {lead && <p className="m-0 max-w-[720px] text-[17px] leading-normal text-tx2">{lead}</p>}
        {meta && <span className="font-mono text-[12.5px] text-tx4 break-words">{meta}</span>}
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
  return onClick ? <button type="button" className={cls} onClick={onClick} aria-label={`${evidenceSentence(e)}: rozwiń w grafie`} title={evidenceSentence(e)}>{inner}</button> : <div className={cls}>{inner}</div>;
}

export interface ReportProps {
  decision: Decision;
  campaign?: Campaign | null;
  incident?: Material | null;
  steps?: JobStep[];
  names: Record<string, string>;
  view: 'raport' | 'graf';
  onView: (v: 'raport' | 'graf') => void;
  onFocus: (id: string) => void;
  focusView?: React.ReactNode;
}

export const hasImages = (art: Artifacts) => !!(art.landing || art.adShot || art.frames.length);

/** Real images of the material: the rendered landing page (evidence outlined) and the ad / video frames. Nothing when there are none. */
export function MaterialImages({ art, url, height = 420 }: { art: Artifacts; url: string; height?: number }) {
  if (!hasImages(art)) return null;
  const ad = art.adShot && !/keyframe|video/.test(art.adShot.role ?? '') && art.adShot.url !== art.landing?.url ? art.adShot : undefined;
  return (
    <section aria-label="Strona i reklama" className="flex flex-col gap-3 min-w-0">
      {art.landing && (
        <figure className="m-0 flex flex-col gap-1.5">
          <figcaption className="text-[12.5px] text-tx3">Strona docelowa{art.landing.boxes.length ? ' · obrysy pokazują, gdzie boty znalazły dowody' : ''}</figcaption>
          <RealShot url={url} shot={art.landing} height={height} />
        </figure>
      )}
      {(ad || art.frames.length > 0) && (
        <figure className="m-0 flex flex-col gap-1.5">
          <figcaption className="text-[12.5px] text-tx3">{ad ? 'Reklama' : 'Klatki z nagrania reklamy'}</figcaption>
          <div className="flex gap-2 overflow-x-auto">
            {(ad ? [ad] : art.frames.slice(0, 4)).map((s) => (
              <a key={s.url} href={s.url} target="_blank" rel="noopener noreferrer" className="flex-none max-w-full">
                <img src={s.url} alt={ad ? 'Zrzut reklamy' : 'Klatka nagrania'} className={(ad ? 'max-h-[150px] max-w-full' : 'h-[96px]') + ' w-auto object-contain rounded-[12px] border border-line1 bg-bg2'} />
              </a>
            ))}
          </div>
        </figure>
      )}
    </section>
  );
}

export function MaterialStrip({ incident, incidentId, art }: { incident?: Material | null; incidentId: string; art: Artifacts }) {
  const title = materialTitle(incident, incidentId);
  return (
    <section aria-label="Sprawdzany materiał" className="mt-5 flex items-center gap-3.5 rounded-[18px] border border-line1 bg-bg1 py-2.5 px-4 max-w-[760px]">
      {art.any && <a href={art.ad ?? art.any} target="_blank" rel="noopener noreferrer" className="flex-none -ml-1.5"><img src={art.ad ?? art.any} alt={`Zrzut materiału ${incidentId}`} className="w-[96px] h-[64px] object-cover object-top rounded-[10px] border border-line1" /></a>}
      <span className="min-w-0 flex flex-col gap-0.5">
        <span className="text-[12px] text-tx3">Sprawdzany materiał</span>
        <b className="text-[14.5px] font-semibold leading-snug line-clamp-2 break-words">{title}</b>
        <span className="font-mono text-[11.5px] text-tx3 truncate">{[incidentId !== title ? incidentId : null, incident?.domain && incident.domain !== title ? incident.domain : null, incident?.captured_at ? fmtDate(incident.captured_at) : null].filter(Boolean).join(' · ')}</span>
      </span>
    </section>
  );
}

export function Report({ decision: d, campaign, incident, names, view, onView, onFocus, focusView }: ReportProps) {
  const art = useArtifacts(d.incident_id);
  const cid = d.campaign_id ?? d.candidate_campaign_id ?? '';
  const story = storyOf(campaign);
  const ev = (d.evidence ?? []).map(prettyEv).map((e) => restoreTemplateCase(e, incident)).filter((e) => e.state !== 'missing')
    .sort((a, b) => (b.state === 'zero' ? -1 : 0) - (a.state === 'zero' ? -1 : 0) || Math.abs(b.weight) - Math.abs(a.weight));
  const cards = ev.slice(0, 6);
  const rest = ev.slice(cards.length);
  const isGraf = view === 'graf';
  const img = hasImages(art);
  const cloudRaw = useApi<GraphPayload>(isGraf && cid ? `/graph?scope=campaign&campaign=${encodeURIComponent(cid)}` : null).data;
  const cloud = useMemo(() => {
    if (!cloudRaw) return undefined;
    const members = cloudRaw.nodes.filter((x) => x.kind === 'incident' && (x.campaign_id === cid || cloudRaw.edges.some((e) => (e.a === cid && e.b === x.id) || (e.b === cid && e.a === x.id))));
    if (!members.length) return undefined;
    return { ...cloudRaw, nodes: [{ id: cid, kind: 'campaign' as const, label: cid }, ...members], edges: members.map((m) => ({ a: cid, b: m.id, type: 'member' as const })) };
  }, [cloudRaw, cid]);
  const op = d.operator_id ?? campaign?.operator_id;
  const ru = d.runner_up;
  // raport: one column of cards next to the images, or two columns of cards when there are no images
  const cols = img ? 1 : 2;
  const listPos = (k: number) => (cols === 1 ? { left: 0, top: 36 + 76 * k, width: 700 } : { left: (k % 2) * 606, top: 36 + 76 * Math.floor(k / 2), width: 586 });
  const listH = 36 + Math.ceil(cards.length / cols) * 76;
  const stageH = isGraf ? Math.max(600, 20 + cards.length * 96 + 20) : Math.max(listH, img ? 36 + 640 : 0);
  const pick = (e: EvidenceItem) => { onView('graf'); onFocus(fid(e, incident?.domain)); };
  const verdictTitle = story.h1 || names[cid] || cid;

  return (
    <main className="relative z-[1] w-full max-w-[1240px] mx-auto px-4 sm:px-6 pt-[30px] pb-8 box-border">
      <ReportHeader
        title={cid ? <Link href={`/kampanie/${encodeURIComponent(cid)}`} className="hover:underline decoration-2 underline-offset-[6px]">{verdictTitle}</Link> : verdictTitle}
        lead={story.p}
      />
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="pill bg-state-gdim text-state-g !h-auto min-h-8 py-1 !text-[13.5px] flex-wrap"><ICheck width={12} height={12} />{d.decision === 'confirm' ? 'Dołącza do kampanii (do potwierdzenia)' : 'Dołącza do kampanii'} <Link href={`/kampanie/${encodeURIComponent(cid)}`} className="underline decoration-[#86efac] underline-offset-4 hover:decoration-current">{cid}</Link> · pewność {p2(d.p)}</span>
        {op && <span className="pill bg-bg3 text-tx1 !h-8">operator {op}</span>}
        {ru && <span className="pill bg-bg3 text-tx2 !h-8">następna: {ru.campaign_id} {p2(ru.p)}{ru.same_operator ? ' · ten sam operator' : ''}</span>}
      </div>

      <MaterialStrip incident={incident} incidentId={d.incident_id} art={art} />
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
            <span className="mv absolute left-0 top-1.5 text-[13px] font-medium text-tx3" style={{ opacity: isGraf ? 0 : 1 }}>Co łączy materiał z kampanią</span>
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
            <div className="mv absolute bg-bg1 border border-line1 rounded-[18px] p-3.5 flex flex-col gap-2 shadow-soft" style={{ left: 0, top: 200, width: 240, height: 200, opacity: isGraf ? 1 : 0, pointerEvents: isGraf ? 'auto' : 'none', transitionDelay: isGraf ? '.3s' : '0s' }}>
              <span className="text-[12px] font-medium text-tx3">Ten materiał</span>
              {art.any && <img src={art.ad ?? art.any} alt={`Zrzut materiału ${d.incident_id}`} className="h-14 w-full flex-none object-cover object-top rounded-[10px] border border-line1" />}
              <b className={(art.any ? 'text-[14px] line-clamp-3' : 'text-[15px] line-clamp-5') + ' flex-none font-semibold tracking-[-0.01em] leading-snug break-words'}>{materialTitle(incident, d.incident_id)}</b>
              <span className="font-mono text-[11.5px] text-tx3 truncate mt-auto">{[d.incident_id, incident?.title ? incident?.domain : null].filter(Boolean).join(' · ')}</span>
            </div>
            {cards.map((e, k) => (
              <div key={k} className="mv absolute" style={isGraf ? { left: 300, top: 20 + 96 * k, width: 260 } : listPos(k)}>
                <FindCard e={e} graph={isGraf} onClick={() => pick(e)} />
              </div>
            ))}
            {/* campaign */}
            <article aria-label={`Kampania ${cid}`} className="mv absolute bg-tx1 text-[#FAFAFA] rounded-[22px] p-5 flex flex-col gap-2.5 shadow-dark" style={{ left: 660, top: 190, width: 300, height: 220, opacity: isGraf ? 1 : 0, pointerEvents: isGraf ? 'auto' : 'none', transitionDelay: isGraf ? '.3s' : '0s' }}>
              <span className="text-[12px] font-medium text-line3">Kampania · dopasowanie {p2(d.p)}</span>
              {campaignTitle(campaign).length > 24
                ? <h2 className="m-0 flex flex-col gap-1.5"><span className="text-[30px] leading-none tracking-[-0.045em] font-semibold">{cid}</span><span className="text-[15px] leading-snug font-semibold line-clamp-3">{campaignTitle(campaign)}</span></h2>
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
            {isGraf && <GraphCloud data={cloud} onPick={onFocus} className="!absolute left-[970px] top-[110px] w-[222px] h-[340px]" label={`Materiały kampanii ${cid}`} />}
            {img && (
              <div className="mv absolute" style={{ left: 740, top: 0, width: 452, opacity: isGraf ? 0 : 1, pointerEvents: isGraf ? 'none' : 'auto' }}>
                <MaterialImages art={art} url={incident?.domain ?? d.incident_id} height={440} />
              </div>
            )}
          </div>

          {/* phone / tablet: plain flow */}
          <div className="lg:hidden mt-5 flex flex-col gap-3">
            {!isGraf && <span className="text-[13px] font-medium text-tx3">Co łączy materiał z kampanią</span>}
            {isGraf && (
              <div className="rounded-[18px] border border-line1 p-3.5 flex items-center gap-3">{art.any && <img src={art.ad ?? art.any} alt="" className="w-14 h-14 object-cover object-top rounded-lg border border-line1" />}<span className="min-w-0"><b className="block line-clamp-2 break-words">{materialTitle(incident, d.incident_id)}</b><span className="font-mono text-[12px] text-tx3">{[d.incident_id, incident?.domain].filter(Boolean).join(' · ')}</span></span></div>
            )}
            {cards.map((e, k) => <FindCard key={k} e={e} graph={isGraf} onClick={() => pick(e)} />)}
            {isGraf ? (
              <article className="bg-tx1 text-[#FAFAFA] rounded-[22px] p-5 flex flex-col gap-2">
                <span className="text-[12px] text-line3">Kampania · dopasowanie {p2(d.p)}</span>
                <h2 className="text-[26px] font-semibold tracking-[-0.04em] leading-none">{cid} {campaignTitle(campaign)}</h2>
                <Link className="tag !bg-white !text-tx1 self-start" href={`/kampanie/${cid}`}>Otwórz kampanię</Link>
              </article>
            ) : img ? <div className="pt-2"><MaterialImages art={art} url={incident?.domain ?? d.incident_id} height={380} /></div> : null}
          </div>

          {!isGraf && rest.length > 0 && (
            <div className="mt-8">
              <h3 className="text-[15px] font-semibold pb-2">Pozostałe dowody <span className="font-normal text-tx3 text-[13px]">· waga i rzadkość każdego śladu</span></h3>
              <div className="flex flex-wrap gap-1.5">{rest.map((e, i) => <EvidenceChip key={i} e={e} onClick={() => pick(e)} />)}</div>
            </div>
          )}
        </>
      )}
      <div className="mt-8 pt-5 border-t border-bg4 flex flex-wrap items-center gap-2">
        <FollowButton variant="sec" incidentId={d.incident_id} evidence={d.evidence ?? []} domain={incident?.domain} campaignId={cid} />
      </div>
    </main>
  );
}

export { BOT_BY_KEY };
