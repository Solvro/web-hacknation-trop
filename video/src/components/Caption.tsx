/**
 * On-screen captions (no voice-over): a card that slides in, holds and fades.
 * Responsibility: draw one Cap at its position in the look the cut picked (CaptionLook
 * context): 'card' = white card with ink text, 'ink' = black card with white text.
 * Idempotency: n/a — pure render.
 */
import { createContext, useContext } from 'react';
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { BOT, BOTS, INK, MUTED, PAPER, SANS } from '../brand.ts';
import type { Cap } from '../types.ts';
import { Bubble } from '../scenes/Zgrai.tsx';

export type Look = 'card' | 'ink' | 'bubble';
export const CaptionLook = createContext<Look>('card');

const EASE = Easing.bezier(0.16, 1, 0.3, 1);

export function Caption({ cap }: { cap: Cap }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const look = useContext(CaptionLook);
  if (look === 'bubble') return <Bubble cap={cap} />;
  const t = frame / fps;
  if (t < cap.at - 0.01 || t > cap.until + 0.4) return null;
  const pIn = interpolate(t, [cap.at, cap.at + 0.45], [0, 1], { easing: EASE, extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const pOut = interpolate(t, [cap.until, cap.until + 0.3], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const pos = cap.pos ?? 'bl';
  const dark = look === 'ink';
  const bot = cap.bot ? BOTS.find((b) => b.key === cap.bot) : undefined;
  const place: React.CSSProperties =
    pos === 'bl' ? { left: 96, bottom: 84 }
    : pos === 'br' ? { right: 96, bottom: 84, alignItems: 'flex-end' }
    : pos === 'tl' ? { left: 96, top: 84 }
    : pos === 'tr' ? { right: 96, top: 84, alignItems: 'flex-end' }
    : { left: 0, right: 0, bottom: 84, alignItems: 'center' };
  return (
    <div
      style={{
        position: 'absolute',
        display: 'flex',
        flexDirection: 'column',
        ...place,
        opacity: pIn * pOut,
        transform: `translateY(${(1 - pIn) * 28}px)`,
      }}
    >
      <div
        style={{
          maxWidth: 1060,
          background: dark ? INK : PAPER,
          color: dark ? PAPER : INK,
          borderRadius: 22,
          padding: '22px 30px 24px',
          boxShadow: '0 2px 4px rgba(0,0,0,.06), 0 24px 60px rgba(0,0,0,.18)',
          fontFamily: SANS,
        }}
      >
        {bot ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8, fontSize: 22, fontWeight: 600, color: dark ? 'rgba(255,255,255,.75)' : MUTED }}>
            <span style={{ width: 14, height: 14, borderRadius: 7, background: bot.key === 'sedzia' && dark ? PAPER : BOT[bot.key] }} />
            {bot.name}
          </div>
        ) : null}
        <div style={{ fontSize: 40, fontWeight: 600, lineHeight: 1.18, letterSpacing: -0.6 }}>{cap.text}</div>
        {cap.sub ? (
          <div style={{ fontSize: 26, fontWeight: 400, lineHeight: 1.3, marginTop: 8, color: dark ? 'rgba(255,255,255,.72)' : MUTED }}>{cap.sub}</div>
        ) : null}
      </div>
    </div>
  );
}
