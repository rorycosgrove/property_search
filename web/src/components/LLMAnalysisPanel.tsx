'use client';

import type { Citation, CompareSetResponse } from '@/lib/api';
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
  analysisIsStale?: boolean;
  onRetry?: () => void;
  canRetry?: boolean;
  embedded?: boolean;
}

export default function LLMAnalysisPanel({ result, loading, error, analysisIsStale = false, onRetry, canRetry = true, embedded = false }: Props) {
  const renderCitation = (citation: Citation, idx: number) => {
    if (citation.type === 'property') {
      return (
        <a
          key={`citation-${idx}`}
          href={citation.url || '#'}
          target="_blank"
          rel="noreferrer"
          className="block rounded-lg border border-[var(--card-border)] bg-[var(--background)] p-2 hover:bg-[var(--card-bg)]"
        >
          <p className="text-xs font-semibold">{citation.label || 'Property evidence'}</p>
          <p className="text-[11px] text-[var(--muted)]">{citation.county || 'Location unavailable'}</p>
        </a>
      );
    }

    return (
      <div key={`citation-${idx}`} className="rounded-lg border border-[var(--card-border)] bg-[var(--background)] p-2">
        <p className="text-xs font-semibold">{citation.label || citation.code || 'Grant evidence'}</p>
        <p className="text-[11px] text-[var(--muted)]">
          {citation.status || 'status unknown'}
          {citation.estimated_benefit ? ` | est ${formatEur(citation.estimated_benefit)}` : ''}
        </p>
      </div>
    );
  };

  const panelClasses = embedded
    ? 'w-full bg-[var(--card-bg)] p-4 overflow-y-auto'
    : 'w-full xl:w-[390px] xl:shrink-0 border-t xl:border-t-0 xl:border-l border-[var(--card-border)] bg-[var(--card-bg)]/90 p-4 overflow-y-auto rise-in';

  const panelHeader = (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">AI output</p>
        <h2 className="text-lg font-semibold">Decision brief</h2>
      </div>
      {onRetry ? (
        <button
          onClick={onRetry}
          disabled={!canRetry || loading}
          className="rounded-full border border-[var(--card-border)] bg-[var(--background)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--background)]/80 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Re-run
        </button>
      ) : null}
    </div>
  );

  if (loading) {
    return (
      <aside className={panelClasses}>
        {panelHeader}
        <div className="rounded-xl border border-[var(--card-border)] bg-[var(--background)] p-3">
          <p className="text-sm text-[var(--muted)]">Atlas is evaluating value, risk, and trade-offs.</p>
        </div>
      </aside>
    );
  }

  if (!result) {
    return (
      <aside className={panelClasses}>
        {panelHeader}
        {error ? (
          <div className="mb-3 rounded-xl border border-[var(--danger)]/35 bg-[var(--danger)]/8 p-3">
            <p className="text-sm font-semibold text-[var(--danger)]">Analysis unavailable</p>
            <p className="text-sm text-[var(--foreground)] mt-1 leading-relaxed">{error.message}</p>
            {error.raw ? (
              <p className="text-xs text-[var(--muted)] mt-2 break-words">{error.raw}</p>
            ) : null}
            <p className="text-xs text-[var(--muted)] mt-2">Try another model in Settings or switch to Hybrid ranking while AI recovers.</p>
            {onRetry ? (
              <button
                onClick={onRetry}
                disabled={!canRetry || loading}
                className="mt-3 rounded-full border border-[var(--danger)]/40 bg-[var(--danger)]/12 px-3 py-1.5 text-xs font-medium hover:bg-[var(--danger)]/20 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Retry analysis
              </button>
            ) : null}
          </div>
        ) : null}
        <div className="rounded-xl border border-[var(--card-border)] bg-[var(--background)] p-3">
          <p className="text-sm text-[var(--muted)] leading-relaxed">
            Add at least two homes to shortlist, then run analysis. Atlas will return a winner,
            key trade-offs, and evidence you can verify.
          </p>
        </div>
      </aside>
    );
  }

  return (
    <aside className={panelClasses}>
      {panelHeader}

      <p className="mb-3 text-xs text-[var(--muted)]">
        Ranking mode: <span className="uppercase tracking-wide">{result.ranking_mode}</span>
      </p>

      {analysisIsStale ? (
        <div className="mb-4 rounded-xl border border-amber-700/35 bg-amber-900/10 p-2.5">
          <p className="text-xs text-amber-200">
            Search context changed. Re-run analysis to refresh this recommendation.
          </p>
        </div>
      ) : null}

      <div className="mb-4 rounded-xl border border-[var(--card-border)] bg-[var(--background)] p-3">
        <p className="text-xs text-[var(--muted)] mb-1">Recommendation</p>
        <p className="font-semibold text-sm">{result.analysis.headline}</p>
        <p className="text-sm text-[var(--muted)] mt-2 leading-relaxed">{result.analysis.recommendation}</p>
        {result.analysis.reasoning ? (
          <p className="text-xs text-[var(--muted)] mt-2">Why this ranking: {result.analysis.reasoning}</p>
        ) : null}
        <p className="text-xs mt-2">Confidence: <span className="font-semibold uppercase">{result.analysis.confidence}</span></p>
      </div>

      <div className="mb-4 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-3">
        <h3 className="mb-2 text-sm font-semibold">Top picks</h3>
        <div className="space-y-2">
          {result.properties.slice(0, 3).map((property, idx) => (
            <div key={property.property_id} className="rounded-lg border border-[var(--card-border)] p-2 bg-[var(--background)]">
              <p className="text-xs text-[var(--muted)]">#{idx + 1}</p>
              <p className="text-sm font-semibold leading-tight">{property.title}</p>
              <p className="text-xs text-[var(--muted)]">{property.county || 'Unknown county'}</p>
              <div className="mt-1 flex justify-between text-xs">
                <span>{formatEur(property.price)}</span>
                <span>LLM {property.llm_value_score?.toFixed(1) ?? 'n/a'}</span>
                <span>Hybrid {property.hybrid_score?.toFixed(1) ?? 'n/a'}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mb-4 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-3">
        <h3 className="mb-2 text-sm font-semibold">Trade-offs</h3>
        <ul className="space-y-1 text-sm text-[var(--muted)]">
          {result.analysis.key_tradeoffs.length > 0 ? result.analysis.key_tradeoffs.map((item, idx) => (
            <li key={`${item}-${idx}`}>{item}</li>
          )) : <li>No explicit trade-offs returned.</li>}
        </ul>
      </div>

      <div className="mb-4 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-3">
        <h3 className="mb-2 text-sm font-semibold">Evidence</h3>
        <div className="space-y-2">
          {result.analysis.citations.length > 0
            ? result.analysis.citations.map((citation, idx) => renderCitation(citation, idx))
            : <p className="text-xs text-[var(--muted)]">No citations were returned.</p>}
        </div>
      </div>

      <div className="rounded-xl border border-[var(--card-border)] bg-[var(--background)] p-3">
        <p className="mb-1 text-xs text-[var(--muted)]">Suggested next step</p>
        <p className="text-sm">Open the top pick detail panel and run enrichment to validate renovation and grant upside before committing.</p>
      </div>
    </aside>
  );
}
