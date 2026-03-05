# Development Guide

## Prerequisites

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose v2
- PostgreSQL 16 with PostGIS (or use Docker)
- Redis 7 (or use Docker)
- (Optional) Ollama for local LLM

## Environment Setup

```bash
# 1. Copy environment config
cp .env.example .env

# 2. Install Python project in editable mode with dev deps
pip install -e ".[dev]"

# 3. Start infrastructure services
docker compose up -d postgres redis

# 4. Run database migrations
alembic upgrade head

# 5. Seed default sources
python scripts/seed.py

# 6. Install frontend dependencies
cd web && npm install && cd ..
```

## Running Locally

### API Server
```bash
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Celery Worker (default queue)
```bash
celery -A apps.worker.celery_app worker -Q default -l info -c 4
```

### Celery Worker (LLM queue)
```bash
celery -A apps.worker.celery_app worker -Q llm -l info -c 1
```

### Celery Beat (scheduler)
```bash
celery -A apps.worker.celery_app beat -l info
```

### Frontend
```bash
cd web && npm run dev
```

### All at once (via Make)
```bash
make dev  # starts API + worker + beat + frontend
```

## Project Structure

```
property_search/
├── packages/
│   ├── shared/         # Config, schemas, utils (leaf dependency)
│   │   ├── __init__.py
│   │   ├── config.py   # Pydantic Settings – all env vars
│   │   ├── logging.py  # structlog JSON logging
│   │   ├── schemas.py  # Request/response Pydantic models
│   │   └── utils.py    # Irish-specific utilities
│   ├── storage/        # Database layer
│   │   ├── __init__.py
│   │   ├── models.py   # SQLAlchemy ORM models (7 tables)
│   │   ├── database.py # Engine, sessions, FastAPI dependency
│   │   └── repositories.py  # Repository pattern classes
│   ├── sources/        # Source adapters
│   │   ├── __init__.py
│   │   ├── base.py     # Abstract SourceAdapter ABC
│   │   ├── daft.py     # Daft.ie scraper
│   │   ├── myhome.py   # MyHome.ie scraper
│   │   ├── propertypal.py  # PropertyPal scraper
│   │   ├── ppr.py      # Property Price Register CSV
│   │   ├── rss.py      # Generic RSS adapter
│   │   └── registry.py # Adapter discovery & registration
│   ├── normalizer/
│   │   ├── __init__.py
│   │   ├── normalizer.py  # RawListing → NormalizedProperty
│   │   ├── geocoder.py    # Nominatim geocoding
│   │   └── ber.py         # BER rating utilities
│   ├── analytics/
│   │   ├── __init__.py
│   │   └── engine.py   # Market analytics queries
│   ├── alerts/
│   │   ├── __init__.py
│   │   └── engine.py   # Alert evaluation logic
│   └── ai/
│       ├── __init__.py
│       ├── provider.py    # Abstract LLM provider
│       ├── ollama_provider.py
│       ├── openai_provider.py
│       ├── prompts.py     # Prompt templates
│       └── service.py     # High-level LLM operations
├── apps/
│   ├── api/
│   │   ├── main.py     # FastAPI app creation
│   │   └── routers/    # Endpoint routers (8 files)
│   └── worker/
│       ├── celery_app.py  # Celery configuration
│       └── tasks.py       # Task definitions
├── web/                # Next.js 14 frontend
│   ├── src/
│   │   ├── app/        # App router pages
│   │   ├── components/ # React components
│   │   └── lib/        # API client, stores, utils
│   └── package.json
├── tests/              # pytest test suite
├── scripts/            # Setup & import scripts
├── docker/             # Dockerfiles
├── docs/               # Documentation
├── .env.example
├── pyproject.toml
├── docker-compose.yml
└── Makefile
```

## Coding Standards

### Python
- **Type hints** on all function signatures
- **Pydantic v2** for all data validation
- **async/await** in API routes and adapters (httpx)
- **structlog** for all logging — never `print()`
- **Repository pattern** — never query ORM directly in routers/tasks
- **Docstrings** on all public classes and functions
- Follow PEP 8, enforced by ruff

### TypeScript / React
- **Strict TypeScript** — no `any` except API responses being typed
- **Functional components** with hooks
- **Zustand** for state management (no prop drilling)
- **Tailwind CSS** — no inline styles except dynamic values
- **Next.js App Router** — `page.tsx` for routes, `'use client'` for interactive components

### Git
- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- One logical change per commit
- Branch from `main`, PR to merge

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=packages --cov=apps --cov-report=html

# Run specific test file
pytest tests/test_normalizer.py -v

# Run specific test class
pytest tests/test_shared_utils.py::TestExtractCounty -v
```

## Adding a New Source Adapter

See [SOURCES.md](SOURCES.md) for detailed instructions.

1. Create `packages/sources/my_source.py`
2. Implement `SourceAdapter` ABC
3. Register in `packages/sources/registry.py`
4. Add a source record via API or seed script

## Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

## Docker

```bash
# Build and start all services
docker compose up -d --build

# View logs
docker compose logs -f api worker

# Run a command in the API container
docker compose exec api python scripts/setup.py

# Rebuild a single service
docker compose up -d --build api
```
