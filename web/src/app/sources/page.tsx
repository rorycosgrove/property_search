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
    const response = await triggerScrape(id);
    setToast(response.status === 'processed_inline'
      ? 'Source processed inline (local mode).'
      : 'Scrape dispatched to queue.');
    window.setTimeout(() => setToast(null), 2500);
  };

  const handleFullOrganicSearch = async () => {
    setRunningFullSearch(true);
    try {
      const response = await triggerFullOrganicSearch();
      const steps = response.steps.map((s) => s.step).join(' -> ');
      const mode = response.status === 'processed_inline' ? 'inline' : response.status;
      setToast(`Full organic search started (${mode}): ${steps}`);

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
      const result = await discoverSourcesAuto(false, 25);
      setToast(
        `Discovery complete: ${result.created.length} created, ${result.existing.length} already known, ${result.skipped_invalid.length} skipped.`,
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
    <div className="p-6 max-w-5xl mx-auto rise-in">
      <div className="mb-6">
        <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">Data Operations</p>
        <h1 className="text-2xl font-bold">Source readiness and ingestion control</h1>
        <div className="mt-3">
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
            className="text-sm ml-2 px-4 py-2 rounded-md border border-[var(--card-border)] bg-[var(--card-bg)] hover:bg-[var(--background)] disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {discoveringSources ? 'Discovering Feeds...' : 'Auto-Discover Feeds'}
          </button>
        </div>
      </div>

      {toast ? (
        <div className="mb-4 rounded-lg border border-[var(--accent)]/30 bg-cyan-900/10 px-3 py-2 text-sm text-[var(--foreground)]">
          {toast}
        </div>
      ) : null}

      <div className="mb-8 rounded-lg border border-[var(--card-border)] bg-[var(--card-bg)] p-4">
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
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[var(--muted)] border-b border-[var(--card-border)]">
                  <th className="py-2 pr-3">Started</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2">Steps</th>
                </tr>
              </thead>
              <tbody>
                {runHistory.map((run) => (
                  <tr key={run.id} className="border-b border-[var(--card-border)]/50 align-top">
                    <td className="py-2 pr-3 whitespace-nowrap">{formatDate(run.created_at) || run.created_at}</td>
                    <td className="py-2 pr-3">
                      <span className="px-2 py-0.5 rounded text-xs bg-[var(--background)] border border-[var(--card-border)]">
                        {run.status}
                      </span>
                    </td>
                    <td className="py-2 font-mono text-xs break-all">
                      {run.steps.map((step) => `${step.step}:${step.status}`).join(' | ')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="mb-8 rounded-lg border border-[var(--card-border)] bg-[var(--card-bg)] p-4">
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
              className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4 flex items-center justify-between"
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
              </div>
              <button
                onClick={() => handleTrigger(source.id)}
                className="text-sm px-3 py-1.5 bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)] rounded transition-colors"
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
