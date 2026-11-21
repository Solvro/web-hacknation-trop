import type { Metadata, Viewport } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import './globals.css';

// Root layout: document only. The analyst app (tabs, header, footer) lives in the (app) route group;
// the public /sprawdz page has its own shell.
export const metadata: Metadata = {
  title: 'trop · sprawdź materiał',
  description: 'TROP: od jednej reklamy do całej kampanii oszustwa, z dowodami.',
};
export const viewport: Viewport = { width: 'device-width', initialScale: 1, themeColor: '#ffffff' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pl" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="min-h-screen flex flex-col font-sans text-[14px] leading-normal">{children}</body>
    </html>
  );
}
