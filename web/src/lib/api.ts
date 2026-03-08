/**
 * API client for the Property Research Dashboard backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
let resolvedAPIBase = API_BASE;
let discoveringAPIBase: Promise<string | null> | null = null;

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
      const healthyCandidates: string[] = [];

      for (const candidate of candidates) {
        if (excludeBase && candidate === excludeBase) {
          continue;
        }

        try {
          const health = await fetch(`${candidate}/health`, { method: 'GET' });
          if (!health.ok) {
            continue;
          }

          healthyCandidates.push(candidate);

          // Prefer API instances that expose the newer LLM models endpoint.
          const llmModels = await fetch(`${candidate}/api/v1/llm/models`, { method: 'GET' });
          if (llmModels.ok) {
            return candidate;
          }
        } catch {
          // Try next candidate port.
        }
      }

      if (healthyCandidates.length > 0) {
        return healthyCandidates[0];
      }

      return null;
    })();
  }

  const found = await discoveringAPIBase;
  discoveringAPIBase = null;
  return found;
}

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  let res = await fetch(`${resolvedAPIBase}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok && isLocalhostBase(API_BASE)) {
    const discovered = await discoverLocalAPIBase(resolvedAPIBase);
    if (discovered && discovered !== resolvedAPIBase) {
      resolvedAPIBase = discovered;
      res = await fetch(`${resolvedAPIBase}${path}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
      });
    }
  }

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
  llm_value_score?: number;
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
): Promise<{ task_id?: string; status: string; result?: Record<string, unknown> }> {
  return fetchJSON<{ task_id?: string; status: string; result?: Record<string, unknown> }>(
    `/api/v1/sources/${sourceId}/trigger`,
    { method: 'POST' },
  );
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
  citations: Array<Record<string, unknown>>;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  processing_time_ms?: number;
  created_at?: string;
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
}

export type RankingMode = 'llm_only' | 'hybrid' | 'user_weighted';

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
    citations: Array<Record<string, unknown>>;
  };
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
) {
  return fetchJSON<ChatTurnResponse>(`/api/v1/llm/chat/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content, property_id: propertyId }),
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
