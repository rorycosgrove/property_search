import Link from 'next/link';

const RESEARCH_ITEMS = [
  {
    title: 'Market Signals',
    description: 'Understand county pricing, trend shifts, and heatmap momentum before shortlisting homes.',
    href: '/analytics',
    cta: 'Open market analytics',
  },
  {
    title: 'Buyer Incentives',
    description: 'Review grants and scheme eligibility so budget constraints are realistic from day one.',
    href: '/grants',
    cta: 'Explore incentives',
  },
  {
    title: 'Source Quality',
    description: 'Check ingestion coverage, pending feed approvals, and discovery status across listing sources.',
    href: '/sources',
    cta: 'Manage sources',
  },
];

export default function ResearchPage() {
  return (
    <div className="max-w-6xl mx-auto px-4 lg:px-6 py-8">
      <div className="rounded-2xl border border-[var(--card-border)] bg-[var(--card-bg)]/80 p-6 lg:p-8 mb-6">
        <p className="text-xs uppercase tracking-[0.14em] text-[var(--muted)]">Research phase</p>
        <h1 className="text-3xl mt-2">Build confidence before you shortlist</h1>
        <p className="mt-3 text-sm text-[var(--muted)] max-w-3xl">
          Start here as a home buyer: review market context, incentives, and data source quality.
          Then move to the Decide workspace with clearer criteria and fewer surprises.
        </p>
        <div className="mt-4">
          <Link
            href="/"
            className="inline-flex px-4 py-2 rounded-full border border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)] hover:bg-[var(--accent-soft-strong)] text-sm"
          >
            Continue to Decide workspace
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {RESEARCH_ITEMS.map((item) => (
          <article key={item.href} className="rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-5 rise-in">
            <h2 className="text-xl">{item.title}</h2>
            <p className="mt-2 text-sm text-[var(--muted)] leading-relaxed">{item.description}</p>
            <Link
              href={item.href}
              className="mt-4 inline-flex text-sm font-medium text-[var(--accent-strong)] hover:underline"
            >
              {item.cta}
            </Link>
          </article>
        ))}
      </div>
    </div>
  );
}
