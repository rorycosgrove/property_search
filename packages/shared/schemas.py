"""
Pydantic schemas for API request/response models and inter-module contracts.

These schemas define the public API surface. Business logic and workers
communicate through these schemas, never through ORM models directly.
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

# ── Enums ─────────────────────────────────────────────────────────────────────

class PropertyType(enum.StrEnum):
    HOUSE = "house"
    APARTMENT = "apartment"
    DUPLEX = "duplex"
    BUNGALOW = "bungalow"
    SITE = "site"
    STUDIO = "studio"
    OTHER = "other"


class SaleType(enum.StrEnum):
    SALE = "sale"
    AUCTION = "auction"
    NEW_HOME = "new_home"
    SITE = "site"


class PropertyStatus(enum.StrEnum):
    NEW = "new"
    ACTIVE = "active"
    PRICE_CHANGED = "price_changed"
    SALE_AGREED = "sale_agreed"
    SOLD = "sold"
    WITHDRAWN = "withdrawn"


class AdapterType(enum.StrEnum):
    SCRAPER = "scraper"
    API = "api"
    RSS = "rss"
    CSV = "csv"


class AlertType(enum.StrEnum):
    NEW_LISTING = "new_listing"
    PRICE_DROP = "price_drop"
    PRICE_INCREASE = "price_increase"
    SALE_AGREED = "sale_agreed"
    MARKET_TREND = "market_trend"
    BACK_ON_MARKET = "back_on_market"


class AlertSeverity(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class NotifyMethod(enum.StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"
    BOTH = "both"


# ── Source Schemas ────────────────────────────────────────────────────────────

class SourceBase(BaseModel):
    name: str = Field(..., max_length=255, description="Human-readable source name")
    url: str = Field(..., max_length=1024, description="Source URL")
    adapter_type: AdapterType = Field(..., description="Adapter category")
    adapter_name: str = Field(..., max_length=100, description="Specific adapter class name")
    config: dict[str, Any] = Field(default_factory=dict, description="Adapter-specific config")
    enabled: bool = Field(default=True, description="Whether to actively poll")
    poll_interval_seconds: int = Field(default=900, description="Poll interval override")
    tags: list[str] = Field(default_factory=list, description="Classification tags")


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    config: dict[str, Any] | None = None
    enabled: bool | None = None
    poll_interval_seconds: int | None = None
    tags: list[str] | None = None


class SourceResponse(SourceBase):
    id: str
    last_polled_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    error_count: int = 0
    total_listings: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Property Schemas ──────────────────────────────────────────────────────────

class PropertyBase(BaseModel):
    title: str
    description: str | None = None
    url: str
    address: str
    address_line1: str | None = None
    address_line2: str | None = None
    town: str | None = None
    county: str | None = None
    eircode: str | None = None
    price: float | None = None
    price_text: str | None = None
    property_type: PropertyType | None = None
    sale_type: SaleType = SaleType.SALE
    bedrooms: int | None = None
    bathrooms: int | None = None
    floor_area_sqm: float | None = None
    ber_rating: str | None = None
    ber_number: str | None = None
    images: list[dict[str, str]] = Field(default_factory=list)
    features: dict[str, Any] = Field(default_factory=dict)
    latitude: float | None = None
    longitude: float | None = None
    status: PropertyStatus = PropertyStatus.NEW
    first_listed_at: datetime | None = None


class PropertyResponse(PropertyBase):
    id: str
    source_id: str
    external_id: str | None = None
    content_hash: str
    created_at: datetime
    updated_at: datetime
    eligible_grants_total: float | None = None
    net_price: float | None = None
    enrichment: LLMEnrichmentResponse | None = None
    price_history: list[PriceHistoryResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PropertyListResponse(BaseModel):
    items: list[PropertyResponse]
    total: int
    page: int
    per_page: int
    pages: int


class PropertyFilters(BaseModel):
    """Query parameters for filtering properties."""
    counties: list[str] | None = None
    min_price: float | None = None
    max_price: float | None = None
    min_bedrooms: int | None = None
    max_bedrooms: int | None = None
    property_types: list[PropertyType] | None = None
    ber_ratings: list[str] | None = None
    keywords: list[str] | None = None
    statuses: list[PropertyStatus] | None = None
    source_id: str | None = None
    sale_type: str | None = None
    lat: float | None = None
    lng: float | None = None
    radius_km: float | None = None
    eligible_only: bool = False
    min_eligible_grants_total: float | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page: int = 1
    per_page: int = 20


# ── Price History Schemas ─────────────────────────────────────────────────────

class PriceHistoryResponse(BaseModel):
    price: float
    price_change: float | None = None
    price_change_pct: float | None = None
    recorded_at: datetime

    model_config = {"from_attributes": True}


class PropertyTimelineEventResponse(BaseModel):
    id: str
    event_type: str
    occurred_at: datetime
    price: float | None = None
    price_change: float | None = None
    price_change_pct: float | None = None
    source_id: str | None = None
    adapter_name: str | None = None
    source_url: str | None = None
    detection_method: str | None = None
    confidence_score: float | None = None
    dedup_key: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


# ── Sold Property Schemas ─────────────────────────────────────────────────────

class SoldPropertyResponse(BaseModel):
    id: str
    address: str
    county: str
    price: float
    sale_date: date
    is_new: bool
    is_full_market_price: bool
    property_size_description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SoldPropertyFilters(BaseModel):
    county: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    date_from: date | None = None
    date_to: date | None = None
    address_contains: str | None = None
    is_new: bool | None = None
    lat: float | None = None
    lng: float | None = None
    radius_km: float | None = None
    page: int = 1
    per_page: int = 20


class SoldPropertyListResponse(BaseModel):
    items: list[SoldPropertyResponse]
    total: int
    page: int
    per_page: int
    pages: int


# ── Saved Search Schemas ──────────────────────────────────────────────────────

class SearchCriteria(BaseModel):
    counties: list[str] | None = None
    min_price: float | None = None
    max_price: float | None = None
    min_bedrooms: int | None = None
    max_bedrooms: int | None = None
    property_types: list[PropertyType] | None = None
    ber_ratings: list[str] | None = None
    min_floor_area_sqm: float | None = None
    keywords: list[str] | None = None
    radius_km: float | None = None
    center_lat: float | None = None
    center_lng: float | None = None


class SavedSearchCreate(BaseModel):
    name: str = Field(..., max_length=255)
    criteria: SearchCriteria
    notify_new_listings: bool = True
    notify_price_drops: bool = True
    notify_method: NotifyMethod = NotifyMethod.IN_APP
    email: str | None = None


class SavedSearchUpdate(BaseModel):
    name: str | None = None
    criteria: SearchCriteria | None = None
    notify_new_listings: bool | None = None
    notify_price_drops: bool | None = None
    notify_method: NotifyMethod | None = None
    email: str | None = None
    is_active: bool | None = None


class SavedSearchResponse(BaseModel):
    id: str
    name: str
    criteria: SearchCriteria
    notify_new_listings: bool
    notify_price_drops: bool
    notify_method: NotifyMethod
    email: str | None = None
    is_active: bool
    last_matched_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Alert Schemas ─────────────────────────────────────────────────────────────

class AlertResponse(BaseModel):
    id: str
    property_id: str | None = None
    saved_search_id: str | None = None
    alert_type: AlertType
    title: str
    description: str | None = None
    severity: AlertSeverity
    metadata: dict[str, Any] = Field(default_factory=dict)
    acknowledged: bool = False
    acknowledged_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    items: list[AlertResponse]
    total: int
    page: int
    per_page: int


# ── LLM Enrichment Schemas ───────────────────────────────────────────────────

class LLMEnrichmentResponse(BaseModel):
    summary: str | None = None
    value_score: float | None = None
    value_reasoning: str | None = None
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    extracted_features: dict[str, Any] = Field(default_factory=dict)
    neighbourhood_notes: str | None = None
    investment_potential: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    processed_at: datetime | None = None
    processing_time_ms: int | None = None

    model_config = {"from_attributes": True}


# ── LLM Config Schemas ───────────────────────────────────────────────────────

class LLMConfigResponse(BaseModel):
    provider: str
    enabled: bool
    bedrock_model_id: str
    bedrock_max_tokens: int
    aws_region: str


class LLMConfigUpdate(BaseModel):
    provider: str | None = None
    enabled: bool | None = None
    bedrock_model: str | None = None
    bedrock_max_tokens: int | None = None


# ── Analytics Schemas ─────────────────────────────────────────────────────────

class CountyPriceStats(BaseModel):
    county: str
    avg_price: float
    median_price: float
    min_price: float
    max_price: float
    count: int


class PriceTrend(BaseModel):
    period: str
    avg_price: float
    median_price: float | None = None
    count: int


class PropertyTypeDistribution(BaseModel):
    property_type: str
    count: int
    percentage: float


class BERDistribution(BaseModel):
    ber_rating: str
    count: int
    percentage: float


class MarketHeatmapEntry(BaseModel):
    county: str
    avg_price: float
    listing_count: int
    avg_price_per_sqm: float | None = None


class AnalyticsSummary(BaseModel):
    total_active_listings: int
    avg_price: float | None
    median_price: float | None
    total_sold_ppr: int
    new_listings_24h: int
    price_changes_24h: int


# ── System ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    database: str
    bedrock: str
    worker: str | None = None
    backend_errors_last_hour: int | None = None


class QualityGateMetric(BaseModel):
    key: str
    label: str
    actual: float | int | None = None
    target: float | int
    comparator: str
    status: str
    sample_size: int | None = None
    note: str | None = None


class QualityGatesResponse(BaseModel):
    status: str
    evaluated_at: datetime
    metrics: list[QualityGateMetric] = Field(default_factory=list)


class AdapterInfo(BaseModel):
    """Information about an available source adapter."""
    name: str
    description: str
    adapter_type: AdapterType
    config_schema: dict[str, Any] = Field(default_factory=dict)
    supports_incremental: bool = False


# ── Grants Schemas ────────────────────────────────────────────────────────────

class GrantProgramBase(BaseModel):
    code: str = Field(..., max_length=80)
    name: str = Field(..., max_length=255)
    country: str = Field(..., max_length=20, description="IE, UK, or NI")
    region: str | None = Field(default=None, max_length=120)
    authority: str | None = Field(default=None, max_length=255)
    description: str | None = None
    eligibility_rules: dict[str, Any] = Field(default_factory=dict)
    benefit_type: str | None = Field(default=None, max_length=80)
    max_amount: float | None = None
    currency: str = Field(default="EUR", max_length=10)
    active: bool = True
    valid_from: date | None = None
    valid_to: date | None = None
    source_url: str | None = Field(default=None, max_length=1024)


class GrantProgramCreate(GrantProgramBase):
    pass


class GrantProgramUpdate(BaseModel):
    name: str | None = None
    region: str | None = None
    authority: str | None = None
    description: str | None = None
    eligibility_rules: dict[str, Any] | None = None
    benefit_type: str | None = None
    max_amount: float | None = None
    currency: str | None = None
    active: bool | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    source_url: str | None = None


class GrantProgramResponse(GrantProgramBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PropertyGrantMatchResponse(BaseModel):
    id: str
    property_id: str
    grant_program_id: str
    status: str
    reason: str | None = None
    estimated_benefit: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    grant_program: GrantProgramResponse | None = None


# ── Chat / Copilot Schemas ───────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    user_identifier: str = Field(..., max_length=120)
    title: str | None = Field(default=None, max_length=255)
    context: dict[str, Any] = Field(default_factory=dict)


class ConversationMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=6000)
    property_id: str | None = None
    retrieval_context: dict[str, Any] | None = None


class ConversationMessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    processing_time_ms: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: str
    title: str | None = None
    user_identifier: str
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    messages: list[ConversationMessageResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ChatTurnResponse(BaseModel):
    conversation_id: str
    user_message: ConversationMessageResponse
    assistant_message: ConversationMessageResponse
    retrieval_context: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)


class CompareWeights(BaseModel):
    value: float = 0.4
    location: float = 0.2
    condition: float = 0.2
    potential: float = 0.2


class CompareSetRequest(BaseModel):
    property_ids: list[str] = Field(..., min_length=2, max_length=5)
    ranking_mode: str = Field(default="hybrid", pattern="^(llm_only|hybrid|user_weighted|net_price)$")
    weights: CompareWeights | None = None


class AutoCompareRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=120)
    property_ids: list[str] = Field(..., min_length=2, max_length=5)
    ranking_mode: str = Field(default="hybrid", pattern="^(llm_only|hybrid|user_weighted|net_price)$")
    search_context: dict[str, Any] = Field(default_factory=dict)
    weights: CompareWeights | None = None
