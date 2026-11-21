// Adapters between GET /graph payloads and the focus views (boards 4a–4d).
import type { BotName, CampaignSummary, EvidenceItem, FocusPanel, GraphNode, GraphPayload } from './contracts';
import { BOTS } from './copy';

/** Node id of the graph a chip opens. Ids follow the API: bare domain, `trace:kit`, `trace:capi`, `cert:…`,
 *  `person:<name>`, incident / campaign / operator ids. */
export function focusIdOf(e: EvidenceItem, incidentDomain?: string | null): string {
  const f = e.field.toLowerCase();
  if (e.type === 'persons' || f.includes('face') || f.includes('person')) return `person:${(e.value || e.display.split('·')[0]).trim()}`;
  if (e.type === 'kit' || f.includes('kit')) return 'trace:kit';
  if (f.includes('capi')) return 'trace:capi';
  if (f.includes('pixel')) return `trace:pixel:${e.value}`;
  if (f.includes('cert')) return incidentDomain || 'cert:le-r11-night';
  if (e.type === 'infra' && f.includes('cdn')) return 'trace:cdn';
  if (e.type === 'infra') return incidentDomain || `trace:${e.value}`;
  if (e.type === 'content') return `trace:content:${e.value}`;
  return `trace:${e.field}:${e.value}`;
}

const KIND_LABEL: Record<string, string> = {
  domain: 'Domena', trace: 'Ślad techniczny', person: 'Osoba', incident: 'Materiał', campaign: 'Kampania', operator: 'Operator',
  operation: 'Operacja', cert: 'Certyfikat', advertiser: 'Reklamodawca',
};

/** Accepts the web's FocusPanel and the API's looser shape ({kind, facts: ["K: V"], bot_sentence: "Bot: …", primary_action}). */
export function normalizePanel(raw: Record<string, unknown> | null | undefined, center?: GraphNode): FocusPanel {
  const r = (raw ?? {}) as Record<string, unknown>;
  const p: FocusPanel = { ...(r as FocusPanel) };
  if (!p.kind_label) p.kind_label = KIND_LABEL[String(r.kind ?? center?.kind ?? '')] ?? undefined;
  if (!p.title) p.title = center?.label;
  if (Array.isArray(r.facts)) {
    p.facts = (r.facts as unknown[]).map((f) => {
      if (typeof f === 'string') { const i = f.indexOf(':'); return i > 0 ? { k: f.slice(0, i).trim(), v: f.slice(i + 1).trim() } : { k: f, v: '' }; }
      const o = f as { k?: string; v?: string; label?: string; value?: string };
      return { k: o.k ?? o.label ?? '', v: String(o.v ?? o.value ?? '') };
    });
  }
  if (!p.bot_text && typeof r.bot_sentence === 'string') {
    const s = r.bot_sentence as string;
    const m = /^([A-ZĄĆĘŁŃÓŚŹŻ][\wąćęłńóśźż]+):\s*(.*)$/.exec(s);
    const bot = m && BOTS.find((b) => b.name === m[1]);
    p.bot_text = bot ? m![2] : s;
    if (bot) p.bot = bot.key as BotName;
  }
  if (!p.action && r.primary_action && typeof r.primary_action === 'object') {
    const a = r.primary_action as { label: string; href?: string };
    p.action = { label: a.label, href: a.href?.replace('/slad/domain/', '/slad/domena/').replace('/slad/person/', '/slad/osoba/') };
  }
  if (!p.link && r.link && typeof r.link === 'object') p.link = r.link as FocusPanel['link'];
  return p;
}

/** Keep the focus node, the origin and the focus node's direct neighbours (max 6), so a whole-graph answer
 *  still renders as a focus view. */
export function neighbourhood(g: GraphPayload, focus: string, origin: string): GraphPayload | null {
  const center = g.nodes.find((n) => n.id === focus);
  if (!center) return null;
  const adj = new Set<string>();
  for (const e of g.edges) { if (e.a === focus) adj.add(e.b); if (e.b === focus) adj.add(e.a); }
  adj.delete(origin);
  const byId = new Map(g.nodes.map((n) => [n.id, n]));
  const others = [...adj].map((id) => byId.get(id)).filter(Boolean) as GraphNode[];
  const nodes = [center, ...others.slice(0, 6)];
  const o = byId.get(origin) ?? { id: origin, kind: 'incident' as const, label: origin, meta: {} };
  nodes.unshift({ ...o, meta: { ...(o.meta ?? {}), sub: 'ten materiał', thumb: true } });
  return { ...g, nodes, focus, panel: g.panel };
}

export function campaignTitle(c?: Pick<CampaignSummary, 'id' | 'name'> | null): string {
  if (!c) return '';
  const name = c.name.includes('«') ? c.name : `«${c.name.split(' — ')[0].trim()}»`;
  return name;
}
