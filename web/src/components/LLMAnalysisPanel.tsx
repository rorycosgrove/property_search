'use client';

import type { CompareSetResponse } from '@/lib/api';
import { formatEur } from '@/lib/utils';

interface CompareErrorState {
  code?: string;
  message: string;
  raw?: string;
}

interface Props {
  result: CompareSetResponse | null;
  loading: boolean;
  error?: CompareErrorState | null;
  onRetry?: () => void;
  canRetry?: boolean;
}

export default function LLMAnalysisPanel({ result, loading, error, onRetry, canRetry = true }: Props) {
  const panelClasses = 'w-full xl:w-[390px] xl:shrink-0 border-t xl:border-t-0 xl:border-l border-[var(--card-border)] ai-glass p-4 overflow-y-auto rise-in';

  if (loading) {
    return (
      <aside className={panelClasses}>
        <h2 className="text-lg font-semibold mb-2">Decision Studio</h2>
        <p className="text-sm text-[var(--muted)]">Atlas AI is evaluating value, risks, and trade-offs...</p>
      </aside>
    );
  }

  if (!result) {
    return (
      <aside className={panelClasses}>
        <h2 className="text-lg font-semibold mb-2">Decision Studio</h2>
        {error ? (
          <div className="rounded-lg border border-[var(--danger)]/35 bg-[var(--danger)]/8 p-3 mb-3">
            <p className="text-sm font-semibold text-[var(--danger)]">Analysis unavailable</p>
            <p className="text-sm text-[var(--foreground)] mt-1 leading-relaxed">{error.message}</p>
            {error.raw ? (
              <p className="text-xs text-[var(--muted)] mt-2 break-words">{error.raw}</p>
            ) : null}
            <p className="text-xs text-[var(--muted)] mt-2">Try: select another model in Settings or run with Hybrid ranking while AI is recovering.</p>
            {onRetry ? (
              <button
                onClick={onRetry}
                disabled={!canRetry || loading}
                className="mt-3 px-3 py-1.5 rounded text-xs font-medium border border-[var(--danger)]/40 bg-[var(--danger)]/12 hover:bg-[var(--danger)]/20 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                Retry analysis
              </button>
            ) : null}
          </div>
        ) : null}
        <p className="text-sm text-[var(--muted)] leading-relaxed">
          Build a shortlist in Decision Studio and run AI analysis to get an evidence-backed winner,
          clear trade-offs, and next-best actions.
        </p>
      </aside>
    );
  }

  return (
    <aside className={panelClasses}>
      <h2 className="text-lg font-semibold mb-1">Decision Studio</h2>
      <p className="text-xs text-[var(--muted)] mb-4">
        Ranking mode: <span className="uppercase tracking-wide">{result.ranking_mode}</span>
      </p>

      {onRetry ? (
        <button
          onClick={onRetry}
          disabled={!canRetry || loading}
          className="mb-4 px-3 py-1.5 rounded text-xs font-medium border border-[var(--card-border)] bg-[var(--background)] hover:bg-[var(--background)]/80 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          Re-run analysis
        </button>
      ) : null}

      <div className="rounded-lg border border-[var(--card-border)] bg-[var(--background)] p-3 mb-4">
        <p className="text-xs text-[var(--muted)] mb-1">Headline</p>
        <p className="font-semibold text-sm">{result.analysis.headline}</p>
        <p className="text-sm text-[var(--muted)] mt-2 leading-relaxed">{result.analysis.recommendation}</p>
        <p className="text-xs mt-2">Confidence: <span className="font-semibold uppercase">{result.analysis.confidence}</span></p>
      </div>

      <div className="mb-4">
        <h3 className="text-sm font-semibold mb-2">Top Picks</h3>
        <div className="space-y-2">
          {result.properties.slice(0, 3).map((property, idx) => (
            <div key={property.property_id} className="rounded-md border border-[var(--card-border)] p-2 bg-[var(--background)]">
              <p className="text-xs text-[var(--muted)]">#{idx + 1}</p>
              <p className="text-sm font-semibold leading-tight">{property.title}</p>
              <p className="text-xs text-[var(--muted)]">{property.county || 'Unknown county'}</p>
              <div className="flex justify-between text-xs mt-1">
                <span>{formatEur(property.price)}</span>
                <span>LLM {property.llm_value_score?.toFixed(1) ?? 'n/a'}</span>
                <span>Hybrid {property.hybrid_score?.toFixed(1) ?? 'n/a'}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mb-4">
        <h3 className="text-sm font-semibold mb-2">Trade-offs</h3>
        <ul className="space-y-1 text-sm text-[var(--muted)]">
          {result.analysis.key_tradeoffs.length > 0 ? result.analysis.key_tradeoffs.map((item, idx) => (
            <li key={`${item}-${idx}`}>- {item}</li>
          )) : <li>- No explicit trade-offs returned.</li>}
        </ul>
      </div>

      <div className="rounded-lg border border-[var(--card-border)] bg-[var(--background)] p-3">
        <p className="text-xs text-[var(--muted)] mb-1">Suggested next step</p>
        <p className="text-sm">Open the top pick detail panel and trigger enrichment to validate renovation and grant upside before final decision.</p>
      </div>
    </aside>
  );
}
