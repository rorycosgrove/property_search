# AWS Deployment Guide

## Overview

The Irish Property Research Dashboard runs entirely on AWS serverless infrastructure, designed to stay within the AWS Free Tier. Infrastructure is defined as code using AWS CDK (TypeScript).

## Prerequisites

1. **AWS Account** with Free Tier eligibility
2. **AWS CLI** installed and configured: `aws configure`
3. **Node.js 20+** (for CDK)
4. **Python 3.12+** (for Lambda packaging)
5. **Docker** (for building Lambda container images)
6. **Amazon Bedrock** model access enabled in your region (eu-west-1 by default)

### Enable Bedrock Model Access

1. Go to the [Amazon Bedrock console](https://console.aws.amazon.com/bedrock)
2. Navigate to **Model access** in the left sidebar
3. Click **Manage model access**
4. Enable: Amazon Titan Text Express, Amazon Titan Text Lite, Amazon Nova Micro
5. Click **Save changes**

## CDK Stacks

All infrastructure is defined in `infra/lib/`:

| Stack | File | Resources |
|-------|------|-----------|
| VPC | `vpc-stack.ts` | VPC, 2 AZs, public/private/isolated subnets, fck-nat instance |
| Secrets | `secrets-stack.ts` | Secrets Manager secret for RDS credentials |
| Database | `database-stack.ts` | RDS PostgreSQL 16 db.t3.micro + DynamoDB config table |
| API | `api-stack.ts` | Lambda (512 MB, 30s) + HTTP API Gateway with CORS |
| Worker | `worker-stack.ts` | 3 SQS queues (scrape/llm/alert) + DLQs + 3 Lambda consumers |
| Scheduler | `scheduler-stack.ts` | 4 EventBridge rules → SQS targets |
| Frontend | `frontend-stack.ts` | Amplify app for Next.js SSR |

## Deployment

### First-Time Setup

```bash
# Install CDK dependencies
cd infra && npm install

# Bootstrap CDK (creates S3 bucket + IAM roles for CDK)
npx cdk bootstrap

# Return to project root
cd ..
```

### Deploy All Stacks

```bash
make deploy
# or: cd infra && npx cdk deploy --all --require-approval broadening
```

CDK will:
1. Package Python code as zip assets (via `Code.fromAsset`)
2. Create all AWS resources in dependency order
3. Output the API Gateway URL and Amplify app URL

### Preview Changes

```bash
make diff
```

### Synthesize CloudFormation (Debug)

```bash
make synth
```

### Tear Down

```bash
make destroy
# or: cd infra && npx cdk destroy --all
```

> **Warning:** This deletes all resources including the RDS database. Data will be lost.

## Environment Variables

Lambda functions receive their configuration via environment variables set by CDK:

| Variable | Description | Set By |
|----------|-------------|--------|
| `POSTGRES_HOST` | RDS endpoint hostname | CDK |
| `POSTGRES_PORT` | RDS port | CDK |
| `POSTGRES_DB` | Database name | CDK |
| `AWS_SECRETS_ARN` | Secrets Manager ARN (DB credentials) | CDK |
| `SCRAPE_QUEUE_URL` | SQS scrape queue URL | CDK |
| `LLM_QUEUE_URL` | SQS LLM queue URL | CDK |
| `ALERT_QUEUE_URL` | SQS alert queue URL | CDK |
| `DYNAMODB_CONFIG_TABLE` | DynamoDB table name | CDK |
| `LLM_PROVIDER` | LLM provider (`bedrock`) | CDK |
| `BEDROCK_MODEL_ID` | Default Bedrock model | CDK |
| `LOG_LEVEL` | Logging level | CDK |

## Free Tier Coverage

| Service | Free Tier Allowance | Expected Usage |
|---------|-------------------|----------------|
| Lambda | 1M requests + 400K GB-s/month | ~10K requests/month |
| API Gateway (HTTP) | 1M requests/month | ~10K requests/month |
| SQS | 1M requests/month | ~5K messages/month |
| RDS PostgreSQL | 750 hrs/month db.t3.micro | Always-on (1 instance) |
| DynamoDB | 25 GB + 25 WCU/RCU forever | < 1 GB, minimal traffic |
| Bedrock | Free trial (varies by model) | ~1K invocations/month |
| Amplify | 1000 build-min + 15 GB hosting | Minimal |
| EventBridge | Free (included) | 4 rules |
| Secrets Manager | $0.40/secret/month | 1 secret (~$0.40/month) |
| NAT (fck-nat) | **Not free** (~$3/month t4g.nano) | 1 instance |

> **Note:** The fck-nat t4g.nano instance is the main cost (~$3/month). This replaces the managed NAT Gateway (~$32/month) to keep costs minimal.

## Database Migrations

After deployment, run migrations via the admin API endpoint (Lambda has VPC access to RDS):

```bash
# Run migrations (API URL from CDK output)
curl -X POST https://<api-gateway-url>/api/v1/admin/migrate

# Check current revision
curl https://<api-gateway-url>/api/v1/admin/migrate/status

# Seed sources
curl -X POST https://<api-gateway-url>/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{"name":"Daft.ie","adapter_name":"daft","enabled":true,"config":{}}'
```

## Monitoring

- **Lambda logs** → CloudWatch Logs (auto-configured)
- **SQS DLQ** → Failed messages land in Dead Letter Queues for inspection
- **RDS metrics** → CloudWatch (CPU, connections, storage)
- **API Gateway** → CloudWatch access logs, latency metrics

## Troubleshooting

### Lambda timeout on scraping
Increase the worker Lambda timeout in `worker-stack.ts` (default: 300s). Some adapters may take longer to scrape.

### Database connection issues
Lambda uses `NullPool` to avoid connection pool leaks. If you see "too many connections", check the RDS `max_connections` parameter (default for db.t3.micro: ~80).

### Bedrock "Access Denied"
Ensure model access is enabled in the Bedrock console for your region. The IAM role needs `bedrock:InvokeModel` and `bedrock:ListFoundationModels` permissions (configured by CDK).

### SQS messages going to DLQ
Check the DLQ for error details. Common causes: Lambda timeout, database connection failure, adapter HTTP errors. Messages are retried 3 times before going to DLQ.
