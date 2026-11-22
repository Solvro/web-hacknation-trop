import type { BotName, EvidenceItem, Layer, StepKey } from './contracts';

export const LAYER_LABEL: Record<Layer, string> = {
  tracking: 'Tracking', kit: 'Zestaw strony', infra: 'Infra', content: 'Treść', persons: 'Osoby', visual: 'Obraz', ad: 'Reklama', media: 'Media',
};
/** One-sentence explanation of each layer (tooltips wherever a layer label is shown). */
export const LAYER_HINT: Record<Layer, string> = {
  tracking: 'Identyfikatory śledzenia reklam (piksel FB, Google Ads).',
  kit: 'Oprogramowanie, na którym postawiono fałszywą stronę (konto operatora, szablon, pliki).',
  infra: 'Domena, serwery, certyfikaty, rejestracja.',
  content: 'Tekst strony, szablon nagłówka, osoby i marki.',
  ad: 'Reklamodawca i tekst reklamy.',
  visual: 'Podobieństwo zrzutów.',
  persons: 'Twarze rozpoznane w galerii.',
  media: 'Nagranie, mowa, głos.',
};
/** Evidence that does not count toward the campaign score on its own (shared by many operators / operator-level only). */
export const isSideEvidence = (e: Pick<EvidenceItem, 'state'> & { level?: string | null }) => e.state === 'zero';
export const SIDE_LEVEL: Record<string, string> = { operator_only: 'ślad operatora', platform: 'wspólna platforma', infra_shared: 'wspólna infrastruktura' };

export interface BotInfo {
  key: BotName;
  name: string;
  color: string;
  step: StepKey;
  stepName: string;          // Raport step title
  run: string;               // default "what I'm doing" line
  master?: boolean;
}

// Fixed order = schema.BOT_STEPS. Colours drive the detective costume variant (jelly script).
export const BOTS: BotInfo[] = [
  { key: 'zwiadowca', name: 'Zwiadowca', color: '#2563EB', step: 'capture', stepName: 'Przechwycenie strony', run: 'Otwieram stronę w piaskownicy. Formularzy nie wysyłam.' },
  { key: 'tropiciel', name: 'Tropiciel', color: '#F97316', step: 'tracking', stepName: 'Ślady techniczne', run: 'Szukam pikseli, bramek konwersji i kitu w ruchu sieciowym.' },
  { key: 'czytelnik', name: 'Czytelnik', color: '#14B8A6', step: 'content', stepName: 'Treść i osoby', run: 'Czytam nagłówek i tekst, rozpoznaję twarze.' },
  { key: 'notariusz', name: 'Notariusz', color: '#8B5CF6', step: 'infra', stepName: 'Domena i certyfikaty', run: 'Pytam RDAP i crt.sh o domenę i certyfikat.' },
  { key: 'archiwista', name: 'Archiwista', color: '#EC4899', step: 'compare', stepName: 'Porównanie z bazą', run: 'Porównuję ślady z materiałami w bazie.' },
  { key: 'sedzia', name: 'Sędzia', color: '#0A0A0A', step: 'verdict', stepName: 'Werdykt', run: 'Ważę dowody i piszę raport.', master: true },
];
export const BOT_BY_KEY = Object.fromEntries(BOTS.map((b) => [b.key, b])) as Record<BotName, BotInfo>;
export const BOT_BY_STEP = Object.fromEntries(BOTS.map((b) => [b.step, b])) as Record<StepKey, BotInfo>;
export const botName = (b?: string | null) => (b && (BOT_BY_KEY as Record<string, BotInfo>)[b]?.name) || 'Bot';
export const botColor = (b?: string | null) => (b && (BOT_BY_KEY as Record<string, BotInfo>)[b]?.color) || '#525252';

/** Thousands with a (non-breaking) space: 1 284. */
export function n(x: number | null | undefined): string {
  if (x == null || Number.isNaN(x)) return '—';
  const s = Math.round(x).toString();
  return s.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}
/** Scores / weights with a dot: 0.94, +2.7 */
export const p2 = (x: number | null | undefined) => (x == null ? '—' : x.toFixed(2));
export function w1(x: number): string {
  if (Math.abs(x) < 0.05) return '0';
  return (x > 0 ? '+' : '') + x.toFixed(1);
}
/** Seconds with a comma (boards: "6,8 s"). */
export const secs = (ms: number | null | undefined) => (ms == null ? '' : (ms / 1000).toFixed(1).replace('.', ',') + ' s');

export function fmtDate(iso?: string | null, withTime = true): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (v: number) => String(v).padStart(2, '0');
  const date = `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()}`;
  return withTime ? `${date} ${p(d.getHours())}:${p(d.getMinutes())}` : date;
}

export const rarity = (e: Pick<EvidenceItem, 'df' | 'N'>) => (e.N ? `${n(e.df ?? 0)} z ${n(e.N)}` : '');

/** Strength meter 0..100 from weight (boards: +3.1 → 100, +0.8 → 26). */
/** Strength meter 0..100. Weight scale differs between engines (mock ≤ 3.1, real ≤ ~7); scale by strength too. */
export const strengthPct = (e: EvidenceItem) => (e.state === 'zero' ? 0 : Math.max(4, Math.min(100, Math.round(Math.max(Math.abs(e.weight) / (Math.abs(e.weight) > 3.2 ? 7 : 3.1), e.strength === 'H' ? 0.7 : e.strength === 'M' ? 0.4 : 0.15) * 100))));
export const strengthLabel = (e: EvidenceItem) =>
  e.state === 'zero' ? 'pomijam' : e.state === 'missing' ? 'brak' : e.state === 'conflict' ? 'sprzeczny' : e.strength === 'H' ? 'silny' : e.strength === 'M' ? 'średni' : 'słaby';

/** Long sentence for the Raport list (board 3); falls back to the chip display. */
export function evidenceSentence(e: EvidenceItem): string {
  const f = e.field.toLowerCase();
  // the real engine already writes a readable "Label: value" display
  if (e.display.includes(':') && e.state !== 'zero') return e.display;
  if (e.state === 'zero') return e.display;
  if (f.includes('capi')) return `Ta sama bramka CAPI co ${n(e.df ?? 0)} materiałów tej kampanii`;
  if (f.includes('kit')) return `Ten sam zestaw strony: ${e.value}`;
  if (f.includes('template') || f.includes('headline')) return `Tekst z szablonu ${e.display.replace(/^szablon\s*/i, '')}`;
  if (f.includes('cert')) return `Certyfikat z tej samej nocnej partii ${e.display.replace(/^(cert(yfikaty?)?\s*(batch)?\s*)/i, '').replace(/,\s*noc$/, '').replace(/\s*\d{2}:\d{2}.*$/, '')}`;
  if (f.includes('face') || e.type === 'persons') return `W reklamie ta sama twarz: ${(e.value || e.display).split(/[·(]/)[0].trim()}`;
  if (f.includes('pixel')) return `Ten sam piksel: ${e.display}`;
  return e.display;
}
export function evidenceMeta(e: EvidenceItem): string {
  const lvl = (e as { level?: string | null }).level ?? '';
  const parts = [botName(e.bot), e.state === 'zero' ? SIDE_LEVEL[lvl] ?? 'nie liczy się do kampanii' : LAYER_LABEL[e.type].toLowerCase()];
  if (e.state !== 'zero' && e.N && e.df) parts.push(rarity(e));
  return parts.join(' · ');
}

export const DECISION_LABEL: Record<string, string> = {
  assign: 'Dołącza do kampanii',
  confirm: 'Dołącza do kampanii (do potwierdzenia)',
  ambiguous: 'Niepewne → triage',
  new: 'Nowa kampania (kandydat)',
  insufficient: 'Za mało śladów',
};

const FIELD_LABEL: Record<string, string> = {
  kit_tenants: 'Konto operatora w zestawie strony', kit_tenant: 'Konto operatora w zestawie strony', landing_type_ids: 'Typ landingu', landing_type_id: 'Typ landingu',
  lander_ids: 'Lander', lander_id: 'Lander', fb_pixels: 'Piksel FB', fb_pixel: 'Piksel FB', capi_gateways: 'Bramka CAPI',
  capi_gateway: 'Bramka CAPI', brands: 'Marki', persons: 'Osoby', kit_endpoints: 'Adresy API zestawu strony', kit_endpoint: 'Adres API zestawu strony',
  url_param_schema: 'Gramatyka URL', chain_param_schemas: 'Gramatyka URL łańcucha', headline_template: 'Szablon nagłówka',
  h1_template: 'Szablon H1', comment_names: 'Fałszywi komentujący', asset_hashes: 'Wspólne pliki', brand_asset_hashes: 'Pliki marki',
  path_shapes: 'Kształt ścieżki', entry_path_template: 'Ścieżka wejścia', google_ads: 'Google Ads', ga4: 'GA4', gtm: 'GTM',
  tiktok_pixels: 'Piksel TikTok', video_hosts: 'Hosting wideo', vertical: 'Branża', products: 'Produkty', domains: 'Domeny',
  registrar: 'Rejestrator', asn: 'ASN', cdn: 'CDN', ns: 'Serwery DNS', text_minhash: 'Tekst strony', dom_minhash: 'Struktura DOM',
};
const VERTICAL: Record<string, string> = { investment: 'inwestycje', health: 'zdrowie', gov: 'dopłaty państwowe', crypto: 'kryptowaluty', loans: 'pożyczki', spiritual: 'duchowość' };

/** Engine displays sometimes start with a raw field name or carry English bits; make them read as Polish UI copy. */
export function prettyDisplay(s: string | null | undefined): string {
  if (!s) return '';
  let out = s.replace(/^([a-z][a-z0-9_]+):\s*/, (m, f: string) => (FIELD_LABEL[f] ? `${FIELD_LABEL[f]}: ` : m));
  // engine labels say "kit"; the UI says "zestaw strony" (the value itself is left as is)
  out = out.replace(/^Tenant kitu:/, 'Konto operatora w zestawie strony:').replace(/^Endpointy kitu:/, 'Adresy API zestawu strony:').replace(/^Endpoint kitu:/, 'Adres API zestawu strony:');
  out = out.replace(/\bshared \(e\.g\. /g, 'wspólne (np. ').replace(/\(e\.g\. /g, '(np. ');
  out = out.replace(/\b(investment|health|gov|crypto|loans|spiritual)\b/g, (v: string) => VERTICAL[v] ?? v).replace(/ != /g, ' ≠ ');
  // engine tokens → Polish
  out = out.replace(/jaccard=([\d.]+)/g, (_m, v: string) => `podobieństwo ${Math.round(parseFloat(v) * 100)}%`);
  out = out.replace(/\('([a-z0-9-]+)', \('(no)?dash', '(no)?digit', (\d+)\)\)/g, (_m, tld: string, nd: string, ng: string, k: string) => {
    const parts = [`.${tld}`, nd && ng ? 'bez myślników i cyfr' : nd ? 'bez myślników' : ng ? 'bez cyfr' : 'z myślnikami i cyframi', `${+k * 3}–${+k * 3 + 2} znaków`];
    return parts.join(', ');
  });
  out = out.replace(/\b([0-9a-f]{8})-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi, 'UUID $1…');
  out = out.replace(/\b([0-9a-f]{8})[0-9a-f]{24,}\b/gi, '$1…');
  out = out.replace(/(\.[a-z]{2,})\|/g, '$1 + ');
  out = out.replace(/ created (\d+) min apart/g, ', rejestracje w odstępie $1 min').replace(/ issued (\d+) min apart/g, ', wystawione w odstępie $1 min');
  out = out.replace(/(\d+) wspólne\b/g, (_m, k: string) => `${k} ${+k === 1 ? 'wspólny' : +k % 10 >= 2 && +k % 10 <= 4 && (+k % 100 < 10 || +k % 100 >= 20) ? 'wspólne' : 'wspólnych'}`);
  // masked template slots stay visible as slots: {per} → {PER} (never filled in)
  out = out.replace(/\{([a-z]{2,8})\}/g, (_m, k: string) => `{${k.toUpperCase()}}`);
  return out;
}
const titleWord = (w: string) => w.replace(/(^|[\s-])(\p{L})/gu, (_m, a: string, b: string) => a + b.toUpperCase());
/** Names of people come lower-case from the engine: show them title-cased; short brand acronyms upper-cased (pko → PKO). */
function caseNames(field: string, display: string): string {
  const i = display.indexOf(': ');
  if (i < 0) return display;
  const head = display.slice(0, i + 2), tail = display.slice(i + 2);
  if (/person|face|comment_name|^persons$/.test(field)) {
    if (/np\. /.test(tail)) return head + tail.replace(/(np\. )([^)]+)/, (_m, a: string, b: string) => a + titleWord(b));
    return head + titleWord(tail);
  }
  if (/brand/.test(field)) {
    const fix = (b: string) => (/^[a-z0-9]{2,5}$/.test(b) && !/^\d+$/.test(b) ? b.toUpperCase() : b);
    if (/np\. /.test(tail)) return head + tail.replace(/(np\. )([^)]+)/, (_m, a: string, b: string) => a + fix(b.trim()));
    return head + tail.split(/,\s*/).map(fix).join(', ');
  }
  return display;
}
export const prettyEv = <T extends { display: string; field?: string }>(e: T): T => ({ ...e, display: caseNames(e.field ?? '', prettyDisplay(e.display)) });
/** Real-mode engine narratives are English; the UI only shows Polish copy. */
const EN = /\b(the|via|and|of|for|with|investment|cure|fake|interview|pain|loss|story|offer|doctor|platform|news|vs)\b/i;
export const isPolish = (t?: string | null) => !!t && !EN.test(t) && /[ąćęłńóśźż]|\b(i|w|z|na|do|się|nie|przez|oraz|dla)\b/i.test(t);
export const plOnly = (t?: string | null) => (isPolish(t) ? t! : '');
export const BOT_FOR_LAYER: Record<string, BotName> = { tracking: 'tropiciel', kit: 'tropiciel', content: 'czytelnik', persons: 'czytelnik', infra: 'notariusz', visual: 'zwiadowca', ad: 'zwiadowca', media: 'czytelnik' };
/** Polish plural form only: pluralWord(5, 'materiał', 'materiały', 'materiałów') → 'materiałów'. */
export const pluralWord = (k: number, one: string, few: string, many: string) => (k === 1 ? one : k % 10 >= 2 && k % 10 <= 4 && (k % 100 < 10 || k % 100 >= 20) ? few : many);
/** Number + Polish plural: plural(2, 'materiał', 'materiały', 'materiałów') → '2 materiały'. */
export const plural = (k: number, one: string, few: string, many: string) => `${n(k)} ${pluralWord(k, one, few, many)}`;
export const verticalPl = (v?: string | null) => (v ? VERTICAL[v] ?? v : '');
