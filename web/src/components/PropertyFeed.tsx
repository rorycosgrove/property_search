'use client';

import type { Property } from '@/lib/api';
import { useFilterStore, useMapStore, useUIStore } from '@/lib/stores';
import { formatEur, berColor, truncate } from '@/lib/utils';
import { LoadingBlock } from '@/components/LoadingState';

interface Props {
  properties: Property[];
  total: number;
  loading: boolean;
}

export default function PropertyFeed({ properties, total, loading }: Props) {
  const { filters, setFilter } = useFilterStore();
  const { selectProperty, comparedPropertyIds, toggleCompareProperty } = useMapStore();
  const { openDetail } = useUIStore();

  const openExternalListing = (url: string | null | undefined) => {
    const raw = String(url || '').trim();
    if (!raw) return;
    const normalized = /^https?:\/\//i.test(raw) ? raw : `https://${raw.replace(/^\/+/, '')}`;
    window.open(normalized, '_blank', 'noopener,noreferrer');
  };

  const page = filters.page || 1;
  const size = filters.size || 20;
  const totalPages = Math.ceil(total / size);
  const rangeStart = total === 0 ? 0 : (page - 1) * size + 1;
  const rangeEnd = Math.min(page * size, total);

  return (
    <div className="flex flex-col h-full">
      <div className="sticky top-0 z-20 border-b border-[var(--card-border)] bg-[var(--card-bg)]/95 px-4 py-4 backdrop-blur-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">Shortlist</p>
            <p className="mt-1 text-sm text-[var(--muted)]">
              {loading
                ? 'Updating your shortlist...'
                : total === 0
                  ? 'No homes currently match this search.'
                  : `${rangeStart}-${rangeEnd} of ${total.toLocaleString()} homes`}
            </p>
          </div>
          <div className="rounded-full border border-[var(--card-border)] px-3 py-1 text-[11px] text-[var(--muted)]">
            Page {page}{totalPages > 0 ? ` of ${totalPages}` : ''}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto bg-[var(--background)]/18 px-3 py-3">
        {loading && properties.length === 0 ? (
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="rounded-2xl border border-[var(--card-border)] bg-[var(--card-bg)] p-4">
                <div className="flex gap-4">
                  <LoadingBlock className="h-24 w-28 rounded-xl" />
                  <div className="min-w-0 flex-1">
                    <LoadingBlock className="h-4 w-24" />
                    <LoadingBlock className="mt-2 h-3 w-3/4" />
                    <LoadingBlock className="mt-3 h-3 w-full" />
                    <LoadingBlock className="mt-2 h-3 w-2/3" />
                    <div className="mt-4 flex gap-2">
                      <LoadingBlock className="h-7 w-24 rounded-full" />
                      <LoadingBlock className="h-7 w-28 rounded-full" />
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : null}

        {properties.map((prop) => (
          (() => {
            const inCompare = comparedPropertyIds.includes(prop.id);
            const compareFull = comparedPropertyIds.length >= 5 && !inCompare;
            return (
          <div
            key={prop.id}
            className="mb-3 rounded-2xl border border-[var(--card-border)] bg-[var(--card-bg)] p-4 shadow-[0_10px_28px_rgba(27,36,48,0.04)] transition-colors hover:bg-[var(--card-bg)]/90 focus:outline-none focus:ring-2 focus:ring-cyan-700/50"
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
            <div className="flex gap-4">
              <div className="h-24 w-28 shrink-0 overflow-hidden rounded-xl bg-neutral-900">
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
                <div className="mb-2 flex items-start justify-between gap-3">
                  <div>
                    <span className="text-base font-bold text-[var(--accent)]">{formatEur(prop.price)}</span>
                    {prop.net_price != null ? (
                      <p className="mt-0.5 text-[11px] text-emerald-300">Net after grants: {formatEur(prop.net_price)}</p>
                    ) : null}
                    {prop.eligible_grants_total != null && prop.eligible_grants_total > 0 ? (
                      <p className="mt-0.5 text-[11px] text-[var(--muted)]">Eligible grants: {formatEur(prop.eligible_grants_total)}</p>
                    ) : null}
                    <p className="mt-1 text-xs text-[var(--muted)]">
                      {prop.county && `${prop.county} · `}
                      {truncate(prop.address, 54)}
                    </p>
                  </div>
                  {prop.ber_rating ? (
                    <span
                      className="rounded-full px-2 py-1 text-[10px] font-bold"
                      style={{ backgroundColor: berColor(prop.ber_rating), color: '#fff' }}
                    >
                      BER {prop.ber_rating}
                    </span>
                  ) : null}
                </div>

                <h3 className="mb-2 text-sm font-semibold leading-snug">{truncate(prop.title, 76)}</h3>

                <div className="mb-3 flex flex-wrap gap-2 text-xs text-[var(--muted)]">
                  {prop.bedrooms != null && <span className="rounded-full bg-[var(--background)] px-2.5 py-1">{prop.bedrooms} bed</span>}
                  {prop.bathrooms != null && <span className="rounded-full bg-[var(--background)] px-2.5 py-1">{prop.bathrooms} bath</span>}
                  {prop.floor_area_sqm != null && <span className="rounded-full bg-[var(--background)] px-2.5 py-1">{prop.floor_area_sqm} sqm</span>}
                </div>

                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleCompareProperty(prop.id);
                    }}
                    disabled={compareFull}
                    className={[
                      'rounded-full border px-3 py-1.5 text-[11px] transition-colors disabled:cursor-not-allowed disabled:opacity-60',
                      inCompare
                        ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]'
                        : compareFull
                          ? 'border-[var(--card-border)] text-[var(--muted)]'
                          : 'border-[var(--card-border)] hover:bg-[var(--background)]',
                    ].join(' ')}
                  >
                    {inCompare ? 'Added to compare' : compareFull ? 'Compare full (5/5)' : 'Add to compare'}
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      openExternalListing(prop.url);
                    }}
                    disabled={!prop.url}
                    className="rounded-full border border-[var(--card-border)] px-3 py-1.5 text-[11px] text-[var(--muted)] transition-colors hover:bg-[var(--background)] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Open external listing
                  </button>
                </div>
              </div>
            </div>
          </div>
            );
          })()
        ))}

        {!loading && properties.length === 0 && (
          <div className="rounded-2xl border border-dashed border-[var(--card-border)] bg-[var(--card-bg)] px-6 py-12 text-center text-[var(--muted)]">
            No homes match these filters yet.
          </div>
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-[var(--card-border)] bg-[var(--card-bg)] px-4 py-3 text-sm">
          <button
            disabled={page <= 1}
            onClick={() => setFilter('page', page - 1)}
            className="rounded-full border border-[var(--card-border)] px-3 py-1.5 transition-colors hover:bg-[var(--background)] disabled:opacity-30"
          >
            Previous
          </button>
          <span className="text-[var(--muted)]">
            Page {page} of {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setFilter('page', page + 1)}
            className="rounded-full border border-[var(--card-border)] px-3 py-1.5 transition-colors hover:bg-[var(--background)] disabled:opacity-30"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
