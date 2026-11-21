'use client';
// The Sprawdź field (board 1, reused on board 14): link, file or a single trace.
import { useRouter } from 'next/navigation';
import { useRef, useState, type DragEvent } from 'react';
import { analyze, isOffline } from '@/lib/api';
import { needsChunks, uploadChunked } from '@/lib/upload';
import { IArrow, IFile, IImage, ISearch, IX } from './icons';
import { useTraceExamples } from '@/lib/examples';

export const DEMO_URL = 'https://morvanta.click/?utm_source=fb&utm_visit=0193a7c2-5b1e-7c3a-9f20-6d1e4b8a2c10';

export type Parsed =
  | { kind: 'url'; url: string }
  | { kind: 'trace'; type: 'domena' | 'piksel' | 'osoba' | 'kit'; value: string }
  | { kind: 'empty' };

export function parseInput(raw: string): Parsed {
  const s = raw.trim();
  if (!s) return { kind: 'empty' };
  if (/^https?:\/\//i.test(s) || /^[\w.-]+\.[a-z]{2,}\/\S*/i.test(s)) return { kind: 'url', url: /^https?:/i.test(s) ? s : `https://${s}` };
  if (/^\/[\w/{}.-]+$/.test(s)) return { kind: 'trace', type: 'kit', value: s };
  if (/^[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$/i.test(s)) return { kind: 'trace', type: 'domena', value: s.toLowerCase() };
  if (/^[\d\s]{10,20}$/.test(s)) return { kind: 'trace', type: 'piksel', value: s.replace(/\s/g, '') };
  return { kind: 'trace', type: 'osoba', value: s };
}

interface Picked { file: File; path: string }
const groupKey = (f: Picked) => (f.path.includes('/') ? `dir:${f.path.split('/')[0]}` : `file:${f.path}`);
function summary(files: Picked[]): { key: string; label: string }[] {
  const g = new Map<string, number>();
  for (const f of files) g.set(groupKey(f), (g.get(groupKey(f)) ?? 0) + 1);
  return [...g.entries()].map(([key, k]) => ({ key, label: key.startsWith('dir:') ? `Folder: ${key.slice(4)} · ${k} ${k === 1 ? 'plik' : k % 10 >= 2 && k % 10 <= 4 && (k % 100 < 10 || k % 100 >= 20) ? 'pliki' : 'plików'}` : key.slice(5) }));
}
/** Read a dropped folder recursively (File System Entries API), keeping relative paths. */
const junk = (name: string) => name.startsWith('.') || /^(thumbs\.db|desktop\.ini)$/i.test(name);
async function walk(entry: FileSystemEntry, prefix: string, out: Picked[]): Promise<void> {
  if (junk(entry.name)) return;
  if (entry.isFile) {
    const file = await new Promise<File>((res, rej) => (entry as FileSystemFileEntry).file(res, rej));
    out.push({ file, path: prefix + entry.name });
    return;
  }
  const reader = (entry as FileSystemDirectoryEntry).createReader();
  for (;;) {
    const batch = await new Promise<FileSystemEntry[]>((res, rej) => reader.readEntries(res, rej));
    if (!batch.length) break;
    for (const e of batch) await walk(e, `${prefix}${entry.name}/`, out);
  }
}

const CHIPS = [
  { key: 'img', label: 'Zdjęcie lub wideo', icon: IImage, accept: 'image/*,video/*' },
  { key: 'har', label: 'HAR lub ZIP', icon: IFile, accept: '.har,.zip,.json,application/zip,application/json' },
] as const;

export function CheckField({ initial = DEMO_URL, onWake, compact }: { initial?: string; onWake?: () => void; compact?: boolean }) {
  const router = useRouter();
  const [text, setText] = useState(initial);
  // each file keeps its path relative to a dropped / picked folder ("1/Zrzut ekranu.png", "1/x_files/a.js")
  const [files, setFiles] = useState<Picked[]>([]);
  const [traceMode, setTraceMode] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const inputs = useRef<Record<string, HTMLInputElement | null>>({});
  const ta = useRef<HTMLTextAreaElement>(null);
  const examples = useTraceExamples();
  const exIdx = useRef(0);

  async function go() {
    setErr(null);
    const parsed = parseInput(text);
    if (!files.length && parsed.kind === 'empty') { setErr('Wklej link, dodaj plik albo wpisz ślad.'); ta.current?.focus(); return; }
    if (!files.length && parsed.kind === 'trace') {
      router.push(`/slad/${parsed.type}/${encodeURIComponent(parsed.value)}`);
      return;
    }
    setBusy(true);
    onWake?.();
    try {
      const items = files.map((f) => ({ file: f.file, name: f.path }));
      // large uploads (> 20 MB) go in 8 MiB chunks so no single request outlives the proxy timeout
      const big = items.length > 0 && needsChunks(items) && !isOffline();
      const [res] = await Promise.all([
        // files win: never send the text field along with an upload
        big ? uploadChunked(items, 'analyze', setProgress)
          : analyze(files.length ? { files: files.map((f) => f.file), names: files.map((f) => f.path) } : { url: (parsed as { url: string }).url }),
        new Promise((r) => setTimeout(r, 900)),
      ]);
      if (!res.job_id) { router.push(`/slad/domena/${encodeURIComponent(text.trim())}`); return; }
      const q = new URLSearchParams();
      if (res.incident_id) q.set('inc', res.incident_id);
      q.set('in', files.length ? summary(files).map((g) => g.label).join(', ') : text.trim());
      router.push(`/analiza/${encodeURIComponent(res.job_id)}?${q}`);
    } catch (e) {
      setErr('Nie udało się wysłać materiału: ' + (e as Error).message);
      setBusy(false); setProgress(null);
    }
  }

  function addFiles(list: FileList | null) {
    if (!list?.length) return;
    // copy now: the input is cleared right after onChange. webkitRelativePath is set for folder picks.
    const picked = Array.from(list).map((f) => ({ file: f, path: (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name }))
      .filter((f) => !f.path.split('/').some(junk));
    setFiles((f) => [...f, ...picked]);
  }
  async function onDrop(e: DragEvent) {
    e.preventDefault(); setDrag(false);
    const items = Array.from(e.dataTransfer.items ?? []);
    const entries = items.map((it) => (it.kind === 'file' ? it.webkitGetAsEntry?.() : null)).filter(Boolean) as FileSystemEntry[];
    if (entries.some((x) => x.isDirectory)) {
      const out: Picked[] = [];
      for (const en of entries) await walk(en, '', out);
      setFiles((f) => [...f, ...out]);
    } else addFiles(e.dataTransfer.files);
  }

  return (
    <form
      className={'card w-full p-[18px] pb-3.5 flex flex-col gap-2.5 text-left transition-shadow ' + (drag ? 'ring-2 ring-tx1' : '')}
      onSubmit={(e) => { e.preventDefault(); go(); }}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
    >
      <label htmlFor="rp-in" className="text-[13px] font-medium text-tx3">Link, plik albo ślad</label>
      <textarea
        id="rp-in" ref={ta} rows={compact ? 1 : 2} value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); go(); } }}
        placeholder={traceMode ? 'domena, piksel albo imię i nazwisko' : 'https://… albo przeciągnij plik'}
        className="border-0 outline-none resize-none p-0 font-mono text-[16px] leading-[1.55] text-tx1 bg-transparent focus-visible:outline-none"
        aria-describedby={err ? 'rp-err' : undefined}
      />
      {files.length > 0 && (
        <ul className="flex flex-wrap gap-1.5" aria-label="Dodane pliki">
          {summary(files).map((g) => (
            <li key={g.key} className="inline-flex items-center gap-1 h-8 pl-3 pr-1 rounded-full bg-bg3 text-[13px] font-mono max-w-full">
              <span className="truncate">{g.label}</span>
              <button type="button" aria-label={`Usuń ${g.label}`} onClick={() => setFiles((x) => x.filter((f) => groupKey(f) !== g.key))}
                className="w-7 h-7 flex-none rounded-full inline-flex items-center justify-center hover:bg-bg4"><IX width={12} height={12} /></button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap md:flex-nowrap items-center justify-between gap-2 pt-1.5">
        <div className="flex flex-wrap md:flex-nowrap gap-1.5 min-w-0">
          {CHIPS.map((c) => (
            <span key={c.key}>
              <button type="button" className="chip whitespace-nowrap" onClick={() => inputs.current[c.key]?.click()}>
                <c.icon width={14} height={14} />{c.label}
              </button>
              <input ref={(el) => { inputs.current[c.key] = el; }} type="file" accept={c.accept} multiple className="hidden"
                aria-label={c.label} onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }} />
            </span>
          ))}
          <span>
            <button type="button" className="chip whitespace-nowrap" onClick={() => inputs.current.dir?.click()}>
              <IFile width={14} height={14} />Wybierz folder
            </button>
            <input ref={(el) => { inputs.current.dir = el; if (el) { el.setAttribute('webkitdirectory', ''); el.setAttribute('directory', ''); } }} type="file" multiple className="hidden"
              aria-label="Wybierz folder" onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }} />
          </span>
          <button type="button" className="chip whitespace-nowrap" aria-pressed={traceMode}
            onClick={() => {
              // fill the field with a real trace from the database (cycles through a few on repeated clicks)
              setTraceMode(true); setFiles([]); setErr(null);
              if (examples.length) { setText(examples[exIdx.current % examples.length]); exIdx.current += 1; } else setText('');
              ta.current?.focus();
            }}>
            <ISearch width={14} height={14} />Domena lub osoba
          </button>
        </div>
        <button type="submit" className="btn-pri" disabled={busy}>
          {progress != null && progress < 1 ? `Wysyłanie ${Math.round(progress * 100)}%` : busy ? 'Budzę boty…' : 'Sprawdź'}<IArrow />
        </button>
      </div>
      {progress != null && (
        <div role="progressbar" aria-label="Wysyłanie" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)} className="h-1.5 rounded-full bg-bg4 overflow-hidden">
          <i className="block h-full bg-tx1 transition-[width] duration-300" style={{ width: `${Math.round(progress * 100)}%` }} />
        </div>
      )}
      {err && <p id="rp-err" role="alert" className="text-[13px] text-state-red">{err}</p>}
    </form>
  );
}
