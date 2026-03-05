# Architecture

## Overview

Irish Property Research Dashboard follows a **modular monolith** architecture deployed on AWS serverless infrastructure. Business logic lives in isolated Python packages under `packages/`, while Lambda handlers (`apps/api`, `apps/worker`) orchestrate those packages. The Next.js frontend is hosted on AWS Amplify and communicates exclusively via the REST API through API Gateway.

## System Diagram

```
┌─────────────────┐     ┌─────────────────────────┐     ┌──────────────────┐
│  Next.js 14     │────▶│  API Gateway (HTTP API)  │────▶│  RDS PostgreSQL  │
│  (AWS Amplify)  │     │  → Lambda (FastAPI)      │     │  16 + PostGIS    │
└─────────────────┘     └──────────┬──────────────┘     └──────────────────┘
                                   │                              ▲
                                   │ send_task()                  │
                                   ▼                              │
                        ┌──────────────────────────┐              │
                        │  Amazon SQS              │              │
                        │  • scrape queue          │              │
                        │  • llm queue             │              │
                        │  • alert queue           │              │
                        └──────────┬───────────────┘              │
                                   │                              │
                        ┌──────────▼───────────────┐              │
                        │  Lambda Workers           │─────────────┘
                        │  (SQS event handlers)     │
                        │                           │──▶ Amazon Bedrock
                        └───────────────────────────┘    (Titan / Nova)
                                   ▲
                        ┌──────────┴───────────────┐
                        │  EventBridge Rules        │
                        │  (scheduler)              │     ┌───────────────┐
                        │  • scrape every 6h        │     │ DynamoDB      │
                        │  • alerts every 6h15m     │     │ (config cache)│
                        │  • PPR weekly             │     └───────────────┘
                        │  • cleanup daily          │
                        └──────────────────────────┘
```

## AWS Infrastructure (CDK Stacks)

| Stack | Resources |
|-------|-----------|
| `VpcStack` | VPC with public/private/isolated subnets, 1 NAT gateway |
| `SecretsStack` | Secrets Manager for RDS credentials |
| `DatabaseStack` | RDS PostgreSQL db.t3.micro + DynamoDB config table |
| `ApiStack` | Lambda (Python 3.12, 512 MB) + HTTP API Gateway with CORS |
| `WorkerStack` | 3 SQS queues (+ DLQs) + 3 Lambda consumers |
| `SchedulerStack` | 4 EventBridge rules → SQS |
| `FrontendStack` | Amplify app for Next.js SSR |

## Module Boundaries

### packages/shared
Configuration (Pydantic Settings), structured logging (structlog), Pydantic request/response schemas, Irish-specific utilities (county lists, eircode regex, BER ratings, address normalization). Includes `queue.py` for SQS message dispatch.

**Depends on:** Nothing (leaf module)

### packages/storage
SQLAlchemy 2.0 ORM models (7 tables), Repository classes, database session management. Uses PostGIS for spatial queries. Lambda-aware connection pooling (NullPool in Lambda, standard pool locally).

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
Amazon Bedrock LLM integration. `BedrockProvider` implements the abstract `LLMProvider` interface using Bedrock Runtime. Service layer handles provider config (stored in DynamoDB), prompt management, and response parsing. Supports property enrichment (summary, value score, pros/cons), market analysis, and property comparison.

Supported models: Amazon Titan Text Express, Amazon Titan Text Lite, Amazon Nova Micro, Amazon Nova Lite, Amazon Nova Pro.

**Depends on:** `shared` (config), `storage` (repositories)

### apps/api
FastAPI application wrapped with Mangum for Lambda deployment. Versioned REST API (`/api/v1/*`). Routers for properties, sold data, sources, analytics, alerts, saved searches, LLM operations, and health checks. CORS configured for Amplify domain.

**Depends on:** All packages

### apps/worker
Two Lambda handler modules:
- **`sqs_handler`** — Processes SQS events, routes tasks by `task_type` to handler functions (scraping, AI enrichment, alert evaluation)
- **`tasks.py`** — Pure Python task functions (no framework decorators), called by the SQS handler

**Depends on:** All packages

### web/
Next.js 14 frontend deployed on AWS Amplify. TypeScript, Tailwind CSS dark theme, Zustand state management. Components: interactive Leaflet map, property feed, filter bar, detail panel, analytics dashboard, alerts page, sources management, settings.

**Depends on:** API only (HTTP via API Gateway)

## Data Flow

### Scrape Pipeline
```
EventBridge (every 6h) → SQS (scrape queue)
  → Lambda worker: scrape_all_sources()
    → fan-out: send_task("scrape", "scrape_source", {source_id}) per source
      → Lambda worker: scrape_source(source_id)
        → adapter.fetch_listings() → adapter.parse_listing()
        → normalizer.normalize() → geocoder.geocode()
        → repository.upsert() (dedup via content_hash)
        → detect price changes → send_task("alert", "evaluate_alerts")
```

### Alert Pipeline
```
SQS (alert queue) → Lambda worker: evaluate_alerts()
  → for each active SavedSearch:
    → match new properties since last_matched_at
    → generate NEW_LISTING alerts
  → check_price_changes() → PRICE_DROP / PRICE_INCREASE alerts
  → check_status_changes() → SALE_AGREED / BACK_ON_MARKET alerts
```

### LLM Enrichment Pipeline
```
User triggers via API → send_task("llm", "enrich_property_llm", {property_id})
  → SQS (llm queue) → Lambda worker: enrich_property_llm()
    → fetch property + nearby sold comps
    → format prompt → BedrockProvider.generate()
    → parse JSON response → store LLMEnrichment
```

## Key Design Decisions

1. **Modular Monolith** — Simpler than microservices, clear boundaries, shared database. Can extract to services later.
2. **Repository Pattern** — Decouples ORM from business logic. Testable via mock repositories.
3. **Content Hash Dedup** — Each property gets a deterministic hash from URL. Updates detected via price/status changes.
4. **SQS Queue Separation** — Three queues (scrape, llm, alert) isolate workloads with independent concurrency and retry settings.
5. **Amazon Bedrock** — No API keys needed, uses IAM credentials. Free tier models (Titan, Nova) for property enrichment.
6. **DynamoDB Config Cache** — Replaces Redis for runtime LLM configuration storage. Serverless, pay-per-use, always-on.
7. **Lambda + NullPool** — Database connections use NullPool in Lambda to avoid connection leaks across invocations.
8. **PostGIS Spatial** — Native spatial queries for nearby property searches, market heatmaps.
9. **Pluggable Adapters** — New sources added by implementing `SourceAdapter` ABC and registering in code.
10. **CDK Infrastructure** — All AWS resources defined as TypeScript CDK stacks, version-controlled and reproducible.
