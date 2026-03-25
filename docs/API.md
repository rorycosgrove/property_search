# API Reference

Base URL: `https://<api-gateway-url>` (AWS) or `http://localhost:8000` (local)

Interactive docs: `<base-url>/docs` (Swagger UI)

All endpoints return JSON. Errors use standard HTTP status codes with `{"detail": "message"}` body.

---

## Health

### GET /health
Check API, database, and Bedrock health.

**Response** `200`
```json
{
  "status": "healthy",
  "database": "connected",
  "bedrock": "available",
  "backend_errors_last_hour": 0
}
```

Fields:
- `status` — `healthy` (all OK) or `degraded` (partial failure)
- `database` — `connected` or `disconnected`
- `bedrock` — `available` or `unavailable`
- `backend_errors_last_hour` — warning/error backend log count in the last hour (nullable if check unavailable)

---

## Admin

### GET /api/v1/admin/backend-logs
Query backend operational logs with optional filters.

**Query Parameters**
| Param | Type | Description |
|-------|------|-------------|
| hours | int | Window size in hours (1..168, default: 24) |
| limit | int | Max rows (1..500, default: 100) |
| level | string | Optional level filter (e.g., ERROR, WARNING, INFO) |
| event_type | string | Optional event type filter |

### GET /api/v1/admin/backend-logs/summary
Return backend log counts grouped by level and event type.

**Query Parameters**
| Param | Type | Description |
|-------|------|-------------|
| hours | int | Window size in hours (1..168, default: 24) |

### GET /api/v1/admin/logs/feed-activity
Recent feed refresh activity summary.

### GET /api/v1/admin/logs/sources
Current source status with polling/error metadata.

### GET /api/v1/admin/logs/discovery
Recent source discovery activity and candidate outcomes.

### GET /api/v1/admin/logs/health
Backend ingestion health summary (recent scrape/error indicators).

### GET /api/v1/admin/logs/recent-errors
Recent warning/error events.

**Query Parameters**
| Param | Type | Description |
|-------|------|-------------|
| level | string | Optional level override (default ERROR/WARNING set) |
| limit | int | Max rows (1..200, default: 25) |

---

## Properties

### GET /api/v1/properties
List properties with filtering, sorting, and pagination.

**Query Parameters**
| Param | Type | Description |
|-------|------|-------------|
| county | string | Filter by county name |
| min_price | int | Minimum price |
| max_price | int | Maximum price |
| min_beds | int | Minimum bedrooms |
| max_beds | int | Maximum bedrooms |
| property_types | string | Comma-separated types (house, apartment, etc.) |
| keywords | string | Space- or comma-separated keywords; trigram-assisted match on title/address with description substring fallback |
| latitude | float | Center lat for spatial search |
| longitude | float | Center lng for spatial search |
| radius_km | float | Radius in km (requires lat/lng) |
| sort_by | string | Sort field (price, net_price, relevance, created_at, date, beds/bedrooms) |
| sort_dir | string | asc or desc |
| eligible_only | bool | Only include properties with confirmed eligible grants |
| min_eligible_grants_total | float | Minimum confirmed eligible grant total |
| page | int | Page number (default: 1) |
| size | int | Page size (default: 20, max: 100) |

**Response** `200`
```json
{
  "items": [
    {
      "id": "uuid",
      "title": "3 Bed Semi-Detached House",
      "address": "123 Main St, Blackrock",
      "county": "Dublin",
      "price": 350000,
      "bedrooms": 3,
      "bathrooms": 2,
      "floor_area_sqm": 120.0,
      "property_type": "house",
      "ber_rating": "B2",
      "latitude": 53.3,
      "longitude": -6.17,
      "url": "https://daft.ie/...",
      "source_id": "uuid",
      "first_listed_at": "2024-01-15T10:00:00Z",
      "description": "..."
    }
  ],
  "total": 1234,
  "page": 1,
  "per_page": 20,
  "pages": 62
}
```

### GET /api/v1/properties/{id}
Get a single property by ID.

**Response** `200` — Property object | `404`

### GET /api/v1/properties/{id}/price-history
Get price change history for a property.

**Response** `200`
```json
[
  {
    "id": "uuid",
    "property_id": "uuid",
    "price": 350000,
    "price_change": -15000,
    "recorded_at": "2024-02-01T00:00:00Z"
  }
]
```

### GET /api/v1/properties/{id}/timeline
Get unified lifecycle and provenance events for a property.

### GET /api/v1/properties/{id}/intelligence
Get a consolidated payload containing property detail, price history, timeline, and retrieval documents.

### GET /api/v1/properties/{id}/brief
Get a structured decision brief for a single property.

### GET /api/v1/properties/{id}/similar
Get similar properties (same county, type, price range).

**Response** `200` — Array of Property objects

### GET /api/v1/properties/{id}/sold-comps
Get sold comparables for a property.

Strategy:
- Uses nearby sold records within 2km when the listing has coordinates.
- Falls back to county + fuzzy-address-hash + address similarity matching when coordinates are missing.

**Query Parameters**
| Param | Type | Description |
|-------|------|-------------|
| limit | int | Maximum comparable sales to return (default: 10, max: 30) |
| min_similarity | float | Minimum address similarity for fallback matching (default: 0.86) |

**Response** `200`
```json
{
  "property_id": "uuid",
  "strategy": "address_fuzzy",
  "items": [
    {
      "id": "uuid",
      "address": "12 Main Street",
      "county": "Dublin",
      "price": 320000,
      "sale_date": "2025-02-10",
      "match_method": "fuzzy_hash_county_address_similarity",
      "match_score": 0.94,
      "match_confidence": "medium"
    }
  ]
}
```

---

## Sold Properties

### GET /api/v1/sold
List sold property records from the Property Price Register.

**Query Parameters**
| Param | Type | Description |
|-------|------|-------------|
| county | string | Filter by county |
| min_price | int | Minimum sale price |
| max_price | int | Maximum sale price |
| address_contains | string | Case-insensitive substring match on sold address |
| min_year | int | Minimum sale year |
| max_year | int | Maximum sale year |
| lat | float | Center latitude for spatial filter |
| lng | float | Center longitude for spatial filter |
| radius_km | float | Radius in km when using spatial filter |
| sort_by | string | Accepted query parameter; current list payload is returned in service default order |
| sort_dir | string | Accepted query parameter; current list payload is returned in service default order |
| page | int | Page number |
| size | int | Page size |

### GET /api/v1/sold/nearby
Find sold properties near a location.

**Query Parameters**
| Param | Type |
|-------|------|
| latitude | float (required) |
| longitude | float (required) |
| radius_km | float (default: 5) |
| limit | int (default: 20) |

### GET /api/v1/sold/stats
Aggregated sold statistics.

**Query Parameters**
| Param | Type | Description |
|-------|------|-------------|
| county | string | Optional county filter |
| group_by | string | month, quarter, or year |

---

## Sources

### GET /api/v1/sources
List all configured data sources.

### POST /api/v1/sources
Create a new source.

**Body**
```json
{
  "name": "Daft.ie – National",
  "url": "https://www.daft.ie/property-for-sale/ireland",
  "adapter_type": "api",
  "adapter_name": "daft",
  "poll_interval_seconds": 900,
  "tags": [],
  "enabled": true,
  "config": {"county": null, "sale_type": "sale"}
}
```

### PATCH /api/v1/sources/{id}
Update a source.

### DELETE /api/v1/sources/{id}
Delete a source.

### GET /api/v1/sources/adapters
List available adapter types.

### POST /api/v1/sources/discover-auto?auto_enable=false&limit=25
Automatically discover and register missing feed/source candidates.

By default, discovered sources are created disabled with a `pending_approval` tag.

### GET /api/v1/sources/discovery/pending
List auto-discovered sources that are awaiting approval.

### POST /api/v1/sources/{id}/approve-discovered
Approve a discovered source and enable it for scheduled scraping.

### POST /api/v1/sources/{id}/reset-cursor
Reset the stored incremental-ingestion cursor for a source.

### POST /api/v1/sources/{id}/trigger
Manually trigger a scrape for this source. Sends a task to the SQS scrape queue.

**Response** `200`
```json
{"task_id": "sqs-message-id", "status": "dispatched"}
```

If queue URLs are unconfigured locally, this endpoint can process inline and return:

```json
{"status": "processed_inline", "result": {...}}
```

Unexpected queue runtime dispatch failures return `503` with structured error detail.

### POST /api/v1/sources/trigger-all
Trigger the full organic search pipeline in one request.

`scrape_all_sources` now performs source discovery at the start of each scrape run. By default,
discovered feeds remain disabled and tagged `pending_approval` until manually approved.

Default steps:
- `scrape_all_sources`
- `evaluate_alerts`
- `enrich_batch_llm`

Optional query params:
- `run_alerts=true|false` (default `true`)
- `run_llm_batch=true|false` (default `true`)
- `llm_limit=1..500` (default `50`)

**Response** `200`
```json
{
  "run_id": "f2f3f4c2-...",
  "status": "dispatched",
  "steps": [
    {"step": "scrape_all_sources", "status": "dispatched", "task_id": "..."},
    {"step": "evaluate_alerts", "status": "dispatched", "task_id": "..."},
    {"step": "enrich_batch_llm", "status": "dispatched", "task_id": "..."}
  ]
}
```

When the scrape step runs inline (local/no queue), `steps[0].result` includes:
- `discovery_during_scrape.created`
- `discovery_during_scrape.existing`
- `discovery_during_scrape.skipped_invalid`
- `discovery_during_scrape.auto_enable` (default `false`)

Worker env controls for discovery-during-scrape:
- `DISCOVERY_DURING_SCRAPE_ENABLED` (default `true`)
- `DISCOVERY_DURING_SCRAPE_AUTO_ENABLE` (default `false`)
- `DISCOVERY_DURING_SCRAPE_LIMIT` (default `10`, bounded)

### GET /api/v1/sources/trigger-all/history?limit=20
List recent full organic search runs from the shared backend ledger.

### POST /api/v1/sources/discover-full
Run the unified source and grant discovery crawler.

Query params:
- `dry_run=true|false`
- `follow_links=true|false`
- `limit=1..500`
- `include_grants=true|false`

**Response** `200`
```json
[
  {
    "id": "f2f3f4c2-...",
    "status": "mixed",
    "triggered_from": "api_sources_trigger_all",
    "options": {"run_alerts": true, "run_llm_batch": true, "llm_limit": 50},
    "steps": [
      {"step": "scrape_all_sources", "status": "processed_inline"},
      {"step": "evaluate_alerts", "status": "dispatched", "task_id": "..."}
    ],
    "error": null,
    "created_at": "2026-03-08T04:20:12.123456+00:00"
  }
]
```

---

## Analytics

### GET /api/v1/analytics/summary
Overall market summary statistics.

### GET /api/v1/analytics/county-stats
Price statistics per county.

### GET /api/v1/analytics/price-trends?county=Dublin
Monthly average prices from sold data.

### GET /api/v1/analytics/type-distribution?county=Dublin
Property type breakdown.

### GET /api/v1/analytics/ber-distribution?county=Dublin
BER rating distribution.

### GET /api/v1/analytics/heatmap
County-level centroid data with average prices for map heatmap.

---

## Alerts

### GET /api/v1/alerts
List alerts with pagination and filtering.

**Query Parameters**: alert_type, acknowledged, page, size

### GET /api/v1/alerts/stats
Alert type breakdown counts.

### GET /api/v1/alerts/unread-count
Count of unacknowledged alerts.

### PATCH /api/v1/alerts/{id}/acknowledge
Mark an alert as read.

### POST /api/v1/alerts/acknowledge-all
Mark all alerts as read.

---

## Saved Searches

### GET /api/v1/saved-searches
List saved search criteria.

### POST /api/v1/saved-searches
Create a saved search (used for alert matching).

**Body**
```json
{
  "name": "Dublin 3-bed under 400k",
  "criteria": {
    "county": "Dublin",
    "min_beds": 3,
    "max_price": 400000,
    "property_types": ["house"]
  },
  "alerts_enabled": true
}
```

### PUT /api/v1/saved-searches/{id}
Update a saved search.

### DELETE /api/v1/saved-searches/{id}
Delete a saved search.

---

## LLM / AI

### GET /api/v1/llm/config
Get current LLM configuration.

**Response** `200`
```json
{
  "enabled": true,
  "provider": "bedrock",
  "model": "anthropic.claude-3-haiku-20240307-v1:0"
}
```

### PUT /api/v1/llm/config
Update LLM configuration. Stored in DynamoDB for persistence.

**Body**
```json
{
  "provider": "bedrock",
  "bedrock_model": "amazon.nova-micro-v1:0"
}
```

### GET /api/v1/llm/health
Check LLM provider availability and enablement status.

**Response** `200` (enabled)
```json
{
  "enabled": true,
  "provider": "bedrock",
  "model": "anthropic.claude-3-haiku-20240307-v1:0",
  "healthy": true
}
```

**Response** `200` (disabled)
```json
{
  "enabled": false,
  "provider": "bedrock",
  "model": "anthropic.claude-3-haiku-20240307-v1:0",
  "healthy": false,
  "reason": "llm_disabled"
}
```

### POST /api/v1/llm/enrich/{property_id}
Trigger AI enrichment for a property. Sends a task to the SQS LLM queue.

**Response** `200`
```json
{"task_id": "sqs-message-id", "status": "dispatched"}
```

**Error responses**
- `404` if property does not exist
- `503` if LLM is disabled
- `503` if LLM queue URL is not configured

### POST /api/v1/llm/enrich-batch
Trigger AI enrichment for all un-enriched properties.

**Response** `200`
```json
{"task_id": "sqs-message-id", "status": "dispatched", "limit": 50}
```

### GET /api/v1/llm/enrichment/{property_id}
Fetch stored LLM enrichment for a property.

**Response** `200`
```json
{
  "id": "uuid",
  "property_id": "uuid",
  "summary": "...",
  "value_score": 7.6,
  "pros": ["..."],
  "cons": ["..."],
  "llm_provider": "bedrock",
  "llm_model": "anthropic.claude-3-haiku-20240307-v1:0"
}
```

### POST /api/v1/llm/compare-set
Compare 2-5 properties and return ranked metrics plus LLM narrative.

**Body**
```json
{
  "property_ids": ["id-1", "id-2"],
  "ranking_mode": "hybrid"
}
```

### POST /api/v1/llm/auto-compare
Run a server-driven comparison for the active workspace session and persist a run ledger row.

Validation rules:
- `session_id`: required, 1..120 chars
- `property_ids`: required, 2..5 entries
- `ranking_mode`: one of `llm_only | hybrid | user_weighted`

**Body**
```json
{
  "session_id": "session-abc",
  "property_ids": ["id-1", "id-2", "id-3"],
  "ranking_mode": "hybrid",
  "search_context": {
    "query": "dublin detached",
    "filters": {"max_price": 550000}
  }
}
```

**Response** `200`
```json
{
  "run_id": "run-123",
  "session_id": "session-abc",
  "cached": false,
  "result": {
    "ranking_mode": "hybrid",
    "winner_property_id": "id-1",
    "properties": [{"property_id": "id-1"}, {"property_id": "id-2"}],
    "analysis": {
      "headline": "Value result",
      "recommendation": "id-1",
      "key_tradeoffs": [],
      "confidence": "medium",
      "citations": []
    }
  }
}
```

When an identical `session_id + ranking_mode + property_ids` request is repeated and a completed run exists, the API may return the existing run with `"cached": true`.

### GET /api/v1/llm/auto-compare/latest?session_id={session_id}
Return the latest persisted auto-compare run for a session.

**Response** `200`
```json
{
  "run_id": "run-123",
  "status": "completed",
  "options": {
    "session_id": "session-abc",
    "ranking_mode": "hybrid",
    "property_ids": ["id-1", "id-2"]
  },
  "steps": [
    {"step": "compare_property_set", "status": "completed"}
  ],
  "result": {
    "ranking_mode": "hybrid",
    "winner_property_id": "id-1",
    "properties": [{"property_id": "id-1"}, {"property_id": "id-2"}],
    "analysis": {
      "headline": "Value result",
      "recommendation": "id-1",
      "key_tradeoffs": [],
      "confidence": "medium",
      "citations": []
    }
  },
  "error": null,
  "created_at": "2026-03-08T12:34:56.000000+00:00"
}
```

### Chat Endpoints
- `POST /api/v1/llm/chat/conversations`
- `GET /api/v1/llm/chat/conversations/{conversation_id}`
- `POST /api/v1/llm/chat/conversations/{conversation_id}/messages`
