'use client';
// Board 14 · Ślad: what Sprawdź shows for a single trace (domain, pixel, person, kit path).
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import type { CampaignSummary, IncidentSummary, TraceData } from '@/lib/contracts';
import { apiGet, useApi } from '@/lib/api';
import { fmtDate, n, p2, plural } from '@/lib/copy';
import { campaignTitle, personName } from '@/lib/graph';
import { JellyRoot } from '@/components/jelly';
import { CheckField } from '@/components/check-field';
import { Bars, Card, Empty, Loading } from '@/components/ui';
import { IChevR } from '@/components/icons';

const API_TYPE: Record<string, string> = { domena: 'domain', osoba: 'person', piksel: 'pixel', kit: 'kit' };
const TYPE_LABEL: Record<string, string> = { domena: 'domena', osoba: 'osoba', piksel: 'piksel', kit: 'kit', domain: 'domena', person: 'osoba', pixel: 'piksel', tracking: 'tracking', infra: 'infra', content: 'treść' };
const WHERE: Record<string, string> = { incydenty: 'materiały', incidents: 'materiały', ads: 'reklamy', landings: 'strony', domains: 'domeny' };

type Raw = { campaigns: { id?: string; name?: string; n?: number; count?: number; narrative?: string }[]; usage?: { label?: string; n?: number; where?: string; count?: number }[]; co_traces?: { type: string; value: string; label?: string; n?: number; count?: number }[] };
type Detail = { id: string; media?: { faces?: { identity?: string | null; score?: number | null; source?: string | null }[] } | null; content?: { persons?: string[] | null } | null; ad?: { text?: string | null; persons?: string[] | null } | null };

/** Polish names decline (Rafał Brzoska → Rafała Brzoskę): match each word by its stem. */
function mentions(text: string, name: string): boolean {
  const t = text.toLowerCase();
  return name.toLowerCase().split(/\s+/).filter(Boolean).every((w) => {
    const stem = w.slice(0, Math.max(4, w.length - 2));
    return new RegExp(`(^|[^\\p{L}])${stem.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`, 'u').test(t);
  });
}

/** How a person is used: campaigns + counts, the headlines naming them (as captured), first / last seen, face matches. */
function PersonUsage({ name, t, names }: { name: string; t: TraceData; names: Record<string, string> }) {
  const latest = t.latest ?? [];
  const [details, setDetails] = useState<Detail[]>([]);
  useEffect(() => {
    let live = true;
    Promise.all(latest.slice(0, 12).map((m) => apiGet<Detail>(`/incidents/${encodeURIComponent(m.id)}`).catch(() => null)))
      .then((r) => { if (live) setDetails(r.filter(Boolean) as Detail[]); });
    return () => { live = false; };
  }, [latest]);
  const lower = name.toLowerCase();
  const faces = details.flatMap((d) => (d.media?.faces ?? []).filter((f) => (f.identity ?? '').toLowerCase() === lower).map((f) => ({ id: d.id, score: f.score ?? 0, source: f.source })));
  const inText = details.filter((d) => (d.content?.persons ?? []).some((p) => p.toLowerCase() === lower)).length;
  const headlines = [...new Set(latest.map((m) => m.title?.trim()).filter((x): x is string => !!x && mentions(x, name)))].slice(0, 3);
  const dates = latest.map((m) => m.captured_at).filter(Boolean).map(String).sort();
  const scores = faces.map((f) => f.score).sort((a, b) => a - b);
  const camps = (t.campaigns as Raw['campaigns']).filter((c) => c.id);
  return (
    <Card title="Jak go wykorzystują">
      <ul className="m-0 p-0 list-none flex flex-col gap-3 text-[14px] leading-normal">
        {camps.length > 0 && (
          <li>
            <span className="block text-[12.5px] text-tx3">W kampaniach</span>
            {camps.map((c) => <span key={c.id} className="block"><Link href={`/kampanie/${encodeURIComponent(c.id!)}`} className="font-semibold hover:underline">{names[c.id!] ?? c.id}</Link> · {plural(c.n ?? c.count ?? 0, 'materiał', 'materiały', 'materiałów')}</span>)}
          </li>
        )}
        {headlines.length > 0 && (
          <li>
            <span className="block text-[12.5px] text-tx3">Nagłówki z tym nazwiskiem</span>
            {headlines.map((h) => <q key={h} className="block text-tx1 [quotes:none] before:content-['„'] after:content-['”']">{h}</q>)}
          </li>
        )}
        {(inText > 0 || faces.length > 0) && (
          <li>
            <span className="block text-[12.5px] text-tx3">Rozpoznanie</span>
            {inText > 0 && <span className="block">Nazwisko w treści strony: {plural(inText, 'materiał', 'materiały', 'materiałów')}</span>}
            {faces.length > 0 && <span className="block">Twarz rozpoznana: {plural(faces.length, 'materiał', 'materiały', 'materiałów')} · podobieństwo {scores.length > 1 && scores[0] !== scores[scores.length - 1] ? `${p2(scores[0])}–${p2(scores[scores.length - 1])}` : p2(scores[0])}{faces.some((f) => f.source === 'ad_screenshot') ? ' · w reklamie' : ''}</span>}
          </li>
        )}
        {dates.length > 0 && (
          <li>
            <span className="block text-[12.5px] text-tx3">W materiałach</span>
            <span className="block">pierwszy raz {fmtDate(dates[0])}{dates.length > 1 ? ` · ostatnio ${fmtDate(dates[dates.length - 1])}` : ''}</span>
          </li>
        )}
      </ul>
    </Card>
  );
}

export default function SladPage() {
  const { type, value: raw } = useParams<{ type: string; value: string }>();
  const value = decodeURIComponent(raw);
  // the engine stores names and domains lower-case
  const apiValue = type === 'osoba' || type === 'domena' ? value.toLowerCase() : value;
  const { data, error, loading } = useApi<TraceData>(`/traces/${API_TYPE[type] ?? type}/${encodeURIComponent(apiValue)}`);
  const list = useApi<CampaignSummary[]>('/campaigns').data;
  const names = useMemo(() => Object.fromEntries((list ?? []).map((c) => [c.id, `${c.id} ${campaignTitle(c)}`])) as Record<string, string>, [list]);
  const t = data;
  const r = t as unknown as Raw | undefined;
  const isPerson = type === 'osoba' || t?.type === 'person';
  const total = r?.campaigns?.reduce((a, c) => a + (c.n ?? c.count ?? 0), 0) || t?.latest?.length || 0;
  const nCamp = r?.campaigns?.filter((c) => c.id).length ?? 0;
  const weekly = t?.weekly ?? [];
  const wlabels = weekly.map((_, i) => (i === weekly.length - 1 ? 'ten tydzień' : i % 3 === 0 ? fmtDate(new Date(Date.now() - (weekly.length - 1 - i) * 7 * 864e5).toISOString(), false).slice(0, 5) : ''));
  const dates = (t?.latest ?? []).map((m) => m.captured_at).filter(Boolean).map(String).sort();
  const seen = { first: dates[0], last: dates[dates.length - 1] };
  const usage = (r?.usage ?? []).map((u) => ({ label: u.label?.trim() || (u.where ? WHERE[u.where] ?? u.where : ''), n: u.n ?? u.count ?? 0 })).filter((u) => u.label);

  return (
    <div className="flex-1 flex flex-col">
      <JellyRoot mode="field" fieldState="awake" wakeKey={1} className="h-[380px] w-full flex items-center justify-center px-4">
        <div data-jelly-clear className="relative z-[4] w-full max-w-[680px]"><CheckField initial={value} compact /></div>
      </JellyRoot>
      <main className="w-full max-w-[1240px] mx-auto px-4 sm:px-6 pb-10 flex flex-col gap-6">
        {loading && <Loading />}
        {error && !t && <Empty>Nie znamy jeszcze tego śladu. Spróbuj z linkiem albo zrzutem, boty sprawdzą materiał.</Empty>}
        {t && (
          <>
            <section className="flex flex-col gap-2.5">
              <span className="pill bg-bg3 text-tx1 self-start">Ślad · {TYPE_LABEL[t.type] ?? TYPE_LABEL[type] ?? type}</span>
              <h1 className="text-[34px] sm:text-[42px] font-semibold tracking-[-0.04em] leading-[1.05] break-words">{t.title ?? (isPerson ? personName(t.value) : t.value)}</h1>
              {t.description && <p className="max-w-[720px] text-[17px] text-tx2">{t.description}</p>}
              <span className="font-mono text-[12.5px] text-tx4">{plural(total, 'materiał', 'materiały', 'materiałów')} · {nCamp} {nCamp === 1 ? 'kampania' : nCamp >= 2 && nCamp <= 4 ? 'kampanie' : 'kampanii'}{seen.first ? ` · pierwszy raz ${fmtDate(seen.first)}` : ''}{seen.last && seen.last !== seen.first ? ` · ostatni ${fmtDate(seen.last)}` : ''}</span>
            </section>
            <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-6 items-start">
              <div className="flex flex-col gap-6 min-w-0">
                <Card title="W kampaniach" id="sl-c">
                  {(r?.campaigns ?? []).map((c, i) => {
                    const inner = (
                      <>
                        <span className="flex-1 min-w-0"><b className="block text-[14.5px] font-semibold">{c.id ? names[c.id] ?? `${c.id} ${campaignTitle({ id: c.id, name: c.name ?? '' })}` : c.name}</b>{c.narrative && <span className="block text-[13px] text-tx3 truncate">{c.narrative}</span>}</span>
                        <b className="font-mono text-[14px]">{c.n ?? c.count}</b>
                        {c.id ? <IChevR className="text-tx4" /> : <span className="w-4" />}
                      </>
                    );
                    return c.id
                      ? <Link key={i} href={`/kampanie/${c.id}`} className="flex items-center gap-3 py-3 border-b border-bg4 last:border-0 hover:bg-bg2 -mx-2 px-2 rounded-lg">{inner}</Link>
                      : <div key={i} className="flex items-center gap-3 py-3 border-b border-bg4 last:border-0 -mx-2 px-2 text-tx2">{inner}</div>;
                  })}
                  {!t.campaigns?.length && <Empty>Nie występuje w żadnej znanej kampanii.</Empty>}
                </Card>
                {weekly.some((x) => x > 0) && <Card title="Materiały tygodniowo"><Bars data={weekly} labels={wlabels} label={`Materiały tygodniowo: ${weekly.join(', ')}`} /></Card>}
                <Card title={isPerson ? 'Materiały z tą osobą' : 'Ostatnie materiały'}>
                  {(t.latest ?? []).map((m: IncidentSummary) => (
                    <Link key={m.id} href={`/analiza/${m.id}`} className="flex items-center gap-3 py-2.5 border-b border-bg4 last:border-0 text-[13.5px] hover:bg-bg2 -mx-2 px-2 rounded-lg">
                      <span className="flex-1 min-w-0"><b className="block font-semibold truncate">{m.title || m.domain || m.id}</b><span className="block font-mono text-[12px] text-tx3 truncate">{[m.id, m.title ? m.domain : null, m.campaign_id ?? 'bez kampanii'].filter(Boolean).join(' · ')}</span></span>
                      <span className="text-tx3 text-[12.5px] flex-none">{fmtDate(m.captured_at)}</span>
                    </Link>
                  ))}
                  {!t.latest?.length && <Empty>Brak materiałów z tym śladem.</Empty>}
                </Card>
              </div>
              <div className="flex flex-col gap-6 min-w-0">
                {isPerson ? <PersonUsage name={t.value} t={t} names={names} /> : usage.length > 0 && (
                  <Card title="Gdzie występuje">
                    <ul className="m-0 p-0 list-none flex flex-col gap-1.5 text-[14px]">{usage.map((u) => <li key={u.label} className="flex justify-between gap-3"><span>{u.label}</span><b className="font-mono">{n(u.n)}</b></li>)}</ul>
                  </Card>
                )}
                {(r?.co_traces ?? []).length > 0 && (
                  <Card title="Często razem z">
                    <div className="flex flex-wrap gap-2">
                      {(r?.co_traces ?? []).map((c) => {
                        const tp = c.type === 'osoba' || c.type === 'person' ? 'osoba' : c.type === 'domena' || c.type === 'domain' ? 'domena' : c.type === 'pixel' ? 'piksel' : null;
                        const body = <><span className="break-all">{c.label ?? c.value}</span> <span className="text-[11px] text-tx4">{TYPE_LABEL[c.type] ?? c.type}</span></>;
                        return tp ? <Link key={c.type + c.value} href={`/slad/${tp}/${encodeURIComponent(c.value)}`} className="chip !h-auto min-h-8 py-1">{body}</Link> : <span key={c.type + c.value} className="chip !cursor-default !h-auto min-h-8 py-1">{body}</span>;
                      })}
                    </div>
                  </Card>
                )}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
