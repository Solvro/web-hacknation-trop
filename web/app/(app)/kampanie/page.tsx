'use client';
// Board 5 · Kampanie: list grouped by operator, Oracle strip, merge strip, filters, "Kogo udają".
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useMemo } from 'react';
import type { CampaignSummary, Operator, OraclePrediction } from '@/lib/contracts';
import { useApi } from '@/lib/api';
import { n, p2, plOnly } from '@/lib/copy';
import { campaignTitle, personName } from '@/lib/graph';
import { Initials, Loading, Page, Sparkline } from '@/components/ui';
import { IChevR } from '@/components/icons';

type F = 'all' | 'grow' | 'new' | 'unreported' | 'update';
const FILTERS: { k: F; label: string; test: (c: CampaignSummary) => boolean }[] = [
  { k: 'all', label: 'Wszystkie', test: () => true },
  { k: 'grow', label: 'Rosną', test: (c) => (c.heat?.trend_pct ?? 0) > 5 },
  { k: 'new', label: 'Nowe', test: (c) => c.status === 'candidate' },
  { k: 'unreported', label: 'Niezgłoszone', test: (c) => (c.report_status ?? 'none') === 'none' },
  { k: 'update', label: 'Do uzupełnienia', test: (c) => c.report_status === 'needs_update' },
];

function mergeHint(c: CampaignSummary, all: CampaignSummary[]): string | null {
  if (c.merge_hint) return c.merge_hint;
  if (c.status === 'candidate' && c.operator_id && /scal|wariant/i.test(`${c.name} ${c.narrative}`)) {
    const big = all.filter((x) => x.operator_id === c.operator_id && x.id !== c.id).sort((a, b) => (b.n_incidents ?? 0) - (a.n_incidents ?? 0))[0];
    return big?.id ?? null;
  }
  return null;
}

function Report({ c, hint }: { c: CampaignSummary; hint: string | null }) {
  if (hint) return <Link href={`/kampanie/scal?a=${hint}&b=${c.id}`} className="pill bg-state-vdim text-state-violet hover:underline">może to {hint}? scal</Link>;
  if (c.status === 'candidate' && !c.operator_id) return <Link href={`/kampanie/${c.id}`} className="pill bg-state-cdim text-state-cyan hover:underline">nowa kampania? potwierdź</Link>;
  switch (c.report_status) {
    case 'sent': return <span className="pill bg-state-gdim text-state-g">zgłoszona</span>;
    case 'needs_update': return <span className="pill bg-[#FFF1E6] text-[#C2410C]">do uzupełnienia</span>;
    case 'draft': return <span className="pill bg-state-adim text-state-amber">szkic zgłoszenia</span>;
    default: return <span className="pill bg-bg3 text-tx2">niezgłoszona</span>;
  }
}

function Kampanie() {
  const sp = useSearchParams();
  const router = useRouter();
  const { data: list, loading } = useApi<CampaignSummary[]>('/campaigns');
  const oracle = useApi<OraclePrediction[]>('/oracle/predictions?status=predicted').data;
  const f = (sp.get('f') as F) ?? 'all';
  const osoba = sp.get('osoba');
  const all = list ?? [];
  const opIds = useMemo(() => [...new Set(all.map((c) => c.operator_id).filter(Boolean))] as string[], [all]);
  const ops = useApi<Operator[]>(opIds.length ? '/operators' : null).data;
  const opName = (id: string) => { const o = (ops ?? []).find?.((x) => x.id === id); return o ? `${id} «${o.codename}»` : id; };

  const set = (k: string, v: string | null) => {
    const q = new URLSearchParams(sp.toString());
    if (v == null) q.delete(k); else q.set(k, v);
    router.replace(`/kampanie?${q}`, { scroll: false });
  };
  const persons = useMemo(() => {
    const m = new Map<string, number>();
    for (const c of all) for (const p of c.persons ?? []) m.set(p, (m.get(p) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
  }, [all]);
  const shown = all.filter((c) => FILTERS.find((x) => x.k === f)!.test(c) && (!osoba || (c.persons ?? []).includes(osoba)));
  const groups = useMemo(() => {
    const g = new Map<string, CampaignSummary[]>();
    for (const c of shown) { const k = c.operator_id ?? ''; g.set(k, [...(g.get(k) ?? []), c]); }
    return [...g.entries()].sort((a, b) => (a[0] ? 0 : 1) - (b[0] ? 0 : 1) || b[1].reduce((s, c) => s + (c.n_incidents ?? 0), 0) - a[1].reduce((s, c) => s + (c.n_incidents ?? 0), 0));
  }, [shown]);
  const merge = all.map((c) => [c, mergeHint(c, all)] as const).find(([, h]) => h);
  const predicted = (oracle ?? []).filter((o) => o.status === 'predicted' && (o.dna_score ?? 0) >= 0.6).slice(0, 3);

  return (
    <Page>
      <h1 className="text-[36px] sm:text-[42px] font-semibold tracking-[-0.04em] leading-none pt-3">Kampanie</h1>
      {predicted.length > 0 && (
        <section aria-label="Oracle" className="rounded-[22px] border border-[#E9E3FF] bg-[#FAF8FF] p-5 flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className="pill bg-white border border-[#DDD3FF] text-state-violet">Oracle · dziś w nocy</span>
            <b className="text-[16px] font-semibold">{predicted.length} nowe domeny pasują do znanych kampanii lub ich zestawów, zanim pojawiła się reklama</b>
          </div>
          <div className="flex flex-wrap gap-2">
            {predicted.map((o) => (
              <Link key={o.domain} href={`/slad/domena/${o.domain}`} className="inline-flex items-center gap-2 h-10 px-3 rounded-xl border border-line1 bg-white font-mono text-[13px] hover:border-line3">
                {o.domain} <span className="text-tx4">→</span> <b className="text-state-violet font-semibold">{all.some((c) => c.id === o.campaign_id) ? o.campaign_id : `rodzina ${o.campaign_id ?? '?'}`} · {p2(o.dna_score)}</b>
              </Link>
            ))}
          </div>
        </section>
      )}
      {merge && (
        <section className="rounded-[22px] bg-bg3 px-5 py-4 flex flex-wrap items-center justify-between gap-3">
          <div><b className="block text-[15px]">{merge[1]} i {merge[0].id} wyglądają na jedną kampanię</b><span className="text-[13px] text-tx2">Te same ślady techniczne i wspólne domeny, różni je tylko format reklam.</span></div>
          <Link href={`/kampanie/scal?a=${merge[1]}&b=${merge[0].id}`} className="text-[14px] font-semibold underline decoration-line2 underline-offset-4">Porównaj i scal</Link>
        </section>
      )}
      <div className="flex flex-col gap-3">
        <div className="seg self-start flex-wrap" role="group" aria-label="Filtr kampanii">
          {FILTERS.map((x) => (
            <button key={x.k} type="button" aria-pressed={f === x.k} onClick={() => set('f', x.k === 'all' ? null : x.k)}>
              {x.label} <span className="text-[11px] text-tx4">{all.filter(x.test).length}</span>
            </button>
          ))}
        </div>
        {persons.length > 0 && (
          <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Kogo udają">
            <span className="text-[13px] text-tx3 mr-1">Kogo udają</span>
            {persons.map(([p, k]) => (
              <button key={p} type="button" className="chip !pl-1" aria-pressed={osoba === p} onClick={() => set('osoba', osoba === p ? null : p)}>
                <Initials name={personName(p)} />{personName(p)} <span className="text-[11px] opacity-70">{k}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      {loading && <Loading />}
      <div className="overflow-x-auto -mx-4 px-4">
        <table className="w-full min-w-[860px] border-collapse text-left">
          <thead>
            <tr className="text-[12.5px] text-tx3 border-b border-line1">
              <th className="font-normal py-2.5 px-2 w-[36%]">Kampania</th><th className="font-normal px-2">14 dni</th><th className="font-normal px-2">Materiały</th>
              <th className="font-normal px-2">Domeny</th><th className="font-normal px-2">Zgłoszenie</th><th className="w-6" />
            </tr>
          </thead>
          {groups.map(([op, cs]) => (
            <tbody key={op || 'none'}>
              <tr className="border-b border-line1"><th colSpan={6} className="text-left py-3 px-2 text-[14px] font-semibold">
                {op ? opName(op) : 'Bez operatora'}
                <span className="font-normal text-[12.5px] text-tx3 ml-2">{op ? (cs.length === 1 ? 'operator · 1 kampania' : '') : 'za mało śladów, żeby powiązać'}</span>
              </th></tr>
              {cs.map((c) => {
                const t = c.heat?.trend_pct ?? 0;
                const hint = mergeHint(c, all);
                return (
                  <tr key={c.id} className="border-b border-line1 hover:bg-bg2 cursor-pointer" onClick={() => router.push(`/kampanie/${c.id}`)}>
                    <td className="py-3.5 px-2"><Link href={`/kampanie/${c.id}`} className="block text-[16px] font-semibold tracking-[-0.01em]" onClick={(e) => e.stopPropagation()}>{c.id} {campaignTitle(c)}</Link><span className="text-[13px] text-tx3">{plOnly(c.narrative)}</span></td>
                    <td className="px-2"><Sparkline data={c.heat?.series_14d ?? []} dashedEmpty label={`Materiały w 14 dni: ${(c.heat?.series_14d ?? []).join(', ')}`} /></td>
                    <td className="px-2"><b className="block text-[18px] font-semibold">{n(c.n_incidents)}</b>
                      <span className={'text-[12.5px] ' + (c.status === 'candidate' && !c.operator_id ? 'text-state-cyan' : t > 5 ? 'text-state-red' : 'text-tx3')}>{c.status === 'candidate' ? (c.operator_id ? 'od wczoraj' : 'nowa dziś') : t > 0 ? `+${Math.round(t)}% w 48 h` : t < 0 ? `${Math.round(t)}% w tygodniu` : 'bez zmian'}</span></td>
                    <td className="px-2"><b className="block text-[14px] font-semibold">{n(c.n_domains)} domen</b><span className="text-[12.5px] text-tx3">{[c.new_domains_24h ? `${c.new_domains_24h} nowe dziś` : '', c.predicted_domains ? `${c.predicted_domains} przewidziana` : ''].filter(Boolean).join(' · ') || 'bez zmian'}</span></td>
                    <td className="px-2" onClick={(e) => e.stopPropagation()}><Report c={c} hint={hint} /></td>
                    <td className="px-2 text-tx4"><IChevR /></td>
                  </tr>
                );
              })}
            </tbody>
          ))}
        </table>
      </div>
      {!loading && !shown.length && <p className="text-tx3 text-[14px]">Żadna kampania nie pasuje do filtra.</p>}
    </Page>
  );
}

export default function Page_() {
  return <Suspense fallback={<Loading />}><Kampanie /></Suspense>;
}
