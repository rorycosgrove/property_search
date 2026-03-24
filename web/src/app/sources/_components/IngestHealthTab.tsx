'use client';

import type { SourceNetNewSummaryItem } from '@/lib/api';

type Props = {
  netNewSummary: SourceNetNewSummaryItem[];
  netNewError: string | null;
  onResetCursor: (sourceId: string) => void;
};

function ZeroBadge({ label }: { label: string }) {
  return (
    <span className="inline-block rounded px-1.5 py-0.5 text-xs font-medium bg-[var(--danger)] text-white">
      {label}
    </span>
  );
}

function WarnBadge({ label }: { label: string }) {
  return (
    <span className="inline-block rounded px-1.5 py-0.5 text-xs font-medium bg-orange-500 text-white">
      {label}
    </span>
  );
}

export function IngestHealthTab(props: Props) {
  if (props.netNewError) {
    return (
      <section className="mb-8 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-4 lg:p-5">
        <h2 className="text-lg font-semibold mb-3">Ingest Health</h2>
        <p className="text-sm text-[var(--danger)]">{props.netNewError}</p>
      </section>
    );
  }

  if (props.netNewSummary.length === 0) {
    return (
      <section className="mb-8 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-4 lg:p-5">
        <h2 className="text-lg font-semibold mb-3">Ingest Health</h2>
        <p className="text-sm text-[var(--muted)]">No ingestion data available yet.</p>
      </section>
    );
  }

  return (
    <section className="mb-8 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-4 lg:p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Ingest Health</h2>
        <p className="text-xs text-[var(--muted)]">
          Showing last {props.netNewSummary[0]?.runs_sampled ?? '?'} runs per source · stalled sources shown first
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--card-border)] text-left text-[var(--muted)]">
              <th className="py-2 px-3 font-medium">Source</th>
              <th className="py-2 px-3 font-medium">Status</th>
              <th className="py-2 px-3 font-medium text-right">New</th>
              <th className="py-2 px-3 font-medium text-right">Updated</th>
              <th className="py-2 px-3 font-medium text-right">Fetched</th>
              <th className="py-2 px-3 font-medium text-right">Zero-new streak</th>
              <th className="py-2 px-3 font-medium text-right">Zero-fetch streak</th>
              <th className="py-2 px-3 font-medium">Last fetch reason</th>
              <th className="py-2 px-3 font-medium">Last run</th>
              <th className="py-2 px-3 font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--card-border)]">
            {props.netNewSummary.map((item) => (
              <tr
                key={item.source_id}
                className={item.zero_ingestion ? 'bg-[var(--danger)]/5' : ''}
              >
                <td className="py-2 px-3 font-medium">{item.source_name ?? item.source_id}</td>
                <td className="py-2 px-3">
                  {item.zero_ingestion ? (
                    <ZeroBadge label="Stalled" />
                  ) : item.consecutive_zero_fetch > 0 ? (
                    <WarnBadge label="Degraded" />
                  ) : (
                    <span className="text-xs text-[var(--muted)]">OK</span>
                  )}
                </td>
                <td className="py-2 px-3 text-right tabular-nums">{item.total_new}</td>
                <td className="py-2 px-3 text-right tabular-nums">{item.total_updated}</td>
                <td className="py-2 px-3 text-right tabular-nums">{item.total_fetched}</td>
                <td className="py-2 px-3 text-right tabular-nums">
                  {item.consecutive_zero_new > 0 ? (
                    <span className="text-[var(--danger)] font-medium">{item.consecutive_zero_new}</span>
                  ) : (
                    <span className="text-[var(--muted)]">0</span>
                  )}
                </td>
                <td className="py-2 px-3 text-right tabular-nums">
                  {item.consecutive_zero_fetch > 0 ? (
                    <span className="text-orange-500 font-medium">{item.consecutive_zero_fetch}</span>
                  ) : (
                    <span className="text-[var(--muted)]">0</span>
                  )}
                </td>
                <td className="py-2 px-3 text-xs text-[var(--muted)]">
                  {item.last_zero_fetch_reason ?? '—'}
                </td>
                <td className="py-2 px-3 text-xs text-[var(--muted)] whitespace-nowrap">
                  {item.last_run_at ? item.last_run_at.replace('T', ' ').slice(0, 16) : '—'}
                </td>
                <td className="py-2 px-3">
                  {item.zero_ingestion || item.consecutive_zero_fetch > 0 ? (
                    <button
                      onClick={() => props.onResetCursor(item.source_id)}
                      className="ui-btn ui-btn-secondary text-xs"
                    >
                      Reset Cursor
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
