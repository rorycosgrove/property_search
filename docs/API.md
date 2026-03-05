# API Reference

Base URL: `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs` (Swagger UI)

All endpoints return JSON. Errors use standard HTTP status codes with `{"detail": "message"}` body.

---

## Health

### GET /health
Check API and database health.

**Response** `200`
```json
{
  "status": "ok",
  "database": "connected"
}
```

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
| keywords | string | Full-text search in title/description |
| latitude | float | Center lat for spatial search |
| longitude | float | Center lng for spatial search |
| radius_km | float | Radius in km (requires lat/lng) |
| sort_by | string | Sort field (price, first_listed_at, updated_at) |
| sort_dir | string | asc or desc |
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
  "size": 20
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

### GET /api/v1/properties/{id}/similar
Get similar properties (same county, type, price range).

**Response** `200` — Array of Property objects

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
| property_type | string | house or apartment |
| page | int | Page number |
| size | int | Page size |

### GET /api/v1/sold/nearby
Find sold properties near a location.

**Query Parameters**
| Param | Type |
|-------|------|
| latitude | float (required) |
| longitude | float (required) |
| radius_km | float (default: 2) |
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
  "name": "Daft.ie – Dublin",
  "adapter_name": "daft",
  "enabled": true,
  "config": {"county": "dublin"}
}
```

### PUT /api/v1/sources/{id}
Update a source.

### DELETE /api/v1/sources/{id}
Delete a source.

### GET /api/v1/sources/adapters
List available adapter types.

### POST /api/v1/sources/{id}/trigger
Manually trigger a scrape for this source.

**Response** `202`
```json
{"task_id": "celery-task-uuid", "status": "queued"}
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

## LLM

### GET /api/v1/llm/config
Get current LLM provider configuration.

### PUT /api/v1/llm/config
Update LLM provider at runtime.

**Body**
```json
{"provider": "ollama", "model": "llama3.1:8b"}
```

### GET /api/v1/llm/health
Check LLM provider connectivity.

### GET /api/v1/llm/enrichment/{property_id}
Get existing AI enrichment for a property.

### POST /api/v1/llm/enrich/{property_id}
Trigger AI enrichment (async, returns task ID).

### POST /api/v1/llm/enrich-batch
Trigger batch enrichment for multiple properties.

**Body**
```json
{"property_ids": ["uuid1", "uuid2"]}
```

### POST /api/v1/llm/compare
Compare 2+ properties using AI.

**Body**
```json
{"property_ids": ["uuid1", "uuid2", "uuid3"]}
```

### GET /api/v1/llm/stats
LLM enrichment statistics (total enriched, provider breakdown).
