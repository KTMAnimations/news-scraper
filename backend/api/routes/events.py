"""Event routes.

This module provides endpoints for accessing financial news events
with sentiment analysis, alpha scores, and filtering capabilities.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.dependencies import DBSession, OptionalUser
from backend.storage.timescale.queries import EventQueries

router = APIRouter()


class EventResponse(BaseModel):
    """Financial event response model.

    Represents a single financial news event with sentiment analysis
    and alpha scoring.

    Attributes:
        id: Unique event identifier (UUID).
        ticker: Associated stock ticker symbol.
        event_time: When the event occurred.
        event_type: Type of event (e.g., SEC_FILING, PRESS_RELEASE, EARNINGS).
        event_category: Category for grouping (e.g., INSIDER_TRADE, FDA, M_AND_A).
        headline: Event headline or title.
        summary: Brief summary of the event.
        source_url: Link to original source.
        source_name: Name of the news source.
        sentiment_score: FinBERT sentiment score (-1.0 to 1.0).
        sentiment_label: Sentiment classification (POSITIVE, NEGATIVE, NEUTRAL).
        alpha_score: Computed trading signal strength (0.0 to 1.0).
        direction: Trading direction indicator (BULLISH, BEARISH, NEUTRAL).
        urgency_level: Priority level (CRITICAL, HIGH, MEDIUM, LOW).
        extracted_tickers: Additional tickers mentioned in the content.
    """

    id: str = Field(..., description="Unique event identifier")
    ticker: str = Field(..., description="Stock ticker symbol")
    event_time: datetime | None = Field(None, description="Event timestamp")
    event_type: str = Field(..., description="Type of financial event")
    event_category: str | None = Field(None, description="Event category")
    headline: str = Field(..., description="Event headline")
    summary: str | None = Field(None, description="Event summary")
    source_url: str | None = Field(None, description="Source URL")
    source_name: str | None = Field(None, description="Source name")
    sentiment_score: float | None = Field(None, description="Sentiment score (-1 to 1)")
    sentiment_label: str | None = Field(None, description="Sentiment label")
    alpha_score: float | None = Field(None, description="Alpha score (0 to 1)")
    direction: str | None = Field(None, description="Trading direction")
    urgency_level: str | None = Field(None, description="Urgency level")
    extracted_tickers: list[str] | None = Field(None, description="Mentioned tickers")


class EventListResponse(BaseModel):
    """Paginated event list response.

    Attributes:
        events: List of events matching the query.
        total: Total number of matching events.
        limit: Maximum events per page.
        offset: Current page offset.
    """

    events: list[EventResponse] = Field(..., description="List of events")
    total: int = Field(..., description="Total matching events")
    limit: int = Field(..., description="Page size limit")
    offset: int = Field(..., description="Current offset")


@router.get(
    "",
    response_model=EventListResponse,
    summary="List financial events",
    description="""
Retrieve a paginated list of financial events with optional filtering.

Supports filtering by ticker, event type, alpha score, direction, and urgency level.
Results are sorted by event time in descending order (newest first).

**Event Types:**
- `SEC_FILING`: SEC filings (Form 4, 8-K, 13D/G)
- `PRESS_RELEASE`: Press releases from newswires
- `EARNINGS`: Earnings announcements
- `SOCIAL`: Social media mentions

**Directions:**
- `BULLISH`: Positive market signal
- `BEARISH`: Negative market signal
- `NEUTRAL`: No clear directional signal

**Urgency Levels:**
- `CRITICAL`: Immediate attention required (alpha >= 0.8)
- `HIGH`: High priority (alpha >= 0.6)
- `MEDIUM`: Standard priority (alpha >= 0.4)
- `LOW`: Low priority (alpha < 0.4)
    """,
    response_description="Paginated list of events",
)
async def list_events(
    db: DBSession,
    current_user: OptionalUser,
    ticker: str | None = Query(None, description="Filter by ticker symbol (e.g., AAPL)", examples=["AAPL"]),
    event_type: str | None = Query(None, description="Filter by event type", examples=["SEC_FILING"]),
    min_alpha: float | None = Query(None, ge=0.0, le=1.0, description="Minimum alpha score (0-1)", examples=[0.5]),
    direction: str | None = Query(None, description="Filter by direction", examples=["BULLISH"]),
    urgency_level: str | None = Query(None, description="Filter by urgency level", examples=["HIGH"]),
    limit: int = Query(100, ge=1, le=500, description="Maximum events to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """List financial events with filtering and pagination.

    Retrieves events from the database with optional filters for ticker,
    event type, alpha score, direction, and urgency level.

    Args:
        db: Database session (injected).
        current_user: Optional authenticated user (injected).
        ticker: Filter by ticker symbol.
        event_type: Filter by event type.
        min_alpha: Minimum alpha score threshold.
        direction: Filter by trading direction.
        urgency_level: Filter by urgency level.
        limit: Maximum number of events to return.
        offset: Pagination offset.

    Returns:
        EventListResponse: Paginated list of matching events.
    """
    queries = EventQueries(db)

    events = await queries.get_events(
        ticker=ticker,
        event_type=event_type,
        min_alpha=min_alpha,
        direction=direction,
        urgency_level=urgency_level,
        limit=limit,
        offset=offset,
    )

    total = await queries.count_events(ticker=ticker, event_type=event_type)

    return EventListResponse(
        events=[
            EventResponse(
                id=str(e.id),
                ticker=e.ticker,
                event_time=e.event_time,
                event_type=e.event_type,
                event_category=e.event_category,
                headline=e.headline,
                summary=e.summary,
                source_url=e.source_url,
                source_name=e.source_name,
                sentiment_score=e.sentiment_score,
                sentiment_label=e.sentiment_label,
                alpha_score=e.alpha_score,
                direction=e.direction,
                urgency_level=e.urgency_level,
                extracted_tickers=e.extracted_tickers,
            )
            for e in events
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/latest",
    response_model=list[EventResponse],
    summary="Get latest events",
    description="Retrieve the most recent financial events, sorted by event time descending.",
    response_description="List of latest events",
)
async def get_latest_events(
    db: DBSession,
    current_user: OptionalUser,
    limit: int = Query(50, ge=1, le=100, description="Maximum events to return"),
):
    """Get the most recent financial events.

    Returns events sorted by event_time in descending order (newest first).
    Useful for displaying a real-time feed of financial news.

    Args:
        db: Database session (injected).
        current_user: Optional authenticated user (injected).
        limit: Maximum number of events to return (1-100).

    Returns:
        list[EventResponse]: List of latest events.
    """
    queries = EventQueries(db)
    events = await queries.get_latest_events(limit=limit)

    return [
        EventResponse(
            id=str(e.id),
            ticker=e.ticker,
            event_time=e.event_time,
            event_type=e.event_type,
            event_category=e.event_category,
            headline=e.headline,
            summary=e.summary,
            source_url=e.source_url,
            source_name=e.source_name,
            sentiment_score=e.sentiment_score,
            sentiment_label=e.sentiment_label,
            alpha_score=e.alpha_score,
            direction=e.direction,
            urgency_level=e.urgency_level,
            extracted_tickers=e.extracted_tickers,
        )
        for e in events
    ]


@router.get(
    "/high-alpha",
    response_model=list[EventResponse],
    summary="Get high-alpha events",
    description="""
Retrieve events with high alpha scores indicating potential trading opportunities.

Alpha scores combine multiple factors:
- **Event Type Weight (35%)**: Insider trades, FDA approvals score higher
- **Sentiment Score (25%)**: FinBERT sentiment analysis
- **Source Reliability (15%)**: SEC filings score highest
- **Recency (15%)**: More recent events score higher
- **Liquidity Factor (10%)**: Micro-cap stocks weighted higher

Events with alpha >= 0.7 are considered high-conviction opportunities.
    """,
    response_description="List of high-alpha events",
)
async def get_high_alpha_events(
    db: DBSession,
    current_user: OptionalUser,
    min_alpha: float = Query(0.5, ge=0.0, le=1.0, description="Minimum alpha score threshold"),
    hours: int = Query(24, ge=1, le=168, description="Look back period in hours"),
    limit: int = Query(50, ge=1, le=100, description="Maximum events to return"),
):
    """Get events with high alpha scores.

    Returns events that exceed the minimum alpha score threshold within
    the specified time window. High alpha events represent potential
    trading opportunities based on our multi-factor scoring model.

    Args:
        db: Database session (injected).
        current_user: Optional authenticated user (injected).
        min_alpha: Minimum alpha score threshold (default: 0.5).
        hours: Time window in hours to look back (default: 24).
        limit: Maximum number of events to return.

    Returns:
        list[EventResponse]: List of high-alpha events.
    """
    queries = EventQueries(db)
    events = await queries.get_high_alpha_events(
        min_alpha=min_alpha,
        hours=hours,
        limit=limit,
    )

    return [
        EventResponse(
            id=str(e.id),
            ticker=e.ticker,
            event_time=e.event_time,
            event_type=e.event_type,
            event_category=e.event_category,
            headline=e.headline,
            summary=e.summary,
            source_url=e.source_url,
            source_name=e.source_name,
            sentiment_score=e.sentiment_score,
            sentiment_label=e.sentiment_label,
            alpha_score=e.alpha_score,
            direction=e.direction,
            urgency_level=e.urgency_level,
            extracted_tickers=e.extracted_tickers,
        )
        for e in events
    ]


@router.get(
    "/ticker/{ticker}",
    response_model=list[EventResponse],
    summary="Get events by ticker",
    description="Retrieve all events associated with a specific stock ticker symbol.",
    response_description="List of events for the ticker",
)
async def get_ticker_events(
    ticker: str,
    db: DBSession,
    current_user: OptionalUser,
    limit: int = Query(100, ge=1, le=500, description="Maximum events to return"),
):
    """Get events for a specific ticker symbol.

    Returns all events associated with the given ticker, sorted by
    event time descending. Useful for viewing the complete news
    history for a specific stock.

    Args:
        ticker: Stock ticker symbol (e.g., AAPL, TSLA).
        db: Database session (injected).
        current_user: Optional authenticated user (injected).
        limit: Maximum number of events to return.

    Returns:
        list[EventResponse]: List of events for the ticker.
    """
    queries = EventQueries(db)
    events = await queries.get_ticker_events(ticker=ticker, limit=limit)

    return [
        EventResponse(
            id=str(e.id),
            ticker=e.ticker,
            event_time=e.event_time,
            event_type=e.event_type,
            event_category=e.event_category,
            headline=e.headline,
            summary=e.summary,
            source_url=e.source_url,
            source_name=e.source_name,
            sentiment_score=e.sentiment_score,
            sentiment_label=e.sentiment_label,
            alpha_score=e.alpha_score,
            direction=e.direction,
            urgency_level=e.urgency_level,
            extracted_tickers=e.extracted_tickers,
        )
        for e in events
    ]


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    summary="Get event by ID",
    description="Retrieve a single event by its unique identifier.",
    response_description="Event details",
    responses={
        200: {"description": "Event found"},
        404: {"description": "Event not found"},
    },
)
async def get_event(
    event_id: UUID,
    db: DBSession,
    current_user: OptionalUser,
):
    """Get a single event by its ID.

    Retrieves the full details of a specific event by its unique identifier.

    Args:
        event_id: Unique event identifier (UUID).
        db: Database session (injected).
        current_user: Optional authenticated user (injected).

    Returns:
        EventResponse: The requested event.

    Raises:
        HTTPException: 404 if event not found.
    """
    queries = EventQueries(db)
    event = await queries.get_event(event_id)

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    return EventResponse(
        id=str(event.id),
        ticker=event.ticker,
        event_time=event.event_time,
        event_type=event.event_type,
        event_category=event.event_category,
        headline=event.headline,
        summary=event.summary,
        source_url=event.source_url,
        source_name=event.source_name,
        sentiment_score=event.sentiment_score,
        sentiment_label=event.sentiment_label,
        alpha_score=event.alpha_score,
        direction=event.direction,
        urgency_level=event.urgency_level,
        extracted_tickers=event.extracted_tickers,
    )
