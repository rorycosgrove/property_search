'use client';

import { useEffect, useState } from 'react';
import {
  approveDiscoveredSource,
  discoverSourcesAuto,
  getPendingDiscoveredSources,
  getOrganicSearchHistory,
  getSources,
  getAdapters,
  triggerFullOrganicSearch,
  triggerScrape,
  type OrganicSearchHistoryItem,
  type AdapterInfo,
  type Source,
} from '@/lib/api';
import { formatDate } from '@/lib/utils';

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [adapters, setAdapters] = useState<AdapterInfo[]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const [runningFullSearch, setRunningFullSearch] = useState(false);
  const [discoveringSources, setDiscoveringSources] = useState(false);
  const [pendingDiscovered, setPendingDiscovered] = useState<Source[]>([]);
  const [runHistory, setRunHistory] = useState<OrganicSearchHistoryItem[]>([]);

  const loadRunHistory = () => {
    getOrganicSearchHistory(20).then(setRunHistory).catch(console.error);
  };

  const loadPendingDiscovered = () => {
    getPendingDiscoveredSources().then(setPendingDiscovered).catch(console.error);
  };

  useEffect(() => {
    getSources().then(setSources).catch(console.error);
    getAdapters().then(setAdapters).catch(console.error);

    loadRunHistory();
    loadPendingDiscovered();
  }, []);

  const handleTrigger = async (id: string) => {
    const response = await triggerScrape(id, { force: true });
    setToast(response.status === 'processed_inline'
      ? 'Source forced refresh processed inline (local mode).'
      : 'Source forced refresh dispatched to queue.');
    window.setTimeout(() => setToast(null), 2500);
  };

  const handleFullOrganicSearch = async () => {
    setRunningFullSearch(true);
    try {
      const response = await triggerFullOrganicSearch({ force: true });
      const steps = response.steps.map((s) => s.step).join(' -> ');
      const mode = response.status === 'processed_inline' ? 'inline' : response.status;
      setToast(`Forced full organic search started (${mode}): ${steps}`);

      loadRunHistory();

      getSources().then(setSources).catch(console.error);
    } catch (error) {
      console.error(error);
      setToast('Failed to trigger full organic search.');
    } finally {
      setRunningFullSearch(false);
      window.setTimeout(() => setToast(null), 3500);
    }
  };

  const handleDiscoverSources = async () => {
    setDiscoveringSources(true);
    try {
      const result = await discoverSourcesAuto(true, 25);
      const runAt = result.run_at ? new Date(result.run_at).toLocaleString() : null;
      setToast(
        `Discovery complete${runAt ? ` (${runAt})` : ''}: ${result.created.length} created and enabled, ${result.existing.length} already known, ${result.skipped_invalid.length} skipped.`,
      );
      getSources().then(setSources).catch(console.error);
      loadPendingDiscovered();
    } catch (error) {
      console.error(error);
      setToast('Failed to auto-discover new sources.');
    } finally {
      setDiscoveringSources(false);
      window.setTimeout(() => setToast(null), 3500);
    }
  };

  const handleApproveDiscovered = async (sourceId: string) => {
    try {
      await approveDiscoveredSource(sourceId);
      setToast('Discovered source approved and enabled.');
      getSources().then(setSources).catch(console.error);
      loadPendingDiscovered();
      window.setTimeout(() => setToast(null), 2500);
    } catch (error) {
      console.error(error);
      setToast('Failed to approve discovered source.');
      window.setTimeout(() => setToast(null), 2500);
    }
  };

  return (
    <div className="p-4 lg:p-6 max-w-6xl mx-auto rise-in">
      <div className="mb-6 rounded-2xl border border-[var(--card-border)] bg-[var(--card-bg)]/90 p-5 lg:p-6">
        <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">Data Operations</p>
        <h1 className="text-2xl lg:text-3xl font-semibold mt-1">Source readiness and ingestion control</h1>
        <p className="text-sm text-[var(--muted)] mt-2 max-w-3xl">
          Manage ingestion reliability, trigger full scrape runs, and monitor discovery outcomes without leaving the map-first workflow.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            onClick={handleFullOrganicSearch}
            disabled={runningFullSearch}
            className="text-sm px-4 py-2 rounded-md bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)] disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {runningFullSearch ? 'Running Full Organic Search...' : 'Run Full Organic Search'}
          </button>
          <button
            onClick={handleDiscoverSources}
            disabled={discoveringSources}
            className="text-sm px-4 py-2 rounded-md border border-[var(--card-border)] bg-[var(--card-bg)] hover:bg-[var(--background)] disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {discoveringSources ? 'Discovering Feeds...' : 'Auto-Discover & Enable Feeds'}
          </button>
        </div>
      </div>

      {toast ? (
        <div className="mb-4 rounded-lg border border-[var(--accent)]/30 bg-cyan-900/10 px-3 py-2 text-sm text-[var(--foreground)]">
          {toast}
        </div>
      ) : null}

      <div className="mb-8 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-4 lg:p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Full Run History</h2>
          <button
            onClick={loadRunHistory}
            className="text-xs px-2 py-1 border border-[var(--card-border)] rounded hover:bg-[var(--background)]"
          >
            Refresh
          </button>
        </div>

        {runHistory.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No full organic-search runs recorded yet.</p>
        ) : (
          <div className="space-y-3">
            {runHistory.map((run) => {
              const scrape = run.steps[0]?.result as Record<string, unknown> | undefined;
              const discovery = scrape?.discovery_during_scrape as Record<string, unknown> | undefined;
              const sourcesSummary = scrape?.source_summary as Record<string, unknown> | undefined;
              return (
                <article key={run.id} className="rounded-lg border border-[var(--card-border)] bg-[var(--background)]/70 p-3">
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    <p className="text-sm font-medium">{formatDate(run.created_at) || run.created_at}</p>
                    <span className="px-2 py-0.5 rounded text-xs bg-[var(--card-bg)] border border-[var(--card-border)]">
                      {run.status}
                    </span>
                  </div>
                  <p className="font-mono text-xs break-all text-[var(--muted)]">
                    {run.steps.map((step) => `${step.step}:${step.status}`).join(' | ')}
                  </p>
                  {discovery || sourcesSummary ? (
                    <div className="mt-2 text-xs text-[var(--muted)] space-y-1">
                      {discovery ? (
                        <p>
                          discovery: created {String(discovery.created ?? 0)}, enabled {String(discovery.created_enabled ?? 0)}, pending {String(discovery.created_pending_approval ?? 0)}
                        </p>
                      ) : null}
                      {sourcesSummary ? (
                        <p>
                          sources: enabled {String(sourcesSummary.enabled ?? 0)}/{String(sourcesSummary.total ?? 0)}, pending {String(sourcesSummary.pending_approval ?? 0)}, disabled by errors {String(sourcesSummary.disabled_by_errors ?? 0)}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </div>

      <div className="mb-8 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-4 lg:p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Pending Feed Approvals</h2>
          <button
            onClick={loadPendingDiscovered}
            className="text-xs px-2 py-1 border border-[var(--card-border)] rounded hover:bg-[var(--background)]"
          >
            Refresh
          </button>
        </div>

        {pendingDiscovered.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No discovered feeds waiting for approval.</p>
        ) : (
          <div className="space-y-3">
            {pendingDiscovered.map((source) => (
              <div
                key={source.id}
                className="border border-[var(--card-border)] rounded-md p-3 flex items-center justify-between gap-3"
              >
                <div>
                  <p className="text-sm font-medium">{source.name}</p>
                  <p className="text-xs text-[var(--muted)]">{source.url}</p>
                </div>
                <button
                  onClick={() => handleApproveDiscovered(source.id)}
                  className="text-xs px-3 py-1.5 rounded border border-[var(--accent)] bg-cyan-900/10 text-[var(--accent-strong)] hover:bg-cyan-900/15"
                >
                  Approve & Enable
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Active sources */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Configured Sources</h2>
        <div className="space-y-3">
          {sources.map((source) => (
            <div
              key={source.id}
              className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-xl p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
            >
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-medium">{source.name}</h3>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    source.enabled ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'
                  }`}>
                    {source.enabled ? 'Active' : 'Disabled'}
                  </span>
                  <span className="text-xs text-[var(--muted)] bg-[var(--background)] px-1.5 py-0.5 rounded">
                    {source.adapter_name}
                  </span>
                </div>
                <p className="text-xs text-[var(--muted)]">
                  Last polled: {formatDate(source.last_polled_at) || 'Never'} ·
                  Listings: {source.total_listings ?? 0}
                  {source.error_count > 0 && (
                    <span className="text-red-400 ml-1">
                      ({source.error_count} errors)
                    </span>
                  )}
                </p>
                {source.last_error ? (
                  <p className="text-xs text-[var(--danger)] mt-1">Last error: {source.last_error}</p>
                ) : null}
                {source.tags?.includes('pending_approval') ? (
                  <p className="text-xs text-amber-300 mt-1">Pending approval: not included in scrape dispatch.</p>
                ) : null}
              </div>
              <button
                onClick={() => handleTrigger(source.id)}
                className="text-sm px-3 py-1.5 bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)] rounded transition-colors w-full sm:w-auto"
              >
                Scrape Now
              </button>
            </div>
          ))}

          {sources.length === 0 && (
            <p className="text-[var(--muted)] text-sm">No sources configured yet.</p>
          )}
        </div>
      </div>

      {/* Available adapters */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Available Adapters</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {adapters.map((adapter) => (
            <div
              key={adapter.name}
              className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4"
            >
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-medium">{adapter.name}</h3>
                <span className="text-xs text-[var(--muted)] bg-[var(--background)] px-1.5 py-0.5 rounded">
                  {adapter.adapter_type}
                </span>
              </div>
              <p className="text-sm text-[var(--muted)]">{adapter.description}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
