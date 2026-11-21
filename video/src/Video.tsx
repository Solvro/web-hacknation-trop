/**
 * Plays one cut: its scenes in a TransitionSeries with the handovers the cut lists.
 * Responsibility: scene dispatch, handover presentations (CSS only: fade, slide, wipe, so
 * every cut renders on the CPU), and the cut length with overlaps subtracted.
 * Idempotency: n/a — pure render.
 */
import { linearTiming, TransitionSeries, type TransitionPresentation } from '@remotion/transitions';
import { fade } from '@remotion/transitions/fade';
import { slide } from '@remotion/transitions/slide';
import { wipe } from '@remotion/transitions/wipe';
import { Fragment } from 'react';
import { AbsoluteFill } from 'remotion';
import { loadFonts, PAPER } from './brand.ts';
import { CaptionLook, type Look } from './components/Caption.tsx';
import { BotsCard, EndCard, Stats, Statement, TitleCard } from './scenes/Cards.tsx';
import { ClipScene } from './scenes/ClipScene.tsx';
import type { Cut, Scene, TransitionId } from './types.ts';

export const FPS = 60;
const HANDOVER_S = 0.5;

loadFonts();

export const overlapFrames = (id: TransitionId | undefined): number => (!id || id === 'cut' ? 0 : Math.round(HANDOVER_S * FPS));

export function cutFrames(cut: Cut): number {
  return cut.scenes.reduce((n, s, i) => n + Math.round(s.scene.dur * FPS) - (i > 0 ? overlapFrames(s.into) : 0), 0);
}

// biome-ignore lint/suspicious/noExplicitAny: presentations carry heterogeneous props
function presentation(id: TransitionId): TransitionPresentation<any> {
  if (id === 'slide') return slide({ direction: 'from-right' });
  if (id === 'wipe') return wipe({ direction: 'from-left' });
  return fade();
}

function SceneView({ scene }: { scene: Scene }) {
  switch (scene.kind) {
    case 'clip':
      return <ClipScene spec={scene} />;
    case 'title':
      return <TitleCard dark={scene.dark} />;
    case 'statement':
      return <Statement spec={scene} />;
    case 'stats':
      return <Stats spec={scene} />;
    case 'bots':
      return <BotsCard />;
    case 'end':
      return <EndCard />;
  }
}

export function Video({ cut, look }: { cut: Cut; look: Look }) {
  return (
    <CaptionLook.Provider value={look}>
      <AbsoluteFill style={{ background: PAPER }}>
        <TransitionSeries>
          {cut.scenes.map((s, i) => (
            <Fragment key={i}>
              {i > 0 && s.into && s.into !== 'cut' ? (
                <TransitionSeries.Transition presentation={presentation(s.into)} timing={linearTiming({ durationInFrames: overlapFrames(s.into) })} />
              ) : null}
              <TransitionSeries.Sequence durationInFrames={Math.round(s.scene.dur * FPS)} premountFor={FPS}>
                <SceneView scene={s.scene} />
              </TransitionSeries.Sequence>
            </Fragment>
          ))}
        </TransitionSeries>
      </AbsoluteFill>
    </CaptionLook.Provider>
  );
}
