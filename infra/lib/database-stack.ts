import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as rds from "aws-cdk-lib/aws-rds";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import { Construct } from "constructs";

export interface DatabaseStackProps extends cdk.StackProps {
  vpc: ec2.IVpc;
  dbSecret: secretsmanager.ISecret;
}

/**
 * Database stack: RDS PostgreSQL 16 (free tier) + DynamoDB config table.
 *
 * - RDS db.t3.micro: 750 hours/month free (12 months), 20GB storage
 * - DynamoDB: 25GB free forever, 25 RCU/WCU
 */
export class DatabaseStack extends cdk.Stack {
  public readonly dbInstance: rds.IDatabaseInstance;
  public readonly configTable: dynamodb.ITable;

  constructor(scope: Construct, id: string, props: DatabaseStackProps) {
    super(scope, id, props);

    const dbSecurityGroup = new ec2.SecurityGroup(this, "DbSg", {
      vpc: props.vpc,
      description: "Security group for RDS PostgreSQL",
      allowAllOutbound: false,
    });

    // RDS PostgreSQL 16 with PostGIS
    this.dbInstance = new rds.DatabaseInstance(this, "Postgres", {
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_16,
      }),
      instanceType: ec2.InstanceType.of(
        ec2.InstanceClass.T3,
        ec2.InstanceSize.MICRO
      ),
      vpc: props.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      securityGroups: [dbSecurityGroup],
      credentials: rds.Credentials.fromSecret(props.dbSecret),
      databaseName: "propertysearch",
      allocatedStorage: 20,
      maxAllocatedStorage: 20,
      storageType: rds.StorageType.GP3,
      multiAz: false,
      deletionProtection: false,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      backupRetention: cdk.Duration.days(7),
      publiclyAccessible: false,
    });

    // Allow Lambda (private subnets) to connect to RDS
    dbSecurityGroup.addIngressRule(
      ec2.Peer.ipv4(props.vpc.vpcCidrBlock),
      ec2.Port.tcp(5432),
      "Allow PostgreSQL from VPC"
    );

    // DynamoDB config table (replaces Redis for LLM config cache)
    this.configTable = new dynamodb.Table(this, "ConfigTable", {
      tableName: "property-search-config",
      partitionKey: { name: "config_key", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    new cdk.CfnOutput(this, "DbEndpoint", {
      value: this.dbInstance.dbInstanceEndpointAddress,
    });
    new cdk.CfnOutput(this, "ConfigTableName", {
      value: this.configTable.tableName,
    });
  }
}
