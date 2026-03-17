import type { SourcesTab } from './types';

type Props = {
  activeTab: SourcesTab;
  setActiveTab: (tab: SourcesTab) => void;
  lastRefreshedAt: string | null;
  isRefreshing: boolean;
  totalSources: number;
  enabledCount: number;
  pendingApprovalCount: number;
  erroringCount: number;
  scrapeCompleted: number;
  scrapeTotal: number;
  latestScrapeTimestamp: string | null;
  runningFullSearch: boolean;
  discoveringSources: boolean;
  scrapingSelected: boolean;
  approvingSelected: boolean;
  selectedSourceCount: number;
  selectedPendingCount: number;
  sourceCountForTab: number;
  activityCountForTab: number;
  historyCountForTab: number;
  onRunFullSearch: () => void;
  onDiscoverSources: () => void;
  onScrapeSelected: () => void;
  onApproveSelected: () => void;
  onRefresh: () => void;
};

function tabButton(
  activeTab: SourcesTab,
  setActiveTab: (tab: SourcesTab) => void,
  tab: SourcesTab,
  label: string,
  count?: number,
) {
  return (
    <button
      key={tab}
      onClick={() => setActiveTab(tab)}
      className={`text-sm px-3 py-2 rounded-md border transition-colors ${
        activeTab === tab
          ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)]'
          : 'border-[var(--card-border)] bg-[var(--card-bg)] hover:bg-[var(--background)]'
      }`}
    >
      {label}
      {count !== undefined ? <span className="ml-1 text-xs text-[var(--muted)]">({count})</span> : null}
    </button>
  );
}

export function DashboardHeader(props: Props) {
  const progressPct =
    props.scrapeTotal > 0 ? Math.min(100, (props.scrapeCompleted / props.scrapeTotal) * 100) : 0;

  return (
    <div className="mb-4 rounded-2xl border border-[var(--card-border)] bg-[var(--card-bg)]/95 p-5 lg:p-6">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">Sources Dashboard</p>
          <h1 className="text-2xl lg:text-3xl font-semibold mt-1">Ingestion Operations Control Center</h1>
          <p className="text-sm text-[var(--muted)] mt-2 max-w-3xl">
            Run ingestion actions, monitor reliability, approve discovered feeds, and track full-run progress in one operational view.
          </p>
        </div>
        <div className="text-xs text-[var(--muted)] lg:text-right">
          <p>{props.lastRefreshedAt ? `Last refreshed ${new Date(props.lastRefreshedAt).toLocaleString()}` : 'Loading data...'}</p>
          <p>{props.isRefreshing ? 'Refreshing dashboard...' : 'Dashboard ready'}</p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 lg:grid-cols-6 gap-3">
        <div className="rounded-lg border border-[var(--card-border)] bg-[var(--background)]/70 p-3">
          <p className="text-xs text-[var(--muted)]">Total Sources</p>
          <p className="text-xl font-semibold">{props.totalSources}</p>
        </div>
        <div className="rounded-lg border border-[var(--card-border)] bg-[var(--background)]/70 p-3">
          <p className="text-xs text-[var(--muted)]">Enabled</p>
          <p className="text-xl font-semibold">{props.enabledCount}</p>
        </div>
        <div className="rounded-lg border border-[var(--card-border)] bg-[var(--background)]/70 p-3">
          <p className="text-xs text-[var(--muted)]">Pending Approval</p>
          <p className="text-xl font-semibold">{props.pendingApprovalCount}</p>
        </div>
        <div className="rounded-lg border border-[var(--card-border)] bg-[var(--background)]/70 p-3">
          <p className="text-xs text-[var(--muted)]">Erroring Sources</p>
          <p className="text-xl font-semibold">{props.erroringCount}</p>
        </div>
        <div className="rounded-lg border border-[var(--card-border)] bg-[var(--background)]/70 p-3">
          <p className="text-xs text-[var(--muted)]">Run Progress</p>
          <p className="text-xl font-semibold">{props.scrapeCompleted}/{props.scrapeTotal || 0}</p>
        </div>
        <div className="rounded-lg border border-[var(--card-border)] bg-[var(--background)]/70 p-3">
          <p className="text-xs text-[var(--muted)]">Latest Completion</p>
          <p className="text-xs font-medium line-clamp-2">
            {props.latestScrapeTimestamp ? new Date(props.latestScrapeTimestamp).toLocaleString() : 'No completion event yet'}
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          onClick={props.onRunFullSearch}
          disabled={props.runningFullSearch}
          className="text-sm px-4 py-2 rounded-md bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)] disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        >
          {props.runningFullSearch ? 'Running Full Organic Search...' : 'Run Full Organic Search'}
        </button>
        <button
          onClick={props.onDiscoverSources}
          disabled={props.discoveringSources}
          className="text-sm px-4 py-2 rounded-md border border-[var(--card-border)] bg-[var(--card-bg)] hover:bg-[var(--background)] disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        >
          {props.discoveringSources ? 'Discovering Feeds...' : 'Auto-Discover Feeds'}
        </button>
        <button
          onClick={props.onScrapeSelected}
          disabled={props.scrapingSelected || props.selectedSourceCount === 0}
          className="text-sm px-4 py-2 rounded-md border border-[var(--card-border)] bg-[var(--card-bg)] hover:bg-[var(--background)] disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        >
          {props.scrapingSelected ? 'Queueing Selected...' : `Scrape Selected Sources (${props.selectedSourceCount})`}
        </button>
        <button
          onClick={props.onApproveSelected}
          disabled={props.approvingSelected || props.selectedPendingCount === 0}
          className="text-sm px-4 py-2 rounded-md border border-[var(--card-border)] bg-[var(--card-bg)] hover:bg-[var(--background)] disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        >
          {props.approvingSelected ? 'Approving...' : `Approve Selected (${props.selectedPendingCount})`}
        </button>
        <button
          onClick={props.onRefresh}
          className="text-sm px-4 py-2 rounded-md border border-[var(--card-border)] bg-[var(--card-bg)] hover:bg-[var(--background)]"
        >
          Refresh Dashboard
        </button>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {tabButton(props.activeTab, props.setActiveTab, 'overview', 'Overview')}
        {tabButton(props.activeTab, props.setActiveTab, 'sources', 'Sources', props.sourceCountForTab)}
        {tabButton(props.activeTab, props.setActiveTab, 'activity', 'Activity', props.activityCountForTab)}
        {tabButton(props.activeTab, props.setActiveTab, 'history', 'History', props.historyCountForTab)}
      </div>

      <div className="mt-3 h-1.5 w-full rounded-full bg-[var(--card-border)] overflow-hidden">
        <div
          className="h-full rounded-full bg-[var(--accent)] transition-all duration-500"
          style={{ width: `${progressPct}%` }}
        />
      </div>
    </div>
  );
}
