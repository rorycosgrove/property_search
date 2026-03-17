"""Alert endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from packages.alerts.service import (
    AlertNotFoundError,
    acknowledge_alert_payload,
    acknowledge_all_payload,
    alert_stats_payload,
    list_alerts_payload,
    unread_count_payload,
)
from packages.storage.database import get_db_session
from packages.storage.repositories import AlertRepository

router = APIRouter()


@router.get("")
def list_alerts(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    alert_type: str | None = None,
    acknowledged: bool | None = None,
    db: Session = Depends(get_db_session),
):
    """List alerts with optional filtering."""
    repo = AlertRepository(db)
    return list_alerts_payload(
        repo=repo,
        page=page,
        size=size,
        alert_type=alert_type,
        acknowledged=acknowledged,
    )


@router.get("/stats")
def get_alert_stats(db: Session = Depends(get_db_session)):
    """Get alert statistics."""
    repo = AlertRepository(db)
    return alert_stats_payload(repo=repo)


@router.get("/unread-count")
def get_unread_count(db: Session = Depends(get_db_session)):
    """Get count of unacknowledged alerts."""
    repo = AlertRepository(db)
    return unread_count_payload(repo=repo)


@router.patch("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str, db: Session = Depends(get_db_session)):
    """Mark an alert as acknowledged."""
    repo = AlertRepository(db)
    try:
        return acknowledge_alert_payload(repo=repo, alert_id=alert_id)
    except AlertNotFoundError as exc:
        raise HTTPException(404, "Alert not found") from exc


@router.post("/acknowledge-all")
def acknowledge_all(db: Session = Depends(get_db_session)):
    """Acknowledge all unread alerts."""
    repo = AlertRepository(db)
    return acknowledge_all_payload(repo=repo)
