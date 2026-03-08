'use client';

import type { Property, RankingMode } from '@/lib/api';
import { formatEur } from '@/lib/utils';

interface Props {
  compared: Property[];
  rankingMode: RankingMode;
  onRankingModeChange: (mode: RankingMode) => void;
  onRemove: (propertyId: string) => void;
  onClear: () => void;
  onAnalyze: () => void;
  loading: boolean;
}

const MODE_LABELS: Record<RankingMode, string> = {
  llm_only: 'LLM only',
  hybrid: 'Hybrid',
  user_weighted: 'User weighted',
};

export default function CompareDock({
  compared,
  rankingMode,
  onRankingModeChange,
  onRemove,
  onClear,
  onAnalyze,
  loading,
}: Props) {
  return (
    <section className="border-t border-[var(--card-border)] bg-[var(--card-bg)]/90 backdrop-blur px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div>
          <h2 className="text-sm font-semibold tracking-wide">Comparison Dock</h2>
          <p className="text-xs text-[var(--muted)]">
            {compared.length}/5 selected for value-for-money analysis
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
            onClick={onAnalyze}
            disabled={loading || compared.length < 2}
            className="px-3 py-1.5 text-xs font-semibold rounded bg-brand-600 hover:bg-brand-700 disabled:opacity-50"
          >
            {loading ? 'Analyzing...' : 'Analyze best value'}
          </button>
          <button
            onClick={onClear}
            disabled={compared.length === 0}
            className="px-3 py-1.5 text-xs rounded border border-[var(--card-border)] hover:bg-[var(--card-border)] disabled:opacity-50"
          >
            Clear
          </button>
        </div>
      </div>

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
                <p className="text-sm text-brand-300 font-bold mt-1">{formatEur(property.price)}</p>
                <button
                  onClick={() => onRemove(property.id)}
                  className="text-[11px] text-red-300 mt-2 hover:text-red-200"
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
