/**
 * Renders the six jelly bots (the app's own WebGL overlay) to public/bots/<key>.png at 3×,
 * cropped from the bot chips of the investigation page. Used as caption avatars.
 * Idempotency: overwrites public/bots/*.png.
 */
import { chromium } from 'playwright';
const NAMES: Record<string, string> = { sedzia: 'Sędzia', notariusz: 'Notariusz', tropiciel: 'Tropiciel', zwiadowca: 'Zwiadowca', archiwista: 'Archiwista', czytelnik: 'Czytelnik' };
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 3 });
await p.goto('https://trop.b.solvro.pl/sledztwa/INV-103?replay=live');
await p.waitForTimeout(4000);
for (const [key, name] of Object.entries(NAMES)) {
  const label = p.getByText(name, { exact: true }).first();
  const box = await label.boundingBox();
  if (!box) { console.log('no', name); continue; }
  // the bot sits left of its name inside the chip
  await p.screenshot({ path: `public/bots/${key}.png`, clip: { x: box.x - 47, y: box.y - 6, width: 42, height: 42 } });
  console.log(key, JSON.stringify(box));
}
await b.close();
