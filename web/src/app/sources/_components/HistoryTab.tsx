import type { OrganicSearchHistoryItem } from '@/lib/api';
import { formatDate } from '@/lib/utils';

type Props = {
  runHistory: OrganicSearchHistoryItem[];
  historyError: string | null;
};

export function HistoryTab(props: Props) {
  return (
    <section className="mb-8 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-4 lg:p-5">
      <h2 className="text-lg font-semibold mb-3">Full Run History</h2>
      {props.historyError ? <p className="text-sm text-[var(--danger)] mb-3">{props.historyError}</p> : null}

      {props.runHistory.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">No full organic-search runs recorded yet.</p>
      ) : (
        <div className="space-y-3">
          {props.runHistory.map((run) => {
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
                <div className="mt-2 text-xs text-[var(--muted)] space-y-1">
                  {run.steps.map((step) => (
                    <p key={`${run.id}-${step.step}-${step.timestamp || 'no-ts'}`}>
                      {step.step}: {step.status}
                      {step.timestamp ? ` at ${new Date(step.timestamp).toLocaleString()}` : ''}
                    </p>
                  ))}
                </div>
                {discovery || sourcesSummary ? (
                  <div className="mt-2 text-xs text-[var(--muted)] space-y-1">
                    {discovery ? (
                      <p>
                        discovery: created {String(discovery.created ?? 0)}, enabled{' '}
                        {String(discovery.created_enabled ?? 0)}, pending {String(discovery.created_pending_approval ?? 0)}
                      </p>
                    ) : null}
                    {sourcesSummary ? (
                      <p>
                        sources: enabled {String(sourcesSummary.enabled ?? 0)}/{String(sourcesSummary.total ?? 0)},
                        pending {String(sourcesSummary.pending_approval ?? 0)}, disabled by errors{' '}
                        {String(sourcesSummary.disabled_by_errors ?? 0)}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
