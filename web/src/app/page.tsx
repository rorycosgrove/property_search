'use client';

import { useEffect, useState } from 'react';
import {
  comparePropertySet,
  type CompareSetResponse,
  getProperties,
  type Property,
  type PropertyListResponse,
} from '@/lib/api';
import { useFilterStore, useMapStore, useUIStore } from '@/lib/stores';
import FilterBar from '@/components/FilterBar';
import PropertyFeed from '@/components/PropertyFeed';
import PropertyMap from '@/components/PropertyMap';
import PropertyDetail from '@/components/PropertyDetail';
import CompareDock from '@/components/CompareDock';
import LLMAnalysisPanel from '@/components/LLMAnalysisPanel';

export default function HomePage() {
  const { filters } = useFilterStore();
  const {
    comparedPropertyIds,
    removeComparedProperty,
    clearComparedProperties,
  } = useMapStore();
  const {
    detailPanelProperty,
    closeDetail,
    rankingMode,
    setRankingMode,
    feedPanelOpen,
    analysisPanelOpen,
    toggleFeedPanel,
    toggleAnalysisPanel,
  } = useUIStore();
  const [data, setData] = useState<PropertyListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareResult, setCompareResult] = useState<CompareSetResponse | null>(null);

  useEffect(() => {
    setLoading(true);
    getProperties(filters)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filters]);

  const properties = data?.items || [];
  const propertyMap = new Map(properties.map((p) => [p.id, p]));
  const comparedProperties = comparedPropertyIds
    .map((id) => propertyMap.get(id))
    .filter((p): p is Property => Boolean(p));

  const runCompare = async () => {
    if (comparedPropertyIds.length < 2) {
      return;
    }
    setCompareLoading(true);
    try {
      const result = await comparePropertySet(comparedPropertyIds, rankingMode);
      setCompareResult(result);
    } catch (err) {
      console.error(err);
    } finally {
      setCompareLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100dvh-64px)] lg:h-[calc(100dvh-62px)]">
      <FilterBar />

      <div className="px-3 py-2 border-b border-[var(--card-border)] bg-[var(--card-bg)]/70 flex flex-wrap items-center gap-2">
        <button
          onClick={toggleFeedPanel}
          className={[
            'px-2.5 py-1.5 rounded-md text-xs border focus:outline-none focus:ring-2 focus:ring-cyan-700',
            feedPanelOpen
              ? 'border-cyan-700 bg-cyan-950/20 text-cyan-900'
              : 'border-[var(--card-border)] hover:bg-[var(--background)]',
          ].join(' ')}
        >
          {feedPanelOpen ? 'Hide list' : 'Show list'}
        </button>
        <button
          onClick={toggleAnalysisPanel}
          className={[
            'px-2.5 py-1.5 rounded-md text-xs border focus:outline-none focus:ring-2 focus:ring-cyan-700',
            analysisPanelOpen
              ? 'border-cyan-700 bg-cyan-950/20 text-cyan-900'
              : 'border-[var(--card-border)] hover:bg-[var(--background)]',
          ].join(' ')}
        >
          {analysisPanelOpen ? 'Hide analysis' : 'Show analysis'}
        </button>
        {detailPanelProperty && (
          <button
            onClick={closeDetail}
            className="px-2.5 py-1.5 rounded-md text-xs border border-[var(--card-border)] hover:bg-[var(--background)] focus:outline-none focus:ring-2 focus:ring-cyan-700"
          >
            Close detail
          </button>
        )}
        <div className="ml-auto text-[11px] text-[var(--muted)] px-2 py-1 border border-[var(--card-border)] rounded-full">
          Compare selected: {comparedPropertyIds.length}/5
        </div>
      </div>

      <div className="flex flex-1 min-h-0 overflow-hidden flex-col lg:flex-row">
        {feedPanelOpen && (
          <div className="w-full lg:w-[340px] lg:shrink-0 border-b lg:border-b-0 lg:border-r border-[var(--card-border)] overflow-y-auto bg-[var(--card-bg)]/50">
            <PropertyFeed
              properties={properties}
              total={data?.total || 0}
              loading={loading}
            />
          </div>
        )}

        <div className="flex-1 flex flex-col min-h-0">
          <div className="flex-1 relative min-h-0">
            <PropertyMap properties={properties} />
          </div>
          <CompareDock
            compared={comparedProperties}
            rankingMode={rankingMode}
            onRankingModeChange={setRankingMode}
            onRemove={removeComparedProperty}
            onClear={() => {
              clearComparedProperties();
              setCompareResult(null);
            }}
            onAnalyze={runCompare}
            loading={compareLoading}
          />
        </div>

        {analysisPanelOpen && (
          <LLMAnalysisPanel result={compareResult} loading={compareLoading} />
        )}

        {detailPanelProperty && (
          <div className="w-full xl:w-[420px] xl:shrink-0 border-t xl:border-t-0 xl:border-l border-[var(--card-border)] overflow-y-auto bg-[var(--background)]">
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
