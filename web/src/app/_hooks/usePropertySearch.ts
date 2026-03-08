import { useEffect, useState } from 'react';

import { getProperties, type Property, type PropertyFilters, type PropertyListResponse } from '@/lib/api';

export function usePropertySearch(filters: PropertyFilters) {
  const [data, setData] = useState<PropertyListResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getProperties(filters)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filters]);

  const properties: Property[] = data?.items || [];

  return {
    data,
    loading,
    properties,
  };
}
