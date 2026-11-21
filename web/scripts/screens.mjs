// Playwright screenshots of every screen (for the lead / docs).
// Usage: BASE=http://127.0.0.1:13000 OUT=../data/screens/ws3 node scripts/screens.mjs [name ...]
// CHROME=/path/to/chrome overrides the browser binary.
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE || 'http://127.0.0.1:13000';
const OUT = path.resolve(process.env.OUT || '../data/screens/ws3');
fs.mkdirSync(OUT, { recursive: true });

// [name, path, waitMs | async (page) => void, viewport?]
const SHOTS = [
  ['01-sprawdz', '/', 2500],
  ['02-analiza', '/', async (p) => { await p.waitForTimeout(3000); await p.click('button[type=submit]'); await p.waitForURL(/analiza/); await p.waitForTimeout(9000); }],
  ['03-raport', '/', async (p) => { await p.waitForTimeout(3000); await p.click('button[type=submit]'); await p.waitForURL(/analiza/); await p.waitForSelector('#rp-verdict', { timeout: 60000 }); await p.waitForTimeout(1500); }],
  ['02-analiza-offline', '/analiza/local-zamach-shot', 6000],
  ['04-graf', '/analiza/INC-24817?view=graf', 3500],
  ['04a-graf-domena', '/analiza/INC-24817?view=graf&focus=morvanta.click', 2500],
  ['04b-graf-slad', '/analiza/INC-24817?view=graf&focus=trace%3Akit', 2500],
  ['04c-graf-osoba', '/analiza/INC-24817?view=graf&focus=person%3AJan%20Kowalski', 2500],
  ['04d-graf-material', '/analiza/INC-24817?view=graf&focus=INC-24702', 2500],
  ['11-nowa', '/analiza/local-nowa-shot', 16000],
  ['12-niepewne', '/analiza/local-niepewne-shot', 14000],
  ['13-blad', '/analiza/local-blad-shot', 22000],
  ['14-slad', '/slad/osoba/Jan%20Kowalski', 3000],
  ['05-kampanie', '/kampanie', 2500],
  ['06-kampania', '/kampanie/KMP-017', 3000],
  ['07-zgloszenie', '/kampanie/KMP-017/zgloszenie', 2500],
  ['08-scal', '/kampanie/scal?a=KMP-017&b=KMP-043&offline=1', 2500],
  ['09-sledztwo', '/sledztwa/INV-7', 7500],
  ['10-sledztwo-koniec', '/sledztwa/INV-7?koniec=1', 3000],
  ['15-lab', '/lab', 2500],
  ['01-sprawdz-phone', '/', 2500, { width: 390, height: 844 }],
  ['03-raport-phone', '/analiza/INC-24817', 3000, { width: 390, height: 844 }],
  ['05-kampanie-phone', '/kampanie', 2500, { width: 390, height: 844 }],
];

// SET=real: the jury path against the real API (ZIP=<path to a DANE item zipped>)
const ZIP = process.env.ZIP;
const upload = async (p) => { await p.waitForTimeout(2500); await p.setInputFiles('input[accept*=".zip"]', ZIP); await p.click('button[type=submit]'); await p.waitForURL(/analiza/); };
const REAL = [
  ['r01-sprawdz', '/', 4000],
  ['r02-analiza', '/', async (p) => { await upload(p); await p.waitForTimeout(3500); }],
  ['r03-raport', '/', async (p) => { await upload(p); await p.waitForSelector('#rp-verdict', { timeout: 60000 }); await p.waitForTimeout(1500); }],
  ['r04-graf', '/', async (p) => { await upload(p); await p.waitForSelector('#rp-verdict', { timeout: 60000 }); await p.click('button:has-text("Graf")'); await p.waitForTimeout(2500); }],
  ['r04a-graf-wezel', '/', async (p) => { await upload(p); await p.waitForSelector('#rp-verdict', { timeout: 60000 }); await p.click('button:has-text("Graf")'); await p.waitForTimeout(1200); await p.locator('.mv button').first().click(); await p.waitForTimeout(3000); }],
  ['r04b-graf-wezel2', '/', async (p) => { await upload(p); await p.waitForSelector('#rp-verdict', { timeout: 60000 }); await p.click('button:has-text("Graf")'); await p.waitForTimeout(1200); await p.locator('.mv button').nth(1).click(); await p.waitForTimeout(3000); }],
  ['r03b-raport-p1', '/analiza/p1', 4000],
  ['r05-kampanie', '/kampanie', 3000],
  ['r06-kampania', '/kampanie/KMP-001', 4000],
  ['r07-zgloszenie', '/kampanie/KMP-001/zgloszenie', 4000],
  ['r09-sledztwo', '/sledztwa?seed=dorquesio.click&kampania=KMP-001', async (p) => { await p.waitForURL(/sledztwa\/[^?]/, { timeout: 30000 }); await p.waitForTimeout(8000); }],
  ['r09b-sledztwa', '/sledztwa', 3000],
  ['r14-slad', '/slad/osoba/rafa%C5%82%20brzoska', 4000],
  ['r14b-slad-domena', '/slad/domena/dorquesio.click', 4000],
  ['r15-lab', '/lab', 4000],
  ['r16-sprawdz-public', '/sprawdz', 4000],
  ['r01-sprawdz-phone', '/', 4000, { width: 390, height: 844 }],
  ['r03-raport-phone', '/analiza/p1', 4000, { width: 390, height: 844 }],
];
const only = process.argv.slice(2);
const exe = process.env.CHROME || [
  `${process.env.HOME}/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome`,
].find((p) => fs.existsSync(p));
const browser = await chromium.launch({ executablePath: exe, args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const jobs = (process.env.SET === 'real' ? REAL : SHOTS).filter(([n]) => !only.length || only.some((o) => n.startsWith(o)));
for (const [name, url, wait, vp] of jobs) {
  const page = await browser.newPage({ viewport: vp || { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(BASE + url, { waitUntil: 'domcontentloaded' });
  try { if (typeof wait === 'function') await wait(page); else await page.waitForTimeout(wait); } catch (e) { errors.push('wait: ' + e.message.split('\n')[0]); }
  try { await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: true, timeout: 60000 }); } catch (e) { errors.push('shot: ' + e.message.split('\n')[0]); }
  console.log(name, errors.length ? 'ERR ' + errors.join(' | ') : 'ok');
  await page.close();
}
await browser.close();
