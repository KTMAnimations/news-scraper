"""Ticker routes."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from backend.api.dependencies import CurrentUser, DBSession
from backend.storage.timescale.queries import EventQueries

router = APIRouter()


class TickerSentiment(BaseModel):
    """Ticker sentiment response."""

    ticker: str
    event_count: int
    avg_sentiment: float
    avg_alpha: float
    time_window_hours: int


class TickerInfo(BaseModel):
    """Ticker info response."""

    ticker: str
    company_name: str | None
    cik: str | None
    is_valid: bool


@router.get("", response_model=list[str])
async def list_tickers(
    db: DBSession,
    current_user: CurrentUser,
    limit: int = Query(100, ge=1, le=500),
):
    """List tracked tickers."""
    # This would return tickers with recent events
    queries = EventQueries(db)

    # Get unique tickers from recent events
    events = await queries.get_latest_events(limit=500)
    tickers = list(set(e.ticker for e in events if e.ticker))[:limit]

    return sorted(tickers)


@router.get("/{ticker}", response_model=TickerInfo)
async def get_ticker_info(
    ticker: str,
    db: DBSession,
    current_user: CurrentUser,
):
    """Get ticker information."""
    import asyncio

    from backend.processing.ner import TickerKnowledgeBase

    kb = TickerKnowledgeBase()
    await kb.load()

    is_valid = kb.is_valid_ticker(ticker)

    return TickerInfo(
        ticker=ticker.upper(),
        company_name=kb.get_company_name(ticker),
        cik=kb.get_cik(ticker),
        is_valid=is_valid,
    )


@router.get("/{ticker}/sentiment", response_model=TickerSentiment)
async def get_ticker_sentiment(
    ticker: str,
    db: DBSession,
    current_user: CurrentUser,
    hours: int = Query(24, ge=1, le=168),
):
    """Get aggregated sentiment for a ticker."""
    queries = EventQueries(db)
    sentiment = await queries.get_ticker_sentiment(ticker, hours=hours)

    return TickerSentiment(**sentiment)


@router.get("/{ticker}/timeline")
async def get_ticker_timeline(
    ticker: str,
    db: DBSession,
    current_user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
):
    """Get event timeline for a ticker."""
    queries = EventQueries(db)
    events = await queries.get_ticker_events(ticker, limit=limit)

    return {
        "ticker": ticker.upper(),
        "events": [
            {
                "id": str(e.id),
                "event_time": e.event_time.isoformat() if e.event_time else None,
                "event_type": e.event_type,
                "headline": e.headline,
                "alpha_score": e.alpha_score,
                "direction": e.direction,
            }
            for e in events
        ],
    }
