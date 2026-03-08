'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  type RetrievalContext,
} from '@/lib/api';
import { useFilterStore, useMapStore, useUIStore } from '@/lib/stores';
import FilterBar from '@/components/FilterBar';
import WorkspaceAskPanel from '@/app/_components/WorkspaceAskPanel';
import WorkspaceMainLayout from '@/app/_components/WorkspaceMainLayout';
import WorkspaceStatusStrip from '@/app/_components/WorkspaceStatusStrip';
import { useAIConversation } from '@/app/_hooks/useAIConversation';
import { useAutoCompare } from '@/app/_hooks/useAutoCompare';
import { usePropertySearch } from '@/app/_hooks/usePropertySearch';
import { useWorkspaceContext } from '@/app/_hooks/useWorkspaceContext';

export default function HomePage() {
  const searchParams = useSearchParams();
  const { filters } = useFilterStore();
  const {
    comparedPropertyIds,
    setComparedProperties,
    removeComparedProperty,
    clearComparedProperties,
  } = useMapStore();
  const {
    detailPanelProperty,
    closeDetail,
    rankingMode,
    setRankingMode,
  } = useUIStore();
  const [autoCompareSessionId, setAutoCompareSessionId] = useState<string>('');

  const AUTO_COMPARE_SESSION_KEY = 'property_search_auto_compare_session_id';

  const { data, loading, properties } = usePropertySearch(filters);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const existing = window.localStorage.getItem(AUTO_COMPARE_SESSION_KEY);
    if (existing) {
      setAutoCompareSessionId(existing);
      return;
    }

    const generated = `web-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    window.localStorage.setItem(AUTO_COMPARE_SESSION_KEY, generated);
    setAutoCompareSessionId(generated);
  }, []);

  useEffect(() => {
    if (searchParams.get('focus') !== 'ask') {
      return;
    }
    const panel = document.getElementById('ask-panel');
    if (panel) {
      panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [searchParams]);

  // Keep hook input independent of compare result to avoid init-order cycles.
  const selectedPropertyIdForCompare = detailPanelProperty?.id || null;

  const {
    compareLoading,
    compareResult,
    compareError,
    autoCompareTargetCount,
    candidateAutoCompareIds,
    guidanceMessage,
    runCompare,
    resetCompareState,
  } = useAutoCompare({
    autoCompareSessionId,
    filters,
    properties,
    comparedPropertyIds,
    selectedPropertyId: selectedPropertyIdForCompare,
    rankingMode,
    setRankingMode,
    setComparedProperties,
  });

  const {
    comparedProperties,
    selectedPropertyId,
    retrievalPreview,
    buildContextPrompt,
  } = useWorkspaceContext({
    properties,
    comparedPropertyIds,
    detailPanelProperty,
    compareResult,
    rankingMode,
  });

  const buildRetrievalContext = (): RetrievalContext => retrievalPreview;

  const askQueryParam = searchParams.get('ask') || '';

  const {
    aiQuery,
    setAiQuery,
    aiReply,
    aiCitations,
    aiRetrievalContext,
    aiLoading,
    aiError,
    setAiError,
    askAtlas,
  } = useAIConversation({
    selectedPropertyId,
    getRetrievalContext: buildRetrievalContext,
    initialQuery: askQueryParam,
  });

  const applyContextToAIQuery = () => {
    setAiQuery(buildContextPrompt());
    setAiError(null);
  };

  return (
    <div className="flex flex-col h-[calc(100dvh-64px)] lg:h-[calc(100dvh-62px)]">
      <FilterBar />

      <WorkspaceStatusStrip
        autoCompareTargetCount={autoCompareTargetCount}
        guidanceMessage={guidanceMessage}
        onUseContext={applyContextToAIQuery}
      />

      <WorkspaceAskPanel
        aiQuery={aiQuery}
        aiLoading={aiLoading}
        aiError={aiError}
        aiReply={aiReply}
        aiCitations={aiCitations}
        aiRetrievalContext={aiRetrievalContext}
        retrievalPreview={retrievalPreview}
        onQueryChange={setAiQuery}
        onAsk={askAtlas}
      />

      <WorkspaceMainLayout
        properties={properties}
        total={data?.total || 0}
        loading={loading}
        comparedProperties={comparedProperties}
        rankingMode={rankingMode}
        compareLoading={compareLoading}
        autoCompareTargetCount={autoCompareTargetCount}
        compareResult={compareResult}
        compareError={compareError}
        canRetry={candidateAutoCompareIds.length >= 2}
        detailPanelProperty={detailPanelProperty}
        onRankingModeChange={setRankingMode}
        onRemoveCompared={removeComparedProperty}
        onClearCompared={() => {
          clearComparedProperties();
          resetCompareState();
        }}
        onRetryCompare={() => runCompare(candidateAutoCompareIds)}
        onCloseDetail={closeDetail}
      />
    </div>
  );
}
