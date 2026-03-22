import Link from 'next/link';
import DiscoveryFeed from '@/components/DiscoveryFeed';

const SURFACES = [
  {
    eyebrow: 'Search',
    title: 'Find properties.',
    description: 'Filter by county, price, beds, BER, and grants. Eligible-only mode surfaces properties where a confirmed grant reduces the net cost.',
    href: '/search',
    cta: 'Open search',
    accent: 'var(--accent)',
  },
  {
    eyebrow: 'Workspace',
    title: 'Compare and decide.',
    description: 'Map view, side-by-side compare, and Atlas AI chat — ask questions grounded in live listing data, price history, and market signals.',
    href: '/workspace',
    cta: 'Open workspace',
    accent: 'var(--accent)',
  },
  {
    eyebrow: 'Insights',
    title: 'Read the market.',
    description: 'County price trends, property-type breakdowns, recent price changes, and best-value opportunity sets.',
    href: '/analytics',
    cta: 'View market data',
    accent: 'var(--signal)',
  },
  {
    eyebrow: 'Alerts',
    title: 'Act on signals.',
    description: 'Price drops, status changes, grant eligibility updates, and agent-generated priority events across your tracked search criteria.',
    href: '/alerts',
    cta: 'Review alerts',
    accent: 'var(--danger)',
  },
];

const QUICK_LINKS = [
  { href: '/grants', label: 'Grant incentives' },
  { href: '/saved-searches', label: 'Saved searches' },
  { href: '/sold', label: 'Sold comparables' },
  { href: '/workspace?focus=ask', label: 'Ask Atlas AI' },
  { href: '/sources', label: 'Source health' },
  { href: '/admin', label: 'Admin' },
];

export default function HomePage() {
  return (
    <div className="page-shell page-shell-wide">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-[28px] border border-[var(--card-border)] bg-[linear-gradient(145deg,rgba(252,251,248,0.97),rgba(240,236,228,0.9))] p-6 shadow-[0_24px_80px_rgba(27,36,48,0.08)] rise-in lg:p-10">
        <div className="absolute inset-y-0 right-0 hidden w-[42%] bg-[radial-gradient(circle_at_20%_30%,rgba(15,118,110,0.13),transparent_58%),radial-gradient(circle_at_80%_70%,rgba(228,157,55,0.18),transparent_50%)] lg:block" />
        <div className="relative max-w-2xl">
          <div className="inline-block rounded-full border border-[var(--accent-soft-strong)] bg-[var(--accent-soft)] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--accent)]">
            Atlas Field Desk
          </div>
          <h1 className="mt-4 text-4xl leading-tight lg:text-[3.25rem]">
            Property intelligence<br className="hidden lg:block" /> for buyers who do<br className="hidden lg:block" /> their homework.
          </h1>
          <p className="mt-4 max-w-xl text-sm leading-7 text-[var(--muted)] lg:text-base">
            Every property you look at comes with its full price history, grant eligibility, source provenance,
            and AI analysis grounded in evidence — not guesswork.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/search"
              className="inline-flex items-center gap-2 rounded-full border border-[var(--accent)] bg-[var(--accent)] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-strong)]"
            >
              Start searching
            </Link>
            <Link
              href="/workspace?focus=ask"
              className="inline-flex items-center gap-2 rounded-full border border-[var(--card-border)] bg-[var(--card-bg)] px-5 py-2.5 text-sm font-medium text-[var(--foreground)] transition-colors hover:bg-white"
            >
              Ask Atlas AI
            </Link>
          </div>
        </div>
      </section>

      {/* Four surfaces */}
      <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {SURFACES.map((s) => (
          <article
            key={s.href}
            className="group flex flex-col rounded-[22px] border border-[var(--card-border)] bg-[var(--card-bg)] p-5 shadow-[0_8px_24px_rgba(27,36,48,0.05)] transition-shadow hover:shadow-[0_16px_40px_rgba(27,36,48,0.09)]"
          >
            <p
              className="text-[10px] font-semibold uppercase tracking-[0.2em]"
              style={{ color: s.accent }}
            >
              {s.eyebrow}
            </p>
            <h2 className="mt-2 text-xl leading-snug">{s.title}</h2>
            <p className="mt-2 flex-1 text-xs leading-6 text-[var(--muted)]">{s.description}</p>
            <Link
              href={s.href}
              className="mt-4 inline-flex items-center gap-1 text-xs font-semibold transition-colors"
              style={{ color: s.accent }}
            >
              {s.cta}
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5">
                <path fillRule="evenodd" d="M6.22 4.22a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06l-3.25 3.25a.75.75 0 0 1-1.06-1.06L8.94 8 6.22 5.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
              </svg>
            </Link>
          </article>
        ))}
      </section>

      {/* Quick links */}
      <section className="mt-6 rounded-[24px] border border-[var(--card-border)] bg-[var(--card-bg)]/85 p-5 lg:p-6">
        <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--muted)]">Quick access</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-6">
          {QUICK_LINKS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-xl border border-[var(--card-border)] bg-[var(--background)]/65 px-4 py-3 text-xs font-medium text-[var(--foreground)] transition-colors hover:border-[var(--accent)] hover:bg-white"
            >
              {item.label}
            </Link>
          ))}
        </div>
      </section>

      {/* Discovery feed */}
      <section className="mt-6">
        <DiscoveryFeed limit={12} />
      </section>
    </div>
  );
}
