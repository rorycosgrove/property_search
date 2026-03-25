# Irish Property Research Dashboard

A comprehensive web-based platform for researching properties to buy across Ireland (Republic + Northern Ireland). Aggregates listings from multiple sources, provides map visualisation, price tracking, alerts, comparative analysis, and AI-powered insights on a low-ops AWS footprint.

![Stack](https://img.shields.io/badge/Python-3.12-blue) ![Stack](https://img.shields.io/badge/FastAPI-0.110-green) ![Stack](https://img.shields.io/badge/Next.js-16-black) ![Stack](https://img.shields.io/badge/AWS_Lambda-serverless-orange) ![Stack](https://img.shields.io/badge/Amazon_Bedrock-AI-purple) ![Stack](https://img.shields.io/badge/RDS_PostgreSQL-16+PostGIS-blue)

## Features

- **Multi-source aggregation** — Daft.ie, MyHome.ie, PropertyPal, Property Price Register, RSS feeds
- **Pluggable adapter system** — add new sources without modifying core code
- **Interactive map** — Leaflet/OSM with price labels, marker hover cards, and click-to-focus navigation
- **Price tracking** — historical price changes, drop/increase detection
- **Smart alerts** — new listings matching saved searches, price drops, status changes
- **Market analytics** — county stats, price trends, BER/type distribution, heatmap
- **AI enrichment** — property summaries, value scores, pros/cons via Amazon Bedrock, with the active model configurable at runtime
- **Modern map-first UI** — responsive panels, utility top nav, and mobile menu optimized for research workflows

## AWS Architecture

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| AWS Lambda | FastAPI backend + SQS workers | 1M requests/month |
| API Gateway (HTTP) | REST API routing | 1M requests/month |
| Amazon SQS | Task queues (scrape, LLM, alert) | 1M requests/month |
| Amazon RDS | PostgreSQL 16 + PostGIS | 750 hrs/month db.t3.micro |
| Amazon DynamoDB | Config cache (replaces Redis) | 25 GB free forever |
| Amazon Bedrock | AI enrichment and comparison workflows | Usage-based |
| AWS Amplify | Next.js SSR hosting | 1000 build-min + 15 GB/month |
| EventBridge | Scheduled tasks (scrape/alerts/PPR/cleanup) | Included |
| AWS CDK | Infrastructure as Code (TypeScript) | — |

## Quick Start

### Prerequisites

- **AWS CLI** configured with credentials (`aws configure`)
- **Node.js 20+** (for CDK and frontend)
- **Python 3.12+**
- **uv** package manager (used by Makefile commands, tests, and scripts)
- **Docker** (for local PostgreSQL only)

## Reliability Progress (Mar 2026)

The reliability-first stabilization plan is implemented and validated:

- Queue dispatch semantics unified (`dispatch_or_inline`) with typed dispatch failures (`QueueDispatchError`) and safer API error mapping.
- Worker ownership consolidated with compatibility shims in `packages/worker/service.py` delegating to canonical `apps/worker/tasks.py`.
- Backend logs operationalized through admin endpoints and repository queries.
- Health diagnostics expanded with `backend_errors_last_hour` signal.
- Migration safety and repository behavior reinforced with dedicated tests.
- Focused verification workflow added: `make test-cov-plan`.

See `docs/RELEASE_NOTES_MAR_2026.md` for implementation details and validation outcomes.

## Run/Deploy At A Glance

| Path | Entry Command | Typical Time | Ease | Notes |
|------|---------------|--------------|------|-------|
| Local (Windows) | `start-all.cmd` | 2-5 min first run, then ~1 min restarts | Easy | Best default for local development. Includes health checks and startup orchestration. |
| Local (Manual split) | `start-local-services.cmd` + `status-local.cmd` | 2-5 min | Moderate | Better for debugging separate API/web terminals. |
| Remote (AWS) | `python deploy.py` | 15-25 min | Moderate | Mostly automated, but Bedrock model access remains manual and production DB migrations require VPC-accessible execution. |

Practical assessment:
- Local is straightforward once prerequisites are installed.
- Remote deployment is practical and repeatable, but not fully one-click due to AWS account setup, Bedrock enablement, and the need to run production migrations from an environment that can reach the private RDS instance.

### Deploy to AWS

```bash
# 1. Clone & configure
git clone <repo-url> property_search
cd property_search

# 2. Run the interactive deploy script (installs deps, bootstraps CDK, deploys)
python deploy.py
```

Or step-by-step:

```bash
python deploy.py --check    # Verify prerequisites
python deploy.py --local    # Set up local dev only
python deploy.py --deploy   # Deploy only (deps already installed)
```

### Local Development

**Windows Users:** See [WINDOWS_SETUP.md](WINDOWS_SETUP.md) for detailed Windows setup instructions.

**Quick Start (Windows):**
```cmd
start-all.cmd
```

Alternative resilient launch (manual split windows):
```cmd
start-local-services.cmd
status-local.cmd
```

If ports/processes get stuck from previous sessions:
```cmd
stop-local.cmd
```

Launcher behavior on Windows:
- API starter cleans stale local API instances and chooses first free port from `8000, 8001, 8002`.
- Selected API port is written to `.dev-runtime/api-port.txt`.
- Web starter reads `.dev-runtime/api-port.txt` and sets `NEXT_PUBLIC_API_URL` automatically.

**Quick Start (Mac/Linux):**
```bash
# 1. Install Python deps
pip install -e ".[dev]"

# 2. Start local PostgreSQL
make up

# 3. Run database migrations
make migrate

# 4. Seed sources
python scripts/seed.py

# 5. Start API locally
uvicorn apps.api.main:app --reload --port 8000

# 6. Start frontend
cd web && npm install && npm run dev
```

Note: if `make` is unavailable in your environment, use direct equivalents such as:
- `docker compose up -d` instead of `make up`
- `uv run alembic upgrade head` instead of `make migrate`
- `uv run pytest -q` instead of `make test`

## Architecture

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design.

```
property_search/
├── packages/           # Business-logic modules
│   ├── shared/         # Config, logging, schemas, utils, SQS queue
│   ├── storage/        # ORM models, repositories, DB
│   ├── sources/        # Pluggable source adapters
│   ├── normalizer/     # Address normalization, geocoding, BER
│   ├── analytics/      # Market analytics engine
│   ├── alerts/         # Alert evaluation engine
│   └── ai/             # Amazon Bedrock LLM provider
├── apps/
│   ├── api/            # FastAPI REST API (Lambda + Mangum)
│   └── worker/         # SQS + EventBridge Lambda handlers
├── web/                # Next.js frontend (Amplify)
├── infra/              # AWS CDK infrastructure (TypeScript)
├── docker/             # Local dev Dockerfiles
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
| [SOURCES.md](docs/SOURCES.md) | Source adapter system & how to add adapters |
| [AWS_DEPLOYMENT.md](docs/AWS_DEPLOYMENT.md) | AWS deployment guide, CDK stacks, costs |
| [QUICKSTART.md](docs/QUICKSTART.md) | Get running in under 5 minutes |
| [CURRENT_STATUS.md](docs/CURRENT_STATUS.md) | Current operational status and known constraints |

## Deployment Notes

- Local development migrations run with `make migrate` or `uv run alembic upgrade head`.
- The current public API does not expose migration endpoints. For AWS deployments, run Alembic from an environment with network access to the private RDS instance before seeding or validating the application.
- `scripts/seed.py` and the source-management API both require `url`, `adapter_type`, and `adapter_name` for each source.

## License

MIT
