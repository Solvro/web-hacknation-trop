'use client';
// Board 7 · Zgłoszenie: one package for the whole campaign. Nothing is ever really sent: the package is prepared,
// exported and logged (ActPackage.disclaimer). The UI says so before and after "Wyślij".

import { useParams, useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import type { ActPackage, Campaign } from '@/lib/contracts';
import { API, apiGet, apiPost, isOffline, useApi } from '@/lib/api';
import { BOT_BY_KEY, n, plural } from '@/lib/copy';
import { campaignTitle } from '@/lib/graph';
import { Bot, JellyRoot } from '@/components/jelly';
import { ReportHeader } from '@/components/analysis/report';
import { Crumbs, Loading, Page } from '@/components/ui';
import { IArrow } from '@/components/icons';

const RECIPIENTS = [
  { id: 'meta_dsa', l: 'M', label: 'Meta · zgłoszenie DSA art. 16', sub: 'usunięcie reklam i zablokowanie kont reklamodawców', on: true },
  { id: 'certpl', l: 'C', label: 'CERT PL · lista ostrzeżeń', sub: 'blokada domen w polskich sieciach', on: true },
  { id: 'google', l: 'G', label: 'Google Safe Browsing', sub: 'ostrzeżenie w przeglądarkach', on: true },
  { id: 'registrar', l: 'R', label: 'Rejestrator · abuse', sub: 'odpowiada rzadko, domyślnie wyłączony', on: false },
];

function localDraft(c: Campaign): ActPackage {
  const cnt = c.counts ?? {};
  return {
    id: 'ACT-local', kind: 'bundle', campaign_id: c.id, status: 'draft', created_at: new Date().toISOString(),
    contents: { ads: c.n_incidents ?? 0, advertisers: cnt.advertisers ?? 0, domains: c.n_domains ?? 0, evidence_items: 64 },
    recipients: [], formats: ['pdf', 'stix'],
    parts: [
      { key: 'ads', label: `${plural(c.n_incidents ?? 0, 'reklama', 'reklamy', 'reklam')} z linkami do Ad Library i zrzutami`, bot: 'zwiadowca', count: c.n_incidents },
      { key: 'advertisers', label: `${plural(cnt.advertisers ?? 0, 'konto', 'konta', 'kont')} reklamodawców z historią reklam`, bot: 'archiwista', count: cnt.advertisers ?? 0 },
      { key: 'domains', label: `${plural(c.n_domains ?? 0, 'domena', 'domeny', 'domen')} z certyfikatami i datami`, bot: 'notariusz', count: c.n_domains },
      { key: 'traces', label: 'Ślady, które łączą reklamy: bramka CAPI i kit', bot: 'tropiciel', count: 2 },
      { key: 'stix', label: 'Uzasadnienie i plik STIX 2.1 dla CERT PL', bot: 'sedzia', count: 'STIX' },
    ],
    notice_text: `Zgłoszenie na podstawie art. 16 DSA.\n\nZgłaszamy ${plural(c.n_incidents ?? 0, 'reklamę', 'reklamy', 'reklam')} z ${plural(cnt.advertisers ?? 0, 'konta', 'kont', 'kont')} reklamodawców. Wszystkie należą do jednej kampanii oszustwa ${campaignTitle(c)} (${c.id}).\n\n${c.narrative ?? ''}\n\nWspólne ślady: ta sama bramka konwersji, ten sam zestaw stron i ten sam szablon tekstu. Lista reklam, adresów i dowodów jest w załączniku.`,
    disclaimer: 'Nic nie zostało wysłane — pakiet przygotowany i wyeksportowany.',
  };
}

export default function ZgloszeniePage() {
  const { id: raw } = useParams<{ id: string }>();
  const id = decodeURIComponent(raw);
  const router = useRouter();
  const { data: c } = useApi<Campaign>(`/campaigns/${encodeURIComponent(id)}`);
  const [pkg, setPkg] = useState<ActPackage | null>(null);
  const [rec, setRec] = useState<Record<string, boolean>>(Object.fromEntries(RECIPIENTS.map((r) => [r.id, r.on])));
  const [text, setText] = useState('');
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [fail, setFail] = useState<string | null>(null);
  const [sendErr, setSendErr] = useState<string | null>(null);
  const dlg = useRef<HTMLDialogElement>(null);

  const asked = useRef(false);
  useEffect(() => {
    if (!c || pkg || asked.current) return;
    asked.current = true;
    (async () => {
      // one draft per campaign: reuse the newest draft, create only when there is none
      const drafts = isOffline() ? [] : await apiGet<ActPackage[]>(`/act/packages?campaign_id=${encodeURIComponent(c.id)}&status=draft`).catch(() => [] as ActPackage[]);
      const mine = (Array.isArray(drafts) ? drafts : []).filter((p) => p.campaign_id === c.id && p.status === 'draft')
        .sort((a, b) => String(b.created_at ?? '').localeCompare(String(a.created_at ?? '')));
      const p = mine[0] ?? await apiPost<ActPackage>('/act/packages', { campaign_id: c.id, kind: 'bundle', recipients: ['meta_dsa', 'certpl', 'google'] }, () => localDraft(c));
      setPkg(p); setText(p.notice_text ?? '');
    })().catch((e: Error) => { asked.current = false; setFail(e.message); });
  }, [c, pkg]);

  if (fail) return (
    <Page>
      <Crumbs items={[{ label: 'Kampanie', href: '/kampanie' }, { label: id, href: `/kampanie/${id}` }, { label: 'Nowe zgłoszenie' }]} />
      <div className="rounded-[22px] border border-dashed border-line2 bg-bg2 p-8 text-center flex flex-col items-center gap-2">
        <b className="text-[17px]">Nie udało się przygotować pakietu</b>
        <span className="text-[14px] text-tx3 max-w-[520px]">Serwer odpowiedział: {fail}. Spróbuj ponownie za chwilę.</span>
        <button type="button" className="btn-sec btn-sm mt-2" onClick={() => { setFail(null); setPkg(null); }}>Spróbuj ponownie</button>
      </div>
    </Page>
  );
  if (!c || !pkg) return <Loading />;
  const nRec = Object.values(rec).filter(Boolean).length;
  const cnt = pkg.contents ?? {};
  const dom = (k: number) => plural(k, 'domena', 'domeny', 'domen');
  const countFor = (rid: string) => rid === 'meta_dsa' ? `${plural(cnt.ads ?? 0, 'reklama', 'reklamy', 'reklam')} · ${plural(cnt.advertisers ?? 0, 'konto', 'konta', 'kont')}` : rid === 'certpl' ? dom(cnt.certpl_new ?? cnt.domains ?? 0) : dom(cnt.domains ?? 0);
  const dl = (fmt: string) => (isOffline() || pkg.id === 'ACT-local' ? undefined : `${API}/act/packages/${pkg.id}/download?format=${fmt}`);

  async function send() {
    setBusy(true);
    const ok = await apiPost(`/act/packages/${pkg!.id}/submit`, { confirm: true, recipients: Object.keys(rec).filter((k) => rec[k]), notice_text: text }, () => ({ ...pkg, status: 'sent' }))
      .then(() => true).catch((e: Error) => { setSendErr(e.message); return false; });
    setBusy(false);
    if (ok) router.push(`/kampanie/${id}?zgloszono=1`);
  }

  return (
    <JellyRoot className="flex-1 flex flex-col">
      <Page>
        <Crumbs items={[{ label: 'Kampanie', href: '/kampanie' }, { label: c.id, href: `/kampanie/${c.id}` }, { label: 'Nowe zgłoszenie' }]} />
        <ReportHeader
          title="Zgłoś całą kampanię naraz"
          lead={`Każdy odbiorca dostaje jedno zgłoszenie ze wszystkimi reklamami i dowodami, zamiast ${plural(cnt.ads ?? c.n_incidents ?? 0, 'osobnego', 'osobnych', 'osobnych')}.`}
          meta={`${campaignTitle(c).length <= 28 ? `${c.id} ${campaignTitle(c)}` : c.id} · ${plural(cnt.ads ?? 0, 'reklama', 'reklamy', 'reklam')} · ${plural(cnt.domains ?? 0, 'domena', 'domeny', 'domen')} · ${plural(cnt.advertisers ?? 0, 'reklamodawca', 'reklamodawcy', 'reklamodawców')}`}
          primary={<button type="button" className="btn-pri" disabled={!nRec} onClick={() => { setConfirm(false); dlg.current?.showModal(); }}>Wyślij {nRec} {nRec === 1 ? 'zgłoszenie' : 'zgłoszenia'}<IArrow /></button>}
          secondary={<span className="text-[12.5px] text-tx3 max-w-[300px] sm:text-right">Demo: pakiet zostanie przygotowany i wyeksportowany, nic nie wyjdzie na zewnątrz.</span>}
        />
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_440px] gap-8 items-start">
          <div className="flex flex-col gap-6">
            <section aria-labelledby="z-to" className="flex flex-col gap-2.5">
              <h2 id="z-to" className="text-[16px] font-semibold">Do kogo</h2>
              {RECIPIENTS.map((r) => (
                <label key={r.id} className={'min-h-[68px] flex items-center gap-3 px-4 py-3 border rounded-[18px] cursor-pointer ' + (rec[r.id] ? 'border-line1 bg-bg1 shadow-soft' : 'border-line1 bg-bg2')}>
                  <input type="checkbox" checked={rec[r.id]} onChange={(e) => setRec({ ...rec, [r.id]: e.target.checked })} className="w-[18px] h-[18px] accent-black" />
                  <span aria-hidden="true" className="w-9 h-9 rounded-lg bg-bg3 inline-flex items-center justify-center text-[13px] font-semibold">{r.l}</span>
                  <span className="flex-1 min-w-0"><b className="block text-[14.5px] font-semibold">{r.label}</b><span className="text-[12.5px] text-tx3">{r.sub}</span></span>
                  <span className="hidden sm:block font-mono text-[12.5px] text-tx2">{countFor(r.id)}</span>
                </label>
              ))}
            </section>
            <section aria-labelledby="z-what" className="flex flex-col gap-2.5">
              <h2 id="z-what" className="text-[16px] font-semibold">Co wysyłamy</h2>
              {(pkg.parts ?? []).map((p, i) => {
                const b = BOT_BY_KEY[String(p.bot) as keyof typeof BOT_BY_KEY];
                return (
                  <div key={i} className="min-h-16 flex items-center gap-3 pl-3.5 pr-4 py-2.5 border border-line1 rounded-[18px] bg-bg1 shadow-soft">
                    {b && <Bot color={b.color} master={b.master} size={34} />}
                    <span className="flex-1 min-w-0"><b className="block text-[14.5px] font-semibold">{String(p.label)}</b><span className="text-[12.5px] text-tx3">przygotował {b?.name ?? 'bot'}{p.ready === false ? ' · w toku' : ''}</span></span>
                    {p.count != null && <b className="font-mono text-[14px]">{String(p.count)}</b>}
                  </div>
                );
              })}
            </section>
          </div>
          <aside className="bg-[#F6F6F6] rounded-panel p-5 flex flex-col gap-3">
            <div className="flex items-center gap-3"><Bot color="#0A0A0A" master size={36} /><span><b className="block text-[17px] font-semibold">Treść zgłoszenia</b><span className="text-[12.5px] text-tx3">napisał Sędzia · możesz poprawić</span></span></div>
            <label className="sr-only-x" htmlFor="z-text">Treść zgłoszenia</label>
            <textarea id="z-text" value={text} onChange={(e) => setText(e.target.value)} rows={14} className="w-full rounded-2xl border border-line1 bg-white p-4 text-[14px] leading-relaxed resize-y" />
            <div className="flex flex-wrap gap-2">
              {['pdf', 'json', 'stix', 'misp', 'csv', 'certpl'].map((f) => {
                const href = dl(f);
                return href ? <a key={f} href={href} className="btn-sec btn-sm">Pobierz {f === 'certpl' ? 'listę CERT PL' : f.toUpperCase()}</a>
                  : <button key={f} type="button" className="btn-sec btn-sm" onClick={() => { const b = new Blob([f === 'stix' ? JSON.stringify({ type: 'bundle', id: `bundle--${c.id}`, objects: [] }, null, 2) : text], { type: f === 'stix' ? 'application/json' : 'text/plain' }); const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = `${c.id}-zgloszenie.${f === 'stix' ? 'json' : 'txt'}`; a.click(); }}>Pobierz {f === 'certpl' ? 'listę CERT PL' : f.toUpperCase()}</button>;
              })}
            </div>
          </aside>
        </div>
      </Page>
      <dialog ref={dlg} className="rounded-[22px] p-0 backdrop:bg-black/40 max-w-[480px] w-[calc(100%-32px)]" aria-labelledby="z-dlg">
        <form method="dialog" className="p-6 flex flex-col gap-4">
          <h2 id="z-dlg" className="text-[20px] font-semibold">Przygotować {nRec} {nRec === 1 ? 'zgłoszenie' : 'zgłoszenia'}?</h2>
          <p className="text-[14px] text-tx2">To wersja demonstracyjna: <b>nic nie zostanie naprawdę wysłane</b>. TROP przygotuje pakiet, wyeksportuje pliki i zapisze go w kampanii jako wysłany.</p>
          <label className="flex items-center gap-2.5 text-[14px]"><input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} className="w-[18px] h-[18px] accent-black" />Sprawdziłem odbiorców i treść</label>
          <div className="flex gap-2 justify-end">
            <button type="submit" className="btn-sec btn-sm">Anuluj</button>
            {sendErr && <span role="alert" className="text-[13px] text-state-red self-center mr-auto">{sendErr}</span>}
            <button type="button" className="btn-pri btn-sm" disabled={!confirm || busy} onClick={send}>{busy ? 'Przygotowuję…' : 'Potwierdź'}</button>
          </div>
        </form>
      </dialog>
    </JellyRoot>
  );
}

