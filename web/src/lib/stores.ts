/**
 * Zustand stores for global application state.
 */

import { create } from 'zustand';
import type { Property, PropertyFilters } from '@/lib/api';

// ── Filter store ────────────────────────────────────────────────────────────

interface FilterState {
  filters: PropertyFilters;
  setFilter: (key: keyof PropertyFilters, value: any) => void;
  setFilters: (filters: Partial<PropertyFilters>) => void;
  resetFilters: () => void;
}

const DEFAULT_FILTERS: PropertyFilters = {
  page: 1,
  size: 20,
  sort_by: 'created_at',
  sort_dir: 'desc',
};

export const useFilterStore = create<FilterState>((set) => ({
  filters: { ...DEFAULT_FILTERS },
  setFilter: (key, value) =>
    set((state) => ({
      filters: { ...state.filters, [key]: value, page: key === 'page' ? value : 1 },
    })),
  setFilters: (newFilters) =>
    set((state) => ({
      filters: { ...state.filters, ...newFilters, page: 1 },
    })),
  resetFilters: () => set({ filters: { ...DEFAULT_FILTERS } }),
}));

// ── Map store ───────────────────────────────────────────────────────────────

interface MapState {
  center: [number, number];
  zoom: number;
  selectedPropertyId: string | null;
  setCenter: (center: [number, number]) => void;
  setZoom: (zoom: number) => void;
  selectProperty: (id: string | null) => void;
}

export const useMapStore = create<MapState>((set) => ({
  center: [53.35, -6.26], // Dublin default
  zoom: 8,
  selectedPropertyId: null,
  setCenter: (center) => set({ center }),
  setZoom: (zoom) => set({ zoom }),
  selectProperty: (id) => set({ selectedPropertyId: id }),
}));

// ── UI store ────────────────────────────────────────────────────────────────

interface UIState {
  sidebarOpen: boolean;
  detailPanelProperty: Property | null;
  toggleSidebar: () => void;
  openDetail: (prop: Property) => void;
  closeDetail: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  detailPanelProperty: null,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  openDetail: (prop) => set({ detailPanelProperty: prop }),
  closeDetail: () => set({ detailPanelProperty: null }),
}));
