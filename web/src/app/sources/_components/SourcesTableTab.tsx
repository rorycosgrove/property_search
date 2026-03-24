import type { Source } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import type { SourceSort, SourceStatusFilter } from './types';

type Props = {
  filteredSources: Source[];
  selectedSourceIds: string[];
  sourceQuery: string;
  statusFilter: SourceStatusFilter;
  sourceSort: SourceSort;
  allVisibleSelected: boolean;
  visibleSourceCount: number;
  sourcesError: string | null;
  currentPage: number;
  totalPages: number;
  totalFilteredCount: number;
  onSetSourceQuery: (value: string) => void;
  onSetStatusFilter: (value: SourceStatusFilter) => void;
  onSetSourceSort: (value: SourceSort) => void;
  onToggleSelectAllVisible: () => void;
  onToggleSourceSelection: (sourceId: string) => void;
  onScrapeNow: (sourceId: string) => void;
  onResetCursor: (sourceId: string) => void;
  onPreviousPage: () => void;
  onNextPage: () => void;
};

export function SourcesTableTab(props: Props) {
  return (
    <section className="mb-8 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-4 lg:p-5">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 mb-4">
        <h2 className="text-lg font-semibold">Configured Sources</h2>
        <div className="flex flex-wrap gap-2">
          <input
            type="text"
            value={props.sourceQuery}
            onChange={(event) => props.onSetSourceQuery(event.target.value)}
            placeholder="Search name, url, adapter, error..."
            className="ui-input min-w-[240px]"
          />
          <select
            value={props.statusFilter}
            onChange={(event) => props.onSetStatusFilter(event.target.value as SourceStatusFilter)}
            className="ui-select"
          >
            <option value="all">All statuses</option>
            <option value="enabled">Enabled</option>
            <option value="disabled">Disabled</option>
            <option value="pending">Pending approval</option>
            <option value="errors">Erroring only</option>
          </select>
          <select
            value={props.sourceSort}
            onChange={(event) => props.onSetSourceSort(event.target.value as SourceSort)}
            className="ui-select"
          >
            <option value="last_polled">Sort: Last polled</option>
            <option value="name">Sort: Name</option>
            <option value="errors">Sort: Errors</option>
            <option value="listings">Sort: Listings</option>
          </select>
        </div>
      </div>

      {props.sourcesError ? <p className="text-sm text-[var(--danger)] mb-3">{props.sourcesError}</p> : null}

      <div className="mb-3 flex items-center gap-3 text-sm">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={props.allVisibleSelected}
            onChange={props.onToggleSelectAllVisible}
            disabled={props.visibleSourceCount === 0}
          />
          Select all visible
        </label>
        <span className="text-[var(--muted)]">
          {props.selectedSourceIds.length} selected / {props.totalFilteredCount} filtered
        </span>
      </div>

      <div className="overflow-auto rounded-lg border border-[var(--card-border)]">
        <table className="w-full text-sm min-w-[900px]">
          <thead className="bg-[var(--background)] text-[var(--muted)]">
            <tr>
              <th className="text-left py-2 px-3">Select</th>
              <th className="text-left py-2 px-3">Source</th>
              <th className="text-left py-2 px-3">Status</th>
              <th className="text-left py-2 px-3">Last Polled</th>
              <th className="text-left py-2 px-3">Listings</th>
              <th className="text-left py-2 px-3">Errors</th>
              <th className="text-left py-2 px-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {props.filteredSources.map((source) => {
              const selected = props.selectedSourceIds.includes(source.id);
              const pending = source.tags?.includes('pending_approval');
              return (
                <tr key={source.id} className="border-t border-[var(--card-border)] hover:bg-[var(--background)]/50">
                  <td className="py-2 px-3">
                    <input type="checkbox" checked={selected} onChange={() => props.onToggleSourceSelection(source.id)} />
                  </td>
                  <td className="py-2 px-3">
                    <p className="font-medium">{source.name}</p>
                    <p className="text-xs text-[var(--muted)] truncate max-w-[360px]">{source.url}</p>
                    <p className="text-xs text-[var(--muted)]">{source.adapter_name}</p>
                  </td>
                  <td className="py-2 px-3">
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      pending
                        ? 'border border-amber-300/40 bg-amber-200/30 text-amber-700'
                        : source.enabled
                          ? 'border border-emerald-300/40 bg-emerald-200/30 text-emerald-700'
                          : 'border border-rose-300/40 bg-rose-200/30 text-rose-700'
                    }`}>
                      {pending ? 'Pending approval' : source.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </td>
                  <td className="py-2 px-3">{formatDate(source.last_polled_at) || 'Never'}</td>
                  <td className="py-2 px-3">{source.total_listings ?? 0}</td>
                  <td className="py-2 px-3">
                    <span className={(source.error_count ?? 0) > 0 ? 'text-[var(--danger)]' : ''}>
                      {source.error_count ?? 0}
                    </span>
                    {source.last_error ? <p className="text-xs text-[var(--danger)] mt-1 line-clamp-2">{source.last_error}</p> : null}
                  </td>
                  <td className="py-2 px-3">
                    <div className="flex flex-col gap-1">
                      <button
                        onClick={() => props.onScrapeNow(source.id)}
                        className="ui-btn ui-btn-primary text-xs"
                      >
                        Scrape Now
                      </button>
                      {source.adapter_name === 'daft' ? (
                        <button
                          onClick={() => props.onResetCursor(source.id)}
                          className="ui-btn ui-btn-secondary text-xs"
                        >
                          Reset Cursor
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {props.filteredSources.length === 0 ? <p className="text-sm text-[var(--muted)] mt-3">No sources match this filter set.</p> : null}

      {props.totalPages > 1 ? (
        <div className="mt-4 flex items-center justify-between gap-3 border-t border-[var(--card-border)] pt-3">
          <button
            type="button"
            onClick={props.onPreviousPage}
            disabled={props.currentPage <= 1}
            className="ui-btn ui-btn-secondary disabled:opacity-50"
          >
            Previous
          </button>
          <p className="text-sm text-[var(--muted)]">
            Page {props.currentPage} of {props.totalPages}
          </p>
          <button
            type="button"
            onClick={props.onNextPage}
            disabled={props.currentPage >= props.totalPages}
            className="ui-btn ui-btn-secondary disabled:opacity-50"
          >
            Next
          </button>
        </div>
      ) : null}
    </section>
  );
}
