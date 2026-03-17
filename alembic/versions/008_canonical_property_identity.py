"""Add canonical property identity indexes

Revision ID: 008_canonical_property_identity
Revises: 007_backend_logs
Create Date: 2026-03-15 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "008_canonical_property_identity"
down_revision: Union[str, None] = "007_backend_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("canonical_property_id", sa.String(length=36), nullable=True))
    op.create_index(
        "ix_properties_canonical_property_id",
        "properties",
        ["canonical_property_id"],
        unique=False,
    )
    op.create_index(
        "ix_properties_source_external_id",
        "properties",
        ["source_id", "external_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_properties_source_external_id", table_name="properties")
    op.drop_index("ix_properties_canonical_property_id", table_name="properties")
    op.drop_column("properties", "canonical_property_id")