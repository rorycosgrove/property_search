"""Initial schema: all tables

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # --- Enum types ---
    adapter_type_enum = postgresql.ENUM(
        "scraper", "rss", "csv", name="adapter_type_enum", create_type=False
    )
    property_type_enum = postgresql.ENUM(
        "house", "apartment", "duplex", "bungalow", "site", "studio", "other",
        name="property_type_enum", create_type=False,
    )
    sale_type_enum = postgresql.ENUM(
        "sale", "auction", "new_home", "site", name="sale_type_enum", create_type=False
    )
    property_status_enum = postgresql.ENUM(
        "new", "active", "price_changed", "sale_agreed", "sold", "withdrawn",
        name="property_status_enum", create_type=False,
    )
    notify_method_enum = postgresql.ENUM(
        "in_app", "email", "both", name="notify_method_enum", create_type=False
    )
    alert_type_enum = postgresql.ENUM(
        "new_listing", "price_drop", "price_increase", "sale_agreed",
        "market_trend", "back_on_market",
        name="alert_type_enum", create_type=False,
    )
    alert_severity_enum = postgresql.ENUM(
        "low", "medium", "high", name="alert_severity_enum", create_type=False
    )

    adapter_type_enum.create(op.get_bind(), checkfirst=True)
    property_type_enum.create(op.get_bind(), checkfirst=True)
    sale_type_enum.create(op.get_bind(), checkfirst=True)
    property_status_enum.create(op.get_bind(), checkfirst=True)
    notify_method_enum.create(op.get_bind(), checkfirst=True)
    alert_type_enum.create(op.get_bind(), checkfirst=True)
    alert_severity_enum.create(op.get_bind(), checkfirst=True)

    # --- sources ---
    op.create_table(
        "sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(1024), unique=True, nullable=False),
        sa.Column("adapter_type", adapter_type_enum, nullable=False),
        sa.Column("adapter_name", sa.String(100), nullable=False),
        sa.Column("config", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("poll_interval_seconds", sa.Integer, server_default=sa.text("900"), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String), server_default=sa.text("'{}'::varchar[]"), nullable=True),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("error_count", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("total_listings", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- properties ---
    op.create_table(
        "properties",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), nullable=False, index=True),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("content_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("address_line1", sa.String(255), nullable=True),
        sa.Column("address_line2", sa.String(255), nullable=True),
        sa.Column("town", sa.String(255), nullable=True),
        sa.Column("county", sa.String(100), nullable=True, index=True),
        sa.Column("eircode", sa.String(10), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=True, index=True),
        sa.Column("price_text", sa.String(100), nullable=True),
        sa.Column("property_type", property_type_enum, nullable=True, index=True),
        sa.Column("sale_type", sale_type_enum, server_default=sa.text("'sale'"), nullable=True),
        sa.Column("bedrooms", sa.Integer, nullable=True, index=True),
        sa.Column("bathrooms", sa.Integer, nullable=True),
        sa.Column("floor_area_sqm", sa.Float, nullable=True),
        sa.Column("ber_rating", sa.String(10), nullable=True, index=True),
        sa.Column("ber_number", sa.String(20), nullable=True),
        sa.Column("images", postgresql.JSONB, server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column("features", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("raw_data", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("status", property_status_enum, server_default=sa.text("'new'"), nullable=True, index=True),
        sa.Column("first_listed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_properties_county_price", "properties", ["county", "price"])
    op.create_index("ix_properties_status_created", "properties", ["status", "created_at"])

    # PostGIS spatial column
    op.execute(
        "SELECT AddGeometryColumn('properties', 'location_point', 4326, 'POINT', 2)"
    )
    op.execute(
        "CREATE INDEX ix_properties_location_point ON properties USING GIST (location_point)"
    )

    # FK: properties.source_id -> sources.id
    op.create_foreign_key(
        "fk_property_source", "properties", "sources", ["source_id"], ["id"]
    )

    # --- property_price_history ---
    op.create_table(
        "property_price_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("property_id", sa.String(36), nullable=False, index=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("price_change", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_change_pct", sa.Float, nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_price_history_property_date", "property_price_history", ["property_id", "recorded_at"]
    )
    op.create_foreign_key(
        "fk_pricehistory_property", "property_price_history", "properties", ["property_id"], ["id"]
    )

    # --- sold_properties ---
    op.create_table(
        "sold_properties",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("county", sa.String(100), nullable=False, index=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("sale_date", sa.Date, nullable=False, index=True),
        sa.Column("is_new", sa.Boolean, nullable=False),
        sa.Column("is_full_market_price", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("vat_exclusive", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("property_size_description", sa.String(200), nullable=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("content_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sold_county_date", "sold_properties", ["county", "sale_date"])
    op.create_index("ix_sold_county_price", "sold_properties", ["county", "price"])
    op.execute(
        "SELECT AddGeometryColumn('sold_properties', 'location_point', 4326, 'POINT', 2)"
    )
    op.execute(
        "CREATE INDEX ix_sold_properties_location_point ON sold_properties USING GIST (location_point)"
    )

    # --- saved_searches ---
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("criteria", postgresql.JSONB, nullable=False),
        sa.Column("notify_new_listings", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("notify_price_drops", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("notify_method", notify_method_enum, server_default=sa.text("'in_app'"), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("last_matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- alerts ---
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("property_id", sa.String(36), nullable=True, index=True),
        sa.Column("saved_search_id", sa.String(36), nullable=True, index=True),
        sa.Column("alert_type", alert_type_enum, nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("severity", alert_severity_enum, server_default=sa.text("'medium'"), nullable=False),
        sa.Column("metadata", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("acknowledged", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_alerts_type_acknowledged", "alerts", ["alert_type", "acknowledged"])
    op.create_foreign_key(
        "fk_alert_property", "alerts", "properties", ["property_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_alert_savedsearch", "alerts", "saved_searches", ["saved_search_id"], ["id"]
    )

    # --- llm_enrichments ---
    op.create_table(
        "llm_enrichments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("property_id", sa.String(36), unique=True, nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("value_score", sa.Float, nullable=True),
        sa.Column("value_reasoning", sa.Text, nullable=True),
        sa.Column("pros", postgresql.JSONB, server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column("cons", postgresql.JSONB, server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column("extracted_features", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("neighbourhood_notes", sa.Text, nullable=True),
        sa.Column("investment_potential", sa.String(50), nullable=True),
        sa.Column("llm_provider", sa.String(50), nullable=True),
        sa.Column("llm_model", sa.String(100), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processing_time_ms", sa.Integer, nullable=True),
    )
    op.create_foreign_key(
        "fk_enrichment_property", "llm_enrichments", "properties", ["property_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_table("llm_enrichments")
    op.drop_table("alerts")
    op.drop_table("saved_searches")
    op.drop_table("sold_properties")
    op.drop_table("property_price_history")
    op.drop_table("properties")
    op.drop_table("sources")

    # Drop enum types
    for name in [
        "alert_severity_enum", "alert_type_enum", "notify_method_enum",
        "property_status_enum", "sale_type_enum", "property_type_enum",
        "adapter_type_enum",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {name}")
