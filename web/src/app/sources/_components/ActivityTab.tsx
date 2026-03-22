import type { BackendLogEntry, Source } from '@/lib/api';

type Props = {
  sourceActivityLogs: BackendLogEntry[];
  sources: Source[];
  activityError: string | null;
  currentPage: number;
  totalPages: number;
  onPreviousPage: () => void;
  onNextPage: () => void;
};

export function ActivityTab(props: Props) {
  return (
    <section className="mb-8 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-4 lg:p-5">
      <h2 className="text-lg font-semibold mb-3">Recent Source Activity</h2>
      {props.activityError ? <p className="text-sm text-[var(--danger)] mb-3">{props.activityError}</p> : null}

      {props.sourceActivityLogs.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">No source activity logs recorded yet.</p>
      ) : (
        <div className="overflow-auto rounded-lg border border-[var(--card-border)]">
          <table className="w-full text-sm min-w-[900px]">
            <thead className="bg-[var(--background)] text-[var(--muted)]">
              <tr>
                <th className="text-left py-2 px-3">Timestamp</th>
                <th className="text-left py-2 px-3">Level</th>
                <th className="text-left py-2 px-3">Event</th>
                <th className="text-left py-2 px-3">Message</th>
                <th className="text-left py-2 px-3">Source</th>
              </tr>
            </thead>
            <tbody>
              {props.sourceActivityLogs.map((entry) => {
                const relatedSource =
                  entry.source_id ? props.sources.find((source) => source.id === entry.source_id) : null;
                return (
                  <tr key={entry.id} className="border-t border-[var(--card-border)] hover:bg-[var(--background)]/50">
                    <td className="py-2 px-3">{entry.timestamp ? new Date(entry.timestamp).toLocaleString() : '-'}</td>
                    <td className="py-2 px-3">{entry.level}</td>
                    <td className="py-2 px-3 font-mono text-xs">{entry.event_type}</td>
                    <td className="py-2 px-3">{entry.message}</td>
                    <td className="py-2 px-3">{relatedSource?.name || '-'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

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
