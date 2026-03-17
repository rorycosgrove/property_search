"""Expand llm_enrichments.investment_potential to Text.

Revision ID: 010_llm_invpot_text
Revises: 009_property_documents
Create Date: 2026-03-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "010_llm_invpot_text"
down_revision = "009_property_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "llm_enrichments",
        "investment_potential",
        existing_type=sa.String(length=50),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "llm_enrichments",
        "investment_potential",
        existing_type=sa.Text(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
