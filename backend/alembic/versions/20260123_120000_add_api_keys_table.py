"""Add API keys table for programmatic access.

Revision ID: 003_api_keys
Revises: 002_sync_models
Create Date: 2026-01-23 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_api_keys"
down_revision: Union[str, None] = "002_sync_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create api_keys table."""
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("scopes", postgresql.ARRAY(sa.String(50)), default=["read"]),
        sa.Column("rate_limit_override", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_count", sa.Integer(), default=0, nullable=False),
        sa.Column("last_ip", sa.String(45), nullable=True),
    )

    # Create indexes
    op.create_index(
        "ix_api_keys_key_hash",
        "api_keys",
        ["key_hash"],
        unique=True,
    )
    op.create_index(
        "ix_api_keys_user_active",
        "api_keys",
        ["user_id", "is_active"],
    )


def downgrade() -> None:
    """Drop api_keys table."""
    op.drop_index("ix_api_keys_user_active")
    op.drop_index("ix_api_keys_key_hash")
    op.drop_table("api_keys")
