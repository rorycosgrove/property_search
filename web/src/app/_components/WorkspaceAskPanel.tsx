'use client';

import type { Citation, RetrievalContext } from '@/lib/api';

interface Props {
  aiQuery: string;
  aiLoading: boolean;
  aiError: string | null;
  aiReply: string | null;
  aiCitations: Citation[];
  aiRetrievalContext: RetrievalContext | null;
  retrievalPreview: RetrievalContext;
  onQueryChange: (value: string) => void;
  onAsk: () => void;
}

export default function WorkspaceAskPanel({
  aiQuery,
  aiLoading,
  aiError,
  aiReply,
  aiCitations,
  aiRetrievalContext,
  retrievalPreview,
  onQueryChange,
  onAsk,
}: Props) {
  return (
    <div id="ask-panel" className="px-4 py-4 border-b border-[var(--card-border)] bg-[var(--card-bg)]/85">
      <div className="mb-3 rounded-lg border border-[var(--card-border)] bg-[var(--background)]/65 px-3 py-2">
        <p className="text-[11px] uppercase tracking-wide text-[var(--muted)]">Context preview</p>
        <p className="text-xs text-[var(--muted)] mt-1">
          Mode: {retrievalPreview.ranking_mode} | Shortlist: {retrievalPreview.shortlist_size} |
          Selected: {retrievalPreview.selected_property_title || 'None'} |
          Winner: {retrievalPreview.winner_property_title || 'None'}
        </p>
      </div>

      <div className="flex flex-col lg:flex-row gap-2">
        <input
          value={aiQuery}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Ask Atlas to compare trade-offs, challenge assumptions, or explain the winner"
          className="flex-1 bg-[var(--background)] border border-[var(--card-border)] rounded-lg px-3 py-2 text-sm focus-ring"
        />
        <button
          type="button"
          onClick={onAsk}
          disabled={!aiQuery.trim() || aiLoading}
          className="px-4 py-2 rounded-lg text-sm font-medium border border-[var(--accent)] bg-cyan-900/10 text-[var(--accent-strong)] hover:bg-cyan-900/15 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {aiLoading ? 'Asking Atlas...' : 'Ask Atlas'}
        </button>
      </div>

      {aiError ? (
        <p className="mt-2 text-xs text-[var(--danger)]">{aiError}</p>
      ) : null}

      {aiReply ? (
        <div className="mt-3 rounded-xl border border-[var(--card-border)] bg-[var(--background)] p-3">
          <p className="text-xs uppercase tracking-wide text-[var(--muted)] mb-1">Atlas recommendation</p>
          <p className="text-sm whitespace-pre-wrap leading-relaxed">{aiReply}</p>

          {aiRetrievalContext ? (
            <p className="text-xs text-[var(--muted)] mt-2">
              Grounded on: {aiRetrievalContext.selected_property_title || 'no focused property'};
              shortlist size {aiRetrievalContext.shortlist_size ?? 0};
              ranking mode {aiRetrievalContext.ranking_mode || 'n/a'}.
            </p>
          ) : null}

          {aiCitations.length > 0 ? (
            <div className="mt-3 pt-2 border-t border-[var(--card-border)]">
              <p className="text-xs uppercase tracking-wide text-[var(--muted)] mb-2">Evidence used</p>
              <div className="space-y-2">
                {aiCitations.map((citation, idx) => {
                  if (citation.type === 'property') {
                    return (
                      <a
                        key={`ai-citation-${idx}`}
                        href={citation.url || '#'}
                        target="_blank"
                        rel="noreferrer"
                        className="block rounded border border-[var(--card-border)] px-2 py-1.5 hover:bg-[var(--card-bg)] text-xs"
                      >
                        {citation.label || 'Property citation'}
                      </a>
                    );
                  }

                  return (
                    <div key={`ai-citation-${idx}`} className="rounded border border-[var(--card-border)] px-2 py-1.5 text-xs">
                      {citation.label || citation.code || 'Grant citation'}
                      {citation.status ? ` • ${citation.status}` : ''}
                      {citation.estimated_benefit ? ` • est ${citation.estimated_benefit}` : ''}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
