"""Admin endpoints — database migrations and diagnostics."""

from __future__ import annotations

import subprocess

from fastapi import APIRouter, HTTPException

from packages.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/migrate", summary="Run Alembic migrations (upgrade head)")
def run_migrations():
    """Execute `alembic upgrade head` inside the Lambda environment."""
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        logger.error("migration_failed", stderr=result.stderr)
        raise HTTPException(status_code=500, detail=result.stderr)
    logger.info("migration_success", stdout=result.stdout)
    return {"status": "ok", "output": result.stdout.strip()}


@router.get("/migrate/status", summary="Current Alembic revision")
def migration_status():
    """Return the current Alembic migration revision."""
    result = subprocess.run(
        ["alembic", "current"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr)
    return {"revision": result.stdout.strip()}
