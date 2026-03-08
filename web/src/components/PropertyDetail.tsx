'use client';

import { useEffect, useState } from 'react';
import type { LLMEnrichment, PriceHistoryEntry, Property, PropertyGrantMatch } from '@/lib/api';
import { getEnrichment, getPriceHistory, getPropertyGrantMatches, triggerEnrichment } from '@/lib/api';
import { useMapStore } from '@/lib/stores';
import { formatEur, formatDate, berColor } from '@/lib/utils';

interface Props {
  property: Property;
  onClose: () => void;
}

export default function PropertyDetail({ property: prop, onClose }: Props) {
  const [enrichment, setEnrichment] = useState<LLMEnrichment | null>(null);
  const [priceHistory, setPriceHistory] = useState<PriceHistoryEntry[]>([]);
  const [grants, setGrants] = useState<PropertyGrantMatch[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { comparedPropertyIds, toggleCompareProperty } = useMapStore();

  useEffect(() => {
    let isMounted = true;

    const load = async () => {
      const errors: string[] = [];
      const [enrichmentResult, historyResult, grantsResult] = await Promise.allSettled([
        getEnrichment(prop.id),
        getPriceHistory(prop.id),
        getPropertyGrantMatches(prop.id),
      ]);

      if (!isMounted) {
        return;
      }

      if (enrichmentResult.status === 'fulfilled') {
        setEnrichment(enrichmentResult.value);
      } else {
        errors.push('AI analysis');
      }

      if (historyResult.status === 'fulfilled') {
        setPriceHistory(historyResult.value);
      } else {
        errors.push('price history');
      }

      if (grantsResult.status === 'fulfilled') {
        setGrants(grantsResult.value);
      } else {
        errors.push('grant data');
      }

      setLoadError(errors.length > 0 ? `Some sections failed to load: ${errors.join(', ')}` : null);
    };

    void load();

    return () => {
      isMounted = false;
    };
  }, [prop.id]);

  const handleEnrich = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      await triggerEnrichment(prop.id);
      window.setTimeout(async () => {
        try {
          const data = await getEnrichment(prop.id);
          setEnrichment(data);
        } catch {
          setLoadError('AI analysis was queued but result is not available yet.');
        }
        setLoading(false);
      }, 5000);
    } catch {
      setLoadError('Failed to trigger AI analysis. Check LLM health and queue configuration.');
      setLoading(false);
    }
  };

  return (
    <div className="p-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="text-2xl font-bold text-[var(--accent)] mb-1">
            {formatEur(prop.price)}
          </div>
          <h2 className="text-base font-semibold leading-tight">{prop.title}</h2>
          <p className="text-sm text-[var(--muted)] mt-0.5">{prop.address}</p>
        </div>
        <button
          onClick={onClose}
          className="ml-2 p-1 hover:bg-[var(--card-border)] rounded transition-colors"
        >
          ✕
        </button>
      </div>

      {/* Hero image */}
      <div className="mb-4 rounded-lg overflow-hidden border border-[var(--card-border)] bg-neutral-900 h-44">
        {prop.images?.[0]?.url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={prop.images[0].url} alt={prop.title} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-sm text-[var(--muted)]">
            No listing image available
          </div>
        )}
      </div>

      <div className="mb-4 flex gap-2">
        <button
          onClick={() => toggleCompareProperty(prop.id)}
          className={[
            'px-3 py-1.5 text-xs rounded border transition-colors',
            comparedPropertyIds.includes(prop.id)
              ? 'border-[var(--accent)] text-[var(--accent)] bg-cyan-900/10'
              : 'border-[var(--card-border)] hover:bg-[var(--card-border)]',
          ].join(' ')}
        >
          {comparedPropertyIds.includes(prop.id) ? 'In comparison dock' : 'Add to comparison dock'}
        </button>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-4 gap-2 mb-4">
        {prop.bedrooms != null && (
          <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded p-2 text-center">
            <div className="text-lg font-bold">{prop.bedrooms}</div>
            <div className="text-xs text-[var(--muted)]">Beds</div>
          </div>
        )}
        {prop.bathrooms != null && (
          <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded p-2 text-center">
            <div className="text-lg font-bold">{prop.bathrooms}</div>
            <div className="text-xs text-[var(--muted)]">Baths</div>
          </div>
        )}
        {prop.floor_area_sqm != null && (
          <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded p-2 text-center">
            <div className="text-lg font-bold">{prop.floor_area_sqm}</div>
            <div className="text-xs text-[var(--muted)]">m²</div>
          </div>
        )}
        {prop.ber_rating && (
          <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded p-2 text-center">
            <div
              className="text-lg font-bold"
              style={{ color: berColor(prop.ber_rating) }}
            >
              {prop.ber_rating}
            </div>
            <div className="text-xs text-[var(--muted)]">BER</div>
          </div>
        )}
      </div>

      {/* Description */}
      {prop.description && (
        <div className="mb-4">
          <h3 className="text-sm font-semibold mb-1">Description</h3>
          <p className="text-sm text-[var(--muted)] leading-relaxed">
            {prop.description.slice(0, 500)}
            {(prop.description?.length || 0) > 500 && '...'}
          </p>
        </div>
      )}

      {/* Price history */}
      {priceHistory.length > 0 && (
        <div className="mb-4">
          <h3 className="text-sm font-semibold mb-2">Price History</h3>
          <div className="space-y-1">
            {priceHistory.map((h: any) => (
              <div key={h.id} className="flex justify-between text-sm">
                <span className="text-[var(--muted)]">{formatDate(h.recorded_at)}</span>
                <span>
                  {formatEur(h.price)}
                  {h.price_change && (
                    <span className={h.price_change < 0 ? 'text-green-400 ml-2' : 'text-red-400 ml-2'}>
                      {h.price_change > 0 ? '+' : ''}{formatEur(h.price_change)}
                    </span>
                  )}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI Enrichment */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold">AI Analysis</h3>
          {!enrichment && (
            <button
              onClick={handleEnrich}
              disabled={loading}
              className="text-xs px-2 py-1 bg-[var(--accent)] text-white rounded hover:bg-[var(--accent-strong)] disabled:opacity-50 transition-colors"
            >
              {loading ? 'Analyzing...' : 'Run AI analysis'}
            </button>
          )}
        </div>

        {enrichment ? (
          <div className="space-y-3">
            <p className="text-sm text-[var(--muted)]">{enrichment.summary}</p>

            {enrichment.value_score && (
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">Value Score:</span>
                <div className="flex-1 bg-[var(--card-border)] rounded-full h-2">
                  <div
                    className="bg-[var(--accent)] h-2 rounded-full"
                    style={{ width: `${enrichment.value_score * 10}%` }}
                  />
                </div>
                <span className="text-sm font-bold">{enrichment.value_score}/10</span>
              </div>
            )}

            {Array.isArray(enrichment.pros) && enrichment.pros.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-green-400 mb-1">Pros</h4>
                <ul className="text-xs text-[var(--muted)] space-y-0.5">
                  {enrichment.pros.map((p: string, i: number) => (
                    <li key={i}>✓ {p}</li>
                  ))}
                </ul>
              </div>
            )}

            {Array.isArray(enrichment.cons) && enrichment.cons.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-red-400 mb-1">Cons</h4>
                <ul className="text-xs text-[var(--muted)] space-y-0.5">
                  {enrichment.cons.map((c: string, i: number) => (
                    <li key={i}>✗ {c}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          !loading && (
            <p className="text-xs text-[var(--muted)]">
              Click &quot;Analyze&quot; to get AI-powered insights
            </p>
          )
        )}
      </div>

      {loadError && (
        <p className="mb-4 text-xs text-amber-300">{loadError}</p>
      )}

      {/* Grants */}
      {grants.length > 0 && (
        <div className="mb-4">
          <h3 className="text-sm font-semibold mb-2">Grant Potential</h3>
          <div className="space-y-2">
            {grants.slice(0, 3).map((match) => (
              <div key={match.id} className="rounded border border-[var(--card-border)] p-2 bg-[var(--card-bg)]">
                <p className="text-xs font-semibold">{match.grant_program?.name || 'Grant program'}</p>
                <p className="text-xs text-[var(--muted)] mt-0.5">{match.reason || 'Eligibility under review'}</p>
                {match.estimated_benefit != null && (
                  <p className="text-xs text-green-300 mt-1">Potential: {formatEur(match.estimated_benefit)}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* External link */}
      <a
        href={prop.url}
        target="_blank"
        rel="noopener noreferrer"
        className="block text-center py-2 bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)] rounded text-sm font-medium transition-colors"
      >
        View on Source Site →
      </a>
    </div>
  );
}
