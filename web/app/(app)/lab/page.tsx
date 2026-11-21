'use client';
// /lab (hidden, not in the tabs): G-ENGINE numbers for the methodology part of the pitch + "Importuj zbiór" batch.
import { useEffect, useRef, useState } from 'react';
import type { BatchResult, LabMetrics } from '@/lib/contracts';
import { API, apiGet, apiPost, isOffline, useApi } from '@/lib/api';
import { DECISION_LABEL, p2 } from '@/lib/copy';
import { Card, Empty, Page } from '@/components/ui';
import { IDownload, IUpload } from '@/components/icons';

const METRICS: [string, string][] = [
  ['bcubed_f1', 'B³ F1'], ['ari', 'ARI'], ['pairwise_precision', 'precyzja par'], ['open_set_accuracy', 'open-set'],
  ['new_campaign_precision', 'precyzja „nowa kampania”'], ['m2_infra_blind_f1', 'F1 bez infra (M2)'],
];

function fmt(v: unknown) { return typeof v === 'number' ? (v <= 1 ? p2(v) : String(v)) : String(v ?? '—'); }

function Batch() {
  const input = useRef<HTMLInputElement>(null);
  const [job, setJob] = useState<string | null>(null);
  const [res, setRes] = useState<BatchResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setErr(null); setRes(null); setBusy(true);
    const fd = new FormData();
    for (const f of Array.from(files)) fd.append('files', f, (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name);
    try {
      const r = await apiPost<{ job_id: string }>('/batch', fd);
      setJob(r.job_id);
    } catch {
      setErr('Import wymaga działającego API (POST /api/v1/batch). W trybie offline nie ma czego liczyć.');
      setBusy(false);
    }
  }
  useEffect(() => {
    if (!job) return;
    let stop = false;
    const tick = async () => {
      try {
        const r = await apiGet<BatchResult>(`/batch/${encodeURIComponent(job)}`);
        if (stop) return;
        setRes(r);
        if (!r.rows?.length || r.rows.length < r.n_items) setTimeout(tick, 1500); else setBusy(false);
      } catch { if (!stop) setTimeout(tick, 2000); }
    };
    tick();
    return () => { stop = true; };
  }, [job]);

  return (
    <Card title="Importuj zbiór" action={job && res?.rows?.length ? <a className="btn-sec btn-sm" href={res.csv_url ?? `${API}/batch/${encodeURIComponent(job)}/results.csv`} download><IDownload />results.csv</a> : undefined}>
      <p className="text-[13.5px] text-tx2 pb-3">Wrzuć ZIP albo folder z materiałami (zrzuty, HAR, wideo). Każdy materiał dostaje kampanię, operację i najważniejsze dowody, jak w <span className="font-mono">results.csv</span>.</p>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-pri btn-sm" onClick={() => input.current?.click()} disabled={busy}><IUpload />{busy ? 'Liczę…' : 'Wybierz ZIP lub pliki'}</button>
        <input ref={input} type="file" multiple accept=".zip,.har,.json,image/*,video/*" className="hidden" aria-label="Pliki do importu" onChange={(e) => upload(e.target.files)} />
      </div>
      {err && <p role="alert" className="text-[13px] text-state-red pt-2">{err}</p>}
      {isOffline() && !err && <p className="text-[12.5px] text-tx3 pt-2">API jest teraz niedostępne: import ruszy, gdy wróci.</p>}
      {res && (
        <div className="overflow-x-auto pt-4">
          <table className="w-full min-w-[760px] text-[13px] border-collapse">
            <thead><tr className="text-left text-tx3 border-b border-line1">{['materiał', 'decyzja', 'kampania', 'pewność', 'operacja', 'pokrycie', 'dowody'].map((h) => <th key={h} className="font-normal py-2 px-2">{h}</th>)}</tr></thead>
            <tbody>
              {res.rows.map((r) => (
                <tr key={r.item + r.incident_id} className="border-b border-bg4">
                  <td className="py-2 px-2 font-mono">{r.item}</td><td className="px-2">{DECISION_LABEL[r.decision] ?? r.decision}</td><td className="px-2 font-mono">{r.campaign}</td>
                  <td className="px-2 font-mono">{p2(r.campaign_p)}</td><td className="px-2 font-mono">{r.operation}</td><td className="px-2 font-mono">{p2(r.coverage)}</td>
                  <td className="px-2 text-tx2 max-w-[320px] truncate" title={r.top_evidence}>{r.top_evidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[12.5px] text-tx3 pt-2">{res.rows.length} z {res.n_items} materiałów</p>
        </div>
      )}
    </Card>
  );
}

type R = Record<string, unknown>;
const num = (v: unknown) => (typeof v === 'number' ? v : undefined);
const PERT: Record<string, string> = {
  duplicate: 'duplikaty', drop_screenshot: 'bez zrzutu', drop_har: 'bez HAR', drop_html: 'bez HTML', swap_domain: 'zmiana domeny',
  rotate_tracking: 'nowe piksele', error_502: 'strona 502', full_rotation: 'pełna rotacja',
};

export default function LabPage() {
  const m = useApi<LabMetrics>('/lab/metrics').data;
  const base = useApi<LabMetrics>('/lab/metrics?view=baselines').data;
  const loco = useApi<LabMetrics>('/lab/metrics?view=loco').data;
  const abl = useApi<{ layer: string; delta_f1: number }[]>('/lab/ablation').data;
  const d = (m?.data ?? {}) as R;
  // real `trop eval` shape: {n, avglink_tau5:{b3_F1, ARI, pair_P, pair_R, hardneg_viol, …}, pair_auc, loco:{…}}
  const al = (d.avglink_tau5 ?? {}) as R;
  const lc = ((d.loco ?? (loco?.data as R | undefined)?.loco) ?? {}) as R;
  const cards: [string, string][] = d.avglink_tau5 ? [
    [fmt(al.b3_F1), 'B³ F1 (kampanie)'], [fmt(al.ARI), 'ARI'], [fmt(al.pair_P), 'precyzja par'], [fmt(al.pair_R), 'czułość par'],
    [String(al.hardneg_viol ?? '—'), 'błędne połączenia (twarde negatywy)'], [fmt(d.pair_auc), 'AUC par'],
  ] : METRICS.map(([k, l]) => [fmt(d[k]), l]);
  const grid = ((base?.data as R | undefined)?.avglink_grid ?? []) as R[];
  const rows = ((base?.data as { rows?: { model: string; bcubed_f1: number }[] } | undefined)?.rows) ?? [];
  const rob = Object.entries(((loco?.data as R | undefined)?.robustness ?? {}) as Record<string, R>);
  return (
    <Page>
      <h1 className="text-[36px] sm:text-[42px] font-semibold tracking-[-0.04em] leading-none pt-3">Lab · metodologia</h1>
      <p className="text-[15px] text-tx2 -mt-2">
        Model {m?.model_version ?? '…'}{num(d.n) ? ` · ocena na ${d.n} materiałach z etykietami` : ''}{d.sample ? ' · przykładowe wartości' : d.source ? ' · liczby z trop eval' : ''}
      </p>
      {!m && <Empty>Ładuję wyniki oceny…</Empty>}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {cards.map(([v, l]) => <div key={l} className="rounded-[18px] border border-line1 p-4"><b className="block text-[28px] font-semibold tracking-[-0.03em]">{v}</b><span className="text-[12.5px] text-tx3">{l}</span></div>)}
      </div>
      {d.loco != null || loco ? (
        <p className="text-[14px] text-tx2">
          Leave-one-campaign-out: {fmt(lc.should_link_acc)} poprawnie dołączonych, {fmt(lc.should_not_link_acc)} poprawnie odrzuconych, {String(lc.wrong_assign ?? '—')} błędnych przypisań.
        </p>
      ) : null}
      {d.conformal_target != null && <p className="text-[13.5px] text-tx2">Kalibracja: błąd {fmt(d.conformal_achieved)} przy celu {fmt(d.conformal_target)}.</p>}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title={grid.length ? 'Próg τ: jakość przy różnych progach' : 'Porównanie metod'}>
          {grid.map((r) => (
            <div key={String(r.tau)} className="py-2"><span className="flex justify-between text-[14px]"><span>τ = {String(r.tau)}{r.tau === 5 ? ' (wybrany)' : ''}</span><b className="font-mono">F1 {p2(num(r.b3_F1))} · błędne {String(r.hardneg_viol ?? '—')}</b></span>
              <span className="block h-2 mt-1 rounded-full bg-bg4 overflow-hidden"><i className="block h-full bg-tx1 rounded-full" style={{ width: `${(num(r.b3_F1) ?? 0) * 100}%` }} /></span></div>
          ))}
          {rows.map((r) => (
            <div key={r.model} className="py-2"><span className="flex justify-between text-[14px]"><span>{r.model}</span><b className="font-mono">{p2(r.bcubed_f1)}</b></span>
              <span className="block h-2 mt-1 rounded-full bg-bg4 overflow-hidden"><i className="block h-full bg-tx1 rounded-full" style={{ width: `${r.bcubed_f1 * 100}%` }} /></span></div>
          ))}
          {!rows.length && !grid.length && <Empty>Brak danych.</Empty>}
        </Card>
        {rob.length > 0 ? (
          <Card title="Stres-test: co gdy czegoś brakuje">
            {rob.map(([k, r]) => (
              <div key={k} className="flex items-center gap-3 py-1.5 text-[14px]"><span className="w-32">{PERT[k] ?? k}</span>
                <span className="flex-1 h-2 rounded-full bg-bg4 overflow-hidden"><i className="block h-full bg-tx1 rounded-full" style={{ width: `${(num(r.acc) ?? 0) * 100}%` }} /></span>
                <b className="font-mono w-28 text-right">{p2(num(r.acc))} · {String(r.wrong_assign ?? 0)} błędnych</b></div>
            ))}
          </Card>
        ) : (
          <Card title="Ablacja: co się dzieje bez warstwy">
            {(abl ?? []).map((r) => (
              <div key={r.layer} className="flex items-center gap-3 py-1.5 text-[14px]"><span className="w-24">{r.layer}</span>
                <span className="flex-1 h-2 rounded-full bg-bg4 overflow-hidden"><i className="block h-full bg-state-red rounded-full" style={{ width: `${Math.min(100, Math.abs(r.delta_f1) * 400)}%` }} /></span>
                <b className="font-mono w-14 text-right">{r.delta_f1.toFixed(2)}</b></div>
            ))}
            {!abl?.length && <Empty>Brak danych.</Empty>}
          </Card>
        )}
      </div>
      <Batch />
    </Page>
  );
}
