/**
 * A segment of a screen capture inside a browser window, with a camera and captions.
 * Responsibility: resolve the segment's marks from captures.json, fit it to the scene's
 * length (playbackRate), move the camera between keyframes, and draw the captions.
 * A missing capture renders as a striped placeholder naming the shot to record.
 * Idempotency: n/a — pure render.
 */
import { AbsoluteFill, Easing, interpolate, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { INK, LINE, MONO, MUTED, PAPER, SANS, STAGE } from '../brand.ts';
import captures from '../captures.json' with { type: 'json' };
import { Caption } from '../components/Caption.tsx';
import type { Cam, ClipScene as Spec, Point } from '../types.ts';

const W = 1920;
const H = 1080;
const S = 0.865; // window scale
const BAR = 46; // window chrome height
const CAM_EASE = Easing.bezier(0.65, 0, 0.35, 1);

type Capture = { seconds: number; marks: Record<string, number> };
const CAPTURES = captures as Record<string, Capture>;

export function resolvePoint(shot: string, p: Point): number {
  if (typeof p === 'number') return p;
  const c = CAPTURES[shot];
  const m = /^([a-z]+)\s*([+-]\s*[\d.]+)?$/.exec(p);
  if (!c || !m) return 0;
  const base = m[1] === 'start' ? 0 : m[1] === 'eof' ? c.seconds : c.marks[m[1]!];
  if (base === undefined) throw new Error(`${shot}: no mark "${m[1]}"`);
  return base + (m[2] ? Number(m[2].replace(/\s/g, '')) : 0);
}

function camAt(cams: Cam[] | undefined, t: number): Cam {
  if (!cams || cams.length === 0) return { at: 0, x: W / 2, y: H / 2, z: 1 };
  if (t <= cams[0]!.at) return cams[0]!;
  for (let i = 1; i < cams.length; i++) {
    const a = cams[i - 1]!;
    const b = cams[i]!;
    if (t <= b.at) {
      const k = CAM_EASE((t - a.at) / Math.max(0.001, b.at - a.at));
      // zoom moves in log space so it feels even
      const z = Math.exp(Math.log(a.z) + (Math.log(b.z) - Math.log(a.z)) * k);
      return { at: t, x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k, z };
    }
  }
  return cams[cams.length - 1]!;
}

const PAGES: Record<string, string> = {
  sprawdz: 'trop.b.solvro.pl',
  nowa: 'trop.b.solvro.pl',
  live: 'trop.b.solvro.pl',
  kampanie: 'trop.b.solvro.pl/kampanie',
  sledztwo: 'trop.b.solvro.pl/sledztwa',
  lab: 'trop.b.solvro.pl/lab',
  extension: 'trop.b.solvro.pl/demo/feed-real.html · wtyczka TROP',
};

export function ClipScene({ spec }: { spec: Spec }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const have = !!CAPTURES[spec.shot];
  const from = have ? resolvePoint(spec.shot, spec.from) : 0;
  const to = have ? resolvePoint(spec.shot, spec.to) : spec.dur;
  const rate = Math.max(0.25, (to - from) / spec.dur);
  const cam = camAt(spec.cam, t);
  const z = cam.z;
  const tx = Math.min(0, Math.max(W - W * z, W / 2 - cam.x * z));
  const ty = Math.min(0, Math.max(H - H * z, H / 2 - cam.y * z));
  // the window settles in on the scene's first frames
  const settle = interpolate(t, [0, 0.5], [0, 1], { easing: Easing.bezier(0.16, 1, 0.3, 1), extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const winW = W * S;
  const winH = H * S + BAR;
  return (
    <AbsoluteFill style={{ background: STAGE }}>
      <div
        style={{
          position: 'absolute',
          left: (W - winW) / 2,
          top: (H - winH) / 2 - 4,
          width: winW,
          height: winH,
          borderRadius: 20,
          overflow: 'hidden',
          background: PAPER,
          boxShadow: '0 1px 2px rgba(0,0,0,.06), 0 30px 80px rgba(0,0,0,.14)',
          border: `1px solid ${LINE}`,
          transform: `scale(${0.985 + 0.015 * settle})`,
        }}
      >
        <div style={{ height: BAR, display: 'flex', alignItems: 'center', gap: 9, padding: '0 20px', borderBottom: `1px solid ${LINE}`, background: '#FAFAF9' }}>
          {['#E5E5E3', '#E5E5E3', '#E5E5E3'].map((c, i) => (
            <span key={i} style={{ width: 13, height: 13, borderRadius: 7, background: c }} />
          ))}
          <div style={{ marginLeft: 18, height: 28, padding: '0 16px', borderRadius: 14, background: PAPER, border: `1px solid ${LINE}`, display: 'flex', alignItems: 'center', fontFamily: MONO, fontSize: 16, color: MUTED }}>
            {spec.chapter ?? PAGES[spec.shot] ?? 'trop.b.solvro.pl'}
          </div>
        </div>
        <div style={{ position: 'relative', width: W * S, height: H * S, overflow: 'hidden' }}>
          <div style={{ position: 'absolute', left: 0, top: 0, width: W, height: H, transformOrigin: '0 0', transform: `scale(${S})` }}>
            <div style={{ position: 'absolute', left: 0, top: 0, width: W, height: H, transformOrigin: '0 0', transform: `translate(${tx}px, ${ty}px) scale(${z})` }}>
              {have ? (
                <OffthreadVideo src={staticFile(`captures/${spec.shot}.mp4`)} trimBefore={Math.round(from * fps)} playbackRate={rate} muted style={{ width: W, height: H }} />
              ) : (
                <AbsoluteFill style={{ background: `repeating-linear-gradient(45deg, #eee 0 30px, #f8f8f8 30px 60px)`, alignItems: 'center', justifyContent: 'center', fontFamily: SANS, fontSize: 48, color: INK }}>
                  brak nagrania: public/captures/{spec.shot}.mp4
                </AbsoluteFill>
              )}
            </div>
          </div>
        </div>
      </div>
      {(spec.caps ?? []).map((c, i) => (
        <Caption key={i} cap={c} />
      ))}
    </AbsoluteFill>
  );
}
