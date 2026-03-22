'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import {
  getAlerts,
  getAnalyticsSummary,
  getGrants,
  getHealth,
  getProperties,
  getSavedSearches,
  getSoldProperties,
  getSources,
} from '@/lib/api';

type EndpointCheck = {
  key: string;
  label: string;
  route: string;
  state: 'ok' | 'error' | 'loading';
  detail: string;
};

const ADMIN_CARDS = [
  {
    title: 'Source Operations',
    description:
      'Manage adapters, approve discovered feeds, trigger scrapes, and monitor ingestion activity.',
    href: '/sources',
    cta: 'Open source operations',
  },
  {
    title: 'Alerts Queue',
    description:
      'Review system and workflow alerts, track unread items, and validate processing health.',
    href: '/alerts',
    cta: 'Open alerts queue',
  },
  {
    title: 'Backend Diagnostics',
    description:
      'Inspect backend logs, feed activity, source health summaries, and queue readiness from admin log endpoints.',
    href: '/settings#backend-diagnostics',
    cta: 'Open backend diagnostics',
  },
  {
    title: 'Listing Repair Console',
    description:
      'Run listing diagnose and repair actions for missed ingest cases using the admin listing repair endpoints.',
    href: '/settings#listing-diagnostics',
    cta: 'Open listing repair console',
  },
  {
    title: 'System Settings',
    description:
      'Adjust runtime settings, model preferences, and operator controls used across the workspace.',
    href: '/settings',
    cta: 'Open settings',
  },
  {
    title: 'Copilot Tools',
    description:
      'Use assistant workflows for operational troubleshooting and guided actions.',
    href: '/copilot',
    cta: 'Open copilot tools',
  },
];

export default function AdminPage() {
  const [checks, setChecks] = useState<EndpointCheck[]>([
    { key: 'health', label: 'Platform health', route: '/admin', state: 'loading', detail: 'Checking...' },
    { key: 'properties', label: 'Properties domain', route: '/workspace', state: 'loading', detail: 'Checking...' },
    { key: 'analytics', label: 'Analytics domain', route: '/analytics', state: 'loading', detail: 'Checking...' },
    { key: 'sold', label: 'Sold comparables', route: '/sold', state: 'loading', detail: 'Checking...' },
    { key: 'grants', label: 'Grants domain', route: '/grants', state: 'loading', detail: 'Checking...' },
    { key: 'alerts', label: 'Alerts domain', route: '/alerts', state: 'loading', detail: 'Checking...' },
    { key: 'saved', label: 'Saved searches', route: '/saved-searches', state: 'loading', detail: 'Checking...' },
    { key: 'sources', label: 'Sources operations', route: '/sources', state: 'loading', detail: 'Checking...' },
  ]);

  useEffect(() => {
    let cancelled = false;

    const runChecks = async () => {
      const results = await Promise.allSettled([
        getHealth(),
        getProperties({ size: 1 }),
        getAnalyticsSummary(),
        getSoldProperties({ size: 1 }),
        getGrants('IE', true),
        getAlerts({ size: 1 }),
        getSavedSearches(),
        getSources(),
      ]);

      if (cancelled) {
        return;
      }

      const next: EndpointCheck[] = [
        {
          key: 'health',
          label: 'Platform health',
          route: '/admin',
          state: results[0].status === 'fulfilled' ? 'ok' : 'error',
          detail: results[0].status === 'fulfilled'
            ? `status ${(results[0].value.status || 'unknown').toString()}`
            : 'health endpoint failed',
        },
        {
          key: 'properties',
          label: 'Properties domain',
          route: '/workspace',
          state: results[1].status === 'fulfilled' ? 'ok' : 'error',
          detail: results[1].status === 'fulfilled'
            ? `${results[1].value.total} total records`
            : 'properties endpoint failed',
        },
        {
          key: 'analytics',
          label: 'Analytics domain',
          route: '/analytics',
          state: results[2].status === 'fulfilled' ? 'ok' : 'error',
          detail: results[2].status === 'fulfilled'
            ? `${results[2].value.total_active_listings} active listings`
            : 'analytics endpoint failed',
        },
        {
          key: 'sold',
          label: 'Sold comparables',
          route: '/sold',
          state: results[3].status === 'fulfilled' ? 'ok' : 'error',
          detail: results[3].status === 'fulfilled'
            ? `${results[3].value.total} sold records`
            : 'sold endpoint failed',
        },
        {
          key: 'grants',
          label: 'Grants domain',
          route: '/grants',
          state: results[4].status === 'fulfilled' ? 'ok' : 'error',
          detail: results[4].status === 'fulfilled'
            ? `${results[4].value.length} active grants`
            : 'grants endpoint failed',
        },
        {
          key: 'alerts',
          label: 'Alerts domain',
          route: '/alerts',
          state: results[5].status === 'fulfilled' ? 'ok' : 'error',
          detail: results[5].status === 'fulfilled'
            ? `${results[5].value.total} alerts`
            : 'alerts endpoint failed',
        },
        {
          key: 'saved',
          label: 'Saved searches',
          route: '/saved-searches',
          state: results[6].status === 'fulfilled' ? 'ok' : 'error',
          detail: results[6].status === 'fulfilled'
            ? `${results[6].value.length} saved searches`
            : 'saved-search endpoint failed',
        },
        {
          key: 'sources',
          label: 'Sources operations',
          route: '/sources',
          state: results[7].status === 'fulfilled' ? 'ok' : 'error',
          detail: results[7].status === 'fulfilled'
            ? `${results[7].value.length} configured sources`
            : 'sources endpoint failed',
        },
      ];

      setChecks(next);
    };

    void runChecks();
    const timer = window.setInterval(runChecks, 45000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const checkSummary = useMemo(() => {
    const ok = checks.filter((item) => item.state === 'ok').length;
    const errored = checks.filter((item) => item.state === 'error').length;
    return { ok, errored, total: checks.length };
  }, [checks]);

  return (
    <div className="page-shell page-shell-wide rise-in">
      <section className="page-hero">
        <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">Admin interface</p>
        <h1 className="mt-2 text-3xl lg:text-4xl">Operations and control center</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--muted)] lg:text-base">
          This is the dedicated admin area. If you need data-source control, alert triage, or operator settings,
          start here instead of navigating through research and buyer workflows.
        </p>
      </section>

      <section className="mt-6 page-section-card">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted)]">Endpoint coverage</p>
            <h2 className="mt-1 text-2xl">API domains wired to UI routes</h2>
          </div>
          <div className="rounded-full border border-[var(--card-border)] px-3 py-1 text-xs text-[var(--muted)]">
            {checkSummary.ok}/{checkSummary.total} healthy
          </div>
        </div>

        {checkSummary.errored > 0 ? (
          <p className="mb-3 rounded-lg border border-[var(--danger)]/35 bg-[var(--danger)]/10 px-3 py-2 text-sm text-[var(--danger)]">
            {checkSummary.errored} endpoint group{checkSummary.errored === 1 ? '' : 's'} currently failing.
          </p>
        ) : null}

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          {checks.map((check) => (
            <article key={check.key} className="rounded-lg border border-[var(--card-border)] bg-[var(--surface)] p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold">{check.label}</p>
                <span
                  className={[
                    'rounded-full border px-2 py-0.5 text-[11px]',
                    check.state === 'ok'
                      ? 'border-emerald-300/50 bg-emerald-200/35 text-emerald-700'
                      : check.state === 'error'
                        ? 'border-rose-300/50 bg-rose-200/35 text-rose-700'
                        : 'border-[var(--card-border)] bg-[var(--background)] text-[var(--muted)]',
                  ].join(' ')}
                >
                  {check.state}
                </span>
              </div>
              <p className="mt-1 text-xs text-[var(--muted)]">{check.detail}</p>
              <Link href={check.route} className="mt-3 inline-flex text-xs text-[var(--accent-strong)] hover:underline">
                Open route
              </Link>
            </article>
          ))}
        </div>
      </section>

      <section className="mt-6 grid gap-4 md:grid-cols-2">
        {ADMIN_CARDS.map((card) => (
          <article key={card.href} className="page-section-card soft-card">
            <h2 className="text-xl">{card.title}</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{card.description}</p>
            <Link href={card.href} className="ui-btn ui-btn-primary mt-4 inline-flex items-center">
              {card.cta}
            </Link>
          </article>
        ))}
      </section>
    </div>
  );
}
