'use client';
// Board 1 · Pole: the only zgrai-style screen. One field, sleeping bots around it.
import Link from 'next/link';
import { useState } from 'react';
import { JellyRoot } from '@/components/jelly';
import { CheckField } from '@/components/check-field';

export default function SprawdzPage() {
  const [wake, setWake] = useState(0);
  return (
    <JellyRoot mode="field" fieldState="asleep" wakeKey={wake} className="flex-1 flex min-h-[640px]">
      <main className="relative z-[1] flex-1 flex items-center justify-center px-4 sm:px-6 pt-4 pb-[120px]">
        <div data-jelly-clear className="w-full max-w-[680px] flex flex-col items-center gap-[26px] text-center">
          <div className="flex flex-col gap-3 items-center">
            <h1 className="m-0 text-[36px] sm:text-[48px] leading-[1.05] tracking-[-0.04em] font-semibold">Co sprawdzamy?</h1>
            <p className="m-0 max-w-[560px] text-[17px] leading-normal text-tx2">
              Wklej link, wrzuć zrzut albo wpisz ślad: domenę, piksel czy nazwisko. Boty pokażą, do której kampanii to należy i dlaczego.
            </p>
          </div>
          <CheckField onWake={() => setWake((w) => w + 1)} />
          <p className="text-[13px] text-tx3">
            Bez sieci? <Link className="underline decoration-line2 underline-offset-4 hover:text-tx1" href="/analiza/demo?replay=demo">Odtwórz nagraną analizę</Link>
          </p>
        </div>
      </main>
    </JellyRoot>
  );
}
