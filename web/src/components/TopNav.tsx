'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

const NAV_ITEMS = [
  { href: '/', label: 'Workspace' },
  { href: '/analytics', label: 'Market' },
  { href: '/grants', label: 'Incentives' },
  { href: '/sources', label: 'Sources' },
  { href: '/settings', label: 'Settings' },
];

export default function TopNav() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isActiveRoute = (href: string): boolean => {
    if (href === '/') {
      return pathname === '/';
    }
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  return (
    <div className="border-b border-[var(--card-border)] ai-glass">
      <div className="px-4 lg:px-6 py-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="h-2.5 w-2.5 rounded-full bg-[var(--success)]" aria-hidden="true" />
          <h1 className="text-lg lg:text-xl tracking-tight">Atlas AI</h1>
          <span className="hidden lg:inline-flex text-[11px] uppercase tracking-[0.16em] text-[var(--muted)] border border-[var(--card-border)] rounded-full px-2 py-1">
            Command Canvas
          </span>
        </div>

        <div className="hidden lg:flex flex-1 max-w-xl">
          <p className="text-xs text-[var(--muted)] border border-[var(--card-border)] rounded-full px-3 py-2 bg-[var(--background)]">
            AI query lives in Workspace so Atlas always responds with current shortlist and ranking context.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setMobileOpen((prev) => !prev)}
          className="lg:hidden px-3 py-1.5 rounded-md border border-[var(--card-border)] text-xs font-semibold hover:bg-[var(--background)] focus:outline-none focus:ring-2 focus:ring-cyan-700"
          aria-expanded={mobileOpen}
          aria-label="Toggle navigation menu"
        >
          Menu
        </button>

        <div className="hidden lg:flex items-center gap-2">
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] border border-[var(--card-border)] text-[var(--muted)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--success)]" aria-hidden="true" />
            AI ready
          </span>
        </div>

        <nav className="hidden lg:flex items-center gap-1" aria-label="Primary">
          {NAV_ITEMS.map((item) => {
            const active = isActiveRoute(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={[
                  'px-3 py-1.5 rounded-md text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-700',
                  active
                    ? 'bg-[var(--accent)] text-white shadow-sm'
                    : 'text-[var(--muted)] hover:text-[var(--foreground)] hover:bg-[var(--background)]',
                ].join(' ')}
                aria-current={active ? 'page' : undefined}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>

      {mobileOpen && (
        <nav
          className="lg:hidden px-4 pb-3 grid grid-cols-2 gap-2"
          aria-label="Mobile primary"
          role="navigation"
        >
          <Link
            href="/?focus=ask"
            onClick={() => setMobileOpen(false)}
            className="col-span-2 px-3 py-2 rounded-md text-sm border border-[var(--accent)] bg-cyan-900/10 text-[var(--accent-strong)]"
          >
            Open Atlas AI Query
          </Link>
          {NAV_ITEMS.map((item) => {
            const active = isActiveRoute(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                className={[
                  'px-3 py-2 rounded-md text-sm border transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-700',
                  active
                    ? 'border-cyan-800 bg-cyan-800 text-white'
                    : 'border-[var(--card-border)] text-[var(--muted)] hover:text-[var(--foreground)] hover:bg-[var(--background)]',
                ].join(' ')}
                aria-current={active ? 'page' : undefined}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      )}
    </div>
  );
}
