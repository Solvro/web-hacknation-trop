// Adapters between GET /graph payloads and the focus views (boards 4a–4d).
import type { BotName, CampaignSummary, EvidenceItem, FocusPanel, GraphNode, GraphPayload } from './contracts';
import { BOTS, fmtDate } from './copy';

/** Focus request for an evidence chip: `ev:<field>:<value>`; `resolveNodeId` maps it onto a real graph node. */
export function focusIdOf(e: EvidenceItem, _incidentDomain?: string | null): string {
  return `ev:${e.field}:${e.value}`;
}

const DOMAIN_FIELDS = /^(entry_url|final_url|domain|registration|cert|cert_batch|domain_dna|history|etld1|host)$/;

/** Graph node id for a Raport chip (`ev:<field>:<value>`), resolved server-side by WS2's aliases: persons →
 *  `person:<name>`, URLs / domain fields → `d:<host>`, everything else `trace:<field>:<value>` (the API answers with
 *  the real node, or a synthetic one next to the origin, so every chip opens). */
export function chipNodeId(id: string, incidentDomain?: string | null): string {
  if (!id.startsWith('ev:')) return id;
  const rest = id.slice(3);
  const i = rest.indexOf(':');
  const field = rest.slice(0, i);
  const value = rest.slice(i + 1);
  if (/person|face/.test(field)) return `person:${value.toLowerCase()}`;
  if (/^https?:\/\//.test(value)) { try { return `d:${new URL(value).hostname}`; } catch { /* fall through */ } }
  if (DOMAIN_FIELDS.test(field) && incidentDomain) return `d:${incidentDomain}`;
  return `trace:${field}:${value}`;
}

/** Find the graph node a focus request means. Exact ids pass through; `ev:` ids match by value
 *  (`trace:<field>s:<value>`, `person:<name>`, `d:<domain>`), case-insensitive. */
export function resolveNodeId(g: GraphPayload, id: string, incidentDomain?: string | null): string | null {
  const nodes = g.nodes ?? [];
  if (nodes.some((n) => n.id === id)) return id;
  const lc = (s: string) => s.toLowerCase();
  if (!id.startsWith('ev:')) {
    const bare = id.replace(/^(d[:-]|domain:)/, '');
    const hit = nodes.find((n) => lc(n.id) === lc(id) || n.id === `d:${bare}` || n.id === `d-${bare}` || lc(n.label) === lc(bare));
    return hit?.id ?? null;
  }
  const rest = id.slice(3);
  const i = rest.indexOf(':');
  const field = rest.slice(0, i);
  const value = rest.slice(i + 1);
  if (!value) return null;
  if (/person|face/.test(field)) {
    const hit = nodes.find((n) => n.kind === 'person' && (lc(n.id) === lc(`person:${value}`) || lc(n.label) === lc(value)));
    if (hit) return hit.id;
  }
  if (DOMAIN_FIELDS.test(field) || /^https?:\/\//.test(value)) {
    let host = incidentDomain ?? '';
    try { if (/^https?:\/\//.test(value)) host = new URL(value).hostname; } catch { /* keep */ }
    const hit = nodes.find((n) => n.kind === 'domain' && (n.id === `d:${host}` || n.id === `d-${host}` || n.label === host));
    if (hit) return hit.id;
  }
  const hit = nodes.find((n) => n.kind === 'trace' && (lc(n.id).endsWith(`:${lc(value)}`) || lc(n.id) === lc(`trace:${field}:${value}`) || lc(n.id) === lc(`trace:${field}s:${value}`)))
    ?? nodes.find((n) => lc(n.id).endsWith(`:${lc(value)}`));
  return hit?.id ?? null;
}

const KIND_LABEL: Record<string, string> = {
  domain: 'Domena', trace: 'Ślad techniczny', person: 'Osoba', incident: 'Materiał', campaign: 'Kampania', operator: 'Operator',
  operation: 'Operacja', cert: 'Certyfikat', advertiser: 'Reklamodawca',
};
const EN_KIND = new Set(Object.keys(KIND_LABEL));
const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1).toLowerCase() : s);
const looksIso = (v: string) => /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v);

/** Accepts the web's FocusPanel and the API's looser shapes; translates leftovers (English kinds, ISO dates, bot names). */
export function normalizePanel(raw: Record<string, unknown> | null | undefined, center?: GraphNode): FocusPanel {
  const r = (raw ?? {}) as Record<string, unknown>;
  const p: FocusPanel = { ...(r as FocusPanel) };
  const kind = String(r.kind ?? center?.kind ?? '');
  p.kind_label = p.kind_label ? (p.kind_label === p.kind_label.toUpperCase() ? cap(p.kind_label) : p.kind_label) : KIND_LABEL[kind];
  if (p.kind_label && /^incydent$/i.test(p.kind_label)) p.kind_label = 'Materiał';
  if (p.badge && EN_KIND.has(p.badge.text)) p.badge = undefined;
  if (p.tags) p.tags = p.tags.filter((t) => !EN_KIND.has(t));
  if (!p.title) p.title = center?.label;
  if (Array.isArray(r.facts)) {
    p.facts = (r.facts as unknown[]).map((f) => {
      if (typeof f === 'string') { const i = f.indexOf(':'); return i > 0 ? { k: f.slice(0, i).trim(), v: f.slice(i + 1).trim() } : { k: f, v: '' }; }
      const o = f as { k?: string; v?: string; label?: string; value?: string };
      return { k: o.k ?? o.label ?? '', v: String(o.v ?? o.value ?? '') };
    }).map((f) => (looksIso(f.v) ? { ...f, v: fmtDate(f.v) } : f));
  }
  if (p.bot && !BOTS.some((b) => b.key === p.bot)) {
    const b = BOTS.find((x) => x.name.toLowerCase() === String(p.bot).toLowerCase());
    p.bot = b ? (b.key as BotName) : undefined;
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
    p.action = { label: a.label, href: a.href };
  }
  const fixHref = (h?: string) => h?.replace('/incydenty/', '/analiza/').replace('/incidents/', '/analiza/').replace('/campaigns/', '/kampanie/')
    .replace('/slad/domain/', '/slad/domena/').replace('/slad/person/', '/slad/osoba/').replace('/slad/pixel/', '/slad/piksel/');
  if (p.action) p.action = { ...p.action, href: fixHref(p.action.href) };
  if (!p.link && r.link && typeof r.link === 'object') p.link = r.link as FocusPanel['link'];
  if (p.link) p.link = { ...p.link, href: fixHref(p.link.href) ?? '/' };
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
  const rank = (n: GraphNode) => ({ campaign: 0, operator: 1, person: 2, domain: 3, trace: 4, incident: 5 } as Record<string, number>)[n.kind] ?? 6;
  const others = ([...adj].map((id) => byId.get(id)).filter(Boolean) as GraphNode[]).sort((a, b) => rank(a) - rank(b));
  const nodes = [center, ...others.slice(0, 6)];
  if (origin) {
    const o = byId.get(origin) ?? { id: origin, kind: 'incident' as const, label: origin, meta: {} };
    nodes.unshift({ ...o, meta: { ...(o.meta ?? {}), sub: 'ten materiał', thumb: true } });
  }
  return { ...g, nodes, focus, panel: g.panel };
}

/** Display name: short names get «», long descriptive (real-mode) names stay as they are. */
export function campaignTitle(c?: Pick<CampaignSummary, 'id' | 'name'> | null): string {
  if (!c) return '';
  const name = (c.name ?? '').trim();
  if (!name || name.includes('«')) return name;
  if (name.length <= 28 && !name.includes(' — ')) return `«${name}»`;
  return name;
}

/** Title-case a lower-case person name from the extractor ("rafał brzoska" → "Rafał Brzoska"). */
export const personName = (s: string) => s.replace(/(^|[\s-])(\p{L})/gu, (_, a, b) => a + b.toUpperCase());
