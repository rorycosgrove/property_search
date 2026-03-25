"""Add persisted address match fields for properties and sold_properties.

Revision ID: 014_match_fields_props_sold
Revises: 013_source_external_unique
Create Date: 2026-03-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "014_match_fields_props_sold"
down_revision = "013_source_external_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("address_normalized", sa.String(length=500), nullable=True))
    op.add_column("properties", sa.Column("fuzzy_address_hash", sa.String(length=16), nullable=True))
    op.create_index("ix_properties_address_normalized", "properties", ["address_normalized"], unique=False)
    op.create_index("ix_properties_fuzzy_address_hash", "properties", ["fuzzy_address_hash"], unique=False)

    op.add_column("sold_properties", sa.Column("address_normalized", sa.String(length=500), nullable=True))
    op.add_column("sold_properties", sa.Column("fuzzy_address_hash", sa.String(length=16), nullable=True))
    op.create_index("ix_sold_address_normalized", "sold_properties", ["address_normalized"], unique=False)
    op.create_index("ix_sold_fuzzy_address_hash", "sold_properties", ["fuzzy_address_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sold_fuzzy_address_hash", table_name="sold_properties")
    op.drop_index("ix_sold_address_normalized", table_name="sold_properties")
    op.drop_column("sold_properties", "fuzzy_address_hash")
    op.drop_column("sold_properties", "address_normalized")

    op.drop_index("ix_properties_fuzzy_address_hash", table_name="properties")
    op.drop_index("ix_properties_address_normalized", table_name="properties")
    op.drop_column("properties", "fuzzy_address_hash")
    op.drop_column("properties", "address_normalized")
