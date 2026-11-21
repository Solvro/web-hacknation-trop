'use client';
// Real images of a material (GET /incidents/{id}/artifacts) and its display title. Only artifacts with a URL count;
// nothing is drawn in place of a missing image (no placeholder tiles).
// Shape (WS2): [{role: ad_screenshot|landing_screenshot|video_keyframe, url, w, h, boxes?: [{kind, x, y, w, h, text?}]}];
// the older {kind, name, url, width, height, mime} is read too.
import { useMemo } from 'react';
import type { IncidentSummary } from './contracts';
import { API, useApi } from './api';

export interface ShotBox { kind: string; x: number; y: number; w: number; h: number; text?: string | null }
export interface Artifact {
  kind?: string; name?: string; url: string; size?: number; mime?: string | null; role?: string | null;
  boxes?: ShotBox[] | null; w?: number | null; h?: number | null; width?: number | null; height?: number | null;
}
export interface Shot { url: string; boxes: ShotBox[]; width?: number | null; height?: number | null; role?: string | null }

/** API-relative URLs go through the same-origin proxy. */
export function artifactUrl(u: string): string {
  if (!u) return '';
  if (/^(https?:|data:|blob:)/i.test(u) || u.startsWith('/api/')) return u;
  return u.startsWith('/') ? API + u : `${API}/${u}`;
}
const isImage = (a: Artifact) => !!a.url && (/screenshot|keyframe|creative_image|image/.test(a.role ?? '') || a.kind === 'screenshot' || a.kind === 'creative'
  || /^image\//.test(a.mime ?? '') || /\.(png|jpe?g|webp|gif)(\?|$)/i.test(a.name ?? a.url));
const toShot = (a?: Artifact): Shot | undefined =>
  a ? { url: artifactUrl(a.url), boxes: (a.boxes ?? []).filter((b) => b && [b.x, b.y, b.w, b.h].every((v) => typeof v === 'number')), width: a.w ?? a.width, height: a.h ?? a.height, role: a.role } : undefined;

export interface Artifacts { ad?: string; adShot?: Shot; landing?: Shot; frames: Shot[]; any?: string }

/** `ad`: the ad screenshot / creative; `landing`: the rendered landing page (with finding boxes); `frames`: video keyframes. */
export function useArtifacts(incidentId?: string | null): Artifacts {
  const { data } = useApi<Artifact[] | { items: Artifact[] }>(incidentId ? `/incidents/${encodeURIComponent(incidentId)}/artifacts` : null);
  return useMemo(() => {
    const list = Array.isArray(data) ? data : Array.isArray(data?.items) ? data!.items : [];
    const imgs = list.filter(isImage);
    if (!imgs.length) return { frames: [] };
    const landing = imgs.find((a) => /landing/.test(a.role ?? '')) ?? imgs.find((a) => !a.role && /landing|lander|capture/i.test(a.name ?? ''));
    const frames = imgs.filter((a) => /keyframe|video/.test(a.role ?? ''));
    const ad = imgs.find((a) => /^ad_|creative/.test(a.role ?? '')) ?? imgs.find((a) => !a.role && a !== landing) ?? frames[0];
    const adShot = toShot(ad);
    return { ad: adShot?.url, adShot, landing: toShot(landing), frames: frames.map((f) => toShot(f)!), any: adShot?.url ?? toShot(landing)?.url ?? toShot(imgs[0])?.url };
  }, [data]);
}

type Detail = {
  id?: string; title?: string | null; domain?: string | null; captured_at?: string | null; source?: unknown;
  landing?: { title?: string | null; h1?: string | null; host?: string | null; etld1?: string | null; final_url?: string | null; entry_url?: string | null } | null;
  ad?: { video_title?: string | null; display_link?: string | null } | null;
  content?: { headline_template?: string | null; h1_template?: string | null } | null;
};
export type Material = IncidentSummary & { h1?: string | null; headline_template?: string | null; h1_template?: string | null };

const hostOf = (u?: string | null) => { try { return u ? new URL(u).hostname : null; } catch { return null; } };

/** `GET /incidents/{id}` answers with the full incident (landing.title, …) or a summary; normalise both. */
export function toMaterial(raw: unknown, id?: string | null): Material | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const d = raw as Detail;
  const src = (d.source && typeof d.source === 'object' ? d.source : {}) as { captured_at?: string | null; type?: string };
  const l = d.landing ?? {};
  return {
    ...(raw as IncidentSummary),
    id: d.id ?? id ?? '',
    source: typeof d.source === 'string' ? d.source : src.type ?? '',
    title: d.title?.trim() || l.title?.trim() || d.ad?.video_title?.trim() || null,
    h1: l.h1 ?? null,
    domain: d.domain ?? l.host ?? l.etld1 ?? hostOf(l.final_url ?? l.entry_url) ?? d.ad?.display_link ?? null,
    captured_at: d.captured_at ?? src.captured_at ?? null,
    headline_template: d.content?.headline_template ?? null,
    h1_template: d.content?.h1_template ?? null,
  };
}

/** The engine compares templates lower-cased; show the material's own template (original casing, `{PER}` slot kept). */
export function restoreTemplateCase<T extends { field: string; value: string; display: string }>(e: T, m?: Material | null): T {
  const t = /h1_template/.test(e.field) ? m?.h1_template : /headline_template/.test(e.field) ? m?.headline_template : null;
  if (!t || t.toLowerCase() !== e.value.toLowerCase()) return e;
  const i = e.display.indexOf(': ');
  return { ...e, display: (i > 0 ? e.display.slice(0, i + 2) : '') + t };
}

/** Display title of a material: page title / headline as captured (original casing), else domain, else id. */
export const materialTitle = (inc?: { id?: string; title?: string | null; domain?: string | null } | null, fallbackId?: string) =>
  inc?.title?.trim() || inc?.domain || inc?.id || fallbackId || '';
