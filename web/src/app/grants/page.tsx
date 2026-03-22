'use client';

import { useEffect, useMemo, useState } from 'react';
import { getGrants, type GrantProgram } from '@/lib/api';
import { LoadingCardGrid, LoadingRows } from '@/components/LoadingState';

const COUNTRY_OPTIONS = ['IE', 'NI', 'UK'];
const GRANTS_PAGE_SIZE = 8;

export default function GrantsPage() {
  const [country, setCountry] = useState<string>('IE');
  const [activeOnly, setActiveOnly] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [grants, setGrants] = useState<GrantProgram[]>([]);
  const [page, setPage] = useState(1);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getGrants(country, activeOnly);
        setGrants(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to fetch grants');
      } finally {
        setLoading(false);
      }
    };

    load().catch(console.error);
  }, [country, activeOnly]);

  useEffect(() => {
    setPage(1);
  }, [country, activeOnly]);

  const totalPotentialValue = useMemo(() => {
    return grants.reduce((sum, grant) => sum + (grant.max_amount ?? 0), 0);
  }, [grants]);

  const totalPages = Math.max(1, Math.ceil(grants.length / GRANTS_PAGE_SIZE));
  const pagedGrants = useMemo(() => {
    const start = (page - 1) * GRANTS_PAGE_SIZE;
    return grants.slice(start, start + GRANTS_PAGE_SIZE);
  }, [grants, page]);

  useEffect(() => {
    setPage((prev) => Math.min(prev, totalPages));
  }, [totalPages]);

  return (
    <div className="page-shell page-shell-regular rise-in">
      <div className="flex flex-wrap gap-3 items-center justify-between mb-6">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">Incentive Intelligence</p>
          <h1 className="text-2xl font-bold">Grants and buyer advantage</h1>
        </div>

        <div className="flex gap-2 items-center">
          <select
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className="ui-select"
          >
            {COUNTRY_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>

          <label className="text-sm flex items-center gap-2">
            <input
              type="checkbox"
              checked={activeOnly}
              onChange={(e) => setActiveOnly(e.target.checked)}
              className="h-4 w-4 accent-[var(--accent)]"
            />
            Active only
          </label>
        </div>
      </div>

      <div className="rounded-lg border border-[var(--card-border)] ai-glass p-4 mb-6 text-sm">
        Atlas tip: combine this grant view with Decision Studio to reveal true net acquisition cost after incentive eligibility.
      </div>

      <div className="mb-6">
        {loading ? (
          <LoadingCardGrid cards={3} />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
              <p className="text-sm text-[var(--muted)]">Programs</p>
              <p className="text-2xl font-semibold mt-2">{grants.length}</p>
            </div>
            <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
              <p className="text-sm text-[var(--muted)]">Country</p>
              <p className="text-2xl font-semibold mt-2">{country}</p>
            </div>
            <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
              <p className="text-sm text-[var(--muted)]">Total Max Support</p>
              <p className="text-2xl font-semibold mt-2">{new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(totalPotentialValue)}</p>
            </div>
          </div>
        )}
      </div>

      {loading && <LoadingRows rows={5} />}
      {error ? (
        <p className="mb-4 rounded-lg border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-3 py-2 text-sm text-[var(--danger)]">
          {error}
        </p>
      ) : null}

      {!loading && !error && (
        <div className="space-y-4">
          {pagedGrants.map((grant) => (
            <article
              key={grant.id}
              className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
                <h2 className="text-lg font-semibold">{grant.name}</h2>
                <span className="text-xs px-2 py-1 rounded border border-[var(--accent)]/30 bg-[var(--accent-soft)] text-[var(--accent-strong)]">
                  {grant.code}
                </span>
              </div>

              <p className="text-sm text-[var(--muted)] mb-3">
                {(grant.authority || 'Authority not specified')} {grant.region ? `- ${grant.region}` : ''}
              </p>

              {grant.description && (
                <p className="text-sm leading-relaxed mb-3">{grant.description}</p>
              )}

              <div className="flex flex-wrap gap-4 text-sm">
                <span>
                  Benefit: {grant.benefit_type || 'Not specified'}
                </span>
                <span>
                  Max: {grant.max_amount != null
                    ? new Intl.NumberFormat('en-IE', {
                        style: 'currency',
                        currency: grant.currency || 'EUR',
                        maximumFractionDigits: 0,
                      }).format(grant.max_amount)
                    : 'Not specified'}
                </span>
                <span className={grant.active ? 'text-[var(--success)]' : 'text-[var(--danger)]'}>
                  Status: {grant.active ? 'Active' : 'Inactive'}
                </span>
                {grant.source_url && (
                  <a
                    href={grant.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="ui-btn ui-btn-soft text-xs"
                  >
                    Official source
                  </a>
                )}
              </div>
            </article>
          ))}

          {!grants.length && (
            <p className="text-[var(--muted)]">No grants found for the selected filters.</p>
          )}

          {grants.length > 0 && totalPages > 1 ? (
            <div className="mt-5 flex items-center justify-between gap-3 border-t border-[var(--card-border)] pt-4">
              <button
                type="button"
                onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                disabled={page <= 1}
                className="ui-btn ui-btn-secondary disabled:opacity-50"
              >
                Previous
              </button>
              <p className="text-sm text-[var(--muted)]">
                Page {page} of {totalPages}
              </p>
              <button
                type="button"
                onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                disabled={page >= totalPages}
                className="ui-btn ui-btn-secondary disabled:opacity-50"
              >
                Next
              </button>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
