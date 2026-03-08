'use client';

import { useEffect, useState } from 'react';
import { getSources, getAdapters, triggerScrape, type AdapterInfo, type Source } from '@/lib/api';
import { formatDate } from '@/lib/utils';

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [adapters, setAdapters] = useState<AdapterInfo[]>([]);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    getSources().then(setSources).catch(console.error);
    getAdapters().then(setAdapters).catch(console.error);
  }, []);

  const handleTrigger = async (id: string) => {
    const response = await triggerScrape(id);
    setToast(response.status === 'processed_inline'
      ? 'Source processed inline (local mode).'
      : 'Scrape dispatched to queue.');
    window.setTimeout(() => setToast(null), 2500);
  };

  return (
    <div className="p-6 max-w-5xl mx-auto rise-in">
      <div className="mb-6">
        <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">Data Operations</p>
        <h1 className="text-2xl font-bold">Source readiness and ingestion control</h1>
      </div>

      {toast ? (
        <div className="mb-4 rounded-lg border border-[var(--accent)]/30 bg-cyan-900/10 px-3 py-2 text-sm text-[var(--foreground)]">
          {toast}
        </div>
      ) : null}

      {/* Active sources */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Configured Sources</h2>
        <div className="space-y-3">
          {sources.map((source) => (
            <div
              key={source.id}
              className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4 flex items-center justify-between"
            >
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-medium">{source.name}</h3>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    source.enabled ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'
                  }`}>
                    {source.enabled ? 'Active' : 'Disabled'}
                  </span>
                  <span className="text-xs text-[var(--muted)] bg-[var(--background)] px-1.5 py-0.5 rounded">
                    {source.adapter_name}
                  </span>
                </div>
                <p className="text-xs text-[var(--muted)]">
                  Last polled: {formatDate(source.last_polled_at) || 'Never'} ·
                  Listings: {source.total_listings ?? 0}
                  {source.error_count > 0 && (
                    <span className="text-red-400 ml-1">
                      ({source.error_count} errors)
                    </span>
                  )}
                </p>
              </div>
              <button
                onClick={() => handleTrigger(source.id)}
                className="text-sm px-3 py-1.5 bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)] rounded transition-colors"
              >
                Scrape Now
              </button>
            </div>
          ))}

          {sources.length === 0 && (
            <p className="text-[var(--muted)] text-sm">No sources configured yet.</p>
          )}
        </div>
      </div>

      {/* Available adapters */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Available Adapters</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {adapters.map((adapter) => (
            <div
              key={adapter.name}
              className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4"
            >
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-medium">{adapter.name}</h3>
                <span className="text-xs text-[var(--muted)] bg-[var(--background)] px-1.5 py-0.5 rounded">
                  {adapter.adapter_type}
                </span>
              </div>
              <p className="text-sm text-[var(--muted)]">{adapter.description}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
