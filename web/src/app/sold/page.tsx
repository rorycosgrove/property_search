'use client';

import { useEffect, useMemo, useState } from 'react';
import { getNearbySold, getSoldProperties, type SoldProperty } from '@/lib/api';
import { COUNTIES, formatDate, formatEur } from '@/lib/utils';
import { LoadingRows } from '@/components/LoadingState';

const PAGE_SIZE = 25;

export default function SoldPage() {
  const [county, setCounty] = useState('');
  const [minPrice, setMinPrice] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const [propertyType, setPropertyType] = useState('');
  const [page, setPage] = useState(1);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<SoldProperty[]>([]);
  const [total, setTotal] = useState(0);

  const [nearbyLat, setNearbyLat] = useState('53.3498');
  const [nearbyLng, setNearbyLng] = useState('-6.2603');
  const [nearbyRadius, setNearbyRadius] = useState('2');
  const [nearbyLoading, setNearbyLoading] = useState(false);
  const [nearbyError, setNearbyError] = useState<string | null>(null);
  const [nearbyResults, setNearbyResults] = useState<SoldProperty[]>([]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getSoldProperties({
          county: county || undefined,
          min_price: minPrice ? Number(minPrice) : undefined,
          max_price: maxPrice ? Number(maxPrice) : undefined,
          property_type: propertyType || undefined,
          page,
          size: PAGE_SIZE,
        });
        setItems(data.items);
        setTotal(data.total);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load sold comparables');
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [county, maxPrice, minPrice, page, propertyType]);

  useEffect(() => {
    setPage(1);
  }, [county, minPrice, maxPrice, propertyType]);

  useEffect(() => {
    setPage((prev) => Math.min(prev, totalPages));
  }, [totalPages]);

  const rangeLabel = useMemo(() => {
    if (total === 0) {
      return 'No sold records found';
    }
    const start = (page - 1) * PAGE_SIZE + 1;
    const end = Math.min(page * PAGE_SIZE, total);
    return `${start}-${end} of ${total.toLocaleString()} sold records`;
  }, [page, total]);

  const loadNearby = async () => {
    const lat = Number(nearbyLat);
    const lng = Number(nearbyLng);
    const radiusKm = Number(nearbyRadius);

    if (!Number.isFinite(lat) || !Number.isFinite(lng) || !Number.isFinite(radiusKm)) {
      setNearbyError('Enter valid latitude, longitude, and radius values.');
      return;
    }

    setNearbyLoading(true);
    setNearbyError(null);
    try {
      const results = await getNearbySold(lat, lng, radiusKm);
      setNearbyResults(results);
    } catch (e) {
      setNearbyError(e instanceof Error ? e.message : 'Failed to load nearby sold comparables');
    } finally {
      setNearbyLoading(false);
    }
  };

  return (
    <div className="page-shell page-shell-wide rise-in">
      <section className="page-hero">
        <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">Comparables</p>
        <h1 className="mt-2 text-3xl lg:text-4xl">Sold property evidence</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--muted)] lg:text-base">
          Use sold transactions to validate asking prices and benchmark shortlist value. This screen maps directly
          to sold list and nearby sold endpoints.
        </p>
      </section>

      <section className="mt-6 page-section-card">
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-[190px] flex-1">
            <label className="mb-1 block text-xs text-[var(--muted)]">County</label>
            <select value={county} onChange={(e) => setCounty(e.target.value)} className="ui-select w-full">
              <option value="">All counties</option>
              {COUNTIES.map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
          </div>
          <div className="min-w-[140px]">
            <label className="mb-1 block text-xs text-[var(--muted)]">Min price</label>
            <input type="number" value={minPrice} onChange={(e) => setMinPrice(e.target.value)} className="ui-input w-full" />
          </div>
          <div className="min-w-[140px]">
            <label className="mb-1 block text-xs text-[var(--muted)]">Max price</label>
            <input type="number" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)} className="ui-input w-full" />
          </div>
          <div className="min-w-[170px]">
            <label className="mb-1 block text-xs text-[var(--muted)]">Property type</label>
            <select value={propertyType} onChange={(e) => setPropertyType(e.target.value)} className="ui-select w-full">
              <option value="">All types</option>
              <option value="house">House</option>
              <option value="apartment">Apartment</option>
            </select>
          </div>
          <button
            type="button"
            onClick={() => {
              setCounty('');
              setMinPrice('');
              setMaxPrice('');
              setPropertyType('');
            }}
            className="ui-btn ui-btn-secondary"
          >
            Clear filters
          </button>
        </div>
      </section>

      <section className="mt-4 page-section-card">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-xl">Sold transactions</h2>
          <p className="text-sm text-[var(--muted)]">{loading ? 'Loading...' : rangeLabel}</p>
        </div>

        {error ? (
          <p className="mb-3 rounded-lg border border-[var(--danger)]/35 bg-[var(--danger)]/10 px-3 py-2 text-sm text-[var(--danger)]">
            {error}
          </p>
        ) : null}

        {loading ? <LoadingRows rows={6} /> : null}

        {!loading && items.length > 0 ? (
          <div className="overflow-auto rounded-lg border border-[var(--card-border)]">
            <table className="min-w-[760px] w-full text-sm">
              <thead className="bg-[var(--background)] text-[var(--muted)]">
                <tr>
                  <th className="px-3 py-2 text-left">Address</th>
                  <th className="px-3 py-2 text-left">County</th>
                  <th className="px-3 py-2 text-left">Sale date</th>
                  <th className="px-3 py-2 text-left">Price</th>
                  <th className="px-3 py-2 text-left">Type</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-t border-[var(--card-border)]">
                    <td className="px-3 py-2">{item.address}</td>
                    <td className="px-3 py-2">{item.county || '-'}</td>
                    <td className="px-3 py-2">{formatDate(item.sale_date) || '-'}</td>
                    <td className="px-3 py-2">{formatEur(item.price)}</td>
                    <td className="px-3 py-2">{item.is_new ? 'New build' : 'Existing'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {!loading && items.length === 0 ? (
          <p className="rounded-lg border border-dashed border-[var(--card-border)] px-4 py-8 text-center text-sm text-[var(--muted)]">
            No sold records match this filter set.
          </p>
        ) : null}

        {totalPages > 1 ? (
          <div className="mt-4 flex items-center justify-between gap-3 border-t border-[var(--card-border)] pt-3">
            <button
              type="button"
              onClick={() => setPage((prev) => Math.max(1, prev - 1))}
              disabled={page <= 1}
              className="ui-btn ui-btn-secondary disabled:opacity-50"
            >
              Previous
            </button>
            <p className="text-sm text-[var(--muted)]">Page {page} of {totalPages}</p>
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
      </section>

      <section className="mt-4 page-section-card">
        <div className="mb-3">
          <h2 className="text-xl">Nearby sold comparables</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">Use coordinates to find recent nearby sold evidence around a specific listing.</p>
        </div>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
          <input
            type="number"
            step="0.0001"
            value={nearbyLat}
            onChange={(e) => setNearbyLat(e.target.value)}
            placeholder="Latitude"
            className="ui-input"
          />
          <input
            type="number"
            step="0.0001"
            value={nearbyLng}
            onChange={(e) => setNearbyLng(e.target.value)}
            placeholder="Longitude"
            className="ui-input"
          />
          <input
            type="number"
            step="0.1"
            value={nearbyRadius}
            onChange={(e) => setNearbyRadius(e.target.value)}
            placeholder="Radius km"
            className="ui-input"
          />
          <button type="button" onClick={() => void loadNearby()} className="ui-btn ui-btn-primary" disabled={nearbyLoading}>
            {nearbyLoading ? 'Loading...' : 'Find nearby sold'}
          </button>
        </div>

        {nearbyError ? (
          <p className="mt-3 rounded-lg border border-[var(--danger)]/35 bg-[var(--danger)]/10 px-3 py-2 text-sm text-[var(--danger)]">
            {nearbyError}
          </p>
        ) : null}

        {nearbyResults.length > 0 ? (
          <div className="mt-3 space-y-2">
            {nearbyResults.map((item) => (
              <article key={item.id} className="rounded-lg border border-[var(--card-border)] bg-[var(--surface)] px-3 py-2">
                <p className="text-sm font-medium">{item.address}</p>
                <p className="text-xs text-[var(--muted)] mt-0.5">
                  {item.county || 'County unknown'} | {formatDate(item.sale_date) || 'Date unknown'} | {formatEur(item.price)}
                </p>
              </article>
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}