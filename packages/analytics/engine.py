"""
Market analytics engine.

Computes county-level, national, and time-series analytics
from property and sold property data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
        now = datetime.now(UTC)
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
        cutoff = datetime.now(UTC) - timedelta(days=months * 30)

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

    # ── Value ranking and drilldown ────────────────────────────────────────────

    def get_best_value_properties(
        self, county: str | None = None, property_type: str | None = None, limit: int = 10
    ) -> list[dict]:
        """Get properties ranked by LLM value score (best value first).
        
        Supports drilldown by county and property type.
        Returns properties with value_score, price/sqm, price/bed metrics.
        """
        try:
            from packages.storage.models import LLMEnrichment
            
            query = self.db.query(
                Property.id,
                Property.title,
                Property.address,
                Property.county,
                Property.property_type,
                Property.price,
                Property.bedrooms,
                Property.floor_area_sqm,
                LLMEnrichment.value_score,
            ).outerjoin(LLMEnrichment, Property.id == LLMEnrichment.property_id)
            
            query = query.filter(
                Property.price.isnot(None),
                Property.price > 0,
                LLMEnrichment.value_score.isnot(None),
            )
            
            if county:
                query = query.filter(Property.county == county)
            if property_type:
                query = query.filter(Property.property_type == property_type)
            
            rows = (
                query
                .order_by(LLMEnrichment.value_score.desc())
                .limit(limit)
                .all()
            )
            
            results = []
            for row in rows:
                price_per_sqm = None
                if row.floor_area_sqm and row.floor_area_sqm > 0:
                    price_per_sqm = round(float(row.price) / float(row.floor_area_sqm), 2)
                
                price_per_bed = None
                if row.bedrooms and row.bedrooms > 0:
                    price_per_bed = round(float(row.price) / row.bedrooms, 2)
                
                results.append({
                    "id": str(row.id),
                    "title": row.title,
                    "address": row.address,
                    "county": row.county,
                    "property_type": row.property_type,
                    "price": float(row.price),
                    "bedrooms": row.bedrooms,
                    "floor_area_sqm": row.floor_area_sqm,
                    "value_score": float(row.value_score) if row.value_score else None,
                    "price_per_sqm": price_per_sqm,
                    "price_per_bed": price_per_bed,
                })
            
            return results
        except Exception as exc:
            logger.warning("best_value_properties_failed", error=str(exc))
            return []

    def get_price_trends_by_type(
        self, county: str | None = None, months: int = 12
    ) -> dict[str, list[PriceTrend]]:
        """Get monthly price trends grouped by property type (drilldown).
        
        Useful for understanding value trends across different property categories.
        """
        try:
            cutoff = datetime.now(UTC) - timedelta(days=months * 30)
            
            query = (
                self.db.query(
                    Property.property_type,
                    func.date_trunc("month", SoldProperty.sale_date).label("month"),
                    func.avg(SoldProperty.price).label("avg_price"),
                    func.count(SoldProperty.id).label("sale_count"),
                )
                .join(SoldProperty, Property.county == SoldProperty.county)
                .filter(
                    SoldProperty.sale_date >= cutoff,
                    SoldProperty.price.isnot(None),
                    SoldProperty.price > 0,
                    Property.property_type.isnot(None),
                )
            )
            
            if county:
                query = query.filter(SoldProperty.county == county)
            
            rows = (
                query
                .group_by(Property.property_type, text("2"))
                .order_by(Property.property_type, text("2"))
                .all()
            )
            
            trends_by_type: dict[str, list[PriceTrend]] = {}
            for row in rows:
                prop_type = row.property_type or "unknown"
                if prop_type not in trends_by_type:
                    trends_by_type[prop_type] = []
                
                trends_by_type[prop_type].append(
                    PriceTrend(
                        period=row.month.strftime("%Y-%m") if row.month else "",
                        avg_price=round(float(row.avg_price), 2),
                        count=row.sale_count,
                    )
                )
            
            return trends_by_type
        except Exception as exc:
            logger.warning("price_trends_by_type_failed", error=str(exc))
            return {}

    def get_price_changes_by_budget(
        self, max_budget: float | None = None, county: str | None = None, days: int = 30, limit: int = 100
    ) -> list[dict]:
        """Get recent price changes filtered by max budget with drilldown details.
        
        Returns properties with price changes, ranked by most recent first.
        Useful for finding opportunities: recent drops in affordable properties.
        """
        try:
            cutoff = datetime.now(UTC) - timedelta(days=days)
            
            query = (
                self.db.query(
                    Property.id,
                    Property.title,
                    Property.address,
                    Property.county,
                    Property.price,
                    Property.property_type,
                    Property.bedrooms,
                    Property.bathrooms,
                    PropertyPriceHistory.price_change,
                    PropertyPriceHistory.price_change_pct,
                    PropertyPriceHistory.recorded_at,
                )
                .join(
                    PropertyPriceHistory,
                    Property.id == PropertyPriceHistory.property_id,
                )
                .filter(PropertyPriceHistory.recorded_at >= cutoff)
            )
            
            # Filter by current price within budget if provided
            if max_budget:
                query = query.filter(Property.price.isnot(None), Property.price <= max_budget)
            else:
                query = query.filter(Property.price.isnot(None))
            
            if county:
                query = query.filter(Property.county == county)
            
            rows = (
                query
                .order_by(PropertyPriceHistory.recorded_at.desc())
                .limit(limit)
                .all()
            )
            
            results = []
            for row in rows:
                results.append({
                    "property_id": str(row.id),
                    "title": row.title,
                    "address": row.address,
                    "county": row.county,
                    "current_price": float(row.price) if row.price else None,
                    "property_type": row.property_type,
                    "bedrooms": row.bedrooms,
                    "bathrooms": row.bathrooms,
                    "price_change": float(row.price_change) if row.price_change else None,
                    "price_change_pct": float(row.price_change_pct) if row.price_change_pct else None,
                    "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
                })
            
            return results
        except Exception as exc:
            logger.warning("price_changes_by_budget_failed", error=str(exc))
            return []

    def get_price_changes_timeline(
        self, max_budget: float | None = None, county: str | None = None, days: int = 30
    ) -> dict:
        """Get price changes aggregated by day for timeline/graph visualization.
        
        Returns: {
          "increases": [{"date": "2026-03-21", "count": 5, "avg_change": 1500, ...}, ...],
          "decreases": [{"date": "2026-03-21", "count": 3, "avg_change": -1200, ...}, ...]
        }
        """
        try:
            cutoff = datetime.now(UTC) - timedelta(days=days)
            
            query = (
                self.db.query(
                    func.date(PropertyPriceHistory.recorded_at).label("date"),
                    func.count(PropertyPriceHistory.id).label("count"),
                    func.avg(PropertyPriceHistory.price_change).label("avg_change"),
                    func.avg(PropertyPriceHistory.price_change_pct).label("avg_change_pct"),
                )
                .join(
                    Property,
                    Property.id == PropertyPriceHistory.property_id,
                )
                .filter(PropertyPriceHistory.recorded_at >= cutoff)
            )
            
            if max_budget:
                query = query.filter(Property.price.isnot(None), Property.price <= max_budget)
            else:
                query = query.filter(Property.price.isnot(None))
            
            if county:
                query = query.filter(Property.county == county)
            
            rows = (
                query
                .group_by(func.date(PropertyPriceHistory.recorded_at))
                .order_by(func.date(PropertyPriceHistory.recorded_at))
                .all()
            )
            
            increases = []
            decreases = []
            
            for row in rows:
                entry = {
                    "date": row.date.isoformat() if row.date else "",
                    "count": row.count,
                    "avg_change": round(float(row.avg_change), 2) if row.avg_change else None,
                    "avg_change_pct": round(float(row.avg_change_pct), 2) if row.avg_change_pct else None,
                }
                
                if row.avg_change and row.avg_change > 0:
                    increases.append(entry)
                elif row.avg_change and row.avg_change < 0:
                    decreases.append(entry)
            
            return {
                "increases": increases,
                "decreases": decreases,
            }
        except Exception as exc:
            logger.warning("price_changes_timeline_failed", error=str(exc))
            return {"increases": [], "decreases": []}

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
