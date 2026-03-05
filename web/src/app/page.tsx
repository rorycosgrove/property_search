'use client';

import { useEffect, useState } from 'react';
import { getProperties, type Property, type PropertyListResponse } from '@/lib/api';
import { useFilterStore, useMapStore, useUIStore } from '@/lib/stores';
import FilterBar from '@/components/FilterBar';
import PropertyFeed from '@/components/PropertyFeed';
import PropertyMap from '@/components/PropertyMap';
import PropertyDetail from '@/components/PropertyDetail';

export default function HomePage() {
  const { filters } = useFilterStore();
  const { selectedPropertyId } = useMapStore();
  const { detailPanelProperty, closeDetail } = useUIStore();
  const [data, setData] = useState<PropertyListResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getProperties(filters)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filters]);

  const properties = data?.items || [];

  return (
    <div className="flex flex-col h-[calc(100vh-52px)]">
      <FilterBar />
      <div className="flex flex-1 overflow-hidden">
        {/* Property feed (left sidebar) */}
        <div className="w-[380px] border-r border-[var(--card-border)] overflow-y-auto">
          <PropertyFeed
            properties={properties}
            total={data?.total || 0}
            loading={loading}
          />
        </div>

        {/* Map (center) */}
        <div className="flex-1 relative">
          <PropertyMap properties={properties} />
        </div>

        {/* Detail panel (right, conditional) */}
        {detailPanelProperty && (
          <div className="w-[420px] border-l border-[var(--card-border)] overflow-y-auto">
            <PropertyDetail
              property={detailPanelProperty}
              onClose={closeDetail}
            />
          </div>
        )}
      </div>
    </div>
  );
}
