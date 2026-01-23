-- Initialize TimescaleDB for news-scraper
-- This script runs on first container startup

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create Events table
CREATE TABLE IF NOT EXISTS events (
    id UUID DEFAULT uuid_generate_v4(),
    ticker VARCHAR(10),
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ingest_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Classification
    event_type VARCHAR(50),
    event_category VARCHAR(50),
    
    -- Content
    headline TEXT NOT NULL,
    summary TEXT,
    content TEXT,
    source_url TEXT,
    source_name VARCHAR(100),
    
    -- Sentiment and Scoring
    sentiment_score FLOAT,
    sentiment_label VARCHAR(20),
    sentiment_confidence FLOAT,
    alpha_score FLOAT,
    direction VARCHAR(20),
    urgency_level VARCHAR(20),
    
    -- Extracted entities (stored as JSONB arrays)
    extracted_tickers JSONB DEFAULT '[]'::jsonb,
    extracted_companies JSONB DEFAULT '[]'::jsonb,
    extracted_people JSONB DEFAULT '[]'::jsonb,
    extracted_amounts JSONB DEFAULT '[]'::jsonb,
    
    -- Additional metadata
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Composite primary key required for TimescaleDB hypertable
    PRIMARY KEY (id, event_time)
);

-- Convert events to a TimescaleDB hypertable
SELECT create_hypertable('events', 'event_time', if_not_exists => TRUE);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_events_ticker ON events (ticker);
CREATE INDEX IF NOT EXISTS idx_events_event_time ON events (event_time DESC);
CREATE INDEX IF NOT EXISTS idx_events_alpha_score ON events (alpha_score DESC) WHERE alpha_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_urgency ON events (urgency_level);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_direction ON events (direction);
CREATE INDEX IF NOT EXISTS idx_events_ticker_time ON events (ticker, event_time DESC);

-- Create Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    
    -- Subscription
    subscription_tier VARCHAR(50) DEFAULT 'starter',
    subscription_status VARCHAR(50) DEFAULT 'active',
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    
    -- FCM for push notifications
    fcm_tokens JSONB DEFAULT '[]'::jsonb,
    
    -- Flags
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_stripe_customer ON users (stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;

-- Create Watchlist table
CREATE TABLE IF NOT EXISTS watchlist (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    notes TEXT,
    alert_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(user_id, ticker)
);

CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist (user_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_ticker ON watchlist (ticker);

-- Create Alerts table
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    
    -- Filter criteria
    ticker VARCHAR(10),
    event_types JSONB DEFAULT '[]'::jsonb,
    min_alpha_score FLOAT,
    urgency_levels JSONB DEFAULT '[]'::jsonb,
    direction VARCHAR(20),
    
    -- Delivery
    delivery_method VARCHAR(20) DEFAULT 'email',
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_triggered_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts (user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts (is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_alerts_ticker ON alerts (ticker) WHERE ticker IS NOT NULL;

-- Create continuous aggregates for analytics
CREATE MATERIALIZED VIEW IF NOT EXISTS events_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', event_time) AS bucket,
    ticker,
    COUNT(*) AS event_count,
    AVG(alpha_score) AS avg_alpha,
    AVG(sentiment_score) AS avg_sentiment,
    COUNT(*) FILTER (WHERE direction = 'BULLISH') AS bullish_count,
    COUNT(*) FILTER (WHERE direction = 'BEARISH') AS bearish_count
FROM events
GROUP BY bucket, ticker
WITH NO DATA;

-- Add refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('events_hourly',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Create retention policy - keep raw events for 90 days
SELECT add_retention_policy('events', INTERVAL '90 days', if_not_exists => TRUE);

-- Create compression policy - compress data older than 7 days
ALTER TABLE events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker'
);

SELECT add_compression_policy('events', INTERVAL '7 days', if_not_exists => TRUE);

-- Grant permissions to the app user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO newsuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO newsuser;
GRANT USAGE ON SCHEMA public TO newsuser;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add trigger for users table
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMIT;
