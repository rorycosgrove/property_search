import type { Metadata } from 'next';
import { Space_Grotesk, Syne } from 'next/font/google';
import './globals.css';
import BottomNav from '@/components/BottomNav';
import TopNav from '@/components/TopNav';
import AlertStream from '@/components/AlertStream';

const syne = Syne({
  subsets: ['latin'],
  variable: '--font-display',
});

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-body',
});

export const metadata: Metadata = {
  title: 'Atlas Field Desk',
  description: 'Mobile-first property intelligence across market signals, grants, operations, and AI decisioning.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${syne.variable} ${spaceGrotesk.variable}`}>
      <head>
        <link
          rel="stylesheet"
          href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
          crossOrigin=""
        />
      </head>
      <body className="bg-[var(--background)] text-[var(--foreground)] min-h-screen antialiased">
        <div className="relative flex min-h-screen flex-col">
          <header>
            <TopNav />
          </header>
          <main className="flex-1 pb-20 lg:pb-0">{children}</main>
          <BottomNav />
          <AlertStream />
        </div>
      </body>
    </html>
  );
}
