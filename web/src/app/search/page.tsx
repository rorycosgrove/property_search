'use client';

import { Suspense } from 'react';
import FilterBar from '@/components/FilterBar';
import PropertyFeed from '@/components/PropertyFeed';
import PropertyDetail from '@/components/PropertyDetail';
import { useFilterStore, useUIStore } from '@/lib/stores';
import { usePropertySearch } from '@/app/_hooks/usePropertySearch';

function SearchPageContent() {
  const { filters } = useFilterStore();
  const { detailPanelProperty, closeDetail } = useUIStore();
  const { data, loading, properties } = usePropertySearch(filters);

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] flex-col lg:flex-row">
      {/* Filter sidebar / top bar */}
      <aside className="flex-shrink-0 border-b border-[var(--card-border)] bg-[var(--card-bg)] lg:w-80 lg:border-b-0 lg:border-r lg:overflow-y-auto">
        <div className="p-4">
          <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)]">Filter</p>
          <h1 className="mt-1 text-xl">Property search</h1>
        </div>
        <FilterBar />
      </aside>

      {/* Results feed */}
      <main className="flex-1 overflow-y-auto">
        <PropertyFeed
          properties={properties}
          total={data?.total ?? 0}
          loading={loading}
        />
      </main>

      {/* Property detail drawer */}
      {detailPanelProperty ? (
        <aside className="fixed inset-0 z-40 flex lg:static lg:w-[22rem] lg:flex-shrink-0 lg:border-l lg:border-[var(--card-border)]">
          {/* Mobile backdrop */}
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm lg:hidden"
            onClick={closeDetail}
            aria-hidden="true"
          />
          <div className="absolute bottom-0 left-0 right-0 max-h-[88dvh] overflow-y-auto rounded-t-[28px] bg-[var(--card-bg)] shadow-[0_-24px_80px_rgba(27,36,48,0.18)] lg:static lg:max-h-none lg:rounded-none lg:shadow-none">
            <PropertyDetail property={detailPanelProperty} onClose={closeDetail} />
          </div>
        </aside>
      ) : null}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense>
      <SearchPageContent />
    </Suspense>
  );
}
