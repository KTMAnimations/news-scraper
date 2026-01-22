"""Database queries for events."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Alert, Event, User, Watchlist


class EventQueries:
    """Query methods for events."""

    def __init__(self, session: AsyncSession):
        """Initialize with database session.

        Args:
            session: AsyncSession instance
        """
        self.session = session

    async def create_event(self, event_data: dict[str, Any]) -> Event:
        """Create a new event.

        Args:
            event_data: Event data dictionary

        Returns:
            Created Event
        """
        event = Event(**event_data)
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_event(self, event_id: UUID) -> Event | None:
        """Get event by ID.

        Args:
            event_id: Event UUID

        Returns:
            Event or None
        """
        result = await self.session.execute(
            select(Event).where(Event.id == event_id)
        )
        return result.scalar_one_or_none()

    async def get_events(
        self,
        ticker: str | None = None,
        event_type: str | None = None,
        min_alpha: float | None = None,
        direction: str | None = None,
        urgency_level: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Event]:
        """Get events with filtering.

        Args:
            ticker: Filter by ticker
            event_type: Filter by event type
            min_alpha: Minimum alpha score
            direction: Filter by direction
            urgency_level: Filter by urgency
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of events
        """
        query = select(Event)
        conditions = []

        if ticker:
            conditions.append(Event.ticker == ticker.upper())

        if event_type:
            conditions.append(Event.event_type == event_type)

        if min_alpha is not None:
            conditions.append(Event.alpha_score >= min_alpha)

        if direction:
            conditions.append(Event.direction == direction)

        if urgency_level:
            conditions.append(Event.urgency_level == urgency_level)

        if start_time:
            conditions.append(Event.event_time >= start_time)

        if end_time:
            conditions.append(Event.event_time <= end_time)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(desc(Event.event_time)).limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_latest_events(self, limit: int = 50) -> list[Event]:
        """Get latest events.

        Args:
            limit: Maximum results

        Returns:
            List of events
        """
        result = await self.session.execute(
            select(Event)
            .order_by(desc(Event.event_time))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_high_alpha_events(
        self,
        min_alpha: float = 0.5,
        hours: int = 24,
        limit: int = 50,
    ) -> list[Event]:
        """Get high alpha score events.

        Args:
            min_alpha: Minimum alpha score threshold
            hours: Time window in hours
            limit: Maximum results

        Returns:
            List of events
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        result = await self.session.execute(
            select(Event)
            .where(
                and_(
                    Event.alpha_score >= min_alpha,
                    Event.event_time >= cutoff,
                )
            )
            .order_by(desc(Event.alpha_score))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_ticker_events(
        self,
        ticker: str,
        limit: int = 100,
        event_types: list[str] | None = None,
    ) -> list[Event]:
        """Get events for a specific ticker.

        Args:
            ticker: Stock ticker symbol
            limit: Maximum results
            event_types: Filter by event types

        Returns:
            List of events
        """
        query = select(Event).where(Event.ticker == ticker.upper())

        if event_types:
            query = query.where(Event.event_type.in_(event_types))

        query = query.order_by(desc(Event.event_time)).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_ticker_sentiment(
        self,
        ticker: str,
        hours: int = 24,
    ) -> dict[str, Any]:
        """Get aggregated sentiment for a ticker.

        Args:
            ticker: Stock ticker symbol
            hours: Time window in hours

        Returns:
            Sentiment aggregation
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        result = await self.session.execute(
            select(
                func.count(Event.id).label("count"),
                func.avg(Event.sentiment_score).label("avg_sentiment"),
                func.avg(Event.alpha_score).label("avg_alpha"),
            )
            .where(
                and_(
                    Event.ticker == ticker.upper(),
                    Event.event_time >= cutoff,
                    Event.sentiment_score.isnot(None),
                )
            )
        )

        row = result.one()

        return {
            "ticker": ticker.upper(),
            "event_count": row.count or 0,
            "avg_sentiment": float(row.avg_sentiment) if row.avg_sentiment else 0.0,
            "avg_alpha": float(row.avg_alpha) if row.avg_alpha else 0.0,
            "time_window_hours": hours,
        }

    async def search_events(
        self,
        query_text: str,
        limit: int = 50,
    ) -> list[Event]:
        """Search events by text.

        Args:
            query_text: Search query
            limit: Maximum results

        Returns:
            List of matching events
        """
        # Simple LIKE search - would use full-text search in production
        pattern = f"%{query_text}%"

        result = await self.session.execute(
            select(Event)
            .where(
                or_(
                    Event.headline.ilike(pattern),
                    Event.summary.ilike(pattern),
                    Event.ticker.ilike(pattern),
                )
            )
            .order_by(desc(Event.event_time))
            .limit(limit)
        )

        return list(result.scalars().all())

    async def count_events(
        self,
        ticker: str | None = None,
        event_type: str | None = None,
        hours: int | None = None,
    ) -> int:
        """Count events matching criteria.

        Args:
            ticker: Filter by ticker
            event_type: Filter by event type
            hours: Time window in hours

        Returns:
            Event count
        """
        query = select(func.count(Event.id))
        conditions = []

        if ticker:
            conditions.append(Event.ticker == ticker.upper())

        if event_type:
            conditions.append(Event.event_type == event_type)

        if hours:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            conditions.append(Event.event_time >= cutoff)

        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        return result.scalar() or 0


class UserQueries:
    """Query methods for users."""

    def __init__(self, session: AsyncSession):
        """Initialize with database session."""
        self.session = session

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.session.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_user(self, user_data: dict[str, Any]) -> User:
        """Create new user."""
        user = User(**user_data)
        self.session.add(user)
        await self.session.flush()
        return user


class WatchlistQueries:
    """Query methods for watchlists."""

    def __init__(self, session: AsyncSession):
        """Initialize with database session."""
        self.session = session

    async def get_user_watchlist(self, user_id: UUID) -> list[Watchlist]:
        """Get user's watchlist."""
        result = await self.session.execute(
            select(Watchlist)
            .where(Watchlist.user_id == user_id)
            .order_by(Watchlist.added_at)
        )
        return list(result.scalars().all())

    async def add_to_watchlist(
        self,
        user_id: UUID,
        ticker: str,
        notes: str | None = None,
    ) -> Watchlist:
        """Add ticker to watchlist."""
        watchlist = Watchlist(
            user_id=user_id,
            ticker=ticker.upper(),
            notes=notes,
        )
        self.session.add(watchlist)
        await self.session.flush()
        return watchlist

    async def remove_from_watchlist(self, user_id: UUID, ticker: str) -> bool:
        """Remove ticker from watchlist."""
        result = await self.session.execute(
            select(Watchlist).where(
                and_(
                    Watchlist.user_id == user_id,
                    Watchlist.ticker == ticker.upper(),
                )
            )
        )
        watchlist = result.scalar_one_or_none()

        if watchlist:
            await self.session.delete(watchlist)
            return True

        return False


class AlertQueries:
    """Query methods for alerts."""

    def __init__(self, session: AsyncSession):
        """Initialize with database session."""
        self.session = session

    async def get_user_alerts(self, user_id: UUID) -> list[Alert]:
        """Get all alerts for a user.

        Args:
            user_id: User UUID

        Returns:
            List of alerts
        """
        result = await self.session.execute(
            select(Alert).where(Alert.user_id == user_id).order_by(Alert.created_at)
        )
        return list(result.scalars().all())

    async def get_active_alerts(self, user_id: UUID) -> list[Alert]:
        """Get active alerts for a user.

        Args:
            user_id: User UUID

        Returns:
            List of active alerts
        """
        result = await self.session.execute(
            select(Alert).where(
                and_(
                    Alert.user_id == user_id,
                    Alert.is_active == True,
                )
            )
        )
        return list(result.scalars().all())

    async def get_all_active_alerts(self) -> list[Alert]:
        """Get all active alerts across all users.

        Returns:
            List of all active alerts
        """
        result = await self.session.execute(
            select(Alert).where(Alert.is_active == True)
        )
        return list(result.scalars().all())

    async def get_alert_by_id(self, alert_id: UUID) -> Alert | None:
        """Get alert by ID.

        Args:
            alert_id: Alert UUID

        Returns:
            Alert or None
        """
        result = await self.session.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        return result.scalar_one_or_none()

    async def create_alert(self, alert_data: dict[str, Any]) -> Alert:
        """Create a new alert.

        Args:
            alert_data: Alert data dictionary

        Returns:
            Created Alert
        """
        alert = Alert(**alert_data)
        self.session.add(alert)
        await self.session.flush()
        return alert

    async def update_alert(
        self,
        alert_id: UUID,
        update_data: dict[str, Any],
    ) -> Alert | None:
        """Update an alert.

        Args:
            alert_id: Alert UUID
            update_data: Fields to update

        Returns:
            Updated Alert or None
        """
        result = await self.session.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = result.scalar_one_or_none()

        if not alert:
            return None

        for key, value in update_data.items():
            if hasattr(alert, key):
                setattr(alert, key, value)

        await self.session.flush()
        return alert

    async def mark_alert_triggered(self, alert_id: UUID) -> Alert | None:
        """Mark alert as triggered with current timestamp.

        Args:
            alert_id: Alert UUID

        Returns:
            Updated Alert or None
        """
        result = await self.session.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = result.scalar_one_or_none()

        if alert:
            alert.last_triggered_at = datetime.now(timezone.utc)
            await self.session.flush()

        return alert

    async def delete_alert(self, alert_id: UUID) -> bool:
        """Delete an alert.

        Args:
            alert_id: Alert UUID

        Returns:
            True if deleted, False if not found
        """
        result = await self.session.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = result.scalar_one_or_none()

        if alert:
            await self.session.delete(alert)
            return True

        return False

    async def get_matching_alerts(self, event: Event) -> list[Alert]:
        """Get alerts that match a given event.

        Args:
            event: Event to match against

        Returns:
            List of matching alerts
        """
        # Get all active alerts
        result = await self.session.execute(
            select(Alert).where(Alert.is_active == True)
        )
        alerts = list(result.scalars().all())

        matching = []
        for alert in alerts:
            if self._alert_matches_event(alert, event):
                matching.append(alert)

        return matching

    def _alert_matches_event(self, alert: Alert, event: Event) -> bool:
        """Check if an alert matches an event.

        Args:
            alert: Alert to check
            event: Event to match

        Returns:
            True if alert matches event
        """
        # Check ticker match
        if alert.ticker and event.ticker:
            if alert.ticker.upper() != event.ticker.upper():
                return False

        # Check event type match
        if alert.event_types and event.event_type:
            if event.event_type not in alert.event_types:
                return False

        # Check minimum alpha score
        if alert.min_alpha_score is not None and event.alpha_score is not None:
            if event.alpha_score < alert.min_alpha_score:
                return False

        # Check urgency level
        if alert.urgency_levels and event.urgency_level:
            if event.urgency_level not in alert.urgency_levels:
                return False

        # Check direction
        if alert.direction and event.direction:
            if alert.direction.lower() != event.direction.lower():
                return False

        return True
