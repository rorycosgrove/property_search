'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

const PHASE_GROUPS = [
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
    links: [{ href: '/', label: 'Workspace' }],
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

        <div className="hidden lg:flex flex-1 max-w-xl">
          <p className="text-xs text-[var(--muted)] border border-[var(--card-border)] rounded-full px-3 py-2 bg-[var(--background)]/70">
            Research -> Decide -> Execute
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
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] border border-[var(--card-border)] text-[var(--muted)] bg-[var(--background)]/70">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--success)]" aria-hidden="true" />
            AI ready
          </span>
        </div>

        <nav className="hidden lg:flex items-start gap-4" aria-label="Primary">
          {PHASE_GROUPS.map((group) => (
            <div key={group.phase} className="flex flex-col gap-1">
              <span className="text-[10px] uppercase tracking-[0.14em] text-[var(--muted)]">{group.phase}</span>
              <div className="flex items-center gap-1 rounded-lg border border-[var(--card-border)] bg-[var(--background)]/70 p-1">
                {group.links.map((item) => {
                  const active = isActiveRoute(item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={[
                        'px-3 py-1.5 rounded-md text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-700 whitespace-nowrap',
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
              </div>
            </div>
          ))}
        </nav>
      </div>

      {mobileOpen && (
        <nav
          className="lg:hidden px-4 pb-4 grid grid-cols-2 gap-2"
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
          {allLinks.map((item) => {
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
