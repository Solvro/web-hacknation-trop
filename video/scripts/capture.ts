/**
 * Records the live TROP app into public/captures/<shot>.mp4 at exactly 60 fps.
 *
 * Responsibility: drive https://trop.b.solvro.pl (or --origin) through each shot in
 * src/shots.ts the way a viewer would (visible cursor, clicks by visible text, smooth
 * scrolls) and record it in VIRTUAL TIME: from a shot's mark() the page clock
 * (performance.now, Date.now, rAF, timers) is frozen and stepped 1/60 s per screenshot.
 * The analysis screen paces its SSE events with setTimeout, so the bots run at their
 * designed speed whatever the machine does. CSS animations run on the compositor clock;
 * their playback rate is matched to the measured capture speed.
 *
 * Usage: pnpm capture [shot…] [--origin URL] [--no-warm]
 * Idempotency: overwrites public/captures/<shot>.mp4 and that shot's manifest entry.
 */
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { homedir, tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { type BrowserContext, type CDPSession, chromium, type Locator, type Page } from 'playwright';
import { SHOTS, type Ctl, type Shot } from '../src/shots.ts';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(root, 'public', 'captures');
const MANIFEST = join(root, 'src', 'captures.json');
const args = process.argv.slice(2);
const flag = (n: string) => {
  const i = args.indexOf(n);
  return i >= 0 ? args[i + 1] : undefined;
};
const ORIGIN = flag('--origin') ?? 'https://trop.b.solvro.pl';
const NO_WARM = args.includes('--no-warm');
const picked = args.filter((a, i) => !a.startsWith('--') && args[i - 1] !== '--origin');
const EXT_DIR = join(root, '..', 'extension');

const OUT_FPS = 60;
const FRAME_MS = 1000 / OUT_FPS;
const VIEW = { width: 1600, height: 900 };
const DSF = 1.2; // 1920×1080 frames with the UI at a legible size

// --- page-side helpers (strings: esbuild's __name() wrappers do not exist in the page) ---
const VIRTUAL_TIME = `
(() => {
  const real = {
    raf: window.requestAnimationFrame.bind(window), caf: window.cancelAnimationFrame.bind(window),
    perfNow: performance.now.bind(performance), dateNow: Date.now,
    setTimeout: window.setTimeout.bind(window), clearTimeout: window.clearTimeout.bind(window),
    setInterval: window.setInterval.bind(window), clearInterval: window.clearInterval.bind(window),
  };
  const vt = { on: false, now: 0, perfBase: 0, dateBase: 0, raf: new Map(), timers: new Map(), seq: 1e7 };
  window.__vt = vt;
  performance.now = () => (vt.on ? vt.now : real.perfNow());
  Date.now = () => (vt.on ? vt.dateBase + (vt.now - vt.perfBase) : real.dateNow());
  const RealDate = Date;
  window.requestAnimationFrame = (cb) => { if (!vt.on) return real.raf(cb); const id = ++vt.seq; vt.raf.set(id, cb); return id; };
  window.cancelAnimationFrame = (id) => (vt.raf.delete(id) ? undefined : real.caf(id));
  const addTimer = (fn, ms, args, every) => { const id = ++vt.seq; vt.timers.set(id, { at: vt.now + Math.max(0, Number(ms) || 0), fn, args, every }); return id; };
  window.setTimeout = (fn, ms, ...args) => (vt.on ? addTimer(fn, ms, args, 0) : real.setTimeout(fn, ms, ...args));
  window.setInterval = (fn, ms, ...args) => (vt.on ? addTimer(fn, ms, args, Math.max(1, Number(ms) || 0)) : real.setInterval(fn, ms, ...args));
  window.clearTimeout = (id) => (vt.timers.delete(id) ? undefined : real.clearTimeout(id));
  window.clearInterval = (id) => (vt.timers.delete(id) ? undefined : real.clearInterval(id));
  const call = (fn, args) => { try { typeof fn === 'function' ? fn(...args) : (0, eval)(String(fn)); } catch (e) { console.error(e); } };
  vt.start = () => { vt.perfBase = real.perfNow(); vt.dateBase = real.dateNow(); vt.now = vt.perfBase; vt.on = true; };
  vt.step = (ms) => {
    const target = vt.now + ms;
    for (let guard = 0; guard < 10000; guard++) {
      let next = null;
      for (const [id, t] of vt.timers) if (t.at <= target && (next === null || t.at < next[1].at)) next = [id, t];
      if (next === null) break;
      const [id, t] = next;
      vt.now = Math.max(vt.now, t.at);
      if (t.every > 0) t.at += t.every; else vt.timers.delete(id);
      call(t.fn, t.args);
    }
    vt.now = target;
    const due = [...vt.raf.values()];
    vt.raf.clear();
    for (const cb of due) call(cb, [vt.now]);
  };
})();
`;

/** A visible cursor (headless screenshots have none) with a click ring. */
const CURSOR = `
(() => {
  const install = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div');
    c.id = '__cur';
    c.style.cssText = 'position:fixed;left:0;top:0;width:28px;height:28px;z-index:2147483647;pointer-events:none;transform:translate(-100px,-100px);';
    c.innerHTML = '<svg width="28" height="28" viewBox="0 0 28 28"><path d="M5 3 L5 22 L10 17.5 L13.5 25 L17 23.5 L13.6 16 L20 16 Z" fill="#0A0A0A" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    const ring = document.createElement('div');
    ring.id = '__ring';
    ring.style.cssText = 'position:fixed;left:0;top:0;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;border:3px solid #F97316;z-index:2147483646;pointer-events:none;opacity:0;';
    document.documentElement.appendChild(ring);
    document.documentElement.appendChild(c);
  };
  window.__cursor = (x, y, show) => {
    install();
    const c = document.getElementById('__cur');
    c.style.transform = 'translate(' + (x - 5) + 'px,' + (y - 3) + 'px)';
    c.style.display = show === false ? 'none' : 'block';
    let chip = document.getElementById('__chip');
    if (window.__chipText && !chip) {
      chip = document.createElement('div');
      chip.id = '__chip';
      chip.style.cssText = 'position:fixed;left:0;top:0;z-index:2147483645;pointer-events:none;background:#fff;border:1px solid #ddd;border-radius:12px;padding:8px 14px;font:500 14px system-ui,sans-serif;color:#0a0a0a;box-shadow:0 8px 24px rgba(0,0,0,.18);white-space:nowrap;';
      document.documentElement.appendChild(chip);
    }
    if (chip) {
      chip.textContent = window.__chipText || '';
      chip.style.display = window.__chipText ? 'block' : 'none';
      chip.style.transform = 'translate(' + (x + 18) + 'px,' + (y + 14) + 'px) rotate(-3deg)';
    }
  };
  window.__ring = (x, y, p) => {
    install();
    const r = document.getElementById('__ring');
    r.style.left = x + 'px'; r.style.top = y + 'px';
    r.style.opacity = p >= 1 ? '0' : String(0.9 * (1 - p));
    r.style.transform = 'scale(' + (0.4 + p * 1.1) + ')';
  };
})();
`;

/** Logs every SSE event with its time since the stream opened (warm-up pass). */
const RECORD_SSE = `
(() => {
  const R = window.EventSource;
  if (!R) return;
  window.__sseLog = [];
  window.EventSource = function (url, opts) {
    const es = new R(url, opts);
    const t0 = performance.now();
    const add = es.addEventListener.bind(es);
    const seen = new Set();
    const rec = (type) => { if (seen.has(type)) return; seen.add(type); add(type, (m) => window.__sseLog.push({ t: performance.now() - t0, type, data: m.data })); };
    rec('message');
    es.addEventListener = (type, fn, o) => { rec(type); return add(type, fn, o); };
    return es;
  };
})();
`;

/** Replays a recorded SSE log on the page clock (take pass), so it follows virtual time. */
const fakeSse = (log: unknown[]) => `
(() => {
  const LOG = ${JSON.stringify(log)};
  const R = window.EventSource;
  window.EventSource = function (url, opts) {
    if (!/\\/stream/.test(String(url))) return new R(url, opts);
    const self = { url: String(url), readyState: 1, onmessage: null, onerror: null, onopen: null, L: {} };
    self.addEventListener = (t, fn) => { (self.L[t] = self.L[t] || []).push(fn); };
    self.removeEventListener = (t, fn) => { self.L[t] = (self.L[t] || []).filter((f) => f !== fn); };
    self.close = () => { self.readyState = 2; };
    const t0 = performance.now();
    let i = 0;
    const tick = () => {
      if (self.readyState === 2) return;
      const el = performance.now() - t0;
      while (i < LOG.length && LOG[i].t <= el) {
        const e = LOG[i++];
        const m = new MessageEvent(e.type, { data: e.data });
        for (const fn of self.L[e.type] || []) fn(m);
        if (e.type === 'message' && self.onmessage) self.onmessage(m);
      }
      if (i < LOG.length) setTimeout(tick, 16); else window.__sseDone = true;
    };
    setTimeout(tick, 0);
    return self;
  };
})();
`;

/** Resolves once no request (ignoring SSE streams) has been in flight for `quietMs`. */
function quietWatcher(page: Page): (cap: number, quietMs?: number) => Promise<void> {
  let inflight = 0;
  let lastChange = Date.now();
  const longLived = (url: string, type: string) => type === 'eventsource' || /\/stream(\?|$)/.test(url);
  page.on('request', (r) => {
    if (longLived(r.url(), r.resourceType())) return;
    inflight++;
    lastChange = Date.now();
  });
  const done = (r: { url(): string; resourceType(): string }) => {
    if (longLived(r.url(), r.resourceType())) return;
    inflight = Math.max(0, inflight - 1);
    lastChange = Date.now();
  };
  page.on('requestfinished', done);
  page.on('requestfailed', done);
  return async (cap, quietMs = 0) => {
    const start = Date.now();
    while (Date.now() - start < cap) {
      if (inflight === 0 && Date.now() - lastChange >= quietMs) return;
      await page.waitForTimeout(25);
    }
  };
}

const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

type Target = string | RegExp | Locator;

class Driver implements Ctl {
  private frames = 0;
  private recording = false;
  private mx = VIEW.width * 0.62;
  private my = VIEW.height * 0.7;
  private frameMsAvg = 120;
  private sinceRate = 0;
  readonly marks: Record<string, number> = {};

  constructor(
    readonly page: Page,
    private readonly cdp: CDPSession,
    private readonly dir: string,
    private readonly quiet: (cap: number, quietMs?: number) => Promise<void>,
    readonly take: boolean,
  ) {}

  get origin(): string {
    return ORIGIN;
  }

  loc(t: Target): Locator {
    if (typeof t !== 'string' && !(t instanceof RegExp)) return t;
    const p = this.page;
    const byText = p.getByText(t, { exact: typeof t === 'string' });
    const byRole = p.getByRole('button', { name: t, exact: typeof t === 'string' }).or(p.getByRole('link', { name: t, exact: typeof t === 'string' }));
    return byRole.or(byText).first();
  }

  async goto(path: string): Promise<void> {
    if (this.recording) throw new Error('goto after mark reloads the page and loses the clock');
    await this.page.goto(ORIGIN + path, { waitUntil: 'domcontentloaded' });
    await this.quiet(20_000, 800);
    await this.page.evaluate(`window.__cursor(${this.mx}, ${this.my}, true)`);
  }

  /** Starts recording (take) from here on. */
  async mark(): Promise<void> {
    if (!this.take) return;
    await this.page.evaluate(`window.__cursor(${this.mx}, ${this.my}, true)`);
    await this.page.evaluate('window.__vt.start()');
    await this.cdp.send('Animation.enable');
    this.recording = true;
  }

  /** Names the current moment of the clip (seconds), for the scene to trim to. */
  label(name: string): void {
    this.marks[name] = this.frames / OUT_FPS;
  }

  private async frame(): Promise<void> {
    const t0 = Date.now();
    await this.page.evaluate(`window.__vt.step(${FRAME_MS})`);
    await this.quiet(2_000);
    // Playwright's screenshot honours deviceScaleFactor (raw CDP returns CSS pixels here)
    const shot = await this.page.screenshot({ type: 'jpeg', quality: 90, caret: 'initial', timeout: 15_000 });
    writeFileSync(join(this.dir, `f${String(this.frames++).padStart(6, '0')}.jpg`), shot);
    // keep CSS animations (compositor clock) in step with the virtual clock
    this.frameMsAvg = this.frameMsAvg * 0.9 + (Date.now() - t0) * 0.1;
    if (++this.sinceRate >= 20) {
      this.sinceRate = 0;
      const rate = Math.max(0.02, Math.min(1, FRAME_MS / this.frameMsAvg));
      await this.cdp.send('Animation.setPlaybackRate', { playbackRate: rate }).catch(() => {});
    }
  }

  async wait(ms: number): Promise<void> {
    if (!this.recording) {
      await this.page.waitForTimeout(ms);
      return;
    }
    const n = Math.max(1, Math.round(ms / FRAME_MS));
    for (let i = 0; i < n; i++) await this.frame();
  }

  /** Records until `cond` holds (checked every 6 frames), or `capMs` of video. */
  async until(cond: () => Promise<boolean>, capMs = 30_000): Promise<void> {
    if (!this.recording) {
      const start = Date.now();
      while (Date.now() - start < Math.max(capMs, 60_000)) {
        if (await cond().catch(() => false)) return;
        await this.page.waitForTimeout(250);
      }
      throw new Error('warm-up: condition never held');
    }
    const n = Math.round(capMs / FRAME_MS);
    for (let i = 0; i < n; i++) {
      await this.frame();
      if (i % 6 === 5 && (await cond().catch(() => false))) return;
    }
    process.stdout.write(`    (until: cap ${capMs} ms reached)\n`);
  }

  /**
   * Waits for an element. While recording, the page clock only moves when frames are
   * taken, so a plain waitFor would starve timer-driven fetches: advance frames instead.
   */
  private async ensure(l: Locator, state: 'visible' | 'attached'): Promise<void> {
    const ok = () => (state === 'visible' ? l.isVisible() : l.count().then((n) => n > 0));
    if (!this.recording) {
      await l.waitFor({ state, timeout: 60_000 });
      return;
    }
    if (await ok().catch(() => false)) return;
    await this.until(ok, 25_000);
    if (!(await ok().catch(() => false))) throw new Error(`never ${state}: ${l}`);
  }

  async untilVisible(t: Target, capMs = 30_000): Promise<void> {
    const l = this.loc(t);
    await this.until(() => l.isVisible(), capMs);
  }

  private async cursorTo(x: number, y: number, ms: number): Promise<void> {
    const n = this.recording ? Math.max(1, Math.round(ms / FRAME_MS)) : 1;
    const [x0, y0] = [this.mx, this.my];
    // a slight arc reads as a hand, not a robot
    const bow = Math.min(60, Math.hypot(x - x0, y - y0) * 0.12);
    for (let i = 1; i <= n; i++) {
      const t = ease(i / n);
      const cx = x0 + (x - x0) * t + Math.sin(Math.PI * t) * bow * 0.4;
      const cy = y0 + (y - y0) * t - Math.sin(Math.PI * t) * bow;
      await this.page.mouse.move(cx, cy);
      await this.page.evaluate(`window.__cursor(${cx}, ${cy}, true)`);
      if (this.recording) await this.frame();
    }
    this.mx = x;
    this.my = y;
  }

  async moveTo(t: Target, ms = 700, at: { x?: number; y?: number } = {}, retried = false): Promise<void> {
    const l = this.loc(t);
    await this.ensure(l, 'visible');
    const box = await l.boundingBox();
    if (!box) throw new Error(`no box for ${String(t)}`);
    // keep the target on screen first (once: a target near the page end may never centre)
    const cy = box.y + box.height * (at.y ?? 0.5);
    if (!retried && (cy < 70 || cy > VIEW.height - 40)) {
      await this.scrollBy(cy - VIEW.height * 0.45, 700);
      return this.moveTo(t, ms, at, true);
    }
    await this.cursorTo(box.x + box.width * (at.x ?? 0.5), box.y + box.height * (at.y ?? 0.5), ms);
  }

  async click(t?: Target, ms = 700, at: { x?: number; y?: number } = {}): Promise<void> {
    if (t !== undefined) await this.moveTo(t, ms, at);
    await this.wait(120);
    await this.page.mouse.down();
    await this.ring(0);
    await this.page.mouse.up();
    for (let i = 1; i <= 18; i++) {
      await this.ring(i / 18);
      if (this.recording) await this.frame();
    }
    await this.ring(1);
  }

  private async ring(p: number): Promise<void> {
    await this.page.evaluate(`window.__ring(${this.mx}, ${this.my}, ${p})`);
  }

  async type(text: string, perCharMs = 55): Promise<void> {
    for (const ch of text) {
      await this.page.keyboard.type(ch);
      await this.wait(perCharMs);
    }
  }

  async press(key: string): Promise<void> {
    await this.page.keyboard.press(key);
    await this.wait(FRAME_MS);
  }

  async scrollBy(dy: number, ms = 900): Promise<void> {
    const y0 = (await this.page.evaluate('window.scrollY')) as number;
    const max = (await this.page.evaluate('document.documentElement.scrollHeight - innerHeight')) as number;
    const y1 = Math.max(0, Math.min(max, y0 + dy));
    const n = this.recording ? Math.max(1, Math.round(ms / FRAME_MS)) : 1;
    for (let i = 1; i <= n; i++) {
      await this.page.evaluate(`window.scrollTo(0, ${y0 + (y1 - y0) * ease(i / n)})`);
      if (this.recording) await this.frame();
    }
  }

  /** Scrolls so the target's top sits at `frac` of the viewport. */
  async scrollTo(t: Target, ms = 900, frac = 0.12): Promise<void> {
    const l = this.loc(t);
    await this.ensure(l, 'attached');
    const top = (await l.evaluate((e) => e.getBoundingClientRect().top)) as number;
    await this.scrollBy(top - VIEW.height * frac, ms);
  }

  async hideCursor(): Promise<void> {
    await this.page.evaluate(`window.__cursor(-100, -100, false)`);
  }

  encode(out: string): number {
    if (this.frames === 0) throw new Error('no frames recorded after mark');
    execFileSync(
      'nice',
      ['-n', '10', 'pnpm', 'exec', 'remotion', 'ffmpeg', '-y', '-loglevel', 'error', '-framerate', String(OUT_FPS),
        '-i', join(this.dir, 'f%06d.jpg'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '16', '-preset', 'medium', out],
      { cwd: root, stdio: ['ignore', 'ignore', 'inherit'] },
    );
    return this.frames / OUT_FPS;
  }
}

async function newContext(shot: Shot): Promise<BrowserContext> {
  const common = { viewport: VIEW, deviceScaleFactor: DSF, acceptDownloads: true, locale: 'pl-PL', timezoneId: 'Europe/Warsaw' };
  if (shot.extension) {
    const ud = join(tmpdir(), `trop-ext-${process.pid}`);
    rmSync(ud, { recursive: true, force: true });
    // extensions need the full Chromium build, not the headless shell
    const full = [1255, 1243, 1234].map((v) => join(homedir(), `.cache/ms-playwright/chromium-${v}/chrome-linux64/chrome`)).find((p) => existsSync(p));
    return chromium.launchPersistentContext(ud, {
      ...common,
      executablePath: process.env.CHROME ?? full,
      headless: false,
      args: ['--headless=new', `--disable-extensions-except=${EXT_DIR}`, `--load-extension=${EXT_DIR}`],
    });
  }
  const b = await chromium.launch();
  return b.newContext(common);
}

function readManifest(): Record<string, unknown> {
  return existsSync(MANIFEST) ? JSON.parse(readFileSync(MANIFEST, 'utf8')) : {};
}

async function runShot(shot: Shot): Promise<void> {
  process.stdout.write(`▶ ${shot.id}\n`);
  const ctx = await newContext(shot);
  await ctx.addInitScript(VIRTUAL_TIME);
  await ctx.addInitScript(CURSOR);
  if (shot.sse === 'virtual') await ctx.addInitScript(RECORD_SSE);
  const passes = shot.warm === false || (NO_WARM && shot.sse !== 'virtual') ? [true] : [false, true];
  for (const take of passes) {
    const page = ctx.pages()[0] ?? (await ctx.newPage());
    const cdp = await ctx.newCDPSession(page);
    const dir = join(tmpdir(), `trop-frames-${shot.id}-${process.pid}`);
    rmSync(dir, { recursive: true, force: true });
    mkdirSync(dir, { recursive: true });
    const d = new Driver(page, cdp, dir, quietWatcher(page), take);
    const t0 = Date.now();
    await shot.run(d);
    if (take) {
      const out = join(OUT, `${shot.id}.mp4`);
      const seconds = d.encode(out);
      const m = readManifest();
      m[shot.id] = { seconds, marks: d.marks, capturedAt: new Date().toISOString(), origin: ORIGIN };
      writeFileSync(MANIFEST, JSON.stringify(m, null, 2));
      process.stdout.write(`  ✓ ${seconds.toFixed(1)} s of video in ${((Date.now() - t0) / 1000).toFixed(0)} s, marks ${JSON.stringify(d.marks)}\n`);
    } else {
      process.stdout.write(`  warm-up done in ${((Date.now() - t0) / 1000).toFixed(0)} s\n`);
      if (shot.sse === 'virtual') {
        const log = (await page.evaluate('window.__sseLog || []')) as unknown[];
        process.stdout.write(`  recorded ${log.length} SSE events\n`);
        if (log.length === 0) throw new Error('no SSE events recorded in warm-up');
        await ctx.addInitScript(fakeSse(log));
      }
      await page.goto('about:blank');
    }
    rmSync(dir, { recursive: true, force: true });
    await cdp.detach().catch(() => {});
  }
  await ctx.close();
}

mkdirSync(OUT, { recursive: true });
const shots = picked.length > 0 ? SHOTS.filter((s) => picked.includes(s.id)) : SHOTS.filter((s) => !s.parked);
for (const s of shots) {
  try {
    await runShot(s);
  } catch (e) {
    process.stdout.write(`  ✗ ${s.id}: ${String(e).slice(0, 400)}\n`);
  }
}
process.exit(0);
