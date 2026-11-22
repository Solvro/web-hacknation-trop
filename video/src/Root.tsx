/**
 * Registers one composition per cut in timeline.ts (1920×1080, 60 fps).
 * Idempotency: n/a — registration.
 */
import { Composition } from 'remotion';
import { CUTS } from './timeline.ts';
import { cutFrames, FPS, Video } from './Video.tsx';

export function Root() {
  return (
    <>
      {CUTS.map((cut) => (
        <Composition
          key={cut.id}
          id={cut.id}
          component={Video}
          durationInFrames={cutFrames(cut)}
          fps={FPS}
          width={1920}
          height={1080}
          defaultProps={{ cut, look: cut.look }}
        />
      ))}
    </>
  );
}
