"""Sync schema with current SQLAlchemy models.

This migration updates the schema to match the models defined in
backend.storage.timescale.models including:
- Events table: add new columns, rename source->source_name, composite PK
- Users table: add subscription_status, fcm_tokens, is_verified columns
- Watchlists table: add alert_enabled column

Revision ID: 003_sync_models
Revises: 002_continuous_aggregates
Create Date: 2026-01-23 10:04:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_sync_models"
down_revision: Union[str, None] = "002_continuous_aggregates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # EVENTS TABLE UPDATES
    # =========================================================================

    # Rename source column to source_name
    op.alter_column("events", "source", new_column_name="source_name")

    # Add new columns to events table
    op.add_column(
        "events",
        sa.Column("ingest_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("event_category", sa.String(50), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("content", sa.Text(), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("sentiment_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("extracted_tickers", postgresql.ARRAY(sa.String()), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("extracted_companies", postgresql.ARRAY(sa.String()), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("extracted_people", postgresql.ARRAY(sa.String()), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("extracted_amounts", postgresql.JSON(), nullable=True),
    )

    # Set default for ingest_time on existing rows
    op.execute("UPDATE events SET ingest_time = created_at WHERE ingest_time IS NULL")

    # Make ingest_time non-nullable after populating
    op.alter_column("events", "ingest_time", nullable=False)

    # Rename existing index if needed (source -> source_name)
    # Note: TimescaleDB hypertables may have special index handling

    # Add new indexes for events
    op.create_index(
        "idx_events_urgency",
        "events",
        ["urgency_level", "event_time"],
        if_not_exists=True,
    )

    # =========================================================================
    # USERS TABLE UPDATES
    # =========================================================================

    # Add new columns to users table
    op.add_column(
        "users",
        sa.Column("subscription_status", sa.String(50), server_default="active", nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("fcm_tokens", postgresql.JSON(), server_default="[]", nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=True),
    )

    # =========================================================================
    # WATCHLISTS TABLE UPDATES
    # =========================================================================

    # Add alert_enabled column to watchlists
    op.add_column(
        "watchlists",
        sa.Column("alert_enabled", sa.Boolean(), server_default="true", nullable=True),
    )


def downgrade() -> None:
    # =========================================================================
    # WATCHLISTS TABLE - REVERT
    # =========================================================================
    op.drop_column("watchlists", "alert_enabled")

    # =========================================================================
    # USERS TABLE - REVERT
    # =========================================================================
    op.drop_column("users", "is_verified")
    op.drop_column("users", "fcm_tokens")
    op.drop_column("users", "subscription_status")

    # =========================================================================
    # EVENTS TABLE - REVERT
    # =========================================================================

    # Drop new index
    op.drop_index("idx_events_urgency", table_name="events", if_exists=True)

    # Make ingest_time nullable again for reverting
    op.alter_column("events", "ingest_time", nullable=True)

    # Drop new columns from events
    op.drop_column("events", "extracted_amounts")
    op.drop_column("events", "extracted_people")
    op.drop_column("events", "extracted_companies")
    op.drop_column("events", "extracted_tickers")
    op.drop_column("events", "sentiment_confidence")
    op.drop_column("events", "content")
    op.drop_column("events", "event_category")
    op.drop_column("events", "ingest_time")

    # Rename source_name back to source
    op.alter_column("events", "source_name", new_column_name="source")
