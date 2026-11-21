'use client';
// Śledztwa: list of investigations and the start form. `?seed=…&kampania=…` (from Raport / Kampania) starts one.
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useRef, useState } from 'react';
import type { Investigation } from '@/lib/contracts';
import { apiPost, useApi } from '@/lib/api';
import { fmtDate } from '@/lib/copy';
import { Card, Empty, Loading, Page } from '@/components/ui';
import { IArrow, IChevR } from '@/components/icons';

const STATUS: Record<string, string> = { running: 'w toku', paused: 'wstrzymane', done: 'zakończone', stopped: 'zatrzymane', error: 'błąd' };

function Sledztwa() {
  const sp = useSearchParams();
  const router = useRouter();
  const { data, loading } = useApi<Investigation[]>('/investigations');
  const [seed, setSeed] = useState(sp.get('seed') || 'morvanta.click');
  const [busy, setBusy] = useState(false);
  const started = useRef(false);

  async function start(s: string) {
    setBusy(true);
    const kampania = sp.get('kampania') || undefined;
    const r = await apiPost<{ id: string }>('/investigations', { seed: s.trim(), campaign_id: kampania, budget_steps: 20 }, () => ({ id: 'INV-7' })).catch(() => ({ id: 'INV-7' }));
    router.push(`/sledztwa/${encodeURIComponent(r.id)}${kampania ? `?kampania=${kampania}` : ''}`);
  }
  useEffect(() => {
    const s = sp.get('seed');
    if (s && !started.current) { started.current = true; start(s); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sp]);

  return (
    <Page>
      <h1 className="text-[36px] sm:text-[42px] font-semibold tracking-[-0.04em] leading-none pt-3">Śledztwa</h1>
      <p className="text-[16px] text-tx2 max-w-[720px] -mt-2">Agent zaczyna od jednej domeny i szuka reszty kampanii: certyfikatów z tej samej nocy, tego samego kitu, tych samych reklamodawców. Bez czatu: widzisz, co znalazł, i decydujesz.</p>
      <form className="card !rounded-[22px] p-4 flex flex-wrap gap-3 items-end" onSubmit={(e) => { e.preventDefault(); start(seed); }}>
        <label className="flex-1 min-w-[240px] flex flex-col gap-1.5">
          <span className="text-[13px] font-medium text-tx3">Od czego zacząć</span>
          <input value={seed} onChange={(e) => setSeed(e.target.value)} className="h-12 px-3.5 rounded-xl border border-line1 font-mono text-[15px]" placeholder="domena, np. morvanta.click" />
        </label>
        <button type="submit" className="btn-pri" disabled={busy || !seed.trim()}>{busy ? 'Uruchamiam…' : 'Szukaj reszty'}<IArrow /></button>
      </form>
      <Card title="Ostatnie śledztwa">
        {loading && <Loading />}
        {(data ?? []).map((i) => (
          <Link key={i.id} href={`/sledztwa/${i.id}`} className="flex items-center gap-3 py-3 border-b border-bg4 last:border-0 hover:bg-bg2 -mx-2 px-2 rounded-lg">
            <b className="font-mono text-[14px] w-[72px]">{i.id}</b>
            <span className="flex-1 min-w-0"><b className="block font-mono text-[14px] font-medium">{i.seed}</b><span className="text-[12.5px] text-tx3">{[i.campaign_id, `${i.nodes?.length ?? 0} węzłów`, fmtDate(i.started_at)].filter(Boolean).join(' · ')}</span></span>
            <span className={'pill ' + (i.status === 'running' ? 'bg-state-gdim text-state-g' : 'bg-bg3 text-tx2')}>{STATUS[i.status ?? ''] ?? i.status}</span>
            <IChevR className="text-tx4" />
          </Link>
        ))}
        {!loading && !data?.length && <Empty>Jeszcze nic. Zacznij od domeny z raportu.</Empty>}
      </Card>
    </Page>
  );
}

export default function Page_() {
  return <Suspense fallback={<Loading />}><Sledztwa /></Suspense>;
}
