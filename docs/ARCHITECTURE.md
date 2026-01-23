# Micro-Alpha News Scraper - System Architecture

This document describes the system architecture of the Micro-Alpha News Scraper platform, including component relationships, data flows, and deployment topology.

## Overview

Micro-Alpha is a real-time financial news aggregation and sentiment analysis platform. The system ingests data from multiple sources, processes it through an NLP pipeline, calculates trading signals, and delivers results via REST API and WebSocket streaming.

## High-Level Architecture

```mermaid
flowchart TB
    subgraph External["External Data Sources"]
        SEC[SEC EDGAR RSS]
        PRN[PR Newswire]
        GNW[GlobeNewswire]
        BWR[Business Wire]
        STW[StockTwits]
        RDT[Reddit]
    end

    subgraph Ingestion["Ingestion Layer"]
        CB[Celery Beat<br/>Scheduler]
        CW[Celery Workers<br/>x2 replicas]
        RQ[(Redis<br/>Task Queue)]
    end

    subgraph Processing["Processing Pipeline"]
        EE[Entity Extractor<br/>spaCy NER]
        CIK[CIK-to-Ticker<br/>Resolution]
        FB[FinBERT Service<br/>Sentiment Analysis]
        AS[Alpha Scorer<br/>Signal Calculation]
        EC[Event Classifier<br/>Type Detection]
    end

    subgraph Storage["Storage Layer"]
        TS[(TimescaleDB<br/>Events + Users)]
        OS[(OpenSearch<br/>Full-Text Index)]
        RC[(Redis Cache<br/>Pub/Sub)]
    end

    subgraph API["API Layer"]
        FA[FastAPI<br/>REST API]
        WS[WebSocket Server<br/>Real-time Streaming]
    end

    subgraph Frontend["Presentation Layer"]
        NX[Next.js Dashboard]
        TV[TradingView<br/>Charts]
    end

    subgraph Notifications["Notification Services"]
        EMAIL[Email Service<br/>SMTP]
        PUSH[Push Notifications<br/>FCM]
    end

    %% Data Flow
    SEC --> CB
    PRN --> CB
    GNW --> CB
    BWR --> CB
    STW --> CB
    RDT --> CB

    CB --> RQ
    RQ --> CW

    CW --> EE
    EE --> CIK
    CIK --> FB
    FB --> EC
    EC --> AS

    AS --> TS
    AS --> OS
    AS --> RC

    TS --> FA
    OS --> FA
    RC --> WS

    FA --> NX
    WS --> NX
    TV --> NX

    AS --> EMAIL
    AS --> PUSH
```

## Component Details

### 1. Data Sources

| Source | Polling Interval | Data Type | Priority |
|--------|------------------|-----------|----------|
| SEC EDGAR | 10 seconds | Form 4, 8-K, 13D/G | Critical |
| PR Newswire | 60 seconds | Press releases | High |
| GlobeNewswire | 60 seconds | Press releases | High |
| Business Wire | 60 seconds | Press releases | High |
| StockTwits | 120 seconds | Social sentiment | Medium |
| Reddit | 120 seconds | Social mentions | Medium |

### 2. Ingestion Layer

#### Celery Beat (Scheduler)
- **Purpose**: Orchestrates periodic scraping tasks
- **Configuration**: Redis as broker (DB 1)
- **Tasks**: Defined in `backend/workers/tasks/`

#### Celery Workers
- **Replicas**: 2 workers for horizontal scaling
- **Queues**: `critical`, `high`, `default`, `low`
- **Concurrency**: 4 processes per worker

```mermaid
flowchart LR
    subgraph Queues
        Q1[critical<br/>SEC filings]
        Q2[high<br/>Press releases]
        Q3[default<br/>Processing]
        Q4[low<br/>Cleanup tasks]
    end

    subgraph Workers
        W1[Worker 1]
        W2[Worker 2]
    end

    Q1 --> W1 & W2
    Q2 --> W1 & W2
    Q3 --> W1 & W2
    Q4 --> W1 & W2
```

### 3. Processing Pipeline

The NLP pipeline processes each event through multiple stages:

```mermaid
flowchart LR
    RAW[Raw Event] --> EXT[Entity<br/>Extraction]
    EXT --> CIK[CIK-to-Ticker<br/>Resolution]
    CIK --> SENT[Sentiment<br/>Analysis]
    SENT --> CLASS[Event<br/>Classification]
    CLASS --> ALPHA[Alpha<br/>Scoring]
    ALPHA --> STORE[Storage]

    style SENT fill:#f9f,stroke:#333
    style ALPHA fill:#ff9,stroke:#333
```

#### Entity Extraction
- **Technology**: spaCy + regex patterns
- **Extracts**: Tickers, company names, people, dollar amounts
- **Validation**: Against SEC ticker knowledge base

#### Sentiment Analysis
- **Primary**: FinBERT (HuggingFace Transformers)
- **Fallback**: Keyword-based sentiment (SimpleSentimentService)
- **Output**: Score (-1 to +1), Label, Confidence

#### Alpha Scoring
Multi-factor signal calculation:

| Factor | Weight | Description |
|--------|--------|-------------|
| Event Type | 35% | Insider buy = 0.9, FDA approval = 0.95 |
| Sentiment | 25% | FinBERT score |
| Source | 15% | SEC = 1.0, PR Newswire = 0.8, Social = 0.5 |
| Recency | 15% | Exponential decay from event_time |
| Liquidity | 10% | Inverse market cap weighting |

### 4. Storage Layer

#### TimescaleDB (PostgreSQL)
- **Purpose**: Primary event storage with time-series optimization
- **Features**: Hypertable partitioning, continuous aggregates
- **Tables**: `events`, `users`, `watchlists`, `alerts`

```mermaid
erDiagram
    USERS ||--o{ WATCHLISTS : has
    USERS ||--o{ ALERTS : creates
    EVENTS }o--|| USERS : viewed_by

    EVENTS {
        uuid id PK
        timestamptz event_time
        varchar ticker
        varchar event_type
        text headline
        float alpha_score
        varchar direction
    }

    USERS {
        uuid id PK
        varchar email UK
        varchar hashed_password
        varchar subscription_tier
    }

    WATCHLISTS {
        uuid id PK
        uuid user_id FK
        varchar ticker
        boolean alert_enabled
    }

    ALERTS {
        uuid id PK
        uuid user_id FK
        varchar name
        float min_alpha_score
        varchar delivery_method
    }
```

#### OpenSearch
- **Purpose**: Full-text search and aggregations
- **Index**: `events` with custom analyzers
- **Features**: Fuzzy matching, highlighting, autocomplete

#### Redis
- **DB 0**: Application cache
- **DB 1**: Celery broker
- **DB 2**: Celery result backend
- **Pub/Sub Channels**:
  - `events:all` - All events
  - `events:high_alpha` - High alpha events
  - `events:ticker:{SYMBOL}` - Per-ticker channels

### 5. API Layer

#### FastAPI REST API
- **Port**: 8000
- **Authentication**: JWT Bearer tokens
- **Rate Limiting**: Tier-based (30-3000 req/min)
- **Documentation**: OpenAPI/Swagger at `/docs`

```mermaid
flowchart TB
    subgraph Endpoints
        AUTH[/api/v1/auth]
        EVENTS[/api/v1/events]
        SEARCH[/api/v1/search]
        TICKERS[/api/v1/tickers]
        WATCHLIST[/api/v1/watchlist]
        ALERTS[/api/v1/alerts]
        BILLING[/api/v1/billing]
        STATS[/api/v1/stats]
    end

    subgraph Middleware
        CORS[CORS]
        RATE[Rate Limiter]
        JWT[JWT Auth]
    end

    CLIENT[Client] --> CORS
    CORS --> RATE
    RATE --> JWT
    JWT --> Endpoints
```

#### WebSocket Server
- **Port**: 8001
- **Endpoints**:
  - `/ws/events` - All events stream
  - `/ws/events/watchlist` - User watchlist events
  - `/ws/events/ticker/{ticker}` - Single ticker stream
  - `/ws/events/high-alpha` - High alpha events only

### 6. Frontend

#### Next.js Dashboard
- **Framework**: Next.js 14 with App Router
- **Styling**: TailwindCSS
- **State**: React Query for server state
- **Charts**: TradingView widget integration

```mermaid
flowchart TB
    subgraph Pages
        DASH[Dashboard]
        TICK[Ticker Detail]
        WATCH[Watchlist]
        ALERT[Alerts]
        SET[Settings]
    end

    subgraph Components
        EVT[EventCard]
        CHART[TradingView]
        BADGE[SentimentBadge]
        FILTER[FilterPanel]
    end

    DASH --> EVT
    TICK --> CHART
    TICK --> EVT
    EVT --> BADGE
    DASH --> FILTER
```

## Data Flow

### Event Ingestion Flow

```mermaid
sequenceDiagram
    participant S as Data Source
    participant B as Celery Beat
    participant W as Worker
    participant P as Pipeline
    participant DB as TimescaleDB
    participant OS as OpenSearch
    participant R as Redis
    participant WS as WebSocket
    participant C as Client

    B->>W: Schedule scrape task
    W->>S: Fetch new data
    S-->>W: Raw event data
    W->>P: Process event
    P->>P: Extract entities
    P->>P: Analyze sentiment
    P->>P: Calculate alpha
    P->>DB: Store event
    P->>OS: Index for search
    P->>R: Publish to channels
    R->>WS: Broadcast event
    WS->>C: Push to clients
```

### User Authentication Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API
    participant DB as Database

    C->>A: POST /auth/login
    A->>DB: Validate credentials
    DB-->>A: User record
    A->>A: Generate JWT tokens
    A-->>C: Access + Refresh tokens

    C->>A: GET /events (with token)
    A->>A: Validate JWT
    A->>DB: Fetch events
    DB-->>A: Event data
    A-->>C: Events response
```

## Deployment Topology

### Docker Compose Services

```mermaid
flowchart TB
    subgraph Network["news-scraper-network"]
        subgraph App["Application Services"]
            API[api:8000]
            WS[websocket-server:8001]
            FE[frontend:3000]
            CW1[celery-worker-1]
            CW2[celery-worker-2]
            CB[celery-beat]
            NLP[nlp-service]
        end

        subgraph Data["Data Services"]
            PG[(postgres:5432)]
            RD[(redis:6379)]
            OS[(opensearch:9200)]
            RP[(redpanda:19092)]
        end

        subgraph Debug["Debug Services - Optional"]
            OSD[opensearch-dashboards:5601]
            RPC[redpanda-console:8080]
        end
    end

    API --> PG & RD & OS
    WS --> RD
    CW1 & CW2 --> PG & RD & OS
    CB --> RD
    NLP --> RD
    FE --> API & WS
```

### Resource Requirements

| Service | CPU | Memory | Storage |
|---------|-----|--------|---------|
| API | 0.5 | 512MB | - |
| WebSocket | 0.25 | 256MB | - |
| Frontend | 0.25 | 256MB | - |
| Celery Worker (x2) | 1.0 | 1GB | - |
| Celery Beat | 0.1 | 128MB | - |
| NLP Service | 1.0 | 2GB | 2GB (model cache) |
| PostgreSQL | 1.0 | 1GB | 20GB+ |
| Redis | 0.25 | 512MB | 1GB |
| OpenSearch | 1.0 | 1GB | 10GB+ |
| Redpanda | 0.5 | 1GB | 5GB+ |

## Security Architecture

### Authentication & Authorization

```mermaid
flowchart TB
    subgraph Auth["Authentication"]
        JWT[JWT Tokens]
        HASH[bcrypt Hashing]
        REFRESH[Refresh Token Rotation]
    end

    subgraph AuthZ["Authorization"]
        TIER[Subscription Tiers]
        RATE[Rate Limiting]
        SCOPE[Route Scopes]
    end

    subgraph Network["Network Security"]
        CORS[CORS Policy]
        TLS[TLS/HTTPS]
        WAF[WAF Rules]
    end
```

### Subscription Tiers

| Tier | Rate Limit | WebSocket | API History | Alerts |
|------|------------|-----------|-------------|--------|
| Starter | 60/min | Yes | 7 days | 5 |
| Professional | 300/min | Yes | 30 days | 25 |
| Team | 600/min | Yes | 90 days | 100 |
| Enterprise | 3000/min | Yes | Unlimited | Unlimited |

## Scalability Considerations

### Horizontal Scaling Points

1. **Celery Workers**: Add more replicas for increased processing throughput
2. **API Servers**: Load balance across multiple FastAPI instances
3. **WebSocket Servers**: Shard by user/ticker with sticky sessions
4. **Read Replicas**: Add PostgreSQL read replicas for query scaling

### Vertical Scaling Points

1. **NLP Service**: GPU acceleration for FinBERT inference
2. **OpenSearch**: Increase memory for larger indices
3. **Redis**: Cluster mode for high availability

## Monitoring & Observability

### Metrics Collection

```mermaid
flowchart LR
    subgraph Services
        S1[API]
        S2[Workers]
        S3[WebSocket]
    end

    subgraph Monitoring
        PROM[Prometheus]
        GRAF[Grafana]
        ALERT[Alertmanager]
    end

    subgraph Logging
        LOG[structlog]
        ELK[ELK Stack]
    end

    S1 & S2 & S3 --> PROM
    PROM --> GRAF
    PROM --> ALERT
    S1 & S2 & S3 --> LOG
    LOG --> ELK
```

### Key Metrics

- **Latency**: Event ingestion time, API response time
- **Throughput**: Events/second, requests/second
- **Error Rates**: 4xx/5xx responses, task failures
- **Queue Depth**: Celery queue sizes
- **Resource Usage**: CPU, memory, disk I/O

## Future Architecture Considerations

1. **Kubernetes Migration**: Move from Docker Compose to K8s for production
2. **Event Sourcing**: Implement CQRS pattern with Redpanda
3. **Multi-Region**: Geographic distribution for lower latency
4. **ML Pipeline**: MLflow for model versioning and A/B testing
5. **GraphQL**: Alternative API for flexible queries

---

*Last Updated: January 23, 2026*
