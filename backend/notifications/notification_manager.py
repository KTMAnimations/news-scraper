"""Notification manager for dispatching alerts."""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.storage.timescale.models import Alert, User, Watchlist

from .email_service import email_service

logger = structlog.get_logger(__name__)


class NotificationManager:
    """Manager for checking and dispatching notifications."""

    def __init__(self, session: AsyncSession):
        """Initialize notification manager.

        Args:
            session: Database session
        """
        self.session = session

    async def check_alerts_for_event(self, event_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Check if an event triggers any user alerts.

        Args:
            event_data: Processed event data

        Returns:
            List of triggered alerts with user info
        """
        triggered = []

        ticker = event_data.get("ticker")
        event_type = event_data.get("event_type")
        alpha_score = event_data.get("alpha_score", 0.0)
        direction = event_data.get("direction")
        urgency_level = event_data.get("urgency_level")

        # Fetch all active alerts
        result = await self.session.execute(
            select(Alert, User)
            .join(User, Alert.user_id == User.id)
            .where(
                and_(
                    Alert.is_active == True,
                    User.is_active == True,
                )
            )
        )

        for alert, user in result.all():
            if self._alert_matches_event(alert, event_data):
                triggered.append({
                    "alert_id": str(alert.id),
                    "alert_name": alert.name,
                    "user_id": str(user.id),
                    "user_email": user.email,
                    "user_name": user.full_name,
                    "delivery_method": alert.delivery_method,
                    "subscription_tier": user.subscription_tier,
                })

                # Update last triggered timestamp
                await self.session.execute(
                    update(Alert)
                    .where(Alert.id == alert.id)
                    .values(last_triggered_at=datetime.now(timezone.utc))
                )

        await self.session.commit()

        logger.info(
            "Alerts checked",
            ticker=ticker,
            event_type=event_type,
            triggered_count=len(triggered),
        )

        return triggered

    def _alert_matches_event(self, alert: Alert, event_data: dict[str, Any]) -> bool:
        """Check if an alert rule matches the event.

        Args:
            alert: Alert rule
            event_data: Event data

        Returns:
            True if alert matches
        """
        ticker = event_data.get("ticker")
        event_type = event_data.get("event_type")
        alpha_score = event_data.get("alpha_score", 0.0)
        direction = event_data.get("direction")
        urgency_level = event_data.get("urgency_level")

        # Check ticker filter
        if alert.ticker and ticker:
            if alert.ticker.upper() != ticker.upper():
                return False

        # Check event types filter
        if alert.event_types:
            if event_type not in alert.event_types:
                return False

        # Check minimum alpha score
        if alert.min_alpha_score is not None:
            if alpha_score is None or abs(alpha_score) < alert.min_alpha_score:
                return False

        # Check urgency levels filter
        if alert.urgency_levels:
            if urgency_level not in alert.urgency_levels:
                return False

        # Check direction filter
        if alert.direction:
            if direction != alert.direction:
                return False

        return True

    async def check_watchlist_alerts(self, event_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Check if event ticker is on any user's watchlist with alerts enabled.

        Args:
            event_data: Event data

        Returns:
            List of watchlist matches with user info
        """
        ticker = event_data.get("ticker")
        if not ticker:
            return []

        result = await self.session.execute(
            select(Watchlist, User)
            .join(User, Watchlist.user_id == User.id)
            .where(
                and_(
                    Watchlist.ticker == ticker.upper(),
                    Watchlist.alert_enabled == True,
                    User.is_active == True,
                )
            )
        )

        matches = []
        for watchlist, user in result.all():
            matches.append({
                "watchlist_id": str(watchlist.id),
                "user_id": str(user.id),
                "user_email": user.email,
                "user_name": user.full_name,
                "subscription_tier": user.subscription_tier,
            })

        return matches

    async def dispatch_alert(
        self,
        alert_info: dict[str, Any],
        event_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Dispatch an alert notification.

        Args:
            alert_info: Alert and user information
            event_data: Event that triggered the alert

        Returns:
            Dispatch result
        """
        delivery_method = alert_info.get("delivery_method", "email")
        user_email = alert_info.get("user_email")
        user_name = alert_info.get("user_name")

        result = {
            "alert_id": alert_info.get("alert_id"),
            "user_id": alert_info.get("user_id"),
            "email_sent": False,
            "push_sent": False,
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
        }

        ticker = event_data.get("ticker", "N/A")
        event_type = event_data.get("event_type", "NEWS")
        headline = event_data.get("headline") or event_data.get("title", "")
        alpha_score = event_data.get("alpha_score", 0.0)
        direction = event_data.get("direction", "NEUTRAL")
        urgency_level = event_data.get("urgency_level", "medium")

        # Send email notification
        if delivery_method in ("email", "both") and user_email:
            result["email_sent"] = email_service.send_alert_email(
                to_email=user_email,
                ticker=ticker,
                event_type=event_type,
                headline=headline,
                alpha_score=alpha_score,
                direction=direction,
                urgency_level=urgency_level,
            )

        # Send push notification
        if delivery_method in ("push", "both"):
            result["push_sent"] = await self._send_push_notification(
                user_id=alert_info.get("user_id"),
                ticker=ticker,
                event_type=event_type,
                headline=headline,
                direction=direction,
            )

        logger.info(
            "Alert dispatched",
            alert_id=alert_info.get("alert_id"),
            user_email=user_email,
            email_sent=result["email_sent"],
            push_sent=result["push_sent"],
        )

        return result

    async def _send_push_notification(
        self,
        user_id: str,
        ticker: str,
        event_type: str,
        headline: str,
        direction: str,
    ) -> bool:
        """Send push notification via FCM.

        Args:
            user_id: User ID
            ticker: Stock ticker
            event_type: Event type
            headline: Event headline
            direction: Signal direction

        Returns:
            True if sent successfully
        """
        if not settings.push_notifications_configured:
            logger.debug("Push notifications not configured")
            return False

        # Push notification implementation would go here
        # Using Firebase Cloud Messaging or similar service
        logger.info(
            "Push notification would be sent",
            user_id=user_id,
            ticker=ticker,
        )
        return False

    async def publish_to_websocket(self, event_data: dict[str, Any]) -> bool:
        """Publish event to WebSocket via Redis pub/sub.

        Args:
            event_data: Event data to publish

        Returns:
            True if published successfully
        """
        try:
            import redis.asyncio as redis

            redis_client = redis.from_url(str(settings.redis_url))

            # Prepare event payload
            payload = {
                "type": "event",
                "data": {
                    "id": event_data.get("id"),
                    "ticker": event_data.get("ticker"),
                    "event_type": event_data.get("event_type"),
                    "headline": event_data.get("headline") or event_data.get("title"),
                    "alpha_score": event_data.get("alpha_score"),
                    "direction": event_data.get("direction"),
                    "urgency_level": event_data.get("urgency_level"),
                    "sentiment_label": event_data.get("sentiment_label"),
                    "sentiment_score": event_data.get("sentiment_score"),
                    "event_time": event_data.get("event_time"),
                    "source": event_data.get("source"),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Publish to general channel
            await redis_client.publish("events:all", json.dumps(payload))

            # Publish to ticker-specific channel
            ticker = event_data.get("ticker")
            if ticker:
                await redis_client.publish(f"events:ticker:{ticker}", json.dumps(payload))

            # Publish high-alpha events to special channel
            alpha_score = event_data.get("alpha_score", 0)
            if abs(alpha_score) >= 0.7:
                await redis_client.publish("events:high_alpha", json.dumps(payload))

            await redis_client.aclose()

            logger.debug("Event published to WebSocket", ticker=ticker)
            return True

        except Exception as e:
            logger.error("Failed to publish to WebSocket", error=str(e))
            return False


async def process_event_notifications(
    session: AsyncSession,
    event_data: dict[str, Any],
) -> dict[str, Any]:
    """Process all notifications for an event.

    Args:
        session: Database session
        event_data: Processed event data

    Returns:
        Notification processing results
    """
    manager = NotificationManager(session)

    results = {
        "alerts_triggered": [],
        "watchlist_matches": [],
        "notifications_sent": 0,
        "websocket_published": False,
    }

    # Check alert rules
    triggered_alerts = await manager.check_alerts_for_event(event_data)
    results["alerts_triggered"] = triggered_alerts

    # Dispatch notifications for triggered alerts
    for alert_info in triggered_alerts:
        dispatch_result = await manager.dispatch_alert(alert_info, event_data)
        if dispatch_result.get("email_sent") or dispatch_result.get("push_sent"):
            results["notifications_sent"] += 1

    # Check watchlist matches (for high-importance events)
    urgency = event_data.get("urgency_level", "low")
    if urgency in ("critical", "high"):
        watchlist_matches = await manager.check_watchlist_alerts(event_data)
        results["watchlist_matches"] = watchlist_matches

        # Send watchlist notifications
        for match in watchlist_matches:
            alert_info = {
                "alert_id": match.get("watchlist_id"),
                "user_id": match.get("user_id"),
                "user_email": match.get("user_email"),
                "user_name": match.get("user_name"),
                "delivery_method": "email",
            }
            dispatch_result = await manager.dispatch_alert(alert_info, event_data)
            if dispatch_result.get("email_sent"):
                results["notifications_sent"] += 1

    # Publish to WebSocket
    results["websocket_published"] = await manager.publish_to_websocket(event_data)

    logger.info(
        "Event notifications processed",
        ticker=event_data.get("ticker"),
        alerts_triggered=len(results["alerts_triggered"]),
        notifications_sent=results["notifications_sent"],
    )

    return results
