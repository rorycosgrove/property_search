import type { PropertyFilters } from '@/lib/api';

export function buildSearchContextKey(filters: PropertyFilters): string {
  return JSON.stringify(filters ?? {});
}