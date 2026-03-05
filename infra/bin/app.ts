#!/usr/bin/env node
/**
 * CDK entry point — Irish Property Search AWS Infrastructure.
 *
 * Deploys the full serverless stack:
 *   VPC → Secrets → Database (RDS + DynamoDB) →
 *   Workers (SQS + Lambda) → API (Lambda + API Gateway) →
 *   Scheduler (EventBridge) → Frontend (Amplify)
 */

import * as cdk from "aws-cdk-lib";
import { VpcStack } from "../lib/vpc-stack";
import { DatabaseStack } from "../lib/database-stack";
import { SecretsStack } from "../lib/secrets-stack";
import { ApiStack } from "../lib/api-stack";
import { WorkerStack } from "../lib/worker-stack";
import { SchedulerStack } from "../lib/scheduler-stack";
import { FrontendStack } from "../lib/frontend-stack";

const app = new cdk.App();

const env: cdk.Environment = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || "eu-west-1",
};

const prefix = app.node.tryGetContext("prefix") || "ps";

// ── Networking ───────────────────────────────────────────────────────────────
const vpcStack = new VpcStack(app, `${prefix}-vpc`, { env });

// ── Secrets ──────────────────────────────────────────────────────────────────
const secretsStack = new SecretsStack(app, `${prefix}-secrets`, { env });

// ── Database (RDS PostgreSQL + PostGIS) ──────────────────────────────────────
const databaseStack = new DatabaseStack(app, `${prefix}-database`, {
  env,
  vpc: vpcStack.vpc,
  dbSecret: secretsStack.dbSecret,
});

// ── Workers (SQS queues + Lambda consumers) ──────────────────────────────────
const workerStack = new WorkerStack(app, `${prefix}-workers`, {
  env,
  vpc: vpcStack.vpc,
  dbSecret: secretsStack.dbSecret,
  dbInstance: databaseStack.dbInstance,
  configTable: databaseStack.configTable,
});

// ── API (Lambda + HTTP API Gateway) ──────────────────────────────────────────
const apiStack = new ApiStack(app, `${prefix}-api`, {
  env,
  vpc: vpcStack.vpc,
  dbSecret: secretsStack.dbSecret,
  dbInstance: databaseStack.dbInstance,
  configTable: databaseStack.configTable,
  scrapeQueue: workerStack.scrapeQueue,
  llmQueue: workerStack.llmQueue,
  alertQueue: workerStack.alertQueue,
});

// ── Scheduler (EventBridge rules) ────────────────────────────────────────────
const schedulerStack = new SchedulerStack(app, `${prefix}-scheduler`, {
  env,
  scrapeQueue: workerStack.scrapeQueue,
  llmQueue: workerStack.llmQueue,
  alertQueue: workerStack.alertQueue,
});

// ── Frontend (Amplify) ───────────────────────────────────────────────────────
const frontendStack = new FrontendStack(app, `${prefix}-frontend`, {
  env,
  apiUrl: apiStack.apiUrl,
});

// ── Tags ─────────────────────────────────────────────────────────────────────
cdk.Tags.of(app).add("Project", "PropertySearch");
cdk.Tags.of(app).add("ManagedBy", "CDK");
