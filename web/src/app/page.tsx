import Link from 'next/link';

const HOME_PANELS = [
  {
    eyebrow: 'Research',
    title: 'Read the market before you shortlist.',
    description: 'Start with county trends, incentive coverage, and source quality instead of opening a full control room first.',
    href: '/research',
    cta: 'Open research view',
  },
  {
    eyebrow: 'Workspace',
    title: 'Keep the advanced map workspace, but behind one click.',
    description: 'The original compare-and-analyze interface now lives on its own route so the product can rebuild from a calmer starting point.',
    href: '/workspace',
    cta: 'Open workspace',
  },
  {
    eyebrow: 'Operations',
    title: 'Check alerts, grants, and source health separately.',
    description: 'Administrative and monitoring tasks stay available, but no longer dominate the first screen.',
    href: '/alerts',
    cta: 'Review action queue',
  },
];

const QUICK_LINKS = [
  { href: '/workspace?focus=ask', label: 'Ask Atlas' },
  { href: '/analytics', label: 'Market analytics' },
  { href: '/grants', label: 'Grant incentives' },
  { href: '/sources', label: 'Source health' },
  { href: '/settings', label: 'Settings' },
];

export default function HomePage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 lg:px-6 lg:py-10">
      <section className="relative overflow-hidden rounded-[28px] border border-[var(--card-border)] bg-[linear-gradient(145deg,rgba(252,251,248,0.96),rgba(240,236,228,0.88))] p-6 lg:p-10 shadow-[0_24px_80px_rgba(27,36,48,0.08)] rise-in">
        <div className="absolute inset-y-0 right-0 hidden w-[38%] bg-[radial-gradient(circle_at_top,rgba(180,35,24,0.12),transparent_55%),radial-gradient(circle_at_70%_70%,rgba(46,125,91,0.16),transparent_48%)] lg:block" />
        <div className="relative max-w-3xl">
          <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--muted)]">Atlas reset</p>
          <h1 className="mt-3 text-4xl leading-tight lg:text-6xl">Property research first. Complex tooling second.</h1>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-[var(--muted)] lg:text-base">
            The product now opens on a simpler home surface so you can choose the task you actually need: market context, buyer incentives, source operations, or the full compare workspace.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/workspace"
              className="inline-flex items-center rounded-full border border-[var(--accent)] bg-[var(--accent)] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-strong)]"
            >
              Open decision workspace
            </Link>
            <Link
              href="/research"
              className="inline-flex items-center rounded-full border border-[var(--card-border)] bg-[var(--card-bg)] px-5 py-2.5 text-sm font-medium text-[var(--foreground)] transition-colors hover:bg-white"
            >
              Start with research
            </Link>
          </div>
        </div>
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-3">
        {HOME_PANELS.map((panel) => (
          <article
            key={panel.href}
            className="rounded-[22px] border border-[var(--card-border)] bg-[var(--card-bg)]/92 p-5 shadow-[0_14px_40px_rgba(27,36,48,0.06)]"
          >
            <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--muted)]">{panel.eyebrow}</p>
            <h2 className="mt-3 text-2xl leading-snug">{panel.title}</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--muted)]">{panel.description}</p>
            <Link
              href={panel.href}
              className="mt-5 inline-flex items-center text-sm font-medium text-[var(--accent-strong)] hover:underline"
            >
              {panel.cta}
            </Link>
          </article>
        ))}
      </section>

      <section className="mt-6 rounded-[24px] border border-[var(--card-border)] bg-[var(--card-bg)]/85 p-5 lg:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--muted)]">Quick actions</p>
            <h2 className="mt-2 text-2xl">Jump straight into one job.</h2>
          </div>
          <p className="max-w-2xl text-sm leading-6 text-[var(--muted)]">
            This home page is intentionally lighter. The deeper map, compare, AI, and monitoring tools are still available, but they no longer compete for attention on first load.
          </p>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {QUICK_LINKS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-2xl border border-[var(--card-border)] bg-[var(--background)]/65 px-4 py-4 text-sm font-medium transition-colors hover:border-[var(--accent)] hover:bg-white"
            >
              {item.label}
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
