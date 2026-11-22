'use client';
// Boards 9 (investigation in progress, tree growing from SSE) and 10 (finished: what gets added).
import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useCallback, useMemo, useState } from 'react';
import type { Campaign, Event, Investigation, InvestigationNode, InvestigationStep } from '@/lib/contracts';
import { apiPost, isOffline, useApi } from '@/lib/api';
import { BOT_BY_KEY, botName, n, plural } from '@/lib/copy';
import { useEventStream } from '@/lib/stream';
import { investigationEvents } from '@/lib/mock/kampanie';
import { Bot, JellyRoot } from '@/components/jelly';
import { ReportHeader } from '@/components/analysis/report';
import { Card, Crumbs, Loading, Page } from '@/components/ui';
import { IArrow, ICheck } from '@/components/icons';

const BRANCHES = [
  { k: 'crtsh', label: 'crt.sh', sub: 'ta sama nocna partia', bot: 'notariusz' },
  { k: 'urlscan', label: 'urlscan', sub: 'ten sam kit', bot: 'tropiciel' },
  { k: 'adlib', label: 'Ad Library', sub: 'ci sami reklamodawcy', bot: 'zwiadowca' },
  { k: 'certpl', label: 'CERT PL', sub: 'lista ostrzeżeń', bot: 'notariusz' },
  { k: 'db', label: 'nasza baza', sub: 'podobne materiały w bazie', bot: 'archiwista' },
  { k: 'content', label: 'treść', sub: 'czyta nowe strony', bot: 'czytelnik' },
] as const;
const TOOL_BOT: Record<string, string> = { crtsh: 'notariusz', dns: 'notariusz', certpl: 'notariusz', urlscan: 'tropiciel', adlibrary: 'zwiadowca', db: 'archiwista', engine: 'czytelnik', oracle: 'archiwista' };
const STRIP = [
  { bot: 'sedzia', sub: 'prowadzi' }, { bot: 'notariusz', sub: 'crt.sh, CERT PL' }, { bot: 'tropiciel', sub: 'urlscan' },
  { bot: 'zwiadowca', sub: 'Ad Library' }, { bot: 'archiwista', sub: 'nasza baza' }, { bot: 'czytelnik', sub: 'czyta strony…' },
] as const;
const HIDDEN_KINDS = new Set(['cert', 'ip', 'source']);

interface S { nodes: InvestigationNode[]; steps: InvestigationStep[]; decision: { node_id: string; question: string; options: string[] } | null; done: string | null; text: string }

function Pill({ nd }: { nd: InvestigationNode }) {
  const st = nd.status;
  const amber = (nd.meta as { tone?: string } | undefined)?.tone === 'amber' || nd.kind === 'list_status';
  const cls = amber ? 'bg-[#FFF4E5] border-[#FCD9A8] text-[#9A3412] font-sans font-medium'
    : st === 'in_campaign' ? 'bg-bg3 border-bg3 text-tx3'
      : st === 'to_decide' ? 'border-dashed border-[#A78BFA] text-state-violet'
        : st === 'in_progress' ? 'border-dashed border-line2 text-tx3'
          : st === 'skipped' ? 'border-line1 text-tx4 line-through' : 'border-tx1 text-tx1';
  return (
    <span className={'inline-flex items-center gap-1.5 h-[34px] px-3 rounded-full border-[1.5px] text-[13px] animate-pop ' + (nd.kind === 'domain' ? 'font-mono ' : 'font-sans font-medium ') + cls}>
      {st === 'in_progress' && <span className="spin !w-3 !h-3 !border-[1.5px]" />}{nd.label}{st === 'to_decide' ? ' ?' : ''}
    </span>
  );
}

function Sledztwo() {
  const { id: raw } = useParams<{ id: string }>();
  const id = decodeURIComponent(raw);
  const sp = useSearchParams();
  const router = useRouter();
  const replay = sp.get('replay') || undefined;
  const fast = sp.get('koniec') === '1';
  // a freshly started investigation may 404 for a moment: retry the stream (and re-read it) a few times
  const [attempt, setAttempt] = useState(0);
  const inv = useApi<Investigation>(`/investigations/${encodeURIComponent(id)}`, [attempt]).data;
  const cid = inv?.campaign_id ?? sp.get('kampania') ?? null;
  const camp = useApi<Campaign>(cid ? `/campaigns/${encodeURIComponent(cid)}` : null).data;
  const [s, setS] = useState<S>({ nodes: [], steps: [], decision: null, done: null, text: '' });
  const [skipped, setSkipped] = useState<Record<string, boolean>>({});
  const [unchecked, setUnchecked] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);

  const onEvent = useCallback((ev: Event) => {
    const d = ev.data as Record<string, unknown>;
    setS((p) => {
      switch (ev.type) {
        case 'graph.node_added': {
          const nd = d.node as InvestigationNode;
          if (p.nodes.some((x) => x.id === nd.id)) return { ...p, nodes: p.nodes.map((x) => (x.id === nd.id ? nd : x)) };
          return { ...p, nodes: [...p.nodes, nd] };
        }
        case 'agent.step': return { ...p, steps: [...p.steps, d.step as InvestigationStep] };
        case 'investigation.decision': return { ...p, decision: d as S['decision'] };
        case 'casefile.delta': return { ...p, text: p.text + String(d.text_delta ?? '') };
        case 'investigation.done': return { ...p, done: String(d.summary ?? ''), nodes: p.nodes.map((x) => (x.status === 'in_progress' ? { ...x, status: 'new' } : x)) };
      }
      return p;
    });
  }, []);
  const [failed, setFailed] = useState(false);
  const onFail = useCallback(() => { if (attempt < 5) setTimeout(() => setAttempt((a) => a + 1), 1500); else setFailed(true); }, [attempt]);
  useEventStream({ path: `/investigations/${encodeURIComponent(id)}/stream${attempt ? `?retry=${attempt}` : ''}`, replay, simulate: () => investigationEvents(id), local: isOffline() && !replay, speed: fast ? 40 : 1, onEvent, onFail });

  const last = s.steps[s.steps.length - 1];
  const activeBot = last ? (last.bot ?? TOOL_BOT[String(last.tool).split('.')[0]] ?? 'sedzia') : 'sedzia';
  const seed = s.nodes[0]?.label ?? inv?.seed ?? sp.get('seed') ?? '';
  const visible = s.nodes.filter((x, i) => i > 0 && !HIDDEN_KINDS.has(x.kind)).map((x) => (skipped[x.id] ? { ...x, status: 'skipped' as const } : x));
  const newDomains = visible.filter((x) => x.kind === 'domain' && x.status === 'new');
  const uniqNew = [...new Map([...newDomains].reverse().map((x) => [x.label, x])).values()].reverse();
  const ads = visible.find((x) => x.kind === 'ad');
  const adsN = Number(/\d+/.exec(ads?.label ?? '')?.[0] ?? 0);
  const certNight = visible.filter((x) => x.branch === 'crtsh' && x.status === 'new').length;
  const offList = Number(/\d+/.exec(visible.find((x) => x.kind === 'list_status')?.label ?? '')?.[0] ?? uniqNew.length);
  const budget = Number(inv?.budget?.steps ?? 20);
  const stepN = Math.max(s.steps.length, Number(last?.n ?? 0));

  async function decide(opt: string) {
    if (!s.decision) return;
    const nid = s.decision.node_id;
    if (/pomi/i.test(opt)) setSkipped((k) => ({ ...k, [nid]: true }));
    else setS((p) => ({ ...p, nodes: p.nodes.map((x) => (x.id === nid ? { ...x, status: 'new' } : x)) }));
    setS((p) => ({ ...p, decision: null }));
    await apiPost(`/investigations/${encodeURIComponent(id)}/steer`, { node_id: nid, choice: opt }, () => ({ ok: true })).catch(() => null);
  }
  async function promote() {
    setBusy(true);
    const ids = [...uniqNew.filter((x) => !unchecked[x.id]).map((x) => x.id), ...(ads && !unchecked[ads.id] ? [ads.id] : [])];
    await apiPost(`/investigations/${encodeURIComponent(id)}/promote`, { campaign_id: cid, node_ids: ids }, () => ({ campaign_id: cid, added: ids.length })).catch(() => null);
    router.push(cid ? `/kampanie/${cid}?dodano=${ids.length}` : '/kampanie');
  }

  const crumbs = <Crumbs items={cid ? [{ label: 'Kampanie', href: '/kampanie' }, { label: cid, href: `/kampanie/${cid}` }, { label: 'Śledztwo' }] : [{ label: 'Śledztwa', href: '/sledztwa' }, { label: id }]} />;

  if (failed && !s.nodes.length && !s.done) {
    return (
      <Page>
        {crumbs}
        <div className="rounded-[22px] border border-dashed border-line2 bg-bg2 p-8 text-center flex flex-col items-center gap-2">
          <b className="text-[17px]">Nie udało się połączyć ze śledztwem {id}</b>
          <span className="text-[14px] text-tx3 max-w-[520px]">Agent mógł już skończyć albo serwer nie odpowiada. {inv?.status === 'done' ? 'Wyniki są zapisane: ' : ''}Spróbuj ponownie albo zacznij nowe śledztwo.</span>
          <div className="flex gap-2 mt-2">
            <a className="btn-sec btn-sm" href={`/sledztwa/${encodeURIComponent(id)}?replay=live`}>Odtwórz zapis</a>
            <a className="btn-pri btn-sm" href="/sledztwa">Nowe śledztwo</a>
          </div>
        </div>
      </Page>
    );
  }

  // ------------------------------------------------------------------ board 10 · finished
  if (s.done) {
    const shown = uniqNew.slice(0, 6);
    const rest = uniqNew.length - shown.length;
    const skippedNodes = visible.filter((x) => x.status === 'skipped' || x.status === 'to_decide');
    const inCamp = visible.filter((x) => x.status === 'in_campaign' && x.kind === 'domain');
    const c = camp?.counts ?? {};
    const add = uniqNew.filter((x) => !unchecked[x.id]).length;
    const before: [string, number, number][] = [
      ['domeny', camp?.n_domains ?? 0, (camp?.n_domains ?? 0) + add],
      ['materiały', camp?.n_incidents ?? 0, (camp?.n_incidents ?? 0) + (ads && !unchecked[ads.id] ? adsN : 0)],
      ['reklamodawcy', c.advertisers ?? 0, c.advertisers ?? 0],
      ['domeny poza listą CERT PL', (camp?.n_domains ?? 0) - (c.certpl_listed ?? 0), (camp?.n_domains ?? 0) - (c.certpl_listed ?? 0) + add],
    ];
    return (
      <Page>
        {crumbs}
        <ReportHeader
          title={`Znaleźliśmy ${plural(uniqNew.length, 'nową domenę', 'nowe domeny', 'nowych domen')}${adsN ? ` i ${plural(adsN, 'reklamę', 'reklamy', 'reklam')}` : ''}`}
          lead={`${certNight ? `${certNight === 1 ? 'Jedna domena dostała' : `${['', '', 'Dwie', 'Trzy', 'Cztery'][certNight] ?? certNight} domeny dostały`} certyfikat tej nocy. ` : ''}Żadnej z nowych nie ma jeszcze na liście CERT PL.`}
          meta={`${id} · start ${seed} · ${stepN} kroków`}
          primary={cid ? <button type="button" className="btn-pri" onClick={promote} disabled={busy}>{busy ? 'Dodaję…' : 'Dodaj do kampanii'}<IArrow /></button> : <Link className="btn-pri" href="/kampanie">Wybierz kampanię<IArrow /></Link>}
          secondary={cid ? <Link className="lnk" href={`/kampanie/${cid}/zgloszenie`}>albo zgłoś od razu</Link> : undefined}
        />
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-6 items-start">
          <section aria-labelledby="sk-add" className="flex flex-col gap-2.5">
            <h2 id="sk-add" className="text-[16px] font-semibold">Co dodajemy</h2>
            {shown.map((x) => {
              const m = (x.meta ?? {}) as { note?: string; why?: string };
              const b = BRANCHES.find((y) => y.k === x.branch)?.bot ?? 'tropiciel';
              return (
                <label key={x.id} className="min-h-16 flex items-center gap-3 px-4 py-2.5 border border-line1 rounded-[18px] bg-bg1 shadow-soft cursor-pointer">
                  <input type="checkbox" checked={!unchecked[x.id]} onChange={(e) => setUnchecked({ ...unchecked, [x.id]: !e.target.checked })} className="w-[18px] h-[18px] accent-black" />
                  <Bot color={BOT_BY_KEY[b as keyof typeof BOT_BY_KEY].color} size={30} />
                  <span className="flex-1 min-w-0"><b className="block font-mono text-[14px] font-medium">{x.label}</b><span className="text-[12.5px] text-tx3">{botName(b)} · {m.why ?? BRANCHES.find((y) => y.k === x.branch)?.sub}</span></span>
                  {m.note && <span className="text-[12.5px] text-tx2 text-right">{m.note}</span>}
                </label>
              );
            })}
            {rest > 0 && <span className="text-[13.5px] text-tx2 underline decoration-line2 underline-offset-4 px-1">i {rest} {rest === 1 ? 'kolejna domena' : 'kolejne domeny'}</span>}
            {ads && adsN > 0 && (
              <label className="min-h-16 flex items-center gap-3 px-4 py-2.5 border border-line1 rounded-[18px] bg-bg1 shadow-soft cursor-pointer mt-3">
                <input type="checkbox" checked={!unchecked[ads.id]} onChange={(e) => setUnchecked({ ...unchecked, [ads.id]: !e.target.checked })} className="w-[18px] h-[18px] accent-black" />
                <Bot color="#2563EB" size={30} />
                <span className="flex-1 min-w-0"><b className="block text-[14.5px] font-semibold">{(ads.meta as { title?: string })?.title ?? ads.label}</b><span className="text-[12.5px] text-tx3">Zwiadowca · {(ads.meta as { why?: string })?.why ?? 'Ad Library'}</span></span>
                <span className="text-[12.5px] text-tx2">Ad Library</span>
              </label>
            )}
          </section>
          <div className="flex flex-col gap-4">
            {camp && <Card title={`${camp.id} po dodaniu`}>
              {before.map(([l, a, b]) => <div key={l} className="flex justify-between py-2.5 border-b border-bg4 last:border-0 text-[14px]"><span>{l}</span><span className="font-mono"><span className="text-tx4">{n(a)} → </span><b>{n(b)}</b></span></div>)}
            </Card>}
            <Card title="Pominięte">
              {skippedNodes.map((x) => <div key={x.id} className="py-2.5 border-b border-bg4"><b className="block font-mono text-[13.5px] font-medium text-tx2">{x.label}</b><span className="text-[12.5px] text-tx3">{x.status === 'skipped' ? 'pominięta przez ciebie' : 'bez decyzji'} · {(x.meta as { why?: string })?.why ?? ''}</span></div>)}
              {inCamp.length > 0 && <div className="py-2.5"><b className="block font-mono text-[13.5px] font-medium text-tx2">{[...new Set(inCamp.map((x) => x.label))].join(', ')}</b><span className="text-[12.5px] text-tx3">już były w tej kampanii</span></div>}
            </Card>
          </div>
        </div>
      </Page>
    );
  }

  // ------------------------------------------------------------------ board 9 · in progress
  return (
    <Page>
      {crumbs}
      <ReportHeader
        title="Szukamy reszty kampanii"
        lead={`Agent zaczął od ${seed || '…'} i sprawdza, co jeszcze ma te same ślady: certyfikaty z tej samej nocy, ten sam kit, tych samych reklamodawców.`}
        meta={`${id}${inv?.model ? ` · ${inv.model}` : ''}`}
        secondary={<button type="button" className="lnk" onClick={async () => { await apiPost(`/investigations/${encodeURIComponent(id)}/stop`, {}, () => ({})).catch(() => null); setS((p) => ({ ...p, done: p.done ?? 'stop' })); }}>Zatrzymaj i pokaż wyniki</button>}
      />
      <ol className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 m-0 p-0 list-none" aria-label="Kto pracuje">
        {STRIP.map((x) => {
          const b = BOT_BY_KEY[x.bot];
          const on = x.bot === activeBot || x.bot === 'sedzia';
          return (
            <li key={x.bot} className={'flex items-center gap-2.5 px-3 py-2.5 rounded-2xl border bg-bg1 ' + (on ? 'border-tx1' : 'border-bg4')}>
              <Bot color={b.color} master={b.master} size={30} state={x.bot === activeBot ? 'speaking' : 'awake'} />
              <span className="min-w-0"><b className="block text-[13.5px] font-semibold">{b.name}</b><span className={'block text-[12px] truncate ' + (on ? 'text-[#166534]' : 'text-tx3')}>{x.sub}</span></span>
            </li>
          );
        })}
      </ol>
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_340px] gap-6 items-start">
        <Card title="Co znaleźli" action={<span className="text-[12.5px] text-tx3">graf rośnie z każdym krokiem</span>}>
          <div className="grid grid-cols-1 md:grid-cols-[170px_minmax(0,1fr)] gap-4 items-center">
            <div className="rounded-2xl bg-tx1 text-white px-4 py-3.5 self-center"><span className="block text-[12px] text-line3">start</span><b className="font-mono text-[14px] break-all">{seed || '…'}</b></div>
            <div className="border-l border-line1 pl-4 flex flex-col">
              {BRANCHES.map((br) => {
                const items = visible.filter((x) => (x.branch ?? 'db') === br.k);
                if (!items.length && !s.steps.some((st) => TOOL_BOT[String(st.tool).split('.')[0]] === br.bot)) return null;
                return (
                  <div key={br.k} className="grid grid-cols-[130px_minmax(0,1fr)] gap-3 py-2.5 items-start">
                    <span><b className="block text-[14px] font-semibold">{br.label}</b><span className="text-[12px] text-tx3">{br.k === 'db' ? (cid ? `już w ${cid}` : 'już znane') : br.sub}</span></span>
                    <div className="flex flex-wrap gap-1.5">{items.map((x) => <Pill key={x.id} nd={x} />)}{!items.length && <span className="spin" />}</div>
                  </div>
                );
              })}
              {!visible.length && <div className="py-8 flex items-center gap-3 text-tx3 text-[14px]"><span className="spin" />Sędzia planuje pierwsze kroki…</div>}
            </div>
          </div>
          <div className="flex flex-wrap gap-4 pt-4 text-[12.5px] text-tx2">
            <span className="inline-flex items-center gap-1.5"><i className="w-3 h-3 rounded-full border-[1.5px] border-tx1" />nowe</span>
            <span className="inline-flex items-center gap-1.5"><i className="w-3 h-3 rounded-full bg-bg3" />już w kampanii</span>
            <span className="inline-flex items-center gap-1.5"><i className="w-3 h-3 rounded-full border-[1.5px] border-dashed border-[#A78BFA]" />do decyzji</span>
            <span className="inline-flex items-center gap-1.5"><i className="w-3 h-3 rounded-full border-[1.5px] border-dashed border-line2" />w toku</span>
          </div>
        </Card>
        <div className="flex flex-col gap-4">
          {s.decision && (
            <section className="rounded-[22px] bg-tx1 text-white p-5 flex flex-col gap-3 shadow-dark" aria-live="assertive">
              <span className="text-[12.5px] text-line3 text-center">Sędzia potrzebuje twojej decyzji</span>
              <p className="text-[16px] leading-snug">{s.decision.question}</p>
              <div className="flex gap-2">
                {s.decision.options.map((o, i) => (
                  <button key={o} type="button" onClick={() => decide(o)} className={'min-h-[44px] px-4 rounded-xl text-[15px] font-semibold ' + (i === 0 ? 'bg-white text-tx1' : 'border border-[#404040] text-white hover:bg-[#1a1a1a]')}>{o}</button>
                ))}
              </div>
            </section>
          )}
          <Card title="Do tej pory">
            {[['nowe domeny', uniqNew.length], ['reklamy', adsN], ['certyfikaty z tej nocy', certNight], ['domeny poza listą CERT PL', offList]].map(([l, v]) => (
              <div key={l as string} className="flex justify-between py-2.5 border-b border-bg4 last:border-0 text-[14px]"><span>{l}</span><b className="font-mono">{v}</b></div>
            ))}
          </Card>
          <div className="px-1">
            <div className="flex justify-between text-[13px] text-tx2 pb-1.5"><span>krok {stepN} z {budget}</span><span>{s.done ? 'koniec' : 'agent pracuje'}</span></div>
            <span className="block h-2 rounded-full bg-bg4 overflow-hidden"><i className="block h-full bg-tx1 rounded-full transition-[width] duration-500" style={{ width: `${Math.min(100, (stepN / budget) * 100)}%` }} /></span>
          </div>
          {s.text && (
            <details className="card !rounded-[18px] p-4 text-[13px]">
              <summary className="cursor-pointer font-semibold">Akta sprawy</summary>
              <div className="pt-2 whitespace-pre-wrap text-tx2 max-h-64 overflow-auto">{s.text.replace(/\*\*|`|_/g, '')}</div>
            </details>
          )}
        </div>
      </div>
    </Page>
  );
}

export default function SledztwoPage() {
  return <JellyRoot className="flex-1 flex flex-col"><Suspense fallback={<Loading />}><Sledztwo /></Suspense></JellyRoot>;
}
