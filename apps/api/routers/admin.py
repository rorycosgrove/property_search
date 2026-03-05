"""Admin endpoints — database migrations and diagnostics."""

from __future__ import annotations

import subprocess
import sys

from fastapi import APIRouter, HTTPException

from packages.shared.constants import MIGRATION_STATUS_TIMEOUT_SECONDS, MIGRATION_TIMEOUT_SECONDS
from packages.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/migrate", summary="Run Alembic migrations (upgrade head)")
def run_migrations():
    """Execute `alembic upgrade head` inside the Lambda environment."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=MIGRATION_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            logger.error("migration_failed", stderr=result.stderr)
            raise HTTPException(status_code=500, detail=result.stderr)
        logger.info("migration_success", stdout=result.stdout)
        return {"status": "ok", "output": result.stdout.strip()}
    except subprocess.TimeoutExpired:
        logger.error("migration_timeout")
        raise HTTPException(status_code=504, detail="Migration timed out")
    except Exception as e:
        logger.error("migration_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/migrate/status", summary="Current Alembic revision")
def migration_status():
    """Return the current Alembic migration revision."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "current"],
            capture_output=True,
            text=True,
            timeout=MIGRATION_STATUS_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=result.stderr)
        return {"revision": result.stdout.strip()}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Status check timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
