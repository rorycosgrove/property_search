# Architecture

## Overview

Irish Property Research Dashboard follows a **modular monolith** architecture, inspired by [World Dash](https://github.com/rorycosgrove/world-dash). Business logic lives in isolated Python packages under `packages/`, while applications (`apps/api`, `apps/worker`) orchestrate those packages. The Next.js frontend communicates exclusively via the REST API.

## System Diagram

```
┌─────────────┐     ┌──────────────────────┐     ┌────────────────┐
│  Next.js 14 │────▶│   FastAPI REST API    │────▶│  PostgreSQL 16 │
│  (port 3000)│     │   (port 8000)         │     │  + PostGIS     │
└─────────────┘     └──────────┬───────────┘     │  + pgvector    │
                               │                  └────────────────┘
                               │ enqueue tasks            ▲
                               ▼                          │
                    ┌──────────────────────┐              │
                    │   Redis 7            │              │
                    │   (broker + cache)   │              │
                    └──────────┬───────────┘              │
                               │                          │
                    ┌──────────▼───────────┐              │
                    │  Celery Workers       │──────────────┘
                    │  • default (scrape)   │
                    │  • llm (AI enrich)    │──▶ Ollama / OpenAI
                    │  • beat (scheduler)   │
                    └──────────────────────┘
```

## Module Boundaries

### packages/shared
Configuration (Pydantic Settings), structured logging (structlog), Pydantic request/response schemas, Irish-specific utilities (county lists, eircode regex, BER ratings, address normalization).

**Depends on:** Nothing (leaf module)

### packages/storage
SQLAlchemy 2.0 ORM models (7 tables), Repository classes, database session management. Uses PostGIS for spatial queries and pgvector for embeddings.

**Depends on:** `shared` (config, logging)

### packages/sources
Pluggable source adapter system. Abstract base class `SourceAdapter` defines the interface. Built-in adapters: Daft, MyHome, PropertyPal, PPR, RSS. Registry auto-discovers adapters and supports runtime registration.

**Depends on:** `shared` (config, utils)

### packages/normalizer
Converts raw scraped listings into canonical `NormalizedProperty` objects. Handles address normalization, county/eircode extraction, price parsing, bedroom/bathroom regex extraction, BER normalization. Includes Nominatim-based geocoder with rate limiting.

**Depends on:** `shared` (utils), `sources` (base types)

### packages/analytics
Market analytics engine. Computes county-level statistics, price trends from sold data, property type distribution, BER distribution, market heatmap data.

**Depends on:** `storage` (repositories, models)

### packages/alerts
Alert evaluation engine. Matches new properties against saved searches, detects price changes and status changes. Generates typed alerts (new_listing, price_drop, price_increase, sale_agreed, back_on_market).

**Depends on:** `storage` (repositories, models)

### packages/ai
Provider-agnostic LLM integration. Abstract `LLMProvider` with `OllamaProvider` and `OpenAIProvider` implementations. Service layer handles provider selection (configurable at runtime via Redis), prompt management, and response parsing. Supports property enrichment (summary, value score, pros/cons), market analysis, and property comparison.

**Depends on:** `shared` (config), `storage` (repositories)

### apps/api
FastAPI application with versioned REST API (`/api/v1/*`). Routers for properties, sold data, sources, analytics, alerts, saved searches, LLM operations, and health checks. CORS enabled, lifespan management.

**Depends on:** All packages

### apps/worker
Celery application with two worker types:
- **default** worker (concurrency=4): Scraping, normalization, geocoding, alert evaluation
- **llm** worker (concurrency=1): AI enrichment (resource-intensive)
- **beat** scheduler: Periodic tasks (scrape every 6h, alerts every 6h15m, PPR weekly, cleanup daily)

**Depends on:** All packages

### web/
Next.js 14 frontend. TypeScript, Tailwind CSS dark theme, Zustand state management. Components: interactive Leaflet map, property feed, filter bar, detail panel, analytics dashboard, alerts page, sources management, settings.

**Depends on:** API only (HTTP)

## Data Flow

### Scrape Pipeline
```
Beat Schedule → scrape_all_sources()
  → fan-out: scrape_source(source_id) per source
    → adapter.fetch_listings() → adapter.parse_listing()
    → normalizer.normalize() → geocoder.geocode()
    → repository.upsert() (dedup via content_hash)
    → detect price changes → chain: evaluate_alerts()
```

### Alert Pipeline
```
evaluate_alerts()
  → for each active SavedSearch:
    → match new properties since last_matched_at
    → generate NEW_LISTING alerts
  → check_price_changes() → PRICE_DROP / PRICE_INCREASE alerts
  → check_status_changes() → SALE_AGREED / BACK_ON_MARKET alerts
```

### LLM Enrichment Pipeline
```
User triggers → enrich_property_llm.apply_async(queue="llm")
  → fetch property + nearby sold comps
  → format prompt → provider.generate()
  → parse JSON response → store LLMEnrichment
```

## Key Design Decisions

1. **Modular Monolith** — Simpler than microservices, clear boundaries, shared database. Can extract to services later.
2. **Repository Pattern** — Decouples ORM from business logic. Testable via mock repositories.
3. **Content Hash Dedup** — Each property gets a deterministic hash from URL. Updates detected via price/status changes.
4. **Dual Celery Queues** — Separates CPU-bound scraping from GPU/API-bound LLM work.
5. **Provider-Agnostic LLM** — Runtime-switchable between Ollama (local, free) and OpenAI (cloud, paid) via Redis config.
6. **PostGIS Spatial** — Native spatial queries for nearby property searches, market heatmaps.
7. **Pluggable Adapters** — New sources added by implementing `SourceAdapter` ABC and registering in code or via entry points.
