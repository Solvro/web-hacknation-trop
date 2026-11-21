'use client';
import { useState } from 'react';
import s from '../sprawdz.module.css';
import { report, type CheckResult } from './api';

const WARN = 'M12 3l10 18H2zM12 10v5M12 18v.01';

function Icon({ d, cls }: { d: string; cls: string }) {
  return (
    <span className={`${s.ico} ${cls}`} aria-hidden="true">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
    </span>
  );
}

const SIGNS = [
  'Znana osoba „poleca” inwestycję, lek albo nagle „przerywa milczenie”.',
  'Strona wygląda jak portal informacyjny, ale adres jest dziwny lub nowy.',
  'Obietnica szybkiego zysku albo „ostatnie sztuki” i presja czasu.',
  'Formularz prosi o telefon, a „konsultant” ma oddzwonić.',
];

export function ResultCard({ result, source }: { result: CheckResult; source: string }) {
  const [state, setState] = useState<'idle' | 'busy' | 'done' | 'error'>('idle');
  const [id, setId] = useState('');

  async function send(note: string) {
    setState('busy');
    try {
      const a = await report({ url: /^https?:/i.test(source) ? source : undefined, note });
      setId(a.report_id);
      setState('done');
    } catch {
      setState('error');
    }
  }

  const status = (
    <>
      {state === 'done' && <span className={s.ack} role="status">Dziękujemy, zgłoszenie przyjęte ({id}).</span>}
      {state === 'error' && <p className={s.err} role="alert">Nie udało się wysłać zgłoszenia. Spróbuj ponownie.</p>}
    </>
  );

  if (result.verdict === 'scam') {
    const c = result.public_campaign;
    return (
      <article className={`${s.res} ${s.scam}`}>
        <div className={s.head}>
          <Icon d={WARN} cls={s.icoRed} />
          <div className={s.headTxt}>
            <h2>To wygląda na znane oszustwo</h2>
            {c && <p style={{ fontSize: 17, margin: 0 }}>Pasuje do kampanii <b>{`„${c.name.replace(/[„”]/g, "")}”`}</b>.</p>}
            {c && <p className={s.muted}>Widzieliśmy {c.seen_count} podobnych reklam od {c.since}.</p>}
          </div>
        </div>
        <div className={s.cols}>
          {c && c.reasons.length > 0 && (
            <div className={s.col}>
              <h3>Dlaczego tak uważamy</h3>
              <ol>{c.reasons.map((r) => <li key={r}>{r}</li>)}</ol>
            </div>
          )}
          <div className={s.col}>
            <h3>Co zrobić teraz</h3>
            <ul>
              {(result.advice.length ? result.advice : ['Nie klikaj w link i nie podawaj danych.']).map((a) => <li key={a}>{a}</li>)}
            </ul>
          </div>
        </div>
        <div className={s.row}>
          <button type="button" className={`${s.btn} ${s.btnp}`} disabled={state === 'busy' || state === 'done'} onClick={() => send('web: to wygląda na znane oszustwo')}>Zgłoś tę reklamę</button>
          {status}
        </div>
      </article>
    );
  }

  return (
    <article className={`${s.res} ${s.unk}`}>
      <div className={s.head}>
        <Icon d="M12 8v5M12 16v.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z" cls={s.icoCy} />
        <div className={s.headTxt}>
          <h2>Nie znamy tego materiału</h2>
          <p style={{ fontSize: 17, margin: 0 }}><b>To nie znaczy, że jest bezpieczny.</b> Nie pasuje do żadnej kampanii, którą już przeanalizowaliśmy.</p>
        </div>
      </div>
      <div className={s.col}>
        <h3>Sygnały ostrzegawcze, sprawdź sam</h3>
        <ul className={s.chk}>{SIGNS.map((t) => <li key={t}><span aria-hidden="true">✓</span>{t}</li>)}</ul>
        {result.advice.length > 0 && <ul>{result.advice.map((a) => <li key={a}>{a}</li>)}</ul>}
      </div>
      <div className={s.row}>
        <button type="button" className={`${s.btn} ${s.btnp}`} disabled={state === 'busy' || state === 'done'} onClick={() => send('web: do sprawdzenia przez analityka')}>Wyślij do sprawdzenia przez analityka</button>
        {status}
      </div>
    </article>
  );
}
