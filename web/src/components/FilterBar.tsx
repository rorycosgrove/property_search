'use client';

import { useMemo, useState } from 'react';
import { useFilterStore } from '@/lib/stores';
import { useUIStore } from '@/lib/stores';
import { COUNTIES } from '@/lib/utils';

export default function FilterBar() {
  const { filters, setFilter, setFilters, resetFilters } = useFilterStore();
  const { setRankingMode } = useUIStore();
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const controlClasses = [
    'bg-[var(--background)] border border-[var(--card-border)] rounded-xl px-3 py-2.5',
    'focus:outline-none focus:ring-2 focus:ring-cyan-700/60 focus:border-cyan-700',
    'hover:border-stone-500 transition-colors',
  ].join(' ');

  const advancedControls = (
    <>
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

      <div className="flex items-center justify-center text-xs text-[var(--muted)] border border-dashed border-[var(--card-border)] rounded-xl px-3 py-2.5 bg-[var(--card-bg)]/80">
        Compare up to 5
      </div>
    </>
  );

  const applyMission = (
    missionFilters: Parameters<typeof setFilters>[0],
    ranking: 'llm_only' | 'hybrid' | 'user_weighted',
  ) => {
    setFilters(missionFilters);
    setRankingMode(ranking);
  };

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

  return (
    <section className="border-b border-[var(--card-border)] ai-glass rise-in">
      <div className="px-4 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--muted)]">Search setup</p>
            <h2 className="text-base lg:text-lg font-semibold">Start broad, then narrow only when needed.</h2>
            <p className="mt-1 max-w-2xl text-xs leading-5 text-[var(--muted)]">
              Keep the first pass simple: county, budget ceiling, and a minimum bedroom count. Open extra filters only when the shortlist is still too wide.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-full border border-[var(--card-border)] px-2.5 py-1 text-[11px] text-[var(--muted)]">
              {activeFilterCount} active
            </span>
            <button
              type="button"
              onClick={resetFilters}
              className="rounded-full border border-[var(--card-border)] px-3 py-1.5 text-xs transition-colors hover:bg-[var(--background)]"
            >
              Reset filters
            </button>
          </div>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <label className="flex flex-col gap-1 text-xs text-[var(--muted)]">
              County
              <select
                value={filters.county || ''}
                onChange={(e) => setFilter('county', e.target.value || undefined)}
                className={controlClasses}
              >
                <option value="">All counties</option>
                {COUNTIES.map((county) => (
                  <option key={county} value={county}>{county}</option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1 text-xs text-[var(--muted)]">
              Max budget
              <input
                type="number"
                placeholder="Any budget"
                value={filters.max_price || ''}
                onChange={(e) => setFilter('max_price', e.target.value ? Number(e.target.value) : undefined)}
                className={controlClasses}
              />
            </label>

            <label className="flex flex-col gap-1 text-xs text-[var(--muted)]">
              Minimum beds
              <select
                value={filters.min_beds || ''}
                onChange={(e) => setFilter('min_beds', e.target.value ? Number(e.target.value) : undefined)}
                className={controlClasses}
              >
                <option value="">Any size</option>
                {[1, 2, 3, 4, 5].map((beds) => (
                  <option key={beds} value={beds}>{beds}+ beds</option>
                ))}
              </select>
            </label>
          </div>

          <button
            type="button"
            onClick={() => setAdvancedOpen((value) => !value)}
            className="rounded-full border border-[var(--card-border)] px-4 py-2 text-xs transition-colors hover:bg-[var(--background)]"
            aria-expanded={advancedOpen}
          >
            {advancedOpen ? 'Hide extra filters' : 'Show extra filters'}
          </button>
        </div>

        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          <button
            type="button"
            onClick={() => applyMission(
              { max_price: 500000, min_beds: 3, sort_by: 'created_at', sort_dir: 'desc' },
              'hybrid',
            )}
            className="rounded-full border border-[var(--card-border)] bg-[var(--card-bg)] px-3 py-1.5 transition-colors hover:border-[var(--accent)]"
          >
            Under EUR500k
          </button>
          <button
            type="button"
            onClick={() => applyMission(
              { min_beds: 3, property_types: 'house', sort_by: 'price', sort_dir: 'asc' },
              'user_weighted',
            )}
            className="rounded-full border border-[var(--card-border)] bg-[var(--card-bg)] px-3 py-1.5 transition-colors hover:border-[var(--accent)]"
          >
            Family homes
          </button>
          <button
            type="button"
            onClick={() => applyMission(
              { keywords: 'ber retrofit grant', sort_by: 'created_at', sort_dir: 'desc' },
              'llm_only',
            )}
            className="rounded-full border border-[var(--card-border)] bg-[var(--card-bg)] px-3 py-1.5 transition-colors hover:border-[var(--accent)]"
          >
            Grant-ready
          </button>
          <span className="rounded-full border border-[var(--card-border)] px-3 py-1.5 text-[var(--muted)]">
            Presets also update ranking mode
          </span>
        </div>
      </div>

      {advancedOpen && (
        <>
          <div className="hidden border-t border-[var(--card-border)] bg-[var(--background)]/28 px-4 py-4 lg:block">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">Extra filters</p>
                <p className="text-sm text-[var(--muted)]">Use these only when your shortlist still needs a second pass.</p>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
              {advancedControls}
            </div>
          </div>

          <div className="lg:hidden fixed inset-0 z-[700]">
            <button
              type="button"
              className="absolute inset-0 bg-slate-950/35"
              onClick={() => setAdvancedOpen(false)}
              aria-label="Close advanced filters"
            />
            <div className="absolute bottom-0 left-0 right-0 rounded-t-2xl border-t border-[var(--card-border)] bg-[var(--card-bg)] p-4 shadow-2xl sheet-in">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-base font-semibold">Extra filters</h3>
                  <p className="text-xs text-[var(--muted)]">Refine only when the main search is still too broad.</p>
                </div>
                <button
                  type="button"
                  onClick={() => setAdvancedOpen(false)}
                  className="px-2 py-1 text-xs border border-[var(--card-border)] rounded-md"
                >
                  Close
                </button>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm max-h-[58vh] overflow-y-auto pb-2">
                {advancedControls}
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
