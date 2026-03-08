# Quick Start Guide

Get the Irish Property Research Dashboard running on AWS in under 10 minutes.

## Option A: Deploy to AWS (Recommended)

### Prerequisites

- **AWS CLI** configured with credentials (`aws configure`)
- **Node.js 20+**
- **Python 3.12+**
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

### Step 1: Set Up

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
```

### Step 2: Start Services

Recommended (Windows, resilient):

```bash
start-all.cmd
status-local.cmd
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

1. API health: `http://localhost:8000/health`
2. LLM health: `http://localhost:8000/api/v1/llm/health`
3. Frontend app: `http://localhost:3000`

If LLM is disabled (`llm_enabled=false`), `/api/v1/llm/health` returns `{"reason":"llm_disabled"}` and enrichment dispatch endpoints return `503`.

### Enable LLM Locally

1. Create/update `.env` in the repo root:
  - `LLM_ENABLED=true`
  - `AWS_REGION=eu-west-1` (or your Bedrock-enabled region)
  - `BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0` (recommended default)
2. Restart the API server so settings are reloaded.
3. Verify: `GET /api/v1/llm/health` returns `{"enabled":true,...}`.

Notes:
- Queue-backed enrichment dispatch (`POST /api/v1/llm/enrich/{property_id}`) also requires `LLM_QUEUE_URL` and AWS credentials.
- Without `LLM_QUEUE_URL`, enrichment dispatch returns `503` with an explicit queue configuration message.
- Ensure `LLM_QUEUE_URL` is present in the API process environment when launching `uvicorn` (for example, exported in your shell session before start).

## What Happens Automatically

Once deployed, the system:
1. **Every 6 hours** — Scrapes all enabled sources for new/updated listings
2. **15 minutes after scrapes** — Evaluates saved searches and generates alerts
3. **Weekly (Sunday 2am)** — Imports latest Property Price Register data
4. **Daily (3am)** — Cleans up old acknowledged alerts

All scheduling is handled by EventBridge rules dispatching to SQS queues.

## AI Enrichment

AI analysis uses **Amazon Bedrock** with free-tier models:
- **Amazon Titan Text Express** — General property enrichment
- **Amazon Nova Micro / Lite** — Lighter, faster alternatives

No API keys needed — Bedrock uses IAM credentials. Configure the model in **Settings** page or via the LLM config API.

## Next Steps

- Create **saved searches** to get alerts for properties matching your criteria
- Use the **Analytics** page for market insights
- Browse the **API docs** at `/docs` (Swagger UI)
- Read [ARCHITECTURE.md](ARCHITECTURE.md) for system design details
- Read [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md) for deployment configuration
- Read [SOURCES.md](SOURCES.md) to add custom data source adapters
