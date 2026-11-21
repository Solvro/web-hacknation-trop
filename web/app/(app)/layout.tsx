import { Header, Footer } from '@/components/shell';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <a href="#main" className="sr-only-x focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-tx1 focus:text-white focus:px-3 focus:py-2 focus:rounded-lg focus:w-auto focus:h-auto focus:[clip-path:none]">Przejdź do treści</a>
      <Header />
      <div id="main" className="flex-1 flex flex-col">{children}</div>
      <Footer />
    </>
  );
}
