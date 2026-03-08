'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  type AutoCompareLatestResponse,
  type Citation,
  createConversation,
  type CompareSetResponse,
  getLatestAutoCompare,
  getConversation,
  getProperties,
  type Property,
  type PropertyListResponse,
  type RetrievalContext,
  sendConversationMessage,
  triggerAutoCompare,
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

const isRankingMode = (value: unknown): value is 'llm_only' | 'hybrid' | 'user_weighted' => {
  return value === 'llm_only' || value === 'hybrid' || value === 'user_weighted';
};

export default function HomePage() {
  const router = useRouter();
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
  const [data, setData] = useState<PropertyListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareResult, setCompareResult] = useState<CompareSetResponse | null>(null);
  const [compareError, setCompareError] = useState<CompareErrorState | null>(null);
  const [aiQuery, setAiQuery] = useState('');
  const [aiReply, setAiReply] = useState<string | null>(null);
  const [aiCitations, setAiCitations] = useState<Citation[]>([]);
  const [aiRetrievalContext, setAiRetrievalContext] = useState<RetrievalContext | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [autoCompareSessionId, setAutoCompareSessionId] = useState<string>('');
  const [autoCompareTargetCount, setAutoCompareTargetCount] = useState(0);
  const lastAutoCompareKeyRef = useRef<string>('');

  const CONVERSATION_KEY = 'property_search_conversation_id';
  const AUTO_COMPARE_SESSION_KEY = 'property_search_auto_compare_session_id';

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
    let active = true;

    const bootConversation = async () => {
      try {
        if (typeof window === 'undefined') {
          return;
        }

        const saved = window.localStorage.getItem(CONVERSATION_KEY);
        if (saved) {
          await getConversation(saved);
          if (active) {
            setConversationId(saved);
          }
          return;
        }

        const userIdentifier = window.navigator.userAgent || 'web-user';
        const created = await createConversation(userIdentifier, 'Main Workspace AI Session');
        window.localStorage.setItem(CONVERSATION_KEY, created.id);
        if (active) {
          setConversationId(created.id);
        }
      } catch {
        // Conversation can be created lazily on first ask if boot fails.
      }
    };

    bootConversation().catch(console.error);

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const queryPrompt = searchParams.get('ask') || '';
    const prompt = queryPrompt;

    if (prompt) {
      setAiQuery(prompt);
    }
  }, [searchParams]);

  useEffect(() => {
    if (searchParams.get('focus') !== 'ask') {
      return;
    }
    const panel = document.getElementById('ask-panel');
    if (panel) {
      panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [searchParams]);

  const properties = data?.items || [];
  const propertyMap = new Map(properties.map((p) => [p.id, p]));
  const comparedProperties = comparedPropertyIds
    .map((id) => propertyMap.get(id))
    .filter((p): p is Property => Boolean(p));

  const winnerMetric = compareResult?.properties?.[0];
  const selectedPropertyId = detailPanelProperty?.id || winnerMetric?.property_id || null;

  const buildRetrievalContext = (): RetrievalContext => ({
    selected_property_id: selectedPropertyId,
    selected_property_title: detailPanelProperty?.title || winnerMetric?.title || null,
    ranking_mode: rankingMode,
    shortlist_size: comparedPropertyIds.length,
    winner_property_id: compareResult?.winner_property_id || null,
    winner_property_title: winnerMetric?.title || null,
    grant_count: winnerMetric?.grants_count ?? 0,
  });

  const candidateAutoCompareIds = useMemo(() => {
    if (comparedPropertyIds.length >= 2) {
      return comparedPropertyIds.slice(0, 5);
    }
    return properties.slice(0, 5).map((p) => p.id);
  }, [comparedPropertyIds, properties]);

  const hydrateAutoCompareFromLatest = useCallback((latest: AutoCompareLatestResponse) => {
    if (latest.result) {
      setCompareResult(latest.result);
      setCompareError(null);
    } else if (latest.status === 'failed' && latest.error) {
      setCompareResult(null);
      setCompareError({
        code: 'auto_compare_failed',
        message: 'The latest automatic comparison run failed.',
        raw: latest.error,
      });
    }

    const rankingModeFromRun = latest.options?.ranking_mode;
    const propertyIdsFromOptions = Array.isArray(latest.options?.property_ids)
      ? latest.options.property_ids.filter((value): value is string => typeof value === 'string' && value.length > 0)
      : [];
    const propertyIdsFromResult = Array.isArray(latest.result?.properties)
      ? latest.result.properties
        .map((metric) => metric.property_id)
        .filter((value): value is string => typeof value === 'string' && value.length > 0)
      : [];

    const normalizedIds = Array.from(new Set(
      (propertyIdsFromOptions.length > 0 ? propertyIdsFromOptions : propertyIdsFromResult).slice(0, 5),
    ));
    if (typeof rankingModeFromRun === 'string' && normalizedIds.length >= 2) {
      if (isRankingMode(rankingModeFromRun) && rankingModeFromRun !== rankingMode) {
        setRankingMode(rankingModeFromRun);
      }
      setComparedProperties(normalizedIds);
      lastAutoCompareKeyRef.current = `${rankingModeFromRun}:${normalizedIds.join(',')}`;
    } else if (normalizedIds.length >= 2) {
      setComparedProperties(normalizedIds);
    }
  }, [rankingMode, setComparedProperties, setRankingMode]);

  const runCompare = async (propertyIds: string[]) => {
    const sessionId = autoCompareSessionId;
    if (propertyIds.length < 2 || !sessionId) {
      return;
    }

    setCompareLoading(true);
    setCompareError(null);
    try {
      const searchContext = {
        filters,
        compared_property_ids: comparedPropertyIds,
        selected_property_id: selectedPropertyId,
      };
      const run = await triggerAutoCompare({
        session_id: sessionId,
        property_ids: propertyIds,
        ranking_mode: rankingMode,
        search_context: searchContext,
      });

      const latest = await getLatestAutoCompare(sessionId).catch(() => null);
      if (latest) {
        hydrateAutoCompareFromLatest(latest);
      } else {
        setCompareResult(run.result);
      }
    } catch (err) {
      setCompareResult(null);
      setCompareError(parseCompareError(err));
    } finally {
      setCompareLoading(false);
    }
  };

  useEffect(() => {
    if (!autoCompareSessionId) {
      return;
    }

    let active = true;
    getLatestAutoCompare(autoCompareSessionId)
      .then((latest) => {
        if (!active) {
          return;
        }
        hydrateAutoCompareFromLatest(latest);
      })
      .catch(() => undefined);

    return () => {
      active = false;
    };
  }, [autoCompareSessionId, hydrateAutoCompareFromLatest]);

  useEffect(() => {
    const ids = candidateAutoCompareIds;
    setAutoCompareTargetCount(ids.length);
    if (ids.length < 2) {
      // Prevent stale winner/analysis from a previous larger shortlist.
      setCompareResult(null);
      setCompareError(null);
      lastAutoCompareKeyRef.current = '';
      return;
    }

    const compareKey = `${rankingMode}:${ids.join(',')}`;
    if (compareKey === lastAutoCompareKeyRef.current) {
      return;
    }

    const timeout = window.setTimeout(() => {
      lastAutoCompareKeyRef.current = compareKey;
      runCompare(ids).catch(console.error);
    }, 800);

    return () => {
      window.clearTimeout(timeout);
    };
  }, [
    candidateAutoCompareIds,
    rankingMode,
    autoCompareSessionId,
    filters,
    comparedPropertyIds,
    selectedPropertyId,
  ]);

  const guidanceMessage = compareResult
    ? 'Atlas has a live recommendation. Ask follow-up questions to challenge risk, grant eligibility, and long-term value.'
    : autoCompareTargetCount >= 2
      ? 'Atlas is preparing a live comparison for your current search.'
      : 'Narrow your search to at least 2 properties and Atlas will compare them automatically.';

  const applyContextToAIQuery = () => {
    const winner = compareResult?.properties?.[0];
    const prompt = winner
      ? `Review this shortlist result and challenge the winner (${winner.title}) against risk, grants, BER, and long-term value.`
      : `Help me compare ${Math.max(comparedPropertyIds.length, 2)} properties using ${rankingMode} ranking and define the best decision criteria.`;

    setAiQuery(prompt);
    setAiError(null);
  };

  const handleAskAtlas = async () => {
    const prompt = aiQuery.trim();
    if (!prompt || aiLoading) {
      return;
    }

    setAiLoading(true);
    setAiError(null);
    setAiCitations([]);

    try {
      let convId = conversationId;

      if (!convId && typeof window !== 'undefined') {
        const userIdentifier = window.navigator.userAgent || 'web-user';
        const created = await createConversation(userIdentifier, 'Main Workspace AI Session');
        convId = created.id;
        window.localStorage.setItem(CONVERSATION_KEY, created.id);
        setConversationId(created.id);
      }

      if (!convId) {
        throw new Error('Could not initialize AI session.');
      }

      const retrievalContext = buildRetrievalContext();
      const result = await sendConversationMessage(
        convId,
        prompt,
        selectedPropertyId || undefined,
        retrievalContext,
      );
      setAiReply(result.assistant_message.content);
      setAiCitations(result.assistant_message.citations || []);
      setAiRetrievalContext(result.retrieval_context || retrievalContext);
    } catch (err) {
      setAiError(err instanceof Error ? err.message : 'Failed to query Atlas AI.');
    } finally {
      setAiLoading(false);
    }
  };

  const retrievalPreview = buildRetrievalContext();

  return (
    <div className="flex flex-col h-[calc(100dvh-64px)] lg:h-[calc(100dvh-62px)]">
      <FilterBar />

      <div className="px-3 py-2 border-b border-[var(--card-border)] ai-glass flex flex-wrap items-center gap-2">
        <div className="px-3 py-1.5 rounded-full text-xs border border-[var(--card-border)] bg-[var(--card-bg)]">
          LLM Workspace: search -> auto-compare -> ask Atlas
        </div>
        <div className="ml-auto text-[11px] text-[var(--muted)] px-2 py-1 border border-[var(--card-border)] rounded-full">
          Auto-compare target: {autoCompareTargetCount}/5
        </div>
      </div>

      <div className="px-3 py-2 border-b border-[var(--card-border)] bg-[var(--card-bg)]/70 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-[var(--muted)]">{guidanceMessage}</span>
        <button
          type="button"
          onClick={applyContextToAIQuery}
          className="ml-auto px-3 py-1.5 rounded-full border border-[var(--accent)] bg-cyan-900/10 text-[var(--accent-strong)] hover:bg-cyan-900/15 text-xs"
        >
          Use context in AI query
        </button>
      </div>

      <div id="ask-panel" className="px-3 py-3 border-b border-[var(--card-border)] ai-glass">
        <div className="mb-2 rounded-md border border-[var(--card-border)] bg-[var(--background)]/60 px-3 py-2">
          <p className="text-[11px] uppercase tracking-wide text-[var(--muted)]">Retrieved context preview</p>
          <p className="text-xs text-[var(--muted)] mt-1">
            Mode: {retrievalPreview.ranking_mode} | Shortlist: {retrievalPreview.shortlist_size} |
            Selected: {retrievalPreview.selected_property_title || 'None'} |
            Winner: {retrievalPreview.winner_property_title || 'None'}
          </p>
        </div>

        <div className="flex flex-col lg:flex-row gap-2">
          <input
            value={aiQuery}
            onChange={(e) => setAiQuery(e.target.value)}
            placeholder="Ask Atlas AI in the workspace: compare trade-offs, validate strategy, or challenge the winner..."
            className="flex-1 bg-[var(--background)] border border-[var(--card-border)] rounded-lg px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={handleAskAtlas}
            disabled={!aiQuery.trim() || aiLoading}
            className="px-4 py-2 rounded-lg text-sm font-medium border border-[var(--accent)] bg-cyan-900/10 text-[var(--accent-strong)] hover:bg-cyan-900/15 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {aiLoading ? 'Asking Atlas...' : 'Ask Atlas'}
          </button>
        </div>

        {aiError ? (
          <p className="mt-2 text-xs text-[var(--danger)]">{aiError}</p>
        ) : null}

        {aiReply ? (
          <div className="mt-3 rounded-lg border border-[var(--card-border)] bg-[var(--card-bg)] p-3">
            <p className="text-xs uppercase tracking-wide text-[var(--muted)] mb-1">Atlas response</p>
            <p className="text-sm whitespace-pre-wrap leading-relaxed">{aiReply}</p>

            {aiRetrievalContext ? (
              <p className="text-xs text-[var(--muted)] mt-2">
                Grounded on: {aiRetrievalContext.selected_property_title || 'no focused property'};
                shortlist size {aiRetrievalContext.shortlist_size ?? 0};
                ranking mode {aiRetrievalContext.ranking_mode || 'n/a'}.
              </p>
            ) : null}

            {aiCitations.length > 0 ? (
              <div className="mt-3 pt-2 border-t border-[var(--card-border)]">
                <p className="text-xs uppercase tracking-wide text-[var(--muted)] mb-2">Evidence</p>
                <div className="space-y-2">
                  {aiCitations.map((citation, idx) => {
                    if (citation.type === 'property') {
                      return (
                        <a
                          key={`ai-citation-${idx}`}
                          href={citation.url || '#'}
                          target="_blank"
                          rel="noreferrer"
                          className="block rounded border border-[var(--card-border)] px-2 py-1.5 hover:bg-[var(--background)] text-xs"
                        >
                          {citation.label || 'Property citation'}
                        </a>
                      );
                    }

                    return (
                      <div key={`ai-citation-${idx}`} className="rounded border border-[var(--card-border)] px-2 py-1.5 text-xs">
                        {citation.label || citation.code || 'Grant citation'}
                        {citation.status ? ` • ${citation.status}` : ''}
                        {citation.estimated_benefit ? ` • est ${citation.estimated_benefit}` : ''}
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="flex flex-1 min-h-0 overflow-hidden flex-col lg:flex-row">
        <div className="w-full lg:w-[340px] lg:shrink-0 border-b lg:border-b-0 lg:border-r border-[var(--card-border)] overflow-y-auto bg-[var(--card-bg)]/65 rise-in">
          <PropertyFeed
            properties={properties}
            total={data?.total || 0}
            loading={loading}
          />
        </div>

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
              lastAutoCompareKeyRef.current = '';
            }}
            loading={compareLoading}
            autoCompareTargetCount={autoCompareTargetCount}
          />
        </div>

        <LLMAnalysisPanel
          result={compareResult}
          loading={compareLoading}
          error={compareError}
          onRetry={() => runCompare(candidateAutoCompareIds)}
          canRetry={candidateAutoCompareIds.length >= 2}
        />

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
