'use client';
// Board 2 · Analiza: material bar, six bots, three live columns.
import { useEffect, useState } from 'react';
import type { CampaignScore, EvidenceItem, JobStep, Layer } from '@/lib/contracts';
import { BOTS, BOT_BY_KEY, LAYER_LABEL, botColor, botName, n, p2, secs, strengthLabel, strengthPct } from '@/lib/copy';
import { Bot } from '../jelly';
import type { JobState } from '@/lib/use-job';

export function useElapsed(start: number, stop: boolean) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (stop) return;
    const t = setInterval(() => setNow(Date.now()), 200);
    return () => clearInterval(t);
  }, [stop]);
  return (now - start) / 1000;
}

export function MaterialBar({ input, incidentId, note, status, onCancel }: { input: string; incidentId?: string | null; note?: string | null; status: React.ReactNode; onCancel?: () => void }) {
  return (
    <section className="card !rounded-[18px] py-2.5 pl-2.5 pr-3.5 flex items-center gap-3.5" aria-label="Sprawdzany materiał">
      <span className="ph-img w-[72px] h-[54px] flex-none hidden sm:grid">zrzut</span>
      <span className="flex-1 min-w-0 flex flex-col gap-[3px]">
        <span className="font-mono text-[14px] font-medium truncate">{input}</span>
        <span className="text-[13px] text-tx3 truncate">{[incidentId, note].filter(Boolean).join(' · ') || 'nowy materiał'}</span>
      </span>
      {status}
      {onCancel && <button type="button" onClick={onCancel} className="min-h-[40px] px-3 text-[14px] text-tx2 hover:text-tx1">Anuluj</button>}
    </section>
  );
}

export function StatusPill({ text, live }: { text: string; live: boolean }) {
  return (
    <span role="status" className={'inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[13px] font-medium whitespace-nowrap ' + (live ? 'bg-[#F0FDF4] text-[#166534]' : 'bg-bg3 text-tx2')}>
      <span className={'w-2 h-2 rounded-full ' + (live ? 'bg-[#22C55E] animate-pulsedot' : 'bg-tx4')} />{text}
    </span>
  );
}

export function BotStrip({ steps }: { steps: JobStep[] }) {
  return (
    <ol className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 m-0 p-0 list-none" aria-label="Kroki analizy">
      {BOTS.map((b) => {
        const st = steps.find((s) => s.key === b.step);
        const status = st?.status ?? 'pending';
        const run = status === 'run';
        const done = status === 'done' || status === 'warn' || status === 'skip' || status === 'error';
        const sub = run ? 'pracuje…' : status === 'done' ? `gotowe · ${secs(st?.duration_ms)}` : status === 'warn' ? `częściowo · ${secs(st?.duration_ms)}`
          : status === 'skip' ? 'pominięty' : status === 'error' ? 'nie udało się' : 'czeka';
        return (
          <li key={b.key} className={'flex items-center gap-2.5 px-3 py-2.5 rounded-2xl border bg-bg1 min-w-0 transition-colors duration-300 ' + (run ? 'border-tx1' : 'border-bg4')}>
            <Bot color={b.color} master={b.master} size={30} state={done ? 'awake' : run ? 'speaking' : 'asleep'} />
            <span className="min-w-0">
              <b className={'block text-[13.5px] font-semibold whitespace-nowrap ' + (done || run ? 'text-tx1' : 'text-tx4')}>{b.name}</b>
              <span className={'block text-[12px] truncate ' + (run ? 'text-[#166534]' : status === 'error' ? 'text-state-red' : status === 'warn' ? 'text-[#9A3412]' : 'text-tx3')}>
                <span className="sr-only-x">{b.stepName}: </span>{sub}
              </span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

const HL_COLOR: Partial<Record<Layer, string>> = { tracking: '#F97316', kit: '#F97316', content: '#14B8A6', persons: '#14B8A6', infra: '#8B5CF6', visual: '#14B8A6' };

/** Stylised captured page with each finding outlined where it was found. */
export function CapturedPage({ url, headline, evidence, capturing, failed }: { url: string; headline?: string | null; evidence: EvidenceItem[]; capturing: boolean; failed?: boolean }) {
  const has = (t: Layer) => evidence.some((e) => e.type === t && e.state !== 'missing' && e.state !== 'zero');
  const box = (t: Layer) => ({ boxShadow: `0 0 0 2px ${has(t) ? HL_COLOR[t] : 'transparent'}` });
  const tag = (t: Layer, label: string, extra = '') => (
    <span className={'tagc ' + extra} style={{ background: HL_COLOR[t], opacity: has(t) ? 1 : 0 }}>{label}</span>
  );
  const capi = evidence.find((e) => e.type === 'tracking');
  const cert = evidence.find((e) => e.type === 'infra' && e.state !== 'zero');
  const host = url.replace(/^https?:\/\//, '');
  return (
    <div className="relative h-[560px] border border-line1 rounded-[18px] overflow-hidden bg-bg1">
      <div className="h-[30px] flex items-center gap-1.5 px-2.5 bg-bg2 border-b border-bg4">
        {[0, 1, 2].map((i) => <i key={i} className="w-[7px] h-[7px] rounded-full bg-line2" />)}
        <span className="ml-1.5 font-mono text-[10.5px] text-tx4 truncate">{host}</span>
      </div>
      <div className="pt-4 px-3.5 flex flex-col gap-3">
        <div className="flex justify-between items-center border-b-2 border-tx1 pb-1.5">
          <b className="text-[15px] font-extrabold tracking-[.12em]">KURIER DNIA</b><span className="text-[10px] text-tx4">21.11.2026</span>
        </div>
        <p className="hl m-0 px-1.5 py-1 text-[16px] font-bold leading-tight tracking-[-0.01em]" style={box('content')}>
          {headline || 'PILNE: Jan Kowalski przerywa milczenie po napaści'}{tag('content', 'Treść')}
        </p>
        <div className="flex gap-2.5">
          <span className="hl w-[92px] h-[92px] flex-none rounded-[10px] bg-bg4 grid place-items-center font-mono text-[10px] text-tx4" style={box('persons')}>
            twarz{tag('persons', 'Osoby', '!right-auto left-1.5')}
          </span>
          <span className="flex-1 flex flex-col gap-[7px] pt-1">
            {[100, 92, 96, 70, 86, 60].map((w, i) => <span key={i} className="gb" style={{ width: `${w}%` }} />)}
          </span>
        </div>
        <span className="flex flex-col gap-[7px]">{[100, 94, 80].map((w, i) => <span key={i} className="gb" style={{ width: `${w}%` }} />)}</span>
        <div className="hl p-2.5 border border-line1 flex flex-col gap-[7px]" style={box('kit')}>
          <span className="text-[11.5px] font-semibold">Zostaw numer, doradca oddzwoni</span>
          <span className="h-[22px] rounded-md border border-line1" /><span className="h-[22px] rounded-md border border-line1" />
          <span className="h-[26px] rounded-md bg-tx1 text-white text-[11px] font-semibold grid place-items-center">Zarejestruj się</span>
          {tag('kit', 'Kit')}
        </div>
      </div>
      <div className="absolute inset-x-0 bottom-0 px-3 py-2.5 bg-bg2 border-t border-bg4 flex flex-col gap-1.5 font-mono text-[10.5px] leading-tight text-tx2">
        <span className="font-sans font-semibold text-[11px] text-tx1">Sieć · {has('tracking') ? '212 żądań' : 'zbieram…'}</span>
        <span>GET {host.split('/')[0]}/ · {failed ? '502' : '200'}</span>
        <span className="hl px-1 py-0.5" style={box('tracking')}>POST {capi ? capi.value.slice(0, 12) + '…/events' : 'cg-…/events'} · 204{tag('tracking', 'Tracking', '!-top-[9px]')}</span>
        <span className="hl px-1 py-0.5" style={box('infra')}>TLS · {cert ? cert.display : 'certyfikat'}{tag('infra', 'Infra', '!-top-[9px]')}</span>
      </div>
      <div className="fadeN absolute inset-x-0 bottom-0 top-[30px] bg-white/90 flex flex-col items-center justify-center gap-3 pointer-events-none" style={{ opacity: capturing ? 1 : 0 }}>
        <span className="spin" /><span className="text-[14px] text-tx2">Otwieram stronę w piaskownicy…</span>
      </div>
      {failed && (
        <div className="absolute inset-x-0 bottom-0 top-[30px] bg-white/92 flex flex-col items-center justify-center gap-2 text-center px-6">
          <b className="text-[15px]">Strona nie odpowiada</b><span className="text-[13px] text-tx3">Boty ustalą tyle, ile się da bez niej.</span>
        </div>
      )}
    </div>
  );
}

export function FoundCard({ e }: { e: EvidenceItem }) {
  const c = botColor(e.bot);
  const zero = e.state === 'zero';
  const miss = e.state === 'missing';
  return (
    <div className={'flex items-center gap-3 px-3.5 py-3 border rounded-2xl animate-pop ' + (zero || miss ? 'border-dashed border-line1 bg-bg2' : 'border-line1 bg-bg1 shadow-soft')}>
      <Bot color={c} master={e.bot === 'sedzia'} size={34} />
      <span className="flex-1 min-w-0 flex flex-col gap-[3px]">
        <span className="flex items-baseline gap-2">
          <span className="text-[12px] font-semibold" style={{ color: c }}>{zero ? 'Wspólne' : LAYER_LABEL[e.type]}</span>
          <span className="text-[12px] text-tx4">znalazł {botName(e.bot)}</span>
        </span>
        <span className={'font-mono text-[14px] font-medium truncate ' + (zero || miss ? 'text-tx4' : 'text-tx1') + (zero ? ' line-through' : '')}>{e.display}</span>
        <span className="text-[12.5px] text-tx3">
          {zero ? `ma go ${n(e.df ?? 0)} niepowiązanych spraw` : miss ? 'brak w materiale' : e.N ? `${n(e.df ?? 0)} z ${n(e.N)} materiałów ma ten ślad` : ''}
        </span>
      </span>
      <span className="flex-none w-[92px] flex flex-col items-end gap-1.5">
        <span className="meter w-[92px]"><i style={{ width: `${strengthPct(e)}%` }} /></span>
        <span className="text-[12px] text-tx3">{strengthLabel(e)}</span>
      </span>
    </div>
  );
}

export function FoundList({ state }: { state: JobState }) {
  const run = state.steps.find((s) => s.status === 'run');
  const rb = run ? BOT_BY_KEY[run.bot] : null;
  const shown = state.evidence;
  const skel = Math.max(0, 6 - shown.length - (run ? 1 : 0));
  return (
    <section aria-labelledby="an-found">
      <div className="colh"><h2 id="an-found">Co znaleźliśmy</h2><span>{shown.length} {shown.length === 1 ? 'ślad' : 'śladów'}</span></div>
      <div className="flex flex-col gap-2.5" aria-live="polite">
        {shown.map((e, i) => <FoundCard key={i} e={e} />)}
        {run && rb && (
          <div className="flex items-center gap-3 px-3.5 py-3 border border-dashed border-line1 rounded-2xl bg-bg2">
            <Bot color={rb.color} master={rb.master} size={34} state="speaking" />
            <span className="flex-1 min-w-0 flex flex-col gap-[3px]">
              <span className="text-[12px] font-semibold text-tx1">{rb.name} pracuje</span>
              <span className="text-[14px] leading-snug text-[#404040]">{run.detail || rb.run}</span>
            </span>
            <span className="spin" role="img" aria-label="w toku" />
          </div>
        )}
        {!state.done && Array.from({ length: skel }).map((_, i) => <div key={i} aria-hidden="true" className="h-[66px] rounded-2xl border border-dashed border-line1 bg-bg2" />)}
      </div>
    </section>
  );
}

export function Ranking({ scores, names, evidence, joined }: { scores: CampaignScore[]; names: Record<string, string>; evidence: EvidenceItem[]; joined: string | null }) {
  const top = [...scores].sort((a, b) => (b.p ?? 0) - (a.p ?? 0)).slice(0, 3);
  const rows = top.length ? top : [null, null, null];
  const ev = evidence.filter((e) => e.state !== 'missing').slice(0, 5);
  const ys = [22, 48, 75, 102, 128];
  return (
    <section aria-labelledby="an-rank">
      <div className="colh"><h2 id="an-rank">Najbliższe kampanie</h2></div>
      <div className="card !rounded-[18px] px-4 pt-3 pb-2">
        {rows.map((r, i) => (
          <div key={r?.campaign_id ?? i} className="flex flex-col gap-1.5 py-2.5 border-b border-bg4 last:border-0">
            <span className="flex justify-between gap-2 text-[14px]">
              <span className="font-semibold" style={{ color: i === 0 ? '#0A0A0A' : i === 1 ? '#525252' : '#8A8A8A' }}>{r ? (names[r.campaign_id] ?? r.campaign_id) : '—'}</span>
              <span className="font-mono text-[13px] font-semibold">{r ? p2(r.p) : '—'}</span>
            </span>
            <span className="block h-2 rounded-full bg-bg4 overflow-hidden">
              <i className="block h-full rounded-full transition-[width] duration-700" style={{ width: `${Math.round((r?.p ?? 0) * 100)}%`, background: i === 0 ? '#0A0A0A' : i === 1 ? '#A3A3A3' : '#D4D4D4' }} />
            </span>
          </div>
        ))}
        {!top.length && <p className="text-[12.5px] text-tx3 pb-1.5">Czekam, aż boty zbiorą ślady.</p>}
      </div>
      <div className="card !rounded-[18px] px-3 pt-3 pb-2 mt-3">
        <span className="block text-[12.5px] text-tx3 px-1 pb-1.5">Tak to się łączy</span>
        <svg viewBox="0 0 270 150" role="img" aria-label={`Materiał łączy się przez ${ev.length} znalezionych śladów${joined ? ` z kampanią ${joined}` : ''}`} className="w-full h-auto block">
          <g fill="none" strokeLinecap="round">
            {ev.map((e, i) => (
              <path key={i} className="fadeN" d={`M40 75 C70 75 80 ${ys[i]} 112 ${ys[i]}`} stroke={e.state === 'zero' ? '#D4D4D4' : i < 3 ? '#171717' : '#A3A3A3'} strokeWidth={e.state === 'zero' ? 1.2 : 2.2 - i * 0.2} strokeDasharray={e.state === 'zero' ? '4 5' : undefined} />
            ))}
            {joined && ev.map((e, i) => e.state === 'zero' ? null : (
              <path key={'k' + i} className="fadeN" d={`M120 ${ys[i]} C170 ${ys[i]} 180 70 222 70`} stroke={i < 3 ? '#171717' : '#A3A3A3'} strokeWidth={1.6} />
            ))}
          </g>
          <rect x="22" y="63" width="22" height="24" rx="6" fill="#0A0A0A" />
          {ev.map((e, i) => <circle key={i} cx="116" cy={ys[i]} r="6" fill={botColor(e.bot)} opacity={e.state === 'zero' ? 0.35 : 1} />)}
          {joined && <circle cx="232" cy="70" r="13" fill="#0A0A0A" />}
          <text x="33" y="104" textAnchor="middle" fontFamily="var(--font-geist-mono), monospace" fontSize="9.5" fill="#525252">INC</text>
          {joined && <text x="232" y="98" textAnchor="middle" fontFamily="var(--font-geist-mono), monospace" fontSize="9.5" fill="#0A0A0A">{joined}</text>}
        </svg>
      </div>
    </section>
  );
}
