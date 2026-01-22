"""Alerting tasks for notifications."""

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog

from backend.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task
def check_alerts_task(data: dict[str, Any]) -> dict[str, Any]:
    """Check if event triggers any user alerts.

    Args:
        data: Processed event data

    Returns:
        Data with alert check results
    """
    async def _check_alerts():
        from backend.notifications import NotificationManager
        from backend.storage.timescale.connection import get_db_context

        async with get_db_context() as session:
            manager = NotificationManager(session)

            # Check alert rules
            triggered_alerts = await manager.check_alerts_for_event(data)

            # Dispatch notifications for triggered alerts
            notifications_sent = 0
            for alert_info in triggered_alerts:
                dispatch_result = await manager.dispatch_alert(alert_info, data)
                if dispatch_result.get("email_sent") or dispatch_result.get("push_sent"):
                    notifications_sent += 1

            # Check watchlist matches for high-importance events
            urgency = data.get("urgency_level", "low")
            watchlist_matches = []
            if urgency in ("critical", "high"):
                watchlist_matches = await manager.check_watchlist_alerts(data)
                for match in watchlist_matches:
                    alert_info = {
                        "alert_id": match.get("watchlist_id"),
                        "user_id": match.get("user_id"),
                        "user_email": match.get("user_email"),
                        "user_name": match.get("user_name"),
                        "delivery_method": "email",
                    }
                    dispatch_result = await manager.dispatch_alert(alert_info, data)
                    if dispatch_result.get("email_sent"):
                        notifications_sent += 1

            return {
                "alerts_triggered": len(triggered_alerts),
                "watchlist_matches": len(watchlist_matches),
                "notifications_sent": notifications_sent,
            }

    result = run_async(_check_alerts())

    data["alerts_triggered"] = result.get("alerts_triggered", 0)
    data["watchlist_matches"] = result.get("watchlist_matches", 0)
    data["notifications_sent"] = result.get("notifications_sent", 0)
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
    async def _dispatch():
        from backend.notifications import NotificationManager
        from backend.storage.timescale.connection import get_db_context

        async with get_db_context() as session:
            manager = NotificationManager(session)
            return await manager.dispatch_alert(alert, event_data)

    result = run_async(_dispatch())

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
    async def _publish():
        from backend.notifications.notification_manager import NotificationManager
        from backend.storage.timescale.connection import get_db_context

        async with get_db_context() as session:
            manager = NotificationManager(session)
            published = await manager.publish_to_websocket(data)
            return published

    published = run_async(_publish())

    logger.debug(
        "WebSocket publish",
        ticker=data.get("ticker"),
        event_type=data.get("event_type"),
        published=published,
    )

    return {
        "published": published,
        "ticker": data.get("ticker"),
        "event_type": data.get("event_type"),
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
    logger.info(
        "Sending push notification",
        user_id=user_id,
        title=title,
    )

    # This would use push service (Firebase, OneSignal, etc.)
    # Placeholder implementation

    return {
        "sent": True,
        "user_id": user_id,
        "title": title,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task
def aggregate_daily_digest() -> dict[str, Any]:
    """Generate and send daily digests to all users with digest enabled.

    Returns:
        Digest generation result
    """
    from datetime import timedelta

    async def _generate_digests():
        from backend.storage.timescale import get_db_session, EventQueries, WatchlistQueries
        from backend.storage.timescale.models import User
        from backend.notifications.email_service import email_service
        from sqlalchemy import select

        digests_sent = 0
        errors = 0

        async for session in get_db_session():
            try:
                # Get all active users
                result = await session.execute(
                    select(User).where(User.is_active == True)
                )
                users = result.scalars().all()

                event_queries = EventQueries(session)
                watchlist_queries = WatchlistQueries(session)

                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

                for user in users:
                    try:
                        # Get user's watchlist
                        watchlist = await watchlist_queries.get_user_watchlist(user.id)
                        tickers = [w.ticker for w in watchlist]

                        if not tickers:
                            continue

                        # Get events for watchlist tickers from last 24 hours
                        all_events = []
                        for ticker in tickers:
                            events = await event_queries.get_events(
                                ticker=ticker,
                                start_time=cutoff,
                                limit=50,
                            )
                            all_events.extend(events)

                        if not all_events:
                            continue

                        # Sort by alpha score
                        all_events.sort(
                            key=lambda e: e.alpha_score or 0,
                            reverse=True,
                        )

                        # Send digest email
                        sent = await email_service.send_daily_digest(
                            to_email=user.email,
                            user_name=user.full_name or user.email,
                            events=all_events[:20],  # Top 20 events
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

            break

        return digests_sent, errors

    digests_sent, errors = run_async(_generate_digests())

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
    from datetime import timedelta

    async def _cleanup():
        from backend.storage.timescale import get_db_session
        from backend.storage.timescale.models import Event
        from sqlalchemy import delete

        deleted_count = 0

        async for session in get_db_session():
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)

                # Delete old events (TimescaleDB retention policy handles this too)
                result = await session.execute(
                    delete(Event).where(Event.event_time < cutoff)
                )
                deleted_count = result.rowcount

                await session.commit()

                logger.info(
                    "Cleaned up old events",
                    deleted=deleted_count,
                    cutoff=cutoff.isoformat(),
                )

            except Exception as e:
                logger.error("Cleanup failed", error=str(e))
                raise

            break

        return deleted_count

    deleted_count = run_async(_cleanup())

    return {
        "cleaned_at": datetime.now(timezone.utc).isoformat(),
        "records_deleted": deleted_count,
        "days_threshold": days,
    }
