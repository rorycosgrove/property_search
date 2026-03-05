"""Alert endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

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
    items, total = repo.list_alerts(
        page=page,
        per_page=size,
        alert_type=alert_type,
        acknowledged=acknowledged,
    )
    return {
        "items": [
            {
                "id": str(a.id),
                "alert_type": a.alert_type,
                "title": a.title,
                "severity": a.severity,
                "property_id": str(a.property_id) if a.property_id else None,
                "saved_search_id": str(a.saved_search_id) if a.saved_search_id else None,
                "metadata": a.metadata_json,
                "acknowledged": a.acknowledged,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in items
        ],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/stats")
def get_alert_stats(db: Session = Depends(get_db_session)):
    """Get alert statistics."""
    repo = AlertRepository(db)
    return repo.get_stats()


@router.get("/unread-count")
def get_unread_count(db: Session = Depends(get_db_session)):
    """Get count of unacknowledged alerts."""
    repo = AlertRepository(db)
    return {"count": repo.count_unacknowledged()}


@router.patch("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str, db: Session = Depends(get_db_session)):
    """Mark an alert as acknowledged."""
    repo = AlertRepository(db)
    alert = repo.acknowledge(alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    return {"acknowledged": True}


@router.post("/acknowledge-all")
def acknowledge_all(db: Session = Depends(get_db_session)):
    """Acknowledge all unread alerts."""
    repo = AlertRepository(db)
    count = repo.acknowledge_all()
    return {"acknowledged": count}
