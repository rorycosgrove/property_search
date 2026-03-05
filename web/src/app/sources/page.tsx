'use client';

import { useEffect, useState } from 'react';
import { getSources, getAdapters, triggerScrape, type Source } from '@/lib/api';
import { formatDate } from '@/lib/utils';

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [adapters, setAdapters] = useState<any[]>([]);

  useEffect(() => {
    getSources().then(setSources).catch(console.error);
    getAdapters().then(setAdapters).catch(console.error);
  }, []);

  const handleTrigger = async (id: string) => {
    await triggerScrape(id);
    alert('Scrape triggered');
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Data Sources</h1>

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
                className="text-sm px-3 py-1.5 bg-brand-600 hover:bg-brand-700 rounded transition-colors"
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
          {adapters.map((adapter: any) => (
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
