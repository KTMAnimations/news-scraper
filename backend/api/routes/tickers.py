"""Ticker routes."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from backend.api.dependencies import CurrentUser, DBSession
from backend.storage.timescale.queries import EventQueries

logger = structlog.get_logger(__name__)

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


class TickerStats(BaseModel):
    """Ticker statistics response."""

    ticker: str
    event_count: int
    avg_sentiment: float
    avg_alpha: float
    bullish_count: int
    bearish_count: int
    neutral_count: int
    high_alpha_count: int
    sentiment_trend: Literal["improving", "declining", "stable"]
    last_event_time: datetime | None
    time_window_hours: int


class TickerPrice(BaseModel):
    """Ticker price data response."""

    ticker: str
    price: float | None
    change: float | None
    change_percent: float | None
    volume: int | None
    market_cap: float | None
    high_52w: float | None
    low_52w: float | None
    last_updated: datetime | None
    source: str


class RelatedTicker(BaseModel):
    """Related ticker info."""

    ticker: str
    company_name: str | None
    reason: str
    event_count: int
    avg_sentiment: float


class RelatedTickersResponse(BaseModel):
    """Related tickers response."""

    ticker: str
    related: list[RelatedTicker]


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


@router.get("/{ticker}/stats", response_model=TickerStats)
async def get_ticker_stats(
    ticker: str,
    db: DBSession,
    current_user: CurrentUser,
    hours: int = Query(24, ge=1, le=168),
):
    """Get comprehensive statistics for a ticker.

    Returns event count, sentiment metrics, direction distribution,
    and sentiment trend analysis.
    """
    queries = EventQueries(db)
    ticker_upper = ticker.upper()

    # Get events for the time period
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    events = await queries.get_events(
        ticker=ticker_upper,
        start_time=cutoff,
        limit=1000,
    )

    if not events:
        return TickerStats(
            ticker=ticker_upper,
            event_count=0,
            avg_sentiment=0.0,
            avg_alpha=0.0,
            bullish_count=0,
            bearish_count=0,
            neutral_count=0,
            high_alpha_count=0,
            sentiment_trend="stable",
            last_event_time=None,
            time_window_hours=hours,
        )

    # Calculate statistics
    sentiment_scores = [e.sentiment_score for e in events if e.sentiment_score is not None]
    alpha_scores = [e.alpha_score for e in events if e.alpha_score is not None]

    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
    avg_alpha = sum(alpha_scores) / len(alpha_scores) if alpha_scores else 0.0

    bullish_count = sum(1 for e in events if e.direction == "BULLISH")
    bearish_count = sum(1 for e in events if e.direction == "BEARISH")
    neutral_count = sum(1 for e in events if e.direction == "NEUTRAL" or not e.direction)
    high_alpha_count = sum(1 for e in events if e.alpha_score and abs(e.alpha_score) >= 0.7)

    # Calculate sentiment trend
    # Compare first half vs second half of the time period
    midpoint = cutoff + timedelta(hours=hours / 2)
    first_half = [e.sentiment_score for e in events if e.event_time and e.event_time < midpoint and e.sentiment_score is not None]
    second_half = [e.sentiment_score for e in events if e.event_time and e.event_time >= midpoint and e.sentiment_score is not None]

    first_avg = sum(first_half) / len(first_half) if first_half else 0
    second_avg = sum(second_half) / len(second_half) if second_half else 0

    diff = second_avg - first_avg
    if diff > 0.1:
        sentiment_trend = "improving"
    elif diff < -0.1:
        sentiment_trend = "declining"
    else:
        sentiment_trend = "stable"

    # Get last event time
    last_event_time = max((e.event_time for e in events if e.event_time), default=None)

    return TickerStats(
        ticker=ticker_upper,
        event_count=len(events),
        avg_sentiment=round(avg_sentiment, 4),
        avg_alpha=round(avg_alpha, 4),
        bullish_count=bullish_count,
        bearish_count=bearish_count,
        neutral_count=neutral_count,
        high_alpha_count=high_alpha_count,
        sentiment_trend=sentiment_trend,
        last_event_time=last_event_time,
        time_window_hours=hours,
    )


async def _fetch_yahoo_price(ticker: str) -> TickerPrice | None:
    """Fetch price data from Yahoo Finance API (free, no API key required)."""
    try:
        # Use Yahoo Finance v8 quote endpoint
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        params = {
            "interval": "1d",
            "range": "1d",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                logger.warning(f"Yahoo Finance API returned {response.status_code} for {ticker}")
                return None

            data = response.json()
            result = data.get("chart", {}).get("result", [])

            if not result:
                return None

            meta = result[0].get("meta", {})
            quote = result[0].get("indicators", {}).get("quote", [{}])[0]

            # Get current price
            price = meta.get("regularMarketPrice")
            prev_close = meta.get("previousClose")

            # Calculate change
            change = None
            change_percent = None
            if price and prev_close:
                change = price - prev_close
                change_percent = (change / prev_close) * 100

            # Get volume (latest)
            volumes = quote.get("volume", [])
            volume = volumes[-1] if volumes else None

            return TickerPrice(
                ticker=ticker.upper(),
                price=price,
                change=round(change, 2) if change else None,
                change_percent=round(change_percent, 2) if change_percent else None,
                volume=volume,
                market_cap=meta.get("marketCap"),
                high_52w=meta.get("fiftyTwoWeekHigh"),
                low_52w=meta.get("fiftyTwoWeekLow"),
                last_updated=datetime.now(timezone.utc),
                source="yahoo",
            )

    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching Yahoo Finance data for {ticker}")
        return None
    except Exception as e:
        logger.error(f"Error fetching Yahoo Finance data for {ticker}: {e}")
        return None


async def _fetch_finnhub_price(ticker: str) -> TickerPrice | None:
    """Fetch price data from Finnhub (free tier available)."""
    try:
        # Finnhub free tier - limited requests
        url = "https://finnhub.io/api/v1/quote"
        params = {
            "symbol": ticker.upper(),
            # Note: In production, you'd want to add an API key here
            # "token": settings.finnhub_api_key,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                return None

            data = response.json()

            # Check if we got valid data
            if not data.get("c"):
                return None

            return TickerPrice(
                ticker=ticker.upper(),
                price=data.get("c"),  # Current price
                change=data.get("d"),  # Change
                change_percent=data.get("dp"),  # Change percent
                volume=None,  # Not provided in quote endpoint
                market_cap=None,
                high_52w=data.get("h"),  # Day high (not 52w)
                low_52w=data.get("l"),  # Day low (not 52w)
                last_updated=datetime.now(timezone.utc),
                source="finnhub",
            )

    except Exception as e:
        logger.error(f"Error fetching Finnhub data for {ticker}: {e}")
        return None


@router.get("/{ticker}/price", response_model=TickerPrice)
async def get_ticker_price(
    ticker: str,
    current_user: CurrentUser,
):
    """Get current price data for a ticker.

    Fetches real-time price data from free financial data providers.
    Falls back to multiple sources if primary fails.
    """
    ticker_upper = ticker.upper()

    # Try Yahoo Finance first (most reliable free source)
    price_data = await _fetch_yahoo_price(ticker_upper)

    if price_data:
        return price_data

    # Fall back to Finnhub if available
    price_data = await _fetch_finnhub_price(ticker_upper)

    if price_data:
        return price_data

    # Return empty response if all sources fail
    return TickerPrice(
        ticker=ticker_upper,
        price=None,
        change=None,
        change_percent=None,
        volume=None,
        market_cap=None,
        high_52w=None,
        low_52w=None,
        last_updated=None,
        source="none",
    )


@router.get("/{ticker}/related", response_model=RelatedTickersResponse)
async def get_related_tickers(
    ticker: str,
    db: DBSession,
    current_user: CurrentUser,
    limit: int = Query(10, ge=1, le=50),
):
    """Get related tickers based on co-mentions in events.

    Finds tickers that frequently appear in the same events
    or are mentioned together in news.
    """
    from backend.processing.ner import TickerKnowledgeBase

    queries = EventQueries(db)
    ticker_upper = ticker.upper()

    # Load knowledge base for company names
    kb = TickerKnowledgeBase()
    await kb.load()

    # Get recent events for this ticker
    events = await queries.get_ticker_events(ticker_upper, limit=200)

    if not events:
        return RelatedTickersResponse(ticker=ticker_upper, related=[])

    # Count co-mentioned tickers
    co_mentions: dict[str, int] = {}
    for event in events:
        # Check extracted_tickers field
        if event.extra_data and event.extra_data.get("extracted_tickers"):
            for t in event.extra_data["extracted_tickers"]:
                if t and t.upper() != ticker_upper:
                    t_upper = t.upper()
                    co_mentions[t_upper] = co_mentions.get(t_upper, 0) + 1

    # If no co-mentions found in extracted_tickers, try to find tickers
    # that have events around the same time
    if not co_mentions:
        # Get event times
        event_times = [e.event_time for e in events if e.event_time]
        if event_times:
            min_time = min(event_times) - timedelta(hours=1)
            max_time = max(event_times) + timedelta(hours=1)

            # Get other events in the same time window
            recent_events = await queries.get_events(
                start_time=min_time,
                end_time=max_time,
                limit=500,
            )

            for event in recent_events:
                if event.ticker and event.ticker != ticker_upper:
                    co_mentions[event.ticker] = co_mentions.get(event.ticker, 0) + 1

    # Sort by frequency and get top related
    sorted_tickers = sorted(co_mentions.items(), key=lambda x: x[1], reverse=True)[:limit]

    # Build related ticker info
    related = []
    for related_ticker, count in sorted_tickers:
        # Get sentiment for related ticker
        sentiment = await queries.get_ticker_sentiment(related_ticker, hours=24)

        related.append(
            RelatedTicker(
                ticker=related_ticker,
                company_name=kb.get_company_name(related_ticker),
                reason="co-mentioned" if co_mentions else "similar timing",
                event_count=count,
                avg_sentiment=sentiment.get("avg_sentiment", 0.0),
            )
        )

    return RelatedTickersResponse(ticker=ticker_upper, related=related)
