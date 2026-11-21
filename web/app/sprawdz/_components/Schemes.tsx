'use client';
import { useEffect, useState } from 'react';
import s from '../sprawdz.module.css';
import { schemes, type PublicCampaign } from './api';

export function Schemes() {
  const [items, setItems] = useState<PublicCampaign[] | null>(null);
  useEffect(() => { schemes().then(setItems).catch(() => setItems([])); }, []);
  if (items === null) return <p className={s.dim} role="status">Ładowanie…</p>;
  if (items.length === 0) return <p className={s.dim}>Nie udało się pobrać listy schematów.</p>;
  return (
    <div className={s.grid}>
      {items.map((c) => (
        <article key={c.name} className={s.card}>
          <div className={s.cnt}>
            <span className={s.num}>{c.seen_count}</span>
            <span className={s.numl}>{c.seen_count === 1 ? 'zgłoszona reklama' : 'zgłoszonych reklam'}<br />od {c.since}</span>
          </div>
          <h3>{c.name}</h3>
          {c.reasons.length > 0 && (
            <>
              <p><b style={{ color: 'var(--tx)' }}>Dlaczego łączymy te reklamy</b></p>
              <ul className={s.rs}>{c.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
            </>
          )}
        </article>
      ))}
    </div>
  );
}
