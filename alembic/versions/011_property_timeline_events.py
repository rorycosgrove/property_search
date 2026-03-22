"""Add unified property timeline events table.

Revision ID: 011_property_timeline_events
Revises: 010_llm_invpot_text
Create Date: 2026-03-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "011_property_timeline_events"
down_revision = "010_llm_invpot_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "property_timeline_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("property_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "occurred_hour_utc",
            sa.DateTime(timezone=False),
            server_default=sa.text("date_trunc('hour', now() AT TIME ZONE 'UTC')"),
            nullable=False,
        ),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_change", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_change_pct", sa.Float(), nullable=True),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("adapter_name", sa.String(length=100), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("detection_method", sa.String(length=100), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("dedup_key", sa.String(length=255), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], name="fk_timeline_property", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_property_timeline_events_property_id", "property_timeline_events", ["property_id"], unique=False)
    op.create_index("ix_property_timeline_events_event_type", "property_timeline_events", ["event_type"], unique=False)
    op.create_index("ix_property_timeline_events_source_id", "property_timeline_events", ["source_id"], unique=False)
    op.create_index(
        "ix_timeline_property_date",
        "property_timeline_events",
        ["property_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "uq_timeline_event_property_type_key_hour",
        "property_timeline_events",
        ["property_id", "event_type", "dedup_key", "occurred_hour_utc"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_timeline_event_property_type_key_hour", table_name="property_timeline_events")
    op.drop_index("ix_timeline_property_date", table_name="property_timeline_events")
    op.drop_index("ix_property_timeline_events_source_id", table_name="property_timeline_events")
    op.drop_index("ix_property_timeline_events_event_type", table_name="property_timeline_events")
    op.drop_index("ix_property_timeline_events_property_id", table_name="property_timeline_events")
    op.drop_table("property_timeline_events")
