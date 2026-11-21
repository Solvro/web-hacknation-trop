'use client';
// Data access: real API through the same-origin /api/v1 proxy, with the typed fixture layer (lib/mock) as fallback.
// NEXT_PUBLIC_MOCK=1 forces the fixtures (offline demo without any backend).
import { useEffect, useState } from 'react';
import type { Health } from './contracts';
import { localAnalyze, resolveGet } from './mock/router';

export const FORCE_MOCK = process.env.NEXT_PUBLIC_MOCK === '1';
export const API = '/api/v1';

/** Remember that the API is down so we stop waiting on it for every call (reset on reload). */
let apiDown = FORCE_MOCK;
export const isOffline = () => apiDown;

function fixture<T>(path: string): T | undefined {
  const [p, qs] = path.split('?');
  return resolveGet(p, new URLSearchParams(qs ?? '')) as T | undefined;
}

export class ApiError extends Error {
  constructor(public status: number, msg: string) { super(msg); }
}

export async function apiGet<T>(path: string, opts: { signal?: AbortSignal } = {}): Promise<T> {
  if (!apiDown) {
    try {
      const r = await fetch(API + path, { signal: opts.signal, headers: { accept: 'application/json' }, cache: 'no-store' });
      if (r.ok) return (await r.json()) as T;
      if (r.status === 502 || r.status === 503 || r.status === 504) apiDown = true;
      const fx = fixture<T>(path);
      if (fx !== undefined) return fx;
      throw new ApiError(r.status, `${r.status} ${path}`);
    } catch (e) {
      if ((e as Error).name === 'AbortError') throw e;
      if (e instanceof ApiError) throw e;
      apiDown = true;
    }
  }
  const fx = fixture<T>(path);
  if (fx === undefined) throw new ApiError(404, `brak danych: ${path}`);
  return fx;
}

export async function apiPost<T>(path: string, body: unknown, fallback?: () => T): Promise<T> {
  if (!apiDown) {
    try {
      const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
      const r = await fetch(API + path, {
        method: 'POST', body: isForm ? (body as FormData) : JSON.stringify(body ?? {}),
        headers: isForm ? { accept: 'application/json' } : { 'content-type': 'application/json', accept: 'application/json' },
      });
      if (r.ok) return (await r.json()) as T;
      if (r.status >= 502) apiDown = true;
      if (fallback) return fallback();
      throw new ApiError(r.status, `${r.status} ${path}`);
    } catch (e) {
      if (e instanceof ApiError) throw e;
      apiDown = true;
    }
  }
  if (fallback) return fallback();
  throw new ApiError(503, 'API niedostępne');
}

export async function analyze(input: { url?: string; trace?: string; files?: File[] }): Promise<{ job_id: string | null; incident_id?: string | null }> {
  const fd = new FormData();
  if (input.url) fd.append('url', input.url);
  if (input.trace) fd.append('trace', input.trace);
  for (const f of input.files ?? []) fd.append('files', f, f.name);
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

export function useHealth(): { health: Health | undefined; offline: boolean } {
  const { data } = useApi<Health>('/health');
  return { health: data, offline: isOffline() };
}
