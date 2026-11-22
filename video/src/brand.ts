/**
 * TROP brand for the videos, copied from web/tailwind.config.ts and app/globals.css.
 * Responsibility: one source for colours, bot colours and the Geist faces.
 * Idempotency: loadFonts() is safe to call more than once.
 */
import { loadFont } from '@remotion/fonts';
import { staticFile } from 'remotion';

export const INK = '#0A0A0A';
export const PAPER = '#FFFFFF';
export const STAGE = '#F3F3F1';
export const MUTED = '#6B6B6B';
export const LINE = '#E6E6E3';
export const GREEN = '#16A34A';
export const AMBER = '#F59E0B';

export const BOT = {
  zwiadowca: '#2563EB',
  tropiciel: '#F97316',
  czytelnik: '#14B8A6',
  notariusz: '#8B5CF6',
  archiwista: '#EC4899',
  sedzia: '#0A0A0A',
} as const;
export type BotName = keyof typeof BOT;

export const BOTS: { key: BotName; name: string; job: string }[] = [
  { key: 'zwiadowca', name: 'Zwiadowca', job: 'przechwytuje stronę' },
  { key: 'tropiciel', name: 'Tropiciel', job: 'piksele, kit, tracking' },
  { key: 'czytelnik', name: 'Czytelnik', job: 'treść i osoby' },
  { key: 'notariusz', name: 'Notariusz', job: 'domeny i certyfikaty' },
  { key: 'archiwista', name: 'Archiwista', job: 'porównuje z bazą' },
  { key: 'sedzia', name: 'Sędzia', job: 'wydaje werdykt' },
];

export const SANS = 'Geist, system-ui, sans-serif';
export const MONO = '"Geist Mono", ui-monospace, monospace';

let loaded = false;
export function loadFonts(): void {
  if (loaded) return;
  loaded = true;
  const faces: [string, string, string][] = [
    ['Geist', 'Geist-Regular.woff2', '400'],
    ['Geist', 'Geist-Medium.woff2', '500'],
    ['Geist', 'Geist-SemiBold.woff2', '600'],
    ['Geist', 'Geist-Bold.woff2', '700'],
    ['Geist Mono', 'GeistMono-Regular.woff2', '400'],
    ['Geist Mono', 'GeistMono-Medium.woff2', '500'],
  ];
  for (const [family, file, weight] of faces) {
    loadFont({ family, url: staticFile(`fonts/${file}`), weight, format: 'woff2' }).catch(() => {});
  }
}
