'use client';

import { useEffect, useState } from 'react';
import type { Property } from '@/lib/api';
import { getEnrichment, getPriceHistory, triggerEnrichment } from '@/lib/api';
import { formatEur, formatDate, berColor } from '@/lib/utils';

interface Props {
  property: Property;
  onClose: () => void;
}

export default function PropertyDetail({ property: prop, onClose }: Props) {
  const [enrichment, setEnrichment] = useState<any>(null);
  const [priceHistory, setPriceHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getEnrichment(prop.id).then(setEnrichment).catch(() => {});
    getPriceHistory(prop.id).then(setPriceHistory).catch(() => {});
  }, [prop.id]);

  const handleEnrich = async () => {
    setLoading(true);
    try {
      await triggerEnrichment(prop.id);
      // Poll for result after a delay
      setTimeout(async () => {
        try {
          const data = await getEnrichment(prop.id);
          setEnrichment(data);
        } catch {}
        setLoading(false);
      }, 5000);
    } catch {
      setLoading(false);
    }
  };

  return (
    <div className="p-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="text-2xl font-bold text-brand-400 mb-1">
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
              className="text-xs px-2 py-1 bg-brand-600 rounded hover:bg-brand-700 disabled:opacity-50 transition-colors"
            >
              {loading ? 'Analyzing...' : 'Analyze'}
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
                    className="bg-brand-500 h-2 rounded-full"
                    style={{ width: `${enrichment.value_score * 10}%` }}
                  />
                </div>
                <span className="text-sm font-bold">{enrichment.value_score}/10</span>
              </div>
            )}

            {enrichment.pros?.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-green-400 mb-1">Pros</h4>
                <ul className="text-xs text-[var(--muted)] space-y-0.5">
                  {enrichment.pros.map((p: string, i: number) => (
                    <li key={i}>✓ {p}</li>
                  ))}
                </ul>
              </div>
            )}

            {enrichment.cons?.length > 0 && (
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

      {/* External link */}
      <a
        href={prop.url}
        target="_blank"
        rel="noopener noreferrer"
        className="block text-center py-2 bg-brand-600 hover:bg-brand-700 rounded text-sm font-medium transition-colors"
      >
        View on Source Site →
      </a>
    </div>
  );
}
