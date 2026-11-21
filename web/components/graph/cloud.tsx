'use client';
// Campaign cloud (Sigma.js + graphology): the campaign's materials around it; click a material → focus view (4d).
import { useEffect, useRef, useState } from 'react';
import type { GraphPayload } from '@/lib/contracts';

export function GraphCloud({ data, highlight, onPick, className, label }: { data: GraphPayload | undefined; highlight?: string; onPick?: (id: string) => void; className?: string; label: string }) {
  const box = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  const pick = useRef(onPick);
  pick.current = onPick;

  useEffect(() => {
    if (!data || !box.current) return;
    let killed = false;
    let renderer: { kill(): void } | null = null;
    (async () => {
      try {
        const [{ default: Graph }, { default: Sigma }] = await Promise.all([import('graphology'), import('sigma')]);
        if (killed || !box.current) return;
        const g = new Graph();
        const center = data.nodes.find((x) => x.kind === 'campaign');
        const members = data.nodes.filter((x) => x !== center);
        if (center) g.addNode(center.id, { x: 0, y: 0, size: 9, color: '#0A0A0A', label: '' });
        members.forEach((m, i) => {
          const a = i * 2.399963; // golden angle spiral
          const r = 0.55 + 0.45 * Math.sqrt((i + 1) / members.length);
          const hl = m.id === highlight;
          g.addNode(m.id, {
            x: Math.cos(a) * r, y: Math.sin(a) * r, size: hl ? 7 : 3 + (m.size ?? 1) * 1.4,
            color: hl ? '#A3A3A3' : `rgba(10,10,10,${0.55 + ((i * 37) % 45) / 100})`, label: m.label,
            borderColor: '#0A0A0A',
          });
        });
        for (const e of data.edges) if (g.hasNode(e.a) && g.hasNode(e.b) && !g.hasEdge(e.a, e.b)) g.addEdge(e.a, e.b, { color: '#E5E5E5', size: 0.6 });
        const s = new Sigma(g, box.current, {
          renderLabels: true, labelFont: 'var(--font-geist-mono), monospace', labelSize: 11, labelColor: { color: '#0A0A0A' },
          enableEdgeEvents: false, zIndex: true, defaultEdgeColor: '#E5E5E5', labelRenderedSizeThreshold: highlight ? 6.5 : 99,
        });
        s.on('clickNode', ({ node }) => { if (node !== center?.id) pick.current?.(node); });
        s.on('enterNode', () => { if (box.current) box.current.style.cursor = 'pointer'; });
        s.on('leaveNode', () => { if (box.current) box.current.style.cursor = 'default'; });
        renderer = s;
      } catch {
        if (!killed) setFailed(true);
      }
    })();
    return () => { killed = true; renderer?.kill(); };
  }, [data, highlight]);

  const members = data?.nodes.filter((x) => x.kind !== 'campaign') ?? [];
  return (
    <div className={'relative ' + (className ?? '')}>
      <div ref={box} className="absolute inset-0" role="img" aria-label={label} />
      {failed && (
        <svg viewBox="-1.1 -1.1 2.2 2.2" className="absolute inset-0 w-full h-full" aria-hidden="true">
          {members.map((m, i) => { const a = i * 2.4; const r = 0.55 + 0.45 * Math.sqrt((i + 1) / members.length); return <line key={'l' + i} x1={0} y1={0} x2={Math.cos(a) * r} y2={Math.sin(a) * r} stroke="#E5E5E5" strokeWidth={0.006} />; })}
          {members.map((m, i) => { const a = i * 2.4; const r = 0.55 + 0.45 * Math.sqrt((i + 1) / members.length); return <circle key={i} cx={Math.cos(a) * r} cy={Math.sin(a) * r} r={0.035} fill="#0A0A0A" opacity={0.6} />; })}
        </svg>
      )}
    </div>
  );
}
