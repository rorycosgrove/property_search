/**
 * API client for the Property Research Dashboard backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
let resolvedAPIBase = API_BASE;
let discoveringAPIBase: Promise<string | null> | null = null;

const DISCOVERY_PROBE_PATHS = [
  '/api/v1/properties?size=1',
  '/api/v1/alerts/unread-count',
  '/api/v1/sources',
];

async function fetchWithTimeout(url: string, timeoutMs = 1800): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { method: 'GET', signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

// Validate API_BASE to prevent SSRF
function validateAPIBase(base: string): void {
  try {
    const url = new URL(base);
    const allowedHosts = ['localhost', '127.0.0.1', 'execute-api.eu-west-1.amazonaws.com'];
    if (!allowedHosts.some((host) => url.hostname === host || url.hostname.endsWith(`.${host}`))) {
      throw new Error('Invalid API host');
    }
  } catch {
    throw new Error('Invalid API URL');
  }
}

validateAPIBase(API_BASE);

function isLocalhostBase(base: string): boolean {
  try {
    const url = new URL(base);
    return url.hostname === 'localhost' || url.hostname === '127.0.0.1';
  } catch {
    return false;
  }
}

function buildCandidateBases(base: string): string[] {
  try {
    const url = new URL(base);
    const fallbackPort = (url.hostname === 'localhost' || url.hostname === '127.0.0.1') ? 8000 : 443;
    const currentPort = Number(url.port || fallbackPort);
    const candidates = [currentPort, 8000, 8001, 8002, 8003, 8004, 8005];
    const uniquePorts = Array.from(new Set(candidates.filter((p) => Number.isInteger(p) && p > 0)));
    return uniquePorts.map((port) => `${url.protocol}//${url.hostname}:${port}`);
  } catch {
    return [base];
  }
}

async function discoverLocalAPIBase(excludeBase?: string): Promise<string | null> {
  if (!isLocalhostBase(API_BASE)) {
    return null;
  }

  if (!discoveringAPIBase) {
    discoveringAPIBase = (async () => {
      const candidates = buildCandidateBases(API_BASE);
      const healthOnlyFallbacks: string[] = [];

      for (const candidate of candidates) {
        if (excludeBase && candidate === excludeBase) {
          continue;
        }

        try {
          const health = await fetchWithTimeout(`${candidate}/health`);
          if (!health.ok) {
            continue;
          }

          // Accept only bases that expose at least one core API path.
          for (const probePath of DISCOVERY_PROBE_PATHS) {
            const probe = await fetchWithTimeout(`${candidate}${probePath}`);
            if (probe.ok) {
              return candidate;
            }
          }

          healthOnlyFallbacks.push(candidate);
        } catch {
          // Try next candidate port.
        }
      }

      if (healthOnlyFallbacks.length > 0) {
        return healthOnlyFallbacks[0];
      }

      return null;
    })();
  }

  const found = await discoveringAPIBase;
  discoveringAPIBase = null;
  return found;
}

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  let requestUrl = `${resolvedAPIBase}${path}`;
  let res = await fetch(requestUrl, {
    ...options,
    cache: 'no-store',
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-cache',
      Pragma: 'no-cache',
      ...options?.headers,
    },
  });

  if (!res.ok && isLocalhostBase(API_BASE)) {
    const discovered = await discoverLocalAPIBase(resolvedAPIBase);
    if (discovered && discovered !== resolvedAPIBase) {
      resolvedAPIBase = discovered;
      requestUrl = `${resolvedAPIBase}${path}`;
      res = await fetch(requestUrl, {
        ...options,
        cache: 'no-store',
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache',
          Pragma: 'no-cache',
          ...options?.headers,
        },
      });
    }
  }

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API error ${res.status} at ${requestUrl}: ${body}`);
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
  llm_value_score?: number;
  eligible_grants_total?: number;
  net_price?: number;
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
  eligible_only?: boolean;
  min_eligible_grants_total?: number;
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

export interface PriceHistoryEntry {
  id: string;
  property_id: string;
  price: number;
  price_change?: number;
  price_change_pct?: number;
  source?: string;
  recorded_at?: string;
}

export async function getPriceHistory(id: string): Promise<PriceHistoryEntry[]> {
  return fetchJSON<PriceHistoryEntry[]>(`/api/v1/properties/${id}/price-history`);
}

export async function getSimilarProperties(id: string, limit = 5): Promise<Property[]> {
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

export async function getSoldProperties(filters: Record<string, string | number | boolean | undefined> = {}): Promise<{ items: SoldProperty[]; total: number }> {
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

export interface CountyStat {
  county: string;
  listing_count: number;
  avg_price?: number;
  median_price?: number;
}

export interface PriceTrend {
  period: string;
  avg_price?: number;
  median_price?: number;
  sale_count: number;
}

export interface PropertyTypeDistribution {
  property_type: string;
  count: number;
  percentage: number;
}

export interface BERDistribution {
  ber_rating: string;
  count: number;
  percentage: number;
}

export interface HeatmapPoint {
  lat: number;
  lng: number;
  weight?: number;
}

export async function getAnalyticsSummary(): Promise<AnalyticsSummary> {
  return fetchJSON<AnalyticsSummary>('/api/v1/analytics/summary');
}

export async function getCountyStats(): Promise<CountyStat[]> {
  return fetchJSON<CountyStat[]>('/api/v1/analytics/county-stats');
}

export async function getPriceTrends(county?: string, months = 12): Promise<PriceTrend[]> {
  const params = new URLSearchParams({ months: String(months) });
  if (county) params.set('county', county);
  return fetchJSON<PriceTrend[]>(`/api/v1/analytics/price-trends?${params}`);
}

export async function getTypeDistribution(county?: string): Promise<PropertyTypeDistribution[]> {
  const params = county ? `?county=${county}` : '';
  return fetchJSON<PropertyTypeDistribution[]>(`/api/v1/analytics/type-distribution${params}`);
}

export async function getBERDistribution(county?: string): Promise<BERDistribution[]> {
  const params = county ? `?county=${county}` : '';
  return fetchJSON<BERDistribution[]>(`/api/v1/analytics/ber-distribution${params}`);
}

export async function getHeatmapData(): Promise<HeatmapPoint[]> {
  return fetchJSON<HeatmapPoint[]>('/api/v1/analytics/heatmap');
}

export interface BestValueProperty {
  id: string;
  title: string;
  address: string;
  url?: string;
  county: string;
  property_type?: string;
  price: number;
  bedrooms?: number;
  floor_area_sqm?: number;
  value_score?: number;
  price_per_sqm?: number;
  price_per_bed?: number;
}

export async function getBestValueProperties(
  county?: string,
  propertyType?: string,
  maxBudget?: number,
  limit = 10
): Promise<BestValueProperty[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (county) params.set('county', county);
  if (propertyType) params.set('property_type', propertyType);
  if (maxBudget !== undefined) params.set('max_price', String(maxBudget));
  return fetchJSON<BestValueProperty[]>(`/api/v1/analytics/best-value-properties?${params}`);
}

export async function getPriceTrendsByType(county?: string, months = 12): Promise<Record<string, PriceTrend[]>> {
  const params = new URLSearchParams({ months: String(months) });
  if (county) params.set('county', county);
  return fetchJSON<Record<string, PriceTrend[]>>(`/api/v1/analytics/price-trends-by-type?${params}`);
}

export interface PriceChange {
  property_id: string;
  title: string;
  address: string;
  url?: string;
  county: string;
  current_price: number | null;
  property_type?: string;
  bedrooms?: number;
  bathrooms?: number;
  price_change: number | null;
  price_change_pct: number | null;
  recorded_at: string;
}

export interface PriceChangesTimeline {
  increases: Array<{
    date: string;
    count: number;
    avg_change: number;
    avg_change_pct: number;
  }>;
  decreases: Array<{
    date: string;
    count: number;
    avg_change: number;
    avg_change_pct: number;
  }>;
}

export async function getPriceChangesByBudget(
  maxBudget?: number,
  county?: string,
  days = 30,
  limit = 100
): Promise<PriceChange[]> {
  const params = new URLSearchParams({ days: String(days), limit: String(limit) });
  if (maxBudget !== undefined) params.set('max_budget', String(maxBudget));
  if (county) params.set('county', county);
  return fetchJSON<PriceChange[]>(`/api/v1/analytics/price-changes-by-budget?${params}`);
}

export async function getPriceChangesTimeline(
  maxBudget?: number,
  county?: string,
  days = 30
): Promise<PriceChangesTimeline> {
  const params = new URLSearchParams({ days: String(days) });
  if (maxBudget !== undefined) params.set('max_budget', String(maxBudget));
  if (county) params.set('county', county);
  return fetchJSON<PriceChangesTimeline>(`/api/v1/analytics/price-changes-timeline?${params}`);
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

export async function getAlerts(filters: Record<string, string | number | boolean | undefined> = {}): Promise<{ items: Alert[]; total: number }> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null) params.set(k, String(v));
  });
  return fetchJSON<{ items: Alert[]; total: number }>(`/api/v1/alerts?${params}`);
}

export async function getUnreadAlertCount(): Promise<{ count: number }> {
  return fetchJSON<{ count: number }>('/api/v1/alerts/unread-count');
}

export async function acknowledgeAlert(id: string): Promise<{ id: string; acknowledged: boolean }> {
  return fetchJSON<{ id: string; acknowledged: boolean }>(`/api/v1/alerts/${id}/acknowledge`, { method: 'PATCH' });
}

export async function acknowledgeAllAlerts(): Promise<{ acknowledged: number }> {
  return fetchJSON<{ acknowledged: number }>('/api/v1/alerts/acknowledge-all', { method: 'POST' });
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

export interface AdapterInfo {
  name: string;
  adapter_type: string;
  description?: string;
}

export async function getSources(): Promise<Source[]> {
  return fetchJSON<Source[]>('/api/v1/sources');
}

export async function getAdapters(): Promise<AdapterInfo[]> {
  return fetchJSON<AdapterInfo[]>('/api/v1/sources/adapters');
}

export async function triggerScrape(
  sourceId: string,
  options?: { force?: boolean },
): Promise<{ task_id?: string; status: string; result?: Record<string, unknown>; timestamp?: string; force?: boolean }> {
  const params = new URLSearchParams();
  if (options?.force) {
    params.set('force', 'true');
  }
  const suffix = params.toString();
  const path = suffix
    ? `/api/v1/sources/${sourceId}/trigger?${suffix}`
    : `/api/v1/sources/${sourceId}/trigger`;
  return fetchJSON<{ task_id?: string; status: string; result?: Record<string, unknown>; timestamp?: string; force?: boolean }>(
    path,
    { method: 'POST' },
  );
}

export interface SourceDiscoveryRunResult {
  run_at?: string;
  created: Source[];
  existing: Array<{ id: string; url: string; name: string; timestamp?: string }>;
  skipped_invalid: Array<{ url?: string; reason: string; timestamp?: string }>;
  auto_enable: boolean;
}

export interface ScrapeSourceSummary {
  total: number;
  enabled: number;
  pending_approval: number;
  disabled_by_errors: number;
}

export interface DiscoveryDuringScrapeSummary {
  created: number;
  created_enabled?: number;
  created_pending_approval?: number;
  existing: number;
  skipped_invalid: number;
  auto_enable: boolean;
  enabled: boolean;
  limit: number;
  error?: string;
}

export async function discoverSourcesAuto(
  autoEnable = false,
  limit = 25,
): Promise<SourceDiscoveryRunResult> {
  return fetchJSON<SourceDiscoveryRunResult>(
    `/api/v1/sources/discover-auto?auto_enable=${String(autoEnable)}&limit=${limit}`,
    { method: 'POST' },
  );
}

export async function getPendingDiscoveredSources(): Promise<Source[]> {
  return fetchJSON<Source[]>('/api/v1/sources/discovery/pending');
}

export async function approveDiscoveredSource(sourceId: string): Promise<Source> {
  return fetchJSON<Source>(`/api/v1/sources/${sourceId}/approve-discovered`, { method: 'POST' });
}

export interface OrganicSearchStepResult {
  step: string;
  status: 'dispatched' | 'processed_inline';
  timestamp?: string;
  task_id?: string;
  result?: Record<string, unknown>;
}

export interface OrganicSearchRunResult {
  run_id?: string;
  status: 'dispatched' | 'processed_inline' | 'mixed';
  steps: OrganicSearchStepResult[];
  created_at?: string;
}

export interface OrganicSearchHistoryItem {
  id: string;
  status: 'dispatched' | 'processed_inline' | 'mixed' | 'failed' | string;
  triggered_from: string;
  options: Record<string, unknown>;
  steps: OrganicSearchStepResult[];
  error?: string | null;
  created_at?: string;
}

export async function triggerFullOrganicSearch(
  options?: { runAlerts?: boolean; runLlmBatch?: boolean; llmLimit?: number; force?: boolean },
): Promise<OrganicSearchRunResult> {
  const params = new URLSearchParams();
  if (options?.force !== undefined) {
    params.set('force', String(options.force));
  }
  if (options?.runAlerts !== undefined) {
    params.set('run_alerts', String(options.runAlerts));
  }
  if (options?.runLlmBatch !== undefined) {
    params.set('run_llm_batch', String(options.runLlmBatch));
  }
  if (options?.llmLimit !== undefined) {
    params.set('llm_limit', String(options.llmLimit));
  }

  const suffix = params.toString();
  const path = suffix ? `/api/v1/sources/trigger-all?${suffix}` : '/api/v1/sources/trigger-all';
  return fetchJSON<OrganicSearchRunResult>(path, { method: 'POST' });
}

export async function getOrganicSearchHistory(limit = 20): Promise<OrganicSearchHistoryItem[]> {
  return fetchJSON<OrganicSearchHistoryItem[]>(`/api/v1/sources/trigger-all/history?limit=${limit}`);
}

// ── Admin / Backend Logs ───────────────────────────────────────────────────

export interface BackendFeedActivity {
  id: string;
  timestamp?: string;
  source_id?: string;
  source_name?: string;
  new: number;
  updated: number;
  skipped: number;
  total_fetched: number;
  geocode_success_rate?: number;
  status: string;
}

export interface BackendSourceStatus {
  id: string;
  name: string;
  enabled: boolean;
  status: 'active' | 'warning' | 'disabled' | string;
  error_count: number;
  last_error?: string;
  last_polled_at?: string;
  last_success_at?: string;
  poll_interval_seconds: number;
  total_listings: number;
}

export interface BackendDiscoveryActivity {
  id: string;
  timestamp?: string;
  event_type: string;
  level: string;
  message: string;
  context: Record<string, unknown>;
}

export interface BackendHealthSummary {
  scrape_runs_24h: number;
  geocode_attempts: number;
  geocode_successes: number;
  geocode_success_rate: number;
  queue_config: {
    scrape_queue_configured: boolean;
    alert_queue_configured: boolean;
    llm_queue_configured: boolean;
  };
  last_error: {
    timestamp?: string;
    message?: string;
    event_type?: string;
    level?: string;
  };
}

export interface BackendLogEntry {
  id: string;
  timestamp?: string;
  level: string;
  event_type: string;
  component: string;
  source_id?: string;
  message: string;
  context: Record<string, unknown>;
}

export async function getBackendLogs(options?: {
  hours?: number;
  limit?: number;
  level?: string;
  eventType?: string;
}): Promise<BackendLogEntry[]> {
  const params = new URLSearchParams();
  if (options?.hours !== undefined) {
    params.set('hours', String(options.hours));
  }
  if (options?.limit !== undefined) {
    params.set('limit', String(options.limit));
  }
  if (options?.level) {
    params.set('level', options.level);
  }
  if (options?.eventType) {
    params.set('event_type', options.eventType);
  }
  const suffix = params.toString();
  const path = suffix ? `/api/v1/admin/backend-logs?${suffix}` : '/api/v1/admin/backend-logs';
  return fetchJSON<BackendLogEntry[]>(path);
}

export async function getBackendFeedActivity(limit = 10): Promise<BackendFeedActivity[]> {
  return fetchJSON<BackendFeedActivity[]>(`/api/v1/admin/logs/feed-activity?limit=${limit}`);
}

export async function getBackendSourceStatus(): Promise<BackendSourceStatus[]> {
  return fetchJSON<BackendSourceStatus[]>('/api/v1/admin/logs/sources');
}

export async function getBackendDiscoveryActivity(limit = 5): Promise<BackendDiscoveryActivity[]> {
  return fetchJSON<BackendDiscoveryActivity[]>(`/api/v1/admin/logs/discovery?limit=${limit}`);
}

export async function getBackendHealthSummary(): Promise<BackendHealthSummary> {
  return fetchJSON<BackendHealthSummary>('/api/v1/admin/logs/health');
}

export async function getBackendRecentErrors(
  limit = 25,
  level?: 'ERROR' | 'WARNING',
): Promise<BackendLogEntry[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (level) {
    params.set('level', level);
  }
  return fetchJSON<BackendLogEntry[]>(`/api/v1/admin/logs/recent-errors?${params.toString()}`);
}

export interface ListingDiagnoseOptions {
  adapterName?: string;
  hours?: number;
  maxProbeSources?: number;
  listingUrl?: string;
  probeMaxPages?: number;
  similarIds?: string[];
}

export interface ListingDiagnoseResult {
  external_id: string;
  adapter_name: string;
  persisted_matches: Array<Record<string, unknown>>;
  persisted_url_matches: Array<Record<string, unknown>>;
  recent_logs: BackendLogEntry[];
  probe: {
    matched?: boolean;
    attempted_sources?: Array<Record<string, unknown>>;
    match_source?: Record<string, unknown>;
    matched_identifiers?: string[];
    listing_url?: string | null;
    title?: string | null;
    api_id?: string | null;
    url_listing_id?: string | null;
    normalized_preview?: Record<string, unknown> | null;
  } | null;
  diagnosis: {
    status: string;
    reason?: string | null;
    recommended_action?: string | null;
  };
  repair: {
    status?: string | null;
    source_action?: string | null;
    source?: Record<string, unknown> | null;
    property?: Record<string, unknown> | null;
  } | null;
}

function buildListingDiagnosticQuery(options?: ListingDiagnoseOptions): string {
  const params = new URLSearchParams();
  if (options?.adapterName) {
    params.set('adapter_name', options.adapterName);
  }
  if (options?.hours !== undefined) {
    params.set('hours', String(options.hours));
  }
  if (options?.maxProbeSources !== undefined) {
    params.set('max_probe_sources', String(options.maxProbeSources));
  }
  if (options?.listingUrl) {
    params.set('listing_url', options.listingUrl);
  }
  if (options?.probeMaxPages !== undefined) {
    params.set('probe_max_pages', String(options.probeMaxPages));
  }
  if (options?.similarIds && options.similarIds.length > 0) {
    params.set('similar_ids', options.similarIds.join(','));
  }
  const suffix = params.toString();
  return suffix ? `?${suffix}` : '';
}

export async function diagnoseListingByExternalId(
  externalId: string,
  options?: ListingDiagnoseOptions,
): Promise<ListingDiagnoseResult> {
  const query = buildListingDiagnosticQuery(options);
  return fetchJSON<ListingDiagnoseResult>(`/api/v1/admin/listings/${externalId}/diagnose${query}`);
}

export async function repairListingByExternalId(
  externalId: string,
  options?: ListingDiagnoseOptions,
): Promise<ListingDiagnoseResult> {
  const query = buildListingDiagnosticQuery(options);
  return fetchJSON<ListingDiagnoseResult>(`/api/v1/admin/listings/${externalId}/repair${query}`, {
    method: 'POST',
  });
}

// ── LLM ─────────────────────────────────────────────────────────────────────

export interface LLMConfig {
  enabled: boolean;
  provider: string;
  model: string;
  queue_configured?: boolean;
  ready_for_enrichment?: boolean;
  reason?: string;
}

export interface LLMModelOption {
  id: string;
  label: string;
}

export interface LLMModelsResponse {
  provider: string;
  models: LLMModelOption[];
  default_model: string;
}

export async function getLLMConfig(): Promise<LLMConfig> {
  return fetchJSON<LLMConfig>('/api/v1/llm/config');
}

export async function getLLMModels(): Promise<LLMModelsResponse> {
  return fetchJSON<LLMModelsResponse>('/api/v1/llm/models');
}

export interface UpdateLLMConfigResponse {
  provider: string;
  model?: string;
  updated: boolean;
  warning?: string | null;
  inference_profile_configured?: boolean;
}

export async function updateLLMConfig(provider: string, model?: string): Promise<UpdateLLMConfigResponse> {
  const body: Record<string, string> = { provider };
  if (model) {
    body.bedrock_model = model;
  }
  return fetchJSON<UpdateLLMConfigResponse>('/api/v1/llm/config', {
    method: 'PUT',
    body: JSON.stringify(body),
  });
}

export interface LLMEnrichment {
  id: string;
  property_id: string;
  summary?: string;
  value_score?: number;
  value_reasoning?: string;
  pros?: string[];
  cons?: string[];
  extracted_features?: Record<string, unknown>;
  neighbourhood_notes?: string;
  investment_potential?: string;
  llm_provider?: string;
  llm_model?: string;
  processed_at?: string;
}

export interface LLMHealth {
  enabled: boolean;
  provider: string;
  model: string;
  healthy: boolean;
  queue_configured?: boolean;
  ready_for_enrichment?: boolean;
  reason?: string;
  model_listed?: boolean;
  invoke_ready?: boolean;
  invoke_error?: string | null;
  inference_profile_configured?: boolean;
}

export async function getLLMHealth(): Promise<LLMHealth> {
  return fetchJSON<LLMHealth>('/api/v1/llm/health');
}

export async function getEnrichment(propertyId: string): Promise<LLMEnrichment> {
  return fetchJSON<LLMEnrichment>(`/api/v1/llm/enrichment/${propertyId}`);
}

export async function triggerEnrichment(propertyId: string): Promise<{ task_id: string; status: string }> {
  return fetchJSON<{ task_id: string; status: string }>(`/api/v1/llm/enrich/${propertyId}`, { method: 'POST' });
}

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | string;
  content: string;
  citations: Citation[];
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  processing_time_ms?: number;
  created_at?: string;
}

export interface PropertyCitation {
  type: 'property';
  property_id: string;
  url?: string | null;
  label?: string | null;
  county?: string | null;
  price?: number | null;
}

export interface GrantCitation {
  type: 'grant';
  grant_program_id?: string;
  code?: string | null;
  label?: string | null;
  url?: string | null;
  status?: string | null;
  estimated_benefit?: number | null;
}

export type Citation = PropertyCitation | GrantCitation;

export interface RetrievalContext {
  selected_property_id?: string | null;
  selected_property_title?: string | null;
  ranking_mode?: RankingMode | null;
  shortlist_size?: number;
  winner_property_id?: string | null;
  winner_property_title?: string | null;
  grant_count?: number;
  grants_considered?: Array<{ code?: string | null; status?: string | null; estimated_benefit?: number | null }>;
}

export interface Conversation {
  id: string;
  title?: string;
  user_identifier: string;
  context: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
  messages: ConversationMessage[];
}

export interface ChatTurnResponse {
  conversation_id: string;
  user_message: ConversationMessage;
  assistant_message: ConversationMessage;
  retrieval_context?: RetrievalContext;
}

export type RankingMode = 'llm_only' | 'hybrid' | 'user_weighted' | 'net_price';

export interface ComparePropertyMetric {
  property_id: string;
  title: string;
  address: string;
  county?: string;
  url: string;
  image_url?: string;
  price?: number;
  price_per_sqm?: number;
  bedrooms?: number;
  bathrooms?: number;
  floor_area_sqm?: number;
  ber_rating?: string;
  llm_value_score?: number;
  hybrid_score?: number;
  weighted_score?: number;
  grants_estimated_total?: number;
  grants_count?: number;
  eligible_grants_total?: number;
  net_price?: number;
}

export interface CompareSetResponse {
  ranking_mode: RankingMode;
  properties: ComparePropertyMetric[];
  winner_property_id?: string;
  analysis: {
    headline: string;
    recommendation: string;
    key_tradeoffs: string[];
    confidence: 'low' | 'medium' | 'high';
    citations: Citation[];
    reasoning?: string;
  };
}

export interface AutoCompareRequest {
  session_id: string;
  property_ids: string[];
  ranking_mode: RankingMode;
  search_context?: Record<string, unknown>;
  weights?: { value?: number; location?: number; condition?: number; potential?: number };
}

export interface AutoCompareRunResponse {
  run_id: string;
  session_id: string;
  result: CompareSetResponse;
  cached?: boolean;
}

export interface AutoCompareLatestResponse {
  run_id: string;
  status: string;
  options: Record<string, unknown>;
  steps: Array<Record<string, unknown>>;
  result?: CompareSetResponse | null;
  error?: string | null;
  created_at?: string | null;
}

export async function createConversation(userIdentifier: string, title?: string) {
  return fetchJSON<Conversation>('/api/v1/llm/chat/conversations', {
    method: 'POST',
    body: JSON.stringify({ user_identifier: userIdentifier, title }),
  });
}

export async function getConversation(conversationId: string) {
  return fetchJSON<Conversation>(`/api/v1/llm/chat/conversations/${conversationId}`);
}

export async function sendConversationMessage(
  conversationId: string,
  content: string,
  propertyId?: string,
  retrievalContext?: RetrievalContext,
) {
  return fetchJSON<ChatTurnResponse>(`/api/v1/llm/chat/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content, property_id: propertyId, retrieval_context: retrievalContext }),
  });
}

export async function comparePropertySet(
  propertyIds: string[],
  rankingMode: RankingMode = 'hybrid',
  weights?: { value?: number; location?: number; condition?: number; potential?: number },
) {
  return fetchJSON<CompareSetResponse>('/api/v1/llm/compare-set', {
    method: 'POST',
    body: JSON.stringify({ property_ids: propertyIds, ranking_mode: rankingMode, weights }),
  });
}

export async function triggerAutoCompare(payload: AutoCompareRequest) {
  return fetchJSON<AutoCompareRunResponse>('/api/v1/llm/auto-compare', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getLatestAutoCompare(sessionId: string) {
  const params = new URLSearchParams({ session_id: sessionId });
  return fetchJSON<AutoCompareLatestResponse>(`/api/v1/llm/auto-compare/latest?${params.toString()}`);
}

// ── Grants ──────────────────────────────────────────────────────────────────

export interface GrantProgram {
  id: string;
  code: string;
  name: string;
  country: string;
  region?: string;
  authority?: string;
  description?: string;
  eligibility_rules?: Record<string, unknown>;
  benefit_type?: string;
  max_amount?: number;
  currency: string;
  active: boolean;
  valid_from?: string;
  valid_to?: string;
  source_url?: string;
  created_at?: string;
  updated_at?: string;
}

export interface PropertyGrantMatch {
  id: string;
  property_id: string;
  grant_program_id: string;
  status: string;
  reason?: string;
  estimated_benefit?: number;
  metadata: Record<string, unknown>;
  created_at?: string;
  grant_program?: GrantProgram;
}

export async function getGrants(country?: string, activeOnly = true) {
  const params = new URLSearchParams();
  if (country) {
    params.set('country', country);
  }
  params.set('active_only', String(activeOnly));
  return fetchJSON<GrantProgram[]>(`/api/v1/grants?${params.toString()}`);
}

export async function getPropertyGrantMatches(propertyId: string) {
  return fetchJSON<PropertyGrantMatch[]>(`/api/v1/grants/property/${propertyId}`);
}

// ── Health ──────────────────────────────────────────────────────────────────

export async function getHealth() {
  return fetchJSON<{ status: string; database: boolean; version: string }>('/health');
}
