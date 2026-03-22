'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  type BERDistribution,
  getAnalyticsSummary,
  getBERDistribution,
  getBestValueProperties,
  getCountyStats,
  getPriceTrends,
  getPriceTrendsByType,
  getPriceChangesByBudget,
  getPriceChangesTimeline,
  getTypeDistribution,
  type AnalyticsSummary,
  type BestValueProperty,
  type CountyStat,
  type PriceTrend,
  type PriceChange,
  type PriceChangesTimeline,
  type PropertyTypeDistribution,
} from '@/lib/api';
import { formatEur, COUNTIES } from '@/lib/utils';
import { LoadingBlock, LoadingRows } from '@/components/LoadingState';

type AnalyticsTab = 'overview' | 'changes' | 'value';

const DEFAULT_MAX_BUDGET = (() => {
  const parsed = Number(process.env.NEXT_PUBLIC_DEFAULT_MAX_BUDGET ?? '100000');
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 100000;
})();

export default function AnalyticsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [countyStats, setCountyStats] = useState<CountyStat[]>([]);
  const [priceTrends, setPriceTrends] = useState<PriceTrend[]>([]);
  const [typeDistribution, setTypeDistribution] = useState<PropertyTypeDistribution[]>([]);
  const [berDistribution, setBERDistribution] = useState<BERDistribution[]>([]);
  const [bestValueProperties, setBestValueProperties] = useState<BestValueProperty[]>([]);
  const [priceTrendsByType, setPriceTrendsByType] = useState<Record<string, PriceTrend[]>>({});
  const [priceChanges, setPriceChanges] = useState<PriceChange[]>([]);
  const [priceChangesTimeline, setPriceChangesTimeline] = useState<PriceChangesTimeline>({increases: [], decreases: []});
  const [selectedCounty, setSelectedCounty] = useState<string>('');
  const [selectedPropertyType, setSelectedPropertyType] = useState<string>('');
  const [maxBudget, setMaxBudget] = useState<number | undefined>(DEFAULT_MAX_BUDGET);
  const [budgetInput, setBudgetInput] = useState<string>(String(DEFAULT_MAX_BUDGET));
  const [activeTab, setActiveTab] = useState<AnalyticsTab>('overview');
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const setActiveTabWithUrl = (tab: AnalyticsTab) => {
    setActiveTab(tab);
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', tab);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  };

  useEffect(() => {
    const tab = searchParams.get('tab');
    if (tab === 'overview' || tab === 'changes' || tab === 'value') {
      setActiveTab(tab);
    }
  }, [searchParams]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setIsLoading(true);
      setLoadError(null);

      const results = await Promise.allSettled([
        getAnalyticsSummary(),
        getCountyStats(),
        getPriceTrends(selectedCounty || undefined),
        getTypeDistribution(selectedCounty || undefined),
        getBERDistribution(selectedCounty || undefined),
        getBestValueProperties(selectedCounty || undefined, selectedPropertyType || undefined, maxBudget),
        getPriceTrendsByType(selectedCounty || undefined),
        getPriceChangesByBudget(maxBudget, selectedCounty || undefined),
        getPriceChangesTimeline(maxBudget, selectedCounty || undefined),
      ]);

      if (cancelled) {
        return;
      }

      const errors: string[] = [];

      if (results[0].status === 'fulfilled') setSummary(results[0].value);
      else errors.push('summary');

      if (results[1].status === 'fulfilled') setCountyStats(results[1].value);
      else errors.push('county stats');

      if (results[2].status === 'fulfilled') setPriceTrends(results[2].value);
      else errors.push('price trends');

      if (results[3].status === 'fulfilled') setTypeDistribution(results[3].value);
      else errors.push('type distribution');

      if (results[4].status === 'fulfilled') setBERDistribution(results[4].value);
      else errors.push('BER distribution');

      if (results[5].status === 'fulfilled') setBestValueProperties(results[5].value);
      else errors.push('best value');

      if (results[6].status === 'fulfilled') setPriceTrendsByType(results[6].value);
      else errors.push('type trends');

      if (results[7].status === 'fulfilled') setPriceChanges(results[7].value);
      else errors.push('price changes');

      if (results[8].status === 'fulfilled') setPriceChangesTimeline(results[8].value);
      else errors.push('price change timeline');

      if (errors.length > 0) {
        setLoadError(`Some analytics sections failed to load: ${errors.join(', ')}`);
      }

      setIsLoading(false);
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [selectedCounty, selectedPropertyType, maxBudget]);

  const renderOverviewLoading = () => (
    <>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
            <LoadingBlock className="h-3 w-20" />
            <LoadingBlock className="mt-2 h-7 w-16" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
            <LoadingBlock className="mb-3 h-5 w-36" />
            <LoadingRows rows={5} />
          </div>
        ))}
      </div>
    </>
  );

  const renderChangesLoading = () => (
    <div className="mt-8 mb-8">
      <LoadingBlock className="h-7 w-56 mb-4" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
          <LoadingBlock className="mb-3 h-5 w-32" />
          <LoadingRows rows={4} />
        </div>
        <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
          <LoadingBlock className="mb-3 h-5 w-32" />
          <LoadingRows rows={4} />
        </div>
      </div>
      <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
        <LoadingBlock className="mb-3 h-5 w-48" />
        <LoadingRows rows={6} />
      </div>
    </div>
  );

  const renderValueLoading = () => (
    <div className="mt-8">
      <LoadingBlock className="h-7 w-64 mb-4" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
            <LoadingBlock className="h-4 w-3/4" />
            <LoadingBlock className="mt-2 h-3 w-1/2" />
            <LoadingBlock className="mt-4 h-3 w-full" />
            <LoadingBlock className="mt-2 h-3 w-5/6" />
            <LoadingBlock className="mt-2 h-3 w-2/3" />
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="page-shell page-shell-wide rise-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">Market Intelligence</p>
          <h1 className="text-2xl font-bold">AI-guided market pulse</h1>
        </div>
        <div className="flex gap-2">
          <input
            type="number"
            placeholder="Max budget (€)"
            value={budgetInput}
            onChange={(e) => {
              setBudgetInput(e.target.value);
              const val = e.target.value ? parseFloat(e.target.value) : undefined;
              setMaxBudget(val);
            }}
            className="ui-input w-32"
          />
          <select
            value={selectedCounty}
            onChange={(e) => setSelectedCounty(e.target.value)}
            className="ui-select"
          >
            <option value="">All of Ireland</option>
            {COUNTIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <select
            value={selectedPropertyType}
            onChange={(e) => setSelectedPropertyType(e.target.value)}
            className="ui-select"
          >
            <option value="">All Types</option>
            {typeDistribution.map((d) => (
              <option key={d.property_type} value={d.property_type}>{d.property_type}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="rounded-lg border border-[var(--card-border)] ai-glass p-4 mb-6">
        <p className="text-sm">Atlas Insight: use this panel to identify pricing pressure, inventory mix, and BER opportunity before running compare analysis in the workspace. Drilldown by county and property type to see value ranking and market trends.</p>
      </div>

      {loadError ? (
        <div className="mb-6 rounded-lg border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-3 py-2 text-sm text-[var(--danger)]">
          {loadError}
        </div>
      ) : null}

       <div className="text-xs text-[var(--muted)] space-y-1 mb-6">
         <p>
            <strong className="text-[var(--foreground)]">Quick Links:</strong>{' '}
            <a href="/workspace" className="text-[var(--accent-strong)] hover:underline">Compare Analysis</a>
           {' • '}
            <a href="#value" onClick={(e) => { e.preventDefault(); setActiveTabWithUrl('value'); }} className="text-[var(--accent-strong)] hover:underline">Best Value</a>
           {' • '}
            <a href="#changes" onClick={(e) => { e.preventDefault(); setActiveTabWithUrl('changes'); }} className="text-[var(--accent-strong)] hover:underline">Price Changes</a>
           {' • '}
            <a href="#overview" onClick={(e) => { e.preventDefault(); setActiveTabWithUrl('overview'); }} className="text-[var(--accent-strong)] hover:underline">Market Overview</a>
         </p>
       </div>
       {/* Tab navigation */}
        <div className="mb-6 flex gap-2 rounded-lg border border-[var(--card-border)] bg-[var(--card-bg)] p-1">
         <button
            onClick={() => setActiveTabWithUrl('overview')}
            className={`ui-btn ${
             activeTab === 'overview'
              ? 'ui-btn-soft font-medium'
              : 'ui-btn-secondary text-[var(--muted)]'
           }`}
         >
           Market Overview
         </button>
         <button
            onClick={() => setActiveTabWithUrl('changes')}
            className={`ui-btn ${
             activeTab === 'changes'
              ? 'ui-btn-soft font-medium'
              : 'ui-btn-secondary text-[var(--muted)]'
           }`}
         >
          Price Changes {maxBudget && <span className="text-xs text-[var(--muted)]"> (max {formatEur(maxBudget)})</span>}
         </button>
         <button
            onClick={() => setActiveTabWithUrl('value')}
            className={`ui-btn ${
             activeTab === 'value'
              ? 'ui-btn-soft font-medium'
              : 'ui-btn-secondary text-[var(--muted)]'
           }`}
         >
          Best Value {maxBudget && <span className="text-xs text-[var(--muted)]"> (max {formatEur(maxBudget)})</span>}
         </button>
       </div>

      {activeTab === 'overview' && (
      isLoading ? renderOverviewLoading() : (
      <>
      {/* Summary cards */}
      {summary && (
        <div id="overview" className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
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
                {countyStats.map((s) => (
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
              {priceTrends.map((t) => (
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
            {typeDistribution.map((d) => (
              <div key={d.property_type} className="flex items-center gap-2">
                <span className="text-sm w-24 capitalize">{d.property_type}</span>
                <div className="flex-1 bg-[var(--card-border)] rounded-full h-4">
                  <div
                    className="bg-[var(--accent)] h-4 rounded-full text-[10px] leading-4 text-center text-white"
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
            {berDistribution.map((d) => (
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
      </>
      )
      )}

      {/* Price changes timeline and drilldown */}
      {activeTab === 'changes' && (
      isLoading ? renderChangesLoading() : (
      <div id="changes" className="mt-8 mb-8">
        <h2 className="text-xl font-semibold mb-4">Price Changes Timeline {maxBudget && <span className="text-sm font-normal text-[var(--muted)]">(up to {formatEur(maxBudget)})</span>}</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Price changes by activity */}
          <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
            <h3 className="font-semibold mb-3">Price Increases</h3>
            {priceChangesTimeline.increases.length > 0 ? (
              <div className="space-y-2">
                {priceChangesTimeline.increases.map((p) => (
                  <div key={p.date} className="flex justify-between items-center text-sm p-2 bg-[var(--background)] rounded">
                    <div>
                      <span className="text-[var(--muted)]">{p.date}</span>
                      <span className="ml-2">{p.count} properties</span>
                    </div>
                    <span className="text-[var(--danger)]">
                      +{formatEur(p.avg_change)} ({p.avg_change_pct > 0 ? '+' : ''}{p.avg_change_pct}%)
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[var(--muted)] text-sm">No price increases</p>
            )}
          </div>

          <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
            <h3 className="font-semibold mb-3">Price Decreases</h3>
            {priceChangesTimeline.decreases.length > 0 ? (
              <div className="space-y-2">
                {priceChangesTimeline.decreases.map((p) => (
                  <div key={p.date} className="flex justify-between items-center text-sm p-2 bg-[var(--background)] rounded">
                    <div>
                      <span className="text-[var(--muted)]">{p.date}</span>
                      <span className="ml-2">{p.count} properties</span>
                    </div>
                    <span className="text-[var(--success)]">
                      {formatEur(p.avg_change)} ({p.avg_change_pct}%)
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[var(--muted)] text-sm">No price decreases</p>
            )}
          </div>
        </div>

        {/* Recent price changes drilldown */}
        <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
          <h3 className="font-semibold mb-3">Recent Price Changes (Drilldown)</h3>
          {priceChanges.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="text-[var(--muted)] border-b border-[var(--card-border)]">
                  <tr>
                    <th className="text-left py-2 px-2">Property</th>
                    <th className="text-right py-2 px-2">Price</th>
                    <th className="text-right py-2 px-2">Change</th>
                    <th className="text-right py-2 px-2">%</th>
                    <th className="text-right py-2 px-2">Beds/Baths</th>
                    <th className="text-right py-2 px-2">Type</th>
                    <th className="text-right py-2 px-2">County</th>
                    <th className="text-right py-2 px-2">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {priceChanges.slice(0, 20).map((change) => (
                    <tr key={`${change.property_id}-${change.recorded_at}`} className="border-b border-[var(--card-border)] hover:bg-[var(--background)]">
                      <td className="py-2 px-2 font-medium">
                        {change.url ? (
                          <a href={change.url} target="_blank" rel="noopener noreferrer" className="text-[var(--accent-strong)] hover:underline">
                            {change.title}
                          </a>
                        ) : (
                          change.title
                        )}
                      </td>
                      <td className="text-right py-2 px-2">{formatEur(change.current_price)}</td>
                      <td className={`text-right py-2 px-2 ${change.price_change != null && change.price_change > 0 ? 'text-[var(--danger)]' : 'text-[var(--success)]'}`}>
                        {change.price_change != null ? `${change.price_change > 0 ? '+' : ''}${formatEur(change.price_change)}` : '-'}
                      </td>
                      <td className={`text-right py-2 px-2 ${change.price_change_pct && change.price_change_pct > 0 ? 'text-[var(--danger)]' : 'text-[var(--success)]'}`}>
                        {change.price_change_pct ? `${change.price_change_pct > 0 ? '+' : ''}${change.price_change_pct.toFixed(2)}%` : '-'}
                      </td>
                      <td className="text-right py-2 px-2">
                        {change.bedrooms || '-'} / {change.bathrooms || '-'}
                      </td>
                      <td className="text-right py-2 px-2 capitalize">{change.property_type || '-'}</td>
                      <td className="text-right py-2 px-2">{change.county}</td>
                      <td className="text-right py-2 px-2 text-[var(--muted)]">
                        {new Date(change.recorded_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {priceChanges.length > 20 && (
                <p className="text-xs text-[var(--muted)] mt-2">Showing 20 of {priceChanges.length} recent price changes</p>
              )}
            </div>
          ) : (
            <p className="text-[var(--muted)] text-sm">No price changes in the selected period</p>
          )}
        </div>
      </div>
      )
      )}

      {/* Best value properties */}
      {activeTab === 'value' && (
      isLoading ? renderValueLoading() : (
      <div id="value" className="mt-8">
        <h2 className="text-xl font-semibold mb-4">Best Value Properties (AI-Ranked)</h2>
        {bestValueProperties.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {bestValueProperties.map((prop) => (
              <div key={prop.id} className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-semibold text-sm">
                    {prop.url ? (
                      <a href={prop.url} target="_blank" rel="noopener noreferrer" className="text-[var(--accent-strong)] hover:underline">
                        {prop.title}
                      </a>
                    ) : (
                      prop.title
                    )}
                  </h3>
                  {prop.value_score && (
                    <div className="bg-[var(--accent)] text-white text-xs rounded-full px-2 py-1">
                      {prop.value_score.toFixed(1)}/10
                    </div>
                  )}
                </div>
                <p className="text-xs text-[var(--muted)] mb-3">
                  {prop.url ? (
                    <a href={prop.url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                      {prop.address}
                    </a>
                  ) : (
                    prop.address
                  )}
                </p>
                <div className="space-y-1 text-xs mb-3">
                  <div className="flex justify-between">
                    <span>Price:</span>
                    <span className="font-semibold">{formatEur(prop.price)}</span>
                  </div>
                  {prop.price_per_sqm && (
                    <div className="flex justify-between">
                      <span>€/m²:</span>
                      <span>{formatEur(prop.price_per_sqm)}</span>
                    </div>
                  )}
                  {prop.price_per_bed && prop.bedrooms && (
                    <div className="flex justify-between">
                      <span>€/bed:</span>
                      <span>{formatEur(prop.price_per_bed)}</span>
                    </div>
                  )}
                </div>
                <div className="text-[10px] text-[var(--muted)]">
                  {prop.bedrooms && <span>{prop.bedrooms} bed  </span>}
                  {prop.floor_area_sqm && <span>{prop.floor_area_sqm}m²</span>}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[var(--muted)] text-sm">No enriched properties available for value ranking.</p>
        )}
      </div>
      )
      )}

      {/* Price trends by type */}
      {!isLoading && activeTab === 'overview' && Object.keys(priceTrendsByType).length > 0 && (
        <div className="mt-8">
          <h2 className="text-xl font-semibold mb-4">Price Trends by Property Type</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {Object.entries(priceTrendsByType).map(([propType, trends]) => (
              <div key={propType} className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-lg p-4">
                <h3 className="font-semibold mb-3 capitalize">{propType}</h3>
                {trends.length > 0 ? (
                  <div className="space-y-2">
                    {trends.map((t) => (
                      <div key={t.period} className="flex justify-between text-sm">
                        <span className="text-[var(--muted)]">{t.period}</span>
                        <span>{formatEur(t.avg_price)} ({t.sale_count} sales)</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[var(--muted)] text-sm">No data available</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
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
