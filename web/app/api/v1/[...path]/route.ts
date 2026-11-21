// Same-origin proxy /api/v1/* → ${API_INTERNAL_URL}/api/v1/* (read at runtime, so one image works in compose and
// Coolify). Bodies are streamed both ways, so SSE (text/event-stream) passes through unbuffered.
import type { NextRequest } from 'next/server';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const HOP = new Set(['connection', 'keep-alive', 'transfer-encoding', 'te', 'trailer', 'upgrade', 'proxy-authorization', 'proxy-authenticate', 'host', 'content-length', 'expect']);

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const base = (process.env.API_INTERNAL_URL || 'http://127.0.0.1:18000').replace(/\/+$/, '');
  const target = `${base}/api/v1/${path.map(encodeURIComponent).join('/')}${req.nextUrl.search}`;
  const headers = new Headers();
  req.headers.forEach((v, k) => { if (!HOP.has(k.toLowerCase())) headers.set(k, v); });
  headers.set('accept-encoding', 'identity');
  const hasBody = !['GET', 'HEAD'].includes(req.method);
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      // request bodies are STREAMED (test-set zips can be hundreds of MB; the web container has 512 MB), the auth
      // middleware does not run on /api, and `expect` is dropped (undici rejects it)
      method: req.method, headers, body: hasBody ? req.body : undefined, redirect: 'manual', cache: 'no-store',
      signal: req.signal,
      // @ts-expect-error Node fetch needs duplex for streamed request bodies
      duplex: hasBody ? 'half' : undefined,
    });
  } catch {
    return Response.json({ error: 'api_unreachable', target: base }, { status: 502 });
  }
  const out = new Headers();
  upstream.headers.forEach((v, k) => { if (!HOP.has(k.toLowerCase()) && k.toLowerCase() !== 'content-encoding') out.set(k, v); });
  if ((upstream.headers.get('content-type') || '').includes('text/event-stream')) {
    out.set('cache-control', 'no-cache, no-transform');
    out.set('x-accel-buffering', 'no');
  }
  return new Response(upstream.body, { status: upstream.status, statusText: upstream.statusText, headers: out });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };
