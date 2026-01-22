"""Search routes."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.api.dependencies import CurrentUser, DBSession
from backend.storage.timescale.queries import EventQueries

router = APIRouter()


class SearchResult(BaseModel):
    """Search result item."""

    id: str
    ticker: str
    headline: str
    summary: str | None
    event_type: str
    event_time: datetime | None
    alpha_score: float | None
    direction: str | None
    source_name: str | None


class SearchResponse(BaseModel):
    """Search response."""

    results: list[SearchResult]
    total: int
    query: str


@router.post("", response_model=SearchResponse)
async def search_events(
    db: DBSession,
    current_user: CurrentUser,
    query: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(50, ge=1, le=100),
):
    """Search events by text."""
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


@router.get("/suggest")
async def get_suggestions(
    db: DBSession,
    current_user: CurrentUser,
    q: str = Query(..., min_length=1, description="Query prefix"),
    limit: int = Query(10, ge=1, le=20),
):
    """Get autocomplete suggestions."""
    # This would use OpenSearch or similar for real autocomplete
    # Simplified implementation

    queries = EventQueries(db)
    events = await queries.search_events(q, limit=limit)

    # Extract unique tickers and headlines
    tickers = list(set(e.ticker for e in events if e.ticker))[:5]
    headlines = [e.headline[:60] for e in events[:5]]

    return {
        "tickers": tickers,
        "headlines": headlines,
    }
