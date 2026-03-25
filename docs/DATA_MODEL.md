# Data Model

This document reflects the current SQLAlchemy schema in `packages/storage/models.py`.

## Core Relationships

```
Source 1────N Property 1────N PropertyPriceHistory
                    │
                    ├────N PropertyTimelineEvent
                    ├────N Alert
                    ├────N PropertyGrantMatch N────1 GrantProgram
                    ├────N PropertyDocument
                    └────0..1 LLMEnrichment

SavedSearch 1────N Alert
Conversation 1────N ConversationMessage

SoldProperty, BackendLog, OrganicSearchRun, SourceQualitySnapshot,
and GeocodeCache are standalone operational datasets.
```

## PostgreSQL Tables

### `sources`
Configured ingestion sources for scrapers, APIs, RSS feeds, and CSV imports.

Key columns:
- `id`, `name`, `url`
- `adapter_type` (`scraper`, `api`, `rss`, `csv`)
- `adapter_name`
- `config`, `enabled`, `poll_interval_seconds`, `tags`
- `last_polled_at`, `last_success_at`, `last_error`, `error_count`, `total_listings`
- `created_at`, `updated_at`

Key behavior:
- `url` is unique and is canonicalized before persistence.
- One source owns many `properties`.

### `properties`
Canonical live property listings aggregated from all enabled sources.

Key columns:
- Identity: `id`, `source_id`, `external_id`, `canonical_property_id`, `content_hash`
- Listing content: `title`, `description`, `url`
- Address and matching: `address`, `address_line1`, `address_line2`, `town`, `county`, `eircode`, `address_normalized`, `fuzzy_address_hash`
- Pricing: `price`, `price_text`
- Attributes: `property_type`, `sale_type`, `bedrooms`, `bathrooms`, `floor_area_sqm`, `ber_rating`, `ber_number`
- Media and metadata: `images`, `features`, `raw_data`
- Geospatial: `location_point`, `latitude`, `longitude`
- Lifecycle: `status`, `first_listed_at`, `last_updated_at`, `created_at`, `updated_at`

Important indexes:
- unique `content_hash`
- composite and filter indexes on county/price/status/source identity
- `address_normalized` and `fuzzy_address_hash`
- trigram GIN indexes on `address` and `title`
- partial unique index on (`source_id`, `external_id`) when `external_id` is not null

### `property_price_history`
Append-only price history snapshots for active listings.

Key columns:
- `property_id`, `price`, `price_change`, `price_change_pct`
- `recorded_at`
- `recorded_hour_utc` for per-hour deduplication

Important indexes:
- `property_id + recorded_at`
- unique `property_id + price + recorded_hour_utc`

### `property_timeline_events`
Unified lifecycle and provenance events for a property.

Key columns:
- `property_id`, `event_type`, `occurred_at`, `occurred_hour_utc`
- optional pricing deltas: `price`, `price_change`, `price_change_pct`
- provenance: `source_id`, `adapter_name`, `source_url`, `detection_method`, `confidence_score`, `dedup_key`
- evidence payloads: `evidence`, `metadata`

### `sold_properties`
Property Price Register sale records used for market analytics and comparable sales.

Key columns:
- `address`, `address_normalized`, `fuzzy_address_hash`, `county`
- `price`, `sale_date`
- `is_new`, `is_full_market_price`, `vat_exclusive`, `property_size_description`
- `location_point`, `latitude`, `longitude`
- `content_hash`, `created_at`

Important indexes:
- county/date and county/price composites
- `address_normalized`, `fuzzy_address_hash`
- trigram GIN index on `address`

### `saved_searches`
User-defined search criteria and notification preferences.

Key columns:
- `name`, `criteria`
- `notify_new_listings`, `notify_price_drops`, `notify_method`, `email`
- `is_active`, `last_matched_at`, `created_at`, `updated_at`

### `alerts`
Notifications generated from search matches and listing state changes.

Key columns:
- `property_id`, `saved_search_id`
- `alert_type` (`new_listing`, `price_drop`, `price_increase`, `sale_agreed`, `market_trend`, `back_on_market`)
- `title`, `description`, `severity`
- `metadata`, `acknowledged`, `acknowledged_at`, `created_at`

### `organic_search_runs`
Execution ledger for full scrape + alerts + enrichment runs.

Key columns:
- `status`, `triggered_from`, `options`, `steps`, `error`, `created_at`

### `backend_logs`
Structured operational event log for diagnostics and admin views.

Key columns:
- `level`, `event_type`, `component`, `source_id`, `message`, `context`, `created_at`

### `source_quality_snapshots`
Periodic source-quality and discovery-quality metrics.

Key columns:
- source identity: `source_id`, `source_name`, `adapter_name`, `run_type`
- ingestion counts: `total_fetched`, `parse_failed`, `new_count`, `updated_count`, `price_unchanged_count`, `dedup_conflicts`
- discovery counts: `candidates_scored`, `created_count`, `auto_enabled_count`, `pending_approval_count`, `existing_count`, `skipped_invalid_count`, `skipped_invalid_config_count`
- `score_avg`, `score_max`, `dry_run`, `follow_links`, `details`, `created_at`

### `geocode_cache`
Persistent cache of successful geocoding lookups.

Key columns:
- `query` (unique), `provider`
- `latitude`, `longitude`, `display_name`, `confidence`, `raw_json`
- `hit_count`, `last_hit_at`, `created_at`, `updated_at`

### `llm_enrichments`
Persisted Bedrock-generated analysis attached one-to-one to a property.

Key columns:
- `property_id` (unique)
- `summary`, `value_score`, `value_reasoning`
- `pros`, `cons`, `extracted_features`, `neighbourhood_notes`, `investment_potential`
- `llm_provider`, `llm_model`, `processed_at`, `processing_time_ms`

### `grant_programs`
Catalog of grant, rebate, equity, and similar buyer-support programs.

Key columns:
- `code`, `name`, `country`, `region`, `authority`
- `description`, `eligibility_rules`, `benefit_type`, `max_amount`, `currency`
- `active`, `valid_from`, `valid_to`, `source_url`, `created_at`, `updated_at`

### `property_grant_matches`
Materialized eligibility assessments between properties and grant programs.

Key columns:
- `property_id`, `grant_program_id`
- `status`, `reason`, `estimated_benefit`, `metadata`, `created_at`

Important indexes:
- unique `property_id + grant_program_id`

### `property_documents`
Retrieval-ready corpus records for property intelligence and chat flows.

Key columns:
- identity: `document_type`, `scope_type`, `scope_key`, `document_key`, `content_hash`
- joins: `property_id`, `source_id`, `canonical_property_id`, `county`
- content: `title`, `content`, `metadata`
- lifecycle: `effective_at`, `expires_at`, `created_at`, `updated_at`

### `conversations` and `conversation_messages`
User chat history persisted for the AI assistant experience.

`conversations`:
- `title`, `user_identifier`, `context`, `created_at`, `updated_at`

`conversation_messages`:
- `conversation_id`, `role`, `content`, `citations`
- token accounting: `prompt_tokens`, `completion_tokens`, `total_tokens`
- `processing_time_ms`, `created_at`

## DynamoDB Table

### `property-search-config`
Runtime configuration cache used for LLM provider/model overrides.

Attributes:
- `config_key` as the partition key
- `config_value` as the stored string value

Common keys include `llm_provider` and `llm_model`.

## Hosting Notes

- Production uses Amazon RDS PostgreSQL 16 with PostGIS in private isolated subnets.
- Local development uses Docker Compose with a PostGIS-enabled PostgreSQL image.
- Lambda functions receive database credentials through AWS Secrets Manager and runtime environment variables.
- Search quality features rely on PostgreSQL `pg_trgm` in production and use Python fallbacks in non-Postgres test environments where needed.
