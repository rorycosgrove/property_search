"""
SQS message publisher utility.

Replaces Celery's .delay() and .apply_async() with SQS message dispatch.
Used by API routers and scheduler handlers to enqueue background tasks.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from packages.shared.logging import get_logger

logger = get_logger(__name__)

# Queue URLs are set via environment variables by CDK
_SCRAPE_QUEUE_URL = os.environ.get("SCRAPE_QUEUE_URL", "")
_LLM_QUEUE_URL = os.environ.get("LLM_QUEUE_URL", "")
_ALERT_QUEUE_URL = os.environ.get("ALERT_QUEUE_URL", "")

_sqs_client = None


def _get_sqs_client():
    global _sqs_client
    if _sqs_client is None:
        import boto3

        _sqs_client = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "eu-west-1"))
    return _sqs_client


def send_task(queue_name: str, task_type: str, payload: dict[str, Any] | None = None) -> str:
    """
    Send a task message to the specified SQS queue.

    Args:
        queue_name: One of 'scrape', 'llm', 'alert'.
        task_type: Task identifier (e.g., 'scrape_source', 'enrich_property').
        payload: Task arguments as a dict.

    Returns:
        The SQS MessageId.
    """
    queue_url = _resolve_queue_url(queue_name)
    if not queue_url:
        raise ValueError(f"No queue URL configured for '{queue_name}'. Set the env var.")

    message_id = str(uuid.uuid4())
    message_body = json.dumps(
        {
            "task_type": task_type,
            "task_id": message_id,
            "payload": payload or {},
        }
    )

    client = _get_sqs_client()
    kwargs: dict[str, Any] = {
        "QueueUrl": queue_url,
        "MessageBody": message_body,
    }
    if queue_url.endswith(".fifo"):
        kwargs["MessageGroupId"] = task_type
        kwargs["MessageDeduplicationId"] = message_id
    response = client.send_message(**kwargs)

    sqs_message_id = response.get("MessageId", message_id)
    logger.info(
        "sqs_task_sent",
        queue=queue_name,
        task_type=task_type,
        message_id=sqs_message_id,
    )
    return sqs_message_id


def _resolve_queue_url(queue_name: str) -> str:
    urls = {
        "scrape": _SCRAPE_QUEUE_URL or os.environ.get("SCRAPE_QUEUE_URL", ""),
        "llm": _LLM_QUEUE_URL or os.environ.get("LLM_QUEUE_URL", ""),
        "alert": _ALERT_QUEUE_URL or os.environ.get("ALERT_QUEUE_URL", ""),
    }
    return urls.get(queue_name, "")
