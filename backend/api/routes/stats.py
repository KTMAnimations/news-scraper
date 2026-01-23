"""Stats routes for dashboard statistics."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import and_, func, select

from backend.api.dependencies import CurrentUser, DBSession
from backend.storage.timescale.models import Event

router = APIRouter()


class StatsResponse(BaseModel):
    """Dashboard stats response."""

    total_events: int
    total_events_yesterday: int
    bullish_events: int
    bullish_events_yesterday: int
    bearish_events: int
    bearish_events_yesterday: int
    high_alpha_events: int
    high_alpha_events_last_hour: int


@router.get("", response_model=StatsResponse)
async def get_dashboard_stats(
    db: DBSession,
    current_user: CurrentUser,
):
    """Get dashboard statistics."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    one_hour_ago = now - timedelta(hours=1)

    # Today's stats
    today_total = await db.execute(
        select(func.count(Event.id)).where(Event.event_time >= today_start)
    )
    total_events = today_total.scalar() or 0

    today_bullish = await db.execute(
        select(func.count(Event.id)).where(
            and_(
                Event.event_time >= today_start,
                Event.direction == "BULLISH",
            )
        )
    )
    bullish_events = today_bullish.scalar() or 0

    today_bearish = await db.execute(
        select(func.count(Event.id)).where(
            and_(
                Event.event_time >= today_start,
                Event.direction == "BEARISH",
            )
        )
    )
    bearish_events = today_bearish.scalar() or 0

    today_high_alpha = await db.execute(
        select(func.count(Event.id)).where(
            and_(
                Event.event_time >= today_start,
                Event.alpha_score >= 0.7,
            )
        )
    )
    high_alpha_events = today_high_alpha.scalar() or 0

    # Yesterday's stats for comparison
    yesterday_total = await db.execute(
        select(func.count(Event.id)).where(
            and_(
                Event.event_time >= yesterday_start,
                Event.event_time < today_start,
            )
        )
    )
    total_events_yesterday = yesterday_total.scalar() or 0

    yesterday_bullish = await db.execute(
        select(func.count(Event.id)).where(
            and_(
                Event.event_time >= yesterday_start,
                Event.event_time < today_start,
                Event.direction == "BULLISH",
            )
        )
    )
    bullish_events_yesterday = yesterday_bullish.scalar() or 0

    yesterday_bearish = await db.execute(
        select(func.count(Event.id)).where(
            and_(
                Event.event_time >= yesterday_start,
                Event.event_time < today_start,
                Event.direction == "BEARISH",
            )
        )
    )
    bearish_events_yesterday = yesterday_bearish.scalar() or 0

    # Last hour high alpha
    last_hour_high_alpha = await db.execute(
        select(func.count(Event.id)).where(
            and_(
                Event.event_time >= one_hour_ago,
                Event.alpha_score >= 0.7,
            )
        )
    )
    high_alpha_events_last_hour = last_hour_high_alpha.scalar() or 0

    return StatsResponse(
        total_events=total_events,
        total_events_yesterday=total_events_yesterday,
        bullish_events=bullish_events,
        bullish_events_yesterday=bullish_events_yesterday,
        bearish_events=bearish_events,
        bearish_events_yesterday=bearish_events_yesterday,
        high_alpha_events=high_alpha_events,
        high_alpha_events_last_hour=high_alpha_events_last_hour,
    )
