import * as cdk from "aws-cdk-lib";
import * as amplify from "aws-cdk-lib/aws-amplify";
import { Construct } from "constructs";

export interface FrontendStackProps extends cdk.StackProps {
  apiUrl: string;
}

/**
 * Frontend stack: AWS Amplify for Next.js hosting.
 *
 * Amplify Free Tier:
 * - 1,000 build minutes/month
 * - 15 GB served/month
 * - 5 GB hosting/month
 *
 * Note: Amplify app must be connected to a Git repository via the
 * AWS Console after deployment. CDK creates the app configuration.
 */
export class FrontendStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: FrontendStackProps) {
    super(scope, id, props);

    const amplifyApp = new amplify.CfnApp(this, "AmplifyApp", {
      name: "PropertySearch",
      platform: "WEB_COMPUTE",
      environmentVariables: [
        {
          name: "NEXT_PUBLIC_API_URL",
          value: props.apiUrl,
        },
        {
          name: "_CUSTOM_IMAGE",
          value: "amplify:al2023",
        },
      ],
      buildSpec: cdk.Fn.sub(`version: 1
applications:
  - appRoot: web
    frontend:
      phases:
        preBuild:
          commands:
            - npm ci
        build:
          commands:
            - npm run build
      artifacts:
        baseDirectory: .next
        files:
          - "**/*"
      cache:
        paths:
          - node_modules/**/*
          - .next/cache/**/*
`),
    });

    // Main branch
    const mainBranch = new amplify.CfnBranch(this, "MainBranch", {
      appId: amplifyApp.attrAppId,
      branchName: "aws-serverless-migration",
      enableAutoBuild: true,
      framework: "Next.js - SSR",
      stage: "PRODUCTION",
    });

    new cdk.CfnOutput(this, "AmplifyAppId", {
      value: amplifyApp.attrAppId,
    });
    new cdk.CfnOutput(this, "AmplifyDefaultDomain", {
      value: `https://${mainBranch.branchName}.${amplifyApp.attrDefaultDomain}`,
    });
  }
}
