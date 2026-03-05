import * as cdk from "aws-cdk-lib";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as lambdaEventSources from "aws-cdk-lib/aws-lambda-event-sources";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as iam from "aws-cdk-lib/aws-iam";
import * as rds from "aws-cdk-lib/aws-rds";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import { Construct } from "constructs";

export interface WorkerStackProps extends cdk.StackProps {
  vpc: ec2.IVpc;
  dbSecret: secretsmanager.ISecret;
  dbInstance: rds.IDatabaseInstance;
  configTable: dynamodb.ITable;
}

/**
 * Worker stack: SQS queues + Lambda consumers.
 *
 * Three queues:
 * - Scrape queue: property scraping tasks (higher concurrency)
 * - LLM queue: Bedrock enrichment tasks (lower concurrency)
 * - Alert queue: alert evaluation tasks
 *
 * SQS: 1M requests/month free
 */
export class WorkerStack extends cdk.Stack {
  public readonly scrapeQueue: sqs.IQueue;
  public readonly llmQueue: sqs.IQueue;
  public readonly alertQueue: sqs.IQueue;

  constructor(scope: Construct, id: string, props: WorkerStackProps) {
    super(scope, id, props);

    // ── Dead Letter Queues ─────────────────────────────────────────────────
    const scrapeDlq = new sqs.Queue(this, "ScrapeDlq", {
      queueName: "property-search-scrape-dlq",
      retentionPeriod: cdk.Duration.days(14),
    });

    const llmDlq = new sqs.Queue(this, "LlmDlq", {
      queueName: "property-search-llm-dlq",
      retentionPeriod: cdk.Duration.days(14),
    });

    const alertDlq = new sqs.Queue(this, "AlertDlq", {
      queueName: "property-search-alert-dlq",
      retentionPeriod: cdk.Duration.days(14),
    });

    // ── Main Queues ────────────────────────────────────────────────────────
    this.scrapeQueue = new sqs.Queue(this, "ScrapeQueue", {
      queueName: "property-search-scrape",
      visibilityTimeout: cdk.Duration.minutes(10),
      deadLetterQueue: { queue: scrapeDlq, maxReceiveCount: 3 },
    });

    this.llmQueue = new sqs.Queue(this, "LlmQueue", {
      queueName: "property-search-llm",
      visibilityTimeout: cdk.Duration.minutes(5),
      deadLetterQueue: { queue: llmDlq, maxReceiveCount: 2 },
    });

    this.alertQueue = new sqs.Queue(this, "AlertQueue", {
      queueName: "property-search-alert",
      visibilityTimeout: cdk.Duration.minutes(5),
      deadLetterQueue: { queue: alertDlq, maxReceiveCount: 3 },
    });

    // ── Shared Lambda code ─────────────────────────────────────────────────
    const lambdaCode = lambda.Code.fromAsset("../", {
      exclude: [
        "infra/**",
        "web/**",
        "docker/**",
        ".git/**",
        "*.egg-info/**",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        ".next",
      ],
    });

    const commonEnv: Record<string, string> = {
      POSTGRES_HOST: props.dbInstance.dbInstanceEndpointAddress,
      POSTGRES_PORT: props.dbInstance.dbInstanceEndpointPort,
      POSTGRES_DB: "propertysearch",
      AWS_SECRETS_ARN: props.dbSecret.secretArn,
      DYNAMODB_CONFIG_TABLE: props.configTable.tableName,
      LLM_PROVIDER: "bedrock",
      BEDROCK_MODEL_ID: "amazon.titan-text-express-v1",
      SCRAPE_QUEUE_URL: this.scrapeQueue.queueUrl,
      LLM_QUEUE_URL: this.llmQueue.queueUrl,
      ALERT_QUEUE_URL: this.alertQueue.queueUrl,
      LOG_LEVEL: "INFO",
    };

    // ── Scrape Worker Lambda ───────────────────────────────────────────────
    const scrapeWorker = new lambda.Function(this, "ScrapeWorker", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "apps.worker.sqs_handler.handler",
      code: lambdaCode,
      vpc: props.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      memorySize: 512,
      timeout: cdk.Duration.minutes(5),
      environment: commonEnv,
      reservedConcurrentExecutions: 4,
    });

    scrapeWorker.addEventSource(
      new lambdaEventSources.SqsEventSource(this.scrapeQueue, {
        batchSize: 1,
      })
    );

    // ── LLM Worker Lambda ──────────────────────────────────────────────────
    const llmWorker = new lambda.Function(this, "LlmWorker", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "apps.worker.sqs_handler.handler",
      code: lambdaCode,
      vpc: props.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      memorySize: 256,
      timeout: cdk.Duration.minutes(3),
      environment: commonEnv,
      reservedConcurrentExecutions: 1,
    });

    llmWorker.addEventSource(
      new lambdaEventSources.SqsEventSource(this.llmQueue, {
        batchSize: 1,
      })
    );

    // ── Alert Worker Lambda ────────────────────────────────────────────────
    const alertWorker = new lambda.Function(this, "AlertWorker", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "apps.worker.sqs_handler.handler",
      code: lambdaCode,
      vpc: props.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      memorySize: 256,
      timeout: cdk.Duration.minutes(3),
      environment: commonEnv,
      reservedConcurrentExecutions: 2,
    });

    alertWorker.addEventSource(
      new lambdaEventSources.SqsEventSource(this.alertQueue, {
        batchSize: 1,
      })
    );

    // ── Grant permissions to all workers ────────────────────────────────────
    for (const fn of [scrapeWorker, llmWorker, alertWorker]) {
      props.dbSecret.grantRead(fn);
      props.configTable.grantReadWriteData(fn);

      fn.addToRolePolicy(
        new iam.PolicyStatement({
          actions: [
            "bedrock:InvokeModel",
            "bedrock:ListFoundationModels",
          ],
          resources: ["*"],
        })
      );

      // Workers need to send messages to other queues
      this.scrapeQueue.grantSendMessages(fn);
      this.llmQueue.grantSendMessages(fn);
      this.alertQueue.grantSendMessages(fn);
    }

    // ── Outputs ────────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, "ScrapeQueueUrl", {
      value: this.scrapeQueue.queueUrl,
    });
    new cdk.CfnOutput(this, "LlmQueueUrl", {
      value: this.llmQueue.queueUrl,
    });
    new cdk.CfnOutput(this, "AlertQueueUrl", {
      value: this.alertQueue.queueUrl,
    });
  }
}
