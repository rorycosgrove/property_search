import { useMemo } from 'react';

import type { CompareSetResponse, Property, RetrievalContext, RankingMode } from '@/lib/api';

interface UseWorkspaceContextArgs {
  properties: Property[];
  comparedPropertyIds: string[];
  detailPanelProperty: Property | null;
  compareResult: CompareSetResponse | null;
  rankingMode: RankingMode;
}

export function useWorkspaceContext({
  properties,
  comparedPropertyIds,
  detailPanelProperty,
  compareResult,
  rankingMode,
}: UseWorkspaceContextArgs) {
  const propertyMap = useMemo(() => new Map(properties.map((property) => [property.id, property])), [properties]);

  const comparedProperties = useMemo(() => (
    comparedPropertyIds
      .map((id) => propertyMap.get(id))
      .filter((property): property is Property => Boolean(property))
  ), [comparedPropertyIds, propertyMap]);

  const winnerMetric = compareResult?.properties?.[0];
  const selectedPropertyId = detailPanelProperty?.id || winnerMetric?.property_id || null;

  const retrievalPreview: RetrievalContext = {
    selected_property_id: selectedPropertyId,
    selected_property_title: detailPanelProperty?.title || winnerMetric?.title || null,
    ranking_mode: rankingMode,
    shortlist_size: comparedPropertyIds.length,
    winner_property_id: compareResult?.winner_property_id || null,
    winner_property_title: winnerMetric?.title || null,
    grant_count: winnerMetric?.grants_count ?? 0,
  };

  const buildContextPrompt = () => {
    if (winnerMetric) {
      return `Review this shortlist result and challenge the winner (${winnerMetric.title}) against risk, grants, BER, and long-term value.`;
    }

    return `Help me compare ${Math.max(comparedPropertyIds.length, 2)} properties using ${rankingMode} ranking and define the best decision criteria.`;
  };

  return {
    comparedProperties,
    selectedPropertyId,
    retrievalPreview,
    buildContextPrompt,
  };
}
