import type { Metadata } from 'next';
import s from './sprawdz.module.css';
import { CheckForm } from './_components/CheckForm';
import { Schemes } from './_components/Schemes';

export const metadata: Metadata = {
  title: 'Sprawdź reklamę, zanim klikniesz · TROP',
  description: 'Wklej link lub zrzut reklamy. Porównamy ją ze znanymi kampaniami oszustw.',
};

const STEPS = [
  ['1', 'Wklej link lub zrzut', 'Wystarczy adres z reklamy albo zdjęcie ekranu telefonu.'],
  ['2', 'Porównujemy wzorce', 'Szukamy wspólnych śladów z przeanalizowanymi kampaniami: wyglądu, tekstu i technicznych odcisków strony.'],
  ['3', 'Wynik i zgłoszenie', 'Dostajesz ocenę z uzasadnieniem. Twoje zgłoszenie pomaga zablokować całą kampanię, a nie jedną reklamę.'],
];

export default function SprawdzPage() {
  return (
    <div className={s.root}>
      <a className={s.skip} href="#main-sprawdz">Przejdź do treści</a>
      <header className={s.header}>
        <div className={`${s.wrap} ${s.row} ${s.between}`}>
          <a className={s.brand} href="/sprawdz" aria-label="TROP, Sprawdź reklamę">
            <svg width="30" height="30" viewBox="0 0 28 28" aria-hidden="true"><g transform="rotate(-40 14 14)"><rect x="3" y="9" width="22" height="10" rx="5" fill="none" stroke="#3BF07E" strokeWidth="1.5" /><path d="M8 9h6v10H8a5 5 0 0 1 0-10z" fill="#FF5D6C" /></g></svg>
            TROP
          </a>
          <nav className={s.nav} aria-label="Menu strony publicznej">
            <a className={s.navl} href="#jak">Jak to działa</a>
            <a className={s.navl} href="#schematy">Schematy tygodnia</a>
          </nav>
        </div>
      </header>

      <main id="main-sprawdz">
        <section className={s.hero}>
          <div className={s.wrap}>
            <span className={s.eb}>follow the fake</span>
            <h1 className={s.big}>Sprawdź reklamę, zanim klikniesz.</h1>
            <p className={s.lead}>Wklej link z reklamy albo wgraj jej zrzut ekranu. Porównamy ją z tysiącami przeanalizowanych reklam oszustów i powiemy, czy pasuje do znanej kampanii.</p>
            <CheckForm />
          </div>
        </section>

        <section id="schematy" className={`${s.wrap} ${s.sec}`}>
          <h2>Schematy tego tygodnia</h2>
          <Schemes />
        </section>

        <section id="jak" className={`${s.wrap} ${s.sec}`}>
          <h2>Jak to działa</h2>
          <div className={s.steps}>
            {STEPS.map(([n, t, d]) => (
              <div key={n} className={s.step}><span className={s.stepn} aria-hidden="true">{n}</span><h3>{t}</h3><p>{d}</p></div>
            ))}
          </div>
        </section>

        <section className={`${s.wrap} ${s.sec}`}>
          <div className={s.panel}>
            <div>
              <h2>Wtyczka oznaczy takie reklamy za Ciebie</h2>
              <p className={s.muted} style={{ fontSize: 15 }}>Działa w przeglądarce, wysyła tylko anonimowy odcisk reklamy.</p>
            </div>
          </div>
        </section>
      </main>

      <footer className={s.footer}>
        <div className={`${s.wrap} ${s.row} ${s.between}`}>
          <span className={s.dim}>TROP, projekt hackathonowy HackNation 2026</span>
          <span className={s.dim}>Brak dopasowania nigdy nie oznacza, że reklama jest bezpieczna.</span>
        </div>
      </footer>
    </div>
  );
}
