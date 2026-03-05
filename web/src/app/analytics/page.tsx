'use client';

import { useEffect, useState } from 'react';
import {
  getAnalyticsSummary,
  getCountyStats,
  getPriceTrends,
  getTypeDistribution,
  getBERDistribution,
  type AnalyticsSummary,
} from '@/lib/api';
import { formatEur, COUNTIES } from '@/lib/utils';

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [countyStats, setCountyStats] = useState<any[]>([]);
  const [priceTrends, setPriceTrends] = useState<any[]>([]);
  const [typeDistribution, setTypeDistribution] = useState<any[]>([]);
  const [berDistribution, setBERDistribution] = useState<any[]>([]);
  const [selectedCounty, setSelectedCounty] = useState<string>('');

  useEffect(() => {
    getAnalyticsSummary().then(setSummary).catch(console.error);
    getCountyStats().then(setCountyStats).catch(console.error);
    getPriceTrends(selectedCounty || undefined).then(setPriceTrends).catch(console.error);
    getTypeDistribution(selectedCounty || undefined).then(setTypeDistribution).catch(console.error);
    getBERDistribution(selectedCounty || undefined).then(setBERDistribution).catch(console.error);
  }, [selectedCounty]);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Market Analytics</h1>
        <select
          value={selectedCounty}
          onChange={(e) => setSelectedCounty(e.target.value)}
          className="bg-[var(--background)] border border-[var(--card-border)] rounded px-3 py-1.5 text-sm"
        >
          <option value="">All of Ireland</option>
          {COUNTIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
          <StatCard label="Active Listings" value={summary.total_active_listings.toLocaleString()} />
          <StatCard label="New (24h)" value={summary.new_listings_24h.toLocaleString()} />
          <StatCard label="Average Price" value={formatEur(summary.avg_price)} />
          <StatCard label="Median Price" value={formatEur(summary.median_price)} />
          <StatCard label="Price Changes (24h)" value={summary.price_changes_24h.toLocaleString()} />
          <StatCard label="Sold Records" value={summary.total_sold_ppr.toLocaleString()} />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* County stats table */}
        <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-3">County Price Stats</h2>
          <div className="overflow-y-auto max-h-[400px]">
            <table className="w-full text-sm">
              <thead className="text-[var(--muted)] border-b border-[var(--card-border)]">
                <tr>
                  <th className="text-left py-2">County</th>
                  <th className="text-right py-2">Listings</th>
                  <th className="text-right py-2">Avg Price</th>
                  <th className="text-right py-2">Median</th>
                </tr>
              </thead>
              <tbody>
                {countyStats.map((s: any) => (
                  <tr key={s.county} className="border-b border-[var(--card-border)] hover:bg-[var(--background)]">
                    <td className="py-2">{s.county}</td>
                    <td className="text-right">{s.listing_count}</td>
                    <td className="text-right">{formatEur(s.avg_price)}</td>
                    <td className="text-right">{formatEur(s.median_price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Price trends */}
        <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-3">Price Trends (Sold)</h2>
          {priceTrends.length > 0 ? (
            <div className="space-y-2">
              {priceTrends.map((t: any) => (
                <div key={t.period} className="flex justify-between text-sm">
                  <span className="text-[var(--muted)]">{t.period}</span>
                  <span>{formatEur(t.avg_price)} ({t.sale_count} sales)</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-[var(--muted)] text-sm">No trend data available</p>
          )}
        </div>

        {/* Property type distribution */}
        <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-3">Property Types</h2>
          <div className="space-y-2">
            {typeDistribution.map((d: any) => (
              <div key={d.property_type} className="flex items-center gap-2">
                <span className="text-sm w-24 capitalize">{d.property_type}</span>
                <div className="flex-1 bg-[var(--card-border)] rounded-full h-4">
                  <div
                    className="bg-brand-500 h-4 rounded-full text-[10px] leading-4 text-center text-white"
                    style={{ width: `${d.percentage}%` }}
                  >
                    {d.percentage > 10 ? `${d.percentage}%` : ''}
                  </div>
                </div>
                <span className="text-xs text-[var(--muted)] w-12 text-right">{d.count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* BER distribution */}
        <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-3">BER Ratings</h2>
          <div className="space-y-1">
            {berDistribution.map((d: any) => (
              <div key={d.ber_rating} className="flex items-center gap-2">
                <span className="text-sm w-8 font-bold">{d.ber_rating}</span>
                <div className="flex-1 bg-[var(--card-border)] rounded-full h-3">
                  <div
                    className="h-3 rounded-full"
                    style={{
                      width: `${d.percentage}%`,
                      backgroundColor: d.ber_rating?.startsWith('A') ? '#00A651'
                        : d.ber_rating?.startsWith('B') ? '#8CC63F'
                        : d.ber_rating?.startsWith('C') ? '#FFF200'
                        : d.ber_rating?.startsWith('D') ? '#F7941D'
                        : '#ED1C24',
                    }}
                  />
                </div>
                <span className="text-xs text-[var(--muted)] w-16 text-right">
                  {d.count} ({d.percentage}%)
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
      <div className="text-xs text-[var(--muted)] mb-1">{label}</div>
      <div className="text-lg font-bold">{value}</div>
    </div>
  );
}
