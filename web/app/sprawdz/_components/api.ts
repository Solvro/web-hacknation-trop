// Public, coarse-only endpoints (docs/design/README.md section 7 and 9). Same-origin proxy by default.
export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? '/api/v1').replace(/\/+$/, '');

export type PublicCampaign = { name: string; seen_count: number; since: string; reasons: string[] };
export type CheckResult = { verdict: 'scam' | 'unknown'; public_campaign?: PublicCampaign | null; advice: string[] };
export type ReportAck = { ok: boolean; report_id: string };

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export async function check(input: { url?: string; text?: string; image?: File | null }): Promise<CheckResult> {
  const fd = new FormData();
  if (input.url) fd.set('url', input.url);
  if (input.text) fd.set('text', input.text);
  if (input.image) fd.set('image', input.image); // ignored by the server until /public/check accepts uploads
  return j(await fetch(`${API_BASE}/public/check`, { method: 'POST', body: fd }));
}

export async function report(body: { url?: string; note?: string }): Promise<ReportAck> {
  return j(await fetch(`${API_BASE}/public/report`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body),
  }));
}

export async function schemes(): Promise<PublicCampaign[]> {
  return j(await fetch(`${API_BASE}/public/schemes?window=7d`));
}
