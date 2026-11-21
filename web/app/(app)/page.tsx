'use client';
// Board 1 · Pole: the only zgrai-style screen. One field, sleeping bots around it, plus a few real materials from
// the database the jury can open straight away.
import Link from 'next/link';
import { useMemo, useState } from 'react';
import type { CampaignSummary, IncidentSummary } from '@/lib/contracts';
import { useApi, useHealth } from '@/lib/api';
import { campaignTitle } from '@/lib/graph';
import { JellyRoot } from '@/components/jelly';
import { CheckField, DEMO_URL } from '@/components/check-field';
import { IArrow } from '@/components/icons';

function Samples() {
  const inc = useApi<IncidentSummary[] | { items: IncidentSummary[] }>('/incidents?limit=200').data;
  const camps = useApi<CampaignSummary[]>('/campaigns').data;
  const picks = useMemo(() => {
    const list = Array.isArray(inc) ? inc : inc?.items ?? [];
    const seen = new Set<string>();
    const out: IncidentSummary[] = [];
    for (const i of list) {
      if (!i.campaign_id || seen.has(i.campaign_id) || !(i.title || i.domain)) continue;
      seen.add(i.campaign_id);
      out.push(i);
      if (out.length === 3) break;
    }
    return out;
  }, [inc]);
  if (!picks.length) return null;
  const name = (id?: string | null) => campaignTitle(camps?.find((c) => c.id === id)) || id;
  return (
    <section aria-labelledby="pr-h" className="w-full flex flex-col gap-2 text-left">
      <h2 id="pr-h" className="text-[13px] font-medium text-tx3 text-center">Nie masz materiału? Otwórz raport jednego z przeanalizowanych:</h2>
      <ul className="m-0 p-0 list-none flex flex-col gap-2">
        {picks.map((i) => (
          <li key={i.id}>
            <Link href={`/analiza/${encodeURIComponent(i.id)}`} className="flex items-center gap-3 px-4 py-3 rounded-2xl border border-line1 bg-bg1/90 hover:border-line3 shadow-soft">
              <span className="flex-1 min-w-0">
                <span className="block text-[12px] text-tx3">Przykład · {i.id}{i.domain ? ` · ${i.domain}` : ''}</span>
                <span className="block text-[14px] font-semibold truncate">{i.title || i.domain}</span>
                <span className="block text-[12.5px] text-tx3 truncate">{i.campaign_id} {name(i.campaign_id)}</span>
              </span>
              <IArrow className="text-tx3 flex-none" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function SprawdzPage() {
  const [wake, setWake] = useState(0);
  const { demo, health } = useHealth();
  return (
    <JellyRoot mode="field" fieldState="asleep" wakeKey={wake} className="flex-1 flex min-h-[640px]">
      <main className="relative z-[1] flex-1 flex items-center justify-center px-4 sm:px-6 pt-4 pb-[120px]">
        <div data-jelly-clear className="w-full max-w-[680px] flex flex-col items-center gap-[26px] text-center">
          <div className="flex flex-col gap-3 items-center">
            <h1 className="m-0 text-[36px] sm:text-[48px] leading-[1.05] tracking-[-0.04em] font-semibold">Co sprawdzamy?</h1>
            <p className="m-0 max-w-[560px] text-[17px] leading-normal text-tx2">
              Wklej link, wrzuć zrzut, plik HAR albo ZIP z materiałem, albo wpisz ślad: domenę, piksel czy nazwisko. Boty pokażą, do której kampanii to należy i dlaczego.
            </p>
          </div>
          {/* the demo URL only makes sense against the fictional universe */}
          <CheckField key={demo ? 'demo' : 'real'} initial={demo ? DEMO_URL : ''} onWake={() => setWake((w) => w + 1)} />
          {health && !demo && <Samples />}
          {demo && (
            <p className="text-[13px] text-tx3">
              Bez sieci? <Link className="underline decoration-line2 underline-offset-4 hover:text-tx1" href="/analiza/demo?replay=demo">Odtwórz nagraną analizę</Link>
            </p>
          )}
        </div>
      </main>
    </JellyRoot>
  );
}
