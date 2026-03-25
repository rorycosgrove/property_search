"""Add persistent geocode cache table.

Revision ID: 016_add_geocode_cache_table
Revises: 015_pg_trgm_indexes
Create Date: 2026-03-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "016_add_geocode_cache_table"
down_revision = "015_pg_trgm_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
	op.create_table(
		"geocode_cache",
		sa.Column("id", sa.String(length=36), nullable=False),
		sa.Column("query", sa.String(length=600), nullable=False),
		sa.Column("provider", sa.String(length=50), nullable=False, server_default="nominatim"),
		sa.Column("latitude", sa.Float(), nullable=False),
		sa.Column("longitude", sa.Float(), nullable=False),
		sa.Column("display_name", sa.Text(), nullable=True),
		sa.Column("confidence", sa.Float(), nullable=True),
		sa.Column("raw_json", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
		sa.Column("hit_count", sa.Integer(), nullable=False, server_default="1"),
		sa.Column("last_hit_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
		sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
		sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
		sa.PrimaryKeyConstraint("id"),
	)
	op.create_index("ix_geocode_cache_query", "geocode_cache", ["query"], unique=True)
	op.create_index("ix_geocode_cache_last_hit_at", "geocode_cache", ["last_hit_at"], unique=False)
	op.create_index(
		"ix_geocode_cache_provider_last_hit",
		"geocode_cache",
		["provider", "last_hit_at"],
		unique=False,
	)


def downgrade() -> None:
	op.drop_index("ix_geocode_cache_provider_last_hit", table_name="geocode_cache")
	op.drop_index("ix_geocode_cache_last_hit_at", table_name="geocode_cache")
	op.drop_index("ix_geocode_cache_query", table_name="geocode_cache")
	op.drop_table("geocode_cache")
