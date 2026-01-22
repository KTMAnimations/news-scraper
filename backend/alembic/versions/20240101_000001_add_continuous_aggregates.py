"""Add TimescaleDB continuous aggregates for analytics.

Revision ID: 002_continuous_aggregates
Revises: 001_initial
Create Date: 2024-01-01 00:00:01.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_continuous_aggregates"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create continuous aggregate for hourly ticker sentiment
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS ticker_sentiment_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', event_time) AS bucket,
            ticker,
            COUNT(*) AS event_count,
            AVG(sentiment_score) AS avg_sentiment,
            AVG(alpha_score) AS avg_alpha,
            SUM(CASE WHEN direction = 'bullish' THEN 1 ELSE 0 END) AS bullish_count,
            SUM(CASE WHEN direction = 'bearish' THEN 1 ELSE 0 END) AS bearish_count
        FROM events
        WHERE ticker IS NOT NULL
        GROUP BY bucket, ticker
        WITH NO DATA;
    """)

    # Add refresh policy for hourly aggregates (refresh every hour, covering last 2 hours)
    op.execute("""
        SELECT add_continuous_aggregate_policy('ticker_sentiment_hourly',
            start_offset => INTERVAL '2 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => TRUE);
    """)

    # Create continuous aggregate for daily ticker summary
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS ticker_summary_daily
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 day', event_time) AS bucket,
            ticker,
            COUNT(*) AS event_count,
            AVG(sentiment_score) AS avg_sentiment,
            AVG(alpha_score) AS avg_alpha,
            MAX(alpha_score) AS max_alpha,
            MIN(alpha_score) AS min_alpha,
            COUNT(DISTINCT event_type) AS event_type_count,
            array_agg(DISTINCT event_type) AS event_types
        FROM events
        WHERE ticker IS NOT NULL
        GROUP BY bucket, ticker
        WITH NO DATA;
    """)

    # Add refresh policy for daily aggregates
    op.execute("""
        SELECT add_continuous_aggregate_policy('ticker_summary_daily',
            start_offset => INTERVAL '2 days',
            end_offset => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day',
            if_not_exists => TRUE);
    """)

    # Create continuous aggregate for event type trends
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS event_type_trends_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', event_time) AS bucket,
            event_type,
            source,
            COUNT(*) AS event_count,
            AVG(alpha_score) AS avg_alpha,
            AVG(sentiment_score) AS avg_sentiment
        FROM events
        WHERE event_type IS NOT NULL
        GROUP BY bucket, event_type, source
        WITH NO DATA;
    """)

    # Add refresh policy for event type trends
    op.execute("""
        SELECT add_continuous_aggregate_policy('event_type_trends_hourly',
            start_offset => INTERVAL '2 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => TRUE);
    """)

    # Create retention policy to automatically delete old data (keep 90 days)
    op.execute("""
        SELECT add_retention_policy('events',
            INTERVAL '90 days',
            if_not_exists => TRUE);
    """)

    # Create compression policy for older chunks (compress after 7 days)
    op.execute("""
        ALTER TABLE events SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'ticker',
            timescaledb.compress_orderby = 'event_time DESC'
        );
    """)

    op.execute("""
        SELECT add_compression_policy('events',
            INTERVAL '7 days',
            if_not_exists => TRUE);
    """)


def downgrade() -> None:
    # Remove policies
    op.execute("SELECT remove_compression_policy('events', if_exists => TRUE);")
    op.execute("SELECT remove_retention_policy('events', if_exists => TRUE);")

    # Remove continuous aggregate policies
    op.execute(
        "SELECT remove_continuous_aggregate_policy('event_type_trends_hourly', if_exists => TRUE);"
    )
    op.execute(
        "SELECT remove_continuous_aggregate_policy('ticker_summary_daily', if_exists => TRUE);"
    )
    op.execute(
        "SELECT remove_continuous_aggregate_policy('ticker_sentiment_hourly', if_exists => TRUE);"
    )

    # Drop continuous aggregates
    op.execute("DROP MATERIALIZED VIEW IF EXISTS event_type_trends_hourly CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ticker_summary_daily CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ticker_sentiment_hourly CASCADE;")
