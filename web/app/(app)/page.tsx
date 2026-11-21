'use client';
// Board 1 · Pole: the only zgrai-style screen. One field, sleeping bots around it, plus a few real materials from
// the database the jury can open straight away.
import Link from 'next/link';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiPost, useApi, useHealth } from '@/lib/api';
import { JellyRoot } from '@/components/jelly';
import { CheckField, DEMO_URL } from '@/components/check-field';
import { IArrow } from '@/components/icons';

interface Sample { id: string; title: string; description?: string; expected?: string; size?: number }

const expectedLabel = (e?: string) => {
  if (!e) return '';
  if (e.startsWith('assign:')) return `oczekiwany wynik: dołącza do ${e.slice(7)}`;
  if (e === 'new') return 'oczekiwany wynik: nowa kampania (kandydat)';
  if (e === 'insufficient') return 'oczekiwany wynik: za mało materiału';
  if (e === 'ambiguous') return 'oczekiwany wynik: niepewne, do decyzji';
  return `oczekiwany wynik: ${e}`;
};

/** Bundled materials (GET /samples): one click runs the full analysis, no files needed. */
function Samples({ onWake }: { onWake: () => void }) {
  const router = useRouter();
  const { data } = useApi<Sample[]>('/samples');
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  if (!data?.length) return null;
  async function run(s: Sample) {
    setBusy(s.id); setErr(null); onWake();
    try {
      const r = await apiPost<{ job_id: string; incident_id?: string | null }>(`/samples/${encodeURIComponent(s.id)}/analyze`, {});
      const q = new URLSearchParams({ in: s.title });
      if (r.incident_id) q.set('inc', r.incident_id);
      router.push(`/analiza/${encodeURIComponent(r.job_id)}?${q}`);
    } catch (e) {
      setErr(`Nie udało się uruchomić przykładu: ${(e as Error).message}`); setBusy(null);
    }
  }
  return (
    <section aria-labelledby="pr-h" className="w-full flex flex-col gap-2 text-left">
      <h2 id="pr-h" className="text-[13px] font-medium text-tx3 text-center">Nie masz materiału? Sprawdź jeden z przygotowanych:</h2>
      <ul className="m-0 p-0 list-none grid grid-cols-1 sm:grid-cols-2 gap-2">
        {data.slice(0, 6).map((s) => (
          <li key={s.id}>
            <button type="button" onClick={() => run(s)} disabled={!!busy} title={s.description}
              className="w-full h-full flex items-center gap-3 px-4 py-3 rounded-2xl border border-line1 bg-bg1/90 hover:border-line3 shadow-soft text-left disabled:opacity-60">
              <span className="flex-1 min-w-0">
                <span className="block text-[14px] font-semibold leading-snug line-clamp-2">{s.title}</span>
                <span className="block text-[12.5px] text-tx3 truncate">{expectedLabel(s.expected)}</span>
              </span>
              {busy === s.id ? <span className="spin" role="img" aria-label="uruchamiam" /> : <IArrow className="text-tx3 flex-none" />}
            </button>
          </li>
        ))}
      </ul>
      {err && <p role="alert" className="text-[13px] text-state-red text-center">{err}</p>}
    </section>
  );
}

export default function SprawdzPage() {
  const [wake, setWake] = useState(0);
  const { demo, health } = useHealth();
  return (
    <JellyRoot mode="field" fieldState="asleep" wakeKey={wake} className="flex-1 flex min-h-[640px]">
      <main className="relative z-[1] flex-1 flex items-center justify-center px-4 sm:px-6 pt-4 pb-[120px]">
        <div data-jelly-clear className="w-full max-w-[800px] flex flex-col items-center gap-[26px] text-center">
          <div className="flex flex-col gap-3 items-center">
            <h1 className="m-0 text-[36px] sm:text-[48px] leading-[1.05] tracking-[-0.04em] font-semibold">Co sprawdzamy?</h1>
            <p className="m-0 max-w-[560px] text-[17px] leading-normal text-tx2">
              Wklej link, wrzuć zrzut, plik HAR albo ZIP z materiałem, albo wpisz ślad: domenę, piksel czy nazwisko. Boty pokażą, do której kampanii to należy i dlaczego.
            </p>
          </div>
          {/* the demo URL only makes sense against the fictional universe */}
          <CheckField key={demo ? 'demo' : 'real'} initial={demo ? DEMO_URL : ''} onWake={() => setWake((w) => w + 1)} />
          {health && !demo && <Samples onWake={() => setWake((w) => w + 1)} />}
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
