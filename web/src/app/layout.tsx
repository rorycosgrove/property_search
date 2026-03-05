import type { Metadata } from 'next';
import './globals.css';

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
    <html lang="en" className="dark">
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
          <header className="border-b border-[var(--card-border)] px-6 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-semibold tracking-tight">
                🏠 Irish Property Dashboard
              </h1>
            </div>
            <nav className="flex gap-4 text-sm text-[var(--muted)]">
              <a href="/" className="hover:text-white transition-colors">Map</a>
              <a href="/analytics" className="hover:text-white transition-colors">Analytics</a>
              <a href="/alerts" className="hover:text-white transition-colors">Alerts</a>
              <a href="/sources" className="hover:text-white transition-colors">Sources</a>
              <a href="/settings" className="hover:text-white transition-colors">Settings</a>
            </nav>
          </header>
          <main className="flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
