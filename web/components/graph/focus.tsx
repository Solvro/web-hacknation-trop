'use client';
// Boards 4a–4d: the graph turned around one node. Left: where you came from; middle: the node; right: its
// neighbours (each clickable again); side panel: facts, one bot sentence, one primary action, one text link.
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import type { FocusPanel, GraphNode, GraphPayload } from '@/lib/contracts';
import { BOT_BY_KEY } from '@/lib/copy';
import { apiPost } from '@/lib/api';
import { Bot } from '../jelly';
import { IArrow, IX } from '../icons';

type Meta = { sub?: string; count?: number; thumb?: boolean | string; title?: string; weak?: boolean; relation?: string; kind_label?: string; side?: string; shared?: boolean; only?: string; bot?: string };
const meta = (n: GraphNode) => (n.meta ?? {}) as Meta;
const nodeTitle = (n: GraphNode) => (n.kind === 'incident' && meta(n).title ? meta(n).title! : n.label);
/** only real image URLs (never the API's mock placeholder svgs) */
const realThumb = (t?: boolean | string) => (typeof t === 'string' && t && !/\/mock\//.test(t) ? t : null);

const TONE: Record<string, string> = {
  g: 'bg-state-gdim text-state-g', amber: 'bg-state-adim text-state-amber', red: 'bg-state-rdim text-state-red', cyan: 'bg-state-cdim text-state-cyan',
  violet: 'bg-state-vdim text-state-violet', neutral: 'bg-bg3 text-tx1',
};

function NodeCard({ n, onClick, active }: { n: GraphNode; onClick?: () => void; active?: boolean }) {
  const m = meta(n);
  const inner = (
    <>
      {realThumb(m.thumb) && <img src={realThumb(m.thumb)!} alt="" className="w-[34px] h-[34px] flex-none rounded-lg object-cover object-top border border-line1" />}
      {!m.thumb && m.bot && <Bot color={BOT_BY_KEY[m.bot as keyof typeof BOT_BY_KEY]?.color ?? '#525252'} size={30} />}
      <span className="flex-1 min-w-0 flex flex-col gap-0.5 text-left">
        <span className={(n.kind === 'incident' && m.title ? 'text-[13px] leading-snug line-clamp-2 break-words ' : 'font-mono text-[13px] truncate ') + 'font-semibold ' + (m.weak ? 'text-tx4 font-medium' : 'text-tx1')}>{n.kind === 'incident' && m.title ? m.title : n.label}</span>
        {(m.sub || (n.kind === 'incident' && m.title)) && <span className="text-[12.5px] text-tx3 truncate">{[n.kind === 'incident' && m.title ? n.id : null, m.sub].filter(Boolean).join(' · ')}</span>}
      </span>
      {m.count != null && <b className="font-mono text-[14px] font-semibold">{m.count}</b>}
    </>
  );
  const cls = 'w-full min-h-[64px] flex items-center gap-3 px-4 rounded-[18px] border ' +
    (m.weak ? 'border-dashed border-line1 bg-bg2' : 'border-line1 bg-bg1 shadow-soft') + (active ? ' ring-2 ring-tx1' : '');
  if (!onClick) return <div className={cls}>{inner}</div>;
  return <button type="button" onClick={onClick} className={cls + ' hover:border-line3 transition-colors'} aria-label={`Rozwiń: ${n.label}`}>{inner}</button>;
}

export function Panel({ p, onClose }: { p: FocusPanel; onClose: () => void }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const bot = p.bot ? BOT_BY_KEY[p.bot] : null;
  async function act() {
    if (!p.action) return;
    if (p.action.kind === 'investigate') {
      setBusy(true);
      const r = await apiPost<{ id: string }>('/investigations', { seed: p.action.seed ?? p.title }, () => ({ id: 'INV-7' }))
        .catch((e: Error) => { setErr(`Nie udało się uruchomić agenta: ${e.message}`); setBusy(false); return null; });
      if (!r) return;
      router.push(`/sledztwa/${encodeURIComponent(r.id)}`);
      return;
    }
    if (p.action.href) router.push(p.action.href);
  }
  return (
    <aside className="card !rounded-[22px] p-5 flex flex-col gap-3" aria-labelledby="focus-title">
      <div className="flex items-center gap-1.5 flex-wrap">
        {p.kind_label && <span className="pill bg-bg3 text-tx1">{p.kind_label}</span>}
        {p.badge && <span className={'pill ' + (TONE[p.badge.tone ?? 'neutral'] ?? TONE.neutral)}>{p.badge.text}</span>}
        {p.tags?.map((t) => <span key={t} className="pill bg-bg3 text-tx1">{t}</span>)}
        <button type="button" onClick={onClose} aria-label="Zamknij i wróć do grafu" className="ml-auto w-9 h-9 rounded-full inline-flex items-center justify-center text-tx2 hover:bg-bg3"><IX /></button>
      </div>
      <h3 id="focus-title" className="text-[26px] font-semibold tracking-[-0.03em] leading-tight">{p.title}</h3>
      {p.description && <p className="text-[14px] leading-normal text-tx2">{p.description}</p>}
      {p.facts && p.facts.length > 0 && (
        <dl className="m-0">{p.facts.filter((f) => f.v != null && String(f.v).trim() && String(f.v).trim() !== '—').map((f) => <div key={f.k} className="kv"><dt>{f.k}</dt><dd>{f.v}</dd></div>)}</dl>
      )}
      {p.bot_text && (
        <div className="flex gap-3 items-start rounded-2xl bg-bg3 p-3.5">
          {bot && <Bot color={bot.color} master={bot.master} size={30} />}
          <span className="flex flex-col gap-1"><span className="text-[12px] text-tx3">{bot?.name ?? 'Bot'}</span><span className="text-[13.5px] leading-normal">{p.bot_text}</span></span>
        </div>
      )}
      {p.action && <button type="button" className="btn-pri self-start" onClick={act} disabled={busy}>{busy ? 'Uruchamiam…' : p.action.label}<IArrow /></button>}
      {err && <p role="alert" className="text-[13px] text-state-red">{err}</p>}
      {p.link && <Link href={p.link.href} className="lnk self-start">{p.link.label}</Link>}
    </aside>
  );
}

export function FocusView({ data, originId, originThumb, onFocus, onBack }: { data: GraphPayload; originId: string; originThumb?: string; onFocus: (id: string) => void; onBack: () => void }) {
  const center = data.nodes.find((n) => n.id === data.focus) ?? data.nodes[0];
  const origin = data.nodes.find((n) => n.id === originId) ?? data.nodes.find((n) => meta(n).sub === 'ten materiał');
  const others = data.nodes.filter((n) => n !== center && n !== origin);
  const bridge = meta(center).side === 'right' && center.kind === 'incident';
  const panel = (data.panel ?? {}) as FocusPanel;
  const rowH = 84;
  const H = Math.max(420, others.length * rowH + 40);
  const mid = H / 2;
  const yOf = (i: number) => 20 + i * rowH + 32;
  const dashed = (n: GraphNode) => meta(n).weak || !!meta(n).relation;
  const stroke = (n: GraphNode) => (meta(n).relation ? '#8B5CF6' : meta(n).weak ? '#A3A3A3' : '#171717');

  return (
    <div className="flex flex-col gap-4">
      <nav aria-label="Ślad" className="text-[14px] flex items-center gap-2">
        <button type="button" onClick={onBack} className="text-tx2 underline decoration-line2 underline-offset-4 hover:text-tx1">Graf</button>
        <span className="text-tx4" aria-hidden="true">›</span>
        <b className="font-semibold">{nodeTitle(center)}</b>
      </nav>
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_380px] gap-6 items-start">
        {/* desktop graph */}
        <div className="hidden lg:block relative" style={{ height: H }}>
          <svg className="absolute left-0 top-0" width={800} height={H} aria-hidden="true">
            <g fill="none" strokeLinecap="round">
              {!bridge && origin && <path d={`M180 ${mid} L232 ${mid}`} stroke="#171717" strokeWidth={2} />}
              {!bridge && others.map((n, i) => (
                <path key={n.id} d={`M450 ${mid} C480 ${mid} 480 ${yOf(i)} 510 ${yOf(i)}`} stroke={stroke(n)} strokeWidth={dashed(n) ? 1.4 : 2.2} strokeDasharray={dashed(n) ? '5 5' : undefined} />
              ))}
              {bridge && others.map((n, i) => (
                <g key={n.id}>
                  {meta(n).only !== 'focus' && <path d={`M180 ${mid} C215 ${mid} 215 ${yOf(i)} 250 ${yOf(i)}`} stroke={meta(n).only ? '#A3A3A3' : '#171717'} strokeWidth={meta(n).only ? 1.4 : 2.2} />}
                  {meta(n).only !== 'origin' && <path d={`M520 ${yOf(i)} C555 ${yOf(i)} 555 ${mid} 590 ${mid}`} stroke={meta(n).only ? '#A3A3A3' : '#171717'} strokeWidth={meta(n).only ? 1.4 : 2.2} />}
                </g>
              ))}
            </g>
          </svg>
          {origin && (
            <div className="absolute" style={{ left: 0, top: mid - 32, width: 180 }}>
              <NodeCard n={{ ...origin, meta: { ...meta(origin), thumb: originThumb ?? true, sub: 'ten materiał', count: undefined } }} />
            </div>
          )}
          {!bridge && (
            <div className="absolute" style={{ left: 232, top: mid - 64, width: 218 }}>
              <div className="rounded-[20px] border-[2.5px] border-tx1 bg-bg1 px-4 py-4 shadow-[0_0_0_6px_#F0F0F0] flex flex-col gap-1.5">
                <span className="text-[12px] text-tx3 text-center">{meta(center).kind_label ?? panel.kind_label}</span>
                <b className="font-mono text-[16px] font-semibold truncate">{nodeTitle(center)}</b>
                {meta(center).sub && <span className="text-[12.5px] text-tx3 truncate">{meta(center).sub}</span>}
              </div>
            </div>
          )}
          {bridge && (
            <div className="absolute" style={{ left: 590, top: mid - 64, width: 200 }}>
              <div className="rounded-[20px] border-[2.5px] border-tx1 bg-bg1 px-4 py-4 shadow-[0_0_0_6px_#F0F0F0] flex flex-col gap-1.5">
                <span className="flex items-center gap-2 text-[12px] text-tx3">{realThumb(meta(center).thumb) && <img src={realThumb(meta(center).thumb)!} alt="" className="w-[26px] h-[26px] rounded-md object-cover border border-line1" />}{meta(center).kind_label ?? 'Materiał'}</span>
                <b className="font-mono text-[16px] font-semibold truncate">{nodeTitle(center)}</b>
                {meta(center).sub && <span className="text-[12.5px] text-tx3 truncate">{meta(center).sub}</span>}
              </div>
            </div>
          )}
          {others.map((n, i) => (
            <div key={n.id} className="absolute" style={{ left: bridge ? 250 : 510, top: yOf(i) - 32, width: bridge ? 270 : 280 }}>
              <NodeCard n={n} onClick={() => onFocus(n.id)} />
            </div>
          ))}
        </div>
        {/* phone / tablet: stacked */}
        <div className="lg:hidden flex flex-col gap-2.5">
          <div className="rounded-[20px] border-[2.5px] border-tx1 bg-bg1 px-4 py-3.5 flex flex-col gap-1">
            <span className="text-[12px] text-tx3">{meta(center).kind_label ?? panel.kind_label}</span>
            <b className="font-mono text-[16px] font-semibold break-all">{nodeTitle(center)}</b>
            {meta(center).sub && <span className="text-[12.5px] text-tx3">{meta(center).sub}</span>}
          </div>
          <span className="text-[12.5px] text-tx3 px-1 pt-1">Powiązane</span>
          {others.map((n) => <NodeCard key={n.id} n={n} onClick={() => onFocus(n.id)} />)}
        </div>
        <Panel p={panel} onClose={onBack} />
      </div>
    </div>
  );
}
