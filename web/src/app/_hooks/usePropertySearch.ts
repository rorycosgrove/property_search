import { useEffect, useMemo, useState } from 'react';

import { getProperties, type Property, type PropertyFilters, type PropertyListResponse } from '@/lib/api';

export function usePropertySearch(filters: PropertyFilters) {
  const [data, setData] = useState<PropertyListResponse | null>(null);
  const [mapProperties, setMapProperties] = useState<Property[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshTick, setRefreshTick] = useState(0);

  const stableFilters = useMemo(() => ({ ...filters }), [filters]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const tick = () => setRefreshTick((value) => value + 1);
    const interval = window.setInterval(tick, 15000);

    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        tick();
      }
    };

    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      window.clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadSearchData = async () => {
      const paginatedPromise = getProperties(stableFilters);

      const mapBaseFilters: PropertyFilters = {
        ...stableFilters,
        page: 1,
        size: 100,
      };

      const firstMapPage = await getProperties(mapBaseFilters);
      const allMapItems = [...firstMapPage.items];
      if (firstMapPage.pages > 1) {
        // Keep map history complete by aggregating all result pages.
        for (let page = 2; page <= firstMapPage.pages; page += 1) {
          const next = await getProperties({ ...mapBaseFilters, page });
          allMapItems.push(...next.items);
        }
      }

      const dedupedMapItems = Array.from(new Map(allMapItems.map((item) => [item.id, item])).values());
      const paginated = await paginatedPromise;

      return {
        paginated,
        mapItems: dedupedMapItems,
      };
    };

    setLoading(true);
    loadSearchData()
      .then(({ paginated, mapItems }) => {
        if (!cancelled) {
          setData(paginated);
          setMapProperties(mapItems);
        }
      })
      .catch(console.error)
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [stableFilters, refreshTick]);

  const properties: Property[] = data?.items || [];

  return {
    data,
    loading,
    properties,
    mapProperties,
  };
}
