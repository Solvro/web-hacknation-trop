/** Prints each cut's length and every scene's start (frame and seconds), for QA. */
import { CUTS } from '../src/timeline.ts';
import { cutFrames, FPS, overlapFrames } from '../src/Video.tsx';

const pick = process.argv.slice(2);
for (const cut of CUTS.filter((c) => pick.length === 0 || pick.includes(c.id))) {
  const total = cutFrames(cut);
  console.log(`${cut.id}: ${total} frames = ${(total / FPS).toFixed(1)} s`);
  let at = 0;
  cut.scenes.forEach((s, i) => {
    if (i > 0) at -= overlapFrames(s.into);
    const sc = s.scene;
    console.log(`  ${String(i).padStart(2)} ${String(at).padStart(5)} ${(at / FPS).toFixed(1).padStart(6)}s  ${sc.kind}${sc.kind === 'clip' ? ` ${sc.shot} ${sc.from}→${sc.to}` : ''} (${sc.dur}s)`);
    at += Math.round(sc.dur * FPS);
  });
}
