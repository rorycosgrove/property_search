"""Add source quality snapshots corpus table.

Revision ID: 012_source_quality_snapshots
Revises: 011_property_timeline_events
Create Date: 2026-03-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "012_source_quality_snapshots"
down_revision = "011_property_timeline_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_quality_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("adapter_name", sa.String(length=100), nullable=True),
        sa.Column("run_type", sa.String(length=30), nullable=False),
        sa.Column("total_fetched", sa.Integer(), nullable=True),
        sa.Column("parse_failed", sa.Integer(), nullable=True),
        sa.Column("new_count", sa.Integer(), nullable=True),
        sa.Column("updated_count", sa.Integer(), nullable=True),
        sa.Column("price_unchanged_count", sa.Integer(), nullable=True),
        sa.Column("dedup_conflicts", sa.Integer(), nullable=True),
        sa.Column("candidates_scored", sa.Integer(), nullable=True),
        sa.Column("created_count", sa.Integer(), nullable=True),
        sa.Column("auto_enabled_count", sa.Integer(), nullable=True),
        sa.Column("pending_approval_count", sa.Integer(), nullable=True),
        sa.Column("existing_count", sa.Integer(), nullable=True),
        sa.Column("skipped_invalid_count", sa.Integer(), nullable=True),
        sa.Column("skipped_invalid_config_count", sa.Integer(), nullable=True),
        sa.Column("score_avg", sa.Float(), nullable=True),
        sa.Column("score_max", sa.Float(), nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=True),
        sa.Column("follow_links", sa.Boolean(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], name="fk_source_quality_source", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_source_quality_snapshots_source_id", "source_quality_snapshots", ["source_id"], unique=False)
    op.create_index("ix_source_quality_snapshots_adapter_name", "source_quality_snapshots", ["adapter_name"], unique=False)
    op.create_index("ix_source_quality_snapshots_run_type", "source_quality_snapshots", ["run_type"], unique=False)
    op.create_index("ix_source_quality_snapshots_created_at", "source_quality_snapshots", ["created_at"], unique=False)
    op.create_index(
        "ix_source_quality_run_created",
        "source_quality_snapshots",
        ["run_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_source_quality_source_created",
        "source_quality_snapshots",
        ["source_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_source_quality_source_created", table_name="source_quality_snapshots")
    op.drop_index("ix_source_quality_run_created", table_name="source_quality_snapshots")
    op.drop_index("ix_source_quality_snapshots_created_at", table_name="source_quality_snapshots")
    op.drop_index("ix_source_quality_snapshots_run_type", table_name="source_quality_snapshots")
    op.drop_index("ix_source_quality_snapshots_adapter_name", table_name="source_quality_snapshots")
    op.drop_index("ix_source_quality_snapshots_source_id", table_name="source_quality_snapshots")
    op.drop_table("source_quality_snapshots")
