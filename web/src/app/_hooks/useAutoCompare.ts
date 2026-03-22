import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  getLatestAutoCompare,
  triggerAutoCompare,
  type AutoCompareLatestResponse,
  type CompareSetResponse,
  type Property,
  type PropertyFilters,
  type RankingMode,
} from '@/lib/api';

export interface CompareErrorState {
  code?: string;
  message: string;
  raw?: string;
}

const isRankingMode = (value: unknown): value is RankingMode => {
  return value === 'llm_only' || value === 'hybrid' || value === 'user_weighted' || value === 'net_price';
};

function parseCompareError(err: unknown): CompareErrorState {
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
}

interface UseAutoCompareArgs {
  autoCompareSessionId: string;
  filters: PropertyFilters;
  properties: Property[];
  comparedPropertyIds: string[];
  selectedPropertyId: string | null;
  rankingMode: RankingMode;
  setRankingMode: (mode: RankingMode) => void;
  setComparedProperties: (ids: string[]) => void;
}

export function useAutoCompare({
  autoCompareSessionId,
  filters,
  properties,
  comparedPropertyIds,
  selectedPropertyId,
  rankingMode,
  setRankingMode,
  setComparedProperties,
}: UseAutoCompareArgs) {
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareResult, setCompareResult] = useState<CompareSetResponse | null>(null);
  const [compareError, setCompareError] = useState<CompareErrorState | null>(null);
  const [analysisStale, setAnalysisStale] = useState(false);
  const [autoCompareTargetCount, setAutoCompareTargetCount] = useState(0);
  const lastComparedContextKeyRef = useRef<string>('');
  const currentCompareContextKeyRef = useRef<string>('');

  const filterContextKey = useMemo(() => JSON.stringify({
    county: filters.county || null,
    min_price: filters.min_price ?? null,
    max_price: filters.max_price ?? null,
    min_beds: filters.min_beds ?? null,
    max_beds: filters.max_beds ?? null,
    property_types: filters.property_types || null,
    sale_type: filters.sale_type || null,
    keywords: filters.keywords || null,
    ber_ratings: filters.ber_ratings || null,
    sort_by: filters.sort_by || null,
    sort_dir: filters.sort_dir || null,
    lat: filters.lat ?? null,
    lng: filters.lng ?? null,
    radius_km: filters.radius_km ?? null,
  }), [filters]);

  const candidateAutoCompareIds = useMemo(() => {
    if (comparedPropertyIds.length >= 2) {
      return comparedPropertyIds.slice(0, 5);
    }
    return properties.slice(0, 5).map((p) => p.id);
  }, [comparedPropertyIds, properties]);

  const buildCompareContextKey = useCallback((ids: string[], mode: RankingMode, contextFiltersKey: string) => {
    return `${mode}:${ids.join(',')}:${contextFiltersKey}`;
  }, []);

  useEffect(() => {
    currentCompareContextKeyRef.current = buildCompareContextKey(candidateAutoCompareIds, rankingMode, filterContextKey);
  }, [buildCompareContextKey, candidateAutoCompareIds, filterContextKey, rankingMode]);

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
      const safeRunMode: RankingMode = isRankingMode(rankingModeFromRun) ? rankingModeFromRun : rankingMode;
      if (safeRunMode !== rankingMode) {
        setRankingMode(safeRunMode);
      }
      setComparedProperties(normalizedIds);
      const runSearchContext = latest.options?.search_context as { filters?: PropertyFilters } | undefined;
      const runFiltersKey = JSON.stringify({
        county: runSearchContext?.filters?.county || null,
        min_price: runSearchContext?.filters?.min_price ?? null,
        max_price: runSearchContext?.filters?.max_price ?? null,
        min_beds: runSearchContext?.filters?.min_beds ?? null,
        max_beds: runSearchContext?.filters?.max_beds ?? null,
        property_types: runSearchContext?.filters?.property_types || null,
        sale_type: runSearchContext?.filters?.sale_type || null,
        keywords: runSearchContext?.filters?.keywords || null,
        ber_ratings: runSearchContext?.filters?.ber_ratings || null,
        sort_by: runSearchContext?.filters?.sort_by || null,
        sort_dir: runSearchContext?.filters?.sort_dir || null,
        lat: runSearchContext?.filters?.lat ?? null,
        lng: runSearchContext?.filters?.lng ?? null,
        radius_km: runSearchContext?.filters?.radius_km ?? null,
      });
      lastComparedContextKeyRef.current = buildCompareContextKey(normalizedIds, safeRunMode, runFiltersKey);
      setAnalysisStale(lastComparedContextKeyRef.current !== buildCompareContextKey(candidateAutoCompareIds, rankingMode, filterContextKey));
    } else if (normalizedIds.length >= 2) {
      setComparedProperties(normalizedIds);
    }
  }, [buildCompareContextKey, candidateAutoCompareIds, filterContextKey, rankingMode, setComparedProperties, setRankingMode]);

  const runCompare = useCallback(async (propertyIds: string[]) => {
    const sessionId = autoCompareSessionId;
    if (propertyIds.length < 2 || !sessionId) {
      return;
    }

    const contextKey = buildCompareContextKey(propertyIds, rankingMode, filterContextKey);
    setCompareLoading(true);
    setCompareError(null);
    setAnalysisStale(false);
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

      if (currentCompareContextKeyRef.current !== contextKey) {
        return;
      }

      const latest = await getLatestAutoCompare(sessionId).catch(() => null);
      if (currentCompareContextKeyRef.current !== contextKey) {
        return;
      }
      if (latest) {
        hydrateAutoCompareFromLatest(latest);
      } else {
        setCompareResult(run.result);
      }
      lastComparedContextKeyRef.current = contextKey;
    } catch (err) {
      setCompareResult(null);
      setCompareError(parseCompareError(err));
    } finally {
      setCompareLoading(false);
    }
  }, [autoCompareSessionId, buildCompareContextKey, comparedPropertyIds, filterContextKey, filters, hydrateAutoCompareFromLatest, rankingMode, selectedPropertyId]);

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
      setAnalysisStale(false);
      lastComparedContextKeyRef.current = '';
      return;
    }

    const contextKey = buildCompareContextKey(ids, rankingMode, filterContextKey);
    const hasAnalysis = Boolean(compareResult || compareError);

    if (!hasAnalysis) {
      setAnalysisStale(false);
      return;
    }

    setAnalysisStale(lastComparedContextKeyRef.current !== contextKey);
  }, [buildCompareContextKey, candidateAutoCompareIds, compareError, compareResult, filterContextKey, rankingMode]);

  const canRunCompare = autoCompareTargetCount >= 2 && Boolean(autoCompareSessionId);

  const guidanceMessage = analysisStale
    ? 'Search context changed. Re-run analysis to refresh Atlas recommendations.'
    : compareResult
      ? 'Atlas has a live recommendation. Ask follow-up questions to challenge risk, grant eligibility, and long-term value.'
      : canRunCompare
        ? 'Analysis is ready for your current search. Run it when you are ready.'
        : 'Narrow your search to at least 2 properties to run analysis.';

  const resetCompareState = useCallback(() => {
    setCompareResult(null);
    setCompareError(null);
    setAnalysisStale(false);
    lastComparedContextKeyRef.current = '';
  }, []);

  return {
    compareLoading,
    compareResult,
    compareError,
    analysisStale,
    canRunCompare,
    autoCompareTargetCount,
    candidateAutoCompareIds,
    guidanceMessage,
    runCompare,
    resetCompareState,
  };
}
