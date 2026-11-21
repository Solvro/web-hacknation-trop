// Small shared building blocks (boards 5–14).
import Link from 'next/link';
import type { ReactNode } from 'react';

export function Crumbs({ items }: { items: { label: string; href?: string }[] }) {
  return (
    <nav aria-label="Ścieżka" className="text-[13px] flex flex-wrap items-center gap-1.5">
      {items.map((it, i) => (
        <span key={i} className="inline-flex items-center gap-1.5">
          {i > 0 && <span className="text-line2" aria-hidden="true">/</span>}
          {it.href ? <Link href={it.href} className="text-tx2 underline decoration-line2 underline-offset-4 hover:text-tx1">{it.label}</Link> : <span className="font-medium" aria-current="page">{it.label}</span>}
        </span>
      ))}
    </nav>
  );
}

export function Page({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <main className={'w-full max-w-[1240px] mx-auto px-4 sm:px-6 pt-6 pb-10 flex flex-col gap-6 ' + className}>{children}</main>;
}

export function Card({ title, action, children, className = '', id }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; id?: string }) {
  return (
    <section className={'card !rounded-[22px] p-5 ' + className} aria-labelledby={id}>
      {(title || action) && (
        <div className="flex items-baseline justify-between gap-3 pb-3">
          {title && <h2 id={id} className="text-[17px] font-semibold tracking-[-0.015em]">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Sparkline({ data, w = 120, h = 30, dashedEmpty, label }: { data: number[]; w?: number; h?: number; dashedEmpty?: boolean; label: string }) {
  if (!data.length) return <span className="text-tx4 text-[12px]">—</span>;
  const max = Math.max(1, ...data);
  const pts = data.map((v, i) => `${(i / Math.max(1, data.length - 1)) * w},${h - 3 - (v / max) * (h - 6)}`);
  const firstNz = data.findIndex((v) => v > 0);
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" aria-label={label} className="block">
      {dashedEmpty && firstNz > 0 ? (
        <>
          <polyline points={pts.slice(0, firstNz + 1).join(' ')} fill="none" stroke="#A3A3A3" strokeWidth={1.2} strokeDasharray="3 3" />
          <polyline points={pts.slice(firstNz).join(' ')} fill="none" stroke="#0A0A0A" strokeWidth={1.6} />
        </>
      ) : <polyline points={pts.join(' ')} fill="none" stroke="#0A0A0A" strokeWidth={1.6} />}
    </svg>
  );
}

export function Bars({ data, labels, highlightLast = true, h = 140, label, markers }: { data: number[]; labels?: string[]; highlightLast?: boolean; h?: number; label: string; markers?: { i: number; text: string; color: string }[] }) {
  const max = Math.max(1, ...data);
  return (
    <div>
      <div className="relative flex items-end gap-2 sm:gap-3 border-b border-line1" style={{ height: h + (markers?.length ? 34 : 0) }} role="img" aria-label={label}>
        {data.map((v, i) => {
          const m = markers?.find((x) => x.i === i);
          return (
            <div key={i} className="relative flex-1 flex flex-col items-center justify-end h-full">
              {m && <span className="absolute top-0 whitespace-nowrap text-[12px] right-0" style={{ color: m.color }}>{m.text}</span>}
              {m && <span className="w-px h-6 mb-1" style={{ background: m.color }} />}
              <span className="w-full max-w-[44px] rounded-t-md" style={{ height: Math.max(4, (v / max) * h), background: highlightLast && i === data.length - 1 ? '#EA580C' : '#1A1A1A' }} />
            </div>
          );
        })}
      </div>
      {labels && <div className="flex gap-2 sm:gap-3 pt-2 text-[12px] text-tx3">{labels.map((l, i) => <span key={i} className="flex-1 text-center">{l}</span>)}</div>}
    </div>
  );
}

export function Initials({ name }: { name: string }) {
  const s = name.replace(/^dr\.?\s+/i, '').replace(/[«»„”.]+/g, ' ').trim().split(/\s+/).map((x) => x[0]).join('').slice(0, 2).toUpperCase();
  return <span aria-hidden="true" className="w-8 h-8 flex-none rounded-full bg-bg4 text-[11px] font-semibold text-tx2 inline-flex items-center justify-center">{s}</span>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-[13.5px] text-tx3 py-2">{children}</p>;
}

export function Loading() {
  return <div className="flex-1 min-h-[300px] flex items-center justify-center" role="status" aria-label="Ładowanie"><span className="spin" /></div>;
}
