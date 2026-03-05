import * as cdk from "aws-cdk-lib";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigwv2 from "aws-cdk-lib/aws-apigatewayv2";
import * as apigwv2Integrations from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as iam from "aws-cdk-lib/aws-iam";
import * as rds from "aws-cdk-lib/aws-rds";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import { Construct } from "constructs";

export interface ApiStackProps extends cdk.StackProps {
  vpc: ec2.IVpc;
  dbSecret: secretsmanager.ISecret;
  dbInstance: rds.IDatabaseInstance;
  configTable: dynamodb.ITable;
  scrapeQueue: sqs.IQueue;
  llmQueue: sqs.IQueue;
  alertQueue: sqs.IQueue;
}

/**
 * API stack: Lambda + HTTP API Gateway.
 *
 * - Lambda runs FastAPI via Mangum adapter
 * - HTTP API Gateway: 1M requests/month free (12 months)
 * - Lambda: 1M requests + 400K GB-seconds/month free
 */
export class ApiStack extends cdk.Stack {
  public readonly apiUrl: string;

  constructor(scope: Construct, id: string, props: ApiStackProps) {
    super(scope, id, props);

    const apiFunction = new lambda.Function(this, "ApiFunction", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "apps.api.lambda_handler.handler",
      code: lambda.Code.fromAsset("../", {
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
      }),
      vpc: props.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      environment: {
        POSTGRES_HOST: props.dbInstance.dbInstanceEndpointAddress,
        POSTGRES_PORT: props.dbInstance.dbInstanceEndpointPort,
        POSTGRES_DB: "propertysearch",
        AWS_SECRETS_ARN: props.dbSecret.secretArn,
        DYNAMODB_CONFIG_TABLE: props.configTable.tableName,
        LLM_PROVIDER: "bedrock",
        BEDROCK_MODEL_ID: "amazon.titan-text-express-v1",
        LOG_LEVEL: "INFO",
        SCRAPE_QUEUE_URL: props.scrapeQueue.queueUrl,
        LLM_QUEUE_URL: props.llmQueue.queueUrl,
        ALERT_QUEUE_URL: props.alertQueue.queueUrl,
      },
    });

    // Grant permissions
    props.dbSecret.grantRead(apiFunction);
    props.configTable.grantReadWriteData(apiFunction);

    apiFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          "bedrock:InvokeModel",
          "bedrock:ListFoundationModels",
        ],
        resources: ["*"],
      })
    );

    props.scrapeQueue.grantSendMessages(apiFunction);
    props.llmQueue.grantSendMessages(apiFunction);
    props.alertQueue.grantSendMessages(apiFunction);

    // HTTP API Gateway
    const httpApi = new apigwv2.HttpApi(this, "HttpApi", {
      apiName: "PropertySearchApi",
      corsPreflight: {
        allowHeaders: ["Content-Type", "Authorization"],
        allowMethods: [
          apigwv2.CorsHttpMethod.GET,
          apigwv2.CorsHttpMethod.POST,
          apigwv2.CorsHttpMethod.PUT,
          apigwv2.CorsHttpMethod.PATCH,
          apigwv2.CorsHttpMethod.DELETE,
          apigwv2.CorsHttpMethod.OPTIONS,
        ],
        allowOrigins: ["*"],
      },
    });

    httpApi.addRoutes({
      path: "/{proxy+}",
      methods: [apigwv2.HttpMethod.ANY],
      integration: new apigwv2Integrations.HttpLambdaIntegration(
        "ApiIntegration",
        apiFunction
      ),
    });

    // Also handle root path
    httpApi.addRoutes({
      path: "/",
      methods: [apigwv2.HttpMethod.ANY],
      integration: new apigwv2Integrations.HttpLambdaIntegration(
        "ApiRootIntegration",
        apiFunction
      ),
    });

    this.apiUrl = httpApi.apiEndpoint;

    new cdk.CfnOutput(this, "ApiUrl", { value: this.apiUrl });
    new cdk.CfnOutput(this, "ApiFunctionArn", {
      value: apiFunction.functionArn,
    });
  }
}
