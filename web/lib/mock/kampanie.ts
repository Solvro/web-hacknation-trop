// Kampanie / Śledztwa / Ślad / Lab fixtures (BRIEF.md universe, board copy). Offline fallback only.
import type { ActPackage, CampaignDNA, DomainIndicator, Event, Investigation, InvestigationNode, Member, Operator, OraclePrediction, Timeline, TraceData } from '../contracts';
import { CAMPAIGNS, CAMPAIGN_STORY, EV_ZAMACH, N } from './universe';

export function campaignDetail(id: string) {
  const c = CAMPAIGNS.find((x) => x.id === id);
  if (!c) return undefined;
  const s = CAMPAIGN_STORY[id];
  const k17 = id === 'KMP-017';
  return {
    ...c, description: s ? `${s.h1}\n${s.p}` : c.narrative, level: 'L2',
    counts: { incidents: c.n_incidents, incidents_24h: k17 ? 5 : 0, domains: c.n_domains, certs_tonight: k17 ? 3 : 0, advertisers: k17 ? 11 : 3, advertisers_removed: k17 ? 4 : 0, persons: c.persons?.length ?? 0, certpl_listed: k17 ? 5 : 0 },
    first_seen: k17 ? '2026-11-08' : '2026-11-02', last_seen: '2026-11-21', brands: k17 ? ['Kurier Dnia'] : [],
  };
}

const DNA_017: CampaignDNA = {
  campaign_id: 'KMP-017', signature: [
    { layer: 'tracking', field: 'capi_gateway', value: 'cg-7f3a91e0.ecs.eu-west-1.on.aws/events', display: 'Ta sama bramka CAPI cg-7f3a…', members_with: 46, members_total: 46, strength: 'H', bot: 'tropiciel' },
    { layer: 'kit', field: 'kit_endpoint', value: '/api/v2/relay/lead/{uuid}/', display: 'Ten sam kit: /api/v2/relay/lead/{uuid}/', members_with: 46, members_total: 46, strength: 'H', bot: 'tropiciel' },
    { layer: 'content', field: 'headline_template', value: 'PILNE: {PER}…', display: '3 szablony tekstu, najnowszy „PILNE: {PER}…”', members_with: 46, members_total: 46, strength: 'H', bot: 'czytelnik' },
    { layer: 'persons', field: 'persons', value: 'Jan Kowalski, Anna Nowak, «Kurier Dnia»', display: 'Te same osoby i portal «Kurier Dnia»', members_with: 44, members_total: 46, strength: 'M', bot: 'czytelnik' },
    { layer: 'infra', field: 'domain_dna', value: 'CVCCVCV .click|.live', display: 'Domeny 7–9 liter, .click i .live, certyfikaty nocą', members_with: 19, members_total: 19, strength: 'M', bot: 'notariusz' },
  ],
};

const TIMELINE_017: Timeline = {
  days: [0, 1, 2, 1, 3, 2, 4, 3, 5, 4, 6, 5, 4, 6].map((v, i) => ({ date: `2026-11-${String(8 + i).padStart(2, '0')}`, incidents: v })),
  events: [
    { at: '2026-11-19T19:28:00Z', kind: 'oracle_predicted', ref: 'morvanta.click' },
    { at: '2026-11-21T00:47:00Z', kind: 'cert_batch', ref: '3 certyfikaty tej nocy' },
  ],
};

const DOMAINS_017: DomainIndicator[] = [
  { fqdn: 'morvanta.click', cert_issued_at: '2026-11-21T02:31:00+01:00', oracle_predicted_at: '2026-11-19T20:28:00+01:00', on_certpl: false, online: true, ads_seen: 4 },
  { fqdn: 'orvinta.click', cert_issued_at: '2026-11-21T01:12:00+01:00', oracle_predicted_at: '2026-11-20T22:40:00+01:00', on_certpl: false, online: true, ads_seen: 0 },
  { fqdn: 'plessuro.live', cert_issued_at: '2026-11-21T00:47:00+01:00', on_certpl: false, online: true, ads_seen: 0 },
  { fqdn: 'velmoria.click', cert_issued_at: '2026-11-12T01:03:00+01:00', on_certpl: true, online: true, ads_seen: 9 },
  { fqdn: 'selqueno.live', cert_issued_at: '2026-11-10T00:22:00+01:00', on_certpl: false, online: '502', ads_seen: 3 },
];

const MEMBERS_017: Member[] = ['INC-24817', 'INC-24790', 'INC-24702', 'INC-24655'].map((id, i) => ({
  incident_id: id, captured_at: ['2026-11-21T02:31:00+01:00', '2026-11-20T11:02:00+01:00', '2026-11-18T10:02:00+01:00', '2026-11-16T08:40:00+01:00'][i],
  source: ['hunter', 'adlibrary', 'extension', 'extension'][i], domain: ['morvanta.click', 'quorvex.click', 'velmoria.click', 'trastino.live'][i],
  person: 'Jan Kowalski', level: 'L2', score: 9 - i * 0.3, p: 0.94 - i * 0.01, top_evidence: EV_ZAMACH.slice(0, 2), layers: [],
}));

export function campaignExtras(id: string, what: string): unknown {
  if (id !== 'KMP-017') {
    if (what === 'dna') return { campaign_id: id, signature: [] };
    if (what === 'timeline') return { days: CAMPAIGNS.find((c) => c.id === id)?.heat?.series_14d?.map((v, i) => ({ date: `2026-11-${String(8 + i).padStart(2, '0')}`, incidents: v })) ?? [], events: [] };
    if (what === 'indicators') return { domains: [], tracking: [], kit: [], persons: [], advertisers: [] };
    if (what === 'members') return [];
    return undefined;
  }
  if (what === 'dna') return DNA_017;
  if (what === 'timeline') return TIMELINE_017;
  if (what === 'indicators') return {
    domains: DOMAINS_017, tracking: [], kit: [],
    persons: [{ id: 'jk', name: 'Jan Kowalski', role: 'przedsiębiorca', count: 31 }, { id: 'an', name: 'Anna Nowak', role: 'dziennikarka', count: 9 }, { id: 'tl', name: 'Tomasz Lewandowski', role: 'dziennikarz', count: 6 }, { id: 'kd', name: '«Kurier Dnia»', role: 'fałszywy portal', count: 46 }],
    advertisers: [{ name: 'Ogród i Pasja 24' }, { name: 'Puzzle Mania PL' }, { name: 'Lena Kwiatkowska Sklep' }],
  };
  if (what === 'members') return MEMBERS_017;
  return undefined;
}

export const operators: Record<string, Operator> = {
  'OP-03': {
    id: 'OP-03', codename: 'Kestrel', operation_id: 'OPN-01',
    campaigns: [{ id: 'KMP-017', name: '«Zamach»', incidents: 46 }, { id: 'KMP-034', name: '«Glikonor»', incidents: 12 }, { id: 'KMP-043', name: '«Kurier wideo»', incidents: 5 }],
    shared: [
      { type: 'kit', field: 'kit_endpoint', value: '/api/v2/relay/lead/{uuid}/', display: 'kit relay v1', strength: 'H', weight: 2.7, df: 58, N },
      { type: 'tracking', field: 'capi_gateway', value: 'cg-7f3a91e0', display: 'bramka CAPI cg-7f3a…', strength: 'H', weight: 3.1, df: 59, N },
      { type: 'infra', field: 'asn', value: 'AS64500', display: 'hosting AS64500', strength: 'M', weight: 1.0, df: 70, N },
      { type: 'infra', field: 'registrar', value: 'R-114', display: 'rejestrator R-114', strength: 'M', weight: 0.8, df: 80, N },
      { type: 'infra', field: 'cert_window', value: 'night', display: 'certyfikaty nocą', strength: 'M', weight: 0.7, df: 90, N },
    ],
    narratives: ['Zmienia tematy, od finansów po zdrowie, ale zostawia ten sam zestaw stron i tę samą bramkę konwersji. Nowe domeny rejestruje partiami, nocą.'],
  },
  'OP-05': { id: 'OP-05', codename: 'Heron', campaigns: [{ id: 'KMP-031', name: '«Platforma AI»', incidents: 58 }], shared: [], narratives: [] },
  'OP-07': { id: 'OP-07', codename: 'Orchid', campaigns: [{ id: 'KMP-022', name: '«Stawy»', incidents: 31 }], shared: [], narratives: [] },
};

export const oracle: OraclePrediction[] = [
  { domain: 'orvinta.click', issued_at: '2026-11-21T01:12:00+01:00', issuer: 'R11', dna_score: 0.93, campaign_id: 'KMP-017', status: 'predicted', reasons: [] },
  { domain: 'plessuro.live', issued_at: '2026-11-21T00:47:00+01:00', issuer: 'R11', dna_score: 0.88, campaign_id: 'KMP-017', status: 'predicted', reasons: [] },
  { domain: 'kelvaro.live', issued_at: '2026-11-21T01:40:00+01:00', issuer: 'R11', dna_score: 0.64, campaign_id: 'KMP-034', status: 'predicted', reasons: [] },
  { domain: 'morvanta.click', issued_at: '2026-11-19T19:28:00+01:00', issuer: 'R11', dna_score: 0.91, campaign_id: 'KMP-017', status: 'confirmed', first_ad_at: '2026-11-21T02:31:00+01:00', lead_time_h: 31, reasons: [] },
  { domain: 'tranvello.click', issued_at: '2026-11-21T02:49:00+01:00', issuer: 'R10', dna_score: 0.71, campaign_id: 'KMP-017', status: 'below_threshold', reasons: [] },
];

export function actPackage(id: string): ActPackage {
  return {
    id, kind: 'bundle', campaign_id: 'KMP-017', status: 'sent', created_at: '2026-11-21T09:12:00+01:00', sent_at: '2026-11-21T09:12:00+01:00',
    contents: { ads: 46, advertisers: 11, domains: 29, evidence_items: 64 },
    recipients: [
      { id: 'meta_dsa', label: 'Meta · DSA art. 16', enabled: true, progress: { done: 0, total: 46 }, status: 'przyjęte, w ocenie' },
      { id: 'certpl', label: 'CERT PL · lista ostrzeżeń', enabled: true, progress: { done: 24, total: 24 }, status: 'na liście' },
      { id: 'google', label: 'Google Safe Browsing', enabled: true, progress: { done: 0, total: 29 }, status: 'w kolejce u Google' },
    ],
    parts: [], notice_text: '', formats: ['pdf', 'json', 'stix'],
    disclaimer: 'Nic nie zostało wysłane — pakiet przygotowany i wyeksportowany.',
  };
}
export const packages: ActPackage[] = [actPackage('ACT-12'), { ...actPackage('ACT-9'), created_at: '2026-11-18T14:00:00+01:00', sent_at: '2026-11-18T14:00:00+01:00', recipients: [{ id: 'meta_dsa', label: 'Meta · DSA art. 16', enabled: true, progress: { done: 12, total: 12 }, status: 'usuniętych w 6 h' }] }];

export function mergePreview(a: string, b: string) {
  const ca = CAMPAIGNS.find((x) => x.id === a); const cb = CAMPAIGNS.find((x) => x.id === b);
  if (!ca || !cb) return undefined;
  const e = (type: string, display: string, bot: string, df: number, total: number, state = 'match') => ({ type, field: type, value: `${df}/${total}`, display, strength: 'H', weight: 1, df, N: total, bot, state });
  return {
    a: ca, b: cb,
    shared: [e('tracking', 'Ta sama bramka CAPI cg-7f3a…', 'tropiciel', 5, 5), e('kit', 'Ten sam kit: /api/v2/relay/lead/{uuid}/', 'tropiciel', 5, 5),
      e('infra', '4 wspólne domeny z tej samej nocnej partii certyfikatów', 'notariusz', 4, 6), e('persons', 'Ta sama osoba i portal: Jan Kowalski, «Kurier Dnia»', 'czytelnik', 5, 5),
      e('content', 'Inny format: wideo z deepfake zamiast tekstu', 'czytelnik', 0, 0, 'conflict')],
    before: { materials_a: 46, materials_b: 5, domains_a: 19, domains_b: 6, advertisers_a: 11, advertisers_b: 2 },
    after: { materials: 51, domains: 21, advertisers: 12 }, undo_token: 'undo-1',
  };
}

export const labMetrics = {
  view: 'summary', model_version: 'engine@fixture',
  data: { sample: true, note: 'przykładowe wartości, podmienić z eval/', bcubed_f1: 0.91, ari: 0.87, pairwise_precision: 0.96, open_set_accuracy: 0.93, new_campaign_precision: 0.95, conformal_target: 0.05, conformal_achieved: 0.041, m2_infra_blind_f1: 0.74 },
};

const TRACE_JK: TraceData = {
  type: 'osoba', value: 'Jan Kowalski', title: 'Jan Kowalski',
  description: 'Twarz i nazwisko przedsiębiorcy pojawiają się w reklamach trzech kampanii. Oszuści używają ich od połowy września.',
  campaigns: [{ id: 'KMP-017', name: '«Zamach»', n: 31, narrative: 'Fałszywe newsy, które prowadzą do „inwestycji”' }, { id: 'KMP-031', name: '«Platforma AI»', n: 18, narrative: 'Inwestycje „ze sztuczną inteligencją”' },
    { id: 'KMP-009', name: '«Kryptobot»', n: 7, narrative: 'Bot, który rzekomo sam gra na giełdzie' }, { id: '', name: 'Bez kampanii', n: 5, narrative: 'pojedyncze materiały, za mało śladów' }],
  weekly: [2, 3, 1, 4, 5, 6, 5, 9, 11, 15],
  latest: [
    { id: 'INC-24817', source: 'hunter', domain: 'morvanta.click', campaign_id: 'KMP-017', captured_at: '2026-11-21T02:31:00+01:00' },
    { id: 'INC-24790', source: 'adlibrary', domain: 'quantapl-invest.top', campaign_id: 'KMP-031', captured_at: '2026-11-20T11:02:00+01:00' },
    { id: 'INC-24702', source: 'extension', domain: 'velmoria.click', campaign_id: 'KMP-017', captured_at: '2026-11-18T10:02:00+01:00' },
    { id: 'INC-24655', source: 'extension', domain: 'zrzut z wtyczki', campaign_id: null, captured_at: '2026-11-16T08:40:00+01:00' },
  ],
  usage: [{ label: 'Przycięte zdjęcie z wywiadu. W 9 materiałach wideo z podłożonym, syntetycznym głosem.', n: 0 }, { label: 'twarz rozpoznana w 52 z 61', n: 52 }, { label: 'głos syntetyczny w 9', n: 9 }],
  co_traces: [{ type: 'portal', value: '«Kurier Dnia»', n: 46 }, { type: 'osoba', value: 'Anna Nowak', n: 9 }, { type: 'szablon', value: '„PILNE: {PER}…”', n: 22 }, { type: 'tracking', value: 'bramka CAPI cg-7f3a…', n: 47 }],
};

export function trace(t?: string, v?: string): TraceData | undefined {
  if (!v) return undefined;
  if (/kowalski/i.test(v)) return TRACE_JK;
  if (t === 'domena' || t === 'domain') return {
    type: 'domena', value: v, title: v, description: `Domena ${v}: ${/morvanta|orvinta|plessuro|velmoria|selqueno/.test(v) ? 'należy do kampanii KMP-017 «Zamach».' : 'nie znamy jej z żadnej kampanii.'}`,
    campaigns: /morvanta|orvinta|plessuro|velmoria|selqueno/.test(v) ? [{ id: 'KMP-017', name: '«Zamach»', n: 4, narrative: 'Fałszywe newsy, które prowadzą do „inwestycji”' }] : [],
    weekly: [0, 0, 0, 0, 0, 0, 0, 0, 1, 3], latest: TRACE_JK.latest.slice(0, 1), usage: [{ label: 'Certyfikat LE R11 z nocnej partii; hosting za Cloudflare.', n: 0 }],
    co_traces: [{ type: 'kit', value: 'kit relay v1', n: 58 }, { type: 'tracking', value: 'bramka CAPI cg-7f3a…', n: 47 }],
  };
  return {
    type: t ?? 'ślad', value: v, title: v, description: 'Ten ślad występuje w materiałach jednej kampanii.',
    campaigns: [{ id: 'KMP-017', name: '«Zamach»', n: 46 }, { id: 'KMP-034', name: '«Glikonor»', n: 12 }], weekly: [1, 2, 2, 3, 4, 4, 5, 6, 7, 8],
    latest: TRACE_JK.latest.slice(0, 3), usage: [], co_traces: [{ type: 'operator', value: 'OP-03 «Kestrel»', n: 2 }],
  };
}

// ------------------------------------------------------------------------------------------- Śledztwo (board 9–10)
const NODES: (InvestigationNode & { parent?: string; bot: string; delay: number })[] = [
  { id: 'n-seed', kind: 'domain', label: 'morvanta.click', status: 'in_campaign', branch: 'db', bot: 'sedzia', delay: 300 },
  { id: 'd-orvinta', kind: 'domain', label: 'orvinta.click', status: 'new', branch: 'crtsh', meta: { note: 'certyfikat dziś 01:12', why: 'ta sama nocna partia certyfikatów' }, bot: 'notariusz', delay: 1200 },
  { id: 'd-plessuro', kind: 'domain', label: 'plessuro.live', status: 'new', branch: 'crtsh', meta: { note: 'certyfikat dziś 00:47', why: 'ta sama nocna partia certyfikatów' }, bot: 'notariusz', delay: 500 },
  { id: 'd-tranvello', kind: 'domain', label: 'tranvello.click', status: 'new', branch: 'urlscan', meta: { note: 'Oracle przewidział', why: 'ten sam kit' }, bot: 'tropiciel', delay: 1400 },
  { id: 'd-kelmora', kind: 'domain', label: 'kelmora.click', status: 'new', branch: 'urlscan', meta: { note: '2 reklamy', why: 'ten sam kit' }, bot: 'tropiciel', delay: 400 },
  { id: 'd-dravento', kind: 'domain', label: 'dravento.live', status: 'new', branch: 'urlscan', meta: { note: 'bez reklam', why: 'ten sam kit' }, bot: 'tropiciel', delay: 400 },
  { id: 'd-vastrino', kind: 'domain', label: 'vastrino.live', status: 'new', branch: 'urlscan', meta: { note: 'bez reklam', why: 'ten sam kit' }, bot: 'tropiciel', delay: 400 },
  { id: 'd-sulvane', kind: 'domain', label: 'sulvane.click', status: 'new', branch: 'urlscan', meta: { note: 'bez reklam', why: 'ten sam kit' }, bot: 'tropiciel', delay: 300 },
  { id: 'd-morquel', kind: 'domain', label: 'morquel.live', status: 'new', branch: 'urlscan', meta: { note: 'bez reklam', why: 'ten sam kit' }, bot: 'tropiciel', delay: 300 },
  { id: 'd-pentaro', kind: 'domain', label: 'pentaro.click', status: 'new', branch: 'urlscan', meta: { note: 'bez reklam', why: 'ten sam kit' }, bot: 'tropiciel', delay: 300 },
  { id: 'd-ombrela', kind: 'domain', label: 'ombrela.click', status: 'new', branch: 'urlscan', meta: { note: 'bez reklam', why: 'ten sam kit' }, bot: 'tropiciel', delay: 300 },
  { id: 'd-kalvesto', kind: 'domain', label: 'kalvesto.live', status: 'to_decide', branch: 'urlscan', meta: { why: 'pasuje też do KMP-034' }, bot: 'tropiciel', delay: 500 },
  { id: 'a-ads', kind: 'ad', label: '9 reklam', status: 'new', branch: 'adlib', meta: { note: 'Ad Library', why: '«Puzzle Mania PL», «Ogród i Pasja 24» i 2 inne', title: '9 reklam na 4 stronach' }, bot: 'zwiadowca', delay: 1400 },
  { id: 'a-pages', kind: 'query_result', label: '4 strony', status: 'new', branch: 'adlib', bot: 'zwiadowca', delay: 300 },
  { id: 'l-certpl', kind: 'list_status', label: '11 domen poza listą', status: 'new', branch: 'certpl', meta: { tone: 'amber' }, bot: 'notariusz', delay: 1200 },
  { id: 'd-velmoria', kind: 'domain', label: 'velmoria.click', status: 'in_campaign', branch: 'db', bot: 'archiwista', delay: 1000 },
  { id: 'd-trastino', kind: 'domain', label: 'trastino.live', status: 'in_campaign', branch: 'db', bot: 'archiwista', delay: 300 },
  { id: 'c-tranvello', kind: 'domain', label: 'tranvello.click', status: 'in_progress', branch: 'content', bot: 'czytelnik', delay: 1000 },
  { id: 'c-kelmora', kind: 'domain', label: 'kelmora.click', status: 'in_progress', branch: 'content', bot: 'czytelnik', delay: 300 },
];
const TOOLS: Record<string, string> = { crtsh: 'crtsh.search', urlscan: 'urlscan.search', adlib: 'adlibrary.search', certpl: 'certpl.check', db: 'db.lookup', content: 'engine.compare' };

export function investigations(id: string): Investigation {
  return {
    id, seed: 'morvanta.click', campaign_id: 'KMP-017', status: 'running', budget: { steps: 20, used: 0, usd: 0.5, usd_used: 0 }, model: 'gemini-pro-latest',
    tools: Object.values(TOOLS), started_at: new Date().toISOString(), nodes: [], edges: [], steps: [], conclusions: [], pending_decision: null,
  };
}

export function investigationEvents(id: string): { delay: number; ev: Event }[] {
  const at = () => new Date().toISOString();
  const out: { delay: number; ev: Event }[] = [];
  let n = 0;
  let lastBranch = '';
  for (const node of NODES) {
    const { bot, delay, parent: _p, ...nd } = node;
    if (node.branch !== lastBranch) {
      n += 1; lastBranch = node.branch ?? '';
      out.push({ delay: Math.max(200, delay - 200), ev: { type: 'agent.step', at: at(), data: { investigation_id: id, step: { n, tool: TOOLS[node.branch ?? 'db'], query: 'morvanta.click', result_summary: '', why: '', produced: [], at: at(), bot } } } });
    }
    out.push({ delay: 200, ev: { type: 'graph.node_added', at: at(), data: { investigation_id: id, node: nd, parent: node.id === 'n-seed' ? null : 'n-seed' } } });
    if (node.id === 'd-kalvesto') {
      out.push({ delay: 300, ev: { type: 'investigation.decision', at: at(), data: { investigation_id: id, node_id: 'd-kalvesto', question: 'kalvesto.live ma ten sam kit, ale inny certyfikat i hosting. Pasuje też do KMP-034. Dołączyć ją do tej kampanii?', options: ['Dołącz', 'Pomiń'] } } });
    }
  }
  out.push({ delay: 2500, ev: { type: 'investigation.done', at: at(), data: { investigation_id: id, summary: 'Znaleźliśmy 10 nowych domen i 9 reklam' } } });
  return out;
}
export function links(a?: string, b?: string): unknown {
  const mk = (txt: string) => ({ type: 'tracking', field: 'x', value: txt, display: txt, strength: 'H', weight: 1 });
  const miss = { type: 'content', field: 'headline_template', value: '', display: 'treść i osoby: strona jest pusta', strength: 'L', weight: 0, state: 'missing' };
  if (a === 'INC-24768' && b === 'KMP-017') return { a, b, score_campaign: 5.4, score_operator: 6.7, p: 0.52, decision: 'triage', evidence: [mk('ta sama bramka CAPI'), mk('ten sam kit'), mk('domena .live z nocnym certyfikatem, jak 19 domen tej kampanii')], missing: [miss], conflicts: [], zeroed: [] };
  if (a === 'INC-24768' && b === 'KMP-034') return { a, b, score_campaign: 5.0, score_operator: 6.7, p: 0.47, decision: 'triage', evidence: [mk('ta sama bramka CAPI'), mk('ten sam kit'), mk('Oracle przypisał kelvaro.live do tej kampanii (0.64)')], missing: [miss], conflicts: [], zeroed: [] };
  return undefined;
}
