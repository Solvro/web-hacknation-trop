'use client';
// Board 8 · Scal kampanie: two cards, which name stays, what links them, before → after, undoable.
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useState } from 'react';
import type { CampaignSummary, MergePreview } from '@/lib/contracts';
import { apiPost, useApi } from '@/lib/api';
import { botColor, botName, LAYER_LABEL, n, prettyDisplay } from '@/lib/copy';
import { campaignTitle } from '@/lib/graph';
import { Bot, JellyRoot } from '@/components/jelly';
import { ReportHeader } from '@/components/analysis/report';
import { Card, Crumbs, Empty, Loading, Page } from '@/components/ui';
import { IArrow } from '@/components/icons';

function Side({ c, keep, onKeep, tag }: { c: CampaignSummary; keep: boolean; onKeep: () => void; tag: string }) {
  return (
    <label className={'flex-1 rounded-[22px] p-5 flex flex-col gap-2 cursor-pointer bg-bg1 ' + (keep ? 'border-2 border-tx1' : 'border border-line1 shadow-soft')}>
      <span className="flex items-center gap-2 text-[13px]"><input type="radio" name="keep" checked={keep} onChange={onKeep} className="w-4 h-4 accent-black" />Zostaw tę nazwę</span>
      <b className="text-[19px] font-semibold tracking-[-0.02em]">{c.id} {campaignTitle(c)}</b>
      <span className="text-[13px] text-tx3">{c.narrative}</span>
      <span className="text-[13.5px] pt-1"><b>{n(c.n_incidents)}</b> materiałów &nbsp; <b>{n(c.n_domains)}</b> domen</span>
      <span className="pill bg-bg3 text-tx1 self-start">{tag}</span>
    </label>
  );
}

function Scal() {
  const sp = useSearchParams();
  const router = useRouter();
  const a = sp.get('a') ?? '';
  const b = sp.get('b') ?? '';
  const { data: m, loading } = useApi<MergePreview>(a && b ? `/campaigns/${encodeURIComponent(a)}/merge-preview?other=${encodeURIComponent(b)}` : null);
  const [keep, setKeep] = useState<'self' | 'other'>('self');
  const [busy, setBusy] = useState(false);
  if (loading) return <Loading />;
  if (!m) return <Page><Empty>{a && b ? `Nie da się porównać ${a} i ${b}.` : 'Wybierz dwie kampanie do scalenia na liście Kampanie.'} <Link className="underline" href="/kampanie">Kampanie</Link></Empty></Page>;
  const A = m.a, B = m.b;
  if (A.id === B.id) return <Page><Crumbs items={[{ label: 'Kampanie', href: '/kampanie' }, { label: 'Scal kampanie' }]} /><Empty>{a} i {b} są już jedną kampanią ({A.id}). <Link className="underline" href={`/kampanie/${A.id}`}>Otwórz {A.id}</Link></Empty></Page>;
  const after = m.after ?? {};
  const rows: [string, number, number, number | string][] = [
    ['materiały', A.n_incidents ?? 0, B.n_incidents ?? 0, after.materials ?? after[A.id] ?? (A.n_incidents ?? 0) + (B.n_incidents ?? 0)],
    ['domeny, bez powtórzeń', A.n_domains ?? 0, B.n_domains ?? 0, after.domains ?? '—'],
  ];
  if (after.advertisers != null) rows.push(['reklamodawcy', m.before.advertisers_a ?? 0, m.before.advertisers_b ?? 0, after.advertisers]);
  async function merge() {
    setBusy(true);
    const target = keep === 'self' ? A.id : B.id;
    await apiPost(`/campaigns/${encodeURIComponent(A.id)}/merge`, { other_id: B.id, keep }, () => ({ id: target })).catch(() => null);
    router.push(`/kampanie/${target}?scalono=${keep === 'self' ? B.id : A.id}`);
  }
  return (
    <JellyRoot className="flex-1 flex flex-col">
      <Page>
        <Crumbs items={[{ label: 'Kampanie', href: '/kampanie' }, { label: 'Scal kampanie' }]} />
        <ReportHeader
          title="Scal dwie kampanie w jedną"
          lead="Boty uważają, że to jedna kampania: te same ślady techniczne i te same domeny. Różni je tylko format reklam."
          meta={`${A.id} ${campaignTitle(A)} + ${B.id} ${campaignTitle(B)}${A.operator_id && A.operator_id === B.operator_id ? ` · ten sam operator ${A.operator_id}` : ''}`}
          primary={<button type="button" className="btn-pri" onClick={merge} disabled={busy}>{busy ? 'Scalam…' : 'Scal kampanie'}<IArrow /></button>}
          secondary={<Link className="lnk" href={`/kampanie/${A.id}`}>albo zostaw osobno</Link>}
        />
        <div className="flex flex-col md:flex-row items-stretch gap-3" role="radiogroup" aria-label="Która nazwa zostaje">
          <Side c={A} keep={keep === 'self'} onKeep={() => setKeep('self')} tag="tekst i zdjęcia" />
          <span aria-hidden="true" className="self-center w-8 h-8 rounded-full bg-bg3 inline-flex items-center justify-center text-tx2">+</span>
          <Side c={B} keep={keep === 'other'} onKeep={() => setKeep('other')} tag={/wideo|nagran|deepfake/i.test(`${B.name} ${B.narrative}`) ? 'wideo z deepfake' : 'inny format'} />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-6 items-start">
          <section aria-labelledby="s-why" className="flex flex-col gap-2.5">
            <h2 id="s-why" className="text-[16px] font-semibold">Co je łączy</h2>
            {m.shared.map((e, i) => {
              const diff = e.state === 'conflict';
              return (
                <div key={i} className={'min-h-16 flex items-center gap-3 pl-3.5 pr-4 py-2.5 border rounded-[18px] ' + (diff ? 'border-dashed border-line1 bg-bg2' : 'border-line1 bg-bg1 shadow-soft')}>
                  <Bot color={botColor(e.bot)} size={34} />
                  <span className="flex-1 min-w-0"><b className={'block text-[14.5px] font-semibold ' + (diff ? 'text-tx2' : '')}>{prettyDisplay(e.display)}</b><span className="text-[12.5px] text-tx3">{botName(e.bot)} · {LAYER_LABEL[e.type].toLowerCase()}{diff ? ' · jedyna różnica' : ''}</span></span>
                  {!diff && e.N ? <b className="font-mono text-[14px]">{(e.N ?? 0) <= 200 ? `${e.df} z ${e.N}` : `${n(e.df ?? 0)}/${n(e.N)}`}</b> : null}
                </div>
              );
            })}
          </section>
          <div className="flex flex-col gap-4">
            <Card title="Po scaleniu">
              {rows.map(([l, x, y, z]) => (
                <div key={l} className="flex justify-between items-center py-2.5 border-b border-bg4 last:border-0 text-[14px]">
                  <span>{l}</span><span className="font-mono"><span className="text-tx4">{x} + {y} → </span><b>{z}</b></span>
                </div>
              ))}
            </Card>
            <section className="rounded-[18px] bg-bg3 p-4"><b className="block text-[14.5px]">{n(B.n_incidents)} materiałów trafi do uzupełnienia zgłoszenia</b><span className="text-[13px] text-tx2">Dzisiejsze zgłoszenie {A.id} obejmie też reklamy z {B.id}.</span></section>
            <p className="text-[12.5px] text-tx3 px-1">Scalenie można cofnąć. Historia obu kampanii zostaje zapisana.</p>
          </div>
        </div>
      </Page>
    </JellyRoot>
  );
}

export default function ScalPage() {
  return <Suspense fallback={<Loading />}><Scal /></Suspense>;
}
