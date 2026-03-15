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
  const inCompare = comparedPropertyIds.includes(prop.id);
  const quickStats = [
    prop.bedrooms != null ? { label: 'Beds', value: String(prop.bedrooms) } : null,
    prop.bathrooms != null ? { label: 'Baths', value: String(prop.bathrooms) } : null,
    prop.floor_area_sqm != null ? { label: 'm2', value: String(prop.floor_area_sqm) } : null,
    prop.ber_rating ? { label: 'BER', value: prop.ber_rating, color: berColor(prop.ber_rating) } : null,
  ].filter((item): item is { label: string; value: string; color?: string } => item !== null);

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
      <div className="mb-4 rounded-2xl border border-[var(--card-border)] bg-[var(--card-bg)]/92 p-4 shadow-[0_10px_30px_rgba(27,36,48,0.05)]">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="flex-1">
            <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">Property detail</p>
            <div className="mt-1 text-2xl font-bold text-[var(--accent)]">{formatEur(prop.price)}</div>
            <h2 className="mt-1 text-base font-semibold leading-tight">{prop.title}</h2>
            <p className="mt-0.5 text-sm text-[var(--muted)]">{prop.address}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full border border-[var(--card-border)] px-2.5 py-1 text-xs transition-colors hover:bg-[var(--background)]"
          >
            Close
          </button>
        </div>

        <div className="mb-4 h-44 overflow-hidden rounded-xl border border-[var(--card-border)] bg-neutral-900">
          {prop.images?.[0]?.url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={prop.images[0].url} alt={prop.title} className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-sm text-[var(--muted)]">
              No listing image available
            </div>
          )}
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          <button
            onClick={() => toggleCompareProperty(prop.id)}
            className={[
              'rounded-full border px-3 py-1.5 text-xs transition-colors',
              inCompare
                ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]'
                : 'border-[var(--card-border)] hover:bg-[var(--card-border)]',
            ].join(' ')}
          >
            {inCompare ? 'Added to compare' : 'Add to compare'}
          </button>
          <a
            href={prop.url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-full border border-[var(--accent)] bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-strong)]"
          >
            Open source listing
          </a>
        </div>

        {quickStats.length > 0 ? (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {quickStats.map((stat) => (
              <div
                key={stat.label}
                className="rounded-xl border border-[var(--card-border)] bg-[var(--background)] px-3 py-2 text-center"
              >
                <div className="text-lg font-bold" style={stat.color ? { color: stat.color } : undefined}>
                  {stat.value}
                </div>
                <div className="text-xs text-[var(--muted)]">{stat.label}</div>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      {prop.description ? (
        <section className="mb-4 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-3">
          <h3 className="mb-1 text-sm font-semibold">Description</h3>
          <p className="text-sm leading-relaxed text-[var(--muted)]">
            {prop.description.slice(0, 500)}
            {(prop.description?.length || 0) > 500 && '...'}
          </p>
        </section>
      ) : null}

      {priceHistory.length > 0 ? (
        <section className="mb-4 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-3">
          <h3 className="mb-2 text-sm font-semibold">Price history</h3>
          <div className="space-y-1.5">
            {priceHistory.map((entry) => (
              <div key={entry.id} className="flex items-center justify-between text-sm">
                <span className="text-[var(--muted)]">{formatDate(entry.recorded_at)}</span>
                <span>
                  {formatEur(entry.price)}
                  {entry.price_change ? (
                    <span className={entry.price_change < 0 ? 'ml-2 text-green-400' : 'ml-2 text-red-400'}>
                      {entry.price_change > 0 ? '+' : ''}
                      {formatEur(entry.price_change)}
                    </span>
                  ) : null}
                </span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="mb-4 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-3">
        <div className="mb-2 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">AI analysis</h3>
            <p className="text-xs text-[var(--muted)]">Generated per property on demand.</p>
          </div>
          {!enrichment ? (
            <button
              onClick={handleEnrich}
              disabled={loading}
              className="rounded-full bg-[var(--accent)] px-3 py-1.5 text-xs text-white transition-colors hover:bg-[var(--accent-strong)] disabled:opacity-50"
            >
              {loading ? 'Analyzing...' : 'Run AI analysis'}
            </button>
          ) : null}
        </div>

        {enrichment ? (
          <div className="space-y-3">
            <p className="text-sm text-[var(--muted)]">{enrichment.summary}</p>

            {enrichment.value_score ? (
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">Value score:</span>
                <div className="h-2 flex-1 rounded-full bg-[var(--card-border)]">
                  <div
                    className="h-2 rounded-full bg-[var(--accent)]"
                    style={{ width: `${enrichment.value_score * 10}%` }}
                  />
                </div>
                <span className="text-sm font-bold">{enrichment.value_score}/10</span>
              </div>
            ) : null}

            {Array.isArray(enrichment.pros) && enrichment.pros.length > 0 ? (
              <div>
                <h4 className="mb-1 text-xs font-semibold text-green-400">Pros</h4>
                <ul className="space-y-0.5 text-xs text-[var(--muted)]">
                  {enrichment.pros.map((pro, index) => (
                    <li key={index}>+ {pro}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {Array.isArray(enrichment.cons) && enrichment.cons.length > 0 ? (
              <div>
                <h4 className="mb-1 text-xs font-semibold text-red-400">Cons</h4>
                <ul className="space-y-0.5 text-xs text-[var(--muted)]">
                  {enrichment.cons.map((con, index) => (
                    <li key={index}>- {con}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : !loading ? (
          <p className="text-xs text-[var(--muted)]">Run analysis to generate AI summary and trade-offs.</p>
        ) : null}
      </section>

      {loadError ? <p className="mb-4 text-xs text-amber-300">{loadError}</p> : null}

      {grants.length > 0 ? (
        <section className="mb-4 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-3">
          <h3 className="mb-2 text-sm font-semibold">Grant potential</h3>
          <div className="space-y-2">
            {grants.slice(0, 3).map((match) => (
              <div key={match.id} className="rounded-lg border border-[var(--card-border)] bg-[var(--background)] p-2">
                <p className="text-xs font-semibold">{match.grant_program?.name || 'Grant program'}</p>
                <p className="mt-0.5 text-xs text-[var(--muted)]">{match.reason || 'Eligibility under review'}</p>
                {match.estimated_benefit != null ? (
                  <p className="mt-1 text-xs text-green-300">Potential: {formatEur(match.estimated_benefit)}</p>
                ) : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <a
        href={prop.url}
        target="_blank"
        rel="noopener noreferrer"
        className="block rounded-lg bg-[var(--accent)] py-2 text-center text-sm font-medium text-white transition-colors hover:bg-[var(--accent-strong)]"
      >
        View on source site
      </a>
    </div>
  );
}
