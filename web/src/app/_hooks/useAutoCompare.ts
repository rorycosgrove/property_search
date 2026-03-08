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
  return value === 'llm_only' || value === 'hybrid' || value === 'user_weighted';
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
  const [autoCompareTargetCount, setAutoCompareTargetCount] = useState(0);
  const lastAutoCompareKeyRef = useRef<string>('');

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

  const runCompare = useCallback(async (propertyIds: string[]) => {
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
  }, [autoCompareSessionId, comparedPropertyIds, filters, hydrateAutoCompareFromLatest, rankingMode, selectedPropertyId]);

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
  }, [autoCompareSessionId, candidateAutoCompareIds, comparedPropertyIds, filters, rankingMode, runCompare, selectedPropertyId]);

  const guidanceMessage = compareResult
    ? 'Atlas has a live recommendation. Ask follow-up questions to challenge risk, grant eligibility, and long-term value.'
    : autoCompareTargetCount >= 2
      ? 'Atlas is preparing a live comparison for your current search.'
      : 'Narrow your search to at least 2 properties and Atlas will compare them automatically.';

  const resetCompareState = useCallback(() => {
    setCompareResult(null);
    setCompareError(null);
    lastAutoCompareKeyRef.current = '';
  }, []);

  return {
    compareLoading,
    compareResult,
    compareError,
    autoCompareTargetCount,
    candidateAutoCompareIds,
    guidanceMessage,
    runCompare,
    resetCompareState,
  };
}
