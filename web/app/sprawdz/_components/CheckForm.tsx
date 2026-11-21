'use client';
import { useRef, useState } from 'react';
import s from '../sprawdz.module.css';
import { check, type CheckResult } from './api';
import { ResultCard } from './ResultCard';

export function CheckForm() {
  const [url, setUrl] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [out, setOut] = useState<{ r: CheckResult; src: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const v = url.trim();
    if (!v && !file) { setError('Wklej link albo wgraj zrzut ekranu.'); return; }
    setError(''); setBusy(true); setOut(null);
    try {
      const looksUrl = /^https?:\/\//i.test(v) || /^[\w-]+(\.[\w-]+)+(\/|$)/.test(v);
      const r = await check({ url: looksUrl ? v : undefined, text: !looksUrl && v ? v : undefined, image: file });
      setOut({ r, src: v });
    } catch {
      setError('Nie udało się połączyć z serwerem. Spróbuj za chwilę.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <form className={s.form} aria-label="Sprawdź reklamę" onSubmit={submit}>
        <div>
          <label className={s.lbl} htmlFor="url">Link do reklamy lub tekst reklamy</label>
          <input className={s.inp} id="url" name="url" type="text" inputMode="url" autoComplete="off" placeholder="https://…" value={url} onChange={(e) => setUrl(e.target.value)} />
        </div>
        <div className={s.row}>
          <button className={`${s.btn} ${s.btnp}`} type="submit" disabled={busy}>{busy ? 'Sprawdzanie…' : 'Sprawdź'}</button>
          <span className={s.dim}>lub</span>
          <input ref={fileRef} className={s.file} id="shot" type="file" accept="image/*" aria-label="Wgraj zrzut ekranu" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <button className={s.btn} type="button" onClick={() => fileRef.current?.click()}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3M12 4v12M7 9l5-5 5 5" /></svg>
            Wgraj zrzut ekranu
          </button>
          {file && <span className={s.fname}>{file.name}</span>}
        </div>
        {error && <p className={s.err} role="alert">{error}</p>}
        <p className={s.dim}>Nie zapisujemy Twoich danych. Link i zrzut służą tylko do porównania; zrzuty kasujemy po 24 h.</p>
      </form>
      <div className={s.results} aria-live="polite" aria-label="Wynik sprawdzenia" style={{ padding: 0, marginTop: 8 }}>
        {out && <ResultCard result={out.r} source={out.src} />}
      </div>
    </>
  );
}
