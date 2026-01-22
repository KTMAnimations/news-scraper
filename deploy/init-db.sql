-- Initialize TimescaleDB and create schema for news-scraper

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Events hypertable (main time-series data)
CREATE TABLE IF NOT EXISTS events (
    id UUID DEFAULT uuid_generate_v4(),
    ticker VARCHAR(10) NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    ingest_time TIMESTAMPTZ DEFAULT NOW(),

    -- Classification
    event_type VARCHAR(50) NOT NULL,
    event_category VARCHAR(50),

    -- Content
    headline TEXT NOT NULL,
    summary TEXT,
    content TEXT,
    source_url TEXT,
    source_name VARCHAR(100),

    -- Sentiment & Scoring
    sentiment_score FLOAT,
    sentiment_label VARCHAR(20),
    sentiment_confidence FLOAT,
    alpha_score FLOAT,
    direction VARCHAR(10),
    urgency VARCHAR(20),

    -- Entities
    extracted_tickers TEXT[],
    extracted_companies TEXT[],
    extracted_people TEXT[],
    extracted_amounts JSONB,

    -- Metadata
    metadata JSONB,

    -- Primary key includes time for hypertable partitioning
    PRIMARY KEY (id, event_time)
);

-- Convert to hypertable (partitioned by event_time)
SELECT create_hypertable('events', 'event_time', if_not_exists => TRUE);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_events_ticker ON events (ticker, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON events (event_type, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_events_alpha ON events (alpha_score DESC) WHERE alpha_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_source ON events (source_name, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_events_sentiment ON events (sentiment_label, event_time DESC);

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,

    -- Subscription
    subscription_tier VARCHAR(50) DEFAULT 'starter',
    subscription_status VARCHAR(50) DEFAULT 'active',
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_stripe ON users (stripe_customer_id);

-- Watchlist table
CREATE TABLE IF NOT EXISTS watchlist_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT,

    UNIQUE(user_id, ticker)
);

CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist_items (user_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_ticker ON watchlist_items (ticker);

-- Alerts table
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,

    -- Filters
    ticker VARCHAR(10),
    event_types TEXT[],
    min_alpha_score FLOAT,
    urgency_levels TEXT[],
    direction VARCHAR(10),

    -- Delivery
    delivery_method VARCHAR(50) DEFAULT 'push',
    is_active BOOLEAN DEFAULT TRUE,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_triggered_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts (user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts (is_active) WHERE is_active = TRUE;

-- SEC Filings tracking (to prevent duplicates)
CREATE TABLE IF NOT EXISTS sec_filings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    accession_number VARCHAR(50) UNIQUE NOT NULL,
    cik VARCHAR(20) NOT NULL,
    ticker VARCHAR(10),
    form_type VARCHAR(20) NOT NULL,
    filed_at TIMESTAMPTZ NOT NULL,
    processed_at TIMESTAMPTZ DEFAULT NOW(),
    event_id UUID,

    -- Raw data
    raw_url TEXT,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_sec_cik ON sec_filings (cik);
CREATE INDEX IF NOT EXISTS idx_sec_ticker ON sec_filings (ticker);
CREATE INDEX IF NOT EXISTS idx_sec_form ON sec_filings (form_type);
CREATE INDEX IF NOT EXISTS idx_sec_filed ON sec_filings (filed_at DESC);

-- Continuous aggregate for hourly sentiment
CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_sentiment
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', event_time) AS hour,
    ticker,
    AVG(sentiment_score) AS avg_sentiment,
    COUNT(*) AS event_count,
    MAX(alpha_score) AS max_alpha,
    MIN(alpha_score) AS min_alpha
FROM events
GROUP BY hour, ticker
WITH NO DATA;

-- Refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('hourly_sentiment',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Retention policy (keep 90 days of detailed data)
SELECT add_retention_policy('events', INTERVAL '90 days', if_not_exists => TRUE);

-- Create compression policy (compress data older than 7 days)
ALTER TABLE events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker'
);

SELECT add_compression_policy('events', INTERVAL '7 days', if_not_exists => TRUE);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for users table
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust as needed)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO newsuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO newsuser;
