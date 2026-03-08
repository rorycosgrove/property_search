import type { Metadata } from 'next';
import { Fraunces, Manrope } from 'next/font/google';
import './globals.css';
import TopNav from '@/components/TopNav';

const fraunces = Fraunces({
  subsets: ['latin'],
  variable: '--font-display',
});

const manrope = Manrope({
  subsets: ['latin'],
  variable: '--font-body',
});

export const metadata: Metadata = {
  title: 'Irish Property Research Dashboard',
  description: 'Research properties to buy in Ireland — price tracking, analytics, and AI insights',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${fraunces.variable} ${manrope.variable}`}>
      <head>
        <link
          rel="stylesheet"
          href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
          crossOrigin=""
        />
      </head>
      <body className="bg-[var(--background)] text-[var(--foreground)] min-h-screen">
        <div className="flex flex-col min-h-screen">
          <header>
            <TopNav />
          </header>
          <main className="flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
