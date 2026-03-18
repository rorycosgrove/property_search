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
  net_price: 'Cheapest after grants',
};

const MODE_HINTS: Record<RankingMode, string> = {
  llm_only: 'Best when you want AI-led interpretation of hidden trade-offs.',
  hybrid: 'Blends AI insight with BER and structured metrics.',
  user_weighted: 'Use when your personal criteria should dominate.',
  net_price: 'Prioritizes homes with the lowest net price after eligible grants.',
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
  const slotsRemaining = Math.max(0, 5 - compared.length);
  const canRun = canRunAnalysis && !loading;

  return (
    <section className="rise-in border-t border-[var(--card-border)] bg-[var(--card-bg)]/88 px-4 py-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">Compare workspace</p>
          <h2 className="text-base font-semibold tracking-tight">Comparison shortlist</h2>
          <p className="mt-1 text-xs text-[var(--muted)]">
            {compared.length}/5 selected, {slotsRemaining} slot{slotsRemaining === 1 ? '' : 's'} open.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="text-[11px] text-[var(--muted)]">
            <span className="mr-2">Ranking mode</span>
            <select
              value={rankingMode}
              onChange={(e) => onRankingModeChange(e.target.value as RankingMode)}
              className="rounded-full border border-[var(--card-border)] bg-[var(--background)] px-3 py-1.5 text-xs focus-ring"
            >
              {Object.entries(MODE_LABELS).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <button
            onClick={onRunAnalysis}
            disabled={!canRun}
            className="rounded-full border border-[var(--accent)] bg-[var(--accent-soft)] px-3 py-1.5 text-xs text-[var(--accent-strong)] hover:bg-[var(--accent-soft-strong)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? 'Running...' : analysisStale ? 'Re-run analysis' : 'Run analysis'}
          </button>
          <button
            onClick={onClear}
            disabled={compared.length === 0}
            className="rounded-full border border-[var(--card-border)] px-3 py-1.5 text-xs hover:bg-[var(--background)] disabled:opacity-50"
          >
            Clear shortlist
          </button>
        </div>
      </div>

      <p className="mb-1 text-sm text-[var(--muted)]">{MODE_HINTS[rankingMode]}</p>
      <p className="mb-4 text-xs text-[var(--muted)]">
        {loading
          ? 'Atlas is running analysis for your current search context...'
          : analysisStale
            ? 'Search context changed. Re-run analysis to refresh the recommendation.'
            : autoCompareTargetCount >= 2
              ? `Ready to analyze top ${autoCompareTargetCount} homes in this search.`
              : 'Analysis becomes available when at least 2 properties are available.'}
      </p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
        {compared.map((property) => {
          const imageUrl = property.images?.[0]?.url;
          return (
            <article
              key={property.id}
              className="overflow-hidden rounded-2xl border border-[var(--card-border)] bg-[var(--background)] shadow-[0_8px_22px_rgba(27,36,48,0.05)]"
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
                {property.net_price != null ? (
                  <p className="mt-0.5 text-xs text-emerald-300">
                    Net after grants: {formatEur(property.net_price)}
                  </p>
                ) : null}
                {property.eligible_grants_total != null && property.eligible_grants_total > 0 ? (
                  <p className="mt-0.5 text-[11px] text-[var(--muted)]">
                    Eligible grants: {formatEur(property.eligible_grants_total)}
                  </p>
                ) : null}
                <button
                  onClick={() => onRemove(property.id)}
                  className="mt-2 rounded-full border border-[var(--card-border)] px-2.5 py-1 text-[11px] text-[var(--danger)] hover:bg-[var(--card-bg)]"
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
            className="flex h-[148px] items-center justify-center rounded-2xl border border-dashed border-[var(--card-border)] text-xs text-[var(--muted)]"
          >
            Select home from shortlist
          </div>
        ))}
      </div>
    </section>
  );
}
