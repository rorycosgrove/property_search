'use client';

import type { Property, RankingMode } from '@/lib/api';
import { formatEur } from '@/lib/utils';

interface Props {
  compared: Property[];
  rankingMode: RankingMode;
  onRankingModeChange: (mode: RankingMode) => void;
  onRemove: (propertyId: string) => void;
  onClear: () => void;
  onRunAnalysis: () => void;
  loading: boolean;
  canRunAnalysis: boolean;
  analysisStale: boolean;
  autoCompareTargetCount: number;
}

const MODE_LABELS: Record<RankingMode, string> = {
  llm_only: 'LLM signal first',
  hybrid: 'Balanced evidence',
  user_weighted: 'Your priorities',
};

const MODE_HINTS: Record<RankingMode, string> = {
  llm_only: 'Best when you want AI-led interpretation of hidden trade-offs.',
  hybrid: 'Blends AI insight with BER and structured metrics.',
  user_weighted: 'Use when your personal criteria should dominate.',
};

export default function CompareDock({
  compared,
  rankingMode,
  onRankingModeChange,
  onRemove,
  onClear,
  onRunAnalysis,
  loading,
  canRunAnalysis,
  analysisStale,
  autoCompareTargetCount,
}: Props) {
  return (
    <section className="border-t border-[var(--card-border)] bg-[var(--card-bg)]/88 px-4 py-4 rise-in">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div>
          <h2 className="text-base font-semibold tracking-tight">Comparison shortlist</h2>
          <p className="text-xs text-[var(--muted)]">
            {compared.length}/5 selected for AI ranking.
          </p>
        </div>

        <div className="flex flex-wrap gap-2 items-center">
          <button
            onClick={onRunAnalysis}
            disabled={!canRunAnalysis || loading}
            className="px-3 py-1.5 text-xs rounded border border-[var(--accent)] bg-cyan-900/10 text-[var(--accent-strong)] hover:bg-cyan-900/15 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Running...' : analysisStale ? 'Re-run analysis' : 'Run analysis'}
          </button>
          <select
            value={rankingMode}
            onChange={(e) => onRankingModeChange(e.target.value as RankingMode)}
            className="bg-[var(--background)] border border-[var(--card-border)] rounded px-2 py-1.5 text-xs focus-ring"
          >
            {Object.entries(MODE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
          <button
            onClick={onClear}
            disabled={compared.length === 0}
            className="px-3 py-1.5 text-xs rounded border border-[var(--card-border)] hover:bg-[var(--background)] disabled:opacity-50"
          >
            Clear
          </button>
        </div>
      </div>

      <p className="text-sm text-[var(--muted)] mb-1">{MODE_HINTS[rankingMode]}</p>
      <p className="text-xs text-[var(--muted)] mb-4">
        {loading
          ? 'Atlas is running analysis for your current search context...'
          : analysisStale
            ? 'Search context changed. Re-run analysis to refresh the recommendation.'
            : autoCompareTargetCount >= 2
              ? `Ready to analyze top ${autoCompareTargetCount} homes in this search.`
              : 'Analysis becomes available when at least 2 properties are available.'}
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
        {compared.map((property) => {
          const imageUrl = property.images?.[0]?.url;
          return (
            <article
              key={property.id}
              className="rounded-xl border border-[var(--card-border)] overflow-hidden bg-[var(--background)]"
            >
              <div className="h-24 bg-neutral-900">
                {imageUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={imageUrl} alt={property.title} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-xs text-[var(--muted)]">
                    No image
                  </div>
                )}
              </div>
              <div className="p-3">
                <p className="text-[11px] text-[var(--muted)] mb-1">{property.county || 'Unknown county'}</p>
                <p className="text-sm font-semibold leading-tight line-clamp-2 min-h-[2.4rem]">{property.title}</p>
                <p className="text-base text-[var(--accent)] font-bold mt-1">{formatEur(property.price)}</p>
                <button
                  onClick={() => onRemove(property.id)}
                  className="text-[11px] text-[var(--danger)] mt-2 hover:opacity-80"
                >
                  Remove
                </button>
              </div>
            </article>
          );
        })}

        {Array.from({ length: Math.max(0, 5 - compared.length) }).map((_, idx) => (
          <div
            key={`empty-${idx}`}
            className="rounded-xl border border-dashed border-[var(--card-border)] h-[148px] flex items-center justify-center text-xs text-[var(--muted)]"
          >
            Add property
          </div>
        ))}
      </div>
    </section>
  );
}
