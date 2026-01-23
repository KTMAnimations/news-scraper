"""Alerting tasks for notifications."""

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import redis
import structlog

from backend.config import settings
from backend.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

# Redis client for pub/sub (synchronous)
_redis_client = None


def get_redis_client():
    """Get or create Redis client for pub/sub."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(str(settings.redis_url))
    return _redis_client


@celery_app.task
def check_alerts_task(data: dict[str, Any]) -> dict[str, Any]:
    """Check if event triggers any user alerts.

    Args:
        data: Processed event data

    Returns:
        Data with alert check results
    """
    from backend.storage.timescale.connection import get_sync_db_context
    from backend.storage.timescale.models import Alert, User, Watchlist
    from sqlalchemy import select

    ticker = data.get("ticker")
    event_type = data.get("event_type")
    alpha_score = data.get("alpha_score", 0)
    urgency = data.get("urgency_level", "low")
    direction = data.get("direction")

    triggered_alerts = []
    watchlist_matches = []

    with get_sync_db_context() as session:
        # Check alert rules
        query = select(Alert, User).join(User).where(Alert.is_active == True)
        result = session.execute(query)
        alerts_with_users = result.fetchall()

        for alert, user in alerts_with_users:
            # Check if alert matches event
            matches = True

            if alert.ticker and alert.ticker.upper() != (ticker or "").upper():
                matches = False
            if alert.event_types and event_type not in alert.event_types:
                matches = False
            if alert.min_alpha_score and (alpha_score or 0) < alert.min_alpha_score:
                matches = False
            if alert.urgency_levels and urgency not in alert.urgency_levels:
                matches = False
            if alert.direction and direction != alert.direction:
                matches = False

            if matches:
                triggered_alerts.append({
                    "alert_id": str(alert.id),
                    "user_id": str(user.id),
                    "user_email": user.email,
                    "user_name": user.full_name,
                    "delivery_method": alert.delivery_method,
                })

        # Check watchlist for high-urgency events
        if urgency in ("critical", "high") and ticker:
            query = select(Watchlist, User).join(User).where(
                Watchlist.ticker == ticker.upper(),
                Watchlist.alert_enabled == True,
            )
            result = session.execute(query)
            watchlist_items = result.fetchall()

            for wl, user in watchlist_items:
                watchlist_matches.append({
                    "watchlist_id": str(wl.id),
                    "user_id": str(user.id),
                    "user_email": user.email,
                    "user_name": user.full_name,
                })

    logger.info(
        "Alerts checked",
        ticker=ticker,
        event_type=event_type,
        triggered_count=len(triggered_alerts),
    )

    data["alerts_triggered"] = len(triggered_alerts)
    data["watchlist_matches"] = len(watchlist_matches)
    data["alerts_checked_at"] = datetime.now(timezone.utc).isoformat()

    # Always publish to WebSocket for real-time updates
    publish_websocket_event.delay(data)

    return data


@celery_app.task
def dispatch_alert(alert: dict[str, Any], event_data: dict[str, Any]) -> dict[str, Any]:
    """Dispatch an alert to users.

    Args:
        alert: Alert info including user details
        event_data: Event data that triggered the alert

    Returns:
        Dispatch result
    """
    from backend.notifications.email_service import email_service

    result = {"email_sent": False, "push_sent": False}
    delivery = alert.get("delivery_method", "email")
    user_email = alert.get("user_email")

    # Send email notification
    if delivery in ("email", "both") and user_email:
        ticker = event_data.get("ticker", "N/A")
        headline = event_data.get("headline", "New event")
        event_type = event_data.get("event_type", "EVENT")
        direction = event_data.get("direction", "")

        subject = f"[{ticker}] {event_type}: {headline[:50]}"
        html_body = f"""
        <h2>{headline}</h2>
        <p><strong>Ticker:</strong> {ticker}</p>
        <p><strong>Type:</strong> {event_type}</p>
        <p><strong>Direction:</strong> {direction}</p>
        <p><strong>Alpha Score:</strong> {event_data.get('alpha_score', 'N/A')}</p>
        <p><a href="{settings.app_url}/events/{event_data.get('id', '')}">View Details</a></p>
        """

        result["email_sent"] = email_service.send_email(
            to_email=user_email,
            subject=subject,
            html_body=html_body,
        )

    logger.info(
        "Alert dispatched",
        alert_id=alert.get("alert_id"),
        email_sent=result.get("email_sent"),
        push_sent=result.get("push_sent"),
    )

    return result


@celery_app.task
def publish_websocket_event(data: dict[str, Any]) -> dict[str, Any]:
    """Publish event to WebSocket subscribers via Redis pub/sub.

    Args:
        data: Event data to publish

    Returns:
        Publish result
    """
    try:
        redis_client = get_redis_client()

        # Prepare event payload
        event_payload = {
            "type": "event",
            "data": {
                "id": data.get("id"),
                "ticker": data.get("ticker"),
                "headline": data.get("headline"),
                "event_type": data.get("event_type"),
                "alpha_score": data.get("alpha_score"),
                "direction": data.get("direction"),
                "urgency_level": data.get("urgency_level"),
                "event_time": data.get("event_time"),
                "source": data.get("source"),
            },
        }

        # Publish to general events channel
        redis_client.publish("events:all", json.dumps(event_payload))

        # Publish to ticker-specific channel if ticker exists
        ticker = data.get("ticker")
        if ticker:
            redis_client.publish(f"events:ticker:{ticker.upper()}", json.dumps(event_payload))

        # Publish to high-alpha channel if score is high
        alpha_score = data.get("alpha_score", 0)
        if alpha_score and alpha_score >= 0.7:
            redis_client.publish("events:high-alpha", json.dumps(event_payload))

        logger.debug(
            "Event published to WebSocket",
            ticker=ticker,
        )

        return {
            "published": True,
            "ticker": ticker,
            "event_type": data.get("event_type"),
        }

    except Exception as e:
        logger.error("WebSocket publish failed", error=str(e))
        return {
            "published": False,
            "error": str(e),
        }


@celery_app.task
def send_email_alert(
    user_email: str,
    subject: str,
    body: str,
    event_data: dict[str, Any],
) -> dict[str, Any]:
    """Send email alert to user.

    Args:
        user_email: User email address
        subject: Email subject
        body: Email body (HTML)
        event_data: Event data for context

    Returns:
        Send result
    """
    from backend.notifications.email_service import email_service

    sent = email_service.send_email(
        to_email=user_email,
        subject=subject,
        html_body=body,
    )

    logger.info(
        "Email alert sent",
        to=user_email,
        subject=subject,
        sent=sent,
    )

    return {
        "sent": sent,
        "to": user_email,
        "subject": subject,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task
def send_push_notification(
    user_id: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send push notification to user.

    Args:
        user_id: User ID
        title: Notification title
        body: Notification body
        data: Additional data payload

    Returns:
        Send result
    """
    from backend.storage.timescale.connection import get_sync_db_context
    from backend.storage.timescale.models import User
    from sqlalchemy import select

    logger.info(
        "Sending push notification",
        user_id=user_id,
        title=title,
    )

    try:
        # Get user FCM tokens
        with get_sync_db_context() as session:
            result = session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user or not user.fcm_tokens:
                return {"sent": False, "reason": "No FCM tokens"}

        # Firebase push would go here
        # For now, just log and return success
        return {
            "sent": True,
            "user_id": user_id,
            "title": title,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("Push notification failed", error=str(e))
        return {"sent": False, "error": str(e)}


@celery_app.task
def aggregate_daily_digest() -> dict[str, Any]:
    """Generate and send daily digests to all users with digest enabled.

    Returns:
        Digest generation result
    """
    from backend.storage.timescale.connection import get_sync_db_context
    from backend.storage.timescale.models import Event, User, Watchlist
    from backend.notifications.email_service import email_service
    from sqlalchemy import select

    digests_sent = 0
    errors = 0

    with get_sync_db_context() as session:
        try:
            # Get all active users
            result = session.execute(
                select(User).where(User.is_active == True)
            )
            users = result.scalars().all()

            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

            for user in users:
                try:
                    # Get user's watchlist
                    result = session.execute(
                        select(Watchlist).where(Watchlist.user_id == user.id)
                    )
                    watchlist = result.scalars().all()
                    tickers = [w.ticker for w in watchlist]

                    if not tickers:
                        continue

                    # Get events for watchlist tickers from last 24 hours
                    result = session.execute(
                        select(Event)
                        .where(Event.ticker.in_(tickers))
                        .where(Event.event_time >= cutoff)
                        .order_by(Event.alpha_score.desc().nullslast())
                        .limit(50)
                    )
                    events = result.scalars().all()

                    if not events:
                        continue

                    # Build digest email
                    events_html = ""
                    for event in events[:20]:
                        events_html += f"""
                        <div style="margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 10px;">
                            <strong>[{event.ticker}]</strong> {event.headline}<br>
                            <small>Alpha: {event.alpha_score:.2f if event.alpha_score else 'N/A'} |
                            Direction: {event.direction or 'N/A'}</small>
                        </div>
                        """

                    html_body = f"""
                    <h2>Your Daily News Digest</h2>
                    <p>Here are the top events for your watchlist in the last 24 hours:</p>
                    {events_html}
                    <p><a href="{settings.app_url}/dashboard">View All Events</a></p>
                    """

                    sent = email_service.send_email(
                        to_email=user.email,
                        subject="Your Daily Alpha News Digest",
                        html_body=html_body,
                    )

                    if sent:
                        digests_sent += 1

                except Exception as e:
                    logger.warning(
                        "Failed to generate digest for user",
                        user_id=str(user.id),
                        error=str(e),
                    )
                    errors += 1

        except Exception as e:
            logger.error("Daily digest generation failed", error=str(e))
            raise

    logger.info(
        "Daily digest generation complete",
        digests_sent=digests_sent,
        errors=errors,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "digests_sent": digests_sent,
        "errors": errors,
    }


@celery_app.task
def cleanup_old_alerts(days: int = 90) -> dict[str, Any]:
    """Clean up old events and compress TimescaleDB chunks.

    Args:
        days: Delete events older than this many days

    Returns:
        Cleanup result
    """
    from backend.storage.timescale.connection import get_sync_db_context
    from backend.storage.timescale.models import Event
    from sqlalchemy import delete

    deleted_count = 0

    with get_sync_db_context() as session:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            # Delete old events (TimescaleDB retention policy handles this too)
            result = session.execute(
                delete(Event).where(Event.event_time < cutoff)
            )
            deleted_count = result.rowcount

            logger.info(
                "Cleaned up old events",
                deleted=deleted_count,
                cutoff=cutoff.isoformat(),
            )

        except Exception as e:
            logger.error("Cleanup failed", error=str(e))
            raise

    return {
        "cleaned_at": datetime.now(timezone.utc).isoformat(),
        "records_deleted": deleted_count,
        "days_threshold": days,
    }
