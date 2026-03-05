"""Health check endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from packages.shared.config import settings
from packages.shared.schemas import HealthResponse
from packages.storage.database import get_db_session

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db_session)):
    """System health check — verifies database and Bedrock connectivity."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    # Check Bedrock availability
    bedrock_ok = False
    try:
        import boto3
        client = boto3.client("bedrock", region_name=settings.aws_region)
        response = client.list_foundation_models(byProvider="Amazon")
        bedrock_ok = len(response.get("modelSummaries", [])) > 0
    except Exception:
        pass

    all_ok = db_ok and bedrock_ok
    return HealthResponse(
        status="healthy" if all_ok else "degraded",
        database="connected" if db_ok else "disconnected",
        bedrock="available" if bedrock_ok else "unavailable",
    )
