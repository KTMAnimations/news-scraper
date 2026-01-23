"""Search routes for OpenSearch full-text search.

Provides endpoints for:
- Full-text search across events with filtering and sorting
- Auto-complete suggestions for headlines and tickers
"""

from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.api.dependencies import DBSession, OptionalUser
from backend.storage.opensearch.client import opensearch_client
from backend.storage.timescale.queries import EventQueries

router = APIRouter()


class SortField(str, Enum):
    """Sort field options for search results."""

    RELEVANCE = "relevance"
    DATE = "date"
    ALPHA_SCORE = "alpha_score"


class SortOrder(str, Enum):
    """Sort order options."""

    ASC = "asc"
    DESC = "desc"


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
    sentiment_label: str | None = None
    score: float | None = None
    highlights: dict[str, list[str]] | None = None


class SearchResponse(BaseModel):
    """Search response with pagination metadata."""

    results: list[SearchResult]
    total: int
    query: str
    limit: int
    offset: int


class TickerSuggestion(BaseModel):
    """Ticker suggestion with metadata."""

    ticker: str
    event_count: int
    latest_headline: str | None
    latest_direction: str | None
    latest_alpha: float | None


class SuggestionsResponse(BaseModel):
    """Combined suggestions response."""

    headlines: list[str]
    tickers: list[str]
    ticker_details: list[TickerSuggestion]


@router.get("", response_model=SearchResponse)
async def search_events(
    db: DBSession,
    current_user: OptionalUser,
    q: str = Query("", description="Search query text"),
    ticker: str | None = Query(None, description="Filter by ticker symbol"),
    event_type: str | None = Query(None, description="Filter by event type"),
    start_date: datetime | None = Query(None, description="Filter events after this date"),
    end_date: datetime | None = Query(None, description="Filter events before this date"),
    min_alpha: float | None = Query(None, ge=0.0, le=1.0, description="Minimum alpha score"),
    sort_by: SortField = Query(SortField.RELEVANCE, description="Field to sort by"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Sort order"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """Full-text search across events with filtering, pagination, and sorting.

    Search events using OpenSearch full-text search with support for:
    - Query text matching across headline, summary, and content
    - Filtering by ticker, event_type, date range, and minimum alpha score
    - Sorting by relevance, date, or alpha_score
    - Pagination with offset and limit

    Returns:
        SearchResponse with matching events and pagination metadata
    """
    # Build filters
    filters: dict[str, Any] = {}
    if ticker:
        filters["ticker"] = ticker
    if event_type:
        filters["event_type"] = event_type
    if min_alpha is not None:
        filters["min_alpha"] = min_alpha
    if start_date:
        filters["start_date"] = start_date
    if end_date:
        filters["end_date"] = end_date

    # Build sort configuration
    sort_config = _build_sort_config(sort_by, sort_order)

    # Search using OpenSearch
    search_result = await opensearch_client.search(
        query=q,
        filters=filters,
        limit=limit,
        offset=offset,
        sort=sort_config,
    )

    # If OpenSearch fails or returns no results, fall back to database
    if search_result.get("error") or (q and not search_result.get("results")):
        queries = EventQueries(db)
        events = await queries.search_events(q, limit=limit)

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
                    sentiment_label=e.sentiment_label,
                )
                for e in events
            ],
            total=len(events),
            query=q,
            limit=limit,
            offset=offset,
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
                sentiment_label=r.get("sentiment_label"),
                score=r.get("_score"),
                highlights=r.get("_highlights"),
            )
            for r in search_result.get("results", [])
        ],
        total=search_result.get("total", 0),
        query=q,
        limit=limit,
        offset=offset,
    )


def _build_sort_config(sort_by: SortField, sort_order: SortOrder) -> list[dict[str, str]]:
    """Build OpenSearch sort configuration.

    Args:
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)

    Returns:
        List of sort dictionaries for OpenSearch
    """
    order = sort_order.value

    if sort_by == SortField.RELEVANCE:
        # For relevance, always use score descending first, then date
        return [{"_score": "desc"}, {"event_time": "desc"}]
    elif sort_by == SortField.DATE:
        return [{"event_time": order}, {"_score": "desc"}]
    elif sort_by == SortField.ALPHA_SCORE:
        return [{"alpha_score": order}, {"event_time": "desc"}]

    # Default fallback
    return [{"_score": "desc"}, {"event_time": "desc"}]


@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_suggestions(
    current_user: OptionalUser,
    q: str = Query(..., min_length=1, description="Query prefix for autocomplete"),
    limit: int = Query(10, ge=1, le=20, description="Maximum suggestions to return"),
):
    """Get autocomplete suggestions for search.

    Returns headline suggestions and ticker suggestions based on the query prefix.
    Useful for implementing search-as-you-type functionality.

    Args:
        q: Query prefix to match
        limit: Maximum number of headline suggestions

    Returns:
        SuggestionsResponse with headline and ticker suggestions
    """
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

    return SuggestionsResponse(
        headlines=headline_suggestions,
        tickers=[t.get("ticker", "") for t in ticker_suggestions],
        ticker_details=[
            TickerSuggestion(
                ticker=s.get("ticker", ""),
                event_count=s.get("event_count", 0),
                latest_headline=s.get("latest_headline"),
                latest_direction=s.get("latest_direction"),
                latest_alpha=s.get("latest_alpha"),
            )
            for s in ticker_suggestions
        ],
    )


@router.get("/tickers", response_model=list[TickerSuggestion])
async def get_ticker_suggestions(
    current_user: OptionalUser,
    q: str = Query(..., min_length=1, description="Ticker prefix"),
    limit: int = Query(10, ge=1, le=20, description="Maximum ticker suggestions"),
):
    """Get ticker suggestions with event metadata.

    Search for tickers matching the given prefix and return metadata
    including event count and latest event information.

    Args:
        q: Ticker prefix to match (case-insensitive)
        limit: Maximum number of suggestions

    Returns:
        List of TickerSuggestion with event metadata
    """
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
