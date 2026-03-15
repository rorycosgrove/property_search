"""Add organic search run ledger table

Revision ID: 006_organic_search_runs
Revises: 005_price_history_dedup_index
Create Date: 2026-03-08 04:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "006_organic_search_runs"
down_revision: Union[str, None] = "005_price_history_dedup_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organic_search_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("triggered_from", sa.String(length=80), nullable=False, server_default=sa.text("'api'")),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organic_search_runs_status", "organic_search_runs", ["status"], unique=False)
    op.create_index("ix_organic_search_runs_created_at", "organic_search_runs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_organic_search_runs_created_at", table_name="organic_search_runs")
    op.drop_index("ix_organic_search_runs_status", table_name="organic_search_runs")
    op.drop_table("organic_search_runs")
