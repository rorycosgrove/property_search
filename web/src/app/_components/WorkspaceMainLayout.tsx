'use client';

import { useEffect, useState } from 'react';

import type { CompareSetResponse, Property } from '@/lib/api';
import type { Citation, RetrievalContext } from '@/lib/api';
import WorkspaceAskPanel from '@/app/_components/WorkspaceAskPanel';
import WorkspaceStatusStrip from '@/app/_components/WorkspaceStatusStrip';
import CompareDock from '@/components/CompareDock';
import FilterBar from '@/components/FilterBar';
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

type WorkspacePanel = 'controls' | 'feed' | 'compare' | 'analysis' | 'detail';

const PANEL_LABELS: Record<WorkspacePanel, string> = {
  controls: 'Tools',
  feed: 'Shortlist',
  compare: 'Compare',
  analysis: 'AI Brief',
  detail: 'Detail',
};

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
  const [desktopPanel, setDesktopPanel] = useState<Exclude<WorkspacePanel, 'controls'>>('feed');
  const [mobilePanel, setMobilePanel] = useState<WorkspacePanel | null>(null);

  useEffect(() => {
    if (!detailPanelProperty && mobilePanel === 'detail') {
      setMobilePanel(null);
    }
    if (!detailPanelProperty && desktopPanel === 'detail') {
      setDesktopPanel('feed');
    }
  }, [detailPanelProperty, mobilePanel, desktopPanel]);

  useEffect(() => {
    if (!detailPanelProperty) {
      return;
    }
    setDesktopPanel('detail');
    setMobilePanel('detail');
  }, [detailPanelProperty]);

  const renderControls = () => (
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
  );

  const renderResultPanel = (panel: Exclude<WorkspacePanel, 'controls'>) => {
    if (panel === 'feed') {
      return <PropertyFeed properties={properties} total={total} loading={loading} />;
    }

    if (panel === 'compare') {
      return (
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
      );
    }

    if (panel === 'analysis') {
      return (
        <LLMAnalysisPanel
          result={compareResult}
          loading={compareLoading}
          error={compareError}
          analysisIsStale={analysisStale}
          onRetry={onRetryCompare}
          canRetry={canRunCompare && canRetry}
          embedded
        />
      );
    }

    return detailPanelProperty ? (
      <PropertyDetail property={detailPanelProperty} onClose={onCloseDetail} />
    ) : (
      <p className="p-4 text-sm text-[var(--muted)]">Select a property on the map or shortlist to open its detail panel.</p>
    );
  };

  const renderMobilePanel = () => {
    if (!mobilePanel) {
      return null;
    }

    return (
      <div className="lg:hidden absolute inset-x-3 bottom-16 z-[460] max-h-[78vh] overflow-hidden rounded-2xl border border-[var(--card-border)] bg-[var(--card-bg)] shadow-2xl rise-in">
        <div className="flex items-center justify-between border-b border-[var(--card-border)] bg-[var(--background)]/70 px-4 py-2">
          <div>
            <p className="text-[10px] uppercase tracking-[0.16em] text-[var(--muted)]">Workspace</p>
            <p className="text-sm font-semibold">{PANEL_LABELS[mobilePanel]}</p>
          </div>
          <button
            type="button"
            onClick={() => setMobilePanel(null)}
            className="rounded-md border border-[var(--card-border)] px-2 py-1 text-xs"
          >
            Close
          </button>
        </div>

        <div className="max-h-[calc(78vh-56px)] overflow-y-auto">
          {mobilePanel === 'controls' ? renderControls() : null}
          {mobilePanel === 'feed' ? <div className="h-[64vh]">{renderResultPanel('feed')}</div> : null}
          {mobilePanel === 'compare' ? renderResultPanel('compare') : null}
          {mobilePanel === 'analysis' ? renderResultPanel('analysis') : null}
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
    );
  };

  return (
    <div className="relative flex flex-1 min-h-0 overflow-hidden bg-[var(--background)]/40">
      <div className="hidden min-h-0 flex-1 lg:grid lg:grid-cols-[minmax(0,1fr)_460px]">
        <section className="relative min-w-0 border-r border-[var(--card-border)] bg-[var(--card-bg)]/35">
          <PropertyMap properties={mapProperties} />
          <div className="pointer-events-none absolute left-4 top-4 z-[430] max-w-sm rounded-2xl border border-[var(--card-border)] bg-[rgba(252,251,248,0.88)] px-4 py-3 shadow-lg backdrop-blur-md">
            <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--muted)]">Decision workspace</p>
            <p className="mt-1 text-sm font-semibold text-[var(--foreground)]">Map on the left, decisions on the right.</p>
            <p className="mt-1 text-xs leading-5 text-[var(--muted)]">Filters, AI context, shortlist, comparison, and detail stay visible in one steady flow instead of hiding behind multiple toolbar modes.</p>
          </div>
        </section>

        <aside className="flex min-h-0 flex-col border-l border-[var(--card-border)] bg-[var(--card-bg)]/92">
          <div className="shrink-0 border-b border-[var(--card-border)] bg-[var(--background)]/60 px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--muted)]">Guided flow</p>
            <h2 className="mt-1 text-lg font-semibold">Search, challenge, then compare.</h2>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto">
            {renderControls()}

            <section className="border-t border-[var(--card-border)] bg-[var(--card-bg)]/94">
              <div className="flex items-center justify-between border-b border-[var(--card-border)] bg-[var(--background)]/45 px-4 py-3">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.16em] text-[var(--muted)]">Decision panels</p>
                  <p className="text-sm font-semibold">Review your shortlist and reasoning.</p>
                </div>
                <div className="text-[11px] text-[var(--muted)]">{properties.length} loaded</div>
              </div>

              <div className="flex flex-wrap gap-2 border-b border-[var(--card-border)] bg-[var(--background)]/30 px-3 py-3 text-xs">
                {(['feed', 'compare', 'analysis', 'detail'] as const).map((panel) => (
                  <button
                    key={panel}
                    type="button"
                    onClick={() => setDesktopPanel(panel)}
                    disabled={panel === 'detail' && !detailPanelProperty}
                    className={[
                      'rounded-full border px-3 py-1.5 transition-colors',
                      desktopPanel === panel
                        ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)]'
                        : 'border-[var(--card-border)] bg-[var(--card-bg)] text-[var(--muted)] hover:bg-[var(--background)]',
                      panel === 'detail' && !detailPanelProperty ? 'cursor-not-allowed opacity-50' : '',
                    ].join(' ')}
                  >
                    {PANEL_LABELS[panel]}
                  </button>
                ))}
              </div>

              <div className="min-h-[28rem]">{renderResultPanel(desktopPanel)}</div>
            </section>
          </div>
        </aside>
      </div>

      <div className="flex min-h-0 flex-1 flex-col lg:hidden">
        <div className="border-b border-[var(--card-border)] bg-[var(--card-bg)]/88 px-4 py-3">
          <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--muted)]">Decision workspace</p>
          <h2 className="mt-1 text-base font-semibold">Open only the panel you need.</h2>
          <p className="mt-1 text-xs leading-5 text-[var(--muted)]">Map stays primary. Tools, shortlist, AI, and detail open as separate sheets.</p>
        </div>

        <div className="relative min-h-0 flex-1 bg-[var(--card-bg)]/35">
          <PropertyMap properties={mapProperties} />

          <div className="absolute bottom-3 left-1/2 z-[450] flex -translate-x-1/2 items-center gap-1 rounded-full border border-[var(--card-border)] bg-[var(--card-bg)]/95 px-2 py-1 backdrop-blur-md shadow-lg">
            {(['controls', 'feed', 'compare', 'analysis'] as const).map((panel) => (
              <button
                key={panel}
                type="button"
                onClick={() => setMobilePanel((current) => (current === panel ? null : panel))}
                className="rounded-full border border-[var(--card-border)] bg-[var(--background)] px-3 py-1.5 text-xs"
              >
                {PANEL_LABELS[panel]}
              </button>
            ))}
            {detailPanelProperty ? (
              <button
                type="button"
                onClick={() => setMobilePanel((current) => (current === 'detail' ? null : 'detail'))}
                className="rounded-full border border-[var(--card-border)] bg-[var(--background)] px-3 py-1.5 text-xs"
              >
                Detail
              </button>
            ) : null}
          </div>

          {renderMobilePanel()}
        </div>
      </div>
    </div>
  );
}
