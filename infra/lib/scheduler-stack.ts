import * as cdk from "aws-cdk-lib";
import * as events from "aws-cdk-lib/aws-events";
import * as targets from "aws-cdk-lib/aws-events-targets";
import * as sqs from "aws-cdk-lib/aws-sqs";
import { Construct } from "constructs";

export interface SchedulerStackProps extends cdk.StackProps {
  scrapeQueue: sqs.IQueue;
  llmQueue: sqs.IQueue;
  alertQueue: sqs.IQueue;
}

/**
 * Scheduler stack: EventBridge rules replacing Celery Beat.
 *
 * EventBridge sends JSON messages directly to SQS queues on a schedule.
 * This avoids the need for a separate scheduler Lambda.
 */
export class SchedulerStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: SchedulerStackProps) {
    super(scope, id, props);

    const scrapeMinute =
      this.node.tryGetContext("scrapeAllCronMinute") ??
      process.env.SCRAPE_ALL_CRON_MINUTE ??
      "0";
    const scrapeHour =
      this.node.tryGetContext("scrapeAllCronHour") ??
      process.env.SCRAPE_ALL_CRON_HOUR ??
      "*/6";
    const alertMinute =
      this.node.tryGetContext("evaluateAlertsCronMinute") ??
      process.env.EVALUATE_ALERTS_CRON_MINUTE ??
      "15";
    const alertHour =
      this.node.tryGetContext("evaluateAlertsCronHour") ??
      process.env.EVALUATE_ALERTS_CRON_HOUR ??
      scrapeHour;

    // Scrape all sources every 6 hours
    new events.Rule(this, "ScrapeAllRule", {
      ruleName: "property-search-scrape-all",
      schedule: events.Schedule.cron({ minute: scrapeMinute, hour: scrapeHour }),
      targets: [
        new targets.SqsQueue(props.scrapeQueue, {
          message: events.RuleTargetInput.fromObject({
            task_type: "scrape_all_sources",
            task_id: "scheduled",
            payload: {},
          }),
        }),
      ],
    });

    // Evaluate alerts 15 minutes after each scrape cycle
    new events.Rule(this, "EvaluateAlertsRule", {
      ruleName: "property-search-evaluate-alerts",
      schedule: events.Schedule.cron({ minute: alertMinute, hour: alertHour }),
      targets: [
        new targets.SqsQueue(props.alertQueue, {
          message: events.RuleTargetInput.fromObject({
            task_type: "evaluate_alerts",
            task_id: "scheduled",
            payload: {},
          }),
        }),
      ],
    });

    // Import PPR data weekly (Sunday 2am)
    new events.Rule(this, "ImportPprRule", {
      ruleName: "property-search-import-ppr",
      schedule: events.Schedule.cron({
        minute: "0",
        hour: "2",
        weekDay: "SUN",
      }),
      targets: [
        new targets.SqsQueue(props.scrapeQueue, {
          message: events.RuleTargetInput.fromObject({
            task_type: "import_ppr",
            task_id: "scheduled",
            payload: {},
          }),
        }),
      ],
    });

    // Cleanup old alerts daily at 3am
    new events.Rule(this, "CleanupAlertsRule", {
      ruleName: "property-search-cleanup-alerts",
      schedule: events.Schedule.cron({ minute: "0", hour: "3" }),
      targets: [
        new targets.SqsQueue(props.alertQueue, {
          message: events.RuleTargetInput.fromObject({
            task_type: "cleanup_old_alerts",
            task_id: "scheduled",
            payload: { days: 90 },
          }),
        }),
      ],
    });

    // Discover new source/feed candidates daily at 4am (approval required before enablement)
    new events.Rule(this, "DiscoverSourcesRule", {
      ruleName: "property-search-discover-sources",
      schedule: events.Schedule.cron({ minute: "0", hour: "4" }),
      targets: [
        new targets.SqsQueue(props.scrapeQueue, {
          message: events.RuleTargetInput.fromObject({
            task_type: "discover_sources",
            task_id: "scheduled",
            payload: { auto_enable: false, limit: 25 },
          }),
        }),
      ],
    });
  }
}
