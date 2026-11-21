'use client';
// Real traces for the "Domena lub osoba" chip: people impersonated in the most campaigns + a domain of the biggest
// campaign, all taken from the API so /slad resolves them with real results.
import { useMemo } from 'react';
import type { CampaignSummary, Indicators } from './contracts';
import { useApi, useHealth } from './api';
import { personName } from './graph';

export function useTraceExamples(): string[] {
  const { demo } = useHealth();
  const camps = useApi<CampaignSummary[]>(demo ? null : '/campaigns').data;
  const top = useMemo(() => [...(camps ?? [])].sort((a, b) => (b.n_incidents ?? 0) - (a.n_incidents ?? 0))[0], [camps]);
  const ind = useApi<Indicators>(top ? `/campaigns/${encodeURIComponent(top.id)}/indicators` : null).data;
  return useMemo(() => {
    if (demo) return ['Jan Kowalski', 'morvanta.click'];
    const count = new Map<string, number>();
    for (const c of camps ?? []) for (const p of c.persons ?? []) count.set(p, (count.get(p) ?? 0) + 1 + (c.id === top?.id ? 0.5 : 0));
    const persons = [...count.entries()].sort((a, b) => b[1] - a[1]).slice(0, 2).map(([p]) => personName(p));
    const domain = ind?.domains?.find((d) => (d.ads_seen ?? 0) > 0)?.fqdn ?? ind?.domains?.[0]?.fqdn;
    return [persons[0], domain, persons[1]].filter(Boolean) as string[];
  }, [demo, camps, ind, top]);
}
