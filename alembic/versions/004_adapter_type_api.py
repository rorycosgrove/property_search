"""Add api value to adapter_type enum

Revision ID: 004_adapter_type_api
Revises: 003_grants_and_conversations
Create Date: 2026-03-08 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_adapter_type_api"
down_revision: Union[str, None] = "003_grants_and_conversations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE adapter_type_enum ADD VALUE IF NOT EXISTS 'api'")


def downgrade() -> None:
    # PostgreSQL enums cannot safely remove values in place.
    op.execute(sa.text("SELECT 1"))
