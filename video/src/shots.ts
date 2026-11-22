/**
 * The shot list: what each capture does in the browser.
 * Responsibility: one entry per public/captures/<id>.mp4. Steps click by visible text, the
 * way a viewer would, so a renamed button fails loudly instead of recording the wrong
 * screen. label() names moments the scenes trim to (manifest.json `marks`, in seconds).
 * Idempotency: n/a — data. Only scripts/capture.ts runs `run` (Node, not the bundle).
 */
import type { Locator, Page } from 'playwright';

type Target = string | RegExp | Locator;

/** What a shot can do; implemented by scripts/capture.ts. */
export interface Ctl {
  readonly page: Page;
  readonly take: boolean;
  goto(path: string): Promise<void>;
  mark(): Promise<void>;
  label(name: string): void;
  wait(ms: number): Promise<void>;
  until(cond: () => Promise<boolean>, capMs?: number): Promise<void>;
  untilVisible(t: Target, capMs?: number): Promise<void>;
  moveTo(t: Target, ms?: number, at?: { x?: number; y?: number }): Promise<void>;
  click(t?: Target, ms?: number, at?: { x?: number; y?: number }): Promise<void>;
  type(text: string, perCharMs?: number): Promise<void>;
  press(key: string): Promise<void>;
  scrollBy(dy: number, ms?: number): Promise<void>;
  scrollTo(t: Target, ms?: number, frac?: number): Promise<void>;
  hideCursor(): Promise<void>;
}

export interface Shot {
  id: string;
  /** Run an unrecorded warm-up pass first (default true). */
  warm?: boolean;
  /** 'virtual': record the SSE stream in warm-up and replay it on the page clock in the take. */
  sse?: 'virtual';
  /** Load extension/ unpacked (persistent context). */
  extension?: boolean;
  parked?: boolean;
  run(c: Ctl): Promise<void>;
}

export const SHOTS: Shot[] = [
  {
    // Sprawdź: one-click sample → six bots → verdict → page with outlines → Graf
    id: 'sprawdz',
    async run(c) {
      await c.goto('/');
      await c.mark();
      await c.wait(1400);
      await c.moveTo(/Wiem, kto strzelał/, 1000);
      await c.wait(400);
      c.label('click');
      await c.click();
      c.label('analysis');
      await c.untilVisible(/Dołącza do kampanii/, 45_000);
      c.label('verdict');
      await c.wait(2600);
      await c.scrollTo(c.page.locator('figcaption', { hasText: 'Strona docelowa' }).first(), 1300, 0.1);
      c.label('outlines');
      await c.wait(3400);
      c.label('end');
    },
  },
  {
    // Raport → Graf on the incident page of a fresh check of the same sample. (A finished
    // job's stream expires on the server while a slow take is still recording, so the
    // Graf switch cannot stay on the /analiza/JOB-… page.)
    id: 'graf',
    warm: false,
    async run(c) {
      await c.goto('/');
      await c.click(/Wiem, kto strzelał/, 1);
      await c.untilVisible(/Dołącza do kampanii/, 60_000);
      const inc = /INC-U[0-9A-F]+/.exec(await c.page.locator('main').innerText())?.[0];
      if (!inc) throw new Error('no incident id on the report');
      await c.goto(`/analiza/${inc}`);
      await c.mark();
      await c.wait(1200);
      await c.click(c.page.getByRole('button', { name: 'Graf', exact: true }), 800);
      c.label('graf');
      await c.wait(500);
      await c.scrollTo(c.page.getByText(/^Kliknij węzeł/).first(), 1000, 0.05);
      await c.wait(1500);
      // graph nodes are SVG buttons: "Osoba: …", "Kampania: …", "Operator: …"
      await c.click(c.page.getByRole('button', { name: /^Osoba: Rafał Brzoska/ }), 900, { y: 0.3 });
      c.label('person');
      await c.wait(2800);
      await c.click(c.page.getByRole('button', { name: /^Kampania: KMP-001/ }), 900, { y: 0.3 });
      c.label('campaign');
      await c.wait(2800);
      await c.click(c.page.getByRole('button', { name: /^Operator: OP-01/ }), 900, { y: 0.3 });
      c.label('operator');
      await c.wait(2800);
      c.label('end');
    },
  },
  {
    // New-campaign case: the sample no campaign explains
    id: 'nowa',
    async run(c) {
      await c.goto('/');
      await c.mark();
      await c.wait(600);
      await c.click(/Poland Invest Summit 2026/, 900);
      c.label('analysis');
      await c.untilVisible('Nie pasuje do żadnej z 9 kampanii', 45_000);
      c.label('verdict');
      await c.wait(2400);
      await c.scrollTo(c.page.getByText('Nie pasuje do żadnej z 9 kampanii'), 1200, 0.18);
      c.label('why');
      await c.moveTo(c.page.getByText(/Różna branża/), 900);
      await c.wait(3600);
      c.label('end');
    },
  },
  {
    // Kampanie → KMP-001 → Zgłoszenie (prepared and exported, never sent)
    id: 'kampanie',
    async run(c) {
      await c.goto('/kampanie');
      await c.mark();
      await c.wait(2400);
      c.label('list');
      await c.click(c.page.getByText(/^KMP-001/).first(), 1000);
      await c.untilVisible('Zgłoś całą kampanię', 20_000);
      c.label('campaign');
      await c.wait(1800);
      await c.scrollBy(520, 1100);
      await c.wait(2200);
      await c.scrollBy(-520, 900);
      await c.click('Zgłoś całą kampanię', 900);
      await c.untilVisible('Zgłoś całą kampanię naraz', 20_000);
      c.label('package');
      await c.wait(2400);
      await c.moveTo('Pobierz STIX', 900);
      await c.wait(500);
      await c.click('Pobierz PDF', 700);
      c.label('pdf');
      await c.wait(2400);
      c.label('end');
    },
  },
  {
    // Śledztwa: the recorded White Rabbit run (?replay=live), tree grows on the page clock
    id: 'sledztwo',
    sse: 'virtual',
    async run(c) {
      await c.goto('/sledztwa/INV-103?replay=live');
      await c.mark();
      c.label('start');
      await c.until(
        async () =>
          (await c.page.evaluate('window.__sseDone === true || (window.__sseLog||[]).some(e => e.type === "investigation.done")')) === true,
        45_000,
      );
      c.label('done');
      await c.wait(3000);
      await c.scrollBy(420, 1200);
      await c.wait(3000);
      c.label('end');
    },
  },
  {
    // Live capture of a link (example.com only; nothing from the scam corpus is opened directly)
    id: 'live',
    warm: false,
    async run(c) {
      await c.goto('/');
      await c.mark();
      await c.wait(500);
      await c.click(c.page.getByPlaceholder(/https/), 800);
      await c.type('https://example.com', 55);
      await c.wait(300);
      await c.click(c.page.getByRole('button', { name: /^Sprawdź/ }).last(), 700);
      c.label('analysis');
      await c.untilVisible('Nie pasuje do żadnej z 9 kampanii', 60_000);
      c.label('verdict');
      await c.wait(2200);
      await c.scrollTo(c.page.locator('figcaption', { hasText: 'Strona docelowa' }).first(), 1100, 0.1);
      await c.wait(2400);
      c.label('end');
    },
  },
  {
    // Lab: 0 wrong links, τ sweep, stress test
    id: 'lab',
    warm: false,
    async run(c) {
      await c.goto('/lab');
      await c.mark();
      await c.wait(2600);
      c.label('scroll');
      await c.scrollTo(c.page.getByText('Próg τ: jakość przy różnych progach'), 1400, 0.1);
      await c.wait(1200);
      await c.moveTo(c.page.getByText('τ = 5 (wybrany)'), 900);
      await c.wait(1200);
      await c.moveTo(c.page.getByText('pełna rotacja'), 900);
      await c.wait(2400);
      c.label('end');
    },
  },
  {
    // The browser extension badge on the app's own demo feed
    id: 'extension',
    extension: true,
    warm: false,
    async run(c) {
      await c.goto('/demo/feed-real.html');
      await c.page.locator('[data-trop-overlay]').first().waitFor({ timeout: 20_000 });
      await c.mark();
      await c.wait(800);
      await c.scrollTo(c.page.locator('#post-scam'), 1200, 0.06);
      c.label('badge');
      await c.wait(1600);
      await c.click(c.page.getByRole('button', { name: 'Dlaczego?' }), 900);
      c.label('why');
      await c.wait(3600);
      c.label('end');
    },
  },
];
