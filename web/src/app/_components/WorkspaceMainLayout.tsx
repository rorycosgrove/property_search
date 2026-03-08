'use client';

import type { CompareSetResponse, Property } from '@/lib/api';
import CompareDock from '@/components/CompareDock';
import LLMAnalysisPanel from '@/components/LLMAnalysisPanel';
import PropertyDetail from '@/components/PropertyDetail';
import PropertyFeed from '@/components/PropertyFeed';
import PropertyMap from '@/components/PropertyMap';

interface CompareErrorState {
  code?: string;
  message: string;
  raw?: string;
}

interface Props {
  properties: Property[];
  total: number;
  loading: boolean;
  comparedProperties: Property[];
  rankingMode: 'llm_only' | 'hybrid' | 'user_weighted';
  compareLoading: boolean;
  analysisStale: boolean;
  canRunCompare: boolean;
  autoCompareTargetCount: number;
  compareResult: CompareSetResponse | null;
  compareError: CompareErrorState | null;
  canRetry: boolean;
  detailPanelProperty: Property | null;
  onRankingModeChange: (mode: 'llm_only' | 'hybrid' | 'user_weighted') => void;
  onRemoveCompared: (propertyId: string) => void;
  onClearCompared: () => void;
  onRunCompare: () => void;
  onRetryCompare: () => void;
  onCloseDetail: () => void;
}

export default function WorkspaceMainLayout({
  properties,
  total,
  loading,
  comparedProperties,
  rankingMode,
  compareLoading,
  analysisStale,
  canRunCompare,
  autoCompareTargetCount,
  compareResult,
  compareError,
  canRetry,
  detailPanelProperty,
  onRankingModeChange,
  onRemoveCompared,
  onClearCompared,
  onRunCompare,
  onRetryCompare,
  onCloseDetail,
}: Props) {
  return (
    <div className="flex flex-1 min-h-0 overflow-hidden flex-col lg:flex-row bg-[var(--background)]/40">
      <div className="w-full lg:w-[360px] lg:shrink-0 border-b lg:border-b-0 lg:border-r border-[var(--card-border)] overflow-y-auto bg-[var(--card-bg)]/80 rise-in">
        <PropertyFeed
          properties={properties}
          total={total}
          loading={loading}
        />
      </div>

      <div className="flex-1 flex flex-col min-h-0 border-l-0 lg:border-l border-[var(--card-border)]/40">
        <div className="flex-1 relative min-h-0 bg-[var(--card-bg)]/35">
          <PropertyMap properties={properties} />
        </div>
        <CompareDock
          compared={comparedProperties}
          rankingMode={rankingMode}
          onRankingModeChange={onRankingModeChange}
          onRemove={onRemoveCompared}
          onClear={onClearCompared}
          onRunAnalysis={onRunCompare}
          loading={compareLoading}
          canRunAnalysis={canRunCompare}
          analysisStale={analysisStale}
          autoCompareTargetCount={autoCompareTargetCount}
        />
      </div>

      <LLMAnalysisPanel
        result={compareResult}
        loading={compareLoading}
        error={compareError}
        analysisIsStale={analysisStale}
        onRetry={onRetryCompare}
        canRetry={canRunCompare && canRetry}
      />

      {detailPanelProperty && (
        <div className="w-full xl:w-[420px] xl:shrink-0 border-t xl:border-t-0 xl:border-l border-[var(--card-border)] overflow-y-auto bg-[var(--card-bg)]/92 rise-in">
          <PropertyDetail
            property={detailPanelProperty}
            onClose={onCloseDetail}
          />
        </div>
      )}
    </div>
  );
}
