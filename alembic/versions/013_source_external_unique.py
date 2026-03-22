"""Enforce source/external property uniqueness for non-null external IDs.

Revision ID: 013_source_external_unique
Revises: 012_source_quality_snapshots
Create Date: 2026-03-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "013_source_external_unique"
down_revision = "012_source_quality_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep the newest row for each duplicate source/external pair before enforcing uniqueness.
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY source_id, external_id
                        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
                    ) AS rn
                FROM properties
                WHERE external_id IS NOT NULL
            )
            DELETE FROM properties p
            USING ranked r
            WHERE p.id = r.id AND r.rn > 1
            """
        )
    )

    op.create_index(
        "uq_properties_source_external_id_not_null",
        "properties",
        ["source_id", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_properties_source_external_id_not_null", table_name="properties")
