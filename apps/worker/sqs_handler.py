"""
AWS Lambda handler for SQS-triggered worker tasks.

Receives SQS events and routes them to the appropriate task function.
Replaces the Celery worker process.
"""

from __future__ import annotations

import json
from typing import Any

from packages.shared.logging import get_logger, setup_logging

logger = get_logger(__name__)

# Task registry — maps task_type strings to handler functions
_TASK_HANDLERS: dict[str, Any] = {}


def _register_handlers():
    """Lazily register task handlers to avoid import-time side effects."""
    if _TASK_HANDLERS:
        return

    from apps.worker.tasks import (
        cleanup_old_alerts,
        discover_all_sources,
        discover_sources,
        enrich_batch_llm,
        enrich_property_llm,
        evaluate_source_quality_governance,
        evaluate_alerts,
        import_ppr,
        materialize_market_documents_task,
        materialize_reference_documents_task,
        scrape_all_sources,
        scrape_source,
    )

    _TASK_HANDLERS.update(
        {
            "scrape_all_sources": scrape_all_sources,
            "discover_sources": discover_sources,
            "discover_all_sources": discover_all_sources,
            "scrape_source": scrape_source,
            "import_ppr": import_ppr,
            "evaluate_alerts": evaluate_alerts,
            "evaluate_source_quality_governance": evaluate_source_quality_governance,
            "enrich_property_llm": enrich_property_llm,
            "enrich_batch_llm": enrich_batch_llm,
            "materialize_market_documents": materialize_market_documents_task,
            "materialize_reference_documents": materialize_reference_documents_task,
            "cleanup_old_alerts": cleanup_old_alerts,
        }
    )


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for SQS events.

    Each SQS record contains a JSON body with:
        {"task_type": "...", "task_id": "...", "payload": {...}}
    """
    setup_logging()
    _register_handlers()

    results = []
    failed = 0

    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            task_type = body.get("task_type", "unknown")
            task_id = body.get("task_id", "")
            payload = body.get("payload", {})

            logger.info("sqs_task_received", task_type=task_type, task_id=task_id)

            handler_fn = _TASK_HANDLERS.get(task_type)
            if not handler_fn:
                logger.error("sqs_unknown_task", task_type=task_type)
                results.append({"task_id": task_id, "error": f"Unknown task: {task_type}"})
                failed += 1
                continue

            result = handler_fn(**payload)
            results.append({"task_id": task_id, "task_type": task_type, "result": result})
            logger.info("sqs_task_completed", task_type=task_type, task_id=task_id)

        except Exception as e:
            logger.error(
                "sqs_task_failed",
                error=str(e),
                record_id=record.get("messageId", ""),
            )
            failed += 1
            results.append({"error": str(e)})

    return {
        "statusCode": 200,
        "processed": len(results),
        "failed": failed,
        "results": results,
    }
