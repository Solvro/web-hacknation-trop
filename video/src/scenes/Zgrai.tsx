/**
 * The zgrai look of the pitch deck (docs/pitch/TROP-pitch-zgrai.pdf on the pitch-deck branch):
 * white, ink and red #E3322B, Instrument Sans with IBM Plex Mono, the giant filled and
 * outlined TROP wordmark, a full-red problem slide, a red closing slide, and bot chat
 * bubbles with one sharp corner.
 * Responsibility: the zgrai scenes and the bubble caption.
 * Idempotency: loadZgraiFonts() is safe to call more than once.
 */
import { loadFont } from '@remotion/fonts';
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { BOT, BOTS } from '../brand.ts';
import type { Cap } from '../types.ts';

export const RED = '#E3322B';
export const ZINK = '#111111';
export const ZSANS = '"Instrument Sans", system-ui, sans-serif';
export const ZMONO = '"IBM Plex Mono", ui-monospace, monospace';

const LATIN = 'U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD';
const LATIN_EXT = 'U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C4, U+2113, U+2C60-2C7F, U+A720-A7FF';

let loaded = false;
export function loadZgraiFonts(): void {
  if (loaded) return;
  loaded = true;
  const faces: [string, string, string, string][] = [
    ['Instrument Sans', 'InstrumentSans-400-latin.woff2', '400 700', LATIN],
    ['Instrument Sans', 'InstrumentSans-400-latin-ext.woff2', '400 700', LATIN_EXT],
    ['IBM Plex Mono', 'IBMPlexMono-400-latin.woff2', '400', LATIN],
    ['IBM Plex Mono', 'IBMPlexMono-400-latin-ext.woff2', '400', LATIN_EXT],
    ['IBM Plex Mono', 'IBMPlexMono-500-latin.woff2', '500', LATIN],
    ['IBM Plex Mono', 'IBMPlexMono-500-latin-ext.woff2', '500', LATIN_EXT],
  ];
  for (const [family, file, weight, unicodeRange] of faces) {
    loadFont({ family, url: staticFile(`fonts/${file}`), weight, unicodeRange, format: 'woff2' }).catch(() => {});
  }
}

const EASE = Easing.bezier(0.16, 1, 0.3, 1);
const rise = (t: number, at: number, d = 0.6) => interpolate(t, [at, at + d], [0, 1], { easing: EASE, extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
function useT() {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return f / fps;
}

/** The deck's top strip: "Solvro Dawid … HackNation 2026" over a thin rule. */
function Strip({ on }: { on: 'red' | 'white' }) {
  const c = on === 'red' ? '#fff' : ZINK;
  return (
    <div style={{ position: 'absolute', left: 64, right: 64, top: 34, display: 'flex', justifyContent: 'space-between', paddingBottom: 12, borderBottom: `2px solid ${on === 'red' ? 'rgba(255,255,255,.8)' : RED}`, fontFamily: ZSANS, fontWeight: 600, fontSize: 22, color: c }}>
      <span>Solvro Dawid</span>
      <span>HackNation 2026 · NASK</span>
    </div>
  );
}

export function ZProblem() {
  const t = useT();
  const big = rise(t, 2.2, 1.1);
  return (
    <AbsoluteFill style={{ background: RED, fontFamily: ZSANS, color: '#fff', overflow: 'hidden' }}>
      <Strip on="red" />
      <div style={{ position: 'absolute', left: 64, top: 105, fontSize: 80, fontWeight: 700, letterSpacing: -2.5, lineHeight: 1.05 }}>
        <div style={{ opacity: rise(t, 0.1), transform: `translateY(${(1 - rise(t, 0.1)) * 30}px)` }}>Reklamy zgłasza się pojedynczo.</div>
        <div style={{ opacity: rise(t, 0.7), transform: `translateY(${(1 - rise(t, 0.7)) * 30}px)` }}>Oszuści działają kampaniami.</div>
      </div>
      <div style={{ position: 'absolute', left: 64, top: 310, display: 'grid', gridTemplateColumns: 'repeat(2, 760px)', gap: '22px 60px', fontSize: 30 }}>
        {[
          ['01', 'Fałszywe portale', 'twarze znanych osób prowadzą do „inwestycji”'],
          ['02', 'Zdejmowane po jednej', 'reklama znika, kampania wraca pod nową domeną'],
          ['03', 'Zmieniają się domeny i twarze', 'nowe adresy, nowe osoby, nowe konta reklamowe'],
          ['04', 'Zaplecze zostaje', 'ten sam zestaw strony, piksel i bramka CAPI'],
        ].map(([n, h, d], i) => (
          <div key={n} style={{ borderTop: '2px solid rgba(255,255,255,.5)', paddingTop: 12, opacity: rise(t, 1.0 + i * 0.25), transform: `translateY(${(1 - rise(t, 1.0 + i * 0.25)) * 18}px)` }}>
            <div style={{ fontFamily: ZMONO, fontSize: 20, opacity: 0.8 }}>{n}</div>
            <div style={{ fontWeight: 700, marginTop: 4 }}>{h}</div>
            <div style={{ fontSize: 24, opacity: 0.85, marginTop: 4 }}>{d}</div>
          </div>
        ))}
      </div>
      <div style={{ position: 'absolute', left: 40, bottom: -140, fontSize: 400, fontWeight: 700, letterSpacing: -18, lineHeight: 1, transform: `translateY(${(1 - big) * 240}px)` }}>Problem</div>
    </AbsoluteFill>
  );
}

export function ZInsight() {
  const t = useT();
  const items: [string, string, boolean][] = [
    ['6', 'reklam', false],
    ['5', 'domen', false],
    ['4', 'reklamodawców', false],
    ['0 z 5', 'domen na liście CERT PL', true],
  ];
  return (
    <AbsoluteFill style={{ background: '#fff', fontFamily: ZSANS, color: ZINK }}>
      <Strip on="white" />
      <div style={{ position: 'absolute', left: 64, top: 120, fontFamily: ZMONO, fontSize: 24, color: RED, opacity: rise(t, 0) }}>WGLĄD · JEDNA KAMPANIA W TROP (KMP-001)</div>
      <div style={{ position: 'absolute', left: 64, top: 165, fontSize: 80, fontWeight: 700, letterSpacing: -2.5, lineHeight: 1.05, opacity: rise(t, 0.15), transform: `translateY(${(1 - rise(t, 0.15)) * 24}px)` }}>
        Tak wygląda jedna kampania
        <br />
        po połączeniu śladów.
      </div>
      <div style={{ position: 'absolute', left: 64, right: 64, top: 470, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 36 }}>
        {items.map(([v, l, red], i) => {
          const p = rise(t, 0.7 + i * 0.18);
          return (
            <div key={l} style={{ borderTop: `3px solid ${red ? RED : ZINK}`, paddingTop: 22, opacity: p, transform: `translateY(${(1 - p) * 30}px)` }}>
              <div style={{ fontSize: 120, fontWeight: 700, letterSpacing: -4, lineHeight: 1, color: red ? RED : ZINK }}>{v}</div>
              <div style={{ fontSize: 32, fontWeight: 600, marginTop: 14 }}>{l}</div>
            </div>
          );
        })}
      </div>
      <div style={{ position: 'absolute', left: 64, bottom: 90, fontSize: 32, color: '#555', opacity: rise(t, 1.7) }}>
        Ten sam zestaw strony, piksel Facebooka i bramka CAPI. Zablokowanie jednej domeny nic nie kończy.
      </div>
    </AbsoluteFill>
  );
}

/** Title: "Follow the fake" over the giant filled / outlined TROP wordmark. */
export function ZTitle() {
  const t = useT();
  const row = (i: number, kind: 'fill' | 'outline' | 'fade') => {
    const p = rise(t, 0.2 + i * 0.18, 0.8);
    const tr: React.CSSProperties = kind === 'fill' ? { color: ZINK } : kind === 'outline' ? { color: 'transparent', WebkitTextStroke: `4px ${ZINK}` } : { color: 'transparent', WebkitTextStroke: '4px #ccc' };
    const op: React.CSSProperties = kind === 'fade' ? { color: '#F3B5B1' } : { color: RED };
    return (
      <div key={i} style={{ display: 'flex', fontSize: 300, fontWeight: 700, letterSpacing: -14, lineHeight: 0.86, opacity: p, transform: `translateX(${(1 - p) * -60}px)` }}>
        <span style={tr}>TR</span>
        <span style={op}>OP</span>
      </div>
    );
  };
  return (
    <AbsoluteFill style={{ background: '#fff', fontFamily: ZSANS, color: ZINK, alignItems: 'center', overflow: 'hidden' }}>
      <Strip on="white" />
      <div style={{ marginTop: 108, fontFamily: ZMONO, fontSize: 24, letterSpacing: 2, opacity: rise(t, 0) }}>
        ZADANIE <span style={{ color: RED }}>NASK</span>: „KOLEKCJONER FEJKÓW”
      </div>
      <div style={{ fontSize: 76, fontWeight: 700, letterSpacing: -2, marginTop: 8, opacity: rise(t, 0.1) }}>Follow the fake</div>
      <div style={{ marginTop: 30 }}>
        {row(0, 'fill')}
        {row(1, 'outline')}
        {row(2, 'fade')}
      </div>
    </AbsoluteFill>
  );
}

export function ZEnd() {
  const t = useT();
  return (
    <AbsoluteFill style={{ background: RED, fontFamily: ZSANS, color: '#fff' }}>
      <Strip on="red" />
      <div style={{ position: 'absolute', left: 64, top: 300, fontSize: 150, fontWeight: 700, letterSpacing: -6, lineHeight: 0.95, opacity: rise(t, 0.1), transform: `translateY(${(1 - rise(t, 0.1)) * 30}px)` }}>
        TROP
        <br />
        Follow the fake.
      </div>
      <div style={{ position: 'absolute', left: 64, top: 640, fontSize: 36, fontWeight: 500, opacity: rise(t, 0.6) }}>Od jednej reklamy do całej kampanii, z dowodami.</div>
      <div style={{ position: 'absolute', left: 64, top: 720, fontFamily: ZMONO, fontSize: 34, lineHeight: 1.5, opacity: rise(t, 0.9) }}>
        trop.b.solvro.pl
        <br />
        github.com/Solvro/web-hacknation-trop
      </div>
      <div style={{ position: 'absolute', right: 96, bottom: 90, display: 'flex', gap: 14, opacity: rise(t, 1.1) }}>
        {BOTS.map((b) => (
          <span key={b.key} style={{ width: 34, height: 34, borderRadius: 17, background: b.key === 'sedzia' ? ZINK : BOT[b.key], border: '3px solid #fff' }} />
        ))}
      </div>
    </AbsoluteFill>
  );
}

/** Caption as a bot chat bubble: ink (or red) with one sharp corner and a mono label. */
export function Bubble({ cap }: { cap: Cap }) {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = f / fps;
  if (t < cap.at - 0.01 || t > cap.until + 0.4) return null;
  const pIn = rise(t, cap.at, 0.45);
  const pOut = interpolate(t, [cap.until, cap.until + 0.3], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const bot = BOTS.find((b) => b.key === (cap.bot ?? 'sedzia'))!;
  const right = cap.pos === 'br' || cap.pos === 'tr';
  const top = cap.pos === 'tl' || cap.pos === 'tr';
  const red = cap.bot === undefined;
  return (
    <div style={{ position: 'absolute', [right ? 'right' : 'left']: 90, [top ? 'top' : 'bottom']: 80, display: 'flex', alignItems: 'flex-end', gap: 16, flexDirection: right ? 'row-reverse' : 'row', opacity: pIn * pOut, transform: `translateY(${(1 - pIn) * 26}px) scale(${0.96 + 0.04 * pIn})`, transformOrigin: right ? 'bottom right' : 'bottom left' }}>
      {cap.bot ? (
        <Img src={staticFile(`bots/${bot.key}.png`)} style={{ width: 96, height: 96, borderRadius: 48, background: '#fff', boxShadow: '0 6px 18px rgba(0,0,0,.22)', flex: 'none', objectFit: 'cover' }} />
      ) : (
        <div style={{ width: 96, height: 96, borderRadius: 48, background: '#fff', boxShadow: '0 6px 18px rgba(0,0,0,.22)', flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ background: ZINK, color: '#fff', fontFamily: ZSANS, fontWeight: 700, fontSize: 24, letterSpacing: -1, borderRadius: 8, padding: '2px 8px 5px' }}>trop</span>
        </div>
      )}
      <div
        style={{
          maxWidth: 1000,
          background: red ? RED : ZINK,
          color: '#fff',
          padding: '18px 26px 20px',
          borderRadius: 22,
          [right ? 'borderBottomRightRadius' : 'borderBottomLeftRadius']: 3,
          boxShadow: '0 20px 50px rgba(0,0,0,.25)',
          fontFamily: ZSANS,
        }}
      >
        <div style={{ fontFamily: ZMONO, fontSize: 18, letterSpacing: 1.5, opacity: 0.75, marginBottom: 6 }}>{(cap.bot ? bot.name : 'TROP').toUpperCase()}</div>
        <div style={{ fontSize: 38, fontWeight: 600, lineHeight: 1.18, letterSpacing: -0.5 }}>{cap.text}</div>
      </div>
    </div>
  );
}
