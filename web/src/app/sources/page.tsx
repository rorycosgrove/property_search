'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  approveDiscoveredSource,
  getBackendLogs,
  discoverSourcesAuto,
  getPendingDiscoveredSources,
  getOrganicSearchHistory,
  getSources,
  getAdapters,
  triggerFullOrganicSearch,
  triggerScrape,
  type BackendLogEntry,
  type OrganicSearchHistoryItem,
  type AdapterInfo,
  type Source,
} from '@/lib/api';
import { DashboardHeader } from './_components/DashboardHeader';
import { OverviewTab } from './_components/OverviewTab';
import { SourcesTableTab } from './_components/SourcesTableTab';
import { ActivityTab } from './_components/ActivityTab';
import { HistoryTab } from './_components/HistoryTab';
import type { SourceSort, SourceStatusFilter, SourcesTab } from './_components/types';

function byLatestTimestamp(a?: string, b?: string): number {
  const at = a ? new Date(a).getTime() : 0;
  const bt = b ? new Date(b).getTime() : 0;
  return bt - at;
}

export default function SourcesPage() {
  const [activeTab, setActiveTab] = useState<SourcesTab>('overview');

  const [sources, setSources] = useState<Source[]>([]);
  const [adapters, setAdapters] = useState<AdapterInfo[]>([]);
  const [runHistory, setRunHistory] = useState<OrganicSearchHistoryItem[]>([]);
  const [sourceActivityLogs, setSourceActivityLogs] = useState<BackendLogEntry[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [sourcesError, setSourcesError] = useState<string | null>(null);
  const [activityError, setActivityError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [adaptersError, setAdaptersError] = useState<string | null>(null);

  const [toast, setToast] = useState<string | null>(null);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string | null>(null);

  const [runningFullSearch, setRunningFullSearch] = useState(false);
  const [discoveringSources, setDiscoveringSources] = useState(false);
  const [scrapingSelected, setScrapingSelected] = useState(false);
  const [approvingSelected, setApprovingSelected] = useState(false);

  const [pendingDiscovered, setPendingDiscovered] = useState<Source[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [selectedPendingIds, setSelectedPendingIds] = useState<string[]>([]);

  const [sourceQuery, setSourceQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<SourceStatusFilter>('all');
  const [sourceSort, setSourceSort] = useState<SourceSort>('last_polled');

  const refreshBurstTimersRef = useRef<number[]>([]);
  const refreshInFlightRef = useRef<Promise<void> | null>(null);

  const latestScrapeComplete = useMemo(() => {
    return sourceActivityLogs.find((entry) => entry.event_type === 'scrape_source_complete') ?? null;
  }, [sourceActivityLogs]);

  const pendingApprovalCount = pendingDiscovered.length;
  const enabledCount = useMemo(() => sources.filter((s) => s.enabled).length, [sources]);
  const erroringCount = useMemo(() => sources.filter((s) => (s.error_count ?? 0) > 0).length, [sources]);

  const activeSources = useMemo(
    () => sources.filter((s) => s.enabled && !s.tags?.includes('pending_approval')),
    [sources],
  );

  const scrapeProgress = useMemo(() => {
    const totalEnabled = activeSources.length;
    const lastRunAt = runHistory[0]?.created_at ?? null;
    const completedLogs = sourceActivityLogs.filter(
      (entry) =>
        entry.event_type === 'scrape_source_complete' &&
        (!lastRunAt || new Date(entry.timestamp) >= new Date(lastRunAt)),
    );
    const uniqueIds = new Set(completedLogs.map((e) => e.source_id).filter(Boolean));
    const completed = uniqueIds.size > 0 ? uniqueIds.size : completedLogs.length;
    return { completed, total: totalEnabled };
  }, [activeSources, sourceActivityLogs, runHistory]);

  const filteredSources = useMemo(() => {
    const needle = sourceQuery.trim().toLowerCase();

    const filtered = sources.filter((source) => {
      const isPending = source.tags?.includes('pending_approval');
      const hasErrors = (source.error_count ?? 0) > 0;

      if (statusFilter === 'enabled' && !source.enabled) return false;
      if (statusFilter === 'disabled' && source.enabled) return false;
      if (statusFilter === 'pending' && !isPending) return false;
      if (statusFilter === 'errors' && !hasErrors) return false;

      if (!needle) return true;
      const haystack = [
        source.name,
        source.url,
        source.adapter_name,
        source.adapter_type,
        source.last_error,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(needle);
    });

    filtered.sort((a, b) => {
      if (sourceSort === 'name') return a.name.localeCompare(b.name);
      if (sourceSort === 'errors') return (b.error_count ?? 0) - (a.error_count ?? 0);
      if (sourceSort === 'listings') return (b.total_listings ?? 0) - (a.total_listings ?? 0);
      return byLatestTimestamp(a.last_polled_at, b.last_polled_at);
    });

    return filtered;
  }, [sources, sourceQuery, statusFilter, sourceSort]);

  const visibleSourceIds = useMemo(() => filteredSources.map((s) => s.id), [filteredSources]);
  const allVisibleSelected =
    visibleSourceIds.length > 0 && visibleSourceIds.every((id) => selectedSourceIds.includes(id));

  const clearRefreshBurstTimers = useCallback(() => {
    refreshBurstTimersRef.current.forEach((timer) => window.clearTimeout(timer));
    refreshBurstTimersRef.current = [];
  }, []);

  const withToast = useCallback((message: string, timeoutMs = 3000) => {
    setToast(message);
    window.setTimeout(() => setToast(null), timeoutMs);
  }, []);

  const refreshSourcesView = useCallback(async () => {
    if (refreshInFlightRef.current) {
      return refreshInFlightRef.current;
    }

    const run = (async () => {
      setIsRefreshing(true);

      const [
        sourcesResult,
        pendingResult,
        adaptersResult,
        historyResult,
        logsResult,
      ] = await Promise.allSettled([
        getSources(),
        getPendingDiscoveredSources(),
        getAdapters(),
        getOrganicSearchHistory(20),
        getBackendLogs({ hours: 72, limit: 80 }),
      ]);

      if (sourcesResult.status === 'fulfilled') {
        setSources(sourcesResult.value);
        setSourcesError(null);
      } else {
        console.error(sourcesResult.reason);
        setSourcesError('Sources list is temporarily unavailable.');
      }

      if (pendingResult.status === 'fulfilled') {
        setPendingDiscovered(pendingResult.value);
      }

      if (adaptersResult.status === 'fulfilled') {
        setAdapters(adaptersResult.value);
        setAdaptersError(null);
      } else {
        console.error(adaptersResult.reason);
        setAdaptersError('Adapter metadata failed to refresh.');
      }

      if (historyResult.status === 'fulfilled') {
        setRunHistory(historyResult.value);
        setHistoryError(null);
      } else {
        console.error(historyResult.reason);
        setHistoryError('Run history is unavailable right now.');
      }

      if (logsResult.status === 'fulfilled') {
        const relevantEventPrefixes = ['source_', 'organic_search_', 'discovery_', 'scrape_'];
        const filteredLogs = logsResult.value
          .filter((entry) => relevantEventPrefixes.some((prefix) => entry.event_type.startsWith(prefix)))
          .sort((a, b) => byLatestTimestamp(a.timestamp, b.timestamp));
        setSourceActivityLogs(filteredLogs);
        setActivityError(null);
      } else {
        console.error(logsResult.reason);
        setActivityError('Activity logs are temporarily unavailable.');
      }

      setLastRefreshedAt(new Date().toISOString());
      setIsRefreshing(false);
      setIsLoading(false);
    })();

    refreshInFlightRef.current = run;
    try {
      await run;
    } finally {
      refreshInFlightRef.current = null;
    }
  }, []);

  const scheduleRefreshBurst = useCallback(() => {
    clearRefreshBurstTimers();
    [2000, 6000, 12000].forEach((delay) => {
      const timer = window.setTimeout(() => {
        void refreshSourcesView();
      }, delay);
      refreshBurstTimersRef.current.push(timer);
    });
  }, [clearRefreshBurstTimers, refreshSourcesView]);

  useEffect(() => {
    void refreshSourcesView();
    const interval = window.setInterval(() => {
      void refreshSourcesView();
    }, 15000);

    return () => {
      window.clearInterval(interval);
      clearRefreshBurstTimers();
    };
  }, [clearRefreshBurstTimers, refreshSourcesView]);

  useEffect(() => {
    setSelectedSourceIds((prev) => prev.filter((id) => sources.some((s) => s.id === id)));
  }, [sources]);

  useEffect(() => {
    setSelectedPendingIds((prev) => prev.filter((id) => pendingDiscovered.some((s) => s.id === id)));
  }, [pendingDiscovered]);

  const handleTrigger = async (id: string) => {
    try {
      const response = await triggerScrape(id, { force: true });
      const timestamp = response.timestamp ? new Date(response.timestamp).toLocaleString() : null;
      withToast(
        response.status === 'processed_inline'
          ? `Source forced refresh processed inline${timestamp ? ` at ${timestamp}` : ''}.`
          : `Source forced refresh dispatched${timestamp ? ` at ${timestamp}` : ''}.`,
      );
      await refreshSourcesView();
      scheduleRefreshBurst();
    } catch (error) {
      console.error(error);
      withToast('Failed to trigger source refresh.');
    }
  };

  const handleScrapeSelected = async () => {
    if (selectedSourceIds.length === 0) {
      withToast('Select at least one source to scrape.', 2200);
      return;
    }

    setScrapingSelected(true);
    const results = await Promise.allSettled(
      selectedSourceIds.map((id) => triggerScrape(id, { force: true })),
    );
    const success = results.filter((r) => r.status === 'fulfilled').length;
    const failed = results.length - success;

    withToast(
      failed === 0
        ? `Queued scrape for ${success} selected source${success === 1 ? '' : 's'}.`
        : `Queued ${success} scrape${success === 1 ? '' : 's'} with ${failed} failure${failed === 1 ? '' : 's'}.`,
      3500,
    );

    setScrapingSelected(false);
    setSelectedSourceIds([]);
    await refreshSourcesView();
    scheduleRefreshBurst();
  };

  const handleFullOrganicSearch = async () => {
    setRunningFullSearch(true);
    try {
      const response = await triggerFullOrganicSearch({ force: true });
      const steps = response.steps.map((s) => s.step).join(' -> ');
      const mode = response.status === 'processed_inline' ? 'inline' : response.status;
      const createdAt = response.created_at ? new Date(response.created_at).toLocaleString() : null;
      withToast(
        response.status === 'dispatched'
          ? `Full organic search queued${createdAt ? ` at ${createdAt}` : ''}. Track progress in Recent Source Activity (look for scrape_source_complete).`
          : `Forced full organic search started (${mode})${createdAt ? ` at ${createdAt}` : ''}: ${steps}`,
        3500,
      );
      await refreshSourcesView();
      scheduleRefreshBurst();
    } catch (error) {
      console.error(error);
      withToast('Failed to trigger full organic search.');
    } finally {
      setRunningFullSearch(false);
    }
  };

  const handleDiscoverSources = async () => {
    setDiscoveringSources(true);
    try {
      const result = await discoverSourcesAuto(false, 25);
      const runAt = result.run_at ? new Date(result.run_at).toLocaleString() : null;
      withToast(
        result.created.length > 0
          ? `Discovery complete${runAt ? ` (${runAt})` : ''}: ${result.created.length} new sources added for approval, ${result.existing.length} already known, ${result.skipped_invalid.length} skipped.`
          : `Discovery complete${runAt ? ` (${runAt})` : ''}: no new sources found, ${result.existing.length} already known, ${result.skipped_invalid.length} skipped.`,
        3500,
      );
      await refreshSourcesView();
      scheduleRefreshBurst();
    } catch (error) {
      console.error(error);
      withToast('Failed to auto-discover new sources.');
    } finally {
      setDiscoveringSources(false);
    }
  };

  const handleApproveDiscovered = async (sourceId: string) => {
    try {
      await approveDiscoveredSource(sourceId);
      withToast('Discovered source approved and enabled.', 2500);
      await refreshSourcesView();
      scheduleRefreshBurst();
    } catch (error) {
      console.error(error);
      withToast('Failed to approve discovered source.', 2500);
    }
  };

  const handleApproveSelected = async () => {
    if (selectedPendingIds.length === 0) {
      withToast('Select pending sources to approve first.', 2200);
      return;
    }

    setApprovingSelected(true);
    const results = await Promise.allSettled(selectedPendingIds.map((id) => approveDiscoveredSource(id)));
    const success = results.filter((r) => r.status === 'fulfilled').length;
    const failed = results.length - success;

    withToast(
      failed === 0
        ? `Approved ${success} discovered source${success === 1 ? '' : 's'}.`
        : `Approved ${success}; ${failed} approval${failed === 1 ? '' : 's'} failed.`,
      3200,
    );

    setSelectedPendingIds([]);
    setApprovingSelected(false);
    await refreshSourcesView();
    scheduleRefreshBurst();
  };

  const toggleSourceSelection = (sourceId: string) => {
    setSelectedSourceIds((prev) =>
      prev.includes(sourceId) ? prev.filter((id) => id !== sourceId) : [...prev, sourceId],
    );
  };

  const togglePendingSelection = (sourceId: string) => {
    setSelectedPendingIds((prev) =>
      prev.includes(sourceId) ? prev.filter((id) => id !== sourceId) : [...prev, sourceId],
    );
  };

  const toggleSelectAllVisible = () => {
    if (allVisibleSelected) {
      setSelectedSourceIds((prev) => prev.filter((id) => !visibleSourceIds.includes(id)));
    } else {
      setSelectedSourceIds((prev) => Array.from(new Set([...prev, ...visibleSourceIds])));
    }
  };

  return (
    <div className="p-4 lg:p-6 max-w-7xl mx-auto rise-in">
      <DashboardHeader
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        lastRefreshedAt={lastRefreshedAt}
        isRefreshing={isRefreshing}
        totalSources={sources.length}
        enabledCount={enabledCount}
        pendingApprovalCount={pendingApprovalCount}
        erroringCount={erroringCount}
        scrapeCompleted={scrapeProgress.completed}
        scrapeTotal={scrapeProgress.total}
        latestScrapeTimestamp={latestScrapeComplete?.timestamp ?? null}
        runningFullSearch={runningFullSearch}
        discoveringSources={discoveringSources}
        scrapingSelected={scrapingSelected}
        approvingSelected={approvingSelected}
        selectedSourceCount={selectedSourceIds.length}
        selectedPendingCount={selectedPendingIds.length}
        sourceCountForTab={filteredSources.length}
        activityCountForTab={sourceActivityLogs.length}
        historyCountForTab={runHistory.length}
        onRunFullSearch={() => {
          void handleFullOrganicSearch();
        }}
        onDiscoverSources={() => {
          void handleDiscoverSources();
        }}
        onScrapeSelected={() => {
          void handleScrapeSelected();
        }}
        onApproveSelected={() => {
          void handleApproveSelected();
        }}
        onRefresh={() => {
          void refreshSourcesView();
        }}
      />

      {toast ? (
        <div className="mb-4 rounded-lg border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-3 py-2 text-sm text-[var(--foreground)]">
          {toast}
        </div>
      ) : null}

      {isLoading ? (
        <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-5 text-sm text-[var(--muted)]">
          Loading sources dashboard...
        </div>
      ) : null}

      {!isLoading && activeTab === 'overview' ? (
        <OverviewTab
          pendingDiscovered={pendingDiscovered}
          selectedPendingIds={selectedPendingIds}
          latestScrapeTimestamp={latestScrapeComplete?.timestamp ?? null}
          scrapeCompleted={scrapeProgress.completed}
          scrapeTotal={scrapeProgress.total}
          adapters={adapters}
          sourcesError={sourcesError}
          adaptersError={adaptersError}
          onTogglePendingSelection={togglePendingSelection}
          onApproveDiscovered={(sourceId) => {
            void handleApproveDiscovered(sourceId);
          }}
        />
      ) : null}

      {!isLoading && activeTab === 'sources' ? (
        <SourcesTableTab
          filteredSources={filteredSources}
          selectedSourceIds={selectedSourceIds}
          sourceQuery={sourceQuery}
          statusFilter={statusFilter}
          sourceSort={sourceSort}
          allVisibleSelected={allVisibleSelected}
          visibleSourceCount={visibleSourceIds.length}
          sourcesError={sourcesError}
          onSetSourceQuery={setSourceQuery}
          onSetStatusFilter={setStatusFilter}
          onSetSourceSort={setSourceSort}
          onToggleSelectAllVisible={toggleSelectAllVisible}
          onToggleSourceSelection={toggleSourceSelection}
          onScrapeNow={(sourceId) => {
            void handleTrigger(sourceId);
          }}
        />
      ) : null}

      {!isLoading && activeTab === 'activity' ? (
        <ActivityTab
          sourceActivityLogs={sourceActivityLogs}
          sources={sources}
          activityError={activityError}
        />
      ) : null}

      {!isLoading && activeTab === 'history' ? (
        <HistoryTab
          runHistory={runHistory}
          historyError={historyError}
        />
      ) : null}
    </div>
  );
}
