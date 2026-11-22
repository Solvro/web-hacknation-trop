/**
 * The cuts: each version of the demo video is a list of scenes with lengths and handovers.
 * Responsibility: the stories and the on-screen claims. Every claim is something the live
 * app shows or the repo's README/METHODOLOGY states; captions name the screen they are on.
 * Camera keyframes are capture pixels (1920×1080).
 * Idempotency: n/a — data.
 */
import type { ClipScene, Cut, Scene, StatsScene } from './types.ts';

const clip = (c: Omit<ClipScene, 'kind'>): ClipScene => ({ kind: 'clip', ...c });
const FULL = { x: 960, y: 540, z: 1 };
// camera paths per capture (capture px), reused by the cuts
const CAM_LAB = (d: number) => [
  { at: 0, x: 960, y: 380, z: 1.3 },
  { at: d * 0.28, x: 960, y: 380, z: 1.3 },
  { at: d * 0.42, ...FULL },
  { at: d * 0.62, x: 1320, y: 380, z: 1.5 },
  { at: d, x: 1320, y: 380, z: 1.5 },
];


// ---- shared scenes -------------------------------------------------------------------

const RESULTS: StatsScene = {
  kind: 'stats',
  dur: 6,
  title: 'Wyniki · trop eval na danych z etykietami',
  items: [
    { value: '0', label: 'błędnych powiązań', note: 'w każdym teście: próbka, perturbacje, DANE' },
    { value: '1.00', label: 'B³ F1 na próbce', note: '15 materiałów z etykietami' },
    { value: '9/9', label: 'DANE held-out', note: 'poprawne decyzje, 0 błędnych' },
    { value: '50', label: 'domen z jednego śledztwa', note: 'White Rabbit: wspólny rzadki zasób' },
  ],
};

const LEVELS: Scene = {
  kind: 'statement',
  dur: 4.2,
  kicker: 'Trzy poziomy',
  lines: [
    { text: 'kampania', at: 0.1 },
    { text: '→ operator', at: 0.45 },
    { text: '→ operacja', at: 0.8, accent: true },
    { text: 'każde powiązanie z dowodami: waga, rzadkość, kto znalazł', at: 1.4, small: true },
  ],
};

// ---- A: the straight jury walkthrough (≈ 1:55) ------------------------------------------

const A: Cut = {
  id: 'A-Przeglad',
  purpose: 'Straight 2-minute jury walkthrough of every screen',
  look: 'card',
  scenes: [
    { scene: { kind: 'title', dur: 3.2 } },
    {
      into: 'fade',
      scene: clip({
        shot: 'sprawdz', from: 'start', to: 'analysis', dur: 3.6,
        cam: [{ at: 0, x: 960, y: 500, z: 1.25 }, { at: 2.3, x: 760, y: 620, z: 1.45 }, { at: 3.6, x: 760, y: 620, z: 1.45 }],
        caps: [{ at: 0.3, until: 3.4, text: 'Sprawdź: link, zrzut, wideo, HAR albo cały folder', sub: 'tu jeden klik: przykładowy materiał z danych', pos: 'tr' }],
      }),
    },
    {
      scene: clip({
        shot: 'sprawdz', from: 'analysis', to: 'verdict', dur: 12,
        cam: [
          { at: 0, ...FULL }, { at: 1.0, x: 960, y: 400, z: 1.3 }, { at: 3.8, x: 960, y: 400, z: 1.3 },
          { at: 4.6, x: 900, y: 600, z: 1.4 }, { at: 7.6, x: 900, y: 600, z: 1.4 },
          { at: 8.4, x: 1250, y: 560, z: 1.45 }, { at: 12, x: 1250, y: 560, z: 1.45 },
        ],
        caps: [
          { at: 0.3, until: 3.8, text: 'Sześć botów-detektywów pracuje po kolei', sub: 'Zwiadowca · Tropiciel · Czytelnik · Notariusz · Archiwista · Sędzia', pos: 'bl' },
          { at: 4.3, until: 7.7, bot: 'tropiciel', text: 'Piksel, konto w zestawie strony, landing', sub: 'przy każdym śladzie: ile materiałów w bazie go ma', pos: 'br' },
          { at: 8.2, until: 11.8, bot: 'archiwista', text: 'Najbliższe kampanie liczą się na żywo', sub: 'a Zwiadowca dokłada zrzut przechwyconej strony', pos: 'bl' },
        ],
      }),
    },
    {
      scene: clip({
        shot: 'sprawdz', from: 'verdict-0.3', to: 'outlines-0.6', dur: 4,
        cam: [{ at: 0, x: 820, y: 420, z: 1.4 }, { at: 2.4, x: 820, y: 420, z: 1.4 }, { at: 3.6, x: 1400, y: 420, z: 1.7 }, { at: 4, x: 1400, y: 420, z: 1.7 }],
        caps: [{ at: 0.2, until: 3.8, text: 'Werdykt: dołącza do kampanii KMP-001 · pewność 0.99', sub: 'operator OP-01, następna kampania tylko 0.01', pos: 'br' }],
      }),
    },
    {
      scene: clip({
        shot: 'sprawdz', from: 'outlines-0.6', to: 'end', dur: 4.4,
        cam: [{ at: 0, x: 1400, y: 420, z: 1.7 }, { at: 4.4, x: 1400, y: 400, z: 1.75 }],
        caps: [{ at: 0.2, until: 4.2, text: 'Przechwycona strona: obrysy pokazują, gdzie boty znalazły dowody', pos: 'bl' }],
      }),
    },
    {
      scene: clip({
        shot: 'graf', from: 'graf-0.3', to: 'end', dur: 11,
        cam: [{ at: 0, x: 960, y: 420, z: 1.15 }, { at: 0.6, x: 960, y: 420, z: 1.15 }, { at: 1.5, x: 950, y: 560, z: 1.36 }, { at: 11, x: 950, y: 560, z: 1.36 }],
        caps: [
          { at: 0.3, until: 3.4, text: 'Graf: materiał, ślady, osoby, kampania, operator', pos: 'br' },
          { at: 3.7, until: 6.6, text: 'Klik w osobę: Rafał Brzoska w 5 materiałach', sub: 'wizerunek albo nazwisko, wspólne dla całej serii', pos: 'br' },
          { at: 6.9, until: 10.8, text: 'Kampania KMP-001 i operator OP-01', sub: 'każdy węzeł rozwija swoje powiązania', pos: 'br' },
        ],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'nowa', from: 'analysis+0.2', to: 'end', dur: 10,
        cam: [{ at: 0, ...FULL }, { at: 5.8, ...FULL }, { at: 6.5, x: 760, y: 560, z: 1.3 }, { at: 7.3, x: 760, y: 560, z: 1.3 }, { at: 8.1, x: 960, y: 640, z: 1.2 }],
        caps: [
          { at: 0.3, until: 4.6, text: 'Materiał, którego żadna kampania nie tłumaczy', sub: '„Poland Invest Summit 2026”', pos: 'bl' },
          { at: 5.0, until: 9.8, bot: 'sedzia', text: 'Nowa kampania (kandydat), bez wymuszania', sub: 'żeby dołączyć, potrzeba co najmniej 0.80; najbliższa ma 0.01', pos: 'bl' },
        ],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'live', from: 'start+0.6', to: 'verdict+1.2', dur: 9,
        cam: [{ at: 0, x: 960, y: 440, z: 1.5 }, { at: 2.2, x: 960, y: 440, z: 1.5 }, { at: 3.0, ...FULL }, { at: 7.3, ...FULL }, { at: 8.1, x: 450, y: 620, z: 1.6 }, { at: 9, x: 450, y: 620, z: 1.6 }],
        caps: [
          { at: 0.3, until: 4.4, bot: 'zwiadowca', text: 'Dowolny link: strona przechwycona w piaskownicy', sub: 'formularzy nie wysyłamy', pos: 'br' },
          { at: 4.7, until: 8.8, text: 'example.com nie pasuje do żadnej kampanii, i słusznie', sub: 'zrzut strony, HTML i ruch sieciowy z piaskownicy', pos: 'br' },
        ],
      }),
    },
    { into: 'fade', scene: LEVELS },
    {
      into: 'fade',
      scene: clip({
        shot: 'kampanie', from: 'start', to: 'package', dur: 11,
        cam: [{ at: 0, x: 960, y: 420, z: 1.3 }, { at: 2.6, x: 960, y: 420, z: 1.3 }, { at: 3.7, x: 960, y: 480, z: 1.12 }, { at: 11, x: 960, y: 480, z: 1.12 }],
        caps: [
          { at: 0.3, until: 3.4, text: 'Kampanie pogrupowane według operatorów', sub: 'i Oracle: nowe domeny pasujące do znanych zestawów, zanim pojawi się reklama', pos: 'br' },
          { at: 3.8, until: 10.8, text: 'KMP-001: 6 materiałów · 5 domen · 4 reklamodawców', sub: '0 z 5 domen na liście CERT PL', pos: 'bl' },
        ],
      }),
    },
    {
      scene: clip({
        shot: 'kampanie', from: 'package', to: 'end', dur: 7,
        cam: [{ at: 0, ...FULL }, { at: 1.2, x: 960, y: 600, z: 1.18 }, { at: 3.4, x: 1250, y: 780, z: 1.5 }, { at: 7, x: 1250, y: 780, z: 1.5 }],
        caps: [
          { at: 0.3, until: 6.8, text: 'Jedno zgłoszenie na całą kampanię', sub: 'Meta DSA art. 16 · CERT PL · STIX 2.1 · PDF. Przygotowane i eksportowane, nic nie wychodzi samo.', pos: 'bl' },
        ],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'sledztwo', from: 'start', to: 'done-0.5', dur: 9.5,
        cam: [{ at: 0, x: 960, y: 420, z: 1.2 }, { at: 1.6, x: 960, y: 420, z: 1.2 }, { at: 2.8, x: 960, y: 660, z: 1.15 }, { at: 9.5, x: 960, y: 660, z: 1.15 }],
        caps: [
          { at: 0.3, until: 4.4, text: 'Śledztwa: White Rabbit startuje od jednej domeny', sub: 'certyfikaty, rejestracje, reklamy, urlscan, lista CERT PL', pos: 'br' },
          { at: 4.7, until: 9.4, text: 'Graf rośnie z każdym krokiem agenta', sub: 'zapis prawdziwego przebiegu (replay), przyspieszony', pos: 'br' },
        ],
      }),
    },
    {
      scene: clip({
        shot: 'sledztwo', from: 'done-0.3', to: 'end', dur: 4.5,
        cam: [{ at: 0, x: 760, y: 420, z: 1.3 }, { at: 4.5, x: 760, y: 460, z: 1.3 }],
        caps: [{ at: 0.3, until: 4.3, text: '50 nowych domen, żadnej jeszcze na liście CERT PL', sub: 'wspólny rzadki zasób strony (urlscan)', pos: 'br' }],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'extension', from: 'start', to: 'end', dur: 7,
        cam: [{ at: 0, x: 950, y: 420, z: 1.6 }, { at: 1.0, x: 950, y: 420, z: 1.6 }, { at: 1.9, x: 950, y: 330, z: 2.0 }, { at: 3.6, x: 950, y: 330, z: 2.0 }, { at: 4.4, x: 950, y: 270, z: 2.2 }, { at: 7, x: 950, y: 270, z: 2.2 }],
        caps: [{ at: 0.3, until: 6.8, text: 'Wtyczka do przeglądarki: ostrzeżenie na reklamie ze znanej kampanii', sub: 'strona demo wzorowana na reklamie z korpusu; z przeglądarki wychodzi tylko anonimowy odcisk', pos: 'bl' }],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'lab', from: 'start', to: 'end', dur: 7.5,
        cam: CAM_LAB(7.5),
        caps: [{ at: 0.3, until: 7.3, text: 'Lab: 0 błędnych przypisań', sub: 'przy wybranym progu τ = 5 i w każdym teście odporności', pos: 'bl' }],
      }),
    },
    { into: 'fade', scene: RESULTS },
    { into: 'fade', scene: { kind: 'end', dur: 4.5 } },
  ],
};

// ---- B: the fast pitch cut (≈ 75 s) ------------------------------------------------------

const B: Cut = {
  id: 'B-Pitch',
  purpose: 'Fast 60-90 s pitch cut with bold captions',
  look: 'ink',
  scenes: [
    { scene: { kind: 'title', dur: 2.6, dark: true } },
    {
      into: 'fade',
      scene: clip({
        shot: 'sprawdz', from: 'click-0.6', to: 'verdict', dur: 9,
        cam: [{ at: 0, x: 760, y: 620, z: 1.45 }, { at: 0.9, ...FULL }, { at: 1.9, x: 960, y: 420, z: 1.25 }, { at: 6.0, x: 960, y: 420, z: 1.25 }, { at: 7.0, x: 1250, y: 560, z: 1.45 }, { at: 9, x: 1250, y: 560, z: 1.45 }],
        caps: [{ at: 0.2, until: 8.8, text: 'Wrzuć reklamę. Sześć botów szuka śladów.', pos: 'bl' }],
      }),
    },
    {
      scene: clip({
        shot: 'sprawdz', from: 'verdict-0.3', to: 'end', dur: 6,
        cam: [{ at: 0, x: 820, y: 420, z: 1.4 }, { at: 2.1, x: 820, y: 420, z: 1.4 }, { at: 3.2, x: 1400, y: 420, z: 1.7 }, { at: 6, x: 1400, y: 400, z: 1.75 }],
        caps: [{ at: 0.2, until: 5.8, text: 'Dołącza do KMP-001 · pewność 0.99', sub: 'z dowodami na przechwyconej stronie', pos: 'br' }],
      }),
    },
    {
      scene: clip({
        shot: 'graf', from: 'person-0.9', to: 'campaign+2.4', dur: 5,
        cam: [{ at: 0, x: 950, y: 560, z: 1.36 }],
        caps: [{ at: 0.2, until: 4.8, text: 'Każde powiązanie da się kliknąć i sprawdzić', pos: 'br' }],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'nowa', from: 'verdict-0.5', to: 'end', dur: 5,
        cam: [{ at: 0, ...FULL }, { at: 0.9, x: 760, y: 560, z: 1.3 }, { at: 1.9, x: 760, y: 560, z: 1.3 }, { at: 2.7, x: 960, y: 640, z: 1.2 }],
        caps: [{ at: 0.2, until: 4.8, text: 'Nic nie pasuje? Nowa kampania, bez zgadywania.', pos: 'bl' }],
      }),
    },
    { into: 'fade', scene: LEVELS },
    {
      into: 'fade',
      scene: clip({
        shot: 'kampanie', from: 'campaign', to: 'end', dur: 11,
        cam: [{ at: 0, x: 960, y: 480, z: 1.12 }, { at: 5.4, x: 960, y: 480, z: 1.12 }, { at: 6.6, x: 960, y: 600, z: 1.18 }, { at: 8.6, x: 1250, y: 780, z: 1.5 }, { at: 11, x: 1250, y: 780, z: 1.5 }],
        caps: [
          { at: 0.2, until: 5.0, text: '6 materiałów, 5 domen, 4 reklamodawców: jedna kampania', pos: 'bl' },
          { at: 5.3, until: 10.8, text: 'Jedno zgłoszenie: DSA, CERT PL, STIX', sub: 'przygotowane do eksportu, nic nie wychodzi samo', pos: 'bl' },
        ],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'sledztwo', from: 'start+1', to: 'end', dur: 8,
        cam: [{ at: 0, x: 960, y: 660, z: 1.15 }, { at: 5.6, x: 960, y: 660, z: 1.15 }, { at: 6.4, x: 760, y: 420, z: 1.3 }, { at: 8, x: 760, y: 420, z: 1.3 }],
        caps: [{ at: 0.2, until: 7.8, text: 'Agent idzie po śladach do reszty kampanii', pos: 'bl' }],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'extension', from: 'badge-0.4', to: 'end', dur: 5,
        cam: [{ at: 0, x: 950, y: 330, z: 2.0 }, { at: 2.2, x: 950, y: 330, z: 2.0 }, { at: 2.9, x: 950, y: 270, z: 2.2 }, { at: 5, x: 950, y: 270, z: 2.2 }],
        caps: [{ at: 0.2, until: 4.8, text: 'A w przeglądarce: ostrzeżenie na reklamie', pos: 'bl' }],
      }),
    },
    { into: 'fade', scene: { ...RESULTS, dark: true, dur: 5.5 } },
    { into: 'fade', scene: { kind: 'end', dur: 4 } },
  ],
};

// ---- C: problem → solution story (≈ 90 s) ------------------------------------------------

const C: Cut = {
  id: 'C-Problem',
  purpose: 'Problem → solution story: one ad is a trace, the campaign is the target',
  look: 'card',
  scenes: [
    {
      scene: {
        kind: 'statement',
        dur: 5,
        dark: true,
        kicker: 'Problem',
        lines: [
          { text: 'Reklamy-oszustwa', at: 0.1 },
          { text: 'zgłaszamy pojedynczo.', at: 0.5 },
          { text: 'Oszuści działają kampaniami.', at: 1.5, accent: true },
        ],
      },
    },
    {
      into: 'fade',
      scene: {
        kind: 'statement',
        dur: 5,
        kicker: 'Jedna kampania w TROP (KMP-001)',
        lines: [
          { text: '6 reklam · 5 domen', at: 0.1 },
          { text: '4 reklamodawców', at: 0.45 },
          { text: '0 z 5 domen na liście CERT PL', at: 0.9, accent: true },
          { text: 'jedna zablokowana domena nic nie kończy', at: 1.6, small: true },
        ],
      },
    },
    { into: 'fade', scene: { kind: 'title', dur: 3, dark: true } },
    { into: 'fade', scene: { kind: 'bots', dur: 4.8 } },
    {
      into: 'fade',
      scene: clip({
        shot: 'sprawdz', from: 'click-0.6', to: 'verdict', dur: 9,
        cam: [{ at: 0, x: 760, y: 620, z: 1.45 }, { at: 0.9, ...FULL }, { at: 1.9, x: 960, y: 420, z: 1.25 }, { at: 6.0, x: 960, y: 420, z: 1.25 }, { at: 7.0, x: 1250, y: 560, z: 1.45 }, { at: 9, x: 1250, y: 560, z: 1.45 }],
        caps: [{ at: 0.3, until: 8.8, text: 'Fałszywa Gazeta.pl: boty zbierają ślady', pos: 'bl' }],
      }),
    },
    {
      scene: clip({
        shot: 'sprawdz', from: 'verdict-0.3', to: 'end', dur: 7,
        cam: [{ at: 0, x: 820, y: 420, z: 1.4 }, { at: 2.4, x: 820, y: 420, z: 1.4 }, { at: 3.6, x: 1400, y: 420, z: 1.7 }, { at: 7, x: 1400, y: 400, z: 1.75 }],
        caps: [{ at: 0.3, until: 6.8, text: 'To nie pierwsza taka reklama: KMP-001 · pewność 0.99', sub: 'ten sam zestaw strony, piksel i bramka CAPI', pos: 'br' }],
      }),
    },
    {
      scene: clip({
        shot: 'graf', from: 'person-0.9', to: 'operator-0.3', dur: 6,
        cam: [{ at: 0, x: 950, y: 560, z: 1.36 }],
        caps: [{ at: 0.3, until: 5.8, text: 'Dlaczego? Wspólne osoby, ślady, operator', sub: 'każdy węzeł grafu da się rozwinąć', pos: 'br' }],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'nowa', from: 'verdict-0.5', to: 'end', dur: 6,
        cam: [{ at: 0, ...FULL }, { at: 0.9, x: 760, y: 560, z: 1.3 }, { at: 2.2, x: 760, y: 560, z: 1.3 }, { at: 3.1, x: 960, y: 640, z: 1.2 }],
        caps: [{ at: 0.3, until: 5.8, text: 'A gdy nic nie pasuje: nowa kampania, nie zgadywanie', sub: 'próg dołączenia 0.80, najbliższa kampania ma 0.01', pos: 'bl' }],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'sledztwo', from: 'start+1', to: 'end', dur: 10,
        cam: [{ at: 0, x: 960, y: 660, z: 1.15 }, { at: 7.2, x: 960, y: 660, z: 1.15 }, { at: 8.0, x: 760, y: 420, z: 1.3 }, { at: 10, x: 760, y: 420, z: 1.3 }],
        caps: [{ at: 0.3, until: 9.8, text: 'Od jednej domeny do całej infrastruktury', sub: 'White Rabbit, na żywo w grafie', pos: 'bl' }],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'kampanie', from: 'package-0.3', to: 'end', dur: 7,
        cam: [{ at: 0, ...FULL }, { at: 1.2, x: 960, y: 600, z: 1.18 }, { at: 3.4, x: 1250, y: 780, z: 1.5 }, { at: 7, x: 1250, y: 780, z: 1.5 }],
        caps: [{ at: 0.3, until: 6.8, text: 'Jedno zgłoszenie zamiast sześciu', sub: 'DSA art. 16 · CERT PL · STIX 2.1. Nic nie wychodzi samo.', pos: 'bl' }],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'extension', from: 'badge-0.4', to: 'end', dur: 5.5,
        cam: [{ at: 0, x: 950, y: 330, z: 2.0 }, { at: 2.4, x: 950, y: 330, z: 2.0 }, { at: 3.1, x: 950, y: 270, z: 2.2 }, { at: 5.5, x: 950, y: 270, z: 2.2 }],
        caps: [{ at: 0.3, until: 5.3, text: 'Ostrzeżenie trafia tam, gdzie jest reklama', sub: 'wtyczka do przeglądarki', pos: 'bl' }],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'lab', from: 'start', to: 'end', dur: 6,
        cam: CAM_LAB(6),
        caps: [{ at: 0.3, until: 5.8, text: 'I bez fałszywych powiązań', sub: 'próg τ = 5: 0 błędnych, także bez zrzutu, HAR czy po zmianie domeny', pos: 'bl' }],
      }),
    },
    { into: 'fade', scene: RESULTS },
    { into: 'fade', scene: { kind: 'end', dur: 4.5 } },
  ],
};

export const CUTS: Cut[] = [A, B, C];
