# Micro-Alpha News Scraper - Product Requirements Document

## Overview

A real-time financial news aggregation and analysis platform focused on micro-cap and small-cap stocks. The system scrapes news from multiple sources, analyzes sentiment using ML models, calculates alpha scores, and delivers actionable trading signals.

## Target Users

- Day traders focused on micro-cap/small-cap stocks
- Retail investors seeking early information edge
- Quantitative traders looking for alpha signals

## Core Value Proposition

1. **Speed**: Real-time ingestion of SEC filings, press releases, and social sentiment
2. **Intelligence**: ML-powered sentiment analysis (FinBERT) and alpha scoring
3. **Signal Quality**: Focus on material events that move illiquid stocks

---

## System Architecture

### Data Sources (Ingestion Layer)

| Source | Frequency | Priority | Data Type |
|--------|-----------|----------|-----------|
| SEC EDGAR RSS | Every 10s | Critical | Form 4, 8-K, 13D/G filings |
| PR Newswire | Every 60s | High | Press releases |
| GlobeNewswire | Every 60s | High | Press releases |
| Business Wire | Every 60s | High | Press releases |
| StockTwits | Every 120s | Medium | Social sentiment |
| Reddit (pennystocks) | Every 120s | Medium | Social sentiment |
| OTC Markets | Every 60min | Medium | Tier changes |

### Processing Pipeline

```
Scrape → Extract Entities → Analyze Sentiment → Calculate Alpha → Store → Alert
```

1. **Entity Extraction**: Extract tickers, companies, people, dollar amounts
2. **Sentiment Analysis**: FinBERT model (ProsusAI/finbert) for financial sentiment
3. **Alpha Scoring**: Combine sentiment, event type, source reliability, recency, liquidity
4. **Storage**: TimescaleDB for time-series, OpenSearch for full-text search
5. **Alerts**: Real-time notifications via WebSocket, push notifications

### Tech Stack

- **Backend**: FastAPI, Celery, Python 3.11
- **Frontend**: Next.js 14, React, TailwindCSS
- **Databases**: TimescaleDB (PostgreSQL), Redis, OpenSearch
- **ML**: HuggingFace Transformers (FinBERT), spaCy
- **Message Queue**: Redis (Celery broker), Redpanda (Kafka-compatible)
- **Infrastructure**: Docker Compose

---

## Feature Requirements

### P0 - Must Have (MVP)

- [x] Real-time SEC EDGAR filing ingestion
- [x] Press release scraping (PR Newswire, etc.)
- [x] FinBERT sentiment analysis
- [x] Alpha score calculation
- [x] Event storage in TimescaleDB
- [x] REST API for events
- [x] Basic web dashboard
- [x] TradingView chart integration
- [ ] **CIK → Ticker resolution for SEC filings** ← Current blocker
- [ ] WebSocket real-time updates working end-to-end

### P1 - Should Have

- [ ] User authentication with real backend (currently mock mode)
- [ ] Watchlist with alerts
- [ ] Email/push notifications for high-alpha events
- [ ] Historical data backfill
- [ ] Advanced search with filters
- [ ] Ticker detail pages with full history

### P2 - Nice to Have

- [ ] Social sentiment aggregation (StockTwits, Reddit, Twitter)
- [ ] OTC tier change monitoring
- [ ] Custom alert rules
- [ ] Mobile app
- [ ] API rate limiting and subscription tiers

---

## Data Models

### Event

```
- id: UUID
- ticker: VARCHAR(10) - Stock symbol
- event_time: TIMESTAMPTZ - When event occurred
- ingest_time: TIMESTAMPTZ - When we captured it
- event_type: VARCHAR(50) - INSIDER_TRADE, EARNINGS_BEAT, FDA_APPROVAL, etc.
- event_category: VARCHAR(50) - SEC_FILING, NEWS, SOCIAL, etc.
- headline: TEXT
- summary: TEXT
- source_url: TEXT
- source_name: VARCHAR(100)
- sentiment_score: FLOAT (-1 to 1)
- sentiment_label: VARCHAR(20) - positive, negative, neutral
- alpha_score: FLOAT (-1 to 1)
- direction: VARCHAR(10) - BULLISH, BEARISH, NEUTRAL
- urgency_level: VARCHAR(20) - critical, high, medium, low
- extracted_tickers: TEXT[]
- extracted_companies: TEXT[]
```

### Alpha Score Components

| Component | Weight | Description |
|-----------|--------|-------------|
| Event Type | 35% | Material event classification |
| Sentiment | 25% | FinBERT sentiment score |
| Source | 15% | Source reliability (SEC > PR Newswire > Social) |
| Recency | 15% | Time decay function |
| Liquidity | 10% | Market cap/volume multiplier (illiquid = higher alpha) |

---

## Known Issues & Technical Debt

### Critical

1. **SEC CIK → Ticker Resolution**: SEC filings contain CIK numbers, not ticker symbols. Need to use knowledge base to resolve.
2. **Database Schema Drift**: Some columns missing (e.g., `fcm_tokens` was missing)

### High

1. **Mock Mode Confusion**: `NEXT_PUBLIC_MOCK_MODE` was affecting both auth AND data fetching. Now separated.
2. **Sentiment Analysis**: Was using keyword-based `SimpleSentimentService` instead of FinBERT. Fixed.

### Medium

1. **Production Build**: Frontend was running in dev mode. Fixed with production Dockerfile.
2. **Volume Mounts**: Docker volume mounts were overriding production builds. Fixed.

---

## API Endpoints

### Events
- `GET /api/v1/events` - List events with filtering
- `GET /api/v1/events/latest` - Get latest events
- `GET /api/v1/events/high-alpha` - Get high alpha events
- `GET /api/v1/events/ticker/{ticker}` - Get events for ticker
- `GET /api/v1/events/{id}` - Get single event

### Tickers
- `GET /api/v1/tickers` - List all tickers
- `GET /api/v1/tickers/{ticker}` - Get ticker info
- `GET /api/v1/tickers/{ticker}/sentiment` - Get ticker sentiment

### User (requires auth)
- `GET /api/v1/watchlist` - Get user watchlist
- `POST /api/v1/watchlist` - Add to watchlist
- `GET /api/v1/alerts` - Get user alerts

---

## Environment Variables

### Backend
```
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/newsdb
REDIS_URL=redis://redis:6379/0
OPENSEARCH_URL=http://opensearch:9200
JWT_SECRET_KEY=<secret>
SEC_USER_AGENT=<email for SEC requests>
```

### Frontend
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8001
NEXT_PUBLIC_MOCK_MODE=true  # Only affects auth, not data
NEXTAUTH_SECRET=<secret>
```

---

## Scheduled Tasks (Celery Beat)

| Task | Schedule | Queue |
|------|----------|-------|
| scrape_sec_filings | Every 10s | critical |
| scrape_news | Every 60s | default |
| scrape_social | Every 120s | default |
| check_otc_tiers | Every 60min | default |
| refresh_knowledge_base | Daily 6AM UTC | low |
| cleanup_old_alerts | Daily 3AM UTC | low |

---

## Success Metrics

1. **Latency**: SEC filing → dashboard < 30 seconds
2. **Coverage**: 95%+ of micro-cap material events captured
3. **Accuracy**: Sentiment classification > 80% agreement with manual labels
4. **Uptime**: 99.9% availability during market hours

---

## Next Steps (Immediate)

1. Fix SEC CIK → ticker resolution
2. Verify end-to-end pipeline stores new events
3. Test WebSocket real-time updates
4. Reprocess existing events with FinBERT if needed
