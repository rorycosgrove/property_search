'use client';

import type { Property, RankingMode } from '@/lib/api';
import { formatEur } from '@/lib/utils';

interface Props {
  compared: Property[];
  rankingMode: RankingMode;
  onRankingModeChange: (mode: RankingMode) => void;
  onRemove: (propertyId: string) => void;
  onClear: () => void;
  loading: boolean;
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
  loading,
  autoCompareTargetCount,
}: Props) {
  return (
    <section className="border-t border-[var(--card-border)] ai-glass px-4 py-3 rise-in">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div>
          <h2 className="text-sm font-semibold tracking-wide">Decision Studio</h2>
          <p className="text-xs text-[var(--muted)]">
            {compared.length}/5 selected. Atlas AI will rank, explain trade-offs, and suggest next actions.
          </p>
        </div>

        <div className="flex flex-wrap gap-2 items-center">
          <select
            value={rankingMode}
            onChange={(e) => onRankingModeChange(e.target.value as RankingMode)}
            className="bg-[var(--background)] border border-[var(--card-border)] rounded px-2 py-1.5 text-xs"
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
            className="px-3 py-1.5 text-xs rounded border border-[var(--card-border)] hover:bg-[var(--card-border)] disabled:opacity-50"
          >
            Clear
          </button>
        </div>
      </div>

      <p className="text-xs text-[var(--muted)] mb-3">{MODE_HINTS[rankingMode]}</p>
      <p className="text-xs text-[var(--muted)] mb-3">
        {loading
          ? 'Atlas is auto-comparing your current search context...'
          : autoCompareTargetCount >= 2
            ? `Auto-compare active for top ${autoCompareTargetCount} properties in this search.`
            : 'Auto-compare will start when at least 2 properties are available.'}
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-2">
        {compared.map((property) => {
          const imageUrl = property.images?.[0]?.url;
          return (
            <article
              key={property.id}
              className="rounded-md border border-[var(--card-border)] overflow-hidden bg-[var(--background)]"
            >
              <div className="h-20 bg-neutral-900">
                {imageUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={imageUrl} alt={property.title} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-xs text-[var(--muted)]">
                    No image
                  </div>
                )}
              </div>
              <div className="p-2">
                <p className="text-[11px] text-[var(--muted)] mb-1">{property.county || 'Unknown county'}</p>
                <p className="text-xs font-semibold leading-tight line-clamp-2 min-h-[2rem]">{property.title}</p>
                <p className="text-sm text-[var(--accent)] font-bold mt-1">{formatEur(property.price)}</p>
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
            className="rounded-md border border-dashed border-[var(--card-border)] h-[132px] flex items-center justify-center text-xs text-[var(--muted)]"
          >
            Add property
          </div>
        ))}
      </div>
    </section>
  );
}
