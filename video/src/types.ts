/**
 * Scene vocabulary shared by the timeline and the scene components.
 * Responsibility: types only. Times inside a scene are seconds from the scene's start.
 * Idempotency: n/a — types.
 */
import type { BotName } from './brand.ts';

/** Camera keyframe: focus point in capture pixels (1920×1080) and zoom (1 = whole frame). */
export interface Cam {
  at: number;
  x: number;
  y: number;
  z: number;
}

export type CapPos = 'bl' | 'br' | 'tl' | 'tr' | 'bc';

export interface Cap {
  at: number;
  until: number;
  text: string;
  sub?: string;
  bot?: BotName;
  pos?: CapPos;
}

/** A point in a capture: a mark name from captures.json, optionally "+1.5" / "-0.5" seconds. */
export type Point = string | number;

export interface ClipScene {
  kind: 'clip';
  shot: string;
  from: Point;
  to: Point;
  /** Output length in seconds; the capture segment is sped up or slowed to fit. */
  dur: number;
  cam?: Cam[];
  caps?: Cap[];
  /** Small label in the window's address strip (defaults to the shot's page). */
  chapter?: string;
}

export interface TitleScene {
  kind: 'title';
  dur: number;
  dark?: boolean;
}

/** Big typography, one or more lines revealed one by one. */
export interface StatementScene {
  kind: 'statement';
  dur: number;
  lines: { text: string; at: number; accent?: boolean; small?: boolean }[];
  dark?: boolean;
  kicker?: string;
}

export interface StatsScene {
  kind: 'stats';
  dur: number;
  title: string;
  items: { value: string; label: string; note?: string }[];
  dark?: boolean;
}

export interface BotsScene {
  kind: 'bots';
  dur: number;
}

export interface EndScene {
  kind: 'end';
  dur: number;
}

/** zgrai deck scenes: problem (red), insight, title wordmark, closing (red). */
export interface ZScene {
  kind: 'zproblem' | 'zinsight' | 'ztitle' | 'zend';
  dur: number;
}

export type Scene = ClipScene | TitleScene | StatementScene | StatsScene | BotsScene | EndScene | ZScene;

export type TransitionId = 'cut' | 'fade' | 'slide' | 'wipe';

export interface Cut {
  id: string;
  purpose: string;
  /** Caption look: white cards or black cards. */
  look: 'card' | 'ink' | 'bubble';
  scenes: { scene: Scene; into?: TransitionId }[];
}
