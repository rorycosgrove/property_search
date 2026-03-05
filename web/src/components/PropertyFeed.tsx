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
  const { selectProperty } = useMapStore();
  const { openDetail } = useUIStore();
  const page = filters.page || 1;
  const size = filters.size || 20;
  const totalPages = Math.ceil(total / size);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-2 border-b border-[var(--card-border)] text-sm text-[var(--muted)]">
        {loading ? 'Loading...' : `${total.toLocaleString()} properties found`}
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {properties.map((prop) => (
          <div
            key={prop.id}
            className="px-4 py-3 border-b border-[var(--card-border)] hover:bg-[var(--card-bg)] cursor-pointer transition-colors"
            onClick={() => {
              selectProperty(prop.id);
              openDetail(prop);
            }}
          >
            {/* Price + BER */}
            <div className="flex items-center justify-between mb-1">
              <span className="font-semibold text-brand-400">
                {formatEur(prop.price)}
              </span>
              {prop.ber_rating && (
                <span
                  className="text-xs font-bold px-1.5 py-0.5 rounded"
                  style={{ backgroundColor: berColor(prop.ber_rating), color: '#fff' }}
                >
                  {prop.ber_rating}
                </span>
              )}
            </div>

            {/* Title */}
            <h3 className="text-sm font-medium leading-tight mb-0.5">
              {truncate(prop.title, 80)}
            </h3>

            {/* Address */}
            <p className="text-xs text-[var(--muted)] mb-1">
              {prop.county && `${prop.county} · `}
              {truncate(prop.address, 60)}
            </p>

            {/* Meta */}
            <div className="flex gap-3 text-xs text-[var(--muted)]">
              {prop.bedrooms != null && <span>{prop.bedrooms} bed</span>}
              {prop.bathrooms != null && <span>{prop.bathrooms} bath</span>}
              {prop.floor_area_sqm != null && <span>{prop.floor_area_sqm} m²</span>}
              {prop.property_type && <span className="capitalize">{prop.property_type}</span>}
            </div>
          </div>
        ))}

        {!loading && properties.length === 0 && (
          <div className="text-center py-12 text-[var(--muted)]">
            No properties match your filters
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
