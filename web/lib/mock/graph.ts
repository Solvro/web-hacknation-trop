// GET /api/v1/graph fixtures: the KMP-017 cloud and the focus views of boards 4a–4d.
import type { FocusPanel, GraphEdge, GraphNode, GraphPayload } from '../contracts';

const node = (id: string, kind: GraphNode['kind'], label: string, meta: Record<string, unknown> = {}, extra: Partial<GraphNode> = {}): GraphNode =>
  ({ id, kind, label, size: 1, meta, ...extra });
const edge = (a: string, b: string, type: GraphEdge['type'], weight = 1, label?: string): GraphEdge => ({ a, b, type, weight, label: label ?? null });

/** Stable pseudo-random so the cloud looks the same on every render. */
function rng(seed: number) { return () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646; }

export function campaignCloud(campaignId = 'KMP-017'): GraphPayload {
  const r = rng(17);
  const n = campaignId === 'KMP-017' ? 46 : 12;
  const nodes: GraphNode[] = [node(campaignId, 'campaign', campaignId, {}, { size: 6 })];
  const edges: GraphEdge[] = [];
  for (let i = 0; i < n; i++) {
    const id = i === 0 ? 'INC-24702' : `INC-${24600 + Math.floor(r() * 300)}${i}`.slice(0, 9);
    const uid = nodes.some((x) => x.id === id) ? `${id}-${i}` : id;
    nodes.push(node(uid, 'incident', uid, { domain: ['velmoria.click', 'morvanta.click', 'orvinta.click', 'trastino.live', 'quorvex.click'][i % 5] }, { campaign_id: campaignId, size: 1 + r() * 1.5 }));
    edges.push(edge(campaignId, uid, 'member', 0.5 + r()));
  }
  return { nodes, edges, hulls: [{ id: campaignId, kind: 'campaign', members: nodes.map((x) => x.id), label: campaignId }], focus: null, panel: null };
}

const ORIGIN = (inc = 'INC-24817') => node(inc, 'incident', inc, { sub: 'ten materiał', thumb: true, role: 'origin' });

function focusPayload(origin: string, center: GraphNode, neighbours: { n: GraphNode; type?: GraphEdge['type']; dashed?: boolean }[], panel: FocusPanel): GraphPayload {
  return {
    nodes: [ORIGIN(origin), center, ...neighbours.map((x) => x.n)],
    edges: [edge(origin, center.id, 'member'), ...neighbours.map((x) => edge(center.id, x.n.id, x.type ?? 'infra', x.dashed ? 0.3 : 1))],
    hulls: [], focus: center.id, panel: panel as Record<string, unknown>,
  };
}

export const FOCUS: Record<string, (origin: string) => GraphPayload> = {
  'morvanta.click': (o) => focusPayload(o,
    node('morvanta.click', 'domain', 'morvanta.click', { kind_label: 'Domena', sub: 'aktywna · od 14.11' }),
    [
      { n: node('cert:le-r11-night', 'cert', 'certyfikat LE R11', { sub: '14.11, 02:10 · Notariusz', bot: 'notariusz' }), type: 'infra' },
      { n: node('kelvaro.live', 'domain', 'kelvaro.live', { sub: 'ta sama noc · KMP-017', bot: 'notariusz' }), type: 'infra' },
      { n: node('selqueno.live', 'domain', 'selqueno.live', { sub: 'ta sama noc · nie odpowiada', bot: 'notariusz' }), type: 'infra' },
      { n: node('kalvesto.live', 'domain', 'kalvesto.live', { sub: 'ta sama noc · jeszcze bez reklam', relation: 'oracle', bot: 'notariusz' }), type: 'operator', dashed: true },
      { n: node('INC-24702', 'incident', 'INC-24702 i 2 inne', { sub: 'reklamy z tą domeną', count: 3, thumb: true }), type: 'member' },
      { n: node('cdn:cloudflare', 'trace', 'Cloudflare', { sub: 'pominięty · 512 spraw', weak: true }), type: 'infra', dashed: true },
    ],
    {
      kind_label: 'Domena', badge: { text: 'aktywna', tone: 'g' }, title: 'morvanta.click',
      description: 'Założona tej samej nocy co 5 innych domen kampanii KMP-017.',
      facts: [{ k: 'Zarejestrowana', v: '14.11, 01:52' }, { k: 'Certyfikat', v: 'LE R11, 14.11 02:10' }, { k: 'Pierwsza reklama', v: '15.11' },
        { k: 'Reklamy', v: '4, ostatnia dziś 02:31' }, { k: 'Rejestrator', v: 'nieznany, RDAP milczy' }, { k: 'Zgłoszenia', v: 'CERT PL: ostrzeżenie' }],
      bot: 'notariusz', bot_text: 'Ta sama partia certyfikatów co kelvaro.live i selqueno.live.',
      action: { label: 'Szukaj sąsiednich domen', kind: 'investigate', seed: 'morvanta.click' },
      link: { label: 'albo pokaż wszystko o domenie', href: '/slad/domena/morvanta.click' },
    }),
  'trace:kit': (o) => focusPayload(o,
    node('trace:kit', 'trace', 'kit relay v1', { kind_label: 'Ślad techniczny', sub: '/api/v2/relay/lead/{uuid}/' }),
    [
      { n: node('KMP-017', 'campaign', 'KMP-017 «Zamach»', { sub: 'fałszywe newsy, „inwestycje”', count: 46, thumb: true }), type: 'kit' },
      { n: node('KMP-034', 'campaign', 'KMP-034 «Glikonor»', { sub: 'lek na cukrzycę', count: 12, thumb: true }), type: 'kit' },
      { n: node('OP-03', 'operator', 'OP-03 «Kestrel»', { sub: 'operator obu kampanii', relation: 'operator' }), type: 'operator', dashed: true },
      { n: node('trace:capi', 'trace', 'bramka CAPI cg-7f3a…', { sub: 'zawsze razem w KMP-017' }), type: 'tracking', dashed: true },
    ],
    {
      kind_label: 'Ślad techniczny', badge: { text: 'rzadki', tone: 'g' }, title: 'kit relay v1',
      description: 'Kod formularza, który wysyła dane ofiary. Ma go tylko jeden operator.',
      facts: [{ k: 'Ścieżka', v: '/api/v2/relay/lead/…' }, { k: 'W materiałach', v: '58 z 1 284' }, { k: 'Kampanie', v: 'KMP-017 (46), KMP-034 (12)' },
        { k: 'Pierwszy raz', v: '2.11' }, { k: 'Ostatni raz', v: 'dziś 02:31' }, { k: 'Waga w tym wyniku', v: '+2.7' }],
      bot: 'tropiciel', bot_text: 'Ten sam kit w dwóch kampaniach to zwykle jeden operator.',
      action: { label: 'Pokaż 58 materiałów', kind: 'trace', href: '/slad/kit/relay-v1' },
      link: { label: 'albo szukaj nowych stron z tym kitem', href: '/sledztwa?seed=%2Fapi%2Fv2%2Frelay%2Flead%2F' },
    }),
  'person:Jan Kowalski': (o) => focusPayload(o,
    node('person:Jan Kowalski', 'person', 'Jan Kowalski', { kind_label: 'Osoba', sub: 'twarz w reklamie · 0.91' }),
    [
      { n: node('KMP-017', 'campaign', 'KMP-017 «Zamach»', { sub: 'fałszywe newsy, „inwestycje”', count: 31, thumb: true }), type: 'persons' },
      { n: node('KMP-031', 'campaign', 'KMP-031 «Platforma AI»', { sub: 'inwestycje „z AI”', count: 18, thumb: true }), type: 'persons' },
      { n: node('KMP-009', 'campaign', 'KMP-009 «Kryptobot»', { sub: 'bot, który „gra sam”', count: 7, thumb: true }), type: 'persons' },
      { n: node('none:jk', 'campaign', 'bez kampanii', { sub: 'za mało śladów', count: 5, thumb: true, weak: true }), type: 'persons', dashed: true },
      { n: node('person:Anna Nowak', 'person', 'Anna Nowak', { sub: 'często w tych samych reklamach', relation: 'operator' }), type: 'operator', dashed: true },
      { n: node('brand:kurier-dnia', 'trace', '«Kurier Dnia»', { sub: 'podrabiany portal', relation: 'operator' }), type: 'operator', dashed: true },
    ],
    {
      kind_label: 'Osoba', badge: { text: 'rośnie', tone: 'red' }, title: 'Jan Kowalski',
      description: 'Twarz i nazwisko przedsiębiorcy w reklamach trzech kampanii.',
      facts: [{ k: 'Materiały', v: '61' }, { k: 'Kampanie', v: '3' }, { k: 'Pierwszy raz', v: '14.09' }, { k: 'Ostatni raz', v: 'dziś 02:31' },
        { k: 'Twarz rozpoznana', v: '52 z 61' }, { k: 'Głos syntetyczny', v: '9 nagrań' }],
      bot: 'czytelnik', bot_text: 'Tu to przycięte zdjęcie z wywiadu, to samo co w 31 reklamach.',
      action: { label: 'Pokaż wszystko o tej osobie', kind: 'trace', href: '/slad/osoba/Jan%20Kowalski' },
      link: { label: 'albo filtruj kampanie po tej osobie', href: '/kampanie?osoba=Jan%20Kowalski' },
    }),
  'INC-24702': (o) => ({
    ...focusPayload(o,
      node('INC-24702', 'incident', 'INC-24702', { kind_label: 'Materiał', sub: 'velmoria.click · 18.11', thumb: true, side: 'right' }),
      [
        { n: node('trace:capi', 'trace', 'bramka CAPI cg-7f3a…', { sub: 'wspólna', shared: true }), type: 'tracking' },
        { n: node('trace:kit', 'trace', 'kit relay v1', { sub: 'wspólny', shared: true }), type: 'kit' },
        { n: node('trace:content:pilne', 'trace', 'szablon „PILNE: {PER}…”', { sub: 'wspólny · 0.88', shared: true }), type: 'content' },
        { n: node('person:Jan Kowalski', 'person', 'Jan Kowalski', { sub: 'ta sama twarz', shared: true }), type: 'persons' },
        { n: node('morvanta.click', 'domain', 'morvanta.click', { sub: 'tylko Twój materiał', only: 'origin', weak: true }), type: 'infra', dashed: true },
        { n: node('velmoria.click', 'domain', 'velmoria.click', { sub: 'tylko INC-24702', only: 'focus', weak: true }), type: 'infra', dashed: true },
      ],
      {
        kind_label: 'Materiał', tags: ['KMP-017'], title: 'INC-24702',
        description: 'Reklama z tej samej kampanii. Łączą ją z Twoją 4 z 5 śladów.',
        facts: [{ k: 'Domena', v: 'velmoria.click' }, { k: 'Zgłoszony', v: '18.11, z wtyczki' }, { k: 'Reklama', v: 'Facebook, 3 dni' },
          { k: 'Status', v: 'usunięta 19.11' }, { k: 'Dopasowanie', v: '0.97' }],
        bot: 'archiwista', bot_text: 'Różni je tylko domena. Ta kampania zmienia domeny co kilka dni.',
        action: { label: 'Otwórz jej raport', kind: 'incident', href: '/analiza/INC-24702' },
        link: { label: 'albo zobacz wszystkie 46 w kampanii', href: '/kampanie/KMP-017' },
      }),
    }),
};

/** Map evidence chips / overview nodes to focus ids (the real API may use its own ids; we pass them through). */
export function focusIdFor(id: string): string | null {
  if (FOCUS[id]) return id;
  if (id.startsWith('trace:kit') || id.startsWith('trace:capi')) return 'trace:kit';
  if (id.startsWith('cert:')) return 'morvanta.click';
  return null;
}
