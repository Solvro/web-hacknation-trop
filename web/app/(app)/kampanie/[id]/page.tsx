'use client';
// Board 6 · Kampania: headline, stats, timeline, "Co łączy te materiały", domains, Zgłoszenia, merge, Oracle,
// operator, persons. Main action "Zgłoś całą kampanię".
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useState } from 'react';
import type { ActPackage, DomainIndicator, Campaign, CampaignDNA, CampaignSummary, IncidentSummary, Indicators, Operator, OraclePrediction, Timeline } from '@/lib/contracts';
import { apiPost, useApi } from '@/lib/api';
import { BOT_FOR_LAYER, plural, botColor, botName, fmtDate, LAYER_LABEL, n, p2, plOnly, prettyDisplay } from '@/lib/copy';
import { campaignTitle, personName } from '@/lib/graph';
import { JellyRoot, Bot } from '@/components/jelly';
import { ReportHeader, storyOf } from '@/components/analysis/report';
import { Bars, Card, Crumbs, Empty, Initials, Loading, Page } from '@/components/ui';
import { IArrow } from '@/components/icons';
import { MaterialThumb } from '@/components/material-thumb';

const RSTATUS: Record<string, string> = { ready: 'gotowe do wysłania', done: 'zrobione', sent: 'wysłane', queued: 'w kolejce', pending: 'czeka', off: 'wyłączony', exported: 'wyeksportowane' };
const opLabel = (op: Operator | undefined, id: string) => (op && op.codename && op.codename !== id ? `${id} «${op.codename}»` : id);
const dshort = (iso?: string | null) => (iso ? fmtDate(iso, false).slice(0, 5).replace(/^0/, '') : '');

function DomainStatus({ d }: { d: DomainIndicator }) {
  if (d.online === '502' || d.online === false) return <span className="pill bg-bg3 text-tx2">wyłączona</span>;
  if (d.on_certpl) return <span className="pill bg-state-gdim text-state-g">na liście CERT PL</span>;
  if (!d.ads_seen) return <span className="pill bg-[#FFF1E6] text-[#C2410C]">nowa, bez reklam</span>;
  return <span className="pill bg-state-rdim text-state-red">aktywna</span>;
}

export default function KampaniaPage() {
  const { id: raw } = useParams<{ id: string }>();
  const id = decodeURIComponent(raw);
  const { data: c, loading, error } = useApi<Campaign>(`/campaigns/${encodeURIComponent(id)}`);
  const dna = useApi<CampaignDNA>(`/campaigns/${encodeURIComponent(id)}/dna`).data;
  const tl = useApi<Timeline>(`/campaigns/${encodeURIComponent(id)}/timeline?range=14d`).data;
  const ind = useApi<Indicators>(`/campaigns/${encodeURIComponent(id)}/indicators`).data;
  const op = useApi<Operator>(c?.operator_id ? `/operators/${c.operator_id}` : null).data;
  const oracle = useApi<OraclePrediction[]>(`/oracle/predictions?campaign=${encodeURIComponent(id)}`).data;
  const pk = useApi<ActPackage[]>(`/act/packages?campaign_id=${encodeURIComponent(id)}`).data;
  const all = useApi<CampaignSummary[]>('/campaigns').data;
  const incs = useApi<IncidentSummary[] | { items: IncidentSummary[] }>('/incidents?limit=1000').data;
  const mats = (Array.isArray(incs) ? incs : incs?.items ?? []).filter((m) => m.campaign_id === id)
    .sort((a, b) => String(b.captured_at ?? '').localeCompare(String(a.captured_at ?? '')));
  const [confirmed, setConfirmed] = useState(false);

  if (loading) return <Loading />;
  if (!c) return <Page><Empty>{error ? `Nie znaleziono kampanii ${id}.` : ''}</Empty></Page>;
  const story = storyOf(c);
  const cnt = c.counts ?? {};
  const days = tl?.days ?? [];
  const evs = tl?.events ?? [];
  const markers = evs.map((e) => {
    const i = days.findIndex((d) => String(d.date) === e.at.slice(0, 10));
    return i < 0 ? null : { i, text: e.kind === 'oracle_predicted' ? `Oracle przewidział ${e.ref}` : e.kind === 'cert_batch' ? e.ref : e.ref, color: e.kind === 'oracle_predicted' ? '#6D28D9' : '#C2410C' };
  }).filter(Boolean).slice(-2) as { i: number; text: string; color: string }[];
  const mergeWith = (all ?? []).find((x) => x.id !== id && x.operator_id && x.operator_id === c.operator_id && (x.merge_hint === id || (x.status === 'candidate' && /scal|wariant/i.test(`${x.name} ${x.narrative}`))));
  const others = (op?.campaigns ?? []).filter((x) => x.id !== id) as { id: string; name: string; incidents: number }[];
  const persons = (ind?.persons ?? []) as { name: string; role?: string; count?: number }[];
  const domains = ind?.domains ?? [];
  const isCandidate = c.status === 'candidate' && !c.operator_id;
  const oracleMine = (oracle ?? []).filter((o) => o.campaign_id === id);

  return (
    <JellyRoot className="flex-1 flex flex-col">
      <Page>
        <Crumbs items={[{ label: 'Kampanie', href: '/kampanie' }, { label: c.id }]} />
        <ReportHeader
          title={story.h1}
          lead={story.p}
          meta={[campaignTitle(c).length <= 28 ? `${c.id} ${campaignTitle(c)}` : c.id, c.operator_id && `operator ${opLabel(op, c.operator_id)}`, c.first_seen && `aktywna od ${fmtDate(c.first_seen, false)}`].filter(Boolean).join(' · ')}
          primary={isCandidate
            ? <button type="button" className="btn-pri" onClick={() => { setConfirmed(true); apiPost(`/triage`, { source: 'kampanie', subject_id: c.id, decision: { action: 'new_campaign' } }, () => ({})).catch(() => null); }}>{confirmed ? 'Potwierdzone' : 'Potwierdź nową kampanię'}<IArrow /></button>
            : <Link className="btn-pri" href={`/kampanie/${c.id}/zgloszenie`}>Zgłoś całą kampanię<IArrow /></Link>}
          secondary={<Link className="lnk" href={domains[0]?.fqdn ? `/sledztwa?seed=${encodeURIComponent(domains[0].fqdn)}&kampania=${c.id}` : `/sledztwa?kampania=${c.id}`}>albo szukaj reszty z agentem</Link>}
        />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            [n(cnt.incidents ?? c.n_incidents), `materiałów${c.heat?.trend_pct ? ` · ${c.heat.trend_pct > 0 ? '+' : ''}${Math.round(c.heat.trend_pct)}% w 48 h` : ''}`, (c.heat?.trend_pct ?? 0) > 5],
            [n(cnt.domains ?? c.n_domains), `domen${c.new_domains_24h ? ` · ${c.new_domains_24h} nowe dziś` : ''}`, false],
            [n(cnt.advertisers ?? 0), `reklamodawców${cnt.advertisers_removed ? ` · ${cnt.advertisers_removed} usuniętych` : ''}`, false],
            [`${n(cnt.certpl_listed ?? 0)} z ${n(cnt.domains ?? c.n_domains)}`, 'domen na liście CERT PL', false],
          ].map(([v, l, hot], i) => (
            <div key={i} className="rounded-[18px] border border-line1 p-4"><b className="block text-[28px] font-semibold tracking-[-0.03em]">{v as string}</b><span className={'text-[12.5px] ' + (hot ? 'text-state-red' : 'text-tx3')}>{l as string}</span></div>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-6 items-start">
          <div className="flex flex-col gap-6 min-w-0">
            <Card title="Materiały w czasie">
              {days.length ? <Bars data={days.map((d) => Number(d.incidents ?? 0))} labels={days.map((d, i) => (String(d.date).slice(0, 10) === new Date().toISOString().slice(0, 10) ? 'dziś' : i % 2 === 0 || i === days.length - 1 ? dshort(String(d.date)) : ''))} markers={markers} label={`Materiały dziennie: ${days.map((d) => d.incidents).join(', ')}`} /> : <Empty>Brak danych.</Empty>}
            </Card>
            <section aria-labelledby="k-dna" className="flex flex-col gap-2.5">
              <h2 id="k-dna" className="text-[16px] font-semibold">Co łączy te materiały</h2>
              {(dna?.signature ?? []).slice(0, 6).map((r, i) => (
                <div key={i} className="min-h-16 flex items-center gap-3 pl-3.5 pr-4 py-2.5 border border-line1 rounded-[18px] bg-bg1 shadow-soft">
                  <Bot color={botColor(r.bot ?? BOT_FOR_LAYER[r.layer])} size={34} />
                  <span className="flex-1 min-w-0"><b className="block text-[14.5px] font-semibold">{prettyDisplay(r.display ?? r.value)}</b><span className="text-[12.5px] text-tx3">{botName(r.bot ?? BOT_FOR_LAYER[r.layer])} · {LAYER_LABEL[r.layer].toLowerCase()}</span></span>
                  <b className="font-mono text-[14px]">{r.members_with} z {r.members_total}</b>
                </div>
              ))}
              {!dna?.signature?.length && <Empty>Za mało materiałów, żeby opisać wspólne ślady.</Empty>}
            </section>
            {mats.length > 0 && (
              <Card title="Materiały" action={<span className="text-[13px] text-tx3">{plural(mats.length, 'materiał', 'materiały', 'materiałów')}</span>}>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
                  {mats.slice(0, 8).map((m) => (
                    <Link key={m.id} href={`/analiza/${encodeURIComponent(m.id)}`} className="flex items-center gap-3 py-2.5 border-b border-bg4 hover:bg-bg2 -mx-2 px-2 rounded-lg min-w-0">
                      <MaterialThumb id={m.id} className="w-12 h-12" />
                      <span className="flex-1 min-w-0"><b className="block text-[13.5px] font-semibold leading-snug line-clamp-2">{m.title || m.domain || m.id}</b><span className="block font-mono text-[12px] text-tx3 truncate">{[m.id, m.title ? m.domain : null, m.captured_at ? fmtDate(m.captured_at, false) : null].filter(Boolean).join(' · ')}</span></span>
                    </Link>
                  ))}
                </div>
              </Card>
            )}
            <Card title="Domeny" action={<span className="text-[13px] text-tx3">{plural(c.n_domains ?? domains.length, 'domena', 'domeny', 'domen')}</span>}>
              {domains.slice(0, 6).map((d) => (
                <Link key={d.fqdn} href={`/slad/domena/${d.fqdn}`} className="flex items-center justify-between gap-3 py-3 border-b border-bg4 last:border-0 hover:bg-bg2 -mx-2 px-2 rounded-lg">
                  <span><b className="block font-mono text-[14px] font-medium">{d.fqdn}</b>
                    <span className="text-[12.5px] text-tx3">{d.online === '502' ? 'nie odpowiada' : [d.cert_issued_at && `certyfikat ${fmtDate(d.cert_issued_at)}`, d.ads_seen ? plural(d.ads_seen, 'reklama', 'reklamy', 'reklam') : d.oracle_predicted_at ? `przewidziana ${dshort(d.oracle_predicted_at)}` : ''].filter(Boolean).join(' · ')}</span></span>
                  <DomainStatus d={d} />
                </Link>
              ))}
              {!domains.length && <Empty>Brak domen.</Empty>}
            </Card>
            <Card title="Zgłoszenia" action={<Link href={`/kampanie/${c.id}/zgloszenie`} className="text-[13px] underline decoration-line2 underline-offset-4 text-tx2">Nowe zgłoszenie</Link>}>
              {(pk ?? []).filter((p) => p.campaign_id === id).sort((a, b) => String(b.created_at).localeCompare(String(a.created_at))).slice(0, 2).map((p) => (
                <div key={p.id} className="pb-3">
                  <span className="block text-[12.5px] text-tx3 pb-1.5 border-b border-bg4">{p.status === 'sent' || p.status === 'exported' ? 'Przygotowane' : 'Szkic'} {fmtDate(p.sent_at ?? p.created_at)} · cała kampania</span>
                  {(p.recipients ?? []).map((r, i) => {
                    const pr = (r.progress ?? {}) as { done?: number; total?: number };
                    const pct = pr.total ? Math.round(((pr.done ?? 0) / pr.total) * 100) : 0;
                    return (
                      <div key={i} className="grid grid-cols-[minmax(0,180px)_1fr] sm:grid-cols-[200px_1fr_minmax(0,260px)] gap-3 items-center py-2.5 border-b border-bg4 last:border-0 text-[13.5px]">
                        <b className="font-semibold">{String(r.label ?? r.id)}</b>
                        <span className="h-2 rounded-full bg-bg4 overflow-hidden"><i className={'block h-full rounded-full ' + (pct >= 100 ? 'bg-[#16A34A]' : 'bg-line3')} style={{ width: `${Math.max(3, pct)}%` }} /></span>
                        <span className={'col-span-2 sm:col-span-1 ' + (pct >= 100 ? 'text-state-g' : 'text-tx2')}>{pr.total != null ? `${pr.done ?? 0} z ${pr.total}` : ''} {RSTATUS[String(r.status ?? '')] ?? String(r.status ?? '')}</span>
                      </div>
                    );
                  })}
                </div>
              ))}
              {!(pk ?? []).some((p) => p.campaign_id === id) && <Empty>Ta kampania nie była jeszcze zgłaszana.</Empty>}
              <p className="text-[12px] text-tx3 pt-1">Pakiety są przygotowywane i eksportowane. TROP niczego nie wysyła sam.</p>
            </Card>
          </div>
          <div className="flex flex-col gap-5">
            {mergeWith && (
              <section className="rounded-[22px] bg-bg3 p-5 flex flex-col gap-1.5">
                <span className="text-[12.5px] text-tx3">Możliwe, że to ta sama kampania</span>
                <b className="text-[17px] font-semibold">{mergeWith.id} {campaignTitle(mergeWith)}</b>
                <p className="text-[13.5px] text-tx2">{plOnly(mergeWith.narrative)}</p>
                <Link href={`/kampanie/scal?a=${id}&b=${mergeWith.id}`} className="self-start text-[14px] font-semibold underline decoration-line2 underline-offset-4 pt-2">Porównaj i scal</Link>
              </section>
            )}
            {oracleMine.length > 0 && (
              <section className="rounded-[22px] border border-[#E9E3FF] bg-[#FAF8FF] p-5">
                <span className="pill bg-white border border-[#DDD3FF] text-state-violet">Oracle</span>
                <h2 className="text-[17px] font-semibold pt-2">Przewidziane domeny</h2>
                <p className="text-[13px] text-tx2 pb-2">Domeny z DNA tej kampanii, które dostały certyfikat, zanim pojawiła się reklama.</p>
                {oracleMine.slice(0, 4).map((o) => (
                  <div key={o.domain} className="flex items-center justify-between gap-2 py-2.5 border-b border-[#ECE7FF] last:border-0">
                    <span><b className="block font-mono text-[13.5px] font-medium">{o.domain}</b><span className="text-[12px] text-tx3">{o.status === 'confirmed' ? `przewidziana ${dshort(o.issued_at)} · reklama ${dshort(o.first_ad_at)}` : `pewność ${p2(o.dna_score)} · ${o.status === 'below_threshold' ? 'poniżej progu' : 'jeszcze bez reklam'}`}</span></span>
                    <span className={'pill ' + (o.status === 'confirmed' ? 'bg-state-gdim text-state-g' : 'bg-state-vdim text-state-violet')}>{o.status === 'confirmed' ? 'trafiona' : 'czeka'}</span>
                  </div>
                ))}
              </section>
            )}
            {op && (
              <Card>
                <span className="text-[12.5px] text-tx3">Operator</span>
                <h2 className="text-[17px] font-semibold">{opLabel(op, op.id)}</h2>
                {op.narratives?.[0] && <p className="text-[13.5px] text-tx2 pt-1.5">{op.narratives[0]}</p>}
                <div className="grid grid-cols-2 gap-2 pt-3">
                  <div className="rounded-xl border border-line1 p-2.5"><b className="block text-[18px]">{n(((op.campaigns ?? []) as { incidents?: number }[]).reduce((s, x) => s + (x.incidents ?? 0), 0))}</b><span className="text-[12px] text-tx3">materiałów</span></div>
                  <div className="rounded-xl border border-line1 p-2.5"><b className="block text-[18px]">{op.campaigns?.length ?? 0}</b><span className="text-[12px] text-tx3">kampanie</span></div>
                </div>
                {(op.shared?.length ?? 0) > 0 && <>
                  <h3 className="text-[12.5px] text-tx3 pt-3 pb-1.5">Rozpoznajemy go po</h3>
                  <div className="flex flex-wrap gap-1.5">{(op.shared ?? []).map((e, i) => <span key={i} className="inline-flex items-center min-h-8 py-1 px-3 rounded-2xl bg-bg3 font-mono text-[12.5px] max-w-full break-all">{prettyDisplay(e.display)}</span>)}</div>
                </>}
                {others.length > 0 && <>
                  <h3 className="text-[12.5px] text-tx3 pt-3">Prowadzi też</h3>
                  {others.map((o) => <Link key={o.id} href={`/kampanie/${o.id}`} className="flex justify-between py-2 border-b border-bg4 last:border-0 hover:underline"><b className="text-[14px]">{o.id} {campaignTitle({ id: o.id, name: o.name })}</b><span className="font-mono text-[13px]">{o.incidents}</span></Link>)}
                </>}
              </Card>
            )}
            {persons.length > 0 && (
              <Card title="Kogo udaje">
                {persons.map((p) => (
                  <Link key={p.name} href={`/slad/osoba/${encodeURIComponent(p.name)}`} className="flex items-center gap-3 py-2.5 border-b border-bg4 last:border-0 hover:bg-bg2 -mx-2 px-2 rounded-lg">
                    <Initials name={personName(p.name)} /><span className="flex-1"><b className="block text-[14px] font-semibold">{personName(p.name)}</b>{p.role && <span className="text-[12.5px] text-tx3">{p.role}</span>}</span>
                    <span className="font-mono text-[13px]">{p.count}</span>
                  </Link>
                ))}
              </Card>
            )}
          </div>
        </div>
      </Page>
    </JellyRoot>
  );
}
