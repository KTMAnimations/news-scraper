"""Initial schema with TimescaleDB hypertables.

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable TimescaleDB extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("is_superuser", sa.Boolean(), default=False, nullable=False),
        sa.Column("subscription_tier", sa.String(50), default="starter"),
        sa.Column("stripe_customer_id", sa.String(255)),
        sa.Column("stripe_subscription_id", sa.String(255)),
        sa.Column("subscription_expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Create events table (will be converted to hypertable)
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("ticker", sa.String(20), index=True),
        sa.Column("headline", sa.Text()),
        sa.Column("summary", sa.Text()),
        sa.Column("source", sa.String(100), index=True),
        sa.Column("source_url", sa.Text()),
        sa.Column("event_type", sa.String(50), index=True),
        sa.Column("sentiment_score", sa.Float()),
        sa.Column("sentiment_label", sa.String(20)),
        sa.Column("alpha_score", sa.Float(), index=True),
        sa.Column("direction", sa.String(20)),
        sa.Column("urgency_level", sa.String(20)),
        sa.Column("entities", postgresql.JSONB()),
        sa.Column("metadata", postgresql.JSONB()),
        sa.Column("raw_content", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Convert events table to TimescaleDB hypertable
    op.execute(
        "SELECT create_hypertable('events', 'event_time', "
        "chunk_time_interval => INTERVAL '1 day', "
        "if_not_exists => TRUE);"
    )

    # Create watchlists table
    op.create_table(
        "watchlists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),
    )

    # Create alerts table
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("ticker", sa.String(20)),
        sa.Column("event_types", postgresql.ARRAY(sa.String(50))),
        sa.Column("min_alpha_score", sa.Float()),
        sa.Column("urgency_levels", postgresql.ARRAY(sa.String(20))),
        sa.Column("direction", sa.String(20)),
        sa.Column("delivery_method", sa.String(50), default="push"),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True)),
    )

    # Create composite indexes for common query patterns
    op.create_index(
        "ix_events_ticker_event_time",
        "events",
        ["ticker", "event_time"],
    )
    op.create_index(
        "ix_events_event_type_event_time",
        "events",
        ["event_type", "event_time"],
    )
    op.create_index(
        "ix_events_alpha_score_event_time",
        "events",
        ["alpha_score", "event_time"],
    )


def downgrade() -> None:
    op.drop_index("ix_events_alpha_score_event_time")
    op.drop_index("ix_events_event_type_event_time")
    op.drop_index("ix_events_ticker_event_time")
    op.drop_table("alerts")
    op.drop_table("watchlists")
    op.drop_table("events")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS timescaledb CASCADE;")
