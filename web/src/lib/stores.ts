/**
 * Zustand stores for global application state.
 */

import { create } from 'zustand';
import type { Property, PropertyFilters, RankingMode } from '@/lib/api';

// ── Filter store ────────────────────────────────────────────────────────────

interface FilterState {
  filters: PropertyFilters;
  setFilter: <K extends keyof PropertyFilters>(key: K, value: PropertyFilters[K]) => void;
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
    set((state) => {
      const nextFilters: PropertyFilters = { ...state.filters, [key]: value };
      if (key !== 'page') {
        nextFilters.page = 1;
      }
      return { filters: nextFilters };
    }),
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
  comparedPropertyIds: string[];
  setCenter: (center: [number, number]) => void;
  setZoom: (zoom: number) => void;
  selectProperty: (id: string | null) => void;
  setComparedProperties: (ids: string[]) => void;
  toggleCompareProperty: (id: string) => void;
  removeComparedProperty: (id: string) => void;
  clearComparedProperties: () => void;
}

export const useMapStore = create<MapState>((set) => ({
  center: [53.35, -6.26], // Dublin default
  zoom: 8,
  selectedPropertyId: null,
  comparedPropertyIds: [],
  setCenter: (center) => set({ center }),
  setZoom: (zoom) => set({ zoom }),
  selectProperty: (id) => set({ selectedPropertyId: id }),
  setComparedProperties: (ids) => {
    const normalized = Array.from(
      new Set(
        (ids || [])
          .filter((id): id is string => typeof id === 'string' && id.length > 0)
          .slice(0, 5),
      ),
    );
    set({ comparedPropertyIds: normalized });
  },
  toggleCompareProperty: (id) =>
    set((state) => {
      const exists = state.comparedPropertyIds.includes(id);
      if (exists) {
        return {
          comparedPropertyIds: state.comparedPropertyIds.filter((x) => x !== id),
        };
      }

      if (state.comparedPropertyIds.length >= 5) {
        return state;
      }

      return {
        comparedPropertyIds: [...state.comparedPropertyIds, id],
      };
    }),
  removeComparedProperty: (id) =>
    set((state) => ({
      comparedPropertyIds: state.comparedPropertyIds.filter((x) => x !== id),
    })),
  clearComparedProperties: () => set({ comparedPropertyIds: [] }),
}));

// ── UI store ────────────────────────────────────────────────────────────────

interface UIState {
  sidebarOpen: boolean;
  feedPanelOpen: boolean;
  analysisPanelOpen: boolean;
  detailPanelProperty: Property | null;
  rankingMode: RankingMode;
  toggleSidebar: () => void;
  toggleFeedPanel: () => void;
  toggleAnalysisPanel: () => void;
  setFeedPanelOpen: (open: boolean) => void;
  setAnalysisPanelOpen: (open: boolean) => void;
  openDetail: (prop: Property) => void;
  closeDetail: () => void;
  setRankingMode: (mode: RankingMode) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  feedPanelOpen: true,
  analysisPanelOpen: true,
  detailPanelProperty: null,
  rankingMode: 'hybrid',
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  toggleFeedPanel: () => set((state) => ({ feedPanelOpen: !state.feedPanelOpen })),
  toggleAnalysisPanel: () => set((state) => ({ analysisPanelOpen: !state.analysisPanelOpen })),
  setFeedPanelOpen: (open) => set({ feedPanelOpen: open }),
  setAnalysisPanelOpen: (open) => set({ analysisPanelOpen: open }),
  openDetail: (prop) => set({ detailPanelProperty: prop }),
  closeDetail: () => set({ detailPanelProperty: null }),
  setRankingMode: (mode) => set({ rankingMode: mode }),
}));
