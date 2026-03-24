'use client';

import { useEffect, useState } from 'react';
import type { LLMEnrichment, Property, PropertyGrantMatch, PropertyIntelligence } from '@/lib/api';
import {
  getEnrichment,
  getPropertyGrantMatches,
  getPropertyIntelligence,
  triggerEnrichment,
} from '@/lib/api';
import { getPropertyBrief, type PropertyBrief } from '@/lib/api';
import { useMapStore } from '@/lib/stores';
import { berColor, formatDate, formatEur } from '@/lib/utils';

interface Props {
  property: Property;
  onClose: () => void;
}

function CompletenessBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    score >= 0.75 ? 'var(--success)' : score >= 0.45 ? 'var(--signal)' : 'var(--danger)';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 rounded-full bg-[var(--card-border)]">
        <div
          className="h-1.5 rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-[10px] font-medium tabular-nums" style={{ color }}>
        {pct}% complete
      </span>
    </div>
  );
}

function SectionHeader({ title }: { title: string }) {
  return (
    <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--muted)]">
      {title}
    </h3>
  );
}

export default function PropertyDetail({ property: prop, onClose }: Props) {
  const [intelligence, setIntelligence] = useState<PropertyIntelligence | null>(null);
  const [grants, setGrants] = useState<PropertyGrantMatch[]>([]);
  const [enrichment, setEnrichment] = useState<LLMEnrichment | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [enrichPending, setEnrichPending] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'history' | 'evidence' | 'ai'>('overview');
  const [brief, setBrief] = useState<PropertyBrief | null>(null);
  const [briefLoading, setBriefLoading] = useState(false);
  const { comparedPropertyIds, toggleCompareProperty } = useMapStore();
  const inCompare = comparedPropertyIds.includes(prop.id);

  useEffect(() => {
    setIntelligence(null);
    setGrants([]);
    setEnrichment(null);
    setLoadError(null);
    setActiveTab('overview');

    let cancelled = false;

    const load = async () => {
      const [intelligenceResult, grantsResult] = await Promise.allSettled([
        getPropertyIntelligence(prop.id),
        getPropertyGrantMatches(prop.id),
      ]);

      if (cancelled) return;

      if (intelligenceResult.status === 'fulfilled') {
        setIntelligence(intelligenceResult.value);
        if (intelligenceResult.value.listing.enrichment) {
          setEnrichment(intelligenceResult.value.listing.enrichment);
        }
      } else {
        setLoadError('Could not load property intelligence. Some sections may be unavailable.');
      }

      if (grantsResult.status === 'fulfilled') {
        setGrants(grantsResult.value);
      }
    };

    void load();
    return () => { cancelled = true; };
  }, [prop.id]);

  const handleEnrich = async () => {
    if (enrichPending) return;
    setEnrichPending(true);
    try {
      await triggerEnrichment(prop.id);
      window.setTimeout(async () => {
        try {
          const data = await getEnrichment(prop.id);
          setEnrichment(data);
        } catch {
          setLoadError('AI analysis queued. Refresh in a moment if it does not appear.');
        }
        setEnrichPending(false);
      }, 4000);
    } catch {
      setLoadError('Failed to queue AI analysis. Check LLM configuration.');
      setEnrichPending(false);
    }
  };

  const listing = intelligence?.listing ?? prop;
  const priceHistory = intelligence?.price_history ?? [];
  const timeline = intelligence?.timeline ?? [];
  const documents = intelligence?.documents ?? [];
  const completeness = intelligence?.completeness_score ?? null;

  const quickStats = [
    listing.bedrooms != null ? { label: 'Beds', value: String(listing.bedrooms) } : null,
    listing.bathrooms != null ? { label: 'Baths', value: String(listing.bathrooms) } : null,
    listing.floor_area_sqm != null ? { label: 'm2', value: String(listing.floor_area_sqm) } : null,
    listing.ber_rating ? { label: 'BER', value: listing.ber_rating, color: berColor(listing.ber_rating) } : null,
  ].filter((s): s is { label: string; value: string; color?: string } => s !== null);

  const TABS = [
    { id: 'overview' as const, label: 'Overview' },
    { id: 'history' as const, label: 'History' },
    { id: 'evidence' as const, label: documents.length > 0 ? `Evidence (${documents.length})` : 'Evidence' },
    { id: 'ai' as const, label: 'AI' },
  ];

  return (
    <div className="flex h-full flex-col">
      <div className="flex-shrink-0 border-b border-[var(--card-border)] bg-[var(--card-bg)] p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--muted)]">
              {listing.county ?? 'Property detail'}
            </p>
            <div className="mt-0.5 text-2xl font-bold leading-tight text-[var(--accent)]">
              {formatEur(listing.price)}
            </div>
            {listing.net_price != null && (
              <p className="text-xs font-medium text-[var(--success)]">
                Net after grants: {formatEur(listing.net_price)}
              </p>
            )}
            <h2 className="mt-1 text-sm font-semibold leading-snug">{listing.title}</h2>
            <p className="text-xs text-[var(--muted)]">{listing.address}</p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="flex-shrink-0 rounded-full border border-[var(--card-border)] p-1.5 text-[var(--muted)] transition-colors hover:bg-[var(--background)]"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-4 w-4">
              <path d="M5.28 4.22a.75.75 0 0 0-1.06 1.06L6.94 8l-2.72 2.72a.75.75 0 1 0 1.06 1.06L8 9.06l2.72 2.72a.75.75 0 1 0 1.06-1.06L9.06 8l2.72-2.72a.75.75 0 0 0-1.06-1.06L8 6.94 5.28 4.22Z" />
            </svg>
          </button>
        </div>

        {completeness !== null ? (
          <div className="mt-3">
            <CompletenessBar score={completeness} />
          </div>
        ) : (
          <div className="mt-3 h-1.5 w-full rounded-full bg-[var(--card-border)]" />
        )}

        <div className="mt-3 h-36 overflow-hidden rounded-xl border border-[var(--card-border)] bg-neutral-100">
          {listing.images?.[0]?.url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={listing.images[0].url}
              alt={listing.title}
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-[var(--muted)]">
              No listing image
            </div>
          )}
        </div>

        {quickStats.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {quickStats.map((s) => (
              <span
                key={s.label}
                className="rounded-full border border-[var(--card-border)] bg-[var(--background)] px-2.5 py-0.5 text-xs font-medium"
                style={s.color ? { borderColor: s.color, color: s.color } : undefined}
              >
                {s.value} {s.label}
              </span>
            ))}
          </div>
        )}

        <div className="mt-3 flex gap-2">
          <button
            onClick={() => toggleCompareProperty(prop.id)}
            className={[
              'flex-1 rounded-full border py-1.5 text-xs font-medium transition-colors',
              inCompare
                ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]'
                : 'border-[var(--card-border)] text-[var(--foreground)] hover:bg-[var(--background)]',
            ].join(' ')}
          >
            {inCompare ? 'In compare' : '+ Compare'}
          </button>
          <a
            href={listing.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 rounded-full border border-[var(--accent)] bg-[var(--accent)] py-1.5 text-center text-xs font-medium text-white transition-colors hover:bg-[var(--accent-strong)]"
          >
            View listing
          </a>
        </div>

        {/* Brief generation */}
        <div className="mt-2">
          {!brief ? (
            <button
              type="button"
              disabled={briefLoading}
              onClick={async () => {
                setBriefLoading(true);
                try {
                  const b = await getPropertyBrief(prop.id);
                  setBrief(b);
                } finally {
                  setBriefLoading(false);
                }
              }}
              className="w-full rounded-full border border-[var(--card-border)] py-1.5 text-xs font-medium text-[var(--muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--foreground)] disabled:opacity-50"
            >
              {briefLoading ? 'Generating brief…' : 'Generate decision brief'}
            </button>
          ) : (
            <div className="rounded-2xl border border-[var(--card-border)] bg-[var(--card-bg)] p-3 text-xs">
              <div className="flex items-center justify-between">
                <p className="font-semibold">Decision Brief</p>
                <button
                  type="button"
                  onClick={() => setBrief(null)}
                  className="text-[var(--muted)] hover:text-[var(--foreground)]"
                >
                  ✕
                </button>
              </div>
              {brief.risk_flags.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {brief.risk_flags.map((flag, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-[var(--danger)]">
                      <span className="mt-0.5 flex-shrink-0">⚠</span>
                      <span className="leading-snug">{flag}</span>
                    </li>
                  ))}
                </ul>
              )}
              {brief.ai_analysis.summary && (
                <p className="mt-2 leading-relaxed text-[var(--muted)]">{brief.ai_analysis.summary}</p>
              )}
              {brief.ai_analysis.value_score != null && (
                <p className="mt-1 font-medium">
                  AI value score: <span className="text-[var(--success)]">{brief.ai_analysis.value_score.toFixed(1)}/10</span>
                </p>
              )}
              <p className="mt-2 text-[var(--muted)]">
                Data: {brief.data_sources.price_history_entries} price entries ·{' '}
                {brief.data_sources.timeline_events} timeline events ·{' '}
                {brief.data_sources.rag_documents} evidence docs
              </p>
            </div>
          )}
        </div>
      </div>

      <div className="flex-shrink-0 border-b border-[var(--card-border)] bg-[var(--card-bg)]">
        <div className="flex overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={[
                'flex-shrink-0 whitespace-nowrap border-b-2 px-4 py-2.5 text-xs font-medium transition-colors',
                activeTab === tab.id
                  ? 'border-[var(--accent)] text-[var(--accent)]'
                  : 'border-transparent text-[var(--muted)] hover:text-[var(--foreground)]',
              ].join(' ')}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {loadError && (
          <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
            {loadError}
          </div>
        )}

        {activeTab === 'overview' && (
          <div className="space-y-4">
            {listing.description && (
              <section>
                <SectionHeader title="Description" />
                <p className="text-sm leading-relaxed text-[var(--muted)]">
                  {listing.description.slice(0, 400)}
                  {(listing.description.length ?? 0) > 400 ? '...' : ''}
                </p>
              </section>
            )}

            {grants.length > 0 && (
              <section>
                <SectionHeader title={`Grant opportunities (${grants.length})`} />
                <div className="space-y-2">
                  {grants.slice(0, 4).map((match) => (
                    <div
                      key={match.id}
                      className="rounded-xl border border-[var(--card-border)] bg-[var(--background)] p-3"
                    >
                      <p className="text-xs font-semibold">{match.grant_program?.name ?? 'Grant program'}</p>
                      <p className="mt-0.5 text-xs text-[var(--muted)]">{match.reason ?? 'Eligibility under review'}</p>
                      {match.estimated_benefit != null && (
                        <p className="mt-1 text-xs font-medium text-[var(--success)]">
                          Potential: {formatEur(match.estimated_benefit)}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {intelligence ? (
              <section>
                <SectionHeader title="Data coverage" />
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { label: 'Price entries', value: intelligence.data_sources.price_history_entries },
                    { label: 'Timeline events', value: intelligence.data_sources.timeline_events },
                    { label: 'Evidence docs', value: intelligence.data_sources.rag_documents },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="rounded-xl border border-[var(--card-border)] bg-[var(--background)] px-3 py-3 text-center"
                    >
                      <div className="text-xl font-bold">{item.value}</div>
                      <div className="mt-0.5 text-[10px] text-[var(--muted)]">{item.label}</div>
                    </div>
                  ))}
                </div>
              </section>
            ) : (
              <div className="grid grid-cols-3 gap-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="skeleton h-16 rounded-xl" />
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'history' && (
          <div className="space-y-4">
            {priceHistory.length > 0 ? (
              <section>
                <SectionHeader title="Price history" />
                <div className="space-y-1.5">
                  {priceHistory.map((entry) => (
                    <div
                      key={entry.id}
                      className="flex items-center justify-between rounded-lg border border-[var(--card-border)] bg-[var(--background)] px-3 py-2"
                    >
                      <span className="text-xs text-[var(--muted)]">{formatDate(entry.recorded_at)}</span>
                      <div className="text-right">
                        <span className="text-sm font-medium">{formatEur(entry.price)}</span>
                        {entry.price_change != null && (
                          <span
                            className={[
                              'ml-2 text-xs',
                              entry.price_change < 0 ? 'text-[var(--success)]' : 'text-[var(--danger)]',
                            ].join(' ')}
                          >
                            {entry.price_change > 0 ? '+' : ''}{formatEur(entry.price_change)}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ) : (
              <p className="text-sm text-[var(--muted)]">No price history recorded yet.</p>
            )}

            {timeline.length > 0 ? (
              <section>
                <SectionHeader title="Activity timeline" />
                <div className="space-y-2">
                  {timeline.slice(0, 10).map((event) => (
                    <div
                      key={event.id}
                      className="rounded-xl border border-[var(--card-border)] bg-[var(--background)] px-3 py-2.5 text-xs"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold uppercase tracking-[0.07em]">
                          {event.event_type.replace(/_/g, ' ')}
                        </span>
                        <span className="flex-shrink-0 text-[var(--muted)]">{formatDate(event.occurred_at)}</span>
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[var(--muted)]">
                        {event.price != null && <span>{formatEur(event.price)}</span>}
                        {event.price_change != null && (
                          <span className={event.price_change < 0 ? 'text-[var(--success)]' : 'text-[var(--danger)]'}>
                            {event.price_change > 0 ? '+' : ''}{formatEur(event.price_change)}
                          </span>
                        )}
                        {event.detection_method && <span className="italic">{event.detection_method}</span>}
                        {typeof event.confidence_score === 'number' && (
                          <span>{(event.confidence_score * 100).toFixed(0)}% confidence</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ) : (
              <p className="text-sm text-[var(--muted)]">No timeline events recorded yet.</p>
            )}
          </div>
        )}

        {activeTab === 'evidence' && (
          <div className="space-y-3">
            <p className="text-xs text-[var(--muted)]">
              Evidence documents stored for this property. These ground AI answers.
            </p>
            {documents.length > 0 ? (
              documents.map((doc) => (
                <div
                  key={doc.document_key}
                  className="rounded-xl border border-[var(--card-border)] bg-[var(--background)] px-3 py-2.5"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-xs font-semibold">{doc.title ?? doc.document_type}</p>
                    <span className="flex-shrink-0 rounded-full bg-[var(--accent-soft)] px-2 py-0.5 text-[10px] font-medium text-[var(--accent)]">
                      {doc.document_type.replace(/_/g, ' ')}
                    </span>
                  </div>
                  {doc.effective_at && (
                    <p className="mt-0.5 text-[10px] text-[var(--muted)]">
                      Effective {formatDate(doc.effective_at)}
                    </p>
                  )}
                </div>
              ))
            ) : (
              <div className="rounded-xl border border-dashed border-[var(--card-border)] px-4 py-6 text-center">
                <p className="text-sm text-[var(--muted)]">No evidence documents yet.</p>
                <p className="mt-1 text-xs text-[var(--muted)]">
                  Documents are built after AI enrichment or pipeline runs.
                </p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'ai' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold">AI analysis</p>
                <p className="text-[10px] text-[var(--muted)]">Generated on demand via enrichment queue.</p>
              </div>
              {!enrichment && (
                <button
                  onClick={handleEnrich}
                  disabled={enrichPending}
                  className="rounded-full border border-[var(--accent)] bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-strong)] disabled:opacity-50"
                >
                  {enrichPending ? 'Analyzing...' : 'Run AI analysis'}
                </button>
              )}
            </div>

            {enrichment ? (
              <div className="space-y-4">
                <p className="text-sm leading-relaxed text-[var(--muted)]">{enrichment.summary}</p>

                {enrichment.value_score != null && (
                  <div>
                    <div className="mb-1 flex items-center justify-between text-xs">
                      <span className="font-medium">Value score</span>
                      <span className="font-bold text-[var(--accent)]">{enrichment.value_score}/10</span>
                    </div>
                    <div className="h-2 rounded-full bg-[var(--card-border)]">
                      <div
                        className="h-2 rounded-full bg-[var(--accent)]"
                        style={{ width: `${enrichment.value_score * 10}%` }}
                      />
                    </div>
                  </div>
                )}

                {Array.isArray(enrichment.pros) && enrichment.pros.length > 0 && (
                  <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-3">
                    <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--success)]">Positives</p>
                    <ul className="space-y-1 text-xs text-[var(--muted)]">
                      {enrichment.pros.map((pro, i) => <li key={i}>+ {pro}</li>)}
                    </ul>
                  </div>
                )}

                {Array.isArray(enrichment.cons) && enrichment.cons.length > 0 && (
                  <div className="rounded-xl border border-red-100 bg-red-50 p-3">
                    <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--danger)]">Considerations</p>
                    <ul className="space-y-1 text-xs text-[var(--muted)]">
                      {enrichment.cons.map((con, i) => <li key={i}>- {con}</li>)}
                    </ul>
                  </div>
                )}

                {enrichment.neighbourhood_notes && (
                  <div>
                    <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">Neighbourhood</p>
                    <p className="text-xs leading-relaxed text-[var(--muted)]">{enrichment.neighbourhood_notes}</p>
                  </div>
                )}
              </div>
            ) : enrichPending ? (
              <div className="space-y-2">
                <div className="skeleton h-4 w-full rounded" />
                <div className="skeleton h-4 w-5/6 rounded" />
                <div className="skeleton h-4 w-4/6 rounded" />
              </div>
            ) : (
              <p className="text-sm text-[var(--muted)]">
                Run AI analysis to get a value score, pros/cons, and neighbourhood notes.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
