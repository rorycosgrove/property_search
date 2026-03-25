"""Enable pg_trgm and add trigram indexes for property search.

Revision ID: 015_pg_trgm_indexes
Revises: 014_match_fields_props_sold
Create Date: 2026-03-25
"""

from __future__ import annotations

from alembic import op


revision = "015_pg_trgm_indexes"
down_revision = "014_match_fields_props_sold"
branch_labels = None
depends_on = None


def upgrade() -> None:
	op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

	op.create_index(
		"ix_properties_address_trgm",
		"properties",
		["address"],
		unique=False,
		postgresql_using="gin",
		postgresql_ops={"address": "gin_trgm_ops"},
	)
	op.create_index(
		"ix_properties_title_trgm",
		"properties",
		["title"],
		unique=False,
		postgresql_using="gin",
		postgresql_ops={"title": "gin_trgm_ops"},
	)
	op.create_index(
		"ix_sold_address_trgm",
		"sold_properties",
		["address"],
		unique=False,
		postgresql_using="gin",
		postgresql_ops={"address": "gin_trgm_ops"},
	)


def downgrade() -> None:
	op.drop_index("ix_sold_address_trgm", table_name="sold_properties")
	op.drop_index("ix_properties_title_trgm", table_name="properties")
	op.drop_index("ix_properties_address_trgm", table_name="properties")
