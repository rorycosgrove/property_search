"""Create unified property documents table

Revision ID: 009_property_documents
Revises: 008_canonical_property_identity
Create Date: 2026-03-15 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "009_property_documents"
down_revision: Union[str, None] = "008_canonical_property_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "property_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_type", sa.String(60), nullable=False),
        sa.Column("scope_type", sa.String(40), nullable=False),
        sa.Column("scope_key", sa.String(255), nullable=False),
        sa.Column("document_key", sa.String(255), nullable=False, unique=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("property_id", sa.String(36), nullable=True),
        sa.Column("source_id", sa.String(36), nullable=True),
        sa.Column("canonical_property_id", sa.String(36), nullable=True),
        sa.Column("county", sa.String(100), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_property_documents_scope", "property_documents", ["scope_type", "scope_key"])
    op.create_index("ix_property_documents_property_type", "property_documents", ["property_id", "document_type"])
    op.create_index("ix_property_documents_canonical_type", "property_documents", ["canonical_property_id", "document_type"])
    op.create_index("ix_property_documents_content_hash", "property_documents", ["content_hash"])
    op.create_index("ix_property_documents_effective_at", "property_documents", ["effective_at"])
    op.create_foreign_key(
        "fk_document_property",
        "property_documents",
        "properties",
        ["property_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_document_source",
        "property_documents",
        "sources",
        ["source_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_document_source", "property_documents", type_="foreignkey")
    op.drop_constraint("fk_document_property", "property_documents", type_="foreignkey")
    op.drop_index("ix_property_documents_effective_at", table_name="property_documents")
    op.drop_index("ix_property_documents_content_hash", table_name="property_documents")
    op.drop_index("ix_property_documents_canonical_type", table_name="property_documents")
    op.drop_index("ix_property_documents_property_type", table_name="property_documents")
    op.drop_index("ix_property_documents_scope", table_name="property_documents")
    op.drop_table("property_documents")