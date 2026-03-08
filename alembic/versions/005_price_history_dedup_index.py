"""Add duplicate suppression index for price history

Revision ID: 005_price_history_dedup_index
Revises: 004_adapter_type_api
Create Date: 2026-03-08 00:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005_price_history_dedup_index"
down_revision: Union[str, None] = "004_adapter_type_api"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add explicit UTC hour bucket column to support immutable-safe unique indexing.
    op.execute(
        sa.text(
            """
            ALTER TABLE property_price_history
            ADD COLUMN IF NOT EXISTS recorded_hour_utc TIMESTAMP
            """
        )
    )

    # Backfill UTC hour buckets for existing rows.
    op.execute(
        sa.text(
            """
            UPDATE property_price_history
            SET recorded_hour_utc = date_trunc('hour', recorded_at AT TIME ZONE 'UTC')
            WHERE recorded_hour_utc IS NULL
            """
        )
    )

    # Keep earliest row per (property, price, UTC hour bucket), remove duplicates.
    op.execute(
        sa.text(
            """
            DELETE FROM property_price_history p
            USING property_price_history q
            WHERE p.id > q.id
              AND p.property_id = q.property_id
              AND p.price = q.price
              AND p.recorded_hour_utc = q.recorded_hour_utc
            """
        )
    )

    # Ensure column stays populated for future inserts.
    op.alter_column(
        "property_price_history",
        "recorded_hour_utc",
        existing_type=sa.DateTime(timezone=False),
        nullable=False,
        server_default=sa.text("date_trunc('hour', now() AT TIME ZONE 'UTC')"),
    )

    # Prevent duplicate same-price events caused by retries in tight windows.
    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_price_history_property_price_hour
            ON property_price_history (property_id, price, recorded_hour_utc)
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DROP INDEX IF EXISTS uq_price_history_property_price_hour
            """
        )
    )
    op.execute(
        sa.text(
            """
            ALTER TABLE property_price_history
            DROP COLUMN IF EXISTS recorded_hour_utc
            """
        )
    )
