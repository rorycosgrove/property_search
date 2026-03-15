'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

const PHASE_GROUPS = [
  {
    phase: 'Start',
    links: [{ href: '/', label: 'Home' }],
  },
  {
    phase: 'Research',
    links: [
      { href: '/research', label: 'Overview' },
      { href: '/analytics', label: 'Market' },
      { href: '/grants', label: 'Incentives' },
      { href: '/sources', label: 'Sources' },
    ],
  },
  {
    phase: 'Decide',
    links: [{ href: '/workspace', label: 'Workspace' }],
  },
  {
    phase: 'Execute',
    links: [
      { href: '/alerts', label: 'Alerts' },
      { href: '/settings', label: 'Settings' },
    ],
  },
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

  const getActivePhase = (): string => {
    for (const group of PHASE_GROUPS) {
      if (group.links.some((item) => isActiveRoute(item.href))) {
        return group.phase;
      }
    }
    return 'Decide';
  };

  const activePhase = getActivePhase();

  const allLinks = PHASE_GROUPS.flatMap((group) => group.links);

  const phaseForHref = (href: string): string => {
    for (const group of PHASE_GROUPS) {
      if (group.links.some((item) => item.href === href)) {
        return group.phase;
      }
    }
    return 'Decide';
  };

  return (
    <div className="border-b border-[var(--card-border)] bg-[var(--card-bg)]/85 backdrop-blur-md">
      <div className="px-4 lg:px-6 py-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="h-2.5 w-2.5 rounded-full bg-[var(--success)]" aria-hidden="true" />
          <h1 className="text-xl lg:text-2xl tracking-tight">Atlas</h1>
          <span className="hidden lg:inline-flex text-[11px] uppercase tracking-[0.16em] text-[var(--muted)] border border-[var(--card-border)] rounded-full px-2 py-1 bg-[var(--background)]">
            {activePhase} phase
          </span>
        </div>

        <nav className="hidden lg:flex items-center gap-2" aria-label="Primary">
          {allLinks.map((item) => {
            const active = isActiveRoute(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={[
                  'px-3 py-1.5 rounded-full text-sm border transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-700',
                  active
                    ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)]'
                    : 'border-transparent text-[var(--muted)] hover:text-[var(--foreground)] hover:border-[var(--card-border)]',
                ].join(' ')}
                aria-current={active ? 'page' : undefined}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

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
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] border border-[var(--card-border)] text-[var(--muted)] bg-[var(--background)]/70">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--success)]" aria-hidden="true" />
            AI ready
          </span>
        </div>
      </div>

      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-[720]">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/35"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation menu"
          />

          <nav
            className="absolute bottom-0 left-0 right-0 rounded-t-2xl border-t border-[var(--card-border)] bg-[var(--card-bg)] p-4 shadow-2xl sheet-in"
            aria-label="Mobile primary"
            role="navigation"
          >
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold">Navigate</p>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="px-2 py-1 text-xs border border-[var(--card-border)] rounded-md"
              >
                Close
              </button>
            </div>

            <div className="grid grid-cols-1 gap-2 max-h-[58vh] overflow-y-auto pb-1">
              <Link
                href="/workspace?focus=ask"
                onClick={() => setMobileOpen(false)}
                className="px-3 py-2 rounded-md text-sm border border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)]"
              >
                Open Atlas AI Query
              </Link>
              {allLinks.map((item) => {
                const active = isActiveRoute(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    className={[
                      'px-3 py-2 rounded-md text-sm border transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-700 flex items-center justify-between',
                      active
                        ? 'border-cyan-800 bg-cyan-800 text-white'
                        : 'border-[var(--card-border)] text-[var(--muted)] hover:text-[var(--foreground)] hover:bg-[var(--background)]',
                    ].join(' ')}
                    aria-current={active ? 'page' : undefined}
                  >
                    <span>{item.label}</span>
                    <span className="text-[10px] uppercase tracking-[0.12em] opacity-70">{phaseForHref(item.href)}</span>
                  </Link>
                );
              })}
            </div>
          </nav>
        </div>
      )}
    </div>
  );
}
