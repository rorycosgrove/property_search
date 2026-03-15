"""
SQS message publisher utility.

Replaces Celery's .delay() and .apply_async() with SQS message dispatch.
Used by API routers and scheduler handlers to enqueue background tasks.
"""

from __future__ import annotations

import json
import os
import time
import uuid
import hashlib
from typing import Any

from packages.shared.logging import get_logger

logger = get_logger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1

# Queue URLs are set via environment variables by CDK
_SCRAPE_QUEUE_URL = os.environ.get("SCRAPE_QUEUE_URL", "")
_LLM_QUEUE_URL = os.environ.get("LLM_QUEUE_URL", "")
_ALERT_QUEUE_URL = os.environ.get("ALERT_QUEUE_URL", "")

_sqs_client = None


class QueueDispatchError(Exception):
    """Raised when sending a task to a queue fails for non-config reasons."""

    def __init__(self, queue_name: str, task_type: str, cause: Exception):
        super().__init__(str(cause))
        self.queue_name = queue_name
        self.task_type = task_type
        self.cause = cause


def _get_sqs_client():
    global _sqs_client
    if _sqs_client is None:
        import boto3
        from botocore.config import Config

        _sqs_client = boto3.client(
            "sqs",
            region_name=os.environ.get("AWS_REGION", "eu-west-1"),
            config=Config(
                connect_timeout=2,
                read_timeout=3,
                retries={"max_attempts": 1},
            ),
        )
    return _sqs_client


def send_task(queue_name: str, task_type: str, payload: dict[str, Any] | None = None) -> str:
    """
    Send a task message to the specified SQS queue with retry logic.

    Args:
        queue_name: One of 'scrape', 'llm', 'alert'.
        task_type: Task identifier (e.g., 'scrape_source', 'enrich_property').
        payload: Task arguments as a dict.

    Returns:
        The SQS MessageId.

    Raises:
        ValueError: If queue URL is not configured.
        Exception: If all retry attempts fail.
    """
    queue_url = _resolve_queue_url(queue_name)
    if not queue_url:
        raise ValueError(f"No queue URL configured for '{queue_name}'. Set the env var.")

    resolved_payload = payload or {}
    message_id = str(uuid.uuid4())
    message_body = json.dumps(
        {
            "task_type": task_type,
            "task_id": message_id,
            "payload": resolved_payload,
        }
    )

    client = _get_sqs_client()
    kwargs: dict[str, Any] = {
        "QueueUrl": queue_url,
        "MessageBody": message_body,
    }
    if queue_url.endswith(".fifo"):
        kwargs["MessageGroupId"] = task_type
        kwargs["MessageDeduplicationId"] = _build_deduplication_id(task_type, resolved_payload)

    # Retry logic with exponential backoff
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.send_message(**kwargs)
            sqs_message_id = response.get("MessageId", message_id)
            logger.info(
                "sqs_task_sent",
                queue=queue_name,
                task_type=task_type,
                message_id=sqs_message_id,
                attempt=attempt + 1,
            )
            return sqs_message_id
        except Exception as e:
            last_error = e
            logger.warning(
                "sqs_send_failed",
                queue=queue_name,
                task_type=task_type,
                attempt=attempt + 1,
                error=str(e),
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS * (2 ** attempt))

    # All retries failed
    logger.error(
        "sqs_send_failed_all_retries",
        queue=queue_name,
        task_type=task_type,
        error=str(last_error),
    )
    raise Exception(f"Failed to send message after {MAX_RETRIES} attempts: {last_error}")


def is_queue_unconfigured_error(exc: Exception) -> bool:
    """Return True when dispatch failed because queue URL is not configured."""
    if not isinstance(exc, ValueError):
        return False
    return "no queue url configured" in str(exc).lower()


def dispatch_or_inline(
    queue_name: str,
    task_type: str,
    payload: dict[str, Any],
    inline_fn,
) -> dict[str, Any]:
    """Dispatch a task to queue, with inline fallback for queue misconfiguration only.

    Unexpected dispatch/runtime errors are re-raised for caller-specific handling.
    """
    try:
        task_id = send_task(queue_name, task_type, payload)
        return {
            "status": "dispatched",
            "task_id": task_id,
        }
    except Exception as exc:
        if not is_queue_unconfigured_error(exc):
            raise QueueDispatchError(queue_name, task_type, exc) from exc
        result = inline_fn(**payload)
        return {
            "status": "processed_inline",
            "result": result,
        }


def _resolve_queue_url(queue_name: str) -> str:
    urls = {
        "scrape": _SCRAPE_QUEUE_URL or os.environ.get("SCRAPE_QUEUE_URL", ""),
        "llm": _LLM_QUEUE_URL or os.environ.get("LLM_QUEUE_URL", ""),
        "alert": _ALERT_QUEUE_URL or os.environ.get("ALERT_QUEUE_URL", ""),
    }
    return urls.get(queue_name, "")


def _build_deduplication_id(task_type: str, payload: dict[str, Any]) -> str:
    """Build deterministic FIFO dedup key from task type + canonical payload."""
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{task_type}:{payload_json}".encode("utf-8")).hexdigest()
    return digest
