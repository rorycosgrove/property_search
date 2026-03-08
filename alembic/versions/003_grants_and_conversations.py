"""Add grants and conversations tables

Revision ID: 003_grants_and_conversations
Revises: 002_indexes_fk
Create Date: 2026-03-07 21:25:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "003_grants_and_conversations"
down_revision: Union[str, None] = "002_indexes_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "grant_programs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("country", sa.String(20), nullable=False),
        sa.Column("region", sa.String(120), nullable=True),
        sa.Column("authority", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("eligibility_rules", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("benefit_type", sa.String(80), nullable=True),
        sa.Column("max_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default=sa.text("'EUR'")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_grant_programs_code"),
    )
    op.create_index("ix_grant_programs_code", "grant_programs", ["code"])
    op.create_index("ix_grant_programs_country", "grant_programs", ["country"])
    op.create_index("ix_grant_programs_region", "grant_programs", ["region"])

    op.create_table(
        "property_grant_matches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("property_id", sa.String(36), nullable=False),
        sa.Column("grant_program_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("estimated_benefit", sa.Numeric(12, 2), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], name="fk_grantmatch_property", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["grant_program_id"], ["grant_programs.id"], name="fk_grantmatch_program", ondelete="CASCADE"),
    )
    op.create_index("ix_property_grant_matches_property_id", "property_grant_matches", ["property_id"])
    op.create_index("ix_property_grant_matches_grant_program_id", "property_grant_matches", ["grant_program_id"])
    op.create_index(
        "ix_property_grant_matches_property_program",
        "property_grant_matches",
        ["property_id", "grant_program_id"],
        unique=True,
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("user_identifier", sa.String(120), nullable=False),
        sa.Column("context", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_conversations_user_identifier", "conversations", ["user_identifier"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name="fk_message_conversation", ondelete="CASCADE"),
    )
    op.create_index("ix_conversation_messages_conversation_id", "conversation_messages", ["conversation_id"])
    op.create_index("ix_conversation_messages_role", "conversation_messages", ["role"])


def downgrade() -> None:
    op.drop_index("ix_conversation_messages_role", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_conversation_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")

    op.drop_index("ix_conversations_user_identifier", table_name="conversations")
    op.drop_table("conversations")

    op.drop_index("ix_property_grant_matches_property_program", table_name="property_grant_matches")
    op.drop_index("ix_property_grant_matches_grant_program_id", table_name="property_grant_matches")
    op.drop_index("ix_property_grant_matches_property_id", table_name="property_grant_matches")
    op.drop_table("property_grant_matches")

    op.drop_index("ix_grant_programs_region", table_name="grant_programs")
    op.drop_index("ix_grant_programs_country", table_name="grant_programs")
    op.drop_index("ix_grant_programs_code", table_name="grant_programs")
    op.drop_table("grant_programs")
