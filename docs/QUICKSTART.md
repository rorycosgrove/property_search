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

```bash
# API server
uvicorn apps.api.main:app --reload --port 8000

# Frontend (in another terminal)
cd web && npm install && npm run dev
```

### Step 3: Open the Dashboard

Navigate to **http://localhost:3000**

- **Map view** — Properties shown as price markers on an OpenStreetMap
- **Filter bar** — County, price range, bedrooms, type, keywords
- **Property feed** — Scrollable list on the left
- **Detail panel** — Click any property for full details + AI analysis

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
