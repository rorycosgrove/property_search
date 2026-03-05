# Data Model

## Entity Relationship

```
Source 1──── N Property 1──── N PropertyPriceHistory
                  │
                  └──── 0..1 LLMEnrichment

SoldProperty (PPR records, independent)

SavedSearch 1──── N Alert
```

## Tables

### source
Represents a configured data source (e.g. "Daft.ie – Dublin").

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| name | VARCHAR(255) | Human-readable name |
| adapter_name | VARCHAR(100) | Adapter key (daft, myhome, ppr, rss, etc.) |
| enabled | BOOLEAN | Whether to include in scheduled scrapes |
| config | JSONB | Adapter-specific configuration |
| last_polled_at | TIMESTAMP | Last successful poll time |
| last_poll_status | VARCHAR(50) | ok / error |
| items_found_last_poll | INTEGER | Count from last poll |
| consecutive_errors | INTEGER | Error streak counter (resets on success) |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### property
Core property listing. Deduplicated by `content_hash`.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | |
| source_id | UUID (FK → source) | Owning source |
| title | VARCHAR(500) | Listing title |
| address | TEXT | Normalized address |
| county | VARCHAR(100) | Extracted county |
| eircode | VARCHAR(8) | Extracted Eircode |
| price | NUMERIC(12,2) | Current asking price |
| bedrooms | SMALLINT | |
| bathrooms | SMALLINT | |
| floor_area_sqm | NUMERIC(8,2) | |
| property_type | VARCHAR(50) | house, apartment, etc. |
| sale_type | VARCHAR(50) | sale, rent, auction |
| status | VARCHAR(50) | available, sale_agreed, sold, withdrawn |
| ber_rating | VARCHAR(10) | A1–G or EXEMPT |
| description | TEXT | Full listing text |
| url | VARCHAR(1000) | Original listing URL |
| image_urls | JSONB | Array of image URLs |
| latitude | DOUBLE | WGS84 |
| longitude | DOUBLE | WGS84 |
| location | GEOMETRY(POINT, 4326) | PostGIS spatial column |
| content_hash | VARCHAR(64) | SHA-256 of URL (dedup key) |
| fuzzy_hash | VARCHAR(64) | Hash of normalized address+price (fuzzy dedup) |
| raw_data | JSONB | Original scraped data |
| first_listed_at | TIMESTAMP | When first seen |
| last_seen_at | TIMESTAMP | Most recent scrape that found it |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**Indexes:**
- `ix_property_content_hash` (UNIQUE)
- `ix_property_county`
- `ix_property_price`
- `ix_property_bedrooms`
- `ix_property_property_type`
- `ix_property_status`
- `ix_property_source_id`
- `ix_property_first_listed_at`
- PostGIS GIST index on `location`

### property_price_history
Tracks price changes over time.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | |
| property_id | UUID (FK → property) | |
| price | NUMERIC(12,2) | Price at this point |
| price_change | NUMERIC(12,2) | Delta from previous (null for first) |
| recorded_at | TIMESTAMP | When change was detected |

### sold_property
Property Price Register records (independent of active listings).

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | |
| address | TEXT | |
| county | VARCHAR(100) | |
| price | NUMERIC(12,2) | Actual sale price |
| sale_date | DATE | |
| property_type | VARCHAR(50) | |
| is_new | BOOLEAN | New build or second-hand |
| latitude | DOUBLE | |
| longitude | DOUBLE | |
| location | GEOMETRY(POINT, 4326) | |
| content_hash | VARCHAR(64) | Dedup key |
| created_at | TIMESTAMP | |

### saved_search
User-defined search criteria for alert matching.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | |
| name | VARCHAR(255) | |
| criteria | JSONB | Search filter criteria |
| alerts_enabled | BOOLEAN | |
| last_matched_at | TIMESTAMP | Last time alerts were evaluated |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### alert
Generated notifications.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | |
| alert_type | VARCHAR(50) | new_listing, price_drop, price_increase, sale_agreed, back_on_market |
| severity | VARCHAR(20) | low, medium, high, critical |
| title | VARCHAR(500) | Human-readable summary |
| property_id | UUID (FK → property, nullable) | Related property |
| saved_search_id | UUID (FK → saved_search, nullable) | Triggering search |
| data | JSONB | Extra context (old_price, new_price, etc.) |
| acknowledged | BOOLEAN | |
| created_at | TIMESTAMP | |

### llm_enrichment
AI-generated insights for a property.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | |
| property_id | UUID (FK → property, UNIQUE) | |
| provider | VARCHAR(50) | ollama or openai |
| model | VARCHAR(100) | Model name used |
| summary | TEXT | AI-generated summary |
| value_score | NUMERIC(3,1) | 1–10 value rating |
| pros | JSONB | Array of strings |
| cons | JSONB | Array of strings |
| features | JSONB | Extracted features |
| neighbourhood | TEXT | Area description |
| investment_notes | TEXT | Investment analysis |
| raw_response | JSONB | Full LLM response |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |
