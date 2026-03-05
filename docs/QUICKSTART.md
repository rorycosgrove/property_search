# Quick Start Guide

Get the Irish Property Research Dashboard running in under 5 minutes.

## Prerequisites

- **Docker Desktop** (includes Docker Compose v2)
- **Git**
- (Optional) **Ollama** for local AI analysis

## Step 1: Clone & Configure

```bash
git clone <repo-url> property_search
cd property_search
cp .env.example .env
```

The default `.env` works with Docker out of the box. Optionally edit:
- `OPENAI_API_KEY` — if using OpenAI instead of Ollama
- `LLM_PROVIDER` — `ollama` (default) or `openai`

## Step 2: Start Services

```bash
docker compose up -d
```

This starts 7 services:
| Service | Port | Description |
|---------|------|-------------|
| postgres | 5432 | PostgreSQL 16 + PostGIS |
| redis | 6379 | Broker + cache |
| api | 8000 | FastAPI REST API |
| worker | — | Celery worker (scraping) |
| llm-worker | — | Celery worker (AI enrichment) |
| beat | — | Celery Beat scheduler |
| web | 3000 | Next.js frontend |

## Step 3: Initialize Database

```bash
docker compose exec api python scripts/setup.py
```

This runs migrations and seeds 5 default data sources (Daft.ie, MyHome.ie, PropertyPal ROI, PropertyPal NI, PPR).

## Step 4: Open the Dashboard

Navigate to **http://localhost:3000**

- **Map view** — Properties shown as price markers on an OpenStreetMap
- **Filter bar** — County, price range, bedrooms, type, keywords
- **Property feed** — Scrollable list on the left
- **Detail panel** — Click any property for full details + AI analysis

## Step 5: Trigger Initial Scrape

The scheduler triggers scrapes every 6 hours. To start immediately:

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/sources/{source_id}/trigger

# Or trigger all sources
docker compose exec api python -c "
from apps.worker.tasks import scrape_all_sources
scrape_all_sources.delay()
"
```

## Step 6: (Optional) Set Up AI Analysis

### Ollama (Local, Free)
```bash
# Install Ollama (https://ollama.ai)
ollama pull llama3.1:8b

# The default config points to localhost:11434
# If running in Docker, set OLLAMA_BASE_URL=http://host.docker.internal:11434
```

### OpenAI (Cloud)
1. Add `OPENAI_API_KEY=sk-...` to `.env`
2. In the dashboard, go to **Settings** → change provider to OpenAI

## What Happens Automatically

Once running, the system:
1. **Every 6 hours** — Scrapes all enabled sources for new/updated listings
2. **15 minutes after scrapes** — Evaluates saved searches and generates alerts
3. **Weekly (Sunday 2am)** — Imports latest Property Price Register data
4. **Daily (3am)** — Cleans up old acknowledged alerts

## Next Steps

- Create **saved searches** to get alerts for properties matching your criteria
- Use the **Analytics** page for market insights
- Browse the **API docs** at http://localhost:8000/docs
- Read [ARCHITECTURE.md](ARCHITECTURE.md) for system design details
- Read [SOURCES.md](SOURCES.md) to add custom data source adapters
