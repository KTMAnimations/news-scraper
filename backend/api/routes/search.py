"""Search routes."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.api.dependencies import CurrentUser, DBSession
from backend.storage.opensearch.client import opensearch_client
from backend.storage.timescale.queries import EventQueries

router = APIRouter()


class SearchResult(BaseModel):
    """Search result item."""

    id: str
    ticker: str | None
    headline: str
    summary: str | None
    event_type: str | None
    event_time: datetime | str | None
    alpha_score: float | None
    direction: str | None
    source_name: str | None
    score: float | None = None
    highlights: dict[str, list[str]] | None = None


class SearchResponse(BaseModel):
    """Search response."""

    results: list[SearchResult]
    total: int
    query: str


class TickerSuggestion(BaseModel):
    """Ticker suggestion with metadata."""

    ticker: str
    event_count: int
    latest_headline: str | None
    latest_direction: str | None
    latest_alpha: float | None


@router.post("", response_model=SearchResponse)
async def search_events(
    db: DBSession,
    current_user: CurrentUser,
    ticker: str | None = Query(None, description="Filter by ticker"),
    event_type: str | None = Query(None, description="Filter by event type"),
    direction: str | None = Query(None, description="Filter by direction"),
    min_alpha: float | None = Query(None, description="Minimum alpha score"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Search events using OpenSearch full-text search."""
    # Build filters
    filters = {}
    if ticker:
        filters["ticker"] = ticker
    if event_type:
        filters["event_type"] = event_type
    if direction:
        filters["direction"] = direction
    if min_alpha is not None:
        filters["min_alpha"] = min_alpha

    # Search using OpenSearch
    search_result = await opensearch_client.search(
        query=query,
        filters=filters,
        limit=limit,
        offset=offset,
    )

    # If OpenSearch fails or returns no results, fall back to database
    if search_result.get("error") or not search_result.get("results"):
        queries = EventQueries(db)
        events = await queries.search_events(query, limit=limit)

        return SearchResponse(
            results=[
                SearchResult(
                    id=str(e.id),
                    ticker=e.ticker,
                    headline=e.headline,
                    summary=e.summary,
                    event_type=e.event_type,
                    event_time=e.event_time,
                    alpha_score=e.alpha_score,
                    direction=e.direction,
                    source_name=e.source_name,
                )
                for e in events
            ],
            total=len(events),
            query=query,
        )

    return SearchResponse(
        results=[
            SearchResult(
                id=r.get("id", ""),
                ticker=r.get("ticker"),
                headline=r.get("headline", ""),
                summary=r.get("summary"),
                event_type=r.get("event_type"),
                event_time=r.get("event_time"),
                alpha_score=r.get("alpha_score"),
                direction=r.get("direction"),
                source_name=r.get("source_name"),
                score=r.get("_score"),
                highlights=r.get("_highlights"),
            )
            for r in search_result.get("results", [])
        ],
        total=search_result.get("total", 0),
        query=query,
    )


@router.get("/suggest")
async def get_suggestions(
    db: DBSession,
    current_user: CurrentUser,
    q: str = Query(..., min_length=1, description="Query prefix"),
    limit: int = Query(10, ge=1, le=20),
):
    """Get autocomplete suggestions for search."""
    # Get headline suggestions from OpenSearch
    headline_suggestions = await opensearch_client.suggest(
        prefix=q,
        field="headline",
        limit=limit,
    )

    # Get ticker suggestions
    ticker_suggestions = await opensearch_client.get_ticker_suggestions(
        prefix=q,
        limit=5,
    )

    return {
        "headlines": headline_suggestions,
        "tickers": [t.get("ticker") for t in ticker_suggestions],
        "ticker_details": ticker_suggestions,
    }


@router.get("/tickers", response_model=list[TickerSuggestion])
async def get_ticker_suggestions(
    current_user: CurrentUser,
    q: str = Query(..., min_length=1, description="Ticker prefix"),
    limit: int = Query(10, ge=1, le=20),
):
    """Get ticker suggestions with event metadata."""
    suggestions = await opensearch_client.get_ticker_suggestions(
        prefix=q,
        limit=limit,
    )

    return [
        TickerSuggestion(
            ticker=s.get("ticker", ""),
            event_count=s.get("event_count", 0),
            latest_headline=s.get("latest_headline"),
            latest_direction=s.get("latest_direction"),
            latest_alpha=s.get("latest_alpha"),
        )
        for s in suggestions
    ]
