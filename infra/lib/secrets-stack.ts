import * as cdk from "aws-cdk-lib";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import { Construct } from "constructs";

/**
 * Secrets Manager stack for database credentials.
 */
export class SecretsStack extends cdk.Stack {
  public readonly dbSecret: secretsmanager.ISecret;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    this.dbSecret = new secretsmanager.Secret(this, "DbSecret", {
      secretName: "property-search/db-credentials",
      description: "RDS PostgreSQL credentials for Property Search",
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ username: "propertysearch" }),
        generateStringKey: "password",
        excludePunctuation: true,
        passwordLength: 30,
      },
    });

    new cdk.CfnOutput(this, "DbSecretArn", { value: this.dbSecret.secretArn });
  }
}
