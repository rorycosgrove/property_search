"""Discovery feed endpoint — surfaces ranked property signals."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from packages.properties.discovery import get_discovery_feed
from packages.storage.database import get_db_session

router = APIRouter()


@router.get("/feed")
def discovery_feed(
    limit: int = Query(20, ge=1, le=60, description="Max number of signal cards to return"),
    db: Session = Depends(get_db_session),
) -> list[dict]:
    """Return a ranked list of property discovery signals.

    Signals include: price drops, high AI-value scores, stale listings,
    and fresh new listings with good data coverage.
    """
    return get_discovery_feed(db, limit=limit)
