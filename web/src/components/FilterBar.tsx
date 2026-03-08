'use client';

import { useMemo, useState } from 'react';
import { useFilterStore } from '@/lib/stores';
import { useUIStore } from '@/lib/stores';
import { COUNTIES } from '@/lib/utils';

export default function FilterBar() {
  const { filters, setFilter, setFilters, resetFilters } = useFilterStore();
  const { setRankingMode } = useUIStore();
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [presetsOpen, setPresetsOpen] = useState(false);

  const controlClasses = [
    'bg-[var(--background)] border border-[var(--card-border)] rounded-md px-2.5 py-2',
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

      <div className="flex items-center justify-center text-xs text-[var(--muted)] border border-dashed border-[var(--card-border)] rounded-md px-2 py-2 bg-[var(--card-bg)]/80">
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
    <section className="px-3 lg:px-4 py-3 border-b border-[var(--card-border)] ai-glass rise-in">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--muted)]">Search Mission</p>
          <h2 className="text-base lg:text-lg font-semibold">Map-first property decisions</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-[var(--muted)] border border-[var(--card-border)] rounded-full px-2 py-1">
            {activeFilterCount} active
          </span>
          <button
            type="button"
            onClick={() => setPresetsOpen((v) => !v)}
            className="px-3 py-1.5 text-xs border border-[var(--card-border)] rounded-md hover:bg-[var(--background)] transition-colors lg:hidden"
          >
            {presetsOpen ? 'Hide presets' : 'Show presets'}
          </button>
          <button
            type="button"
            onClick={resetFilters}
            className="px-3 py-1.5 text-xs border border-[var(--card-border)] rounded-md hover:bg-[var(--background)] transition-colors"
          >
            Reset
          </button>
        </div>
      </div>

      <div className={["mb-3 flex flex-wrap gap-2 text-xs", presetsOpen ? 'flex' : 'hidden lg:flex'].join(' ')}>
        <button
          type="button"
          onClick={() => applyMission(
            { max_price: 500000, min_beds: 3, sort_by: 'created_at', sort_dir: 'desc' },
            'hybrid',
          )}
          className="px-3 py-1.5 rounded-full border border-[var(--card-border)] bg-[var(--card-bg)] hover:border-[var(--accent)]"
        >
          Best value under EUR500k
        </button>
        <button
          type="button"
          onClick={() => applyMission(
            { min_beds: 3, property_types: 'house', sort_by: 'price', sort_dir: 'asc' },
            'user_weighted',
          )}
          className="px-3 py-1.5 rounded-full border border-[var(--card-border)] bg-[var(--card-bg)] hover:border-[var(--accent)]"
        >
          Family-ready homes
        </button>
        <button
          type="button"
          onClick={() => applyMission(
            { keywords: 'ber retrofit grant', sort_by: 'created_at', sort_dir: 'desc' },
            'llm_only',
          )}
          className="px-3 py-1.5 rounded-full border border-[var(--card-border)] bg-[var(--card-bg)] hover:border-[var(--accent)]"
        >
          Grant-optimized shortlist
        </button>
        <span className="px-3 py-1.5 rounded-full border border-[var(--card-border)] text-[var(--muted)]">
          Presets update shortlist and ranking mode
        </span>
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
          className="px-3 py-2 text-xs border border-[var(--card-border)] rounded-md hover:bg-[var(--background)] transition-colors"
          aria-expanded={advancedOpen}
        >
          {advancedOpen ? 'Hide advanced filters' : 'More filters'}
        </button>
      </div>

      {advancedOpen && (
        <>
          <div className="hidden lg:grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 text-sm">
            {advancedControls}
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
                <h3 className="text-base font-semibold">Advanced Filters</h3>
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
