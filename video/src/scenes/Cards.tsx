/**
 * The typographic scenes: title, statement, stats, the six bots and the end card.
 * Responsibility: brand-only scenes between captures (Geist, ink on white or the
 * inverse, bot colours). Every number shown is one the app or the docs show.
 * Idempotency: n/a — pure render.
 */
import { AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { BOT, BOTS, INK, MONO, MUTED, PAPER, SANS } from '../brand.ts';
import type { StatementScene, StatsScene } from '../types.ts';

const EASE = Easing.bezier(0.16, 1, 0.3, 1);
const ORANGE = BOT.tropiciel;

function useT() {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return { t: f / fps, f, fps };
}

const rise = (t: number, at: number, d = 0.6) =>
  interpolate(t, [at, at + d], [0, 1], { easing: EASE, extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

export function Logo({ size = 120, dark = false }: { size?: number; dark?: boolean }) {
  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: dark ? PAPER : INK,
        color: dark ? INK : PAPER,
        borderRadius: size * 0.24,
        padding: `${size * 0.08}px ${size * 0.26}px ${size * 0.14}px`,
        fontFamily: SANS,
        fontWeight: 700,
        fontSize: size,
        letterSpacing: -size * 0.04,
        lineHeight: 1,
      }}
    >
      trop
    </div>
  );
}

/** Six coloured dots (the bots) in a row. */
function BotDots({ t, at, size = 22 }: { t: number; at: number; size?: number }) {
  return (
    <div style={{ display: 'flex', gap: size * 0.7 }}>
      {BOTS.map((b, i) => {
        const p = rise(t, at + i * 0.08, 0.5);
        return <span key={b.key} style={{ width: size, height: size, borderRadius: size / 2, background: b.key === 'sedzia' ? MUTED : BOT[b.key], opacity: p, transform: `scale(${0.4 + 0.6 * p})` }} />;
      })}
    </div>
  );
}

export function TitleCard({ dark = false }: { dark?: boolean }) {
  const { t } = useT();
  const fg = dark ? PAPER : INK;
  const p0 = rise(t, 0.1, 0.8);
  const p1 = rise(t, 0.45);
  const p2 = rise(t, 0.75);
  return (
    <AbsoluteFill style={{ background: dark ? INK : PAPER, alignItems: 'center', justifyContent: 'center', fontFamily: SANS, color: fg }}>
      <div style={{ transform: `translateY(${(1 - p0) * 30}px) scale(${0.92 + 0.08 * p0})`, opacity: p0 }}>
        <Logo size={150} dark={dark} />
      </div>
      <div style={{ marginTop: 40, fontSize: 64, fontWeight: 600, letterSpacing: -1.5, opacity: p1, transform: `translateY(${(1 - p1) * 20}px)` }}>follow the fake</div>
      <div style={{ marginTop: 20, fontSize: 32, color: dark ? 'rgba(255,255,255,.7)' : MUTED, opacity: p2, transform: `translateY(${(1 - p2) * 20}px)` }}>
        reklamy-oszustwa → kampanie → operatorzy → operacje
      </div>
      <div style={{ marginTop: 44 }}>
        <BotDots t={t} at={0.9} />
      </div>
      <div style={{ position: 'absolute', bottom: 64, fontSize: 24, color: dark ? 'rgba(255,255,255,.55)' : MUTED, opacity: p2, fontFamily: MONO }}>
        HackNation 2026 · NASK · „Kolekcjoner fejków”
      </div>
    </AbsoluteFill>
  );
}

export function Statement({ spec }: { spec: StatementScene }) {
  const { t } = useT();
  const dark = !!spec.dark;
  const fg = dark ? PAPER : INK;
  return (
    <AbsoluteFill style={{ background: dark ? INK : PAPER, justifyContent: 'center', padding: '0 160px', fontFamily: SANS, color: fg }}>
      {spec.kicker ? (
        <div style={{ fontFamily: MONO, fontSize: 26, color: dark ? 'rgba(255,255,255,.6)' : MUTED, marginBottom: 34, opacity: rise(t, 0) }}>{spec.kicker}</div>
      ) : null}
      {spec.lines.map((l, i) => {
        const p = rise(t, l.at, 0.7);
        return (
          <div
            key={i}
            style={{
              fontSize: l.small ? 44 : 96,
              fontWeight: l.small ? 500 : 700,
              letterSpacing: l.small ? -0.5 : -3,
              lineHeight: 1.08,
              marginTop: l.small ? 28 : 6,
              color: l.accent ? ORANGE : l.small ? (dark ? 'rgba(255,255,255,.75)' : MUTED) : fg,
              opacity: p,
              transform: `translateY(${(1 - p) * 36}px)`,
              clipPath: `inset(0 0 ${(1 - p) * 30}% 0)`,
            }}
          >
            {l.text}
          </div>
        );
      })}
    </AbsoluteFill>
  );
}

export function Stats({ spec }: { spec: StatsScene }) {
  const { t, f, fps } = useT();
  const dark = !!spec.dark;
  const fg = dark ? PAPER : INK;
  const n = spec.items.length;
  return (
    <AbsoluteFill style={{ background: dark ? INK : PAPER, justifyContent: 'center', padding: '0 140px', fontFamily: SANS, color: fg }}>
      <div style={{ fontSize: 30, fontFamily: MONO, color: dark ? 'rgba(255,255,255,.6)' : MUTED, opacity: rise(t, 0), marginBottom: 48 }}>{spec.title}</div>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(n, 4)}, 1fr)`, gap: 36 }}>
        {spec.items.map((it, i) => {
          const s = spring({ frame: f - Math.round((0.25 + i * 0.22) * fps), fps, config: { damping: 18, stiffness: 120 } });
          return (
            <div key={i} style={{ borderTop: `3px solid ${dark ? 'rgba(255,255,255,.25)' : '#DDD'}`, paddingTop: 28, opacity: Math.min(1, s * 1.4), transform: `translateY(${(1 - s) * 40}px)` }}>
              <div style={{ fontSize: 112, fontWeight: 700, letterSpacing: -4, lineHeight: 1 }}>{it.value}</div>
              <div style={{ fontSize: 32, fontWeight: 600, marginTop: 20, lineHeight: 1.2 }}>{it.label}</div>
              {it.note ? <div style={{ fontSize: 24, marginTop: 10, color: dark ? 'rgba(255,255,255,.6)' : MUTED, lineHeight: 1.3 }}>{it.note}</div> : null}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
}

export function BotsCard() {
  const { t } = useT();
  return (
    <AbsoluteFill style={{ background: PAPER, justifyContent: 'center', padding: '0 150px', fontFamily: SANS, color: INK }}>
      <div style={{ fontSize: 72, fontWeight: 700, letterSpacing: -2.5, opacity: rise(t, 0), transform: `translateY(${(1 - rise(t, 0)) * 24}px)` }}>Sześć botów-detektywów</div>
      <div style={{ fontSize: 34, color: MUTED, marginTop: 14, opacity: rise(t, 0.2) }}>każdy czyta inny rodzaj śladu, Sędzia łączy je w werdykt</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '34px 40px', marginTop: 64 }}>
        {BOTS.map((b, i) => {
          const p = rise(t, 0.45 + i * 0.16, 0.55);
          return (
            <div key={b.key} style={{ display: 'flex', alignItems: 'center', gap: 24, opacity: p, transform: `translateY(${(1 - p) * 26}px)` }}>
              <span style={{ width: 64, height: 64, borderRadius: 32, background: BOT[b.key], flex: 'none', transform: `scale(${0.5 + 0.5 * p})` }} />
              <div>
                <div style={{ fontSize: 40, fontWeight: 700, letterSpacing: -1 }}>{b.name}</div>
                <div style={{ fontSize: 27, color: MUTED, marginTop: 2 }}>{b.job}</div>
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
}

export function EndCard() {
  const { t } = useT();
  const p0 = rise(t, 0.05, 0.8);
  const p1 = rise(t, 0.4);
  const p2 = rise(t, 0.7);
  return (
    <AbsoluteFill style={{ background: INK, alignItems: 'center', justifyContent: 'center', fontFamily: SANS, color: PAPER }}>
      <div style={{ opacity: p0, transform: `scale(${0.9 + 0.1 * p0})` }}>
        <Logo size={130} dark />
      </div>
      <div style={{ marginTop: 34, fontSize: 58, fontWeight: 600, letterSpacing: -1.5, opacity: p1 }}>follow the fake</div>
      <div style={{ marginTop: 22, fontSize: 30, color: 'rgba(255,255,255,.7)', opacity: p1 }}>od jednej reklamy do całej kampanii, z dowodami</div>
      <div style={{ marginTop: 50, opacity: p2, transform: `translateY(${(1 - p2) * 16}px)`, background: PAPER, color: INK, borderRadius: 40, padding: '16px 40px', fontFamily: MONO, fontSize: 40, fontWeight: 500 }}>
        trop.b.solvro.pl
      </div>
      <div style={{ marginTop: 46 }}>
        <BotDots t={t} at={0.9} size={18} />
      </div>
      <div style={{ position: 'absolute', bottom: 60, fontSize: 24, color: 'rgba(255,255,255,.5)', fontFamily: MONO, opacity: p2 }}>
        HackNation 2026 · NASK · „Kolekcjoner fejków”
      </div>
    </AbsoluteFill>
  );
}
