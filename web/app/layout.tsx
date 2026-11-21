import type { Metadata, Viewport } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import { Header, Footer } from '@/components/shell';
import './globals.css';

export const metadata: Metadata = {
  title: 'trop · sprawdź materiał',
  description: 'TROP: od jednej reklamy do całej kampanii oszustwa, z dowodami.',
};
export const viewport: Viewport = { width: 'device-width', initialScale: 1, themeColor: '#ffffff' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pl" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="min-h-screen flex flex-col font-sans text-[14px] leading-normal">
        <a href="#main" className="sr-only-x focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-tx1 focus:text-white focus:px-3 focus:py-2 focus:rounded-lg focus:w-auto focus:h-auto focus:[clip-path:none]">Przejdź do treści</a>
        <Header />
        <div id="main" className="flex-1 flex flex-col">{children}</div>
        <Footer />
      </body>
    </html>
  );
}
