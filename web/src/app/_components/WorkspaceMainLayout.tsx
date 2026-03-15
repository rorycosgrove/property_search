'use client';

import { useEffect, useState } from 'react';

import type { CompareSetResponse, Property } from '@/lib/api';
import type { Citation, RetrievalContext } from '@/lib/api';
import CompareDock from '@/components/CompareDock';
import FilterBar from '@/components/FilterBar';
import LLMAnalysisPanel from '@/components/LLMAnalysisPanel';
import PropertyDetail from '@/components/PropertyDetail';
import PropertyFeed from '@/components/PropertyFeed';
import PropertyMap from '@/components/PropertyMap';
import WorkspaceAskPanel from '@/app/_components/WorkspaceAskPanel';
import WorkspaceStatusStrip from '@/app/_components/WorkspaceStatusStrip';

interface CompareErrorState {
  code?: string;
  message: string;
  raw?: string;
}

interface Props {
  properties: Property[];
  mapProperties: Property[];
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
  guidanceMessage: string;
  aiQuery: string;
  aiLoading: boolean;
  aiError: string | null;
  aiReply: string | null;
  aiCitations: Citation[];
  aiRetrievalContext: RetrievalContext | null;
  retrievalPreview: RetrievalContext;
  askPanelOpen: boolean;
  onRankingModeChange: (mode: 'llm_only' | 'hybrid' | 'user_weighted') => void;
  onRemoveCompared: (propertyId: string) => void;
  onClearCompared: () => void;
  onRunCompare: () => void;
  onRetryCompare: () => void;
  onCloseDetail: () => void;
  onUseContext: () => void;
  onToggleAskPanel: () => void;
  onQueryChange: (value: string) => void;
  onAsk: () => void;
}

export default function WorkspaceMainLayout({
  properties,
  mapProperties,
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
  guidanceMessage,
  aiQuery,
  aiLoading,
  aiError,
  aiReply,
  aiCitations,
  aiRetrievalContext,
  retrievalPreview,
  askPanelOpen,
  onRankingModeChange,
  onRemoveCompared,
  onClearCompared,
  onRunCompare,
  onRetryCompare,
  onCloseDetail,
  onUseContext,
  onToggleAskPanel,
  onQueryChange,
  onAsk,
}: Props) {
  const [mobilePanel, setMobilePanel] = useState<'feed' | 'compare' | 'analysis' | 'detail' | null>(null);
  const [desktopToolbarOpen, setDesktopToolbarOpen] = useState(true);
  const [desktopPanel, setDesktopPanel] = useState<'controls' | 'feed' | 'compare' | 'analysis' | 'detail'>('controls');

  useEffect(() => {
    if (!detailPanelProperty && mobilePanel === 'detail') {
      setMobilePanel(null);
    }
    if (!detailPanelProperty && desktopPanel === 'detail') {
      setDesktopPanel('feed');
    }
  }, [detailPanelProperty, mobilePanel, desktopPanel]);

  const mobilePanelTitle = mobilePanel === 'feed'
    ? 'Shortlist'
    : mobilePanel === 'compare'
      ? 'Compare'
      : mobilePanel === 'analysis'
        ? 'AI Brief'
        : 'Property Detail';

  return (
    <div className="relative flex flex-1 min-h-0 overflow-hidden bg-[var(--background)]/40">
      <div className="hidden lg:flex flex-1 min-h-0">
        <div className="relative flex-1 min-w-0 bg-[var(--card-bg)]/35 border-r border-[var(--card-border)]">
          <PropertyMap properties={mapProperties} />
        </div>

        <aside
          className={[
            'shrink-0 bg-[var(--card-bg)]/92 transition-all duration-300 ease-out overflow-hidden',
            desktopToolbarOpen ? 'w-[420px]' : 'w-[60px]',
          ].join(' ')}
          aria-label="Workspace controls"
        >
          <div className="h-full flex flex-col border-l border-[var(--card-border)]">
            <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--card-border)] bg-[var(--background)]/70">
              {desktopToolbarOpen ? <p className="text-sm font-semibold">Controls</p> : <span className="text-[10px] text-[var(--muted)]">UI</span>}
              <button
                type="button"
                onClick={() => setDesktopToolbarOpen((v) => !v)}
                className="px-2 py-1 text-xs border border-[var(--card-border)] rounded-md hover:bg-[var(--background)]"
                aria-label={desktopToolbarOpen ? 'Collapse toolbar' : 'Expand toolbar'}
              >
                {desktopToolbarOpen ? 'Hide' : 'Show'}
              </button>
            </div>

            {desktopToolbarOpen ? (
              <>
                <div className="px-2 py-2 border-b border-[var(--card-border)] bg-[var(--background)]/40 grid grid-cols-2 gap-1 text-xs">
                  <button
                    type="button"
                    onClick={() => setDesktopPanel('controls')}
                    className={[
                      'px-2 py-1.5 rounded-md border transition-colors',
                      desktopPanel === 'controls' ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)]' : 'border-[var(--card-border)] hover:bg-[var(--background)]',
                    ].join(' ')}
                  >
                    Controls
                  </button>
                  <button
                    type="button"
                    onClick={() => setDesktopPanel('feed')}
                    className={[
                      'px-2 py-1.5 rounded-md border transition-colors',
                      desktopPanel === 'feed' ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)]' : 'border-[var(--card-border)] hover:bg-[var(--background)]',
                    ].join(' ')}
                  >
                    Shortlist
                  </button>
                  <button
                    type="button"
                    onClick={() => setDesktopPanel('compare')}
                    className={[
                      'px-2 py-1.5 rounded-md border transition-colors',
                      desktopPanel === 'compare' ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)]' : 'border-[var(--card-border)] hover:bg-[var(--background)]',
                    ].join(' ')}
                  >
                    Compare
                  </button>
                  <button
                    type="button"
                    onClick={() => setDesktopPanel('analysis')}
                    className={[
                      'px-2 py-1.5 rounded-md border transition-colors',
                      desktopPanel === 'analysis' ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)]' : 'border-[var(--card-border)] hover:bg-[var(--background)]',
                    ].join(' ')}
                  >
                    AI Brief
                  </button>
                  <button
                    type="button"
                    onClick={() => setDesktopPanel('detail')}
                    className={[
                      'px-2 py-1.5 rounded-md border transition-colors',
                      desktopPanel === 'detail' ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)]' : 'border-[var(--card-border)] hover:bg-[var(--background)]',
                    ].join(' ')}
                    disabled={!detailPanelProperty}
                  >
                    Detail
                  </button>
                </div>

                <div className="flex-1 min-h-0 overflow-y-auto">
                  {desktopPanel === 'controls' ? (
                    <div className="min-h-full">
                      <FilterBar />
                      <WorkspaceStatusStrip
                        autoCompareTargetCount={autoCompareTargetCount}
                        guidanceMessage={guidanceMessage}
                        analysisStale={analysisStale}
                        canRunCompare={canRunCompare}
                        compareLoading={compareLoading}
                        askPanelOpen={askPanelOpen}
                        onUseContext={onUseContext}
                        onRunCompare={onRunCompare}
                        onToggleAskPanel={onToggleAskPanel}
                      />
                      {askPanelOpen ? (
                        <WorkspaceAskPanel
                          aiQuery={aiQuery}
                          aiLoading={aiLoading}
                          aiError={aiError}
                          aiReply={aiReply}
                          aiCitations={aiCitations}
                          aiRetrievalContext={aiRetrievalContext}
                          retrievalPreview={retrievalPreview}
                          onQueryChange={onQueryChange}
                          onAsk={onAsk}
                        />
                      ) : null}
                    </div>
                  ) : null}

                  {desktopPanel === 'feed' ? (
                    <PropertyFeed
                      properties={properties}
                      total={total}
                      loading={loading}
                    />
                  ) : null}

                  {desktopPanel === 'compare' ? (
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
                  ) : null}

                  {desktopPanel === 'analysis' ? (
                    <LLMAnalysisPanel
                      result={compareResult}
                      loading={compareLoading}
                      error={compareError}
                      analysisIsStale={analysisStale}
                      onRetry={onRetryCompare}
                      canRetry={canRunCompare && canRetry}
                      embedded
                    />
                  ) : null}

                  {desktopPanel === 'detail' ? (
                    detailPanelProperty ? (
                      <PropertyDetail
                        property={detailPanelProperty}
                        onClose={onCloseDetail}
                      />
                    ) : (
                      <p className="p-4 text-sm text-[var(--muted)]">Select a property on the map to open detail in this panel.</p>
                    )
                  ) : null}
                </div>
              </>
            ) : (
              <div className="flex-1 flex flex-col items-center gap-2 py-3">
                <button
                  type="button"
                  onClick={() => {
                    setDesktopToolbarOpen(true);
                    setDesktopPanel('controls');
                  }}
                  className="w-10 h-10 rounded-md border border-[var(--card-border)] text-xs hover:bg-[var(--background)]"
                  aria-label="Open controls"
                >
                  UI
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setDesktopToolbarOpen(true);
                    setDesktopPanel('feed');
                  }}
                  className="w-10 h-10 rounded-md border border-[var(--card-border)] text-xs hover:bg-[var(--background)]"
                  aria-label="Open shortlist"
                >
                  S
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setDesktopToolbarOpen(true);
                    setDesktopPanel('compare');
                  }}
                  className="w-10 h-10 rounded-md border border-[var(--card-border)] text-xs hover:bg-[var(--background)]"
                  aria-label="Open compare"
                >
                  C
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setDesktopToolbarOpen(true);
                    setDesktopPanel('analysis');
                  }}
                  className="w-10 h-10 rounded-md border border-[var(--card-border)] text-xs hover:bg-[var(--background)]"
                  aria-label="Open AI brief"
                >
                  AI
                </button>
              </div>
            )}
          </div>
        </aside>
      </div>

      <div className="flex-1 flex flex-col min-h-0 lg:hidden">
        <div className="relative flex-1 min-h-0 bg-[var(--card-bg)]/35">
          <PropertyMap properties={mapProperties} />

          <div className="lg:hidden absolute bottom-3 left-1/2 -translate-x-1/2 z-[450] flex items-center gap-1 rounded-full border border-[var(--card-border)] bg-[var(--card-bg)]/95 px-2 py-1 backdrop-blur-md shadow-lg">
            <button
              type="button"
              onClick={() => setMobilePanel((p) => (p === 'feed' ? null : 'feed'))}
              className="px-3 py-1.5 text-xs rounded-full border border-[var(--card-border)] bg-[var(--background)]"
            >
              Shortlist
            </button>
            <button
              type="button"
              onClick={() => setMobilePanel((p) => (p === 'compare' ? null : 'compare'))}
              className="px-3 py-1.5 text-xs rounded-full border border-[var(--card-border)] bg-[var(--background)]"
            >
              Compare
            </button>
            <button
              type="button"
              onClick={() => setMobilePanel((p) => (p === 'analysis' ? null : 'analysis'))}
              className="px-3 py-1.5 text-xs rounded-full border border-[var(--card-border)] bg-[var(--background)]"
            >
              AI Brief
            </button>
            {detailPanelProperty ? (
              <button
                type="button"
                onClick={() => setMobilePanel((p) => (p === 'detail' ? null : 'detail'))}
                className="px-3 py-1.5 text-xs rounded-full border border-[var(--card-border)] bg-[var(--background)]"
              >
                Detail
              </button>
            ) : null}
          </div>

          {mobilePanel && (
            <div className="lg:hidden absolute inset-x-3 bottom-16 z-[460] max-h-[74vh] overflow-hidden rounded-2xl border border-[var(--card-border)] bg-[var(--card-bg)] shadow-2xl rise-in">
              <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--card-border)] bg-[var(--background)]/70">
                <p className="text-sm font-semibold">{mobilePanelTitle}</p>
                <button
                  type="button"
                  onClick={() => setMobilePanel(null)}
                  className="px-2 py-1 text-xs border border-[var(--card-border)] rounded-md"
                >
                  Close
                </button>
              </div>

              <div className="max-h-[calc(74vh-46px)] overflow-y-auto">
                {mobilePanel === 'feed' ? (
                  <div className="h-[62vh]">
                    <PropertyFeed
                      properties={properties}
                      total={total}
                      loading={loading}
                    />
                  </div>
                ) : null}

                {mobilePanel === 'compare' ? (
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
                ) : null}

                {mobilePanel === 'analysis' ? (
                  <LLMAnalysisPanel
                    result={compareResult}
                    loading={compareLoading}
                    error={compareError}
                    analysisIsStale={analysisStale}
                    onRetry={onRetryCompare}
                    canRetry={canRunCompare && canRetry}
                    embedded
                  />
                ) : null}

                {mobilePanel === 'detail' ? (
                  detailPanelProperty ? (
                    <PropertyDetail
                      property={detailPanelProperty}
                      onClose={() => {
                        onCloseDetail();
                        setMobilePanel(null);
                      }}
                    />
                  ) : (
                    <p className="p-4 text-sm text-[var(--muted)]">Select a property on the map or shortlist to view details.</p>
                  )
                ) : null}
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
