'use client';
// Board 14 · Ślad: what Sprawdź shows for a single trace (domain, pixel, person, kit path).
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useState } from 'react';
import type { TraceData } from '@/lib/contracts';
import { useApi } from '@/lib/api';
import { fmtDate, n } from '@/lib/copy';
import { campaignTitle } from '@/lib/graph';
import { JellyRoot } from '@/components/jelly';
import { CheckField } from '@/components/check-field';
import { Bars, Card, Empty, Loading } from '@/components/ui';
import { IChevR } from '@/components/icons';

const API_TYPE: Record<string, string> = { domena: 'domain', osoba: 'person', piksel: 'pixel', kit: 'kit' };
const TYPE_LABEL: Record<string, string> = { domena: 'domena', osoba: 'osoba', piksel: 'piksel', kit: 'kit', domain: 'domena', person: 'osoba', pixel: 'piksel' };

export default function SladPage() {
  const { type, value: raw } = useParams<{ type: string; value: string }>();
  const value = decodeURIComponent(raw);
  const { data, error, loading } = useApi<TraceData>(`/traces/${API_TYPE[type] ?? type}/${encodeURIComponent(value)}`);
  const [wake] = useState(1);
  const t = data;
  const total = t?.campaigns?.reduce((a, c) => a + (c.n ?? 0), 0) ?? 0;
  const nCamp = t?.campaigns?.filter((c) => c.id).length ?? 0;
  const weekly = t?.weekly ?? [];
  const wlabels = weekly.map((_, i) => (i === weekly.length - 1 ? 'ten tydzień' : i % 3 === 0 ? fmtDate(new Date(Date.parse('2026-11-21') - (weekly.length - 1 - i) * 7 * 864e5).toISOString(), false).slice(0, 5) : ''));
  const usageNote = t?.usage?.find((u) => !u.n);
  const usagePills = t?.usage?.filter((u) => u.n) ?? [];

  return (
    <div className="flex-1 flex flex-col">
      <JellyRoot mode="field" fieldState="awake" wakeKey={wake} className="h-[380px] w-full flex items-center justify-center px-4">
        <div data-jelly-clear className="relative z-[4] w-full max-w-[680px]"><CheckField initial={value} compact /></div>
      </JellyRoot>
      <main className="w-full max-w-[1240px] mx-auto px-4 sm:px-6 pb-10 flex flex-col gap-6">
        {loading && <Loading />}
        {error && !t && <Empty>Nie znamy jeszcze tego śladu. Spróbuj z linkiem albo zrzutem, boty sprawdzą materiał.</Empty>}
        {t && (
          <>
            <section className="flex flex-col gap-2.5">
              <span className="pill bg-bg3 text-tx1 self-start">Ślad · {TYPE_LABEL[t.type] ?? TYPE_LABEL[type] ?? type}</span>
              <h1 className="text-[34px] sm:text-[42px] font-semibold tracking-[-0.04em] leading-[1.05] break-words">{t.title ?? t.value}</h1>
              {t.description && <p className="max-w-[720px] text-[17px] text-tx2">{t.description}</p>}
              <span className="font-mono text-[12.5px] text-tx4">{n(total)} materiałów · {nCamp} {nCamp === 1 ? 'kampania' : 'kampanie'}{t.latest?.[0]?.captured_at ? ` · ostatni ${fmtDate(t.latest[0].captured_at)}` : ''}</span>
            </section>
            <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-6 items-start">
              <div className="flex flex-col gap-6">
                <Card title="W kampaniach" id="sl-c">
                  {(t.campaigns ?? []).map((c, i) => {
                    const inner = (
                      <>
                        <span className="flex-1 min-w-0"><b className="block text-[14.5px] font-semibold">{c.id ? `${c.id} ${campaignTitle({ id: c.id, name: c.name })}` : c.name}</b><span className="block text-[13px] text-tx3 truncate">{c.narrative}</span></span>
                        <b className="font-mono text-[14px]">{c.n}</b>
                        {c.id ? <IChevR className="text-tx4" /> : <span className="w-4" />}
                      </>
                    );
                    return c.id
                      ? <Link key={i} href={`/kampanie/${c.id}`} className="flex items-center gap-3 py-3 border-b border-bg4 last:border-0 hover:bg-bg2 -mx-2 px-2 rounded-lg">{inner}</Link>
                      : <div key={i} className="flex items-center gap-3 py-3 border-b border-bg4 last:border-0 -mx-2 px-2 text-tx2">{inner}</div>;
                  })}
                  {!t.campaigns?.length && <Empty>Nie występuje w żadnej znanej kampanii.</Empty>}
                </Card>
                {weekly.length > 0 && <Card title="Materiały tygodniowo"><Bars data={weekly} labels={wlabels} label={`Materiały tygodniowo: ${weekly.join(', ')}`} /></Card>}
                <Card title="Ostatnie materiały">
                  {(t.latest ?? []).map((m) => (
                    <Link key={m.id} href={`/analiza/${m.id}`} className="grid grid-cols-[110px_minmax(0,1fr)_auto] gap-3 items-center py-2.5 border-b border-bg4 last:border-0 text-[13.5px] hover:bg-bg2 -mx-2 px-2 rounded-lg">
                      <b className="font-mono">{m.id}</b><span className="truncate">{[m.domain, m.campaign_id ?? 'bez kampanii'].filter(Boolean).join(' · ')}</span><span className="text-tx3">{fmtDate(m.captured_at)}</span>
                    </Link>
                  ))}
                </Card>
              </div>
              <div className="flex flex-col gap-6">
                <Card title="Jak go wykorzystują">
                  {usageNote && <div className="flex gap-3 pb-3"><span className="ph-img w-16 h-16 flex-none">twarz</span><p className="text-[13.5px] text-tx2">{usageNote.label}</p></div>}
                  <div className="flex flex-wrap gap-2">{usagePills.map((u) => <span key={u.label} className="chip !cursor-default">{u.label}</span>)}</div>
                  {!t.usage?.length && <Empty>Brak opisu.</Empty>}
                </Card>
                <Card title="Często razem z">
                  <div className="flex flex-wrap gap-2">
                    {(t.co_traces ?? []).map((c) => {
                      const tp = c.type === 'osoba' || c.type === 'person' ? 'osoba' : c.type === 'domena' ? 'domena' : null;
                      const body = <>{c.label ?? c.value} <span className="text-[11px] text-tx4">{c.type}</span></>;
                      return tp ? <Link key={c.value} href={`/slad/${tp}/${encodeURIComponent(c.value)}`} className="chip">{body}</Link> : <span key={c.value} className="chip !cursor-default">{body}</span>;
                    })}
                  </div>
                </Card>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
