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


@router.get("/best-value-properties")
def get_best_value_properties(
    county: str | None = None,
    property_type: str | None = None,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db_session),
):
    """Get properties ranked by LLM value score (best value first).
    
    Supports drilldown by county and property type.
    Returns properties with value metrics: price, price/sqm, price/bedroom.
    """
    engine = AnalyticsEngine(db)
    return engine.get_best_value_properties(county=county, property_type=property_type, limit=limit)


@router.get("/price-trends-by-type")
def get_price_trends_by_type(
    county: str | None = None,
    months: int = Query(12, ge=1, le=60),
    db: Session = Depends(get_db_session),
):
    """Get monthly price trends by property type (drilldown).
    
    Useful for understanding value trends across different property categories.
    """
    engine = AnalyticsEngine(db)
    trends = engine.get_price_trends_by_type(county=county, months=months)
    return {prop_type: [t.model_dump() for t in trends_list] for prop_type, trends_list in trends.items()}


@router.get("/price-changes-by-budget")
def get_price_changes_by_budget(
    max_budget: float | None = None,
    county: str | None = None,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db_session),
):
    """Get recent price changes filtered by max budget with drilldown details.
    
    Returns properties with price changes within your budget, ranked by most recent.
    Useful for finding opportunities: recent price drops in affordable properties.
    """
    engine = AnalyticsEngine(db)
    return engine.get_price_changes_by_budget(max_budget=max_budget, county=county, days=days, limit=limit)


@router.get("/price-changes-timeline")
def get_price_changes_timeline(
    max_budget: float | None = None,
    county: str | None = None,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db_session),
):
    """Get price changes aggregated by day for timeline/graph visualization.
    
    Shows volume of price increases vs decreases over time within your budget.
    """
    engine = AnalyticsEngine(db)
    return engine.get_price_changes_timeline(max_budget=max_budget, county=county, days=days)
