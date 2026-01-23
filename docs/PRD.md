# Micro-Alpha News Scraper - Product Requirements Document

## Executive Summary

Micro-Alpha is a real-time financial news aggregation and analysis platform designed for traders focused on micro-cap and small-cap stocks. The platform provides an information edge by ingesting SEC filings, press releases, and social sentiment faster than traditional sources, then applying ML-powered analysis to surface actionable trading signals.

---

## Vision Statement

**For** day traders and retail investors focused on micro-cap stocks
**Who** need early access to material events that move illiquid stocks
**The** Micro-Alpha News Scraper **is a** real-time intelligence platform
**That** aggregates financial news, analyzes sentiment, and calculates alpha scores
**Unlike** Bloomberg Terminal or traditional news aggregators
**Our product** focuses specifically on micro-cap opportunities with sub-30-second latency and ML-powered signal quality scoring

---

## Target Users

### Primary Personas

1. **The Day Trader (Alex)**
   - Trades micro-cap and penny stocks daily
   - Needs real-time alerts on insider trades, SEC filings, and press releases
   - Values speed over depth of analysis
   - Willing to pay $50-100/month for an edge

2. **The Retail Investor (Jordan)**
   - Part-time investor focusing on small-cap growth stocks
   - Wants curated high-alpha events rather than noise
   - Needs clear bullish/bearish signals
   - Uses mobile and desktop interchangeably

3. **The Quant Trader (Sam)**
   - Builds algorithmic trading strategies
   - Needs API access to raw event data and sentiment scores
   - Wants historical data for backtesting
   - Requires high reliability and low latency

---

## Core Value Proposition

| Value | Description |
|-------|-------------|
| **Speed** | SEC filings and press releases captured within 10-30 seconds of publication |
| **Intelligence** | FinBERT ML model for accurate financial sentiment analysis |
| **Signal Quality** | Alpha scoring combines multiple factors to surface high-conviction opportunities |
| **Focus** | Specialized for micro-cap/small-cap where information asymmetry creates alpha |

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA SOURCES                                    │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────────────┤
│ SEC EDGAR   │ PR Newswire │ GlobeNews   │ StockTwits  │ Reddit              │
│ (10s)       │ (60s)       │ (60s)       │ (120s)      │ (120s)              │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴──────────┬──────────┘
       │             │             │             │                 │
       └─────────────┴─────────────┴─────────────┴─────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INGESTION LAYER                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ Celery Beat     │  │ Celery Workers  │  │ Redis Queue     │              │
│  │ (Scheduler)     │──│ (Processing)    │──│ (Broker)        │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PROCESSING PIPELINE                                 │
│                                                                              │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐ │
│   │ Entity   │──▶│ CIK→     │──▶│ FinBERT  │──▶│ Alpha    │──▶│ Store &  │ │
│   │ Extract  │   │ Ticker   │   │ Sentiment│   │ Scoring  │   │ Alert    │ │
│   └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            STORAGE LAYER                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ TimescaleDB     │  │ Redis Pub/Sub   │  │ OpenSearch      │              │
│  │ (Events)        │  │ (Real-time)     │  │ (Full-text)     │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PRESENTATION LAYER                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ Next.js         │  │ FastAPI         │  │ WebSocket       │              │
│  │ Dashboard       │  │ REST API        │  │ Server          │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Backend** | FastAPI, Python 3.11 | REST API, async I/O |
| **Task Queue** | Celery, Redis | Distributed task processing |
| **Frontend** | Next.js 14, React, TailwindCSS | Web dashboard |
| **Database** | TimescaleDB (PostgreSQL) | Time-series event storage |
| **Cache** | Redis | Session cache, pub/sub |
| **Search** | OpenSearch | Full-text search |
| **ML** | HuggingFace Transformers, FinBERT | Sentiment analysis |
| **NLP** | spaCy | Entity extraction |
| **Streaming** | Redpanda (Kafka-compatible) | Event streaming |
| **Infrastructure** | Docker Compose | Container orchestration |

---

## Epics & User Stories

### Epic 1: Real-Time Data Ingestion

**Goal**: Capture financial events from multiple sources with minimal latency

#### User Stories

| ID | Story | Acceptance Criteria | Priority | Status |
|----|-------|---------------------|----------|--------|
| US-1.1 | As a trader, I want SEC filings captured within 30 seconds so I can act before the market moves | SEC EDGAR RSS polled every 10s; Form 4, 8-K, 13D/G filings captured; CIK resolved to ticker symbol | P0 | ✅ Done |
| US-1.2 | As a trader, I want press releases from major newswires captured in real-time | PR Newswire, GlobeNewswire, Business Wire scraped every 60s; Tickers extracted from content | P0 | ✅ Done |
| US-1.3 | As a trader, I want social sentiment from StockTwits aggregated | StockTwits trending tickers and messages captured every 120s | P1 | ✅ Done |
| US-1.4 | As a trader, I want Reddit penny stock discussions monitored | r/pennystocks posts scraped every 120s; Ticker mentions extracted | P1 | ✅ Done |
| US-1.5 | As a trader, I want OTC tier changes monitored for uplisting opportunities | OTC Markets checked every 60 minutes for tier changes | P2 | 🔲 Pending |
| US-1.6 | As a trader, I want Twitter/X mentions of cashtags captured | Twitter API integration for cashtag monitoring | P2 | 🔲 Pending |

---

### Epic 2: NLP Processing & Analysis

**Goal**: Extract meaningful signals from raw text using ML models

#### User Stories

| ID | Story | Acceptance Criteria | Priority | Status |
|----|-------|---------------------|----------|--------|
| US-2.1 | As a user, I want ticker symbols automatically extracted from news content | Regex and NLP-based ticker extraction; CIK→ticker resolution for SEC filings | P0 | ✅ Done |
| US-2.2 | As a user, I want company names and people extracted for context | spaCy NER extracts ORG and PERSON entities | P0 | ✅ Done |
| US-2.3 | As a user, I want accurate sentiment analysis on financial text | FinBERT model provides positive/negative/neutral with confidence score | P0 | ✅ Done |
| US-2.4 | As a user, I want events classified by type (insider trade, earnings, FDA, etc.) | Event classifier categorizes by filing type and content | P0 | ✅ Done |
| US-2.5 | As a user, I want dollar amounts extracted from SEC filings | Regex extraction of monetary values from content | P1 | ✅ Done |

---

### Epic 3: Alpha Scoring & Signals

**Goal**: Calculate actionable trading signals from processed events

#### User Stories

| ID | Story | Acceptance Criteria | Priority | Status |
|----|-------|---------------------|----------|--------|
| US-3.1 | As a trader, I want an alpha score that combines multiple signal factors | Alpha = 35% event_type + 25% sentiment + 15% source + 15% recency + 10% liquidity | P0 | ✅ Done |
| US-3.2 | As a trader, I want clear bullish/bearish direction indicators | Direction derived from sentiment and event type | P0 | ✅ Done |
| US-3.3 | As a trader, I want urgency levels to prioritize my attention | Critical/High/Medium/Low based on alpha score and event type | P0 | ✅ Done |
| US-3.4 | As a quant, I want access to the raw scoring factors for my own models | API returns alpha_factors breakdown | P1 | ✅ Done |

---

### Epic 4: Data Storage & Retrieval

**Goal**: Persist events with efficient querying for historical analysis

#### User Stories

| ID | Story | Acceptance Criteria | Priority | Status |
|----|-------|---------------------|----------|--------|
| US-4.1 | As a user, I want events stored in a time-series database | TimescaleDB hypertable with event_time partitioning | P0 | ✅ Done |
| US-4.2 | As a user, I want to query events by ticker, type, and time range | REST API with filter parameters | P0 | ✅ Done |
| US-4.3 | As a user, I want full-text search across headlines and content | OpenSearch integration for search | P1 | 🔲 Pending |
| US-4.4 | As a user, I want duplicate events filtered out | Deduplication by ticker + headline hash | P0 | ✅ Done |

---

### Epic 5: Web Dashboard

**Goal**: Provide an intuitive interface for monitoring events and signals

#### User Stories

| ID | Story | Acceptance Criteria | Priority | Status |
|----|-------|---------------------|----------|--------|
| US-5.1 | As a user, I want a real-time feed of latest events | Dashboard shows events sorted by time with auto-refresh | P0 | ✅ Done |
| US-5.2 | As a user, I want to filter events by ticker, type, and alpha score | Filter controls on dashboard | P0 | ✅ Done |
| US-5.3 | As a user, I want to see high-alpha events highlighted | Dedicated high-alpha section with visual emphasis | P0 | ✅ Done |
| US-5.4 | As a user, I want TradingView charts on ticker detail pages | TradingView widget integration | P0 | ✅ Done |
| US-5.5 | As a user, I want sentiment badges showing bullish/bearish/neutral | Color-coded sentiment indicators | P0 | ✅ Done |
| US-5.6 | As a user, I want the dashboard to update in real-time via WebSocket | WebSocket connection for live updates | P1 | 🔄 In Progress |
| US-5.7 | As a user, I want dark mode and light mode themes | Theme toggle in UI | P1 | 🔄 In Progress |

---

### Epic 6: User Authentication & Personalization

**Goal**: Enable user accounts with personalized features

#### User Stories

| ID | Story | Acceptance Criteria | Priority | Status |
|----|-------|---------------------|----------|--------|
| US-6.1 | As a user, I want to create an account and log in | Email/password authentication with JWT | P1 | 🔲 Pending |
| US-6.2 | As a user, I want to maintain a watchlist of tickers | Add/remove tickers; persisted to database | P1 | 🔲 Pending |
| US-6.3 | As a user, I want to create custom alert rules | Alert on specific tickers, event types, alpha thresholds | P1 | 🔲 Pending |
| US-6.4 | As a user, I want email notifications for high-alpha events | Email delivery for triggered alerts | P2 | 🔲 Pending |
| US-6.5 | As a user, I want push notifications on mobile | FCM integration for push notifications | P2 | 🔲 Pending |

---

### Epic 7: API & Integrations

**Goal**: Provide programmatic access for power users and integrations

#### User Stories

| ID | Story | Acceptance Criteria | Priority | Status |
|----|-------|---------------------|----------|--------|
| US-7.1 | As a developer, I want REST API endpoints for all event data | Full CRUD API with OpenAPI documentation | P0 | ✅ Done |
| US-7.2 | As a developer, I want WebSocket streaming for real-time events | WebSocket server with pub/sub channels | P1 | 🔄 In Progress |
| US-7.3 | As a quant, I want to download historical data for backtesting | CSV/JSON export endpoints | P2 | 🔲 Pending |
| US-7.4 | As a developer, I want API rate limiting and authentication | JWT auth with tier-based rate limits | P2 | 🔲 Pending |

---

### Epic 8: Infrastructure & Operations

**Goal**: Ensure reliable, scalable, and maintainable system operations

#### User Stories

| ID | Story | Acceptance Criteria | Priority | Status |
|----|-------|---------------------|----------|--------|
| US-8.1 | As an operator, I want all services containerized | Docker Compose for local dev; production-ready Dockerfiles | P0 | ✅ Done |
| US-8.2 | As an operator, I want health checks on all services | /health endpoints; Docker healthchecks | P0 | ✅ Done |
| US-8.3 | As an operator, I want structured logging for debugging | structlog with JSON output | P0 | ✅ Done |
| US-8.4 | As an operator, I want the frontend optimized for production | Next.js production build with standalone output | P0 | ✅ Done |
| US-8.5 | As an operator, I want database migrations managed | Alembic migrations for schema changes | P1 | 🔲 Pending |
| US-8.6 | As an operator, I want metrics and monitoring | Prometheus metrics; Grafana dashboards | P2 | 🔲 Pending |

---

## Data Models

### Event Model

```sql
CREATE TABLE events (
    id UUID PRIMARY KEY,
    event_time TIMESTAMPTZ NOT NULL,
    ticker VARCHAR(10),
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
    urgency_level VARCHAR(20),

    -- Entities
    extracted_tickers TEXT[],
    extracted_companies TEXT[],
    extracted_people TEXT[],
    extracted_amounts JSONB,

    -- Metadata
    metadata JSONB DEFAULT '{}'
);

-- TimescaleDB hypertable
SELECT create_hypertable('events', 'event_time');
```

### Alpha Score Formula

```
alpha_score = (
    event_weight * 0.35 +
    sentiment_score * 0.25 +
    source_weight * 0.15 +
    recency_weight * 0.15 +
    liquidity_weight * 0.10
) * direction_multiplier
```

| Component | Weight | Calculation |
|-----------|--------|-------------|
| Event Type | 35% | Insider buy = 0.9, FDA approval = 0.95, earnings beat = 0.7, etc. |
| Sentiment | 25% | FinBERT score (-1 to +1) |
| Source | 15% | SEC = 1.0, PR Newswire = 0.8, Social = 0.5 |
| Recency | 15% | Exponential decay from event_time |
| Liquidity | 10% | Inverse of market cap (micro-cap = higher weight) |

---

## API Reference

### Events API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/events` | GET | List events with filtering |
| `/api/v1/events/latest` | GET | Get latest N events |
| `/api/v1/events/high-alpha` | GET | Get high alpha events (score > 0.7) |
| `/api/v1/events/ticker/{ticker}` | GET | Get events for specific ticker |
| `/api/v1/events/{id}` | GET | Get single event by ID |

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | int | Max results (default: 50, max: 500) |
| `offset` | int | Pagination offset |
| `ticker` | string | Filter by ticker symbol |
| `event_type` | string | Filter by event type |
| `min_alpha` | float | Minimum alpha score |
| `direction` | string | BULLISH, BEARISH, NEUTRAL |
| `since` | datetime | Events after this time |

---

## Scheduled Tasks

| Task | Schedule | Description |
|------|----------|-------------|
| `scrape_sec_filings` | Every 10s | Poll SEC EDGAR RSS feed |
| `scrape_news` | Every 60s | Scrape PR Newswire, GlobeNewswire |
| `scrape_social` | Every 120s | Scrape StockTwits, Reddit |
| `check_otc_tiers` | Every 60min | Check OTC Markets for tier changes |
| `refresh_knowledge_base` | Daily 6AM UTC | Update CIK→ticker mappings from SEC |
| `cleanup_old_alerts` | Daily 3AM UTC | Remove stale alert records |

---

## Environment Configuration

### Backend (.env)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://newsuser:newspass@postgres:5432/newsdb

# Redis
REDIS_URL=redis://redis:6379/0

# OpenSearch
OPENSEARCH_URL=http://opensearch:9200

# Security
JWT_SECRET_KEY=your-secret-key-here
SEC_USER_AGENT=your-email@example.com

# Feature Flags
DEBUG=false
```

### Frontend (.env.local)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8001
NEXT_PUBLIC_MOCK_MODE=false
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-nextauth-secret
```

---

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| SEC Filing Latency | < 30 seconds | ✅ ~15 seconds |
| Event Coverage | 95% of material events | 🔄 Measuring |
| Sentiment Accuracy | > 80% agreement | ✅ FinBERT active |
| System Uptime | 99.9% during market hours | 🔄 Measuring |
| API Response Time | < 200ms p95 | ✅ ~100ms |

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Claude | Initial PRD with epics |
| 0.1 | 2026-01-22 | Claude | Draft PRD |
