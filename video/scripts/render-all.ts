/**
 * Renders every cut in src/timeline.ts CUTS to out/<id>.mp4 (CPU, nice -n 10).
 * Positional arguments pick cuts; --flags pass through to `remotion render`.
 * Idempotency: overwrites out/<id>.mp4 for each cut rendered.
 */
import { execFileSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { CUTS } from '../src/timeline.ts';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const flags = args.filter((a) => a.startsWith('--'));
const picked = args.filter((a) => !a.startsWith('--'));
const cuts = picked.length > 0 ? CUTS.filter((c) => picked.includes(c.id)) : CUTS;
for (const cut of cuts) {
  const out = join('out', `${cut.id}.mp4`);
  process.stdout.write(`▶ ${cut.id}: ${cut.purpose}\n`);
  const t0 = Date.now();
  execFileSync('nice', ['-n', '10', 'pnpm', 'exec', 'remotion', 'render', 'src/index.ts', cut.id, out, '--concurrency=6', '--log=error', ...flags], {
    cwd: root,
    stdio: ['ignore', 'inherit', 'inherit'],
  });
  process.stdout.write(`  ✓ ${out} in ${((Date.now() - t0) / 1000).toFixed(0)} s\n`);
}
