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

interface CompareErrorState {
  code?: string;
  message: string;
  raw?: string;
}

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
  const [compareError, setCompareError] = useState<CompareErrorState | null>(null);

  const parseCompareError = (err: unknown): CompareErrorState => {
    const fallback: CompareErrorState = {
      message: 'Failed to run AI analysis. Check LLM health and model configuration.',
    };

    if (!(err instanceof Error)) {
      return fallback;
    }

    const match = err.message.match(/API error \d+:\s*(.*)$/);
    if (!match) {
      return { ...fallback, raw: err.message };
    }

    try {
      const payload = JSON.parse(match[1]) as {
        detail?: { code?: string; message?: string; error?: string };
      };
      const detail = payload.detail;
      if (detail?.message) {
        return {
          code: detail.code,
          message: detail.message,
          raw: detail.error,
        };
      }
    } catch {
      // Keep fallback with raw message.
    }

    return { ...fallback, raw: err.message };
  };

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
    setCompareError(null);
    try {
      const result = await comparePropertySet(comparedPropertyIds, rankingMode);
      setCompareResult(result);
    } catch (err) {
      setCompareResult(null);
      setCompareError(parseCompareError(err));
    } finally {
      setCompareLoading(false);
    }
  };

  const guidanceMessage = compareResult
    ? 'Analysis complete. Ask Atlas to stress-test the winner against grants, BER, and renovation risk.'
    : comparedPropertyIds.length >= 2
      ? 'You are ready to run Decision Studio. Atlas can also pre-brief your comparison strategy.'
      : 'Select at least 2 homes to unlock AI decision analysis and evidence-backed trade-offs.';

  const openCopilotWithContext = () => {
    const winner = compareResult?.properties?.[0];
    const prompt = winner
      ? `Review this shortlist result and challenge the winner (${winner.title}) against risk, grants, BER, and long-term value.`
      : `Help me compare ${Math.max(comparedPropertyIds.length, 2)} properties using ${rankingMode} ranking and define the best decision criteria.`;

    if (typeof window !== 'undefined') {
      window.localStorage.setItem('atlas_pending_prompt', prompt);
      window.location.assign(`/copilot?prefill=${encodeURIComponent(prompt)}`);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100dvh-64px)] lg:h-[calc(100dvh-62px)]">
      <FilterBar />

      <div className="px-3 py-2 border-b border-[var(--card-border)] ai-glass flex flex-wrap items-center gap-2">
        <div className="px-3 py-1.5 rounded-full text-xs border border-[var(--card-border)] bg-[var(--card-bg)]">
          AI Mission: shortlist + compare + explain
        </div>
        <button
          onClick={toggleFeedPanel}
          className={[
            'px-2.5 py-1.5 rounded-md text-xs border focus:outline-none focus:ring-2 focus:ring-cyan-700',
            feedPanelOpen
              ? 'border-[var(--accent)] bg-cyan-900/10 text-[var(--accent-strong)]'
              : 'border-[var(--card-border)] hover:bg-[var(--background)]',
          ].join(' ')}
        >
          {feedPanelOpen ? 'Hide shortlist' : 'Show shortlist'}
        </button>
        <button
          onClick={toggleAnalysisPanel}
          className={[
            'px-2.5 py-1.5 rounded-md text-xs border focus:outline-none focus:ring-2 focus:ring-cyan-700',
            analysisPanelOpen
              ? 'border-[var(--accent)] bg-cyan-900/10 text-[var(--accent-strong)]'
              : 'border-[var(--card-border)] hover:bg-[var(--background)]',
          ].join(' ')}
        >
          {analysisPanelOpen ? 'Hide decision studio' : 'Show decision studio'}
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

      <div className="px-3 py-2 border-b border-[var(--card-border)] bg-[var(--card-bg)]/70 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-[var(--muted)]">{guidanceMessage}</span>
        <button
          type="button"
          onClick={openCopilotWithContext}
          className="ml-auto px-3 py-1.5 rounded-full border border-[var(--accent)] bg-cyan-900/10 text-[var(--accent-strong)] hover:bg-cyan-900/15 text-xs"
        >
          Send context to Atlas
        </button>
      </div>

      <div className="flex flex-1 min-h-0 overflow-hidden flex-col lg:flex-row">
        {feedPanelOpen && (
          <div className="w-full lg:w-[340px] lg:shrink-0 border-b lg:border-b-0 lg:border-r border-[var(--card-border)] overflow-y-auto bg-[var(--card-bg)]/65 rise-in">
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
              setCompareError(null);
            }}
            onAnalyze={runCompare}
            loading={compareLoading}
          />
        </div>

        {analysisPanelOpen && (
          <LLMAnalysisPanel
            result={compareResult}
            loading={compareLoading}
            error={compareError}
            onRetry={runCompare}
            canRetry={comparedPropertyIds.length >= 2}
          />
        )}

        {detailPanelProperty && (
          <div className="w-full xl:w-[420px] xl:shrink-0 border-t xl:border-t-0 xl:border-l border-[var(--card-border)] overflow-y-auto bg-[var(--background)] rise-in">
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
