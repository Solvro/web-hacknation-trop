// Fictional universe of docs/design/canvas/BRIEF.md (same values as the canvas boards).
// Used only when the API is unreachable or NEXT_PUBLIC_MOCK=1. Shapes = docs/contracts/schema.json.
import type { CampaignSummary, Decision, EvidenceItem, IncidentSummary, LayerCoverage } from '../contracts';

export const N = 1284;
const ev = (e: Partial<EvidenceItem> & Pick<EvidenceItem, 'type' | 'field' | 'value' | 'display' | 'strength' | 'weight'>): EvidenceItem => ({
  level: 'campaign', df: 0, N, idf: 0, state: 'match', ...e,
});

// ------------------------------------------------------------------------------------------- campaigns
export const CAMPAIGNS: CampaignSummary[] = [
  {
    id: 'KMP-017', name: '«Zamach»', narrative: 'Fałszywe newsy o napaści, potem „inwestycja”', vertical: 'investment', status: 'active',
    operator_id: 'OP-03', heat: { series_48h: [], series_14d: [2, 1, 3, 2, 3, 2, 4, 3, 5, 4, 6, 5, 4, 7], trend_pct: 38 },
    n_incidents: 46, n_domains: 19, new_domains_24h: 3, predicted_domains: 1, persons: ['Jan Kowalski', 'Anna Nowak', 'Tomasz Lewandowski'],
    report_status: 'needs_update',
  },
  {
    id: 'KMP-034', name: '«Glikonor»', narrative: 'Lek na cukrzycę reklamowany twarzą lekarza (deepfake)', vertical: 'health', status: 'active',
    operator_id: 'OP-03', heat: { series_48h: [], series_14d: [1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 1, 1], trend_pct: 8 },
    n_incidents: 12, n_domains: 6, new_domains_24h: 0, predicted_domains: 1, persons: ['dr Piotr Wiśniewski'], report_status: 'none',
  },
  {
    id: 'KMP-043', name: '«Kurier wideo»', narrative: 'Nagrania deepfake z «Kurier Dnia», założona wczoraj', vertical: 'investment', status: 'candidate',
    operator_id: 'OP-03', heat: { series_48h: [], series_14d: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 3], trend_pct: 0 },
    n_incidents: 5, n_domains: 6, new_domains_24h: 0, predicted_domains: 0, persons: ['Anna Nowak'], report_status: 'none',
    merge_hint: 'KMP-017',
  },
  {
    id: 'KMP-031', name: '«Platforma AI»', narrative: 'Inwestycje „ze sztuczną inteligencją” ze znanymi twarzami', vertical: 'investment', status: 'fading',
    operator_id: 'OP-05', heat: { series_48h: [], series_14d: [6, 6, 6, 6, 5, 5, 5, 4, 4, 4, 4, 3, 3, 3], trend_pct: -12 },
    n_incidents: 58, n_domains: 23, new_domains_24h: 0, predicted_domains: 0, persons: ['Marek Zieliński', 'Katarzyna Wójcik', 'Jan Kowalski'],
    report_status: 'sent',
  },
  {
    id: 'KMP-022', name: '«Stawy»', narrative: 'Fałszywy lekarz poleca suplement na stawy', vertical: 'health', status: 'active',
    operator_id: 'OP-07', heat: { series_48h: [], series_14d: [3, 2, 3, 2, 3, 3, 2, 3, 2, 3, 3, 2, 3, 3], trend_pct: 0 },
    n_incidents: 31, n_domains: 9, new_domains_24h: 0, predicted_domains: 0, persons: ['dr Piotr Wiśniewski'], report_status: 'sent',
  },
  {
    id: 'KMP-040', name: '«Bon energetyczny»', narrative: 'Nowa: fałszywe dopłaty do rachunków za prąd', vertical: 'gov', status: 'candidate',
    operator_id: null, heat: { series_48h: [], series_14d: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3], trend_pct: 0 },
    n_incidents: 3, n_domains: 2, new_domains_24h: 2, predicted_domains: 0, persons: [], report_status: 'none',
  },
];
export const campaignName = (id?: string | null) => {
  const c = CAMPAIGNS.find((x) => x.id === id);
  return c ? `${c.id} ${c.name}` : id ?? '';
};

// ------------------------------------------------------------------------------------------- INC-24817 (assign)
export const EV_ZAMACH: EvidenceItem[] = [
  ev({ type: 'tracking', field: 'capi_gateway', value: 'cg-7f3a91e0.ecs.eu-west-1.on.aws/events', display: 'bramka CAPI cg-7f3a91e0…', strength: 'H', weight: 3.1, df: 47, idf: 3.31, bot: 'tropiciel' }),
  ev({ type: 'kit', field: 'kit_endpoint', value: '/api/v2/relay/lead/{uuid}/', display: 'kit relay v1', strength: 'H', weight: 2.7, df: 58, idf: 3.1, bot: 'tropiciel', level: 'operator_only' }),
  ev({ type: 'content', field: 'headline_template', value: 'PILNE: {PER} przerywa milczenie po napaści', display: '„PILNE: {PER} przerywa…”', strength: 'H', weight: 2.2, df: 22, idf: 4.07, bot: 'czytelnik' }),
  ev({ type: 'infra', field: 'cert_batch', value: 'LE R11 21.11 00:47–02:31', display: 'certyfikaty LE R11, noc', strength: 'M', weight: 1.4, df: 6, idf: 5.36, bot: 'notariusz' }),
  ev({ type: 'persons', field: 'face', value: 'Jan Kowalski', display: 'Jan Kowalski · 0.91', strength: 'M', weight: 0.8, df: 61, idf: 3.05, bot: 'czytelnik' }),
  ev({ type: 'infra', field: 'cdn', value: 'Cloudflare 203.0.113.0/24', display: 'Cloudflare', strength: 'L', weight: 0, df: 512, idf: 0.92, bot: 'archiwista', state: 'zero', level: 'platform' }),
];
const LAYERS_ZAMACH: LayerCoverage[] = [
  { layer: 'tracking', state: 'available' }, { layer: 'kit', state: 'available' }, { layer: 'infra', state: 'partial', reason: 'RDAP timeout' },
  { layer: 'content', state: 'available' }, { layer: 'persons', state: 'available' }, { layer: 'visual', state: 'available' },
  { layer: 'ad', state: 'available' }, { layer: 'media', state: 'missing', reason: 'brak nagrania (ASR)' },
];
export const DECISION_ZAMACH: Decision = {
  incident_id: 'INC-24817', decision: 'assign', campaign_id: 'KMP-017', score: 10.2, margin: 6.1, p: 0.94, tau: 5, delta: 1, confirm_floor: 1,
  operator_id: 'OP-03', scores: [
    { campaign_id: 'KMP-017', score: 10.2, score_operator: 8.4, p: 0.94, in_set: true },
    { campaign_id: 'KMP-034', score: 4.1, score_operator: 8.4, p: 0.41, in_set: false },
    { campaign_id: 'KMP-022', score: 0.6, score_operator: 0.2, p: 0.08, in_set: false },
  ],
  runner_up: { campaign_id: 'KMP-034', score: 4.1, p: 0.41, same_operator: true },
  coverage: 0.78, layers: LAYERS_ZAMACH, evidence: EV_ZAMACH, why_not: [], set: ['KMP-017'], model_version: 'engine@1',
};

// ------------------------------------------------------------------------------------------- INC-24822 (new)
export const EV_BON: EvidenceItem[] = [
  ev({ type: 'tracking', field: 'fb_pixel', value: '1188042077315520', display: 'Piksel Meta 1188 0420 7731 552', strength: 'H', weight: 0, df: 1, idf: 7.16, bot: 'tropiciel' }),
  ev({ type: 'kit', field: 'form_path', value: '/karta/weryfikacja/', display: 'Formularz /karta/weryfikacja/ prosi o numer karty', strength: 'H', weight: 0, df: 1, idf: 7.16, bot: 'tropiciel' }),
  ev({ type: 'content', field: 'headline_template', value: 'Bon energetyczny 2026: odbierz 1 200 zł', display: '„Bon energetyczny 2026: odbierz 1 200 zł”', strength: 'M', weight: 0, df: 3, idf: 6.06, bot: 'czytelnik' }),
  ev({ type: 'infra', field: 'registration', value: 'bon-energia24.online', display: 'Domena zarejestrowana wczoraj, inny rejestrator niż znane kampanie', strength: 'L', weight: 0, df: 1, idf: 7.16, bot: 'notariusz' }),
  ev({ type: 'persons', field: 'face', value: '', display: 'Brak znanych twarzy, podrobione logo ministerstwa', strength: 'L', weight: 0, df: 0, idf: 0, bot: 'czytelnik', state: 'missing' }),
];
export const DECISION_BON: Decision = {
  incident_id: 'INC-24822', decision: 'new', candidate_campaign_id: 'KMP-040', score: 0.9, margin: 0.6, p: 0.18, tau: 5, delta: 1, confirm_floor: 1,
  scores: [
    { campaign_id: 'KMP-031', score: 0.9, p: 0.18, in_set: false },
    { campaign_id: 'KMP-022', score: 0.3, p: 0.06, in_set: false },
    { campaign_id: 'KMP-017', score: 0.2, p: 0.04, in_set: false },
  ],
  coverage: 0.7, layers: [], evidence: EV_BON, set: [], why_not: [], model_version: 'engine@1',
};

// ------------------------------------------------------------------------------------------- INC-24768 (ambiguous)
export const EV_KELVARO: EvidenceItem[] = [
  ev({ type: 'tracking', field: 'capi_gateway', value: 'cg-7f3a91e0.ecs.eu-west-1.on.aws/events', display: 'bramka CAPI cg-7f3a91e0…', strength: 'H', weight: 3.1, df: 59, idf: 3.08, bot: 'tropiciel', level: 'operator_only' }),
  ev({ type: 'kit', field: 'kit_endpoint', value: '/api/v2/relay/lead/{uuid}/', display: 'kit relay v1', strength: 'H', weight: 2.7, df: 58, idf: 3.1, bot: 'tropiciel', level: 'operator_only' }),
  ev({ type: 'infra', field: 'cert_batch', value: '.live · LE R11 noc', display: 'domena .live, nocny certyfikat', strength: 'M', weight: 0.9, df: 25, idf: 3.9, bot: 'notariusz' }),
  ev({ type: 'content', field: 'headline_template', value: '', display: 'treść i osoby: strona jest pusta', strength: 'L', weight: 0, df: 0, idf: 0, bot: 'czytelnik', state: 'missing' }),
];
export const DECISION_KELVARO: Decision = {
  incident_id: 'INC-24768', decision: 'ambiguous', candidate_campaign_id: 'KMP-017', score: 5.4, margin: 0.4, p: 0.52, tau: 5, delta: 1, confirm_floor: 1,
  operator_id: 'OP-03', scores: [
    { campaign_id: 'KMP-017', score: 5.4, score_operator: 6.7, p: 0.52, in_set: true },
    { campaign_id: 'KMP-034', score: 5.0, score_operator: 6.7, p: 0.47, in_set: true },
  ],
  runner_up: { campaign_id: 'KMP-034', score: 5.0, p: 0.47, same_operator: true },
  coverage: 0.45, layers: [], evidence: EV_KELVARO, set: ['KMP-017', 'KMP-034'], why_not: [], model_version: 'engine@1',
};

// ------------------------------------------------------------------------------------------- INC-24830 (page down)
export const EV_SELQUENO: EvidenceItem[] = [
  ev({ type: 'infra', field: 'domain_dna', value: 'selqueno.live', display: 'Domena ma DNA KMP-017: 8 liter, .live, certyfikat nocą', strength: 'M', weight: 1.2, df: 19, idf: 4.2, bot: 'notariusz' }),
  ev({ type: 'infra', field: 'history', value: 'KMP-017 do 17.11', display: 'Ta domena działała w KMP-017 do 17.11', strength: 'M', weight: 1.6, df: 3, idf: 6.0, bot: 'archiwista' }),
];
export const DECISION_SELQUENO: Decision = {
  incident_id: 'INC-24830', decision: 'insufficient', candidate_campaign_id: 'KMP-017', score: 2.8, margin: 2.1, p: 0.61, tau: 5, delta: 1, confirm_floor: 1,
  scores: [{ campaign_id: 'KMP-017', score: 2.8, p: 0.61, in_set: false }], coverage: 0.25, layers: [
    { layer: 'tracking', state: 'error', reason: '502' }, { layer: 'kit', state: 'error', reason: '502' }, { layer: 'content', state: 'missing' },
    { layer: 'infra', state: 'available' },
  ], evidence: EV_SELQUENO, set: [], why_not: [], model_version: 'engine@1',
};

export const DECISIONS: Record<string, Decision> = {
  'INC-24817': DECISION_ZAMACH, 'INC-24822': DECISION_BON, 'INC-24768': DECISION_KELVARO, 'INC-24830': DECISION_SELQUENO,
  'INC-24702': { ...DECISION_ZAMACH, incident_id: 'INC-24702', p: 0.97 },
};

export const INCIDENTS: Record<string, IncidentSummary & { input?: string; note?: string; advertiser?: string }> = {
  'INC-24817': { id: 'INC-24817', source: 'hunter', captured_at: '2026-11-21T02:31:00+01:00', domain: 'morvanta.click', title: 'PILNE: Jan Kowalski przerywa milczenie po napaści', person: 'Jan Kowalski', campaign_id: 'KMP-017', decision: 'assign', p: 0.94, coverage: 0.78, input: 'https://morvanta.click/?utm_source=fb&utm_visit=0193a7c2-…', note: 'link i zrzut reklamy «Puzzle Mania PL»', advertiser: 'Puzzle Mania PL' },
  'INC-24822': { id: 'INC-24822', source: 'extension', captured_at: '2026-11-21T08:12:00+01:00', domain: 'bon-energia24.online', title: 'Bon energetyczny 2026: odbierz 1 200 zł', campaign_id: null, decision: 'new', p: 0.18, coverage: 0.7, input: 'https://bon-energia24.online/karta/weryfikacja/', note: 'zgłoszone z wtyczki przez 3 osoby' },
  'INC-24768': { id: 'INC-24768', source: 'har', captured_at: '2026-11-21T07:40:00+01:00', domain: 'kelvaro.live', title: null, campaign_id: null, decision: 'ambiguous', p: 0.52, coverage: 0.45, input: 'kelvaro.live.har', note: 'plik HAR, bez zrzutu reklamy' },
  'INC-24830': { id: 'INC-24830', source: 'url', captured_at: '2026-11-21T09:14:00+01:00', domain: 'selqueno.live', title: null, campaign_id: null, decision: 'insufficient', p: 0.61, coverage: 0.25, input: 'https://selqueno.live/', note: '3 próby, ostatnia 09:14' },
  'INC-24702': { id: 'INC-24702', source: 'extension', captured_at: '2026-11-18T10:02:00+01:00', domain: 'velmoria.click', title: '«Wiem, kto to zrobił»: atak na Annę Nowak', person: 'Anna Nowak', campaign_id: 'KMP-017', decision: 'assign', p: 0.97, coverage: 0.81, input: 'https://velmoria.click/', note: 'zgłoszony z wtyczki' },
};

/** Campaign headline for the Raport (first line) + paragraph (rest). */
export const CAMPAIGN_STORY: Record<string, { h1: string; p: string }> = {
  'KMP-017': { h1: 'Fałszywe newsy, które prowadzą do „inwestycji”', p: 'Reklama udaje pilną wiadomość z «Kurier Dnia», a link prowadzi do fałszywej „platformy inwestycyjnej”, która wyłudza pieniądze.' },
  'KMP-040': { h1: 'Fałszywe dopłaty do rachunków za prąd', p: 'Reklama obiecuje „bon energetyczny” od państwa, a link prowadzi do formularza, który zbiera dane karty płatniczej.' },
  'KMP-034': { h1: 'Lek na cukrzycę reklamowany twarzą lekarza', p: 'Reklama pokazuje deepfake „dr. Piotra Wiśniewskiego”, a sklep sprzedaje Glikonor.' },
};
