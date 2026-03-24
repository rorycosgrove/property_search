'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV_ITEMS = [
  {
    href: '/',
    label: 'Home',
    icon: (active: boolean) => (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        className="h-5 w-5"
        aria-hidden="true"
      >
        <path
          fillRule="evenodd"
          d="M9.293 2.293a1 1 0 0 1 1.414 0l7 7A1 1 0 0 1 17 11h-1v6a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1v-3a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v3a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-6H3a1 1 0 0 1-.707-1.707l7-7Z"
          clipRule="evenodd"
        />
      </svg>
    ),
  },
  {
    href: '/search',
    label: 'Search',
    icon: (active: boolean) => (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        className="h-5 w-5"
        aria-hidden="true"
      >
        <path
          fillRule="evenodd"
          d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM2 9a7 7 0 1 1 12.452 4.391l3.328 3.329a.75.75 0 1 1-1.06 1.06l-3.329-3.328A7 7 0 0 1 2 9Z"
          clipRule="evenodd"
        />
      </svg>
    ),
  },
  {
    href: '/workspace',
    label: 'Workspace',
    icon: (active: boolean) => (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        className="h-5 w-5"
        aria-hidden="true"
      >
        <path d="M14.916 2.404a.75.75 0 0 1-.32 1.012l-.596.31V17a1 1 0 0 1-1 1h-2.26a.75.75 0 0 1-.75-.75V16a.5.5 0 0 0-.5-.5h-2a.5.5 0 0 0-.5.5v1.25a.75.75 0 0 1-.75.75H4a1 1 0 0 1-1-1V3.726l-.596-.31a.75.75 0 0 1 .692-1.332l7.5 3.9a.75.75 0 0 1 0 1.332L6 9.51V16h1v-1a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1h1V7.726l-3.404-1.77a.75.75 0 0 1 0-1.332l4.92-2.56a.75.75 0 0 1 1.012.32 1.009 1.009 0 0 1-.612.02Z" />
      </svg>
    ),
  },
  {
    href: '/alerts',
    label: 'Alerts',
    icon: (active: boolean) => (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        className="h-5 w-5"
        aria-hidden="true"
      >
        <path
          fillRule="evenodd"
          d="M4 8a6 6 0 1 1 12 0c0 1.887.454 3.665 1.257 5.234a.75.75 0 0 1-.515 1.076 32.903 32.903 0 0 1-3.256.508 3.5 3.5 0 0 1-6.972 0 32.91 32.91 0 0 1-3.256-.508.75.75 0 0 1-.515-1.076A11.448 11.448 0 0 0 4 8Zm6 7c-.655 0-1.246-.288-1.653-.745a31.417 31.417 0 0 0 3.306 0A1.998 1.998 0 0 1 10 15Z"
          clipRule="evenodd"
        />
      </svg>
    ),
  },
  {
    href: '/analytics',
    label: 'Insights',
    icon: (active: boolean) => (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        className="h-5 w-5"
        aria-hidden="true"
      >
        <path d="M15.5 2A1.5 1.5 0 0 0 14 3.5v13a1.5 1.5 0 0 0 3 0v-13A1.5 1.5 0 0 0 15.5 2ZM9.5 6A1.5 1.5 0 0 0 8 7.5v9a1.5 1.5 0 0 0 3 0v-9A1.5 1.5 0 0 0 9.5 6ZM3.5 10A1.5 1.5 0 0 0 2 11.5v5a1.5 1.5 0 0 0 3 0v-5A1.5 1.5 0 0 0 3.5 10Z" />
      </svg>
    ),
  },
];

export default function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-30 lg:hidden"
      aria-label="Primary navigation"
    >
      {/* Frosted glass backdrop */}
      <div className="absolute inset-0 border-t border-[var(--card-border)] bg-[rgba(255,253,248,0.92)] backdrop-blur-md" />

      <div className="relative grid h-16 grid-cols-5">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === '/'
              ? pathname === '/'
              : pathname === item.href || pathname.startsWith(item.href + '/');

          return (
            <Link
              key={item.href}
              href={item.href}
              className={[
                'flex flex-col items-center justify-center gap-0.5 text-[10px] font-medium transition-colors',
                isActive
                  ? 'text-[var(--accent)]'
                  : 'text-[var(--muted)] hover:text-[var(--foreground)]',
              ].join(' ')}
              aria-current={isActive ? 'page' : undefined}
            >
              <span
                className={[
                  'flex h-6 w-6 items-center justify-center rounded-full transition-all',
                  isActive ? 'bg-[var(--accent-soft)]' : '',
                ].join(' ')}
              >
                {item.icon(isActive)}
              </span>
              {item.label}
            </Link>
          );
        })}
      </div>

      {/* Safe area spacer for notched phones */}
      <div className="h-safe-area-inset-bottom bg-[rgba(255,253,248,0.92)]" />
    </nav>
  );
}
