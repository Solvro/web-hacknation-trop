'use client';
// Data access: the API through the same-origin /api/v1 proxy. Nothing else.
// The fictional fixture layer (lib/mock) is used ONLY on explicit opt-in: build with NEXT_PUBLIC_MOCK=1, or open any
// page with `?offline=1` (kept for the browser session; `?offline=0` clears). Without opt-in, API errors surface as
// empty/error states — the app never shows fictional data next to real data.
import { useEffect, useState } from 'react';
import type { Health } from './contracts';
import { localAnalyze, resolveGet } from './mock/router';

export const FORCE_MOCK = process.env.NEXT_PUBLIC_MOCK === '1';
export const API = '/api/v1';

let optIn = FORCE_MOCK;
if (typeof window !== 'undefined') {
  try {
    const q = new URLSearchParams(window.location.search).get('offline');
    if (q === '1') sessionStorage.setItem('trop-offline', '1');
    if (q === '0') sessionStorage.removeItem('trop-offline');
    if (sessionStorage.getItem('trop-offline') === '1') optIn = true;
  } catch { /* storage blocked */ }
}
/** True only when the user explicitly asked for the offline fixture demo. */
export const isOffline = () => optIn;

function fixture<T>(path: string): T | undefined {
  const [p, qs] = path.split('?');
  return resolveGet(p, new URLSearchParams(qs ?? '')) as T | undefined;
}

export class ApiError extends Error {
  constructor(public status: number, msg: string) { super(msg); }
}

export async function apiGet<T>(path: string, opts: { signal?: AbortSignal } = {}): Promise<T> {
  if (optIn) {
    const fx = fixture<T>(path);
    if (fx === undefined) throw new ApiError(404, `brak danych: ${path}`);
    return fx;
  }
  let r: Response;
  try {
    r = await fetch(API + path, { signal: opts.signal, headers: { accept: 'application/json' }, cache: 'no-store' });
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new ApiError(503, 'Brak połączenia z API');
  }
  if (!r.ok) throw new ApiError(r.status, `${r.status} ${path}`);
  return (await r.json()) as T;
}

/** POST. `fallback` runs only in the explicit offline demo. */
export async function apiPost<T>(path: string, body: unknown, fallback?: () => T): Promise<T> {
  if (optIn) {
    if (fallback) return fallback();
    throw new ApiError(503, 'Tryb offline: ta akcja wymaga API');
  }
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
  let r: Response;
  try {
    r = await fetch(API + path, {
      method: 'POST', body: isForm ? (body as FormData) : JSON.stringify(body ?? {}),
      headers: isForm ? { accept: 'application/json' } : { 'content-type': 'application/json', accept: 'application/json' },
    });
  } catch {
    throw new ApiError(503, 'Brak połączenia z API');
  }
  if (!r.ok) {
    let msg = `${r.status} ${path}`;
    try { const j = await r.json(); if (j?.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail); } catch { /* not json */ }
    throw new ApiError(r.status, msg);
  }
  return (await r.json()) as T;
}

/** `names` = per-file upload names; for folders the relative path ("1/x_files/a.js"), which the API uses to rebuild it. */
export async function analyze(input: { url?: string; trace?: string; files?: File[]; names?: string[] }): Promise<{ job_id: string | null; incident_id?: string | null; trace?: unknown }> {
  const fd = new FormData();
  if (input.url) fd.append('url', input.url);
  if (input.trace) fd.append('trace', input.trace);
  (input.files ?? []).forEach((f, i) => fd.append('files', f, input.names?.[i] ?? f.name));
  const label = input.url ?? input.trace ?? (input.files ?? []).map((f) => f.name).join(' ');
  return apiPost('/analyze', fd, () => localAnalyze(label));
}

export function useApi<T>(path: string | null, deps: unknown[] = []): { data: T | undefined; error: Error | undefined; loading: boolean } {
  const [state, set] = useState<{ data: T | undefined; error: Error | undefined; loading: boolean }>({ data: undefined, error: undefined, loading: !!path });
  useEffect(() => {
    if (!path) { set({ data: undefined, error: undefined, loading: false }); return; }
    const ac = new AbortController();
    set((s) => ({ ...s, loading: true }));
    apiGet<T>(path, { signal: ac.signal })
      .then((data) => set({ data, error: undefined, loading: false }))
      .catch((error) => { if (error.name !== 'AbortError') set({ data: undefined, error, loading: false }); });
    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);
  return state;
}

/** API mode. `demo` = fictional data on screen (API in mock mode, or the explicit offline opt-in). */
export function useHealth(): { health: Health | undefined; offline: boolean; demo: boolean; down: boolean } {
  const { data, error } = useApi<Health>('/health');
  // read after mount so server and client render the same first frame
  const [off, setOff] = useState(false);
  useEffect(() => { setOff(isOffline()); }, [data, error]);
  return { health: data, offline: off, demo: off || data?.mode === 'mock', down: !!error && !off };
}
