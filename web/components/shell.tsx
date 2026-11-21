'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useHealth } from '@/lib/api';

const TABS = [
  { href: '/', label: 'Sprawdź', match: (p: string) => p === '/' || p.startsWith('/analiza') || p.startsWith('/slad') },
  { href: '/kampanie', label: 'Kampanie', match: (p: string) => p.startsWith('/kampanie') },
  { href: '/sledztwa', label: 'Śledztwa', match: (p: string) => p.startsWith('/sledztwa') },
];

export function Logo() {
  return (
    <Link href="/" aria-label="trop, strona główna" className="inline-flex items-baseline text-[24px] font-bold tracking-[-0.04em] text-tx1 no-underline">
      <span className="px-[9px] pb-0.5 rounded-[9px] bg-tx1 text-white tracking-[-0.03em]">trop</span>
    </Link>
  );
}

export function ModePill() {
  const { health, offline, demo, down } = useHealth();
  if (down) return <span className="pill bg-state-rdim text-state-red" role="status"><span className="w-2 h-2 rounded-full bg-state-red" />API niedostępne</span>;
  if (!health || !demo) return <span className="w-[120px]" aria-hidden="true" />;
  return (
    <span className="pill bg-state-adim text-state-amber" title={offline ? 'Tryb offline: lokalne dane demonstracyjne' : 'API w trybie demonstracyjnym'}>
      <span className="w-2 h-2 rounded-full bg-[#F59E0B]" />demo · dane fikcyjne{offline ? ' · offline' : ''}
    </span>
  );
}

export function Header() {
  const path = usePathname() || '/';
  const onPole = path === '/';
  return (
    <header className={'relative z-[4] border-b ' + (onPole ? 'border-transparent' : 'border-bg4')}>
      <div data-jelly-clear className="max-w-[1240px] mx-auto px-4 sm:px-6 py-4 flex flex-wrap items-center gap-x-6 gap-y-3">
        <Logo />
        <nav aria-label="Sekcje" className="flex-1 flex flex-wrap justify-center gap-0.5 order-3 sm:order-none w-full sm:w-auto">
          {TABS.map((t) => {
            const on = t.match(path);
            return (
              <Link key={t.href} href={t.href} aria-current={on ? 'page' : undefined}
                className={'inline-flex items-center min-h-[38px] px-3.5 rounded-full text-[14px] font-medium no-underline transition-colors ' +
                  (on ? 'bg-bg4 text-tx1 font-semibold' : 'text-tx2 hover:bg-bg3 hover:text-tx1')}>
                {t.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto sm:ml-0"><ModePill /></div>
      </div>
    </header>
  );
}

export function Footer() {
  const { demo } = useHealth();
  return (
    <footer className="relative z-[4] mt-auto border-t border-bg4">
      <div className="max-w-[1240px] mx-auto px-4 sm:px-6 py-5 flex flex-wrap gap-x-6 gap-y-1 justify-between text-[12.5px] text-tx3">
        <span>TROP · follow the fake · HackNation 2026 · zadanie NASK „Kolekcjoner fejków”</span>
        <span>{demo ? 'Tryb demo: wszystkie dane są fikcyjne.' : 'TROP niczego nie wysyła sam: zgłoszenia przygotowujesz i eksportujesz Ty.'}</span>
      </div>
    </footer>
  );
}
