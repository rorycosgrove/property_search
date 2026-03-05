"""
SQLAlchemy ORM models for the Property Search application.

All tables are defined here. Business logic should not import these directly;
use the repository layer instead (packages.storage.repositories).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ──────────────────────────────────────────────────────────────────────────────
# Source — represents a configured data source (scraper, RSS feed, CSV import)
# ──────────────────────────────────────────────────────────────────────────────

class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    adapter_type: Mapped[str] = mapped_column(
        Enum("scraper", "rss", "csv", name="adapter_type_enum", create_constraint=True),
        nullable=False,
    )
    adapter_name: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    poll_interval_seconds: Mapped[int] = mapped_column(Integer, default=900, server_default="900")
    tags: Mapped[list] = mapped_column(ARRAY(String), default=list, server_default="{}")

    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_listings: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default="now()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default="now()", onupdate=_utcnow
    )

    # Relationships
    properties: Mapped[list[Property]] = relationship("Property", back_populates="source")


# ──────────────────────────────────────────────────────────────────────────────
# Property — a property listing from any source
# ──────────────────────────────────────────────────────────────────────────────

class Property(Base):
    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(
        String(36),
        # ForeignKey defined via explicit constraint below for flexibility
        nullable=False,
        index=True,
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Core listing fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    # Address fields
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    town: Mapped[str | None] = mapped_column(String(255), nullable=True)
    county: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    eircode: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Pricing
    price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True, index=True)
    price_text: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Property details
    property_type: Mapped[str | None] = mapped_column(
        Enum(
            "house", "apartment", "duplex", "bungalow", "site", "studio", "other",
            name="property_type_enum", create_constraint=True,
        ),
        nullable=True,
        index=True,
    )
    sale_type: Mapped[str] = mapped_column(
        Enum("sale", "auction", "new_home", "site", name="sale_type_enum", create_constraint=True),
        default="sale",
        server_default="sale",
    )
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floor_area_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)
    ber_rating: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    ber_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Media & features
    images: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    features: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    raw_data: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    # Geospatial
    location_point = mapped_column(
        Geometry(geometry_type="POINT", srid=4326), nullable=True, index=True
    )
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Lifecycle
    status: Mapped[str] = mapped_column(
        Enum(
            "new", "active", "price_changed", "sale_agreed", "sold", "withdrawn",
            name="property_status_enum", create_constraint=True,
        ),
        default="new",
        server_default="new",
        index=True,
    )
    first_listed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default="now()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default="now()", onupdate=_utcnow
    )

    # Relationships
    source: Mapped[Source] = relationship("Source", back_populates="properties")
    price_history: Mapped[list[PropertyPriceHistory]] = relationship(
        "PropertyPriceHistory", back_populates="property", order_by="PropertyPriceHistory.recorded_at.desc()"
    )
    enrichment: Mapped[LLMEnrichment | None] = relationship(
        "LLMEnrichment", back_populates="property", uselist=False
    )
    alerts: Mapped[list[Alert]] = relationship("Alert", back_populates="property")

    __table_args__ = (
        Index("ix_properties_county_price", "county", "price"),
        Index("ix_properties_status_created", "status", "created_at"),
        {"schema": None},
    )


# ──────────────────────────────────────────────────────────────────────────────
# PropertyPriceHistory — tracks price changes over time
# ──────────────────────────────────────────────────────────────────────────────

class PropertyPriceHistory(Base):
    __tablename__ = "property_price_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    property_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    price_change: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default="now()"
    )

    # Relationships
    property: Mapped[Property] = relationship("Property", back_populates="price_history")

    __table_args__ = (
        Index("ix_price_history_property_date", "property_id", "recorded_at"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# SoldProperty — from Property Price Register (PPR)
# ──────────────────────────────────────────────────────────────────────────────

class SoldProperty(Base):
    __tablename__ = "sold_properties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    county: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_new: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_full_market_price: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    vat_exclusive: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    property_size_description: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Geospatial
    location_point = mapped_column(
        Geometry(geometry_type="POINT", srid=4326), nullable=True, index=True
    )
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default="now()"
    )

    __table_args__ = (
        Index("ix_sold_county_date", "county", "sale_date"),
        Index("ix_sold_county_price", "county", "price"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# SavedSearch — user search criteria with notification preferences
# ──────────────────────────────────────────────────────────────────────────────

class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    criteria: Mapped[dict] = mapped_column(JSONB, nullable=False)
    notify_new_listings: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notify_price_drops: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notify_method: Mapped[str] = mapped_column(
        Enum("in_app", "email", "both", name="notify_method_enum", create_constraint=True),
        default="in_app",
        server_default="in_app",
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default="now()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default="now()", onupdate=_utcnow
    )

    # Relationships
    alerts: Mapped[list[Alert]] = relationship("Alert", back_populates="saved_search")


# ──────────────────────────────────────────────────────────────────────────────
# Alert — generated alerts for price drops, new matches, etc.
# ──────────────────────────────────────────────────────────────────────────────

class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    property_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    saved_search_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    alert_type: Mapped[str] = mapped_column(
        Enum(
            "new_listing", "price_drop", "price_increase", "sale_agreed",
            "market_trend", "back_on_market",
            name="alert_type_enum", create_constraint=True,
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(
        Enum("low", "medium", "high", name="alert_severity_enum", create_constraint=True),
        default="medium",
        server_default="medium",
    )
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSONB, default=dict, server_default="{}"
    )
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default="now()"
    )

    # Relationships
    property: Mapped[Property | None] = relationship("Property", back_populates="alerts")
    saved_search: Mapped[SavedSearch | None] = relationship("SavedSearch", back_populates="alerts")

    __table_args__ = (
        Index("ix_alerts_type_acknowledged", "alert_type", "acknowledged"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# LLMEnrichment — LLM analysis results for a property
# ──────────────────────────────────────────────────────────────────────────────

class LLMEnrichment(Base):
    __tablename__ = "llm_enrichments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    property_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    pros: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    cons: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    extracted_features: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    neighbourhood_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    investment_potential: Mapped[str | None] = mapped_column(String(50), nullable=True)

    llm_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default="now()"
    )
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    property: Mapped[Property] = relationship("Property", back_populates="enrichment")


# ── Foreign Key constraints (defined after all tables exist) ──────────────────
# Using SQLAlchemy column-level FK on the mapped_column directly would also work,
# but this way keeps the model definitions cleaner and avoids circular import issues.

from sqlalchemy import ForeignKeyConstraint  # noqa: E402

Property.__table__.append_constraint(
    ForeignKeyConstraint(["source_id"], ["sources.id"], name="fk_property_source")
)
PropertyPriceHistory.__table__.append_constraint(
    ForeignKeyConstraint(["property_id"], ["properties.id"], name="fk_pricehistory_property")
)
Alert.__table__.append_constraint(
    ForeignKeyConstraint(["property_id"], ["properties.id"], name="fk_alert_property")
)
Alert.__table__.append_constraint(
    ForeignKeyConstraint(
        ["saved_search_id"], ["saved_searches.id"], name="fk_alert_savedsearch"
    )
)
LLMEnrichment.__table__.append_constraint(
    ForeignKeyConstraint(["property_id"], ["properties.id"], name="fk_enrichment_property")
)
