# Development Guide

## Prerequisites

- Python 3.12+
- Node.js 20+
- Docker (for local PostgreSQL)
- AWS CLI configured with credentials (`aws configure`)
- (Optional) AWS CDK CLI: `npm install -g aws-cdk`

## Environment Setup

```bash
# 1. Install Python project in editable mode with dev deps
pip install -e ".[dev]"

# 2. Start local PostgreSQL with PostGIS
docker compose up -d

# 3. Run database migrations
make migrate

# 4. Seed default sources
python scripts/seed.py

# 5. Install frontend dependencies
cd web && npm install && cd ..
```

## Running Locally

### API Server
```bash
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd web && npm run dev
```

### Run a Task Manually (no SQS needed)
```bash
# Scrape all sources
python -c "from apps.worker.tasks import scrape_all_sources; scrape_all_sources()"

# Evaluate alerts
python -c "from apps.worker.tasks import evaluate_alerts; evaluate_alerts()"
```

### All at Once (via Make)
```bash
make up       # Start local PostgreSQL
make migrate  # Run migrations
make seed     # Seed sources
```

## Project Structure

```
property_search/
├── packages/
│   ├── shared/         # Config, schemas, utils (leaf dependency)
│   │   ├── config.py   # Pydantic Settings – all env vars
│   │   ├── logging.py  # structlog JSON logging
│   │   ├── schemas.py  # Request/response Pydantic models
│   │   ├── queue.py    # SQS message publisher utility
│   │   └── utils.py    # Irish-specific utilities
│   ├── storage/        # Database layer
│   │   ├── models.py   # SQLAlchemy ORM models (7 tables)
│   │   ├── database.py # Engine, sessions, Lambda-aware pooling
│   │   └── repositories.py  # Repository pattern classes
│   ├── sources/        # Source adapters
│   │   ├── base.py     # Abstract SourceAdapter ABC
│   │   ├── daft.py     # Daft.ie scraper
│   │   ├── myhome.py   # MyHome.ie scraper
│   │   ├── propertypal.py  # PropertyPal scraper
│   │   ├── ppr.py      # Property Price Register CSV
│   │   ├── rss.py      # Generic RSS adapter
│   │   └── registry.py # Adapter discovery & registration
│   ├── normalizer/
│   │   ├── normalizer.py  # RawListing → NormalizedProperty
│   │   ├── geocoder.py    # Nominatim geocoding
│   │   └── ber.py         # BER rating utilities
│   ├── analytics/
│   │   └── engine.py   # Market analytics queries
│   ├── alerts/
│   │   └── engine.py   # Alert evaluation logic
│   └── ai/
│       ├── provider.py        # Abstract LLM provider
│       ├── bedrock_provider.py # Amazon Bedrock implementation
│       ├── prompts.py         # Prompt templates
│       └── service.py         # High-level LLM operations
├── apps/
│   ├── api/
│   │   ├── main.py           # FastAPI app creation
│   │   ├── lambda_handler.py # Mangum wrapper for Lambda
│   │   └── routers/          # Endpoint routers (8 files)
│   └── worker/
│       ├── sqs_handler.py       # SQS event Lambda handler
│       └── tasks.py             # Task function definitions
├── web/                # Next.js 14 frontend
│   ├── src/
│   │   ├── app/        # App router pages
│   │   ├── components/ # React components
│   │   └── lib/        # API client, stores, utils
│   └── package.json
├── infra/              # AWS CDK infrastructure (TypeScript)
│   ├── bin/app.ts      # CDK entry point
│   └── lib/            # Stack definitions (7 stacks)
├── tests/              # pytest test suite
├── scripts/            # Setup & import scripts
├── docker/             # Local dev Dockerfiles
├── docs/               # Documentation
├── pyproject.toml
├── docker-compose.yml  # Local PostgreSQL only
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
make test

# Run with coverage
make test-cov

# Run specific test file
uv run pytest tests/test_normalizer.py -v

# Run specific test class
uv run pytest tests/test_shared_utils.py::TestExtractCounty -v
```

Tests use `unittest.mock` and `moto` to mock AWS services (SQS, Bedrock, DynamoDB) — no real AWS calls needed.

## Adding a New Source Adapter

See [SOURCES.md](SOURCES.md) for detailed instructions.

1. Create `packages/sources/my_source.py`
2. Implement `SourceAdapter` ABC
3. Register in `packages/sources/registry.py`
4. Add a source record via API or seed script

## Database Migrations

```bash
# Create a new migration
make migration msg="description"

# Apply migrations
make migrate

# Rollback one step
uv run alembic downgrade -1
```

## AWS CDK (Infrastructure)

```bash
# Synthesize CloudFormation templates
make synth

# Preview changes
make diff

# Deploy all stacks
make deploy

# Tear down all stacks
make destroy
```

See [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md) for the full deployment guide.
