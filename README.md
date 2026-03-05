# Irish Property Research Dashboard

A comprehensive web-based platform for researching properties to buy across Ireland (Republic + Northern Ireland). Aggregates listings from multiple sources, provides map visualisation, price tracking, alerts, comparative analysis, and AI-powered insights — all running on AWS serverless infrastructure within the free tier.

![Stack](https://img.shields.io/badge/Python-3.12-blue) ![Stack](https://img.shields.io/badge/FastAPI-0.110-green) ![Stack](https://img.shields.io/badge/Next.js-14-black) ![Stack](https://img.shields.io/badge/AWS_Lambda-serverless-orange) ![Stack](https://img.shields.io/badge/Amazon_Bedrock-AI-purple) ![Stack](https://img.shields.io/badge/RDS_PostgreSQL-16+PostGIS-blue)

## Features

- **Multi-source aggregation** — Daft.ie, MyHome.ie, PropertyPal, Property Price Register, RSS feeds
- **Pluggable adapter system** — add new sources without modifying core code
- **Interactive map** — Leaflet/OSM with price-label markers, spatial search
- **Price tracking** — historical price changes, drop/increase detection
- **Smart alerts** — new listings matching saved searches, price drops, status changes
- **Market analytics** — county stats, price trends, BER/type distribution, heatmap
- **AI enrichment** — property summaries, value scores, pros/cons via Amazon Bedrock (Titan / Nova models)
- **Dark theme UI** — responsive, fast Next.js 14 frontend

## AWS Architecture

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| AWS Lambda | FastAPI backend + SQS workers | 1M requests/month |
| API Gateway (HTTP) | REST API routing | 1M requests/month |
| Amazon SQS | Task queues (scrape, LLM, alert) | 1M requests/month |
| Amazon RDS | PostgreSQL 16 + PostGIS | 750 hrs/month db.t3.micro |
| Amazon DynamoDB | Config cache (replaces Redis) | 25 GB free forever |
| Amazon Bedrock | AI enrichment (Titan Text / Nova) | Free trial included |
| AWS Amplify | Next.js SSR hosting | 1000 build-min + 15 GB/month |
| EventBridge | Scheduled tasks (replaces Celery Beat) | Included |
| AWS CDK | Infrastructure as Code (TypeScript) | — |

## Quick Start

### Prerequisites

- **AWS CLI** configured with credentials (`aws configure`)
- **Node.js 20+** (for CDK and frontend)
- **Python 3.12+**
- **Docker** (for local PostgreSQL only)

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
├── web/                # Next.js 14 frontend (Amplify)
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

## License

MIT
