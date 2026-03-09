"""Add backend logs table

Revision ID: 007_backend_logs
Revises: 006_organic_search_runs
Create Date: 2026-03-09 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "007_backend_logs"
down_revision: Union[str, None] = "006_organic_search_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backend_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("component", sa.String(100), nullable=False, server_default=sa.text("'worker'")),
        sa.Column("source_id", sa.String(36), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_backend_logs_created_at", "backend_logs", ["created_at"])
    op.create_index("ix_backend_logs_source_id", "backend_logs", ["source_id"])
    op.create_index("ix_backend_logs_event_created", "backend_logs", ["event_type", "created_at"])
    op.create_index("ix_backend_logs_level_created", "backend_logs", ["level", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_backend_logs_level_created", table_name="backend_logs")
    op.drop_index("ix_backend_logs_event_created", table_name="backend_logs")
    op.drop_index("ix_backend_logs_source_id", table_name="backend_logs")
    op.drop_index("ix_backend_logs_created_at", table_name="backend_logs")
    op.drop_table("backend_logs")
