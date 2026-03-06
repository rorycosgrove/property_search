/**
 * API client for the Property Research Dashboard backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Validate API_BASE to prevent SSRF
function validateAPIBase(base: string): void {
  try {
    const url = new URL(base);
    const allowedHosts = ['localhost', '127.0.0.1', 'execute-api.eu-west-1.amazonaws.com'];
    if (!allowedHosts.some(host => url.hostname === host || url.hostname.endsWith(`.${host}`))) {
      throw new Error('Invalid API host');
    }
  } catch {
    throw new Error('Invalid API URL');
  }
}

validateAPIBase(API_BASE);

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API error ${res.status}: ${body}`);
  }

  return res.json();
}

// ── Properties ──────────────────────────────────────────────────────────────

export interface Property {
  id: string;
  title: string;
  description?: string;
  url: string;
  address: string;
  county?: string;
  eircode?: string;
  price?: number;
  property_type?: string;
  sale_type?: string;
  bedrooms?: number;
  bathrooms?: number;
  floor_area_sqm?: number;
  ber_rating?: string;
  images?: { url: string; caption?: string }[];
  features?: Record<string, unknown>;
  latitude?: number;
  longitude?: number;
  status?: string;
  source_id?: string;
  first_listed_at?: string;
  created_at?: string;
}

export interface PropertyListResponse {
  items: Property[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface PropertyFilters {
  county?: string;
  min_price?: number;
  max_price?: number;
  min_beds?: number;
  max_beds?: number;
  property_types?: string;
  sale_type?: string;
  keywords?: string;
  ber_ratings?: string;
  sort_by?: string;
  sort_dir?: string;
  lat?: number;
  lng?: number;
  radius_km?: number;
  page?: number;
  size?: number;
}

export async function getProperties(filters: PropertyFilters = {}): Promise<PropertyListResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value));
    }
  });
  return fetchJSON<PropertyListResponse>(`/api/v1/properties?${params}`);
}

export async function getProperty(id: string): Promise<Property> {
  return fetchJSON<Property>(`/api/v1/properties/${id}`);
}

export async function getPriceHistory(id: string) {
  return fetchJSON<any[]>(`/api/v1/properties/${id}/price-history`);
}

export async function getSimilarProperties(id: string, limit = 5) {
  return fetchJSON<Property[]>(`/api/v1/properties/${id}/similar?limit=${limit}`);
}

// ── Sold Properties ─────────────────────────────────────────────────────────

export interface SoldProperty {
  id: string;
  address: string;
  county?: string;
  price?: number;
  sale_date?: string;
  is_new?: boolean;
  latitude?: number;
  longitude?: number;
}

export async function getSoldProperties(filters: Record<string, any> = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null) params.set(k, String(v));
  });
  return fetchJSON<{ items: SoldProperty[]; total: number }>(`/api/v1/sold?${params}`);
}

export async function getNearbySold(lat: number, lng: number, radiusKm = 5) {
  return fetchJSON<SoldProperty[]>(`/api/v1/sold/nearby?lat=${lat}&lng=${lng}&radius_km=${radiusKm}`);
}

// ── Analytics ───────────────────────────────────────────────────────────────

export interface AnalyticsSummary {
  total_active_listings: number;
  avg_price?: number;
  median_price?: number;
  total_sold_ppr: number;
  new_listings_24h: number;
  price_changes_24h: number;
}

export async function getAnalyticsSummary(): Promise<AnalyticsSummary> {
  return fetchJSON('/api/v1/analytics/summary');
}

export async function getCountyStats() {
  return fetchJSON<any[]>('/api/v1/analytics/county-stats');
}

export async function getPriceTrends(county?: string, months = 12) {
  const params = new URLSearchParams({ months: String(months) });
  if (county) params.set('county', county);
  return fetchJSON<any[]>(`/api/v1/analytics/price-trends?${params}`);
}

export async function getTypeDistribution(county?: string) {
  const params = county ? `?county=${county}` : '';
  return fetchJSON<any[]>(`/api/v1/analytics/type-distribution${params}`);
}

export async function getBERDistribution(county?: string) {
  const params = county ? `?county=${county}` : '';
  return fetchJSON<any[]>(`/api/v1/analytics/ber-distribution${params}`);
}

export async function getHeatmapData() {
  return fetchJSON<any[]>('/api/v1/analytics/heatmap');
}

// ── Alerts ──────────────────────────────────────────────────────────────────

export interface Alert {
  id: string;
  alert_type: string;
  title: string;
  severity: string;
  property_id?: string;
  metadata?: Record<string, unknown>;
  acknowledged: boolean;
  created_at?: string;
}

export async function getAlerts(filters: Record<string, any> = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null) params.set(k, String(v));
  });
  return fetchJSON<{ items: Alert[]; total: number }>(`/api/v1/alerts?${params}`);
}

export async function getUnreadAlertCount(): Promise<{ count: number }> {
  return fetchJSON('/api/v1/alerts/unread-count');
}

export async function acknowledgeAlert(id: string) {
  return fetchJSON(`/api/v1/alerts/${id}/acknowledge`, { method: 'PATCH' });
}

export async function acknowledgeAllAlerts() {
  return fetchJSON('/api/v1/alerts/acknowledge-all', { method: 'POST' });
}

// ── Sources ─────────────────────────────────────────────────────────────────

export interface Source {
  id: string;
  name: string;
  url: string;
  adapter_type: string;
  adapter_name: string;
  config?: Record<string, unknown>;
  enabled: boolean;
  poll_interval_seconds: number;
  tags: string[];
  last_polled_at?: string;
  last_success_at?: string;
  last_error?: string;
  error_count: number;
  total_listings: number;
  created_at?: string;
  updated_at?: string;
}

export async function getSources(): Promise<Source[]> {
  return fetchJSON('/api/v1/sources');
}

export async function getAdapters() {
  return fetchJSON<any[]>('/api/v1/sources/adapters');
}

export async function triggerScrape(sourceId: string) {
  return fetchJSON(`/api/v1/sources/${sourceId}/trigger`, { method: 'POST' });
}

// ── LLM ─────────────────────────────────────────────────────────────────────

export async function getLLMConfig() {
  return fetchJSON<{ provider: string; model: string }>('/api/v1/llm/config');
}

export async function updateLLMConfig(provider: string, model?: string) {
  const body: Record<string, string> = { provider };
  if (model) {
    body.bedrock_model = model;
  }
  return fetchJSON('/api/v1/llm/config', {
    method: 'PUT',
    body: JSON.stringify(body),
  });
}

export async function getEnrichment(propertyId: string) {
  return fetchJSON<any>(`/api/v1/llm/enrichment/${propertyId}`);
}

export async function triggerEnrichment(propertyId: string) {
  return fetchJSON(`/api/v1/llm/enrich/${propertyId}`, { method: 'POST' });
}

// ── Health ──────────────────────────────────────────────────────────────────

export async function getHealth() {
  return fetchJSON<{ status: string; database: boolean; version: string }>('/health');
}
