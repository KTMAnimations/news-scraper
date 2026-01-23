"""FastAPI application entry point.

This module initializes the FastAPI application with all routes, middleware,
and lifecycle handlers for the Micro-Alpha News Scraper platform.
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.storage.timescale import init_db

from .middleware import RateLimitMiddleware
from .routes import alerts, api_keys, auth, billing, events, notifications, search, stats, tickers, watchlist
from .websocket.streamer import EventStreamer, router as websocket_router

logger = structlog.get_logger(__name__)

# Global event streamer instance
event_streamer = EventStreamer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.

    Manages startup and shutdown procedures including database initialization
    and WebSocket event streaming.
    """
    # Startup
    logger.info("Starting application...")
    await init_db()

    # Start WebSocket event streamer
    await event_streamer.start()
    logger.info("Event streamer started")

    yield

    # Shutdown
    logger.info("Shutting down application...")
    await event_streamer.stop()
    logger.info("Event streamer stopped")


# API metadata for OpenAPI documentation
API_DESCRIPTION = """
# Micro-Alpha News Scraper API

A real-time financial news aggregation and sentiment analysis platform designed for traders
focused on micro-cap and small-cap stocks.

## Features

* **Real-time Event Ingestion**: SEC filings captured within 30 seconds of publication
* **ML-Powered Sentiment Analysis**: FinBERT model for accurate financial sentiment
* **Alpha Scoring**: Multi-factor signal quality scoring for high-conviction opportunities
* **Full-Text Search**: OpenSearch-powered search across all events
* **WebSocket Streaming**: Real-time event notifications

## Authentication

The API supports two authentication methods:

### JWT Bearer Token (Web/Mobile Apps)
Obtain tokens via the `/api/v1/auth/login` endpoint:
```
Authorization: Bearer <your_jwt_token>
```

### API Key (Programmatic Access)
Generate API keys at `/api/v1/api-keys` and use them via header:
```
X-API-Key: malf_<your_api_key>
```

API keys support scopes (`read`, `write`, `admin`) and can have custom rate limits.

## Rate Limiting

Rate limits are enforced per subscription tier:

| Tier | Requests/Minute |
|------|-----------------|
| Anonymous | 30 |
| Starter | 60 |
| Professional | 300 |
| Team | 600 |
| Enterprise | 3000 |

Rate limit headers are included in all responses:
- `X-RateLimit-Limit`: Your rate limit
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets

## Versioning

All API endpoints are versioned under `/api/v1/`. Future versions will be available
at `/api/v2/`, etc.
"""

API_TAGS_METADATA = [
    {
        "name": "Authentication",
        "description": "User registration, login, and token management.",
    },
    {
        "name": "API Keys",
        "description": "API key management for programmatic access.",
    },
    {
        "name": "Events",
        "description": "Financial news events with sentiment analysis and alpha scores.",
    },
    {
        "name": "Search",
        "description": "Full-text search across events using OpenSearch.",
    },
    {
        "name": "Tickers",
        "description": "Ticker information, sentiment aggregation, and event timelines.",
    },
    {
        "name": "Watchlist",
        "description": "User watchlist management for tracking specific tickers.",
    },
    {
        "name": "Alerts",
        "description": "Custom alert rules for event notifications.",
    },
    {
        "name": "Billing",
        "description": "Subscription management via Stripe integration.",
    },
    {
        "name": "Stats",
        "description": "Dashboard statistics and market sentiment overview.",
    },
    {
        "name": "Notifications",
        "description": "Push notification management and preferences.",
    },
    {
        "name": "WebSocket",
        "description": "Real-time event streaming via WebSocket connections.",
    },
]

# Create FastAPI app
app = FastAPI(
    title="Micro-Alpha News Scraper API",
    description=API_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=API_TAGS_METADATA,
    contact={
        "name": "Micro-Alpha Support",
        "url": "https://github.com/KTMAnimations/news-scraper",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# Rate limiting middleware (add first so it runs early)
if not settings.debug:
    app.add_middleware(RateLimitMiddleware, default_limit=60, window_seconds=60)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(api_keys.router, prefix="/api/v1/api-keys", tags=["API Keys"])
app.include_router(events.router, prefix="/api/v1/events", tags=["Events"])
app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
app.include_router(tickers.router, prefix="/api/v1/tickers", tags=["Tickers"])
app.include_router(watchlist.router, prefix="/api/v1/watchlist", tags=["Watchlist"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alerts"])
app.include_router(billing.router, prefix="/api/v1/billing", tags=["Billing"])
app.include_router(stats.router, prefix="/api/v1/stats", tags=["Stats"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])

# WebSocket routes (no prefix - paths defined in router)
app.include_router(websocket_router, tags=["WebSocket"])


@app.get(
    "/",
    summary="API Root",
    description="Returns basic API information and status.",
    response_description="API status and version information",
    tags=["Health"],
)
async def root():
    """Root endpoint returning API information.

    Returns:
        dict: API name, version, and running status.
    """
    return {
        "name": "Micro-Alpha News Scraper API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get(
    "/health",
    summary="Health Check",
    description="Returns the health status of the API. Used for container orchestration health probes.",
    response_description="Health status object",
    tags=["Health"],
)
async def health_check():
    """Health check endpoint for monitoring and orchestration.

    This endpoint is used by Docker health checks and load balancers
    to verify the API is responding to requests.

    Returns:
        dict: Health status indicating the service is healthy.
    """
    return {"status": "healthy"}
