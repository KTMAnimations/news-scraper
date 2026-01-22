"""Event routes."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from backend.api.dependencies import CurrentUser, DBSession
from backend.storage.timescale.queries import EventQueries

router = APIRouter()


class EventResponse(BaseModel):
    """Event response model."""

    id: str
    ticker: str
    event_time: datetime | None
    event_type: str
    event_category: str | None
    headline: str
    summary: str | None
    source_url: str | None
    source_name: str | None
    sentiment_score: float | None
    sentiment_label: str | None
    alpha_score: float | None
    direction: str | None
    urgency_level: str | None
    extracted_tickers: list[str] | None


class EventListResponse(BaseModel):
    """Event list response."""

    events: list[EventResponse]
    total: int
    limit: int
    offset: int


@router.get("", response_model=EventListResponse)
async def list_events(
    db: DBSession,
    current_user: CurrentUser,
    ticker: str | None = Query(None, description="Filter by ticker"),
    event_type: str | None = Query(None, description="Filter by event type"),
    min_alpha: float | None = Query(None, description="Minimum alpha score"),
    direction: str | None = Query(None, description="Filter by direction"),
    urgency_level: str | None = Query(None, description="Filter by urgency level"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List events with filtering."""
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


@router.get("/latest", response_model=list[EventResponse])
async def get_latest_events(
    db: DBSession,
    current_user: CurrentUser,
    limit: int = Query(50, ge=1, le=100),
):
    """Get latest events."""
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


@router.get("/high-alpha", response_model=list[EventResponse])
async def get_high_alpha_events(
    db: DBSession,
    current_user: CurrentUser,
    min_alpha: float = Query(0.5, ge=0.0, le=1.0),
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, ge=1, le=100),
):
    """Get high alpha score events."""
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


@router.get("/ticker/{ticker}", response_model=list[EventResponse])
async def get_ticker_events(
    ticker: str,
    db: DBSession,
    current_user: CurrentUser,
    limit: int = Query(100, ge=1, le=500),
):
    """Get events for a specific ticker."""
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


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Get single event by ID."""
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
