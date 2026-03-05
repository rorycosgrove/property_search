'use client';

import { useFilterStore } from '@/lib/stores';
import { COUNTIES } from '@/lib/utils';

export default function FilterBar() {
  const { filters, setFilter, resetFilters } = useFilterStore();

  return (
    <div className="flex items-center gap-3 px-4 py-2 border-b border-[var(--card-border)] bg-[var(--card-bg)] overflow-x-auto text-sm">
      {/* County */}
      <select
        value={filters.county || ''}
        onChange={(e) => setFilter('county', e.target.value || undefined)}
        className="bg-[var(--background)] border border-[var(--card-border)] rounded px-2 py-1.5 text-sm"
      >
        <option value="">All Counties</option>
        {COUNTIES.map((c) => (
          <option key={c} value={c}>{c}</option>
        ))}
      </select>

      {/* Price range */}
      <input
        type="number"
        placeholder="Min price"
        value={filters.min_price || ''}
        onChange={(e) => setFilter('min_price', e.target.value ? Number(e.target.value) : undefined)}
        className="bg-[var(--background)] border border-[var(--card-border)] rounded px-2 py-1.5 w-28 text-sm"
      />
      <span className="text-[var(--muted)]">—</span>
      <input
        type="number"
        placeholder="Max price"
        value={filters.max_price || ''}
        onChange={(e) => setFilter('max_price', e.target.value ? Number(e.target.value) : undefined)}
        className="bg-[var(--background)] border border-[var(--card-border)] rounded px-2 py-1.5 w-28 text-sm"
      />

      {/* Beds */}
      <select
        value={filters.min_beds || ''}
        onChange={(e) => setFilter('min_beds', e.target.value ? Number(e.target.value) : undefined)}
        className="bg-[var(--background)] border border-[var(--card-border)] rounded px-2 py-1.5 text-sm"
      >
        <option value="">Any beds</option>
        {[1, 2, 3, 4, 5].map((n) => (
          <option key={n} value={n}>{n}+ beds</option>
        ))}
      </select>

      {/* Property type */}
      <select
        value={filters.property_types || ''}
        onChange={(e) => setFilter('property_types', e.target.value || undefined)}
        className="bg-[var(--background)] border border-[var(--card-border)] rounded px-2 py-1.5 text-sm"
      >
        <option value="">All types</option>
        <option value="house">House</option>
        <option value="apartment">Apartment</option>
        <option value="duplex">Duplex</option>
        <option value="bungalow">Bungalow</option>
        <option value="site">Site</option>
      </select>

      {/* Keywords */}
      <input
        type="text"
        placeholder="Keywords..."
        value={filters.keywords || ''}
        onChange={(e) => setFilter('keywords', e.target.value || undefined)}
        className="bg-[var(--background)] border border-[var(--card-border)] rounded px-2 py-1.5 flex-1 min-w-[120px] text-sm"
      />

      {/* Sort */}
      <select
        value={`${filters.sort_by || 'first_listed_at'}_${filters.sort_dir || 'desc'}`}
        onChange={(e) => {
          const [by, dir] = e.target.value.split('_');
          setFilter('sort_by', by);
          setFilter('sort_dir', dir);
        }}
        className="bg-[var(--background)] border border-[var(--card-border)] rounded px-2 py-1.5 text-sm"
      >
        <option value="first_listed_at_desc">Newest first</option>
        <option value="first_listed_at_asc">Oldest first</option>
        <option value="price_asc">Price: Low → High</option>
        <option value="price_desc">Price: High → Low</option>
      </select>

      {/* Reset */}
      <button
        onClick={resetFilters}
        className="px-3 py-1.5 text-xs border border-[var(--card-border)] rounded hover:bg-[var(--card-border)] transition-colors"
      >
        Reset
      </button>
    </div>
  );
}
