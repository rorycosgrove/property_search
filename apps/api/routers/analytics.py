"""Analytics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from packages.analytics.engine import AnalyticsEngine
from packages.storage.database import get_db_session

router = APIRouter()


@router.get("/summary")
def get_summary(db: Session = Depends(get_db_session)):
    """Get high-level market analytics summary."""
    engine = AnalyticsEngine(db)
    return engine.get_summary().model_dump()


@router.get("/county-stats")
def get_county_stats(db: Session = Depends(get_db_session)):
    """Get price statistics by county."""
    engine = AnalyticsEngine(db)
    return [s.model_dump() for s in engine.get_county_stats()]


@router.get("/price-trends")
def get_price_trends(
    county: str | None = None,
    months: int = Query(12, ge=1, le=60),
    db: Session = Depends(get_db_session),
):
    """Get monthly price trends from sold property data."""
    engine = AnalyticsEngine(db)
    return [t.model_dump() for t in engine.get_price_trends(county=county, months=months)]


@router.get("/type-distribution")
def get_type_distribution(
    county: str | None = None,
    db: Session = Depends(get_db_session),
):
    """Get property type distribution."""
    engine = AnalyticsEngine(db)
    return [d.model_dump() for d in engine.get_type_distribution(county=county)]


@router.get("/ber-distribution")
def get_ber_distribution(
    county: str | None = None,
    db: Session = Depends(get_db_session),
):
    """Get BER rating distribution."""
    engine = AnalyticsEngine(db)
    return [d.model_dump() for d in engine.get_ber_distribution(county=county)]


@router.get("/heatmap")
def get_heatmap(db: Session = Depends(get_db_session)):
    """Get market heatmap data (avg price by location)."""
    engine = AnalyticsEngine(db)
    return [e.model_dump() for e in engine.get_market_heatmap()]
