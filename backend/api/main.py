"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.storage.timescale import init_db

from .routes import alerts, auth, billing, events, search, stats, tickers, watchlist
from .websocket.streamer import EventStreamer, router as websocket_router

# Global event streamer instance
event_streamer = EventStreamer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await init_db()
    await event_streamer.start()
    yield
    # Shutdown
    await event_streamer.stop()


# Create FastAPI app
app = FastAPI(
    title="News Scraper API",
    description="Micro-Alpha News Scraper for Illiquid Assets Sentiment",
    version="0.1.0",
    lifespan=lifespan,
)

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
app.include_router(events.router, prefix="/api/v1/events", tags=["Events"])
app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
app.include_router(tickers.router, prefix="/api/v1/tickers", tags=["Tickers"])
app.include_router(watchlist.router, prefix="/api/v1/watchlist", tags=["Watchlist"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alerts"])
app.include_router(billing.router, prefix="/api/v1/billing", tags=["Billing"])
app.include_router(stats.router, prefix="/api/v1/stats", tags=["Stats"])
app.include_router(websocket_router, prefix="/api/v1", tags=["WebSocket"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "News Scraper API",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
