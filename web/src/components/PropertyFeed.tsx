'use client';

import type { Property } from '@/lib/api';
import { useFilterStore, useMapStore, useUIStore } from '@/lib/stores';
import { formatEur, berColor, truncate } from '@/lib/utils';

interface Props {
  properties: Property[];
  total: number;
  loading: boolean;
}

export default function PropertyFeed({ properties, total, loading }: Props) {
  const { filters, setFilter } = useFilterStore();
  const { selectProperty, comparedPropertyIds, toggleCompareProperty } = useMapStore();
  const { openDetail } = useUIStore();
  const page = filters.page || 1;
  const size = filters.size || 20;
  const totalPages = Math.ceil(total / size);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--card-border)] text-sm text-[var(--muted)] bg-[var(--card-bg)]/88">
        {loading ? 'Updating your shortlist...' : `${total.toLocaleString()} homes match your search`}
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {properties.map((prop) => (
          (() => {
            const inCompare = comparedPropertyIds.includes(prop.id);
            const compareFull = comparedPropertyIds.length >= 5 && !inCompare;
            return (
          <div
            key={prop.id}
            className="p-3 border-b border-[var(--card-border)] hover:bg-[var(--card-bg)]/85 cursor-pointer transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-700/50"
            onClick={() => {
              selectProperty(prop.id);
              openDetail(prop);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                selectProperty(prop.id);
                openDetail(prop);
              }
            }}
            role="button"
            tabIndex={0}
          >
            <div className="flex gap-3">
              <div className="w-24 h-20 rounded-md overflow-hidden bg-neutral-900 shrink-0">
                {prop.images?.[0]?.url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={prop.images[0].url}
                    alt={prop.title}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-[10px] text-[var(--muted)]">
                    No image
                  </div>
                )}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-[var(--accent)] text-sm">{formatEur(prop.price)}</span>
                  {prop.ber_rating && (
                    <span
                      className="text-[10px] font-bold px-1.5 py-0.5 rounded"
                      style={{ backgroundColor: berColor(prop.ber_rating), color: '#fff' }}
                    >
                      {prop.ber_rating}
                    </span>
                  )}
                </div>

                <h3 className="text-sm font-semibold leading-tight mb-0.5">{truncate(prop.title, 72)}</h3>
                <p className="text-xs text-[var(--muted)] mb-1">
                  {prop.county && `${prop.county} · `}
                  {truncate(prop.address, 50)}
                </p>

                <div className="flex gap-2 text-[11px] text-[var(--muted)] mb-1">
                  {prop.bedrooms != null && <span>{prop.bedrooms} bed</span>}
                  {prop.bathrooms != null && <span>{prop.bathrooms} bath</span>}
                  {prop.floor_area_sqm != null && <span>{prop.floor_area_sqm} sqm</span>}
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleCompareProperty(prop.id);
                  }}
                  disabled={compareFull}
                  className={[
                    'text-[11px] px-2 py-1 rounded border transition-colors disabled:cursor-not-allowed disabled:opacity-60',
                    inCompare
                      ? 'border-[var(--accent)] text-[var(--accent)] bg-cyan-900/10'
                      : compareFull
                        ? 'border-[var(--card-border)] text-[var(--muted)]'
                      : 'border-[var(--card-border)] hover:bg-[var(--background)]',
                  ].join(' ')}
                >
                  {inCompare ? 'In compare' : compareFull ? 'Compare full (5/5)' : 'Add to compare'}
                </button>
              </div>
            </div>
          </div>
            );
          })()
        ))}

        {!loading && properties.length === 0 && (
          <div className="text-center py-12 text-[var(--muted)]">
            No homes match these filters
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-2 border-t border-[var(--card-border)] text-sm">
          <button
            disabled={page <= 1}
            onClick={() => setFilter('page', page - 1)}
            className="px-2 py-1 rounded border border-[var(--card-border)] disabled:opacity-30 hover:bg-[var(--card-border)] transition-colors"
          >
            ← Prev
          </button>
          <span className="text-[var(--muted)]">
            Page {page} of {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setFilter('page', page + 1)}
            className="px-2 py-1 rounded border border-[var(--card-border)] disabled:opacity-30 hover:bg-[var(--card-border)] transition-colors"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
