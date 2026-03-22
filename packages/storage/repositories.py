"""
Repository classes implementing the Repository Pattern for data access.

All database queries live here. Business logic (API endpoints, worker tasks)
call repository methods that accept/return Pydantic schemas or simple types,
never ORM model instances. This decouples persistence from domain logic.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geography
from geoalchemy2.elements import WKTElement
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from sqlalchemy import and_, case, cast, func, or_, select, Float
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.orm import Session, joinedload

from packages.shared.constants import (
    SIMILAR_PROPERTY_BEDROOM_RANGE,
    SIMILAR_PROPERTY_LIMIT,
    SIMILAR_PROPERTY_PRICE_TOLERANCE,
    SOURCE_ERROR_THRESHOLD,
)
from packages.shared.money import to_decimal
from packages.shared.schemas import (
    CountyPriceStats,
    PropertyFilters,
    SoldPropertyFilters,
)
from packages.shared.utils import utc_now
from packages.storage.models import (
    Alert,
    BackendLog,
    Conversation,
    ConversationMessage,
    GrantProgram,
    LLMEnrichment,
    Property,
    PropertyDocument,
    PropertyGrantMatch,
    PropertyPriceHistory,
    PropertyTimelineEvent,
    SourceQualitySnapshot,
    OrganicSearchRun,
    SavedSearch,
    SoldProperty,
    Source,
)


def _build_location_point(latitude: float | None, longitude: float | None) -> WKTElement | None:
    """Create a PostGIS point value when coordinates are present and parseable."""
    if latitude is None or longitude is None:
        return None
    try:
        lat = float(latitude)
        lng = float(longitude)
    except (TypeError, ValueError):
        return None
    return WKTElement(f"POINT({lng} {lat})", srid=4326)

# ──────────────────────────────────────────────────────────────────────────────
# SourceRepository
# ──────────────────────────────────────────────────────────────────────────────

class SourceRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_all(self, enabled_only: bool = False) -> list[Source]:
        query = select(Source).order_by(Source.name)
        if enabled_only:
            query = query.where(Source.enabled.is_(True))
        return list(self.session.scalars(query))

    def get_by_id(self, source_id: str) -> Source | None:
        return self.session.get(Source, source_id)

    def get_by_url(self, url: str) -> Source | None:
        return self.session.scalar(select(Source).where(Source.url == url))

    def create(self, **kwargs) -> Source:
        source = Source(**kwargs)
        self.session.add(source)
        self.session.flush()
        return source

    def update(self, source_id: str, **kwargs) -> Source | None:
        source = self.get_by_id(source_id)
        if not source:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(source, key):
                setattr(source, key, value)
        source.updated_at = utc_now()
        self.session.flush()
        return source

    def delete(self, source_id: str) -> bool:
        source = self.get_by_id(source_id)
        if not source:
            return False
        self.session.delete(source)
        self.session.flush()
        return True

    def mark_poll_success(self, source_id: str, listings_count: int = 0) -> None:
        source = self.get_by_id(source_id)
        if source:
            now = utc_now()
            source.last_polled_at = now
            source.last_success_at = now
            source.error_count = 0
            source.last_error = None
            actual_count = (
                self.session.scalar(
                    select(func.count(Property.id)).where(Property.source_id == source_id)
                )
                or 0
            )
            source.total_listings = actual_count
            self.session.flush()

    def mark_poll_error(self, source_id: str, error_message: str) -> None:
        source = self.get_by_id(source_id)
        if source:
            source.last_polled_at = utc_now()
            source.error_count += 1
            source.last_error = error_message
            # Auto-disable after N consecutive errors
            if source.error_count >= SOURCE_ERROR_THRESHOLD:
                source.enabled = False
            self.session.flush()

    def try_acquire_scrape_lock(self, source_id: str) -> bool:
        """Acquire a transaction-scoped advisory lock for a source scrape.

        Returns True when lock is acquired, False when another scrape is in-flight.
        Falls back to True on non-Postgres dialects.
        """
        bind = self.session.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""
        if dialect_name != "postgresql":
            return True

        try:
            # hashtext(source_id) provides a stable lock key per source.
            acquired = self.session.scalar(
                select(func.pg_try_advisory_xact_lock(func.hashtext(source_id)))
            )
            return bool(acquired)
        except DatabaseError:
            # Fail closed when lock checks cannot run to avoid duplicate concurrent scrapes.
            return False

    def should_skip_poll(self, source: Source, now: datetime | None = None) -> bool:
        """Return True when source poll interval has not elapsed yet."""
        if source.last_polled_at is None:
            return False

        interval_seconds = max(int(source.poll_interval_seconds or 0), 0)
        if interval_seconds == 0:
            return False

        now_dt = now or utc_now()
        next_allowed = source.last_polled_at + timedelta(seconds=interval_seconds)
        return now_dt < next_allowed


# ──────────────────────────────────────────────────────────────────────────────
# PropertyRepository
# ──────────────────────────────────────────────────────────────────────────────

class PropertyRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, property_id: str, include_relations: bool = True) -> Property | None:
        if not hasattr(self.session, "scalar"):
            return self.session.get(Property, property_id)

        query = select(Property).where(Property.id == property_id)
        if include_relations:
            query = query.options(
                joinedload(Property.enrichment),
                joinedload(Property.price_history),
                joinedload(Property.source),
            )
        return self.session.scalar(query)

    def get_by_content_hash(self, content_hash: str) -> Property | None:
        return self.session.scalar(
            select(Property).where(Property.content_hash == content_hash)
        )

    def get_by_external_id_and_source(self, source_id: str, external_id: str) -> Property | None:
        return self.session.scalar(
            select(Property).where(
                Property.source_id == source_id,
                Property.external_id == external_id,
            )
        )

    def list_by_external_id(self, external_id: str) -> list[Property]:
        query = (
            select(Property)
            .where(Property.external_id == external_id)
            .options(joinedload(Property.source))
            .order_by(Property.created_at.desc())
        )
        return list(self.session.scalars(query).unique())

    def list_by_url_suffix(self, suffix: str, limit: int = 20) -> list[Property]:
        query = (
            select(Property)
            .where(Property.url.ilike(f"%{suffix}"))
            .options(joinedload(Property.source))
            .order_by(Property.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(query).unique())

    def get_by_canonical_property_id(self, canonical_property_id: str) -> Property | None:
        return self.session.scalar(
            select(Property)
            .where(Property.canonical_property_id == canonical_property_id)
            .order_by(Property.created_at.desc())
        )

    def list_by_canonical_property_id(self, canonical_property_id: str) -> list[Property]:
        query = (
            select(Property)
            .where(Property.canonical_property_id == canonical_property_id)
            .order_by(Property.created_at.desc())
        )
        return list(self.session.scalars(query))

    def list_properties(self, filters: PropertyFilters) -> tuple[list[Property], int]:
        """
        List properties with filtering, sorting, and pagination.

        Returns (items, total_count).
        """
        query = select(Property).options(
            joinedload(Property.enrichment),
            joinedload(Property.price_history),
        )
        count_query = select(func.count(Property.id))

        # Apply filters
        conditions = []

        if filters.counties:
            conditions.append(Property.county.in_(filters.counties))

        if filters.min_price is not None:
            conditions.append(Property.price >= filters.min_price)

        if filters.max_price is not None:
            conditions.append(Property.price <= filters.max_price)

        if filters.min_bedrooms is not None:
            conditions.append(Property.bedrooms >= filters.min_bedrooms)

        if filters.max_bedrooms is not None:
            conditions.append(Property.bedrooms <= filters.max_bedrooms)

        if filters.property_types:
            conditions.append(Property.property_type.in_([pt.value for pt in filters.property_types]))

        if filters.sale_type:
            conditions.append(Property.sale_type == filters.sale_type)

        if filters.ber_ratings:
            conditions.append(Property.ber_rating.in_(filters.ber_ratings))

        if filters.keywords:
            for keyword in filters.keywords:
                pattern = f"%{keyword}%"
                conditions.append(
                    or_(
                        Property.title.ilike(pattern),
                        Property.description.ilike(pattern),
                        Property.address.ilike(pattern),
                    )
                )

        if filters.statuses:
            conditions.append(Property.status.in_([s.value for s in filters.statuses]))

        if filters.source_id:
            conditions.append(Property.source_id == filters.source_id)

        # Geospatial radius filter
        if filters.lat is not None and filters.lng is not None and filters.radius_km is not None:
            point = ST_SetSRID(ST_MakePoint(filters.lng, filters.lat), 4326)
            radius_metres = filters.radius_km * 1000
            conditions.append(
                ST_DWithin(
                    cast(Property.location_point, Geography),
                    cast(point, Geography),
                    radius_metres,
                )
            )

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        # Sorting
        sort_map = {
            "price": Property.price,
            "created_at": Property.created_at,
            "date": Property.created_at,
            "beds": Property.bedrooms,
            "bedrooms": Property.bedrooms,
        }
        sort_col = sort_map.get(filters.sort_by, Property.created_at)
        if filters.sort_order == "asc":
            query = query.order_by(sort_col.asc().nullslast())
        else:
            query = query.order_by(sort_col.desc().nullslast())

        # Count
        total = self.session.scalar(count_query) or 0

        # Pagination
        offset = (filters.page - 1) * filters.per_page
        query = query.offset(offset).limit(filters.per_page)

        items = list(self.session.scalars(query).unique())
        return items, total

    def list_properties_with_eligible_grants(
        self,
        filters: PropertyFilters,
    ) -> tuple[list[Property], int, dict[str, dict[str, float]]]:
        """List properties sorted by net price (price - eligible grants)."""
        eligible_grants_expr = func.coalesce(
            func.sum(
                case(
                    (
                        and_(
                            PropertyGrantMatch.status == "eligible",
                            PropertyGrantMatch.estimated_benefit.is_not(None),
                        ),
                        PropertyGrantMatch.estimated_benefit,
                    ),
                    else_=0.0,
                )
            ),
            0.0,
        )
        grant_totals_sq = (
            select(
                PropertyGrantMatch.property_id.label("property_id"),
                eligible_grants_expr.label("eligible_grants_total"),
            )
            .group_by(PropertyGrantMatch.property_id)
            .subquery()
        )

        eligible_total_col = func.coalesce(grant_totals_sq.c.eligible_grants_total, 0.0)
        net_price_expr = (func.coalesce(Property.price, 0.0) - eligible_total_col)

        query = (
            select(
                Property,
                eligible_total_col.label("eligible_grants_total"),
                net_price_expr.label("net_price"),
            )
            .outerjoin(grant_totals_sq, grant_totals_sq.c.property_id == Property.id)
            .options(
                joinedload(Property.enrichment),
                joinedload(Property.price_history),
            )
        )
        conditions = []

        if filters.counties:
            conditions.append(Property.county.in_(filters.counties))

        if filters.min_price is not None:
            conditions.append(Property.price >= filters.min_price)

        if filters.max_price is not None:
            conditions.append(Property.price <= filters.max_price)

        if filters.min_bedrooms is not None:
            conditions.append(Property.bedrooms >= filters.min_bedrooms)

        if filters.max_bedrooms is not None:
            conditions.append(Property.bedrooms <= filters.max_bedrooms)

        if filters.property_types:
            conditions.append(Property.property_type.in_([pt.value for pt in filters.property_types]))

        if filters.sale_type:
            conditions.append(Property.sale_type == filters.sale_type)

        if filters.ber_ratings:
            conditions.append(Property.ber_rating.in_(filters.ber_ratings))

        if filters.keywords:
            for keyword in filters.keywords:
                pattern = f"%{keyword}%"
                conditions.append(
                    or_(
                        Property.title.ilike(pattern),
                        Property.description.ilike(pattern),
                        Property.address.ilike(pattern),
                    )
                )

        if filters.statuses:
            conditions.append(Property.status.in_([s.value for s in filters.statuses]))

        if filters.source_id:
            conditions.append(Property.source_id == filters.source_id)

        if filters.lat is not None and filters.lng is not None and filters.radius_km is not None:
            point = ST_SetSRID(ST_MakePoint(filters.lng, filters.lat), 4326)
            radius_metres = filters.radius_km * 1000
            conditions.append(
                ST_DWithin(
                    cast(Property.location_point, Geography),
                    cast(point, Geography),
                    radius_metres,
                )
            )

        if conditions:
            query = query.where(and_(*conditions))

        having_conditions = []
        if filters.eligible_only:
            having_conditions.append(eligible_total_col > 0)
        if filters.min_eligible_grants_total is not None:
            having_conditions.append(eligible_total_col >= filters.min_eligible_grants_total)
        if having_conditions:
            query = query.where(and_(*having_conditions))

        if filters.sort_order == "desc":
            query = query.order_by(net_price_expr.desc(), Property.created_at.desc(), Property.id.asc())
        else:
            query = query.order_by(net_price_expr.asc(), Property.created_at.desc(), Property.id.asc())

        total = self.session.scalar(
            select(func.count()).select_from(query.order_by(None).subquery())
        ) or 0

        offset = (filters.page - 1) * filters.per_page
        query = query.offset(offset).limit(filters.per_page)

        rows = list(self.session.execute(query).unique())
        items = [row[0] for row in rows]
        metrics = {
            str(row[0].id): {
                "eligible_grants_total": float(row[1] or 0.0),
                "net_price": float(row[2] or 0.0),
            }
            for row in rows
        }
        return items, total, metrics

    def create(self, **kwargs) -> Property:
        location_point = _build_location_point(kwargs.get("latitude"), kwargs.get("longitude"))
        if location_point is not None:
            kwargs["location_point"] = location_point
        prop = Property(**kwargs)
        self.session.add(prop)
        self.session.flush()
        # Record initial price history
        if prop.price is not None:
            PriceHistoryRepository(self.session).add_entry(
                property_id=prop.id,
                price=prop.price,
                price_change=None,
                price_change_pct=None,
            )
        return prop

    def update(self, property_id: str, **kwargs) -> Property | None:
        prop = self.get_by_id(property_id, include_relations=False)
        if not prop:
            return None

        lat = kwargs.get("latitude", prop.latitude)
        lng = kwargs.get("longitude", prop.longitude)
        location_point = _build_location_point(lat, lng)
        if location_point is not None:
            kwargs["location_point"] = location_point

        old_price = prop.price
        for key, value in kwargs.items():
            if value is not None and hasattr(prop, key):
                setattr(prop, key, value)
        prop.updated_at = utc_now()
        self.session.flush()

        # Record price history if price changed
        new_price = prop.price
        if new_price is not None and (old_price is None or new_price != old_price):
            price_change = (new_price - old_price) if old_price is not None else None
            price_change_pct = ((price_change / old_price) * 100) if old_price and price_change is not None else None
            PriceHistoryRepository(self.session).add_entry(
                property_id=prop.id,
                price=new_price,
                price_change=price_change,
                price_change_pct=price_change_pct,
            )
        return prop

    def get_stats(
        self,
        county: str | None = None,
        property_type: str | None = None,
    ) -> dict:
        """Get aggregate statistics for properties."""
        query = select(
            func.count(Property.id).label("total"),
            func.avg(Property.price).label("avg_price"),
            func.min(Property.price).label("min_price"),
            func.max(Property.price).label("max_price"),
        ).where(Property.status.in_(["new", "active", "price_changed"]))

        if county:
            query = query.where(Property.county == county)
        if property_type:
            query = query.where(Property.property_type == property_type)

        row = self.session.execute(query).one()
        return {
            "total": row.total or 0,
            "avg_price": float(row.avg_price) if row.avg_price else None,
            "min_price": float(row.min_price) if row.min_price else None,
            "max_price": float(row.max_price) if row.max_price else None,
        }

    def get_price_by_county(self, property_type: str | None = None) -> list[CountyPriceStats]:
        """Get average/median/min/max price grouped by county."""
        query = (
            select(
                Property.county,
                func.avg(Property.price).label("avg_price"),
                func.min(Property.price).label("min_price"),
                func.max(Property.price).label("max_price"),
                func.count(Property.id).label("count"),
                # PostgreSQL percentile for median
                func.percentile_cont(0.5).within_group(Property.price).label("median_price"),
            )
            .where(
                and_(
                    Property.county.isnot(None),
                    Property.price.isnot(None),
                    Property.status.in_(["new", "active", "price_changed"]),
                )
            )
            .group_by(Property.county)
            .order_by(func.avg(Property.price).desc())
        )

        if property_type:
            query = query.where(Property.property_type == property_type)

        rows = self.session.execute(query).all()
        return [
            CountyPriceStats(
                county=row.county,
                avg_price=float(row.avg_price),
                median_price=float(row.median_price) if row.median_price else 0,
                min_price=float(row.min_price),
                max_price=float(row.max_price),
                count=row.count,
            )
            for row in rows
        ]

    def count_new_since(self, since: datetime) -> int:
        return (
            self.session.scalar(
                select(func.count(Property.id)).where(Property.created_at >= since)
            )
            or 0
        )

    def count_price_changes_since(self, since: datetime) -> int:
        return (
            self.session.scalar(
                select(func.count(Property.id)).where(
                    and_(
                        Property.status == "price_changed",
                        Property.updated_at >= since,
                    )
                )
            )
            or 0
        )

    def find_similar(
        self,
        property_id: str,
        limit: int = SIMILAR_PROPERTY_LIMIT,
    ) -> list[Property]:
        """Find similar properties based on county, type, bedrooms, and price range."""
        prop = self.get_by_id(property_id, include_relations=False)
        if not prop:
            return []

        conditions = [
            Property.id != property_id,
            Property.status.in_(["new", "active", "price_changed"]),
        ]

        if prop.county:
            conditions.append(Property.county == prop.county)
        if prop.property_type:
            conditions.append(Property.property_type == prop.property_type)
        if prop.bedrooms:
            conditions.append(
                Property.bedrooms.between(
                    prop.bedrooms - SIMILAR_PROPERTY_BEDROOM_RANGE,
                    prop.bedrooms + SIMILAR_PROPERTY_BEDROOM_RANGE
                )
            )
        if prop.price:
            price_range = prop.price * SIMILAR_PROPERTY_PRICE_TOLERANCE
            conditions.append(
                Property.price.between(prop.price - price_range, prop.price + price_range)
            )

        query = (
            select(Property)
            .where(and_(*conditions))
            .order_by(Property.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(query))


# ──────────────────────────────────────────────────────────────────────────────
# PriceHistoryRepository
# ──────────────────────────────────────────────────────────────────────────────

class PriceHistoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def add_entry(
        self,
        property_id: str,
        price: Decimal | float,
        price_change: Decimal | float | None = None,
        price_change_pct: float | None = None,
        timeline_event_type: str | None = None,
        timeline_context: dict[str, Any] | None = None,
    ) -> PropertyPriceHistory:
        hour_bucket = datetime.now(UTC).replace(minute=0, second=0, microsecond=0, tzinfo=None)

        bind = self.session.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""
        entry: PropertyPriceHistory | None = None
        inserted_new = False

        if dialect_name == "postgresql":
            table = PropertyPriceHistory.__table__
            insert_stmt = (
                pg_insert(table)
                .values(
                    property_id=property_id,
                    price=price,
                    price_change=price_change,
                    price_change_pct=price_change_pct,
                    recorded_hour_utc=hour_bucket,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        table.c.property_id,
                        table.c.price,
                        table.c.recorded_hour_utc,
                    ]
                )
                .returning(table.c.id)
            )
            inserted_id = self.session.scalar(insert_stmt)
            if inserted_id is not None:
                inserted_new = True
                entry = self.session.get(PropertyPriceHistory, str(inserted_id))
            else:
                entry = self.session.scalar(
                    select(PropertyPriceHistory)
                    .where(PropertyPriceHistory.property_id == property_id)
                    .where(PropertyPriceHistory.price == price)
                    .where(PropertyPriceHistory.recorded_hour_utc == hour_bucket)
                    .order_by(PropertyPriceHistory.recorded_at.desc())
                    .limit(1)
                )
        else:
            candidate = PropertyPriceHistory(
                property_id=property_id,
                price=price,
                price_change=price_change,
                price_change_pct=price_change_pct,
                recorded_hour_utc=hour_bucket,
            )
            if hasattr(self.session, "begin_nested"):
                try:
                    with self.session.begin_nested():
                        self.session.add(candidate)
                        self.session.flush()
                except IntegrityError:
                    candidate = None
            else:
                self.session.add(candidate)
                self.session.flush()

            if candidate is not None:
                inserted_new = True
                entry = candidate
            else:
                entry = self.session.scalar(
                    select(PropertyPriceHistory)
                    .where(PropertyPriceHistory.property_id == property_id)
                    .where(PropertyPriceHistory.price == price)
                    .where(PropertyPriceHistory.recorded_hour_utc == hour_bucket)
                    .order_by(PropertyPriceHistory.recorded_at.desc())
                    .limit(1)
                )
        if entry is None:
            raise RuntimeError("failed to persist or resolve property price history entry")

        if inserted_new:
            resolved_event_type = timeline_event_type or (
                "asking_price_changed" if price_change is not None else "asking_price_set"
            )
            context = dict(timeline_context or {})
            metadata = {"origin": "price_history"}
            metadata.update(context.pop("metadata_json", {}) or {})
            dedup_key = context.pop("dedup_key", None) or f"price:{float(price):.2f}"

            PropertyTimelineRepository(self.session).add_event(
                property_id=property_id,
                event_type=resolved_event_type,
                price=price,
                price_change=price_change,
                price_change_pct=price_change_pct,
                detection_method=str(context.pop("detection_method", None) or "price_history_repository"),
                confidence_score=context.pop("confidence_score", 1.0),
                dedup_key=dedup_key,
                metadata_json=metadata,
                **context,
            )
        return entry

    def add_entry_if_new_price(
        self,
        property_id: str,
        price: Decimal | float,
        price_change: Decimal | float | None = None,
        price_change_pct: float | None = None,
        tolerance: Decimal | float = Decimal("0.01"),
        timeline_event_type: str | None = None,
        timeline_context: dict[str, Any] | None = None,
    ) -> PropertyPriceHistory | None:
        """Insert a history row only when latest recorded price is different."""
        # Safe conversion to Decimal
        price_dec = to_decimal(price)
        if price_dec is None:
            return None
            
        latest_price = self.get_latest_price(property_id)
        if latest_price is not None:
            tolerance_dec = to_decimal(tolerance, Decimal("0.01"))
            if abs(latest_price - price_dec) <= tolerance_dec:
                return None
                
        # Convert price_change to Decimal if provided
        price_change_dec = to_decimal(price_change) if price_change is not None else None
        
        return self.add_entry(
            property_id=property_id,
            price=price_dec,
            price_change=price_change_dec,
            price_change_pct=price_change_pct,
            timeline_event_type=timeline_event_type,
            timeline_context=timeline_context,
        )

    def get_for_property(self, property_id: str) -> list[PropertyPriceHistory]:
        return list(
            self.session.scalars(
                select(PropertyPriceHistory)
                .where(PropertyPriceHistory.property_id == property_id)
                .order_by(PropertyPriceHistory.recorded_at.asc())
            )
        )

    def list_for_property(self, property_id: str) -> list[PropertyPriceHistory]:
        return self.get_for_property(property_id)

    def get_latest_price(self, property_id: str) -> Decimal | None:
        entry = self.session.scalar(
            select(PropertyPriceHistory)
            .where(PropertyPriceHistory.property_id == property_id)
            .order_by(PropertyPriceHistory.recorded_at.desc())
            .limit(1)
        )
        return entry.price if entry else None


# ──────────────────────────────────────────────────────────────────────────────
# PropertyTimelineRepository
# ──────────────────────────────────────────────────────────────────────────────

class PropertyTimelineRepository:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _hour_bucket_utc(value: datetime | None) -> datetime:
        if value is None:
            ts = datetime.now(UTC)
        elif value.tzinfo is None:
            ts = value.replace(tzinfo=UTC)
        else:
            ts = value.astimezone(UTC)
        return ts.replace(minute=0, second=0, microsecond=0, tzinfo=None)

    def add_event(
        self,
        *,
        property_id: str,
        event_type: str,
        occurred_at: datetime | None = None,
        price: float | None = None,
        price_change: float | None = None,
        price_change_pct: float | None = None,
        source_id: str | None = None,
        adapter_name: str | None = None,
        source_url: str | None = None,
        detection_method: str | None = None,
        confidence_score: float | None = None,
        dedup_key: str | None = None,
        evidence: dict | None = None,
        metadata_json: dict | None = None,
    ) -> PropertyTimelineEvent | None:
        hour_bucket = self._hour_bucket_utc(occurred_at)

        entry_kwargs = {
            "property_id": property_id,
            "event_type": event_type,
            "occurred_hour_utc": hour_bucket,
            "price": price,
            "price_change": price_change,
            "price_change_pct": price_change_pct,
            "source_id": source_id,
            "adapter_name": adapter_name,
            "source_url": source_url,
            "detection_method": detection_method,
            "confidence_score": confidence_score,
            "dedup_key": dedup_key,
            "evidence": evidence or {},
            "metadata_json": metadata_json or {},
        }
        if occurred_at is not None:
            entry_kwargs["occurred_at"] = occurred_at

        bind = self.session.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""
        if dialect_name == "postgresql":
            table = PropertyTimelineEvent.__table__
            insert_stmt = (
                pg_insert(table)
                .values(**entry_kwargs)
                .on_conflict_do_nothing(
                    index_elements=[
                        table.c.property_id,
                        table.c.event_type,
                        table.c.dedup_key,
                        table.c.occurred_hour_utc,
                    ]
                )
                .returning(table.c.id)
            )
            inserted_id = self.session.scalar(insert_stmt)
            if inserted_id is None:
                return None
            return self.session.get(PropertyTimelineEvent, str(inserted_id))

        # Non-PostgreSQL fallback keeps compatibility while still handling race duplicates.
        entry = PropertyTimelineEvent(**entry_kwargs)
        if hasattr(self.session, "begin_nested"):
            try:
                with self.session.begin_nested():
                    self.session.add(entry)
                    self.session.flush()
            except IntegrityError:
                return None
            return entry

        self.session.add(entry)
        self.session.flush()
        return entry

    def list_for_property(self, property_id: str, *, limit: int = 200) -> list[PropertyTimelineEvent]:
        safe_limit = max(1, min(limit, 2000))
        return list(
            self.session.scalars(
                select(PropertyTimelineEvent)
                .where(PropertyTimelineEvent.property_id == property_id)
                .order_by(PropertyTimelineEvent.occurred_at.desc())
                .limit(safe_limit)
            )
        )


# ──────────────────────────────────────────────────────────────────────────────
# SoldPropertyRepository
# ──────────────────────────────────────────────────────────────────────────────

class SoldPropertyRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_sold(self, filters: SoldPropertyFilters) -> tuple[list[SoldProperty], int]:
        query = select(SoldProperty)
        count_query = select(func.count(SoldProperty.id))

        conditions = []

        if filters.county:
            conditions.append(SoldProperty.county == filters.county)

        if filters.min_price is not None:
            conditions.append(SoldProperty.price >= filters.min_price)

        if filters.max_price is not None:
            conditions.append(SoldProperty.price <= filters.max_price)

        if filters.date_from:
            conditions.append(SoldProperty.sale_date >= filters.date_from)

        if filters.date_to:
            conditions.append(SoldProperty.sale_date <= filters.date_to)

        if filters.address_contains:
            conditions.append(
                SoldProperty.address.ilike(f"%{filters.address_contains}%")
            )

        if filters.is_new is not None:
            conditions.append(SoldProperty.is_new.is_(filters.is_new))

        if filters.lat is not None and filters.lng is not None and filters.radius_km is not None:
            point = ST_SetSRID(ST_MakePoint(filters.lng, filters.lat), 4326)
            radius_metres = filters.radius_km * 1000
            conditions.append(
                ST_DWithin(
                    cast(SoldProperty.location_point, Geography),
                    cast(point, Geography),
                    radius_metres,
                )
            )

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        total = self.session.scalar(count_query) or 0

        query = query.order_by(SoldProperty.sale_date.desc())
        offset = (filters.page - 1) * filters.per_page
        query = query.offset(offset).limit(filters.per_page)

        items = list(self.session.scalars(query))
        return items, total

    def get_by_content_hash(self, content_hash: str) -> SoldProperty | None:
        return self.session.scalar(
            select(SoldProperty).where(SoldProperty.content_hash == content_hash)
        )

    def create(self, **kwargs) -> SoldProperty:
        location_point = _build_location_point(kwargs.get("latitude"), kwargs.get("longitude"))
        if location_point is not None:
            kwargs["location_point"] = location_point
        sold = SoldProperty(**kwargs)
        self.session.add(sold)
        self.session.flush()
        return sold

    def bulk_create(self, records: list[dict]) -> int:
        """Bulk insert sold properties. Returns count of inserted records."""
        if not records:
            return 0
        self.session.bulk_insert_mappings(SoldProperty, records)
        self.session.flush()
        return len(records)

    def count_total(self) -> int:
        return self.session.scalar(select(func.count(SoldProperty.id))) or 0

    def get_nearby_sold(
        self, lat: float, lng: float, radius_km: float = 2.0, limit: int = 20
    ) -> list[SoldProperty]:
        point = ST_SetSRID(ST_MakePoint(lng, lat), 4326)
        radius_metres = radius_km * 1000
        query = (
            select(SoldProperty)
            .where(
                ST_DWithin(
                    cast(SoldProperty.location_point, Geography),
                    cast(point, Geography),
                    radius_metres,
                )
            )
            .order_by(SoldProperty.sale_date.desc())
            .limit(limit)
        )
        return list(self.session.scalars(query))

    def get_stats_by_county(
        self,
        county: str | None = None,
        date_from=None,
        date_to=None,
        group_by: str = "month",
    ) -> list[dict]:
        """Get aggregate sold statistics, optionally grouped by time period."""
        # Group by expression
        if group_by == "year":
            period_expr = func.to_char(SoldProperty.sale_date, "YYYY")
        elif group_by == "quarter":
            period_expr = func.to_char(SoldProperty.sale_date, "YYYY-\"Q\"Q")
        else:
            period_expr = func.to_char(SoldProperty.sale_date, "YYYY-MM")

        query = (
            select(
                period_expr.label("period"),
                func.avg(SoldProperty.price).label("avg_price"),
                func.count(SoldProperty.id).label("count"),
            )
            .group_by(period_expr)
            .order_by(period_expr)
        )

        conditions = []
        if county:
            conditions.append(SoldProperty.county == county)
        if date_from:
            conditions.append(SoldProperty.sale_date >= date_from)
        if date_to:
            conditions.append(SoldProperty.sale_date <= date_to)

        if conditions:
            query = query.where(and_(*conditions))

        rows = self.session.execute(query).all()
        return [
            {"period": row.period, "avg_price": float(row.avg_price), "count": row.count}
            for row in rows
        ]


# ──────────────────────────────────────────────────────────────────────────────
# SavedSearchRepository
# ──────────────────────────────────────────────────────────────────────────────

class SavedSearchRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_all(self, active_only: bool = False) -> list[SavedSearch]:
        query = select(SavedSearch).order_by(SavedSearch.created_at.desc())
        if active_only:
            query = query.where(SavedSearch.is_active.is_(True))
        return list(self.session.scalars(query))

    def get_by_id(self, search_id: str) -> SavedSearch | None:
        return self.session.get(SavedSearch, search_id)

    def create(self, **kwargs) -> SavedSearch:
        search = SavedSearch(**kwargs)
        self.session.add(search)
        self.session.flush()
        return search

    def update(self, search_id: str, **kwargs) -> SavedSearch | None:
        search = self.get_by_id(search_id)
        if not search:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(search, key):
                setattr(search, key, value)
        search.updated_at = utc_now()
        self.session.flush()
        return search

    def delete(self, search_id: str) -> bool:
        search = self.get_by_id(search_id)
        if not search:
            return False
        self.session.delete(search)
        self.session.flush()
        return True


# ──────────────────────────────────────────────────────────────────────────────
# AlertRepository
# ──────────────────────────────────────────────────────────────────────────────

class AlertRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_alerts(
        self,
        alert_type: str | None = None,
        severity: str | None = None,
        acknowledged: bool | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Alert], int]:
        query = select(Alert)
        count_query = select(func.count(Alert.id))

        conditions = []
        if alert_type:
            conditions.append(Alert.alert_type == alert_type)
        if severity:
            conditions.append(Alert.severity == severity)
        if acknowledged is not None:
            conditions.append(Alert.acknowledged.is_(acknowledged))

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        total = self.session.scalar(count_query) or 0

        query = query.order_by(Alert.created_at.desc())
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)

        items = list(self.session.scalars(query))
        return items, total

    def get_by_id(self, alert_id: str) -> Alert | None:
        return self.session.get(Alert, alert_id)

    def create(self, **kwargs) -> Alert:
        alert = Alert(**kwargs)
        self.session.add(alert)
        self.session.flush()
        return alert

    def acknowledge(self, alert_id: str) -> Alert | None:
        alert = self.get_by_id(alert_id)
        if not alert:
            return None
        alert.acknowledged = True
        alert.acknowledged_at = utc_now()
        self.session.flush()
        return alert

    def acknowledge_all(self) -> int:
        """Acknowledge all unacknowledged alerts. Returns count acknowledged."""
        now = utc_now()
        result = self.session.execute(
            Alert.__table__.update()
            .where(Alert.acknowledged.is_(False))
            .values(acknowledged=True, acknowledged_at=now)
        )
        self.session.flush()
        return result.rowcount

    def count_unacknowledged(self) -> int:
        return (
            self.session.scalar(
                select(func.count(Alert.id)).where(Alert.acknowledged.is_(False))
            )
            or 0
        )

    def get_stats(self) -> dict:
        """Get alert statistics grouped by type."""
        rows = self.session.execute(
            select(
                Alert.alert_type,
                func.count(Alert.id).label("total"),
                func.count(Alert.id).filter(Alert.acknowledged.is_(False)).label("unacknowledged"),
            ).group_by(Alert.alert_type)
        ).all()
        return {
            "by_type": [
                {
                    "type": row.alert_type,
                    "total": row.total,
                    "unacknowledged": row.unacknowledged,
                }
                for row in rows
            ],
            "total_unacknowledged": self.count_unacknowledged(),
        }


# ──────────────────────────────────────────────────────────────────────────────
# LLMEnrichmentRepository
# ──────────────────────────────────────────────────────────────────────────────

class LLMEnrichmentRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_property_id(self, property_id: str) -> LLMEnrichment | None:
        return self.session.scalar(
            select(LLMEnrichment).where(LLMEnrichment.property_id == property_id)
        )

    def upsert(self, property_id: str, **kwargs) -> LLMEnrichment:
        """Create or update enrichment for a property."""
        enrichment = self.get_by_property_id(property_id)
        if enrichment:
            for key, value in kwargs.items():
                if hasattr(enrichment, key):
                    setattr(enrichment, key, value)
            enrichment.processed_at = utc_now()
        else:
            enrichment = LLMEnrichment(property_id=property_id, **kwargs)
            self.session.add(enrichment)
        self.session.flush()
        return enrichment

    def count_processed(self) -> int:
        return self.session.scalar(select(func.count(LLMEnrichment.id))) or 0

    def avg_processing_time(self) -> float | None:
        result = self.session.scalar(
            select(func.avg(LLMEnrichment.processing_time_ms)).where(
                LLMEnrichment.processing_time_ms.isnot(None)
            )
        )
        return float(result) if result else None


# ──────────────────────────────────────────────────────────────────────────────
# PropertyDocumentRepository
# ──────────────────────────────────────────────────────────────────────────────

class PropertyDocumentRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_document_key(self, document_key: str) -> PropertyDocument | None:
        return self.session.scalar(
            select(PropertyDocument).where(PropertyDocument.document_key == document_key)
        )

    def upsert_document(self, document_key: str, **kwargs) -> PropertyDocument:
        document = self.get_by_document_key(document_key)
        if document:
            for key, value in kwargs.items():
                if hasattr(document, key):
                    setattr(document, key, value)
            document.updated_at = utc_now()
        else:
            document = PropertyDocument(document_key=document_key, **kwargs)
            self.session.add(document)
        self.session.flush()
        return document

    def list_for_property(self, property_id: str) -> list[PropertyDocument]:
        query = (
            select(PropertyDocument)
            .where(PropertyDocument.property_id == property_id)
            .order_by(PropertyDocument.document_type.asc(), PropertyDocument.effective_at.desc().nullslast())
        )
        return list(self.session.scalars(query))

    def list_for_scope(self, scope_type: str, scope_key: str) -> list[PropertyDocument]:
        query = (
            select(PropertyDocument)
            .where(PropertyDocument.scope_type == scope_type, PropertyDocument.scope_key == scope_key)
            .order_by(PropertyDocument.document_type.asc(), PropertyDocument.effective_at.desc().nullslast())
        )
        return list(self.session.scalars(query))

    def search_documents(
        self,
        query_terms: list[str],
        *,
        county: str | None = None,
        property_id: str | None = None,
        doc_types: list[str] | None = None,
        limit: int = 20,
    ) -> list[PropertyDocument]:
        """Lexical keyword search across document content and title.

        Returns documents ordered by a combined relevance+freshness score.
        The caller is responsible for ranking/scoring if needed; this provides
        a broad retrieval set filtered to the most relevant candidates.
        """
        stmt = select(PropertyDocument)

        # Restrict by property or county scope
        if property_id:
            stmt = stmt.where(PropertyDocument.property_id == property_id)
        if county:
            stmt = stmt.where(PropertyDocument.county == county)
        if doc_types:
            stmt = stmt.where(PropertyDocument.document_type.in_(doc_types))

        # Build keyword match condition across content + title (any term)
        if query_terms:
            term_conditions = []
            for term in query_terms[:10]:  # cap at 10 terms to protect the query
                pattern = f"%{term}%"
                term_conditions.append(PropertyDocument.content.ilike(pattern))
                term_conditions.append(PropertyDocument.title.ilike(pattern))
            stmt = stmt.where(or_(*term_conditions))

        # Order: non-expired first, then by most recent effective_at
        now = datetime.now(UTC)
        stmt = stmt.where(
            or_(PropertyDocument.expires_at.is_(None), PropertyDocument.expires_at > now)
        )
        stmt = stmt.order_by(
            PropertyDocument.effective_at.desc().nullslast(),
            PropertyDocument.updated_at.desc(),
        ).limit(limit)

        return list(self.session.scalars(stmt))


# ──────────────────────────────────────────────────────────────────────────────
# BackendLogRepository
# ──────────────────────────────────────────────────────────────────────────────

class BackendLogRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_recent(
        self,
        *,
        hours: int = 24,
        limit: int = 100,
        level: str | None = None,
        event_type: str | None = None,
    ) -> list[BackendLog]:
        window_start = utc_now() - timedelta(hours=max(hours, 1))
        query = select(BackendLog).where(BackendLog.created_at >= window_start)

        if level:
            query = query.where(BackendLog.level == level.upper())
        if event_type:
            query = query.where(BackendLog.event_type == event_type)

        query = query.order_by(BackendLog.created_at.desc()).limit(limit)
        return list(self.session.scalars(query))

    def list_recent_errors(self, *, hours: int = 24, limit: int = 100) -> list[BackendLog]:
        window_start = utc_now() - timedelta(hours=max(hours, 1))
        query = (
            select(BackendLog)
            .where(BackendLog.created_at >= window_start)
            .where(BackendLog.level.in_(["ERROR", "WARNING"]))
            .order_by(BackendLog.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(query))

    def count_recent_errors(self, *, hours: int = 1) -> int:
        window_start = utc_now() - timedelta(hours=max(hours, 1))
        count_query = (
            select(func.count(BackendLog.id))
            .where(BackendLog.created_at >= window_start)
            .where(BackendLog.level.in_(["ERROR", "WARNING"]))
        )
        return int(self.session.scalar(count_query) or 0)

    def summary(self, *, hours: int = 24) -> dict:
        window_start = utc_now() - timedelta(hours=max(hours, 1))

        by_level_rows = self.session.execute(
            select(BackendLog.level, func.count(BackendLog.id).label("total"))
            .where(BackendLog.created_at >= window_start)
            .group_by(BackendLog.level)
        ).all()

        by_event_rows = self.session.execute(
            select(BackendLog.event_type, func.count(BackendLog.id).label("total"))
            .where(BackendLog.created_at >= window_start)
            .group_by(BackendLog.event_type)
        ).all()

        return {
            "hours": max(hours, 1),
            "total": sum(int(row.total or 0) for row in by_level_rows),
            "by_level": [{"level": row.level, "count": int(row.total or 0)} for row in by_level_rows],
            "by_event_type": [
                {"event_type": row.event_type, "count": int(row.total or 0)}
                for row in by_event_rows
            ],
        }


# ──────────────────────────────────────────────────────────────────────────────
# SourceQualitySnapshotRepository
# ──────────────────────────────────────────────────────────────────────────────

class SourceQualitySnapshotRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_snapshot(self, **kwargs) -> SourceQualitySnapshot:
        snapshot = SourceQualitySnapshot(**kwargs)
        self.session.add(snapshot)
        self.session.flush()
        return snapshot

    def list_recent(
        self,
        *,
        source_id: str | None = None,
        run_type: str | None = None,
        limit: int = 100,
    ) -> list[SourceQualitySnapshot]:
        query = select(SourceQualitySnapshot)

        if source_id:
            query = query.where(SourceQualitySnapshot.source_id == source_id)
        if run_type:
            query = query.where(SourceQualitySnapshot.run_type == run_type)

        query = query.order_by(SourceQualitySnapshot.created_at.desc()).limit(max(1, min(limit, 1000)))
        return list(self.session.scalars(query))


# ──────────────────────────────────────────────────────────────────────────────
# GrantProgramRepository
# ──────────────────────────────────────────────────────────────────────────────

class GrantProgramRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_programs(
        self,
        country: str | None = None,
        active_only: bool = True,
    ) -> list[GrantProgram]:
        query = select(GrantProgram).order_by(GrantProgram.name.asc())
        if country:
            query = query.where(GrantProgram.country == country)
        if active_only:
            query = query.where(GrantProgram.active.is_(True))
        return list(self.session.scalars(query))

    def get_by_id(self, grant_id: str) -> GrantProgram | None:
        return self.session.get(GrantProgram, grant_id)

    def get_by_code(self, code: str) -> GrantProgram | None:
        return self.session.scalar(select(GrantProgram).where(GrantProgram.code == code))

    def create(self, **kwargs) -> GrantProgram:
        grant = GrantProgram(**kwargs)
        self.session.add(grant)
        self.session.flush()
        return grant

    def update(self, grant_id: str, **kwargs) -> GrantProgram | None:
        grant = self.get_by_id(grant_id)
        if not grant:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(grant, key):
                setattr(grant, key, value)
        grant.updated_at = utc_now()
        self.session.flush()
        return grant


class PropertyGrantMatchRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_for_property(self, property_id: str) -> list[PropertyGrantMatch]:
        return list(
            self.session.scalars(
                select(PropertyGrantMatch)
                .options(joinedload(PropertyGrantMatch.grant_program))
                .where(PropertyGrantMatch.property_id == property_id)
                .order_by(PropertyGrantMatch.created_at.desc())
            )
        )

    def upsert_match(
        self,
        property_id: str,
        grant_program_id: str,
        status: str,
        reason: str | None = None,
        estimated_benefit: float | None = None,
        metadata: dict | None = None,
    ) -> PropertyGrantMatch:
        match = self.session.scalar(
            select(PropertyGrantMatch).where(
                and_(
                    PropertyGrantMatch.property_id == property_id,
                    PropertyGrantMatch.grant_program_id == grant_program_id,
                )
            )
        )
        if match:
            match.status = status
            match.reason = reason
            match.estimated_benefit = estimated_benefit
            match.metadata_json = metadata or {}
        else:
            match = PropertyGrantMatch(
                property_id=property_id,
                grant_program_id=grant_program_id,
                status=status,
                reason=reason,
                estimated_benefit=estimated_benefit,
                metadata_json=metadata or {},
            )
            self.session.add(match)
        self.session.flush()
        return match


# ──────────────────────────────────────────────────────────────────────────────
# ConversationRepository
# ──────────────────────────────────────────────────────────────────────────────

class ConversationRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_conversation(
        self,
        user_identifier: str,
        title: str | None = None,
        context: dict | None = None,
    ) -> Conversation:
        convo = Conversation(
            user_identifier=user_identifier,
            title=title,
            context=context or {},
        )
        self.session.add(convo)
        self.session.flush()
        return convo

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        return self.session.scalar(
            select(Conversation)
            .options(joinedload(Conversation.messages))
            .where(Conversation.id == conversation_id)
        )

    def assistant_message_quality_snapshot(self, *, hours: int = 24, limit: int = 1000) -> dict[str, float | int | None]:
        """Return citation and latency stats for recent assistant messages."""
        cutoff = utc_now() - timedelta(hours=hours)
        query = (
            select(ConversationMessage)
            .where(ConversationMessage.role == "assistant")
            .where(ConversationMessage.created_at >= cutoff)
            .order_by(ConversationMessage.created_at.desc())
            .limit(limit)
        )
        messages = list(self.session.scalars(query))

        sample_size = len(messages)
        if sample_size == 0:
            return {
                "sample_size": 0,
                "citation_coverage": None,
                "p95_latency_ms": None,
            }

        with_citations = sum(1 for message in messages if (message.citations or []))
        citation_coverage = with_citations / sample_size

        latencies = sorted(
            int(message.processing_time_ms)
            for message in messages
            if message.processing_time_ms is not None
        )
        p95_latency_ms: int | None = None
        if latencies:
            index = max(0, int(round(0.95 * len(latencies))) - 1)
            p95_latency_ms = latencies[index]

        return {
            "sample_size": sample_size,
            "citation_coverage": citation_coverage,
            "p95_latency_ms": p95_latency_ms,
        }

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        citations: list | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        processing_time_ms: int | None = None,
    ) -> ConversationMessage:
        msg = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations or [],
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            processing_time_ms=processing_time_ms,
        )
        self.session.add(msg)

        convo = self.session.get(Conversation, conversation_id)
        if convo:
            convo.updated_at = utc_now()

        self.session.flush()
        return msg


# ──────────────────────────────────────────────────────────────────────────────
# OrganicSearchRunRepository
# ──────────────────────────────────────────────────────────────────────────────

class OrganicSearchRunRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        status: str,
        triggered_from: str,
        options: dict,
        steps: list,
        error: str | None = None,
    ) -> OrganicSearchRun:
        run = OrganicSearchRun(
            status=status,
            triggered_from=triggered_from,
            options=options,
            steps=steps,
            error=error,
        )
        self.session.add(run)
        self.session.flush()
        return run

    def list_recent(self, limit: int = 20) -> list[OrganicSearchRun]:
        query = (
            select(OrganicSearchRun)
            .order_by(OrganicSearchRun.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(query))

    def get_latest_for_session(self, *, session_id: str, triggered_from: str) -> OrganicSearchRun | None:
        query = (
            select(OrganicSearchRun)
            .where(OrganicSearchRun.triggered_from == triggered_from)
            .where(OrganicSearchRun.options["session_id"].astext == session_id)
            .order_by(OrganicSearchRun.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(query)
