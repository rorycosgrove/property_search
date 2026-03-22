'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { getDiscoveryFeed, type DiscoverySignal, type SignalType } from '@/lib/api';

// ── Signal meta ──────────────────────────────────────────────────────────────

const SIGNAL_META: Record<SignalType, { label: string; color: string; icon: string }> = {
  price_drop: {
    label: 'Price drop',
    color: 'var(--danger)',
    icon: 'M3 4h2l2 8h8l2-8h2M9 18a1 1 0 1 0 2 0 1 1 0 0 0-2 0m4 0a1 1 0 1 0 2 0 1 1 0 0 0-2 0',
  },
  high_value: {
    label: 'Strong value',
    color: 'var(--success)',
    icon: 'M5 3l14 9-14 9V3z',
  },
  stale: {
    label: 'Stale listing',
    color: 'var(--signal)',
    icon: 'M12 8v4l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0z',
  },
  new_listing: {
    label: 'New listing',
    color: 'var(--accent)',
    icon: 'M12 4v16m8-8H4',
  },
};

const SEVERITY_RING: Record<string, string> = {
  high:   'border-l-[var(--danger)]',
  medium: 'border-l-[var(--signal)]',
  low:    'border-l-[var(--muted)]',
};

// ── Card ─────────────────────────────────────────────────────────────────────

function SignalCard({ signal, onSelect }: { signal: DiscoverySignal; onSelect?: (id: string) => void }) {
  const meta = SIGNAL_META[signal.signal_type] ?? SIGNAL_META.new_listing;
  const ring = SEVERITY_RING[signal.severity] ?? SEVERITY_RING.medium;

  return (
    <article
      className={`flex gap-3 rounded-2xl border border-[var(--card-border)] border-l-[3px] ${ring} bg-[var(--card-bg)] p-4 shadow-[0_4px_16px_rgba(27,36,48,0.05)] transition-shadow hover:shadow-[0_8px_24px_rgba(27,36,48,0.09)]`}
    >
      {/* Signal icon */}
      <div
        className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl"
        style={{ background: `${meta.color}18` }}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.8}
          className="h-4 w-4"
          style={{ color: meta.color }}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d={meta.icon} />
        </svg>
      </div>

      <div className="min-w-0 flex-1">
        {/* Type eyebrow */}
        <div className="flex items-center gap-2">
          <span
            className="text-[9px] font-bold uppercase tracking-[0.18em]"
            style={{ color: meta.color }}
          >
            {meta.label}
          </span>
          {signal.county && (
            <span className="text-[9px] text-[var(--muted)]">{signal.county}</span>
          )}
        </div>

        {/* Headline */}
        <p className="mt-0.5 text-sm font-semibold leading-snug">{signal.headline}</p>

        {/* Address */}
        <p className="mt-0.5 truncate text-xs text-[var(--muted)]">{signal.address}</p>

        {/* Detail */}
        <p className="mt-1 text-xs leading-5 text-[var(--muted)]">{signal.detail}</p>

        {/* Actions */}
        <div className="mt-2 flex items-center gap-3">
          {onSelect && (
            <button
              type="button"
              onClick={() => onSelect(signal.property_id)}
              className="text-xs font-medium text-[var(--accent)] hover:underline"
            >
              View detail
            </button>
          )}
          <a
            href={signal.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-[var(--muted)] hover:text-[var(--foreground)]"
          >
            Source ↗
          </a>
        </div>
      </div>

      {/* Price chip */}
      {signal.price != null && (
        <div className="flex-shrink-0 text-right">
          <span className="text-sm font-semibold">
            €{signal.price.toLocaleString('en-IE')}
          </span>
        </div>
      )}
    </article>
  );
}

// ── Filter tabs ───────────────────────────────────────────────────────────────

const FILTER_OPTIONS: { key: SignalType | 'all'; label: string }[] = [
  { key: 'all', label: 'All signals' },
  { key: 'price_drop', label: 'Price drops' },
  { key: 'high_value', label: 'High value' },
  { key: 'new_listing', label: 'New listings' },
  { key: 'stale', label: 'Stale' },
];

// ── Main component ────────────────────────────────────────────────────────────

interface DiscoveryFeedProps {
  /** Called when user clicks "View detail" on a card — passes property_id */
  onSelectProperty?: (id: string) => void;
  /** How many cards to load */
  limit?: number;
  /** Show compact (no heading, no filter bar) */
  compact?: boolean;
}

export default function DiscoveryFeed({ onSelectProperty, limit = 16, compact = false }: DiscoveryFeedProps) {
  const [signals, setSignals] = useState<DiscoverySignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<SignalType | 'all'>('all');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getDiscoveryFeed(limit)
      .then((data) => {
        if (!cancelled) setSignals(data);
      })
      .catch(() => {
        if (!cancelled) setError('Could not load signals.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [limit]);

  const filtered = activeFilter === 'all' ? signals : signals.filter((s) => s.signal_type === activeFilter);

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: compact ? 3 : 6 }).map((_, i) => (
          <div key={i} className="h-[88px] animate-pulse rounded-2xl bg-[var(--card-bg)] border border-[var(--card-border)]" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-[var(--card-border)] bg-[var(--card-bg)] p-6 text-center text-sm text-[var(--muted)]">
        {error}
      </div>
    );
  }

  if (signals.length === 0) {
    return (
      <div className="rounded-2xl border border-[var(--card-border)] bg-[var(--card-bg)] p-8 text-center">
        <p className="text-sm text-[var(--muted)]">No signals detected right now. Check back as the dataset updates.</p>
      </div>
    );
  }

  return (
    <div>
      {!compact && (
        <>
          <div className="flex items-baseline justify-between">
            <div>
              <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--muted)]">Discovery</p>
              <h2 className="mt-1 text-xl">Signals from your dataset</h2>
            </div>
            <Link
              href="/search"
              className="text-xs text-[var(--accent)] hover:underline"
            >
              Browse all →
            </Link>
          </div>

          {/* Filter tabs */}
          <div className="mt-4 flex flex-wrap gap-1.5">
            {FILTER_OPTIONS.map((opt) => {
              const count = opt.key === 'all' ? signals.length : signals.filter((s) => s.signal_type === opt.key).length;
              if (count === 0 && opt.key !== 'all') return null;
              return (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => setActiveFilter(opt.key)}
                  className={`rounded-full px-3 py-1 text-[11px] font-medium transition-colors ${
                    activeFilter === opt.key
                      ? 'bg-[var(--accent)] text-white'
                      : 'border border-[var(--card-border)] bg-[var(--card-bg)] text-[var(--muted)] hover:border-[var(--accent)]'
                  }`}
                >
                  {opt.label}
                  <span className="ml-1 opacity-60">{count}</span>
                </button>
              );
            })}
          </div>
        </>
      )}

      {/* Cards */}
      <div className={`${compact ? '' : 'mt-4'} space-y-2`}>
        {filtered.map((signal) => (
          <SignalCard
            key={`${signal.signal_type}:${signal.property_id}`}
            signal={signal}
            onSelect={onSelectProperty}
          />
        ))}
      </div>
    </div>
  );
}
