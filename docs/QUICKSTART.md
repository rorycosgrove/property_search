# Quick Start Guide

Get the Irish Property Research Dashboard running locally or on AWS with a practical step-by-step path.

## Option A: Deploy to AWS (Recommended)

### Prerequisites

- **AWS CLI** configured with credentials (`aws configure`)
- **Node.js 20+**
- **Python 3.12+**
- **uv** package manager
- AWS account with Bedrock model access enabled in your region

### One-Command Deploy

```bash
git clone <repo-url> property_search
cd property_search
python deploy.py
```

The interactive script will:
1. Check prerequisites (Python, Node, AWS CLI, credentials)
2. Install all dependencies (Python, CDK, frontend)
3. Bootstrap CDK and deploy all 7 stacks
4. Run database migrations
5. Seed default property sources

### Manual Step-by-Step

#### Step 1: Clone & Install

```bash
git clone <repo-url> property_search
cd property_search

# Install CDK dependencies
cd infra && npm install && cd ..

# Install Python dependencies
pip install -e ".[dev]"
```

### Step 2: Deploy Infrastructure

```bash
# Bootstrap CDK (first time only)
cd infra && npx cdk bootstrap && cd ..

# Deploy all stacks
make deploy
```

CDK deploys 7 stacks:
| Stack | Resources |
|-------|-----------|
| VPC | Network with public/private/isolated subnets |
| Secrets | RDS credentials in Secrets Manager |
| Database | RDS PostgreSQL 16 (db.t3.micro, free tier) + DynamoDB |
| API | Lambda + HTTP API Gateway |
| Worker | 3 SQS queues + 3 Lambda workers |
| Scheduler | EventBridge rules (scrape, alerts, PPR, cleanup) |
| Frontend | Amplify app for Next.js |

### Step 3: Initialize Database

```bash
# The API URL is printed in CDK output
# Run migrations via the admin endpoint:
curl -X POST https://<api-gateway-url>/api/v1/admin/migrate
```

### Step 4: Access the Dashboard

- **Frontend** — Amplify URL (printed in CDK output)
- **API docs** — `https://<api-gateway-url>/docs` (Swagger UI)

### Step 5: Seed Sources

```bash
curl -X POST https://<api-url>/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{"name":"Daft.ie","adapter_name":"daft","enabled":true,"config":{}}'
```

## Option B: Local Development

### Prerequisites

- **Docker** (for PostgreSQL)
- **Python 3.12+**
- **Node.js 20+**
- **uv** package manager

### Step 1: First-Time Local Setup

```bash
git clone <repo-url> property_search
cd property_search

# Install Python deps
pip install -e ".[dev]"

# Start local PostgreSQL
make up

# Run migrations and seed data
make migrate
python scripts/seed.py

# Optional: install frontend deps once
cd web && npm install && cd ..
```

### Step 2: Start Services

Recommended (Windows, resilient):

```bash
start-all.cmd
status-local.cmd
```

`start-all.cmd` launches API, web, and the local SQS worker window.

Repeat-start path after first-time setup:

```cmd
start-all.cmd
```

```bash
# API server (Windows)
start-api-llm.cmd

# API server (Mac/Linux)
uvicorn apps.api.main:app --reload --port 8000

# Frontend (in another terminal)
cd web && npm install && start-dev.cmd
```

The Windows launchers are resilient:
- They clean stale local processes before startup.
- API auto-selects a free port from `8000, 8001, 8002` and writes `.dev-runtime/api-port.txt`.
- Web launcher reads that file and points `NEXT_PUBLIC_API_URL` to the active API automatically.
- Local SQS worker window is started so dispatched `scrape/llm/alert` tasks are consumed.

If you are running with queue dispatch (`LOCAL_USE_SQS=1`) and need to restart only the worker:

```cmd
start-sqs-worker.cmd
```

If stale local processes are holding ports from previous runs:

```cmd
stop-local.cmd
```

Then relaunch API and frontend.

### Step 3: Open the Dashboard

Navigate to **http://localhost:3000**

- **Map view** — Price markers with smooth click-to-focus behavior
- **Marker hover cards** — Image, price, address, beds/baths/area, BER, value score
- **Top navigation** — Responsive utility nav with active route highlighting and mobile menu
- **Workspace controls** — Toggle list and analysis panels to prioritize map area on smaller screens

### Launch Verification (Local)

After starting services, verify:

1. API health: `http://localhost:8000/health` (or selected API port from `.dev-runtime/api-port.txt`)
2. LLM health: `http://localhost:8000/api/v1/llm/health`
3. Frontend app: `http://localhost:3000`
4. Optional focused reliability checks: `make test-cov-plan`
5. Queue visibility and worker health: `status-local.cmd`

If LLM is disabled (`llm_enabled=false`), `/api/v1/llm/health` reports disabled state and enrichment dispatch endpoints return `503`.

### Enable LLM Locally

1. Create/update `.env` in the repo root:
  - `LLM_ENABLED=true`
  - `AWS_REGION=eu-west-1` (or your Bedrock-enabled region)
  - `BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0` (recommended default)
2. Restart the API server so settings are reloaded.
3. Verify: `GET /api/v1/llm/health` returns `{"enabled":true,...}`.

Notes:
- Queue-backed enrichment dispatch (`POST /api/v1/llm/enrich/{property_id}`) requires AWS credentials.
- If `LLM_QUEUE_URL` is not configured, enrich endpoints fall back to inline processing for queue-misconfiguration cases.
- Unexpected queue runtime failures return `503` with structured dispatch-failure details.

### Local SQS + Retrieval Document Refresh

When running local SQS dispatch mode, these environment variables are recommended:

- `LOCAL_USE_SQS=1`
- `SCRAPE_QUEUE_URL`, `LLM_QUEUE_URL`, `ALERT_QUEUE_URL`
- `REFERENCE_DOCUMENT_REFRESH_ON_SCRAPE=1` to enqueue `materialize_reference_documents` after scrape dispatch.

If you see DB errors mentioning missing `property_documents`, run migrations:

```bash
python -m alembic upgrade head
```

If geospatial functions fail, ensure PostGIS is installed/enabled for your local DB:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

## What Happens Automatically

Once deployed, the system:
1. **Every 6 hours** — Scrapes all enabled sources for new/updated listings
2. **15 minutes after scrapes** — Evaluates saved searches and generates alerts
3. **Weekly (Sunday 2am)** — Imports latest Property Price Register data
4. **Daily (3am)** — Cleans up old acknowledged alerts

All scheduling is handled by EventBridge rules dispatching to SQS queues.

## AI Enrichment

AI analysis uses **Amazon Bedrock** models configured through environment settings and the LLM configuration endpoints.

No API keys needed — Bedrock uses IAM credentials. Configure the model in **Settings** page or via the LLM config API.

## Next Steps

- Create **saved searches** to get alerts for properties matching your criteria
- Use the **Analytics** page for market insights
- Browse the **API docs** at `/docs` (Swagger UI)
- Read [ARCHITECTURE.md](ARCHITECTURE.md) for system design details
- Read [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md) for deployment configuration
- Read [SOURCES.md](SOURCES.md) to add custom data source adapters
