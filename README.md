# Irish Property Research Dashboard

A comprehensive web-based platform for researching properties to buy across Ireland (Republic + Northern Ireland). Aggregates listings from multiple sources, provides map visualisation, price tracking, alerts, comparative analysis, and AI-powered insights.

![Stack](https://img.shields.io/badge/Python-3.12-blue) ![Stack](https://img.shields.io/badge/FastAPI-0.110-green) ![Stack](https://img.shields.io/badge/Next.js-14-black) ![Stack](https://img.shields.io/badge/PostgreSQL-16+PostGIS-blue) ![Stack](https://img.shields.io/badge/Redis-7-red) ![Stack](https://img.shields.io/badge/Celery-5.3-green)

## Features

- **Multi-source aggregation** — Daft.ie, MyHome.ie, PropertyPal, Property Price Register, RSS feeds
- **Pluggable adapter system** — add new sources without modifying core code
- **Interactive map** — Leaflet/OSM with price-label markers, spatial search
- **Price tracking** — historical price changes, drop/increase detection
- **Smart alerts** — new listings matching saved searches, price drops, status changes
- **Market analytics** — county stats, price trends, BER/type distribution, heatmap
- **AI enrichment** — property summaries, value scores, pros/cons via Ollama or OpenAI
- **Dark theme UI** — responsive, fast Next.js 14 frontend

## Quick Start

### Prerequisites

- Docker & Docker Compose v2
- (Optional) Ollama for local AI: `ollama pull llama3.1:8b`

### Launch

```bash
# 1. Clone & configure
cp .env.example .env
# Edit .env if needed (defaults work out of the box for Docker)

# 2. Start everything
docker compose up -d

# 3. Run initial setup (migrations + seed sources)
docker compose exec api python scripts/setup.py

# 4. Open the dashboard
open http://localhost:3000
```

The API is available at `http://localhost:8000` with docs at `/docs`.

### Local Development (no Docker)

```bash
# Install Python deps
pip install -e ".[dev]"

# Start Postgres + Redis (or use Docker for just those)
docker compose up -d postgres redis

# Run migrations
alembic upgrade head

# Seed sources
python scripts/seed.py

# Start API
uvicorn apps.api.main:app --reload --port 8000

# Start worker
celery -A apps.worker.celery_app worker -Q default -l info

# Start frontend
cd web && npm install && npm run dev
```

## Architecture

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design.

```
property_search/
├── packages/           # Business-logic modules
│   ├── shared/         # Config, logging, schemas, utils
│   ├── storage/        # ORM models, repositories, DB
│   ├── sources/        # Pluggable source adapters
│   ├── normalizer/     # Address normalization, geocoding, BER
│   ├── analytics/      # Market analytics engine
│   ├── alerts/         # Alert evaluation engine
│   └── ai/             # LLM providers (Ollama, OpenAI)
├── apps/
│   ├── api/            # FastAPI REST API
│   └── worker/         # Celery tasks & beat schedule
├── web/                # Next.js 14 frontend
├── docker/             # Dockerfiles & init scripts
├── scripts/            # Setup, seed, import scripts
├── tests/              # pytest suite
└── docs/               # Full documentation
```

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, module boundaries, data flow |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | Development setup, coding standards, workflow |
| [API.md](docs/API.md) | REST API reference (all endpoints) |
| [DATA_MODEL.md](docs/DATA_MODEL.md) | Database schema, relationships, indexes |
| [SOURCES.md](docs/SOURCES.md) | Source adapter system, writing custom adapters |
| [QUICKSTART.md](docs/QUICKSTART.md) | Step-by-step getting started guide |

## License

MIT
