import type { AdapterInfo, Source } from '@/lib/api';

type Props = {
  pendingDiscovered: Source[];
  selectedPendingIds: string[];
  latestScrapeTimestamp: string | null;
  scrapeCompleted: number;
  scrapeTotal: number;
  adapters: AdapterInfo[];
  sourcesError: string | null;
  adaptersError: string | null;
  onTogglePendingSelection: (sourceId: string) => void;
  onApproveDiscovered: (sourceId: string) => void;
};

export function OverviewTab(props: Props) {
  return (
    <>
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-8">
        <section className="xl:col-span-2 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-4 lg:p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold">Pending Feed Approvals</h2>
            <p className="text-xs text-[var(--muted)]">{props.pendingDiscovered.length} waiting</p>
          </div>
          {props.sourcesError ? <p className="text-sm text-[var(--danger)] mb-3">{props.sourcesError}</p> : null}
          {props.pendingDiscovered.length === 0 ? (
            <p className="text-sm text-[var(--muted)]">No discovered feeds waiting for approval.</p>
          ) : (
            <div className="space-y-2">
              {props.pendingDiscovered.slice(0, 8).map((source) => (
                <label
                  key={source.id}
                  className="flex items-start gap-3 rounded-lg border border-[var(--card-border)] bg-[var(--background)]/70 p-3"
                >
                  <input
                    type="checkbox"
                    checked={props.selectedPendingIds.includes(source.id)}
                    onChange={() => props.onTogglePendingSelection(source.id)}
                    className="mt-0.5"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{source.name}</p>
                    <p className="text-xs text-[var(--muted)] truncate">{source.url}</p>
                    <p className="text-xs text-[var(--muted)] mt-1">
                      Added {source.created_at ? new Date(source.created_at).toLocaleString() : 'unknown time'}
                    </p>
                  </div>
                  <button
                    onClick={(event) => {
                      event.preventDefault();
                      props.onApproveDiscovered(source.id);
                    }}
                    className="text-xs px-3 py-1.5 rounded border border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)] hover:bg-[var(--accent-soft-strong)]"
                  >
                    Approve
                  </button>
                </label>
              ))}
            </div>
          )}
        </section>

        <section className="rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-4 lg:p-5">
          <h2 className="text-lg font-semibold mb-3">Status Rail</h2>
          <div className="space-y-2 text-sm">
            <p className="text-[var(--muted)]">Primary actions affect scrape and discovery queues.</p>
            <div className="rounded-md border border-[var(--card-border)] p-3 bg-[var(--background)]/70">
              <p className="text-xs text-[var(--muted)]">Latest Scrape Completion</p>
              <p className="font-medium">
                {props.latestScrapeTimestamp ? new Date(props.latestScrapeTimestamp).toLocaleString() : 'No event yet'}
              </p>
            </div>
            <div className="rounded-md border border-[var(--card-border)] p-3 bg-[var(--background)]/70">
              <p className="text-xs text-[var(--muted)] mb-1">Current Run Progress</p>
              <p className="font-medium mb-2">
                {props.scrapeCompleted}/{props.scrapeTotal || 0}
              </p>
              <div className="h-1.5 w-full rounded-full bg-[var(--card-border)] overflow-hidden">
                <div
                  className="h-full rounded-full bg-[var(--accent)] transition-all duration-500"
                  style={{
                    width: `${
                      props.scrapeTotal > 0
                        ? Math.min(100, (props.scrapeCompleted / props.scrapeTotal) * 100)
                        : 0
                    }%`,
                  }}
                />
              </div>
            </div>
          </div>
        </section>
      </div>

      {props.adapters.length > 0 ? (
        <section className="rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-4 lg:p-5">
          <h2 className="text-lg font-semibold mb-3">Adapters Snapshot</h2>
          {props.adaptersError ? <p className="text-sm text-[var(--danger)] mb-2">{props.adaptersError}</p> : null}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {props.adapters.map((adapter) => (
              <div key={adapter.name} className="bg-[var(--background)] border border-[var(--card-border)] rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-medium">{adapter.name}</h3>
                  <span className="text-xs text-[var(--muted)] bg-[var(--card-bg)] px-1.5 py-0.5 rounded">
                    {adapter.adapter_type}
                  </span>
                </div>
                <p className="text-sm text-[var(--muted)]">{adapter.description}</p>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </>
  );
}
