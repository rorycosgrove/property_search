"""
Market analytics engine.

Computes county-level, national, and time-series analytics
from property and sold property data.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from packages.shared.logging import get_logger
from packages.shared.schemas import (
    AnalyticsSummary,
    BERDistribution,
    CountyPriceStats,
    MarketHeatmapEntry,
    PriceTrend,
    PropertyTypeDistribution,
)
from packages.storage.models import Property, PropertyPriceHistory, SoldProperty

logger = get_logger(__name__)


class AnalyticsEngine:
    """
    Computes market analytics from property data.

    All methods accept a SQLAlchemy session and return Pydantic schemas.
    """

    def __init__(self, db: Session):
        self.db = db

    # ── Summary ───────────────────────────────────────────────────────────────

    def get_summary(self) -> AnalyticsSummary:
        """Get high-level analytics summary."""
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(hours=24)

        total_listings = self.db.query(func.count(Property.id)).scalar() or 0
        new_24h = (
            self.db.query(func.count(Property.id))
            .filter(Property.first_listed_at >= day_ago)
            .scalar()
            or 0
        )
        avg_price = (
            self.db.query(func.avg(Property.price))
            .filter(Property.price.isnot(None), Property.price > 0)
            .scalar()
        )
        median_price = self._compute_median_price()
        price_changes_24h = (
            self.db.query(func.count(PropertyPriceHistory.id))
            .filter(PropertyPriceHistory.recorded_at >= day_ago)
            .scalar()
            or 0
        )
        total_sold = self.db.query(func.count(SoldProperty.id)).scalar() or 0

        return AnalyticsSummary(
            total_active_listings=total_listings,
            new_listings_24h=new_24h,
            avg_price=round(float(avg_price), 2) if avg_price else None,
            median_price=round(float(median_price), 2) if median_price else None,
            price_changes_24h=price_changes_24h,
            total_sold_ppr=total_sold,
        )

    # ── County price stats ────────────────────────────────────────────────────

    def get_county_stats(self) -> list[CountyPriceStats]:
        """Get price statistics grouped by county."""
        rows = (
            self.db.query(
                Property.county,
                func.count(Property.id).label("count"),
                func.avg(Property.price).label("avg_price"),
                func.min(Property.price).label("min_price"),
                func.max(Property.price).label("max_price"),
            )
            .filter(
                Property.county.isnot(None),
                Property.price.isnot(None),
                Property.price > 0,
            )
            .group_by(Property.county)
            .order_by(func.count(Property.id).desc())
            .all()
        )

        results = []
        for row in rows:
            results.append(
                CountyPriceStats(
                    county=row.county,
                    count=row.count,
                    avg_price=round(float(row.avg_price), 2),
                    min_price=round(float(row.min_price), 2),
                    max_price=round(float(row.max_price), 2),
                    median_price=self._compute_county_median(row.county),
                )
            )
        return results

    # ── Price trends ──────────────────────────────────────────────────────────

    def get_price_trends(
        self,
        county: str | None = None,
        months: int = 12,
    ) -> list[PriceTrend]:
        """Get monthly average price trends."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)

        query = (
            self.db.query(
                func.date_trunc("month", SoldProperty.sale_date).label("month"),
                func.avg(SoldProperty.price).label("avg_price"),
                func.count(SoldProperty.id).label("sale_count"),
            )
            .filter(
                SoldProperty.sale_date >= cutoff,
                SoldProperty.price.isnot(None),
                SoldProperty.price > 0,
            )
        )

        if county:
            query = query.filter(SoldProperty.county == county)

        rows = (
            query
            .group_by(text("1"))
            .order_by(text("1"))
            .all()
        )

        return [
            PriceTrend(
                period=row.month.strftime("%Y-%m") if row.month else "",
                avg_price=round(float(row.avg_price), 2),
                count=row.sale_count,
            )
            for row in rows
        ]

    # ── Property type distribution ────────────────────────────────────────────

    def get_type_distribution(self, county: str | None = None) -> list[PropertyTypeDistribution]:
        """Get distribution of property types."""
        query = self.db.query(
            Property.property_type,
            func.count(Property.id).label("count"),
            func.avg(Property.price).label("avg_price"),
        ).filter(Property.property_type.isnot(None))

        if county:
            query = query.filter(Property.county == county)

        rows = (
            query
            .group_by(Property.property_type)
            .order_by(func.count(Property.id).desc())
            .all()
        )

        total = sum(r.count for r in rows) or 1

        return [
            PropertyTypeDistribution(
                property_type=row.property_type or "unknown",
                count=row.count,
                percentage=round(row.count / total * 100, 1),
                avg_price=round(float(row.avg_price), 2) if row.avg_price else None,
            )
            for row in rows
        ]

    # ── BER distribution ──────────────────────────────────────────────────────

    def get_ber_distribution(self, county: str | None = None) -> list[BERDistribution]:
        """Get distribution of BER ratings."""
        query = self.db.query(
            Property.ber_rating,
            func.count(Property.id).label("count"),
        ).filter(Property.ber_rating.isnot(None))

        if county:
            query = query.filter(Property.county == county)

        rows = (
            query
            .group_by(Property.ber_rating)
            .order_by(func.count(Property.id).desc())
            .all()
        )

        total = sum(r.count for r in rows) or 1

        return [
            BERDistribution(
                ber_rating=row.ber_rating,
                count=row.count,
                percentage=round(row.count / total * 100, 1),
            )
            for row in rows
        ]

    # ── Market heatmap ────────────────────────────────────────────────────────

    def get_market_heatmap(self) -> list[MarketHeatmapEntry]:
        """Get heatmap data — average price per location cluster."""
        # Use county centroids as heatmap points
        rows = (
            self.db.query(
                Property.county,
                func.avg(Property.latitude).label("lat"),
                func.avg(Property.longitude).label("lng"),
                func.avg(Property.price).label("avg_price"),
                func.count(Property.id).label("count"),
            )
            .filter(
                Property.county.isnot(None),
                Property.latitude.isnot(None),
                Property.longitude.isnot(None),
                Property.price.isnot(None),
                Property.price > 0,
            )
            .group_by(Property.county)
            .all()
        )

        return [
            MarketHeatmapEntry(
                county=row.county,
                avg_price=round(float(row.avg_price), 2),
                listing_count=row.count,
            )
            for row in rows
            if row.lat and row.lng
        ]

    # ── Private helpers ───────────────────────────────────────────────────────

    def _compute_median_price(self) -> float | None:
        """Compute median price using percentile_cont (PostgreSQL)."""
        try:
            result = self.db.execute(
                text(
                    "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY price) "
                    "FROM properties WHERE price IS NOT NULL AND price > 0"
                )
            ).scalar()
            return float(result) if result else None
        except Exception:
            return None

    def _compute_county_median(self, county: str) -> float | None:
        """Compute median price for a county."""
        try:
            result = self.db.execute(
                text(
                    "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY price) "
                    "FROM properties WHERE county = :county AND price IS NOT NULL AND price > 0"
                ),
                {"county": county},
            ).scalar()
            return round(float(result), 2) if result else None
        except Exception:
            return None
