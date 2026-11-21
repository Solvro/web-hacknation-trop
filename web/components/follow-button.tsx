'use client';
// "Śledź dalej": start an investigation from this material. The API derives the pivots from `incident:<id>`
// (landing/chain domains, ad display link, domains named in the video, advertiser); if it does not accept
// incident seeds, fall back to the best domain in the evidence; with neither, the button is not shown.
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import type { EvidenceItem } from '@/lib/contracts';
import { apiPost } from '@/lib/api';
import { IArrow } from './icons';

function bestDomain(evidence: EvidenceItem[], domain?: string | null): string | null {
  for (const e of evidence) {
    if (/^https?:\/\//.test(e.value)) { try { return new URL(e.value).hostname; } catch { /* next */ } }
  }
  const d = evidence.find((e) => e.type === 'infra' && /^[a-z0-9-]+(\.[a-z0-9-]+)+$/i.test(e.value));
  return d?.value ?? domain ?? null;
}

export function FollowButton({ incidentId, evidence = [], domain, campaignId, variant = 'pri' }: { incidentId?: string | null; evidence?: EvidenceItem[]; domain?: string | null; campaignId?: string | null; variant?: 'pri' | 'sec' }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const fallback = bestDomain(evidence, domain);
  if (!incidentId && !fallback) return null;
  async function go() {
    setBusy(true); setErr(null);
    const body = (seed: string) => ({ seed, campaign_id: campaignId ?? undefined, budget_steps: 20 });
    let r: { id: string } | null = null;
    if (incidentId) r = await apiPost<{ id: string }>('/investigations', body(`incident:${incidentId}`), () => ({ id: 'INV-7' })).catch(() => null);
    if (!r && fallback) r = await apiPost<{ id: string }>('/investigations', body(fallback), () => ({ id: 'INV-7' })).catch(() => null);
    if (!r) { setErr('Nie udało się uruchomić śledztwa.'); setBusy(false); return; }
    router.push(`/sledztwa/${encodeURIComponent(r.id)}${campaignId ? `?kampania=${encodeURIComponent(campaignId)}` : ''}`);
  }
  return (
    <span className="inline-flex flex-col items-start sm:items-end gap-1">
      <button type="button" className={variant === 'pri' ? 'btn-pri' : 'btn-sec'} onClick={go} disabled={busy} title="Agent szuka kolejnych domen, reklam i reklamodawców z tymi samymi śladami">
        {busy ? 'Uruchamiam agenta…' : 'Śledź dalej'}<IArrow />
      </button>
      {err && <span role="alert" className="text-[12.5px] text-state-red">{err}</span>}
    </span>
  );
}
