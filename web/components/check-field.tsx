'use client';
// The Sprawdź field (board 1, reused on board 14): link, file or a single trace.
import { useRouter } from 'next/navigation';
import { useRef, useState, type DragEvent } from 'react';
import { analyze } from '@/lib/api';
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

const CHIPS = [
  { key: 'img', label: 'Zdjęcie lub wideo', icon: IImage, accept: 'image/*,video/*' },
  { key: 'har', label: 'HAR lub ZIP', icon: IFile, accept: '.har,.zip,.json,application/zip,application/json' },
] as const;

export function CheckField({ initial = DEMO_URL, onWake, compact }: { initial?: string; onWake?: () => void; compact?: boolean }) {
  const router = useRouter();
  const [text, setText] = useState(initial);
  const [files, setFiles] = useState<File[]>([]);
  const [traceMode, setTraceMode] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
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
      const [res] = await Promise.all([
        // files win: never send the text field along with an upload
        analyze(files.length ? { files } : { url: (parsed as { url: string }).url }),
        new Promise((r) => setTimeout(r, 900)),
      ]);
      if (!res.job_id) { router.push(`/slad/domena/${encodeURIComponent(text.trim())}`); return; }
      const q = new URLSearchParams();
      if (res.incident_id) q.set('inc', res.incident_id);
      q.set('in', files.length ? files.map((f) => f.name).join(', ') : text.trim());
      router.push(`/analiza/${encodeURIComponent(res.job_id)}?${q}`);
    } catch (e) {
      setErr('Nie udało się wysłać materiału: ' + (e as Error).message);
      setBusy(false);
    }
  }

  function addFiles(list: FileList | null) {
    if (!list?.length) return;
    const picked = Array.from(list); // copy now: the input is cleared right after onChange
    setFiles((f) => [...f, ...picked]);
  }
  function onDrop(e: DragEvent) { e.preventDefault(); setDrag(false); addFiles(e.dataTransfer.files); }

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
          {files.map((f, i) => (
            <li key={i} className="inline-flex items-center gap-1 h-8 pl-3 pr-1 rounded-full bg-bg3 text-[13px] font-mono">
              {f.name}
              <button type="button" aria-label={`Usuń ${f.name}`} onClick={() => setFiles((x) => x.filter((_, j) => j !== i))}
                className="w-7 h-7 rounded-full inline-flex items-center justify-center hover:bg-bg4"><IX width={12} height={12} /></button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2.5 pt-1.5">
        <div className="flex flex-wrap gap-1.5">
          {CHIPS.map((c) => (
            <span key={c.key}>
              <button type="button" className="chip" onClick={() => inputs.current[c.key]?.click()}>
                <c.icon width={14} height={14} />{c.label}
              </button>
              <input ref={(el) => { inputs.current[c.key] = el; }} type="file" accept={c.accept} multiple className="hidden"
                aria-label={c.label} onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }} />
            </span>
          ))}
          <button type="button" className="chip" aria-pressed={traceMode}
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
          {busy ? 'Budzę boty…' : 'Sprawdź'}<IArrow />
        </button>
      </div>
      {err && <p id="rp-err" role="alert" className="text-[13px] text-state-red">{err}</p>}
    </form>
  );
}
