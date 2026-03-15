from __future__ import annotations

from typing import Any

from packages.shared.constants import ALERT_CLEANUP_DAYS
from packages.shared.logging import get_logger

logger = get_logger(__name__)

def scrape_all_sources(force: bool = False) -> dict[str, Any]:
    """Deprecated shim: forward to canonical worker task implementation."""
    logger.warning(
        "worker_service_scrape_all_sources_deprecated",
        message="Use apps.worker.tasks.scrape_all_sources instead.",
    )
    from apps.worker.tasks import scrape_all_sources as task_scrape_all_sources

    return task_scrape_all_sources(force=force)

def evaluate_alerts() -> dict[str, int]:
    """Compatibility shim: delegate to canonical worker task implementation."""
    logger.warning(
        "worker_service_evaluate_alerts_deprecated",
        message="Use apps.worker.tasks.evaluate_alerts instead.",
    )
    from apps.worker.tasks import evaluate_alerts as task_evaluate_alerts

    return task_evaluate_alerts()

def enrich_property_llm(property_id: str) -> dict[str, Any]:
    """Compatibility shim: delegate to canonical worker task implementation."""
    logger.warning(
        "worker_service_enrich_property_deprecated",
        message="Use apps.worker.tasks.enrich_property_llm instead.",
    )
    from apps.worker.tasks import enrich_property_llm as task_enrich_property_llm

    return task_enrich_property_llm(property_id)

def enrich_batch_llm(limit: int = 10) -> dict[str, Any]:
    """Compatibility shim: delegate to canonical worker task implementation."""
    logger.warning(
        "worker_service_enrich_batch_deprecated",
        message="Use apps.worker.tasks.enrich_batch_llm instead.",
    )
    from apps.worker.tasks import enrich_batch_llm as task_enrich_batch_llm

    return task_enrich_batch_llm(limit)

def cleanup_old_alerts(days: int = ALERT_CLEANUP_DAYS) -> dict[str, int]:
    """Compatibility shim: delegate to canonical worker task implementation."""
    logger.warning(
        "worker_service_cleanup_alerts_deprecated",
        message="Use apps.worker.tasks.cleanup_old_alerts instead.",
    )
    from apps.worker.tasks import cleanup_old_alerts as task_cleanup_old_alerts

    return task_cleanup_old_alerts(days)
