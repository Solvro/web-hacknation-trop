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

export default function LabPage() {
  const m = useApi<LabMetrics>('/lab/metrics').data;
  const base = useApi<LabMetrics>('/lab/metrics?view=baselines').data;
  const abl = useApi<{ layer: string; delta_f1: number }[]>('/lab/ablation').data;
  const d = (m?.data ?? {}) as Record<string, unknown>;
  const rows = ((base?.data as { rows?: { model: string; bcubed_f1: number }[] } | undefined)?.rows) ?? [];
  return (
    <Page>
      <h1 className="text-[36px] sm:text-[42px] font-semibold tracking-[-0.04em] leading-none pt-3">Lab · metodologia</h1>
      <p className="text-[15px] text-tx2 -mt-2">Model {m?.model_version ?? '…'}{d.sample ? ' · przykładowe wartości, do podmiany z eval/' : ''}</p>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {METRICS.map(([k, l]) => <div key={k} className="rounded-[18px] border border-line1 p-4"><b className="block text-[28px] font-semibold tracking-[-0.03em]">{fmt(d[k])}</b><span className="text-[12.5px] text-tx3">{l}</span></div>)}
      </div>
      {d.conformal_target != null && <p className="text-[13.5px] text-tx2">Kalibracja: błąd {fmt(d.conformal_achieved)} przy celu {fmt(d.conformal_target)}.</p>}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Porównanie metod">
          {rows.map((r) => (
            <div key={r.model} className="py-2"><span className="flex justify-between text-[14px]"><span>{r.model}</span><b className="font-mono">{p2(r.bcubed_f1)}</b></span>
              <span className="block h-2 mt-1 rounded-full bg-bg4 overflow-hidden"><i className="block h-full bg-tx1 rounded-full" style={{ width: `${r.bcubed_f1 * 100}%` }} /></span></div>
          ))}
          {!rows.length && <Empty>Brak danych.</Empty>}
        </Card>
        <Card title="Ablacja: co się dzieje bez warstwy">
          {(abl ?? []).map((r) => (
            <div key={r.layer} className="flex items-center gap-3 py-1.5 text-[14px]"><span className="w-24">{r.layer}</span>
              <span className="flex-1 h-2 rounded-full bg-bg4 overflow-hidden"><i className="block h-full bg-state-red rounded-full" style={{ width: `${Math.min(100, Math.abs(r.delta_f1) * 400)}%` }} /></span>
              <b className="font-mono w-14 text-right">{r.delta_f1.toFixed(2)}</b></div>
          ))}
          {!abl?.length && <Empty>Brak danych.</Empty>}
        </Card>
      </div>
      <Batch />
    </Page>
  );
}
