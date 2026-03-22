"""Health check endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from packages.shared.config import settings
from packages.shared.logging import get_logger
from packages.shared.schemas import HealthResponse, QualityGateMetric, QualityGatesResponse
from packages.storage.database import get_db_session
from packages.storage.repositories import BackendLogRepository, ConversationRepository

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db_session)):
    """System health check — verifies database and Bedrock connectivity."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        logger.warning("health_db_check_failed", error=str(exc))

    # Check Bedrock availability with bounded latency.
    # When LLM is disabled we consider Bedrock non-blocking for health checks.
    bedrock_ok = not settings.llm_enabled
    if settings.llm_enabled:
        try:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "bedrock",
                region_name=settings.aws_region,
                config=Config(connect_timeout=2, read_timeout=3, retries={"max_attempts": 1}),
            )
            response = client.list_foundation_models(byProvider="Amazon")
            bedrock_ok = len(response.get("modelSummaries", [])) > 0
        except Exception as exc:
            logger.warning("health_bedrock_check_failed", error=str(exc))
            bedrock_ok = False

    backend_errors_last_hour: int | None = None
    try:
        backend_errors_last_hour = BackendLogRepository(db).count_recent_errors(hours=1)
    except Exception as exc:
        logger.warning("health_backend_log_check_failed", error=str(exc))

    all_ok = db_ok and bedrock_ok
    return HealthResponse(
        status="healthy" if all_ok else "degraded",
        database="connected" if db_ok else "disconnected",
        bedrock="available" if bedrock_ok else "unavailable",
        backend_errors_last_hour=backend_errors_last_hour,
    )


@router.get("/api/v1/health/quality-gates", response_model=QualityGatesResponse)
def quality_gates(db: Session = Depends(get_db_session)):
    """Evaluate product quality gates for AI citation quality and reliability."""
    evaluated_at = datetime.now(UTC)

    metrics: list[QualityGateMetric] = []

    backend_errors = BackendLogRepository(db).count_recent_errors(hours=1)
    backend_ok = backend_errors <= settings.quality_gate_backend_errors_last_hour_max
    metrics.append(
        QualityGateMetric(
            key="backend_errors_last_hour",
            label="Backend errors (last hour)",
            actual=backend_errors,
            target=settings.quality_gate_backend_errors_last_hour_max,
            comparator="<=",
            status="pass" if backend_ok else "fail",
        )
    )

    chat_snapshot = ConversationRepository(db).assistant_message_quality_snapshot(hours=24)
    sample_size = int(chat_snapshot.get("sample_size") or 0)

    citation_coverage = chat_snapshot.get("citation_coverage")
    if sample_size < settings.quality_gate_min_assistant_messages_sample:
        citation_status = "warn"
        citation_note = "Insufficient assistant-message sample size for strict evaluation"
    elif citation_coverage is None:
        citation_status = "fail"
        citation_note = "No citation coverage data available"
    else:
        citation_status = (
            "pass"
            if float(citation_coverage) >= settings.quality_gate_chat_citation_coverage_min
            else "fail"
        )
        citation_note = None

    metrics.append(
        QualityGateMetric(
            key="chat_citation_coverage_24h",
            label="Chat citation coverage (24h)",
            actual=float(citation_coverage) if citation_coverage is not None else None,
            target=settings.quality_gate_chat_citation_coverage_min,
            comparator=">=",
            status=citation_status,
            sample_size=sample_size,
            note=citation_note,
        )
    )

    p95_latency = chat_snapshot.get("p95_latency_ms")
    if sample_size < settings.quality_gate_min_assistant_messages_sample:
        latency_status = "warn"
        latency_note = "Insufficient assistant-message sample size for strict evaluation"
    elif p95_latency is None:
        latency_status = "fail"
        latency_note = "No latency samples available"
    else:
        latency_status = (
            "pass"
            if int(p95_latency) <= settings.quality_gate_chat_p95_latency_ms_max
            else "fail"
        )
        latency_note = None

    metrics.append(
        QualityGateMetric(
            key="chat_p95_latency_ms_24h",
            label="Chat p95 latency (24h)",
            actual=int(p95_latency) if p95_latency is not None else None,
            target=settings.quality_gate_chat_p95_latency_ms_max,
            comparator="<=",
            status=latency_status,
            sample_size=sample_size,
            note=latency_note,
        )
    )

    has_fail = any(metric.status == "fail" for metric in metrics)
    has_warn = any(metric.status == "warn" for metric in metrics)
    overall_status = "fail" if has_fail else "warn" if has_warn else "pass"

    return QualityGatesResponse(
        status=overall_status,
        evaluated_at=evaluated_at,
        metrics=metrics,
    )
