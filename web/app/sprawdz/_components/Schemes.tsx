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
          <div className={s.row} style={{ flexWrap: 'nowrap' }}>
            <span className={s.sil} aria-hidden="true">
              <svg width="30" height="30" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="9" r="4.5" /><path d="M3 24c1-5.5 4.5-8 9-8s8 2.5 9 8z" /></svg>
            </span>
            <h3>{c.name}</h3>
          </div>
          <p><b style={{ color: 'var(--tx)' }}>Skala:</b> {c.seen_count} reklam od {c.since}.</p>
          {c.reasons.length > 0 && <p><b style={{ color: 'var(--tx)' }}>Jak rozpoznać:</b> {c.reasons.join('; ')}.</p>}
        </article>
      ))}
    </div>
  );
}
