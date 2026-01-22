"""Watchlist routes."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.api.dependencies import CurrentUser, DBSession
from backend.storage.timescale.queries import WatchlistQueries

router = APIRouter()


class WatchlistItem(BaseModel):
    """Watchlist item response."""

    id: str
    ticker: str
    added_at: datetime | None
    notes: str | None
    alert_enabled: bool


class WatchlistAdd(BaseModel):
    """Add to watchlist request."""

    ticker: str
    notes: str | None = None


@router.get("", response_model=list[WatchlistItem])
async def get_watchlist(
    db: DBSession,
    current_user: CurrentUser,
):
    """Get user's watchlist."""
    queries = WatchlistQueries(db)
    items = await queries.get_user_watchlist(current_user.id)

    return [
        WatchlistItem(
            id=str(item.id),
            ticker=item.ticker,
            added_at=item.added_at,
            notes=item.notes,
            alert_enabled=item.alert_enabled,
        )
        for item in items
    ]


@router.post("", response_model=WatchlistItem)
async def add_to_watchlist(
    data: WatchlistAdd,
    db: DBSession,
    current_user: CurrentUser,
):
    """Add ticker to watchlist."""
    queries = WatchlistQueries(db)

    try:
        item = await queries.add_to_watchlist(
            user_id=current_user.id,
            ticker=data.ticker,
            notes=data.notes,
        )
        await db.commit()

        return WatchlistItem(
            id=str(item.id),
            ticker=item.ticker,
            added_at=item.added_at,
            notes=item.notes,
            alert_enabled=item.alert_enabled,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticker already in watchlist or invalid",
        )


@router.delete("/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    db: DBSession,
    current_user: CurrentUser,
):
    """Remove ticker from watchlist."""
    queries = WatchlistQueries(db)

    removed = await queries.remove_from_watchlist(
        user_id=current_user.id,
        ticker=ticker,
    )

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticker not in watchlist",
        )

    await db.commit()

    return {"status": "removed", "ticker": ticker.upper()}
