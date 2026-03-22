'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import {
  getAlerts,
  getAnalyticsSummary,
  getDataLifecycleHistory,
  getDataLifecycleReport,
  getGrants,
  getHealth,
  getProperties,
  runDataLifecycleAction,
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
    title: 'Data Lifecycle',
    description:
      'Inspect archival and rollup candidate counts before running retention jobs across properties, logs, and history tables.',
    href: '/settings#data-lifecycle',
    cta: 'Open lifecycle controls',
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
  const [lifecycleSummary, setLifecycleSummary] = useState<string>('Loading lifecycle candidates...');
  const [lifecycleActionStatus, setLifecycleActionStatus] = useState<string>('No lifecycle dry-run executed yet.');
  const [lifecycleActionBusy, setLifecycleActionBusy] = useState<string | null>(null);
  const [lifecycleHistory, setLifecycleHistory] = useState<Array<{
    id: string;
    timestamp?: string;
    message: string;
    context: Record<string, unknown>;
  }>>([]);
  const [checks, setChecks] = useState<EndpointCheck[]>([
    { key: 'health', label: 'Platform health', route: '/admin', state: 'loading', detail: 'Checking...' },
    { key: 'properties', label: 'Properties domain', route: '/workspace', state: 'loading', detail: 'Checking...' },
    { key: 'analytics', label: 'Analytics domain', route: '/analytics', state: 'loading', detail: 'Checking...' },
    { key: 'sold', label: 'Sold comparables', route: '/sold', state: 'loading', detail: 'Checking...' },
    { key: 'grants', label: 'Grants domain', route: '/grants', state: 'loading', detail: 'Checking...' },
    { key: 'alerts', label: 'Alerts domain', route: '/alerts', state: 'loading', detail: 'Checking...' },
    { key: 'saved', label: 'Saved searches', route: '/saved-searches', state: 'loading', detail: 'Checking...' },
    { key: 'sources', label: 'Sources operations', route: '/sources', state: 'loading', detail: 'Checking...' },
    { key: 'lifecycle', label: 'Data lifecycle', route: '/settings#data-lifecycle', state: 'loading', detail: 'Checking...' },
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
        getDataLifecycleReport(),
        getDataLifecycleHistory({ hours: 168, limit: 8 }),
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
        {
          key: 'lifecycle',
          label: 'Data lifecycle',
          route: '/settings#data-lifecycle',
          state: results[8].status === 'fulfilled' ? 'ok' : 'error',
          detail: results[8].status === 'fulfilled'
            ? `${results[8].value.candidates.property_archive} archive · ${results[8].value.candidates.price_history_rollup} rollup`
            : 'lifecycle endpoint failed',
        },
      ];

      if (results[8].status === 'fulfilled') {
        const c = results[8].value.candidates;
        setLifecycleSummary(
          `${c.property_archive.toLocaleString()} properties, ${c.backend_log_archive.toLocaleString()} logs, ${c.price_history_rollup.toLocaleString()} price history rows, and ${c.timeline_rollup.toLocaleString()} timeline rows currently eligible.`
        );
      } else {
        setLifecycleSummary('Unable to load lifecycle candidate counts.');
      }

      if (results[9].status === 'fulfilled') {
        setLifecycleHistory(results[9].value.map((row) => ({
          id: row.id,
          timestamp: row.timestamp,
          message: row.message,
          context: row.context,
        })));
      } else {
        setLifecycleHistory([]);
      }

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

  const runLifecycleDryRun = async (
    action: 'archive_properties' | 'archive_backend_logs' | 'rollup_price_and_timeline',
  ) => {
    setLifecycleActionBusy(action);
    try {
      const result = await runDataLifecycleAction(action, { dryRun: true });
      setLifecycleActionStatus(
        `${result.action} dry-run complete: ${result.affected_candidates.toLocaleString()} candidates.`
      );
      const history = await getDataLifecycleHistory({ hours: 168, limit: 8 });
      setLifecycleHistory(history.map((row) => ({
        id: row.id,
        timestamp: row.timestamp,
        message: row.message,
        context: row.context,
      })));
    } catch {
      setLifecycleActionStatus(`${action} dry-run failed. Check backend logs.`);
    } finally {
      setLifecycleActionBusy(null);
    }
  };

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

      <section className="mt-6 rounded-2xl border border-[var(--card-border)] bg-[var(--card-bg)]/85 p-5">
        <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted)]">Lifecycle preview</p>
        <h2 className="mt-1 text-2xl">Retention dry-run snapshot</h2>
        <p className="mt-2 max-w-4xl text-sm leading-6 text-[var(--muted)]">{lifecycleSummary}</p>
        <p className="mt-2 text-xs text-[var(--muted)]">{lifecycleActionStatus}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => runLifecycleDryRun('archive_properties')}
            disabled={lifecycleActionBusy !== null}
            className="rounded-full border border-[var(--card-border)] bg-[var(--card-bg)] px-3 py-1.5 text-xs font-medium text-[var(--foreground)] transition-colors hover:border-[var(--accent)] disabled:opacity-60"
          >
            {lifecycleActionBusy === 'archive_properties' ? 'Running…' : 'Dry-run archive properties'}
          </button>
          <button
            type="button"
            onClick={() => runLifecycleDryRun('archive_backend_logs')}
            disabled={lifecycleActionBusy !== null}
            className="rounded-full border border-[var(--card-border)] bg-[var(--card-bg)] px-3 py-1.5 text-xs font-medium text-[var(--foreground)] transition-colors hover:border-[var(--accent)] disabled:opacity-60"
          >
            {lifecycleActionBusy === 'archive_backend_logs' ? 'Running…' : 'Dry-run archive logs'}
          </button>
          <button
            type="button"
            onClick={() => runLifecycleDryRun('rollup_price_and_timeline')}
            disabled={lifecycleActionBusy !== null}
            className="rounded-full border border-[var(--card-border)] bg-[var(--card-bg)] px-3 py-1.5 text-xs font-medium text-[var(--foreground)] transition-colors hover:border-[var(--accent)] disabled:opacity-60"
          >
            {lifecycleActionBusy === 'rollup_price_and_timeline' ? 'Running…' : 'Dry-run rollup history'}
          </button>
        </div>
        <Link href="/settings#data-lifecycle" className="mt-3 inline-flex text-sm font-medium text-[var(--accent-strong)] hover:underline">
          Open lifecycle settings
        </Link>

        <div className="mt-5 rounded-xl border border-[var(--card-border)] bg-[var(--background)]/55 p-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted)]">Recent lifecycle runs</p>
          {lifecycleHistory.length === 0 ? (
            <p className="mt-2 text-xs text-[var(--muted)]">No lifecycle actions recorded in the selected lookback.</p>
          ) : (
            <ul className="mt-2 space-y-2">
              {lifecycleHistory.map((entry) => {
                const action = typeof entry.context.action === 'string' ? entry.context.action : 'unknown';
                const affected = typeof entry.context.affected_candidates === 'number'
                  ? entry.context.affected_candidates
                  : Number(entry.context.affected_candidates ?? 0);
                return (
                  <li key={entry.id} className="rounded-lg border border-[var(--card-border)] bg-[var(--card-bg)] px-3 py-2">
                    <p className="text-xs font-medium">{action}</p>
                    <p className="text-[11px] text-[var(--muted)]">
                      {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : 'unknown time'} · {affected.toLocaleString()} candidates
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
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
