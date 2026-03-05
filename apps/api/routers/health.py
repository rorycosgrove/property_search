"""Health check endpoints."""

import redis as redis_lib
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from packages.shared.config import settings
from packages.shared.schemas import HealthResponse
from packages.storage.database import get_db_session

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db_session)):
    """System health check — verifies database connectivity."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    # Check Redis connectivity
    redis_ok = False
    try:
        r = redis_lib.from_url(settings.redis_url, socket_timeout=2)
        r.ping()
        redis_ok = True
    except Exception:
        pass

    all_ok = db_ok and redis_ok
    return HealthResponse(
        status="healthy" if all_ok else "degraded",
        database="connected" if db_ok else "disconnected",
        redis="connected" if redis_ok else "disconnected",
    )
