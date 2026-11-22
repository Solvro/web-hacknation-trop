'use client';
// zgrai jelly bots in detective costumes (docs/design/canvas/assets/jelly-overlay-detective.js + three.js r128,
// both served from /public/vendor). The overlay engine scans its root for [data-jelly] spans and draws the bots on
// one WebGL canvas. Without WebGL the spans fall back to flat CSS blobs (see .jelly-fallback below).
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';

interface JellyHandle { wake(): void; sleep(): void; refresh(): void; poke(t?: unknown): void; dispose(): void }
declare global {
  interface Window {
    ZgraiJelly?: { mountOverlay(canvas: HTMLCanvasElement, root: HTMLElement | null, opts?: Record<string, unknown>): JellyHandle };
    THREE?: unknown;
    __jellyLoading?: Promise<void>;
  }
}

function loadScript(src: string) {
  return new Promise<void>((res, rej) => {
    const s = document.createElement('script');
    s.src = src; s.async = false; s.onload = () => res(); s.onerror = () => rej(new Error(src));
    document.head.appendChild(s);
  });
}
export function loadJelly(): Promise<void> {
  if (typeof window === 'undefined') return Promise.resolve();
  if (window.ZgraiJelly) return Promise.resolve();
  if (!window.__jellyLoading) {
    window.__jellyLoading = (window.THREE ? Promise.resolve() : loadScript('/vendor/three-r128.min.js'))
      .then(() => loadScript('/vendor/jelly-overlay-detective.js'));
  }
  return window.__jellyLoading;
}
function hasWebGL() {
  try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch { return false; }
}

export const FIELD_COLORS = ['#2563EB', '#F97316', '#14B8A6', '#8B5CF6', '#EC4899'];

export interface JellyRootProps {
  mode?: 'plain' | 'field';
  /** field mode: 'asleep' | 'awake' */
  fieldState?: 'asleep' | 'awake';
  /** increments → wake the field bots */
  wakeKey?: number;
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
}

/** Mount point for bots. `plain`: a fixed viewport canvas drawing every [data-jelly] avatar inside the root.
 *  `field`: bots roam the root's box around [data-jelly-clear] areas (board 1 and board 14). */
export function JellyRoot({ mode = 'plain', fieldState = 'asleep', wakeKey = 0, className, style, children }: JellyRootProps) {
  const root = useRef<HTMLDivElement>(null);
  const cv = useRef<HTMLCanvasElement>(null);
  const handle = useRef<JellyHandle | null>(null);
  const [fallback, setFallback] = useState(false);

  useEffect(() => {
    let disposed = false;
    if (!hasWebGL()) { setFallback(true); return; }
    loadJelly().then(() => {
      if (disposed || !window.ZgraiJelly || !cv.current || !root.current) return;
      const opts: Record<string, unknown> = { costume: 'detective' };
      if (mode === 'field') opts.field = { bots: FIELD_COLORS.map((c) => ({ color: c, shape: 'auto' })), master: true, state: fieldState };
      handle.current = window.ZgraiJelly.mountOverlay(cv.current, root.current, opts);
    }).catch(() => setFallback(true));
    return () => { disposed = true; handle.current?.dispose(); handle.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  useEffect(() => { if (wakeKey > 0) handle.current?.wake(); }, [wakeKey]);

  return (
    <div ref={root} className={(className ?? '') + (fallback ? ' jelly-fallback' : '')} style={{ position: 'relative', ...style }}>
      <canvas
        ref={cv}
        aria-hidden="true"
        className={mode === 'field' ? 'max-sm:!hidden' : undefined}
        style={mode === 'field'
          ? { position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 3 }
          : { position: 'fixed', inset: 0, width: '100vw', height: '100vh', pointerEvents: 'none', zIndex: 30 }}
      />
      {children}
    </div>
  );
}

export interface BotProps {
  color: string;
  state?: 'asleep' | 'awake' | 'speaking';
  size?: number;
  master?: boolean;
  costume?: string;
  className?: string;
}
/** One bot avatar slot. The engine draws into the space this span occupies. */
export function Bot({ color, state = 'awake', size = 34, master, costume, className }: BotProps) {
  return (
    <span
      data-jelly={master ? 'square' : 'auto'}
      data-color={color}
      data-state={state}
      {...(master ? { 'data-master': '' } : {})}
      {...(costume ? { 'data-costume': costume } : {})}
      aria-hidden="true"
      className={'jelly-slot ' + (className ?? '')}
      style={{ flex: 'none', display: 'block', width: size, height: size, ['--jc' as string]: color }}
    />
  );
}
