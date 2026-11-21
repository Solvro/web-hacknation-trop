// Optional HTTP basic auth for the analyst app: set TROP_BASIC_AUTH="user:pass" (runtime env). Unset = open (default).
// The public page /sprawdz and the public API (/api/v1/public/*) always stay open, as do static assets.
import { NextResponse, type NextRequest } from 'next/server';

export function middleware(req: NextRequest) {
  const cred = process.env.TROP_BASIC_AUTH;
  if (!cred) return NextResponse.next();
  const { pathname } = req.nextUrl;
  if (pathname === '/sprawdz' || pathname.startsWith('/sprawdz/') || pathname.startsWith('/api/v1/public/')) return NextResponse.next();
  const h = req.headers.get('authorization') ?? '';
  if (h.startsWith('Basic ')) {
    try { if (atob(h.slice(6)) === cred) return NextResponse.next(); } catch { /* bad header */ }
  }
  return new NextResponse('Wymagane logowanie', { status: 401, headers: { 'WWW-Authenticate': 'Basic realm="TROP", charset="UTF-8"' } });
}

export const config = {
  runtime: 'nodejs',
  // everything except Next internals and public static files
  matcher: ['/((?!_next/static|_next/image|favicon.ico|vendor/).*)'],
};
