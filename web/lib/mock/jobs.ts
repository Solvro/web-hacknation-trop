// Client-side simulation of GET /api/v1/jobs/{id}/stream (CONTRACTS §4.1) for offline demo.
import type { Decision, EvidenceItem, Event, JobStep, StepKey } from '../contracts';
import { BOT_BY_STEP } from '../copy';
import {
  DECISION_BON, DECISION_KELVARO, DECISION_SELQUENO, DECISION_ZAMACH, EV_BON, EV_KELVARO, EV_SELQUENO, EV_ZAMACH,
} from './universe';

export type Scenario = 'zamach' | 'nowa' | 'niepewne' | 'blad';
export interface TimedEvent { delay: number; ev: Event }

/** Pick the demo outcome from what the user typed (only used without a live API). */
export function scenarioFor(input: string): Scenario {
  const s = input.toLowerCase();
  if (/bon|energ|prąd|prad|karta/.test(s)) return 'nowa';
  if (/kelvaro|glikonor|niepewn|\.har/.test(s)) return 'niepewne';
  if (/selqueno|502|blad|błąd|offline/.test(s)) return 'blad';
  return 'zamach';
}
export const SCENARIO_INCIDENT: Record<Scenario, string> = {
  zamach: 'INC-24817', nowa: 'INC-24822', niepewne: 'INC-24768', blad: 'INC-24830',
};
export const scenarioFromJobId = (id: string): Scenario | null => {
  const m = /^local-(zamach|nowa|niepewne|blad)/.exec(id);
  return m ? (m[1] as Scenario) : null;
};

interface StepPlan {
  key: StepKey;
  run: string;
  out: string;
  notes?: string[];
  ms: number;
  status?: JobStep['status'];
  warnings?: string[];
  evidence?: EvidenceItem[];
  ranking?: { id: string; p: number }[][];
}

function build(jobId: string, plans: StepPlan[], decision: Decision, error?: { step: StepKey; message: string }): TimedEvent[] {
  const out: TimedEvent[] = [];
  const at = () => new Date().toISOString();
  const push = (delay: number, type: Event['type'], data: Record<string, unknown>) => out.push({ delay, ev: { type, at: at(), data: { job_id: jobId, ...data } } });
  const step = (p: StepPlan, status: JobStep['status'], detail: string, extra: Partial<JobStep> = {}): JobStep => ({
    key: p.key, bot: BOT_BY_STEP[p.key].key, label: BOT_BY_STEP[p.key].stepName, status, detail, ...extra,
  });
  for (const p of plans) {
    const pace = Math.max(700, Math.min(1800, p.ms / 4));
    push(260, 'job.step', { step: step(p, 'run', p.run) });
    const evs = p.evidence ?? [];
    evs.forEach((e, i) => {
      push(pace / (evs.length + 1), 'job.evidence', { bot: BOT_BY_STEP[p.key].key, item: e });
      push(40, 'job.finding', { finding: { evidence: e, where: e.type === 'tracking' || e.type === 'infra' ? 'har' : 'html' } });
      const r = p.ranking?.[i];
      if (r) push(120, 'job.ranking', { scores: r.map((x) => ({ campaign_id: x.id, score: x.p * 10, p: x.p, in_set: false })) });
    });
    if (error && error.step === p.key) {
      push(pace, 'job.error', { step: p.key, message: error.message });
      push(80, 'job.step', { step: step(p, 'error', [p.out, ...(p.notes ?? [])].join('\n'), { duration_ms: p.ms }) });
      continue;
    }
    if (p.ranking && p.ranking.length > evs.length) {
      for (const r of p.ranking.slice(evs.length)) push(pace / 2, 'job.ranking', { scores: r.map((x) => ({ campaign_id: x.id, score: x.p * 10, p: x.p, in_set: false })) });
    }
    push(pace, 'job.step', { step: step(p, p.status ?? 'done', [p.out, ...(p.notes ?? [])].join('\n'), { duration_ms: p.ms, warnings: p.warnings ?? [] }) });
  }
  push(700, 'job.done', { incident_id: decision.incident_id, decision });
  return out;
}

export function scenarioEvents(jobId: string, sc: Scenario): TimedEvent[] {
  if (sc === 'zamach') {
    const [capi, kit, tpl, cert, face, cf] = EV_ZAMACH;
    return build(jobId, [
      { key: 'capture', run: 'Otwieram stronę w piaskownicy. Formularzy nie wysyłam.', out: '4 przekierowania · 212 żądań', ms: 6800,
        notes: ['Otworzyłem stronę w piaskownicy. Formularzy nie wysyłam.', 'Droga: l.facebook.com → morvanta.click/?utm_visit=0193a7c2-…'] },
      { key: 'tracking', run: 'Szukam pikseli, bramek konwersji i kitu w ruchu sieciowym.', out: 'bramka CAPI · kit relay v1', ms: 600, evidence: [capi, kit],
        notes: ['Bramka CAPI cg-7f3a… ma 47 materiałów, wszystkie z KMP-017.', 'Ścieżka /api/v2/relay/lead/{uuid}/ występuje też w KMP-034.'] },
      { key: 'content', run: 'Czytam nagłówek i tekst, rozpoznaję twarze.', out: 'szablon „PILNE” · Jan Kowalski', ms: 3900, evidence: [tpl, face],
        notes: ['Tekst pasuje do szablonu „PILNE: {PER} przerywa…” (0.93).', 'Twarz w reklamie: Jan Kowalski, podobieństwo 0.91.'] },
      { key: 'infra', run: 'Pytam RDAP i crt.sh. RDAP nie odpowiada, ponawiam.', out: 'częściowo: RDAP nie odpowiedział', ms: 2400, status: 'warn', evidence: [cert],
        warnings: ['RDAP timeout'], notes: ['Certyfikat z nocnej partii 6 certyfikatów LE R11.', 'RDAP milczał 3 razy, więc rejestratora nie znam. Werdykt liczony bez tej informacji.'] },
      { key: 'compare', run: 'Porównuję ślady z 1 284 materiałami w bazie.', out: '312 podobnych · 9 kampanii', ms: 400, evidence: [cf],
        ranking: [[{ id: 'KMP-017', p: 0.9 }, { id: 'KMP-034', p: 0.44 }, { id: 'KMP-022', p: 0.12 }], [{ id: 'KMP-017', p: 0.94 }, { id: 'KMP-034', p: 0.41 }, { id: 'KMP-022', p: 0.08 }]],
        notes: ['Najbliżej: KMP-017 0.94, KMP-034 0.41, KMP-022 0.08.', 'Cloudflare 203.0.113.0/24 pomijam: ma go 512 niepowiązanych spraw.'] },
      { key: 'verdict', run: 'Ważę dowody i piszę raport.', out: 'KMP-017 · pewność 0.94', ms: 5500,
        notes: ['Tylko KMP-017 przekracza próg pewności.', 'Najwięcej ważyły bramka CAPI i kit.'] },
    ], DECISION_ZAMACH);
  }
  if (sc === 'nowa') {
    const [px, form, tpl, reg, faces] = EV_BON;
    return build(jobId, [
      { key: 'capture', run: 'Otwieram stronę w piaskownicy. Formularzy nie wysyłam.', out: '2 przekierowania · 64 żądania', ms: 5200, notes: ['Strona prosi o numer karty. Niczego nie wpisuję.'] },
      { key: 'tracking', run: 'Szukam pikseli, bramek konwersji i kitu w ruchu sieciowym.', out: 'nowy piksel · nowy formularz', ms: 700, evidence: [px, form], notes: ['Piksel Meta 1188 0420 7731 552: nikt w bazie go nie używa.'] },
      { key: 'content', run: 'Czytam nagłówek i tekst, rozpoznaję twarze.', out: '„Bon energetyczny 2026” · bez twarzy', ms: 3100, evidence: [tpl, faces], notes: ['3 podobne materiały przyszły z wtyczki.'] },
      { key: 'infra', run: 'Pytam RDAP i crt.sh o domenę i certyfikat.', out: 'domena z wczoraj', ms: 1900, evidence: [reg], notes: ['Inny rejestrator niż w znanych kampaniach.'] },
      { key: 'compare', run: 'Porównuję ślady z 1 284 materiałami w bazie.', out: 'brak kampanii powyżej progu', ms: 500,
        ranking: [[{ id: 'KMP-031', p: 0.18 }, { id: 'KMP-022', p: 0.06 }, { id: 'KMP-017', p: 0.04 }]], notes: ['Najbliżej: KMP-031 0.18. Żeby dołączyć, potrzeba co najmniej 0.80.'] },
      { key: 'verdict', run: 'Ważę dowody i piszę raport.', out: 'nowa kampania (kandydat)', ms: 2600, notes: ['Ślady są nowe. To najpewniej początek nowej kampanii.'] },
    ], DECISION_BON);
  }
  if (sc === 'niepewne') {
    const [capi, kit, live, empty] = EV_KELVARO;
    return build(jobId, [
      { key: 'capture', run: 'Czytam plik HAR. Strony nie otwieram.', out: 'HAR · 148 żądań', ms: 900, notes: ['Plik HAR bez zrzutu reklamy.'] },
      { key: 'tracking', run: 'Szukam pikseli, bramek konwersji i kitu w ruchu sieciowym.', out: 'bramka CAPI · kit relay v1', ms: 600, evidence: [capi, kit], notes: ['Te ślady mają obie kampanie OP-03.'] },
      { key: 'content', run: 'Szukam tekstu i twarzy.', out: 'strona jest pusta', ms: 400, status: 'skip', evidence: [empty], notes: ['Bez zrzutu nie mam czego przeczytać.'] },
      { key: 'infra', run: 'Pytam RDAP i crt.sh o domenę i certyfikat.', out: 'kelvaro.live · nocny certyfikat', ms: 1700, evidence: [live] },
      { key: 'compare', run: 'Porównuję ślady z 1 284 materiałami w bazie.', out: '2 kampanie tego samego operatora', ms: 400,
        ranking: [[{ id: 'KMP-017', p: 0.52 }, { id: 'KMP-034', p: 0.47 }]] },
      { key: 'verdict', run: 'Ważę dowody i piszę raport.', out: 'niepewne: KMP-017 0.52 / KMP-034 0.47', ms: 1200, notes: ['Dwie kampanie są zbyt blisko siebie, żeby wybrać samemu.'] },
    ], DECISION_KELVARO);
  }
  const [dna, hist] = EV_SELQUENO;
  return build(jobId, [
    { key: 'capture', run: 'Otwieram stronę w piaskownicy. Formularzy nie wysyłam.', out: 'błąd 502 przy 3 próbach', ms: 9000, notes: ['Strona: błąd 502 przy 3 próbach.'] },
    { key: 'tracking', run: 'Bez strony nie zobaczę ruchu sieciowego.', out: 'potrzebuje strony', ms: 0, status: 'skip' },
    { key: 'content', run: 'Bez strony ani zrzutu nie mam czego czytać.', out: 'potrzebuje strony albo zrzutu', ms: 0, status: 'skip' },
    { key: 'infra', run: 'Pytam rejestr i crt.sh. Strony nie potrzebuję.', out: 'DNA domeny jak KMP-017', ms: 1800, evidence: [dna] },
    { key: 'compare', run: 'Szukam tej domeny w bazie.', out: 'domena znana z KMP-017', ms: 400, evidence: [hist], ranking: [[{ id: 'KMP-017', p: 0.61 }]] },
    { key: 'verdict', run: 'Ważę dowody i piszę raport.', out: 'wstępnie KMP-017, bez potwierdzenia', ms: 600 },
  ], DECISION_SELQUENO, { step: 'capture', message: 'selqueno.live od 17.11 zwraca błąd 502. Bez strony boty nie zobaczą kitu ani formularza, więc nie potwierdzą kampanii.' });
}
