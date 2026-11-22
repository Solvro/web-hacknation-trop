'use client';
// Graf: an explorable graph around one material. Every node is labelled and typed; hovering shows what it is and
// highlights its edges; clicking unfolds ITS neighbours in place (GET /graph?focus=<id>&origin=<incident>), merged into
// what is already on screen (dedupe by id), animated; clicking again folds them back. Below 640 px: a list.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Decision, EvidenceItem, FocusPanel, GraphEdge, GraphNode, GraphPayload, IncidentSummary } from '@/lib/contracts';
import { apiGet, useApi } from '@/lib/api';
import { LAYER_HINT, LAYER_LABEL, n as fmtN, p2, plural, prettyDisplay, w1 } from '@/lib/copy';
import { normalizePanel, personName } from '@/lib/graph';
import { Panel } from './focus';

type Layer = keyof typeof LAYER_LABEL;
interface VNode extends GraphNode { x: number; y: number; parent: string | null; removing?: boolean; pinned?: boolean }
interface VEdge extends GraphEdge { key: string; dashed?: boolean; note?: string }
type Pt = { x: number; y: number };

const ANIM = 420;
const MIN_D = 128;
const LAYER_COLOR: Record<string, string> = { tracking: '#F97316', kit: '#8B5CF6', infra: '#7C3AED', content: '#14B8A6', persons: '#0D9488', visual: '#0EA5E9', ad: '#65A30D', media: '#DB2777' };
const KIND_COLOR: Record<string, string> = { incident: '#0A0A0A', campaign: '#0A0A0A', domain: '#D97706', person: '#0D9488', operator: '#6D28D9', operation: '#6D28D9', cert: '#7C3AED', advertiser: '#65A30D' };
const KIND_LABEL: Record<string, string> = { incident: 'Materiał', campaign: 'Kampania', domain: 'Domena', person: 'Osoba', operator: 'Operator', operation: 'Operacja', trace: 'Ślad', cert: 'Certyfikat', advertiser: 'Reklamodawca' };
const FIELD: Record<string, string> = {
  fb_pixel: 'Piksel FB', capi_gateway: 'Bramka CAPI', lander_id: 'Zestaw strony: lander', kit_tenant: 'Zestaw strony: konto',
  landing_type_id: 'Zestaw strony: typ', kit_endpoint: 'Zestaw strony: adres API', asset_hash: 'Wspólny plik', brand_asset_hash: 'Plik marki',
  url_param_schema: 'Gramatyka URL', chain_param_schema: 'Gramatyka URL', google_ad: 'Google Ads', ga4: 'GA4', gtm: 'GTM', tiktok_pixel: 'Piksel TikTok',
  headline_template: 'Szablon nagłówka', h1_template: 'Szablon H1', comment_name: 'Fałszywy komentujący', brand: 'Marka', cdn: 'CDN', ns_pair: 'Para NS',
  ns: 'Serwery DNS', registrar: 'Rejestrator', asn: 'ASN', path_shape: 'Kształt ścieżki', entry_path_template: 'Ścieżka wejścia', video_host: 'Hosting wideo',
  kit: 'Zestaw strony', capi: 'Bramka CAPI', pixel: 'Piksel', content: 'Treść', text_minhash: 'Tekst strony', dom_minhash: 'Struktura strony',
  registrar_batch: 'Partia rejestracji', cert_batch: 'Partia certyfikatów', ad_text: 'Tekst reklamy', vertical: 'Branża', brand_asset: 'Plik marki',
  advertiser: 'Reklamodawca', entry_url: 'Adres wejścia', domain_shape: 'Kształt domeny',
};
const meta = (n?: GraphNode) => (n?.meta ?? {}) as { field?: string; value?: string; layer?: string; count?: number; sub?: string; thumb?: unknown };
const fieldKey = (f?: string) => (f ?? '').replace(/s$/, '');
const shortVal = (v: string, k = 20) => {
  if (v.length <= k) return v;
  if (/^[0-9a-f-]{16,}$/i.test(v)) return v.slice(0, 8) + '…';
  return v.slice(0, k - 1) + '…';
};
const ease = (t: number) => 1 - Math.pow(1 - t, 3);
const ekey = (a: string, b: string) => (a < b ? `${a}|${b}` : `${b}|${a}`);

function Glyph({ kind, layer, color }: { kind: string; layer?: string; color: string }) {
  const p = { fill: 'none', stroke: color, strokeWidth: 1.6, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  if (kind === 'campaign') return <path d="M-5 6V-6M-5 -6h9l-2 3 2 3h-9" {...p} stroke="#fff" />;
  if (kind === 'incident') return <g {...p}><rect x={-5} y={-6.5} width={10} height={13} rx={1.5} /><path d="M-2.5 -2.5h5M-2.5 0.5h5M-2.5 3.5h3" /></g>;
  if (kind === 'domain') return <g {...p}><circle r={6} /><path d="M-6 0h12M0 -6c-3 3.5-3 8.5 0 12M0 -6c3 3.5 3 8.5 0 12" /></g>;
  if (kind === 'person') return <g {...p}><circle cy={-2.5} r={3} /><path d="M-5.5 6c0-3.5 2.5-5 5.5-5s5.5 1.5 5.5 5" /></g>;
  if (kind === 'operator' || kind === 'operation') return <g {...p}><circle cx={-2.5} cy={-2} r={2.4} /><circle cx={3.5} cy={-1} r={2} /><path d="M-7 6c0-3 2-4.5 4.5-4.5S2 3 2 6M2.5 6c0-2 1.2-3.5 3-3.5" /></g>;
  if (layer === 'tracking') return <g {...p}><circle r={5.5} /><circle r={1.6} fill={color} /><path d="M0 -8v3M0 5v3M-8 0h3M5 0h3" /></g>;
  if (layer === 'kit') return <path d="M-3 -6l-4 6 4 6M3 -6l4 6-4 6" {...p} />;
  if (layer === 'infra') return <g {...p}><rect x={-6} y={-6} width={12} height={5} rx={1} /><rect x={-6} y={1} width={12} height={5} rx={1} /></g>;
  if (layer === 'content') return <path d="M-6 -4.5h12M-6 -1.5h12M-6 1.5h9M-6 4.5h6" {...p} />;
  if (layer === 'persons') return <g {...p}><circle cy={-2.5} r={3} /><path d="M-5.5 6c0-3.5 2.5-5 5.5-5s5.5 1.5 5.5 5" /></g>;
  return <circle r={3} fill={color} />;
}

export interface ExplorerProps {
  originId: string;
  decision: Decision;
  names: Record<string, string>;
  originTitle?: string | null;
  originThumb?: string;
  /** a node to unfold right away (chip clicked in the Raport); `null` = none */
  focusId?: string | null;
  focusMissing?: boolean;
}

export function GraphExplorer({ originId, decision, names, originTitle, originThumb, focusId, focusMissing }: ExplorerProps) {
  const incList = useApi<IncidentSummary[] | { items: IncidentSummary[] }>('/incidents?limit=500').data;
  const titles = useMemo(() => new Map((Array.isArray(incList) ? incList : incList?.items ?? []).map((i) => [i.id, i.title || i.domain || i.id])), [incList]);
  const evByValue = useMemo(() => {
    const m = new Map<string, EvidenceItem>();
    for (const e of decision.evidence ?? []) if (e.value) m.set(e.value.toLowerCase(), e);
    return m;
  }, [decision.evidence]);

  const [nodes, setNodes] = useState<Record<string, VNode>>({});
  const [edges, setEdges] = useState<Record<string, VEdge>>({});
  const [expanded, setExpanded] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>(originId);
  const [panels, setPanels] = useState<Record<string, FocusPanel>>({});
  const [more, setMore] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [hover, setHover] = useState<{ node?: string; edge?: string; x: number; y: number } | null>(null);
  const [anim, setAnim] = useState<{ from: Record<string, Pt>; t0: number } | null>(null);
  const [now, setNow] = useState(0);
  const [vb, setVb] = useState({ x: -480, y: -300, w: 960, h: 600 });
  const box = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  const nodesRef = useRef(nodes); nodesRef.current = nodes;
  const edgesRef = useRef(edges); edgesRef.current = edges;
  const expRef = useRef(expanded); expRef.current = expanded;
  const initial = useRef<{ nodes: Record<string, VNode>; edges: Record<string, VEdge>; panel?: FocusPanel; more: number } | null>(null);
  const [aspect, setAspect] = useState(1.6);

  // ---------------------------------------------------------------- animation clock
  useEffect(() => {
    if (!anim) return;
    let raf = 0;
    const tick = () => { const t = performance.now(); setNow(t); if (t - anim.t0 < ANIM) raf = requestAnimationFrame(tick); else setAnim(null); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [anim]);
  const pos = useCallback((id: string): Pt => {
    const nd = nodes[id];
    if (!nd) return { x: 0, y: 0 };
    const f = anim?.from[id];
    if (!f) return nd;
    const t = ease(Math.min(1, Math.max(0, (now - anim!.t0) / ANIM)));
    return { x: f.x + (nd.x - f.x) * t, y: f.y + (nd.y - f.y) * t };
  }, [nodes, anim, now]);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => { const r = el.getBoundingClientRect(); if (r.width && r.height) setAspect(r.width / r.height); });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // ---------------------------------------------------------------- labels
  const label = useCallback((nd: GraphNode): { title: string; sub: string; layer?: string } => {
    const m = meta(nd);
    if (nd.kind === 'incident') {
      const t = nd.id === originId ? originTitle || titles.get(nd.id) : titles.get(nd.id);
      return { title: shortVal(t || nd.id, 30), sub: nd.id === originId ? `ten materiał · ${nd.id}` : `materiał · ${nd.id}` };
    }
    if (nd.kind === 'campaign') {
      const nm = (names[nd.id] ?? nd.label ?? '').replace(nd.id, '').replace(/^\s*·\s*/, '').trim();
      return { title: nd.id, sub: shortVal(nm || 'kampania', 30) };
    }
    if (nd.kind === 'trace') {
      const field = fieldKey(m.field ?? nd.id.split(':')[1]);
      const value = m.value ?? nd.id.split(':').slice(2).join(':');
      const layer = m.layer ?? (nd.id.includes(':cdn:') ? 'infra' : undefined);
      return { title: FIELD[field] ?? FIELD[m.field ?? ''] ?? (layer ? LAYER_LABEL[layer as Layer] : 'Ślad'), sub: shortVal(prettyDisplay(value), 26), layer };
    }
    if (nd.kind === 'person') return { title: personName(nd.label || nd.id.replace(/^person:/, '')), sub: 'osoba', layer: 'persons' };
    if (nd.kind === 'domain') return { title: shortVal(nd.label || nd.id.replace(/^d[:-]/, ''), 28), sub: 'domena' };
    if (nd.kind === 'operator') return { title: nd.id, sub: 'operator' };
    return { title: shortVal(nd.label || nd.id, 28), sub: KIND_LABEL[nd.kind] ?? nd.kind };
  }, [names, originId, originTitle, titles]);

  const evOf = useCallback((nd?: GraphNode) => {
    const v = meta(nd).value;
    return v ? evByValue.get(v.toLowerCase()) : undefined;
  }, [evByValue]);

  const edgeText = useCallback((e: VEdge): string => {
    if (e.note) return e.note;
    if (e.type === 'member') return e.label || 'należy do kampanii';
    if (e.type === 'operator') return e.label || 'ten sam operator';
    if (e.type === 'operation') return e.label || 'ta sama operacja';
    const tr = [nodes[e.a], nodes[e.b]].find((x) => x?.kind === 'trace' || x?.kind === 'person');
    const ev = evOf(tr);
    const what = tr ? label(tr).title.replace(/^Zestaw strony: /, '') : '';
    const w = ev?.weight ?? e.weight;
    return [LAYER_LABEL[e.type as Layer] ?? e.type, what && what !== LAYER_LABEL[e.type as Layer] ? (tr?.kind === 'trace' ? what.toLowerCase() : what) : null, w != null ? w1(w) : null].filter(Boolean).join(' · ');
  }, [nodes, evOf, label]);

  // ---------------------------------------------------------------- layout
  function place(parent: VNode, grand: Pt | null, kids: GraphNode[], all: Record<string, VNode>): VNode[] {
    const n = kids.length;
    const base = grand ? Math.atan2(parent.y - grand.y, parent.x - grand.x) : 0;
    const spread = grand ? Math.min(Math.PI * 1.5, Math.max(Math.PI * 0.6, n * 0.42)) : Math.PI * 2;
    const R = 190 + Math.max(0, n - 6) * 14;
    const out: VNode[] = kids.map((k, i) => {
      const a = grand ? base - spread / 2 + (spread * (i + 0.5)) / n : base + (i * Math.PI * 2) / n;
      return { ...k, x: parent.x + Math.cos(a) * R, y: parent.y + Math.sin(a) * R * 0.78, parent: parent.id };
    });
    const others = Object.values(all).filter((x) => !x.removing);
    for (let it = 0; it < 60; it++) {
      for (const a of out) {
        for (const b of [...others, ...out]) {
          if (a === b) continue;
          const dx = a.x - b.x, dy = (a.y - b.y) * 1.35;
          const d = Math.hypot(dx, dy) || 0.01;
          if (d < MIN_D) { const k = (MIN_D - d) / d * (out.includes(b) ? 0.5 : 1); a.x += dx * k * 0.5; a.y += (dy / 1.35) * k * 0.5; }
        }
      }
    }
    return out;
  }

  const fitTo = useCallback((ns: Record<string, VNode>, asp = aspect) => {
    const list = Object.values(ns).filter((x) => !x.removing);
    if (!list.length) return;
    const xs = list.map((x) => x.x), ys = list.map((x) => x.y);
    let x0 = Math.min(...xs) - 120, x1 = Math.max(...xs) + 120, y0 = Math.min(...ys) - 70, y1 = Math.max(...ys) + 90;
    let w = Math.max(640, x1 - x0), h = Math.max(420, y1 - y0);
    if (w / h < asp) w = h * asp; else h = w / asp;
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    x0 = cx - w / 2; y0 = cy - h / 2;
    setVb({ x: x0, y: y0, w, h });
  }, [aspect]);

  // ---------------------------------------------------------------- data
  const fetchFocus = useCallback(async (id: string) => {
    const g = await apiGet<GraphPayload>(`/graph?focus=${encodeURIComponent(id)}&origin=${encodeURIComponent(originId)}`);
    return g;
  }, [originId]);

  // initial: the material, its campaign(s), the strongest 4–6 traces
  useEffect(() => {
    let live = true;
    (async () => {
      const g = await fetchFocus(originId).catch(() => null);
      if (!live) return;
      const center: VNode = { ...(g?.nodes.find((x) => x.id === originId) ?? { id: originId, kind: 'incident', label: originId }), x: 0, y: 0, parent: null };
      const es: Record<string, VEdge> = {};
      const neigh: { node: GraphNode; w: number; e: GraphEdge }[] = [];
      for (const e of g?.edges ?? []) {
        const other = e.a === originId ? e.b : e.b === originId ? e.a : null;
        const nd = other ? g!.nodes.find((x) => x.id === other) : undefined;
        if (!nd) continue;
        const ev = evOf(nd);
        neigh.push({ node: nd, e, w: nd.kind === 'campaign' ? 99 : ev ? Math.abs(ev.weight) : e.weight ?? 0 });
      }
      const cid = decision.campaign_id ?? decision.candidate_campaign_id;
      const camps: GraphNode[] = [];
      if (cid && !neigh.some((x) => x.node.id === cid)) camps.push({ id: cid, kind: 'campaign', label: names[cid] ?? cid });
      const ru = decision.runner_up;
      if (ru && (ru.p ?? 0) >= 0.1 && ru.campaign_id !== cid) camps.push({ id: ru.campaign_id, kind: 'campaign', label: names[ru.campaign_id] ?? ru.campaign_id });
      const seen = new Set<string>();
      const ranked = neigh.sort((a, b) => b.w - a.w).filter((x) => (seen.has(x.node.id) ? false : (seen.add(x.node.id), true)));
      const campsIn = ranked.filter((x) => x.node.kind === 'campaign').map((x) => x.node);
      const rest = ranked.filter((x) => x.node.kind !== 'campaign');
      const top = rest.slice(0, 6).map((x) => x.node);
      const kids = [...campsIn, ...camps, ...top];
      const placed = place(center, null, kids, { [originId]: center });
      const ns: Record<string, VNode> = { [originId]: center };
      for (const k of placed) ns[k.id] = { ...k, pinned: true };
      for (const x of ranked) if (ns[x.node.id]) es[ekey(originId, x.node.id)] = { ...x.e, key: ekey(originId, x.node.id) };
      for (const c of camps) {
        const isRu = ru && c.id === ru.campaign_id;
        es[ekey(originId, c.id)] = { a: originId, b: c.id, type: 'member', key: ekey(originId, c.id), dashed: !!isRu || decision.decision !== 'assign',
          note: isRu ? `następna kampania · ${p2(ru!.p)}` : `${decision.decision === 'assign' ? 'dołącza' : 'kandydat'} · pewność ${p2(decision.p)}` };
      }
      for (const c of campsIn) es[ekey(originId, c.id)] = { ...es[ekey(originId, c.id)], note: `${decision.decision === 'assign' ? 'dołącza' : 'kandydat'} · pewność ${p2(decision.p)}` };
      const panel = g ? normalizePanel(g.panel as Record<string, unknown>, center) : undefined;
      const hidden = Math.max(0, rest.length - top.length);
      initial.current = { nodes: ns, edges: es, panel, more: hidden };
      setNodes(ns); setEdges(es); setExpanded([]); setSelected(originId);
      setPanels(panel ? { [originId]: panel } : {}); setMore(hidden ? { [originId]: hidden } : {});
      setAnim({ from: Object.fromEntries(Object.keys(ns).map((k) => [k, { x: 0, y: 0 }])), t0: performance.now() });
      fitTo(ns);
    })();
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [originId, decision.incident_id]);

  const descendants = (id: string, ns: Record<string, VNode>): string[] => {
    const out: string[] = [];
    const walk = (p: string) => { for (const x of Object.values(ns)) if (x.parent === p && !x.pinned && !out.includes(x.id)) { out.push(x.id); walk(x.id); } };
    walk(id);
    return out;
  };

  const collapse = useCallback((id: string) => {
    const ns = nodesRef.current;
    const gone = descendants(id, ns);
    const from: Record<string, Pt> = {};
    const next = { ...ns };
    for (const g of gone) { from[g] = { x: ns[g].x, y: ns[g].y }; next[g] = { ...ns[g], x: ns[id].x, y: ns[id].y, removing: true }; }
    setNodes(next);
    setExpanded((e) => e.filter((x) => x !== id && !gone.includes(x)));
    setMore((m) => { const c = { ...m }; delete c[id]; return c; });
    setAnim({ from, t0: performance.now() });
    setSelected(id);
    setTimeout(() => {
      setNodes((cur) => { const c = { ...cur }; for (const g of gone) if (c[g]?.removing) delete c[g]; return c; });
      setEdges((cur) => { const c = { ...cur }; for (const k of Object.keys(c)) if (gone.includes(c[k].a) || gone.includes(c[k].b)) delete c[k]; return c; });
    }, ANIM + 20);
  }, []);

  const expand = useCallback(async (id: string) => {
    if (busy) return;
    if (expRef.current.includes(id)) { collapse(id); return; }
    setBusy(id); setNote(null); setSelected(id);
    const g = await fetchFocus(id).catch(() => null);
    setBusy(null);
    if (!g || !g.nodes?.length) { setNote('Ten węzeł nie ma więcej powiązań w bazie.'); return; }
    // the API resolves aliases (trace:fb_pixel:… → trace:fb_pixels:…): continue with the real id
    const realId = g.focus && g.nodes.some((x) => x.id === g.focus) ? g.focus : id;
    if (realId !== id) {
      if (expRef.current.includes(realId)) { setSelected(realId); return; }
      id = realId;
      setSelected(realId);
    }
    const ns = { ...nodesRef.current };
    let center = ns[id];
    if (!center) {
      // chip from the Raport that is not on screen yet: hang it off the material
      const raw = g.nodes.find((x) => x.id === id) ?? { id, kind: 'trace' as const, label: id };
      const [p] = place(ns[originId], null, [raw], ns);
      center = p; ns[id] = p;
    }
    const neigh: { node: GraphNode; w: number }[] = [];
    for (const e of g.edges) {
      const other = e.a === id ? e.b : e.b === id ? e.a : null;
      const nd = other ? g.nodes.find((x) => x.id === other) : undefined;
      if (nd && !neigh.some((x) => x.node.id === nd.id)) neigh.push({ node: nd, w: nd.kind === 'campaign' ? 99 : e.weight ?? 0 });
    }
    const fresh = neigh.filter((x) => !ns[x.node.id] || ns[x.node.id].removing).sort((a, b) => b.w - a.w);
    const take = fresh.slice(0, 8).map((x) => x.node);
    const grand = center.parent ? ns[center.parent] : (id === originId ? null : ns[originId]);
    const placed = place(center, grand ?? null, take, ns);
    const from: Record<string, Pt> = {};
    for (const p of placed) { ns[p.id] = p; from[p.id] = { x: center.x, y: center.y }; }
    const es = { ...edgesRef.current };
    for (const e of g.edges) if (ns[e.a] && ns[e.b] && !es[ekey(e.a, e.b)]) es[ekey(e.a, e.b)] = { ...e, key: ekey(e.a, e.b) };
    setNodes(ns); setEdges(es);
    setExpanded((x) => [...x.filter((y) => y !== id), id]);
    setPanels((pn) => ({ ...pn, [id]: normalizePanel(g.panel as Record<string, unknown>, g.nodes.find((x) => x.id === id)) }));
    setMore((m) => ({ ...m, [id]: Math.max(0, fresh.length - take.length) }));
    if (!take.length) setNote(neigh.length ? 'Wszystkie powiązania tego węzła są już na ekranie.' : 'Ten węzeł nie ma więcej powiązań w bazie.');
    setAnim({ from, t0: performance.now() });
    // keep new nodes in view: zoom out only when they fall outside
    setVb((v) => {
      const out = placed.some((p) => p.x < v.x + 60 || p.x > v.x + v.w - 60 || p.y < v.y + 40 || p.y > v.y + v.h - 60);
      if (!out) return v;
      const list = Object.values(ns);
      const x0 = Math.min(v.x, ...list.map((p) => p.x - 120)), x1 = Math.max(v.x + v.w, ...list.map((p) => p.x + 120));
      const y0 = Math.min(v.y, ...list.map((p) => p.y - 70)), y1 = Math.max(v.y + v.h, ...list.map((p) => p.y + 90));
      let w = x1 - x0, h = y1 - y0;
      if (w / h < aspect) w = h * aspect; else h = w / aspect;
      return { x: (x0 + x1) / 2 - w / 2, y: (y0 + y1) / 2 - h / 2, w, h };
    });
  }, [busy, collapse, fetchFocus, originId, aspect]);

  // a chip clicked in the Raport → unfold it
  const lastFocus = useRef<string | null>(null);
  useEffect(() => {
    if (!focusId || !Object.keys(nodes).length || lastFocus.current === focusId) return;
    lastFocus.current = focusId;
    if (!expanded.includes(focusId)) expand(focusId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusId, nodes]);
  useEffect(() => { if (focusMissing) setNote('Ten ślad liczy się do wyniku, ale nie jest osobnym węzłem w grafie.'); }, [focusMissing]);

  function reset() {
    const i = initial.current;
    if (!i) return;
    const cur = nodesRef.current;
    const from: Record<string, Pt> = {};
    for (const k of Object.keys(i.nodes)) if (cur[k]) from[k] = { x: cur[k].x, y: cur[k].y };
    setNodes(i.nodes); setEdges(i.edges); setExpanded([]); setSelected(originId); setNote(null);
    setMore(i.more ? { [originId]: i.more } : {});
    setAnim({ from, t0: performance.now() });
    fitTo(i.nodes);
  }
  function centreOn(id: string) {
    const nd = nodesRef.current[id];
    if (!nd) return;
    setSelected(id);
    setVb((v) => ({ ...v, x: nd.x - v.w / 2, y: nd.y - v.h / 2 }));
  }

  // ---------------------------------------------------------------- pan / zoom
  const drag = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);
  const toSvg = (cx: number, cy: number) => {
    const r = svg.current!.getBoundingClientRect();
    return { x: vb.x + ((cx - r.left) / r.width) * vb.w, y: vb.y + ((cy - r.top) / r.height) * vb.h };
  };
  const zoom = (f: number) => setVb((v) => ({ x: v.x + (v.w * (1 - f)) / 2, y: v.y + (v.h * (1 - f)) / 2, w: v.w * f, h: v.h * f }));

  // ---------------------------------------------------------------- render
  const list = Object.values(nodes);
  const hl = hover?.node ?? null;
  const hlEdge = hover?.edge ?? null;
  const touches = (e: VEdge, id: string) => e.a === id || e.b === id;
  const degree = (id: string) => Object.values(edges).filter((e) => touches(e, id)).length;
  const expandable = (nd: VNode) => !expanded.includes(nd.id) && (meta(nd).count == null || (meta(nd).count ?? 0) > degree(nd.id) || (more[nd.id] ?? 0) > 0);
  const badge = (nd: VNode) => {
    if (expanded.includes(nd.id)) return (more[nd.id] ?? 0) > 0 ? `+${more[nd.id]}` : '−';
    const c = meta(nd).count;
    const extra = c != null ? c - degree(nd.id) : null;
    if (nd.id === originId && more[originId]) return `+${more[originId]}`;
    return extra != null && extra > 0 ? `+${extra}` : expandable(nd) ? '+' : null;
  };
  const panel = useMemo(() => {
    const raw = panels[selected];
    const nd = nodes[selected];
    if (!raw || !nd) return raw;
    const l = label(nd); const m = meta(nd);
    const p: FocusPanel = { ...raw, facts: raw.facts?.filter((f) => f.v && f.v !== '—') };
    if (nd.kind === 'trace') {
      p.kind_label = `Ślad · ${LAYER_LABEL[(l.layer ?? 'kit') as Layer] ?? ''}`;
      const value = m.value ?? nd.id.split(':').slice(2).join(':');
      p.title = value ? `${l.title}: ${prettyDisplay(value)}` : l.title;
      p.description = [l.layer ? LAYER_HINT[l.layer as Layer] : '', m.count != null ? `Ten ślad ma ${plural(m.count, 'materiał', 'materiały', 'materiałów')} w bazie.` : ''].filter(Boolean).join(' ');
    } else if (nd.kind === 'incident') {
      p.title = (nd.id === originId ? originTitle : titles.get(nd.id)) || nd.id;
      p.description = nd.id === originId ? 'Sprawdzany materiał.' : `Materiał ${nd.id}.`;
      if (nd.id === originId) { p.action = undefined; p.link = undefined; }
    } else if (nd.kind === 'person') {
      p.title = l.title; p.description = m.count != null ? `Wizerunek albo nazwisko w ${plural(m.count, 'materiale', 'materiałach', 'materiałach')}.` : p.description;
    } else if (nd.kind === 'campaign') {
      p.title = names[nd.id] ?? nd.id; p.description = undefined;
    } else {
      p.title = prettyDisplay(p.title); p.description = prettyDisplay(p.description);
    }
    p.bot_text = p.bot_text ? prettyDisplay(p.bot_text).replace(/^.*?:\s*(\d+) połączeń; most do ([^.]+)\.$/, (_m, k: string, o: string) => `${plural(+k, 'powiązanie', 'powiązania', 'powiązań')} w grafie; łączy się z ${o === originId ? 'tym materiałem' : o}.`) : p.bot_text;
    return p;
  }, [panels, selected, nodes, label, originId, originTitle, titles, names]);
  const hoverNode = hl ? nodes[hl] : null;
  const hoverEdge = hlEdge ? edges[hlEdge] : null;
  const tipBox = (() => {
    if (!hover || !svg.current) return null;
    const r = svg.current.getBoundingClientRect();
    const b = box.current!.getBoundingClientRect();
    return { left: hover.x - b.left, top: hover.y - b.top, w: r.width };
  })();
  const nodeAria = (nd: VNode) => {
    const l = label(nd);
    return `${KIND_LABEL[nd.kind] ?? nd.kind}: ${l.title}${l.sub ? `, ${l.sub}` : ''}. ${expanded.includes(nd.id) ? 'Rozwinięty, Enter zwija.' : 'Enter rozwija powiązania.'}`;
  };
  const trail = [originId, ...expanded.filter((x) => x !== originId)];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 justify-between">
        <nav aria-label="Rozwinięte węzły" className="flex flex-wrap items-center gap-1 text-[13px] min-w-0">
          {trail.map((id, i) => nodes[id] && (
            <span key={id} className="inline-flex items-center gap-1 min-w-0">
              {i > 0 && <span className="text-tx4" aria-hidden="true">›</span>}
              <button type="button" onClick={() => centreOn(id)} className={'px-2 py-1 rounded-lg hover:bg-bg3 truncate max-w-[220px] ' + (selected === id ? 'font-semibold text-tx1' : 'text-tx2')}>{label(nodes[id]).title}</button>
            </span>
          ))}
        </nav>
        <div className="hidden sm:flex items-center gap-1.5">
          <button type="button" className="chip" onClick={() => zoom(0.8)} aria-label="Przybliż">+</button>
          <button type="button" className="chip" onClick={() => zoom(1.25)} aria-label="Oddal">−</button>
          <button type="button" className="chip" onClick={() => fitTo(nodesRef.current)}>Wyśrodkuj</button>
          <button type="button" className="chip" onClick={reset} disabled={!expanded.length}>Zwiń wszystko</button>
        </div>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-5 items-start">
        <div className="min-w-0">
          {/* desktop / tablet: the graph */}
          <div ref={box} className="hidden sm:block relative h-[600px] rounded-[22px] border border-line1 bg-[#FCFCFC] overflow-hidden select-none">
            <svg ref={svg} viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`} className="w-full h-full touch-none" role="group" aria-label="Graf powiązań materiału"
              onPointerDown={(e) => { if ((e.target as Element).closest('[data-node]')) return; drag.current = { x: e.clientX, y: e.clientY, vx: vb.x, vy: vb.y }; (e.currentTarget as Element).setPointerCapture(e.pointerId); }}
              onPointerMove={(e) => { const d = drag.current; if (!d || !svg.current) return; const r = svg.current.getBoundingClientRect(); setVb((v) => ({ ...v, x: d.vx - ((e.clientX - d.x) / r.width) * v.w, y: d.vy - ((e.clientY - d.y) / r.height) * v.h })); }}
              onPointerUp={() => { drag.current = null; }}
              onWheel={(e) => { if (!e.ctrlKey && !e.metaKey) return; e.preventDefault(); const p = toSvg(e.clientX, e.clientY); const f = e.deltaY > 0 ? 1.12 : 0.89; setVb((v) => ({ x: p.x - (p.x - v.x) * f, y: p.y - (p.y - v.y) * f, w: v.w * f, h: v.h * f })); }}
              style={{ cursor: drag.current ? 'grabbing' : 'grab' }}>
              <g>
                {Object.values(edges).map((e) => {
                  if (!nodes[e.a] || !nodes[e.b]) return null;
                  const A = pos(e.a), B = pos(e.b);
                  const col = e.type === 'member' ? '#0A0A0A' : e.type === 'operator' || e.type === 'operation' ? '#8B5CF6' : LAYER_COLOR[e.type] ?? '#A3A3A3';
                  const on = hl ? touches(e, hl) : hlEdge ? hlEdge === e.key : true;
                  const gone = nodes[e.a].removing || nodes[e.b].removing;
                  const ev = evOf([nodes[e.a], nodes[e.b]].find((x) => x.kind === 'trace'));
                  const w = Math.max(1.2, Math.min(4, (ev ? Math.abs(ev.weight) / 2 : e.weight ?? 1) * 1.1));
                  return (
                    <g key={e.key} opacity={gone ? 0.15 : on ? 1 : 0.18} style={{ transition: 'opacity .2s' }}>
                      <line x1={A.x} y1={A.y} x2={B.x} y2={B.y} stroke={col} strokeWidth={hlEdge === e.key ? w + 1.5 : w} strokeDasharray={e.dashed || e.type === 'operator' ? '6 6' : undefined} strokeLinecap="round" />
                      <line x1={A.x} y1={A.y} x2={B.x} y2={B.y} stroke="transparent" strokeWidth={14} style={{ cursor: 'help' }}
                        onPointerEnter={(ev2) => setHover({ edge: e.key, x: ev2.clientX, y: ev2.clientY })} onPointerMove={(ev2) => setHover({ edge: e.key, x: ev2.clientX, y: ev2.clientY })} onPointerLeave={() => setHover(null)} />
                    </g>
                  );
                })}
              </g>
              <g>
                {list.map((nd) => {
                  const P = pos(nd.id);
                  const l = label(nd);
                  const isOrigin = nd.id === originId;
                  const r = isOrigin ? 30 : nd.kind === 'campaign' ? 26 : 19;
                  const col = nd.kind === 'trace' ? LAYER_COLOR[l.layer ?? ''] ?? '#525252' : KIND_COLOR[nd.kind] ?? '#525252';
                  const filled = nd.kind === 'campaign' || isOrigin;
                  const on = hl ? hl === nd.id || Object.values(edges).some((e) => touches(e, hl) && touches(e, nd.id)) : hlEdge ? edges[hlEdge] && touches(edges[hlEdge], nd.id) : true;
                  const sel = selected === nd.id;
                  const bd = badge(nd);
                  const thumb = isOrigin && originThumb;
                  return (
                    <g key={nd.id} data-node transform={`translate(${P.x} ${P.y})`} opacity={nd.removing ? 0 : on ? 1 : 0.28}
                      style={{ transition: 'opacity .25s', cursor: 'pointer', outline: 'none' }} tabIndex={0} role="button" aria-label={nodeAria(nd)} aria-expanded={expanded.includes(nd.id)}
                      onClick={() => expand(nd.id)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); expand(nd.id); } }}
                      onPointerEnter={(e) => setHover({ node: nd.id, x: e.clientX, y: e.clientY })}
                      onPointerMove={(e) => setHover({ node: nd.id, x: e.clientX, y: e.clientY })}
                      onPointerLeave={() => setHover(null)}
                      onFocus={() => { const r = svg.current!.getBoundingClientRect(); setHover({ node: nd.id, x: r.left + ((P.x - vb.x) / vb.w) * r.width, y: r.top + ((P.y - vb.y) / vb.h) * r.height }); }}
                      onBlur={() => setHover(null)}>
                      {sel && <circle r={r + 7} fill="none" stroke="#0A0A0A" strokeWidth={3} />}
                      {hl === nd.id && !sel && <circle r={r + 6} fill="none" stroke={col} strokeOpacity={0.35} strokeWidth={6} />}
                      {thumb ? (
                        <>
                          <clipPath id="origin-clip"><circle r={r} /></clipPath>
                          <image href={originThumb} x={-r} y={-r} width={r * 2} height={r * 2} preserveAspectRatio="xMidYMin slice" clipPath="url(#origin-clip)" />
                          <circle r={r} fill="none" stroke="#0A0A0A" strokeWidth={2.5} />
                        </>
                      ) : (
                        <>
                          <circle r={r} fill={filled ? '#0A0A0A' : '#fff'} stroke={col} strokeWidth={filled ? 0 : 2} />
                          {!filled && <circle r={r - 4} fill={col} fillOpacity={0.09} />}
                          <g transform={isOrigin ? 'scale(1.5)' : nd.kind === 'campaign' ? 'scale(1.3)' : undefined}><Glyph kind={nd.kind} layer={l.layer} color={filled ? '#fff' : col} /></g>
                        </>
                      )}
                      {busy === nd.id && <circle r={r + 4} fill="none" stroke="#0A0A0A" strokeWidth={2} strokeDasharray="10 8"><animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="1s" repeatCount="indefinite" /></circle>}
                      {bd && (
                        <g transform={`translate(${r * 0.74} ${-r * 0.74})`}>
                          <rect x={-2} y={-9} width={Math.max(18, bd.length * 7 + 8)} height={18} rx={9} fill={expanded.includes(nd.id) ? '#fff' : '#0A0A0A'} stroke="#0A0A0A" strokeWidth={1.2} />
                          <text x={Math.max(18, bd.length * 7 + 8) / 2 - 2} y={4} textAnchor="middle" fontSize={11} fontWeight={700} fill={expanded.includes(nd.id) ? '#0A0A0A' : '#fff'} fontFamily="var(--font-geist-mono), monospace">{bd}</text>
                        </g>
                      )}
                      <g transform={`translate(0 ${r + 16})`} style={{ pointerEvents: 'none' }}>
                        <text textAnchor="middle" fontSize={13} fontWeight={600} fill="#0A0A0A" stroke="#FCFCFC" strokeWidth={4} paintOrder="stroke">{l.title}</text>
                        <text y={16} textAnchor="middle" fontSize={11.5} fill="#737373" stroke="#FCFCFC" strokeWidth={4} paintOrder="stroke" fontFamily={nd.kind === 'trace' ? 'var(--font-geist-mono), monospace' : undefined}>{l.sub}</text>
                      </g>
                    </g>
                  );
                })}
              </g>
            </svg>
            {/* tooltip */}
            {tipBox && (hoverNode || hoverEdge) && (
              <div role="tooltip" className="pointer-events-none absolute z-10 max-w-[300px] rounded-xl bg-tx1 text-white px-3 py-2 text-[12.5px] leading-snug shadow-dark"
                style={{ left: Math.min(tipBox.left + 14, (box.current?.clientWidth ?? 800) - 310), top: tipBox.top + 14 }}>
                {hoverNode && (() => {
                  const l = label(hoverNode); const m = meta(hoverNode); const ev = evOf(hoverNode);
                  const full = hoverNode.kind === 'trace' ? m.value ?? hoverNode.id : hoverNode.kind === 'incident' ? (hoverNode.id === originId ? originTitle : titles.get(hoverNode.id)) ?? hoverNode.id : names[hoverNode.id] ?? l.title;
                  return (
                    <>
                      <span className="block text-[11px] uppercase tracking-[.06em] text-line3">{hoverNode.kind === 'trace' ? `Ślad · ${LAYER_LABEL[(l.layer ?? 'kit') as Layer] ?? ''}` : KIND_LABEL[hoverNode.kind]}</span>
                      <b className="block font-semibold break-words">{l.title}</b>
                      <span className="block font-mono text-[11.5px] text-line2 break-all">{full}</span>
                      {hoverNode.kind === 'trace' && l.layer && LAYER_HINT[l.layer as Layer] && <span className="block text-line3 pt-0.5">{LAYER_HINT[l.layer as Layer]}</span>}
                      {m.count != null && hoverNode.kind !== 'incident' && <span className="block pt-1">{hoverNode.kind === 'campaign' ? `${fmtN(m.count)} powiązań` : `wspólny dla ${plural(m.count, 'materiału', 'materiałów', 'materiałów')}`}</span>}
                      {ev && <span className="block">waga w tym wyniku {w1(ev.weight)}</span>}
                      <span className="block text-line3 pt-1">{expanded.includes(hoverNode.id) ? 'Kliknij, żeby zwinąć' : 'Kliknij, żeby rozwinąć powiązania'}</span>
                    </>
                  );
                })()}
                {hoverEdge && !hoverNode && <span>{edgeText(hoverEdge)}</span>}
              </div>
            )}
            <span className="absolute left-3 bottom-2.5 text-[11.5px] text-tx4">Przeciągnij tło, żeby przesunąć · Ctrl + kółko: powiększenie · Tab i Enter: węzły z klawiatury</span>
            {note && <span role="status" className="absolute right-3 bottom-2.5 text-[12px] bg-white border border-line1 rounded-lg px-2.5 py-1 text-tx2">{note}</span>}
          </div>

          {/* phone: the same graph as a list */}
          <ul className="sm:hidden m-0 p-0 list-none flex flex-col gap-1.5" aria-label="Powiązania materiału">
            {(() => {
              const rows: React.ReactElement[] = [];
              const walk = (id: string, depth: number) => {
                const nd = nodes[id];
                if (!nd || nd.removing) return;
                const l = label(nd);
                const bd = badge(nd);
                const col = nd.kind === 'trace' ? LAYER_COLOR[l.layer ?? ''] ?? '#525252' : KIND_COLOR[nd.kind] ?? '#525252';
                const via = Object.values(edges).find((e) => nd.parent && touches(e, nd.parent) && touches(e, id));
                rows.push(
                  <li key={id} style={{ paddingLeft: Math.min(depth, 4) * 14 }}>
                    <button type="button" onClick={() => expand(id)} aria-expanded={expanded.includes(id)}
                      className={'w-full min-h-[52px] flex items-center gap-2.5 px-3 py-2 rounded-2xl border text-left ' + (selected === id ? 'border-tx1 border-2' : 'border-line1') + ' bg-bg1'}>
                      <svg width={26} height={26} viewBox="-13 -13 26 26" aria-hidden="true" className="flex-none"><circle r={12} fill={nd.kind === 'campaign' || id === originId ? '#0A0A0A' : '#fff'} stroke={col} strokeWidth={1.5} /><Glyph kind={nd.kind} layer={l.layer} color={nd.kind === 'campaign' || id === originId ? '#fff' : col} /></svg>
                      <span className="flex-1 min-w-0"><b className="block text-[13.5px] font-semibold truncate">{l.title}</b><span className="block text-[12px] text-tx3 truncate">{[l.sub, via ? edgeText(via) : null].filter(Boolean).join(' · ')}</span></span>
                      {busy === id ? <span className="spin" /> : bd && <span className="pill bg-bg3 text-tx1 font-mono">{bd}</span>}
                    </button>
                  </li>,
                );
                for (const k of Object.values(nodes)) if (k.parent === id) walk(k.id, depth + 1);
              };
              walk(originId, 0);
              return rows;
            })()}
            {note && <li role="status" className="text-[12.5px] text-tx3 px-1">{note}</li>}
          </ul>
        </div>
        {panel ? <Panel p={panel} onClose={() => setSelected(originId)} /> : <div className="hidden xl:block" />}
      </div>
    </div>
  );
}

