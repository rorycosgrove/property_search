"""Local SQS poller for development.

Consumes messages from configured queues and routes them through
apps.worker.sqs_handler.handler so local behavior mirrors Lambda workers.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

from apps.worker.sqs_handler import handler as sqs_handler


_RUNNING = True


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _on_signal(signum: int, _frame: Any) -> None:
    global _RUNNING
    _RUNNING = False
    print(f"[sqs-local-worker] received signal={signum}; shutting down", flush=True)


def _build_records(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for msg in messages:
        records.append(
            {
                "messageId": msg.get("MessageId"),
                "receiptHandle": msg.get("ReceiptHandle"),
                "body": msg.get("Body", "{}"),
                "attributes": msg.get("Attributes", {}),
                "messageAttributes": msg.get("MessageAttributes", {}),
                "eventSource": "aws:sqs",
            }
        )
    return records


def _poll_queue(client: Any, queue_name: str, queue_url: str) -> int:
    try:
        response = client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=5,
            WaitTimeSeconds=10,
            VisibilityTimeout=60,
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
        )
    except (ClientError, BotoCoreError) as exc:
        print(f"[sqs-local-worker] {queue_name} receive failed: {exc}", flush=True)
        return 0

    messages = response.get("Messages", [])
    if not messages:
        return 0

    processed = 0
    for msg in messages:
        event = {"Records": _build_records([msg])}
        result = sqs_handler(event, context=None)
        failed = int(result.get("failed", 0) or 0)

        if failed == 0:
            try:
                client.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=msg["ReceiptHandle"],
                )
            except (ClientError, BotoCoreError) as exc:
                print(
                    f"[sqs-local-worker] {queue_name} delete failed for {msg.get('MessageId')}: {exc}",
                    flush=True,
                )
                continue
            processed += 1
            task_type = "unknown"
            try:
                payload = json.loads(msg.get("Body", "{}"))
                task_type = payload.get("task_type", "unknown")
            except Exception:
                pass
            print(
                f"[sqs-local-worker] processed queue={queue_name} message={msg.get('MessageId')} task={task_type}",
                flush=True,
            )
        else:
            print(
                f"[sqs-local-worker] handler reported failure queue={queue_name} message={msg.get('MessageId')}; leaving for retry",
                flush=True,
            )

    return processed


def main() -> int:
    load_dotenv()

    if not _is_truthy(os.environ.get("LOCAL_USE_SQS")):
        print("[sqs-local-worker] LOCAL_USE_SQS is not enabled; exiting.", flush=True)
        return 0

    region = os.environ.get("AWS_REGION", "eu-west-1")
    queues = {
        "scrape": os.environ.get("SCRAPE_QUEUE_URL", ""),
        "llm": os.environ.get("LLM_QUEUE_URL", ""),
        "alert": os.environ.get("ALERT_QUEUE_URL", ""),
    }
    active_queues = {k: v for k, v in queues.items() if v}

    if not active_queues:
        print("[sqs-local-worker] No queue URLs configured; nothing to consume.", flush=True)
        return 1

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    client = boto3.client("sqs", region_name=region)

    print(
        f"[sqs-local-worker] started region={region} queues={','.join(active_queues.keys())}",
        flush=True,
    )

    idle_loops = 0
    while _RUNNING:
        processed_total = 0
        for queue_name, queue_url in active_queues.items():
            if not _RUNNING:
                break
            processed_total += _poll_queue(client, queue_name, queue_url)

        if processed_total == 0:
            idle_loops += 1
            # Keep output sparse while idle; print heartbeat every ~30s.
            if idle_loops % 3 == 0:
                print("[sqs-local-worker] idle; waiting for messages", flush=True)
        else:
            idle_loops = 0

        time.sleep(1)

    print("[sqs-local-worker] stopped", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
