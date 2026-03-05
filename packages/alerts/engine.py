"""
Alert evaluation engine.

Evaluates saved searches against new/changed properties and generates
alerts for price drops, new listings matching criteria, sale agreed, etc.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from packages.shared.logging import get_logger
from packages.shared.schemas import AlertSeverity, AlertType
from packages.storage.models import Alert, Property, PropertyPriceHistory, SavedSearch
from packages.storage.repositories import (
    AlertRepository,
    PropertyRepository,
    SavedSearchRepository,
)

logger = get_logger(__name__)


class AlertEngine:
    """
    Evaluates saved searches and property changes to generate alerts.

    Called by the Celery worker after each scraping cycle.
    """

    def __init__(self, db: Session):
        self.db = db
        self.property_repo = PropertyRepository(db)
        self.search_repo = SavedSearchRepository(db)
        self.alert_repo = AlertRepository(db)

    def evaluate_all(self) -> int:
        """
        Evaluate all active saved searches and generate alerts.

        Returns the number of new alerts generated.
        """
        searches = self.search_repo.get_all(active_only=True)
        total_alerts = 0

        for search in searches:
            try:
                count = self._evaluate_search(search)
                total_alerts += count
            except Exception as e:
                logger.error("alert_eval_error", search_id=str(search.id), error=str(e))

        logger.info("alert_evaluation_complete", total_alerts=total_alerts)
        return total_alerts

    def check_price_changes(self) -> int:
        """
        Check for recent price changes and generate alerts.

        Returns the count of price-change alerts created.
        """
        count = 0

        # Find properties with recent price history entries
        recent = (
            self.db.query(PropertyPriceHistory)
            .filter(PropertyPriceHistory.price_change.isnot(None))
            .order_by(PropertyPriceHistory.recorded_at.desc())
            .limit(500)
            .all()
        )

        for entry in recent:
            prop = self.db.get(Property, entry.property_id)
            if not prop:
                continue

            # Determine alert type from price change
            if entry.price_change and entry.price_change < 0:
                alert_type = AlertType.PRICE_DROP
                severity = AlertSeverity.HIGH
                pct = abs(float(entry.price_change_pct or 0))
                title = f"Price dropped {pct:.1f}% on {prop.title[:60]}"
            elif entry.price_change and entry.price_change > 0:
                alert_type = AlertType.PRICE_INCREASE
                severity = AlertSeverity.MEDIUM
                pct = float(entry.price_change_pct or 0)
                title = f"Price increased {pct:.1f}% on {prop.title[:60]}"
            else:
                continue

            # Avoid duplicate alerts for the same price change
            existing = (
                self.db.query(Alert)
                .filter(
                    Alert.property_id == prop.id,
                    Alert.alert_type == alert_type.value,
                    Alert.metadata_json["price_history_id"].astext == str(entry.id),
                )
                .first()
            )
            if existing:
                continue

            self.alert_repo.create(
                alert_type=alert_type.value,
                title=title,
                severity=severity.value,
                property_id=prop.id,
                metadata_json={
                    "price_history_id": str(entry.id),
                    "old_price": float(entry.price - (entry.price_change or 0)),
                    "new_price": float(entry.price),
                    "change_amount": float(entry.price_change),
                    "change_pct": float(entry.price_change_pct) if entry.price_change_pct else None,
                },
            )
            count += 1

        return count

    def check_status_changes(self, property_id: str, old_status: str, new_status: str) -> None:
        """Generate alert when a property status changes (e.g., sale agreed)."""
        prop = self.db.get(Property, property_id)
        if not prop:
            return

        if new_status == "sale_agreed":
            self.alert_repo.create(
                alert_type=AlertType.SALE_AGREED.value,
                title=f"Sale Agreed: {prop.title[:60]}",
                severity=AlertSeverity.MEDIUM.value,
                property_id=prop.id,
                metadata_json={
                    "old_status": old_status,
                    "new_status": new_status,
                    "price": float(prop.price) if prop.price else None,
                },
            )

        if new_status == "active" and old_status in ("sale_agreed", "withdrawn"):
            self.alert_repo.create(
                alert_type=AlertType.BACK_ON_MARKET.value,
                title=f"Back on Market: {prop.title[:60]}",
                severity=AlertSeverity.HIGH.value,
                property_id=prop.id,
                metadata_json={"old_status": old_status},
            )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _evaluate_search(self, search: SavedSearch) -> int:
        """Evaluate a single saved search. Returns alert count."""
        criteria = search.criteria or {}
        count = 0

        # Build filters from criteria
        filters: dict[str, Any] = {}
        if "county" in criteria:
            filters["county"] = criteria["county"]
        if "min_price" in criteria:
            filters["min_price"] = criteria["min_price"]
        if "max_price" in criteria:
            filters["max_price"] = criteria["max_price"]
        if "min_beds" in criteria:
            filters["min_beds"] = criteria["min_beds"]
        if "property_types" in criteria:
            filters["property_types"] = criteria["property_types"]
        if "keywords" in criteria:
            filters["keywords"] = criteria["keywords"]

        # Find matching properties listed since last notification
        last_notified = search.last_matched_at or datetime(2000, 1, 1, tzinfo=timezone.utc)

        from packages.shared.schemas import PropertyFilters
        property_filters = PropertyFilters(
            counties=[filters["county"]] if filters.get("county") else None,
            min_price=filters.get("min_price"),
            max_price=filters.get("max_price"),
            min_bedrooms=filters.get("min_beds"),
            property_types=filters.get("property_types"),
            page=1,
            per_page=100,
        )

        properties, total = self.property_repo.list_properties(property_filters)

        for prop in properties:
            # Only alert for properties listed after last notification
            if prop.first_listed_at and prop.first_listed_at <= last_notified:
                continue

            # Check if alert already exists
            existing = (
                self.db.query(Alert)
                .filter(
                    Alert.property_id == prop.id,
                    Alert.saved_search_id == search.id,
                    Alert.alert_type == AlertType.NEW_LISTING.value,
                )
                .first()
            )
            if existing:
                continue

            self.alert_repo.create(
                alert_type=AlertType.NEW_LISTING.value,
                title=f"New match: {prop.title[:60]}",
                severity=AlertSeverity.LOW.value,
                property_id=prop.id,
                saved_search_id=search.id,
                metadata_json={
                    "search_name": search.name,
                    "price": float(prop.price) if prop.price else None,
                    "county": prop.county,
                },
            )
            count += 1

        # Update last matched timestamp
        if count > 0:
            search.last_matched_at = datetime.now(timezone.utc)
            self.db.add(search)

        return count
