'use client';
// Chunked uploads for large materials (production proxies cut requests longer than ~60 s):
//   POST /uploads {name, size, kind:'zip'|'files', n_files?} → {upload_id, chunk_size}
//   PUT  /uploads/{id}/chunks/{n}   raw bytes (zip) or multipart `files` with relative paths (folder / several files)
//   POST /uploads/{id}/complete {mode:'analyze'|'batch'} → {job_id[, batch]}
// Chunks go one after another, each retried up to 3 times. Anything ≤ 20 MB keeps the single multipart POST.
import { API, ApiError, apiPost } from './api';

export const CHUNKED_ABOVE = 20 * 1024 * 1024;
const DEFAULT_CHUNK = 8 * 1024 * 1024;

export interface UploadItem { file: File; name: string }
export interface UploadDone { job_id: string | null; incident_id?: string | null; batch?: unknown }

export const totalSize = (items: UploadItem[]) => items.reduce((a, f) => a + f.file.size, 0);
export const needsChunks = (items: UploadItem[]) => totalSize(items) > CHUNKED_ABOVE;

async function putWithRetry(path: string, body: BodyInit, headers: Record<string, string>, tries = 3): Promise<void> {
  let last: unknown;
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(API + path, { method: 'PUT', body, headers });
      if (r.ok) return;
      last = new ApiError(r.status, `${r.status} ${path}`);
      if (r.status >= 400 && r.status < 500 && r.status !== 408 && r.status !== 429) break; // not worth retrying
    } catch (e) {
      last = e;
    }
    await new Promise((res) => setTimeout(res, 800 * (i + 1)));
  }
  throw last instanceof Error ? last : new ApiError(503, 'Wysyłanie przerwane');
}

/** Groups of files whose sizes add up to ≤ chunk (a single bigger file travels alone). */
function groups(items: UploadItem[], chunk: number): UploadItem[][] {
  const out: UploadItem[][] = [];
  let cur: UploadItem[] = [];
  let size = 0;
  for (const it of items) {
    if (cur.length && size + it.file.size > chunk) { out.push(cur); cur = []; size = 0; }
    cur.push(it); size += it.file.size;
  }
  if (cur.length) out.push(cur);
  return out;
}

/** Upload in chunks and start the analysis (or batch). `onProgress` gets 0..1 of bytes sent. */
export async function uploadChunked(items: UploadItem[], mode: 'analyze' | 'batch', onProgress?: (f: number) => void): Promise<UploadDone> {
  const total = totalSize(items) || 1;
  const zip = items.length === 1 && /\.zip$/i.test(items[0].name);
  const first = items[0]?.name ?? 'upload';
  const name = zip ? first : first.includes('/') ? first.split('/')[0] : first;
  const init = await apiPost<{ upload_id: string; chunk_size?: number }>('/uploads', { name, size: total, kind: zip ? 'zip' : 'files', n_files: items.length });
  const chunk = init.chunk_size || DEFAULT_CHUNK;
  const base = `/uploads/${encodeURIComponent(init.upload_id)}/chunks/`;
  let sent = 0;
  onProgress?.(0);
  if (zip) {
    const f = items[0].file;
    for (let n = 0, off = 0; off < f.size; n++, off += chunk) {
      const part = f.slice(off, Math.min(f.size, off + chunk));
      await putWithRetry(base + n, part, { 'content-type': 'application/octet-stream' });
      sent += part.size; onProgress?.(sent / total);
    }
  } else {
    const gs = groups(items, chunk);
    for (let n = 0; n < gs.length; n++) {
      const fd = new FormData();
      for (const it of gs[n]) fd.append('files', it.file, it.name);
      await putWithRetry(base + n, fd, { accept: 'application/json' });
      sent += gs[n].reduce((a, it) => a + it.file.size, 0); onProgress?.(sent / total);
    }
  }
  return apiPost<UploadDone>(`/uploads/${encodeURIComponent(init.upload_id)}/complete`, { mode });
}
