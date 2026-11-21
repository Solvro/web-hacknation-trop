import type { BotName, EvidenceItem, Layer, StepKey } from './contracts';

export const LAYER_LABEL: Record<Layer, string> = {
  tracking: 'Tracking', kit: 'Kit', infra: 'Infra', content: 'Treść', persons: 'Osoby', visual: 'Obraz', ad: 'Reklama', media: 'Media',
};

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
  if (e.state === 'zero') return `${e.display} pominięty: ma go ${n(e.df ?? 0)} niepowiązanych spraw`;
  if (f.includes('capi')) return `Ta sama bramka CAPI co ${n(e.df ?? 0)} materiałów tej kampanii`;
  if (f.includes('kit')) return `Ten sam kit: ${e.value}`;
  if (f.includes('template') || f.includes('headline')) return `Tekst z szablonu ${e.display.replace(/^szablon\s*/i, '')}`;
  if (f.includes('cert')) return `Certyfikat z tej samej nocnej partii ${e.display.replace(/^(cert(yfikaty?)?\s*(batch)?\s*)/i, '').replace(/,\s*noc$/, '').replace(/\s*\d{2}:\d{2}.*$/, '')}`;
  if (f.includes('face') || e.type === 'persons') return `W reklamie ta sama twarz: ${(e.value || e.display).split(/[·(]/)[0].trim()}`;
  if (f.includes('pixel')) return `Ten sam piksel: ${e.display}`;
  return e.display;
}
export function evidenceMeta(e: EvidenceItem): string {
  const parts = [botName(e.bot), e.state === 'zero' ? 'wspólna infrastruktura' : LAYER_LABEL[e.type].toLowerCase()];
  if (e.state === 'zero') parts.push('waga 0');
  else if (e.N && e.df) parts.push(rarity(e));
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
  kit_tenants: 'Tenant kitu', kit_tenant: 'Tenant kitu', landing_type_ids: 'Typ landingu', landing_type_id: 'Typ landingu',
  lander_ids: 'Lander', lander_id: 'Lander', fb_pixels: 'Piksel FB', fb_pixel: 'Piksel FB', capi_gateways: 'Bramka CAPI',
  capi_gateway: 'Bramka CAPI', brands: 'Marki', persons: 'Osoby', kit_endpoints: 'Endpointy kitu', kit_endpoint: 'Endpoint kitu',
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
  out = out.replace(/\bshared \(e\.g\. /g, 'wspólne (np. ').replace(/\(e\.g\. /g, '(np. ');
  out = out.replace(/^Branża: (\w+)/, (_, v: string) => `Branża: ${VERTICAL[v] ?? v}`);
  return out;
}
export const prettyEv = <T extends { display: string }>(e: T): T => ({ ...e, display: prettyDisplay(e.display) });
/** Real-mode engine narratives are English; the UI only shows Polish copy. */
const EN = /\b(the|via|and|of|for|with|investment|cure|fake|interview|pain|loss|story|offer|doctor|platform|news|vs)\b/i;
export const isPolish = (t?: string | null) => !!t && !EN.test(t) && /[ąćęłńóśźż]|\b(i|w|z|na|do|się|nie|przez|oraz|dla)\b/i.test(t);
export const plOnly = (t?: string | null) => (isPolish(t) ? t! : '');
export const BOT_FOR_LAYER: Record<string, BotName> = { tracking: 'tropiciel', kit: 'tropiciel', content: 'czytelnik', persons: 'czytelnik', infra: 'notariusz', visual: 'zwiadowca', ad: 'zwiadowca', media: 'czytelnik' };
export const plural = (k: number, one: string, few: string, many: string) => `${n(k)} ${k === 1 ? one : k % 10 >= 2 && k % 10 <= 4 && (k % 100 < 10 || k % 100 >= 20) ? few : many}`;
export const verticalPl = (v?: string | null) => (v ? VERTICAL[v] ?? v : '');
