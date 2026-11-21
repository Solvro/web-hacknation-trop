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
        shot: 'sprawdz', from: 'start', to: 'analysis', dur: 4.6,
        cam: [{ at: 0, x: 960, y: 520, z: 1.25 }, { at: 3.6, x: 760, y: 640, z: 1.35 }],
        caps: [{ at: 0.4, until: 4.3, text: 'Sprawdź: link, zrzut, wideo, HAR albo cały folder', sub: 'tu jeden klik: przykładowy materiał z danych', pos: 'tr' }],
      }),
    },
    {
      scene: clip({
        shot: 'sprawdz', from: 'analysis', to: 'verdict', dur: 12,
        cam: [{ at: 0, ...FULL }, { at: 11.5, ...FULL }],
        caps: [
          { at: 0.3, until: 3.8, text: 'Sześć botów-detektywów pracuje po kolei', sub: 'Zwiadowca · Tropiciel · Czytelnik · Notariusz · Archiwista · Sędzia', pos: 'bl' },
          { at: 4.1, until: 7.6, bot: 'tropiciel', text: 'Piksele, konto w zestawie strony, typ landingu', sub: 'każdy ślad z rzadkością: ile materiałów go ma', pos: 'bl' },
          { at: 7.9, until: 11.8, bot: 'sedzia', text: 'Najbliższe kampanie liczą się na żywo', pos: 'bl' },
        ],
      }),
    },
    {
      scene: clip({
        shot: 'sprawdz', from: 'verdict', to: 'outlines', dur: 5,
        cam: [{ at: 0, ...FULL }],
        caps: [{ at: 0.3, until: 4.8, text: 'Werdykt: dołącza do kampanii KMP-001 · pewność 0.99', sub: 'operator OP-01, następna kampania tylko 0.01', pos: 'br' }],
      }),
    },
    {
      scene: clip({
        shot: 'sprawdz', from: 'outlines', to: 'graf', dur: 4.6,
        cam: [{ at: 0, ...FULL }],
        caps: [{ at: 0.2, until: 4.4, text: 'Przechwycona strona: obrysy pokazują, gdzie boty znalazły dowody', pos: 'bl' }],
      }),
    },
    {
      scene: clip({
        shot: 'sprawdz', from: 'graf', to: 'end', dur: 8,
        cam: [{ at: 0, ...FULL }],
        caps: [
          { at: 0.3, until: 3.9, text: 'Graf: od materiału przez dowody do kampanii', pos: 'tr' },
          { at: 4.2, until: 7.8, text: 'Klik w węzeł: z czym jeszcze łączy się ten ślad', sub: 'Lander z zestawu strony wspólny dla 5 materiałów', pos: 'tr' },
        ],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'nowa', from: 'analysis+0.2', to: 'end', dur: 10,
        cam: [{ at: 0, ...FULL }],
        caps: [
          { at: 0.3, until: 4.6, text: 'Materiał, którego żadna kampania nie tłumaczy', sub: '„Poland Invest Summit 2026”', pos: 'bl' },
          { at: 5.0, until: 9.8, bot: 'sedzia', text: 'Nowa kampania (kandydat), bez wymuszania', sub: 'żeby dołączyć, potrzeba co najmniej 0.80; najbliższa ma 0.01', pos: 'bl' },
        ],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'live', from: 'start+0.4', to: 'end', dur: 9,
        cam: [{ at: 0, ...FULL }],
        caps: [
          { at: 0.3, until: 4.4, bot: 'zwiadowca', text: 'Dowolny link: strona przechwycona w piaskownicy', sub: 'formularzy nie wysyłamy', pos: 'bl' },
          { at: 4.7, until: 8.8, text: 'example.com: nic wspólnego z kampaniami, więc nic nie dołącza', pos: 'bl' },
        ],
      }),
    },
    { into: 'fade', scene: LEVELS },
    {
      into: 'fade',
      scene: clip({
        shot: 'kampanie', from: 'start', to: 'package', dur: 11,
        cam: [{ at: 0, ...FULL }],
        caps: [
          { at: 0.3, until: 3.4, text: 'Kampanie pogrupowane według operatorów', sub: 'i Oracle: nowe domeny pasujące do znanych zestawów, zanim pojawi się reklama', pos: 'bl' },
          { at: 3.8, until: 10.8, text: 'KMP-001: 6 materiałów · 5 domen · 4 reklamodawców', sub: '0 z 5 domen na liście CERT PL', pos: 'bl' },
        ],
      }),
    },
    {
      scene: clip({
        shot: 'kampanie', from: 'package', to: 'end', dur: 7,
        cam: [{ at: 0, ...FULL }],
        caps: [
          { at: 0.3, until: 6.8, text: 'Jedno zgłoszenie na całą kampanię', sub: 'Meta DSA art. 16 · CERT PL · STIX 2.1 · PDF. Przygotowane i eksportowane, nic nie wychodzi samo.', pos: 'bl' },
        ],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'sledztwo', from: 'start', to: 'end', dur: 13,
        cam: [{ at: 0, ...FULL }],
        caps: [
          { at: 0.3, until: 4.8, text: 'Śledztwa: White Rabbit startuje od jednej domeny', sub: 'certyfikaty, rejestracje, reklamy, urlscan, lista CERT PL', pos: 'bl' },
          { at: 5.2, until: 12.8, text: 'Graf rośnie z każdym krokiem agenta', sub: 'nagranie prawdziwego przebiegu (replay)', pos: 'bl' },
        ],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'extension', from: 'start', to: 'end', dur: 7,
        cam: [{ at: 0, ...FULL }],
        caps: [{ at: 0.3, until: 6.8, text: 'Wtyczka do przeglądarki: znacznik na reklamie ze znanej kampanii', sub: 'z przeglądarki wychodzi tylko anonimowy odcisk reklamy', pos: 'bl' }],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'lab', from: 'start', to: 'end', dur: 7.5,
        cam: [{ at: 0, ...FULL }],
        caps: [{ at: 0.3, until: 7.3, text: 'Lab: 0 błędnych przypisań', sub: 'przy każdym progu τ i w każdym teście odporności', pos: 'br' }],
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
        shot: 'sprawdz', from: 'click-0.6', to: 'verdict', dur: 8,
        cam: [{ at: 0, ...FULL }],
        caps: [{ at: 0.2, until: 7.8, text: 'Wrzuć reklamę. Sześć botów szuka śladów.', pos: 'bl' }],
      }),
    },
    {
      scene: clip({
        shot: 'sprawdz', from: 'verdict', to: 'graf', dur: 6,
        cam: [{ at: 0, ...FULL }],
        caps: [{ at: 0.2, until: 5.8, text: 'Dołącza do KMP-001 · pewność 0.99', sub: 'z dowodami na przechwyconej stronie', pos: 'br' }],
      }),
    },
    {
      scene: clip({
        shot: 'sprawdz', from: 'graf+0.5', to: 'end', dur: 5,
        cam: [{ at: 0, ...FULL }],
        caps: [{ at: 0.2, until: 4.8, text: 'Każde powiązanie da się kliknąć i sprawdzić', pos: 'tr' }],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'nowa', from: 'verdict-0.5', to: 'end', dur: 5,
        cam: [{ at: 0, ...FULL }],
        caps: [{ at: 0.2, until: 4.8, text: 'Nic nie pasuje? Nowa kampania, bez zgadywania.', pos: 'bl' }],
      }),
    },
    { into: 'fade', scene: LEVELS },
    {
      into: 'fade',
      scene: clip({
        shot: 'kampanie', from: 'campaign', to: 'end', dur: 10,
        cam: [{ at: 0, ...FULL }],
        caps: [
          { at: 0.2, until: 4.6, text: '6 reklam, 5 domen, 4 reklamodawców: jedna kampania', pos: 'bl' },
          { at: 4.9, until: 9.8, text: 'Jedno zgłoszenie: DSA, CERT PL, STIX', sub: 'przygotowane do eksportu, nic nie wychodzi samo', pos: 'bl' },
        ],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'sledztwo', from: 'start', to: 'end', dur: 8,
        cam: [{ at: 0, ...FULL }],
        caps: [{ at: 0.2, until: 7.8, text: 'Agent idzie po śladach do reszty kampanii', pos: 'bl' }],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'extension', from: 'badge-0.4', to: 'end', dur: 5,
        cam: [{ at: 0, ...FULL }],
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
        cam: [{ at: 0, ...FULL }],
        caps: [{ at: 0.3, until: 8.8, text: 'Fałszywa Gazeta.pl: boty zbierają ślady', pos: 'bl' }],
      }),
    },
    {
      scene: clip({
        shot: 'sprawdz', from: 'verdict', to: 'graf', dur: 7,
        cam: [{ at: 0, ...FULL }],
        caps: [{ at: 0.3, until: 6.8, text: 'To nie pierwsza taka reklama: KMP-001 · pewność 0.99', sub: 'ten sam zestaw strony, piksel i bramka CAPI', pos: 'br' }],
      }),
    },
    {
      scene: clip({
        shot: 'sprawdz', from: 'graf+0.5', to: 'end', dur: 6,
        cam: [{ at: 0, ...FULL }],
        caps: [{ at: 0.3, until: 5.8, text: 'Dlaczego? Każdy dowód z wagą i rzadkością', pos: 'tr' }],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'sledztwo', from: 'start', to: 'end', dur: 10,
        cam: [{ at: 0, ...FULL }],
        caps: [{ at: 0.3, until: 9.8, text: 'Od jednej domeny do całej infrastruktury', sub: 'White Rabbit, na żywo w grafie', pos: 'bl' }],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'kampanie', from: 'package-0.3', to: 'end', dur: 7,
        cam: [{ at: 0, ...FULL }],
        caps: [{ at: 0.3, until: 6.8, text: 'Jedno zgłoszenie zamiast sześciu', sub: 'DSA art. 16 · CERT PL · STIX 2.1. Nic nie wychodzi samo.', pos: 'bl' }],
      }),
    },
    {
      into: 'slide',
      scene: clip({
        shot: 'lab', from: 'start', to: 'end', dur: 6,
        cam: [{ at: 0, ...FULL }],
        caps: [{ at: 0.3, until: 5.8, text: 'I bez fałszywych powiązań', sub: '0 błędnych przypisań w każdym teście', pos: 'br' }],
      }),
    },
    { into: 'fade', scene: RESULTS },
    { into: 'fade', scene: { kind: 'end', dur: 4.5 } },
  ],
};

export const CUTS: Cut[] = [A, B, C];
