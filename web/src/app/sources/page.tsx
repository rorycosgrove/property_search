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
  resetSourceCursor,
  getSourceNetNewSummary,
  type BackendLogEntry,
  type OrganicSearchHistoryItem,
  type AdapterInfo,
  type Source,
  type SourceNetNewSummaryItem,
} from '@/lib/api';
import { DashboardHeader } from './_components/DashboardHeader';
import { OverviewTab } from './_components/OverviewTab';
import { SourcesTableTab } from './_components/SourcesTableTab';
import { ActivityTab } from './_components/ActivityTab';
import { HistoryTab } from './_components/HistoryTab';
import { IngestHealthTab } from './_components/IngestHealthTab';
import type { SourceSort, SourceStatusFilter, SourcesTab } from './_components/types';
import { LoadingBlock, LoadingRows } from '@/components/LoadingState';

const SOURCES_PAGE_SIZE = 25;
const ACTIVITY_PAGE_SIZE = 25;
const HISTORY_PAGE_SIZE = 8;

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
  const [netNewSummary, setNetNewSummary] = useState<SourceNetNewSummaryItem[]>([]);
  const [netNewError, setNetNewError] = useState<string | null>(null);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [selectedPendingIds, setSelectedPendingIds] = useState<string[]>([]);

  const [sourceQuery, setSourceQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<SourceStatusFilter>('all');
  const [sourceSort, setSourceSort] = useState<SourceSort>('last_polled');
  const [sourcesPage, setSourcesPage] = useState(1);
  const [activityPage, setActivityPage] = useState(1);
  const [historyPage, setHistoryPage] = useState(1);

  const renderLoadingPanel = () => {
    if (activeTab === 'sources') {
      return (
        <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-5">
          <LoadingBlock className="h-5 w-48" />
          <LoadingRows rows={8} />
        </div>
      );
    }

    if (activeTab === 'activity' || activeTab === 'history') {
      return (
        <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-5">
          <LoadingBlock className="h-5 w-40" />
          <LoadingRows rows={6} />
        </div>
      );
    }

    return (
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-5">
          <LoadingBlock className="h-5 w-44" />
          <LoadingRows rows={4} />
        </div>
        <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-5">
          <LoadingBlock className="h-5 w-40" />
          <LoadingRows rows={4} />
        </div>
      </div>
    );
  };

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
  const sourcesTotalPages = Math.max(1, Math.ceil(filteredSources.length / SOURCES_PAGE_SIZE));
  const pagedFilteredSources = useMemo(() => {
    const start = (sourcesPage - 1) * SOURCES_PAGE_SIZE;
    return filteredSources.slice(start, start + SOURCES_PAGE_SIZE);
  }, [filteredSources, sourcesPage]);
  const pagedVisibleSourceIds = useMemo(() => pagedFilteredSources.map((s) => s.id), [pagedFilteredSources]);
  const pagedActivityLogs = useMemo(() => {
    const start = (activityPage - 1) * ACTIVITY_PAGE_SIZE;
    return sourceActivityLogs.slice(start, start + ACTIVITY_PAGE_SIZE);
  }, [sourceActivityLogs, activityPage]);
  const activityTotalPages = Math.max(1, Math.ceil(sourceActivityLogs.length / ACTIVITY_PAGE_SIZE));
  const pagedRunHistory = useMemo(() => {
    const start = (historyPage - 1) * HISTORY_PAGE_SIZE;
    return runHistory.slice(start, start + HISTORY_PAGE_SIZE);
  }, [runHistory, historyPage]);
  const historyTotalPages = Math.max(1, Math.ceil(runHistory.length / HISTORY_PAGE_SIZE));
  const allVisibleSelected =
    pagedVisibleSourceIds.length > 0 && pagedVisibleSourceIds.every((id) => selectedSourceIds.includes(id));

  useEffect(() => {
    setSourcesPage(1);
  }, [sourceQuery, statusFilter, sourceSort]);

  useEffect(() => {
    setSourcesPage((prev) => Math.min(prev, sourcesTotalPages));
  }, [sourcesTotalPages]);

  useEffect(() => {
    setActivityPage((prev) => Math.min(prev, activityTotalPages));
  }, [activityTotalPages]);

  useEffect(() => {
    setHistoryPage((prev) => Math.min(prev, historyTotalPages));
  }, [historyTotalPages]);

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
        netNewResult,
      ] = await Promise.allSettled([
        getSources(),
        getPendingDiscoveredSources(),
        getAdapters(),
        getOrganicSearchHistory(20),
        getBackendLogs({ hours: 72, limit: 80 }),
        getSourceNetNewSummary(20),
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

      if (netNewResult.status === 'fulfilled') {
        setNetNewSummary(netNewResult.value);
        setNetNewError(null);
      } else {
        console.error(netNewResult.reason);
        setNetNewError('Ingest health data is temporarily unavailable.');
      }

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

  const handleResetCursor = async (sourceId: string) => {
    try {
      const result = await resetSourceCursor(sourceId);
      withToast(`Cursor reset for "${result.source_name}".`, 2500);
      await refreshSourcesView();
    } catch (error) {
      console.error(error);
      withToast('Failed to reset cursor.', 2500);
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
      setSelectedSourceIds((prev) => prev.filter((id) => !pagedVisibleSourceIds.includes(id)));
    } else {
      setSelectedSourceIds((prev) => Array.from(new Set([...prev, ...pagedVisibleSourceIds])));
    }
  };

  return (
    <div className="page-shell page-shell-wide rise-in">
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
        renderLoadingPanel()
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
          filteredSources={pagedFilteredSources}
          selectedSourceIds={selectedSourceIds}
          sourceQuery={sourceQuery}
          statusFilter={statusFilter}
          sourceSort={sourceSort}
          allVisibleSelected={allVisibleSelected}
          visibleSourceCount={pagedVisibleSourceIds.length}
          sourcesError={sourcesError}
          currentPage={sourcesPage}
          totalPages={sourcesTotalPages}
          totalFilteredCount={filteredSources.length}
          onSetSourceQuery={setSourceQuery}
          onSetStatusFilter={setStatusFilter}
          onSetSourceSort={setSourceSort}
          onToggleSelectAllVisible={toggleSelectAllVisible}
          onToggleSourceSelection={toggleSourceSelection}
          onPreviousPage={() => setSourcesPage((prev) => Math.max(1, prev - 1))}
          onNextPage={() => setSourcesPage((prev) => Math.min(sourcesTotalPages, prev + 1))}
          onScrapeNow={(sourceId) => {
            void handleTrigger(sourceId);
          }}
          onResetCursor={(sourceId) => {
            void handleResetCursor(sourceId);
          }}
        />
      ) : null}

      {!isLoading && activeTab === 'activity' ? (
        <ActivityTab
          sourceActivityLogs={pagedActivityLogs}
          sources={sources}
          activityError={activityError}
          currentPage={activityPage}
          totalPages={activityTotalPages}
          onPreviousPage={() => setActivityPage((prev) => Math.max(1, prev - 1))}
          onNextPage={() => setActivityPage((prev) => Math.min(activityTotalPages, prev + 1))}
        />
      ) : null}

      {!isLoading && activeTab === 'history' ? (
        <HistoryTab
          runHistory={pagedRunHistory}
          historyError={historyError}
          currentPage={historyPage}
          totalPages={historyTotalPages}
          onPreviousPage={() => setHistoryPage((prev) => Math.max(1, prev - 1))}
          onNextPage={() => setHistoryPage((prev) => Math.min(historyTotalPages, prev + 1))}
        />
      ) : null}

      {!isLoading && activeTab === 'ingest' ? (
        <IngestHealthTab
          netNewSummary={netNewSummary}
          netNewError={netNewError}
          onResetCursor={(sourceId) => {
            void handleResetCursor(sourceId);
          }}
        />
      ) : null}
    </div>
  );
}
