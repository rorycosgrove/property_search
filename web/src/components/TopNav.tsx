'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

const NAV_ITEMS = [
  { href: '/', label: 'Workspace' },
  { href: '/analytics', label: 'Market' },
  { href: '/grants', label: 'Incentives' },
  { href: '/copilot', label: 'Copilot' },
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
    <div className="border-b border-[var(--card-border)] bg-[var(--card-bg)]/85 backdrop-blur-md">
      <div className="px-4 lg:px-6 py-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="h-2 w-2 rounded-full bg-emerald-600" aria-hidden="true" />
          <h1 className="text-lg lg:text-xl tracking-tight" style={{ fontFamily: 'var(--font-display)' }}>
            Property Value Atlas
          </h1>
          <span className="hidden lg:inline-flex text-[11px] uppercase tracking-[0.16em] text-[var(--muted)] border border-[var(--card-border)] rounded-full px-2 py-1">
            Map-First Utility
          </span>
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
                    ? 'bg-cyan-800 text-white shadow-sm'
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
