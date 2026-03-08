'use client';

import { useMemo, useState } from 'react';
import { useFilterStore } from '@/lib/stores';
import { COUNTIES } from '@/lib/utils';

export default function FilterBar() {
  const { filters, setFilter, resetFilters } = useFilterStore();
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const activeFilterCount = useMemo(() => {
    let count = 0;
    const tracked: Array<keyof typeof filters> = [
      'county',
      'min_price',
      'max_price',
      'min_beds',
      'property_types',
      'keywords',
      'sort_by',
      'sort_dir',
    ];

    tracked.forEach((key) => {
      const value = filters[key];
      if (value !== undefined && value !== null && value !== '') {
        if (key === 'sort_by' && value === 'created_at') return;
        if (key === 'sort_dir' && value === 'desc') return;
        count += 1;
      }
    });

    return count;
  }, [filters]);

  const controlClasses = [
    'bg-[var(--background)] border border-[var(--card-border)] rounded-md px-2.5 py-2',
    'focus:outline-none focus:ring-2 focus:ring-cyan-700/60 focus:border-cyan-700',
    'hover:border-stone-500 transition-colors',
  ].join(' ');

  return (
    <section className="px-3 lg:px-4 py-3 border-b border-[var(--card-border)] bg-gradient-to-r from-stone-950 via-slate-900 to-cyan-950 text-stone-100">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-stone-400">Search Mission</p>
          <h2 className="text-base lg:text-lg font-semibold">Find The Best Value Property</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-stone-400 border border-stone-600/80 rounded-full px-2 py-1">
            {activeFilterCount} active
          </span>
          <button
            onClick={resetFilters}
            className="px-3 py-1.5 text-xs border border-stone-500 rounded-md hover:bg-stone-700/40 transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-600"
          >
            Reset filters
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-sm mb-2">
        <select
          value={filters.county || ''}
          onChange={(e) => setFilter('county', e.target.value || undefined)}
          className={controlClasses}
        >
          <option value="">All Counties</option>
          {COUNTIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>

        <input
          type="number"
          placeholder="Max EUR"
          value={filters.max_price || ''}
          onChange={(e) => setFilter('max_price', e.target.value ? Number(e.target.value) : undefined)}
          className={controlClasses}
        />

        <button
          type="button"
          onClick={() => setAdvancedOpen((v) => !v)}
          className="px-3 py-2 text-xs border border-stone-500 rounded-md hover:bg-stone-700/40 transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-600"
          aria-expanded={advancedOpen}
        >
          {advancedOpen ? 'Hide advanced filters' : 'Show advanced filters'}
        </button>
      </div>

      {advancedOpen && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-2 text-sm">
          <input
            type="number"
            placeholder="Min EUR"
            value={filters.min_price || ''}
            onChange={(e) => setFilter('min_price', e.target.value ? Number(e.target.value) : undefined)}
            className={controlClasses}
          />

          <select
            value={filters.min_beds || ''}
            onChange={(e) => setFilter('min_beds', e.target.value ? Number(e.target.value) : undefined)}
            className={controlClasses}
          >
            <option value="">Any beds</option>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>{n}+ beds</option>
            ))}
          </select>

          <select
            value={filters.property_types || ''}
            onChange={(e) => setFilter('property_types', e.target.value || undefined)}
            className={controlClasses}
          >
            <option value="">All types</option>
            <option value="house">House</option>
            <option value="apartment">Apartment</option>
            <option value="duplex">Duplex</option>
            <option value="bungalow">Bungalow</option>
            <option value="site">Site</option>
          </select>

          <input
            type="text"
            placeholder="Keywords"
            value={filters.keywords || ''}
            onChange={(e) => setFilter('keywords', e.target.value || undefined)}
            className={controlClasses}
          />

          <select
            value={`${filters.sort_by || 'created_at'}_${filters.sort_dir || 'desc'}`}
            onChange={(e) => {
              const [by, dir] = e.target.value.split('_');
              setFilter('sort_by', by);
              setFilter('sort_dir', dir);
            }}
            className={controlClasses}
          >
            <option value="created_at_desc">Newest</option>
            <option value="created_at_asc">Oldest</option>
            <option value="price_asc">Price Low-High</option>
            <option value="price_desc">Price High-Low</option>
          </select>

          <div className="flex items-center justify-center text-xs text-stone-400 border border-dashed border-stone-600 rounded-md px-2 py-2 bg-stone-900/30">
            Compare up to 5
          </div>
        </div>
      )}
    </section>
  );
}
