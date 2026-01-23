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
    """Dispatch an alert to users via email and/or push notification.

    Args:
        alert: Alert info including user details and delivery method
        event_data: Event data that triggered the alert

    Returns:
        Dispatch result with email_sent and push_sent status
    """
    from backend.notifications.email_service import email_service

    result = {"email_sent": False, "push_sent": False}
    delivery = alert.get("delivery_method", "email")
    user_email = alert.get("user_email")
    user_id = alert.get("user_id")

    # Extract event details
    ticker = event_data.get("ticker", "N/A")
    headline = event_data.get("headline", "New event")
    event_type = event_data.get("event_type", "EVENT")
    direction = event_data.get("direction", "")
    alpha_score = event_data.get("alpha_score")
    urgency = event_data.get("urgency_level", "medium")

    # Send email notification
    if delivery in ("email", "both") and user_email:
        subject = f"[{ticker}] {event_type}: {headline[:50]}"
        html_body = f"""
        <h2>{headline}</h2>
        <p><strong>Ticker:</strong> {ticker}</p>
        <p><strong>Type:</strong> {event_type}</p>
        <p><strong>Direction:</strong> {direction}</p>
        <p><strong>Alpha Score:</strong> {alpha_score if alpha_score else 'N/A'}</p>
        <p><a href="{settings.app_url}/dashboard/ticker/{ticker}">View Details</a></p>
        """

        result["email_sent"] = email_service.send_email(
            to_email=user_email,
            subject=subject,
            html_body=html_body,
        )

    # Send push notification
    if delivery in ("push", "both") and user_id:
        # Format notification title based on direction
        direction_emoji = ""
        if direction == "BULLISH":
            direction_emoji = "+"
        elif direction == "BEARISH":
            direction_emoji = "-"

        push_title = f"{ticker} {direction_emoji} {event_type}"
        push_body = headline[:200]  # Truncate for push notification

        # Build data payload for the notification
        push_data = {
            "type": "alert",
            "eventId": event_data.get("id", ""),
            "ticker": ticker,
            "alertId": alert.get("alert_id", ""),
            "eventType": event_type,
            "direction": direction,
            "alphaScore": str(alpha_score) if alpha_score else "",
            "urgency": urgency,
            "url": f"/dashboard/ticker/{ticker}",
        }

        # Queue push notification task
        send_push_notification_task.delay(
            user_id=user_id,
            title=push_title,
            body=push_body,
            data=push_data,
        )
        result["push_sent"] = True  # Task queued (actual delivery async)

    logger.info(
        "Alert dispatched",
        alert_id=alert.get("alert_id"),
        user_id=user_id,
        delivery_method=delivery,
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
    """Send email alert to user (legacy - use send_email_alert_task instead).

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


@celery_app.task(bind=True, max_retries=3)
def send_email_alert_task(
    self,
    user_email: str,
    event_data: dict[str, Any],
    user_name: str | None = None,
) -> dict[str, Any]:
    """Send email alert notification for an event.

    This task sends a professional HTML email alert with event details including
    ticker, headline, sentiment, alpha score, and other relevant information.
    Includes plain text fallback for email clients that don't support HTML.

    Args:
        user_email: Recipient email address
        event_data: Event data dictionary containing:
            - ticker: Stock ticker symbol
            - headline: Event headline
            - event_type: Type of event (e.g., "INSIDER_TRADE")
            - sentiment_label: Sentiment classification
            - alpha_score: Calculated alpha score
            - direction: Signal direction (BULLISH/BEARISH/NEUTRAL)
            - urgency_level: Urgency level (critical/high/medium/low)
            - id or event_id: Event ID for deep linking
            - source_name: Source of the event
            - event_time: Time of the event
        user_name: Optional user name for personalization

    Returns:
        Dict with send result including:
            - sent: Boolean indicating success
            - to: Recipient email
            - subject: Email subject used
            - sent_at: Timestamp of send attempt
            - error: Error message if failed

    Raises:
        Retries up to 3 times on transient failures with exponential backoff.
    """
    from backend.notifications.email_service import email_service
    from backend.notifications.email_templates import (
        render_alert_email_html,
        render_alert_email_text,
        render_alert_subject,
    )

    try:
        # Extract event details
        ticker = event_data.get("ticker", "UNKNOWN")
        headline = event_data.get("headline") or event_data.get("title", "No headline available")
        event_type = event_data.get("event_type", "EVENT")
        sentiment_label = event_data.get("sentiment_label")
        alpha_score = event_data.get("alpha_score", 0.0)
        direction = event_data.get("direction", "NEUTRAL")
        urgency_level = event_data.get("urgency_level", "low")
        event_id = event_data.get("id") or event_data.get("event_id")
        source_name = event_data.get("source_name") or event_data.get("source")

        # Parse event time
        event_time = None
        raw_time = event_data.get("event_time") or event_data.get("filing_time")
        if raw_time:
            if isinstance(raw_time, datetime):
                event_time = raw_time
            elif isinstance(raw_time, str):
                try:
                    event_time = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

        # Generate email content using templates
        subject = render_alert_subject(
            ticker=ticker,
            event_type=event_type,
            direction=direction,
            urgency_level=urgency_level,
        )

        html_body = render_alert_email_html(
            ticker=ticker,
            headline=headline,
            event_type=event_type,
            sentiment_label=sentiment_label,
            alpha_score=alpha_score,
            direction=direction,
            urgency_level=urgency_level,
            event_id=str(event_id) if event_id else None,
            source_name=source_name,
            event_time=event_time,
        )

        text_body = render_alert_email_text(
            ticker=ticker,
            headline=headline,
            event_type=event_type,
            sentiment_label=sentiment_label,
            alpha_score=alpha_score,
            direction=direction,
            urgency_level=urgency_level,
            event_id=str(event_id) if event_id else None,
            source_name=source_name,
            event_time=event_time,
        )

        # Send the email
        sent = email_service.send_email(
            to_email=user_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

        logger.info(
            "Email alert task completed",
            to=user_email,
            ticker=ticker,
            event_type=event_type,
            direction=direction,
            sent=sent,
        )

        return {
            "sent": sent,
            "to": user_email,
            "subject": subject,
            "ticker": ticker,
            "event_type": event_type,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(
            "Failed to send email alert",
            to=user_email,
            ticker=event_data.get("ticker"),
            error=str(e),
            retry_count=self.request.retries,
        )
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=10 * (self.request.retries + 1))


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_push_notification_task(
    self,
    user_id: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    image: str | None = None,
) -> dict[str, Any]:
    """Send push notification to user via Firebase Cloud Messaging.

    This task sends push notifications to all registered FCM tokens for a user.
    It handles token validation, batch sending, and automatic cleanup of
    invalid tokens.

    Args:
        user_id: User ID (UUID as string)
        title: Notification title (max 100 chars recommended)
        body: Notification body (max 1000 chars recommended)
        data: Additional data payload (will be delivered as-is to the client)
        image: Optional image URL for the notification

    Returns:
        Send result with success/failure counts

    Notification payload structure:
        {
            "notification": {
                "title": "Event Alert",
                "body": "AAPL: New SEC filing detected",
                "image": "https://..."
            },
            "data": {
                "type": "event|alert|digest|system",
                "eventId": "uuid",
                "ticker": "AAPL",
                "alertId": "uuid",
                "url": "/dashboard/ticker/AAPL",
                "urgency": "critical|high|medium|low"
            }
        }
    """
    import httpx
    from backend.storage.timescale.connection import get_sync_db_context
    from backend.storage.timescale.models import User
    from sqlalchemy import select

    logger.info(
        "Sending push notification",
        user_id=user_id,
        title=title,
    )

    # Check if FCM is configured
    if not settings.push_notifications_configured:
        logger.warning("Push notifications not configured - skipping")
        return {
            "sent": False,
            "reason": "FCM not configured",
            "user_id": user_id,
        }

    try:
        # Get user FCM tokens
        with get_sync_db_context() as session:
            result = session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                return {
                    "sent": False,
                    "reason": "User not found",
                    "user_id": user_id,
                }

            if not user.fcm_tokens:
                return {
                    "sent": False,
                    "reason": "No FCM tokens registered",
                    "user_id": user_id,
                }

            # Extract tokens from stored format
            tokens = []
            for token_entry in user.fcm_tokens:
                if isinstance(token_entry, dict):
                    tokens.append(token_entry.get("token"))
                elif isinstance(token_entry, str):
                    tokens.append(token_entry)

            tokens = [t for t in tokens if t]  # Filter out None/empty

            if not tokens:
                return {
                    "sent": False,
                    "reason": "No valid FCM tokens",
                    "user_id": user_id,
                }

        # Build FCM message payload
        notification_payload = {
            "title": title[:100],  # FCM has limits
            "body": body[:1000],
        }
        if image:
            notification_payload["image"] = image

        data_payload = data or {}
        # Ensure all data values are strings (FCM requirement)
        data_payload = {k: str(v) if v is not None else "" for k, v in data_payload.items()}

        # Send to each token
        success_count = 0
        failure_count = 0
        invalid_tokens = []

        # Use FCM HTTP v1 API
        fcm_url = f"https://fcm.googleapis.com/v1/projects/{settings.fcm_project_id}/messages:send"

        # Get access token for FCM
        # Note: In production, use service account authentication
        # For simplicity, we're using the legacy server key approach
        headers = {
            "Authorization": f"key={settings.fcm_server_key}",
            "Content-Type": "application/json",
        }

        # Use legacy HTTP protocol for simplicity
        legacy_fcm_url = "https://fcm.googleapis.com/fcm/send"

        with httpx.Client(timeout=30.0) as client:
            for token in tokens:
                try:
                    message = {
                        "to": token,
                        "notification": notification_payload,
                        "data": data_payload,
                        # Android-specific options
                        "android": {
                            "priority": "high",
                            "notification": {
                                "click_action": "OPEN_APP",
                                "channel_id": "alerts",
                            },
                        },
                        # Web push options
                        "webpush": {
                            "headers": {
                                "Urgency": "high",
                            },
                            "notification": {
                                "icon": "/icons/notification-icon.png",
                                "badge": "/icons/badge-icon.png",
                                "requireInteraction": data_payload.get("urgency") in ("critical", "high"),
                            },
                            "fcm_options": {
                                "link": data_payload.get("url", "/dashboard"),
                            },
                        },
                    }

                    response = client.post(
                        legacy_fcm_url,
                        json=message,
                        headers=headers,
                    )

                    if response.status_code == 200:
                        response_data = response.json()
                        if response_data.get("success", 0) > 0:
                            success_count += 1
                        else:
                            failure_count += 1
                            # Check for invalid token errors
                            results = response_data.get("results", [])
                            if results and results[0].get("error") in (
                                "NotRegistered",
                                "InvalidRegistration",
                            ):
                                invalid_tokens.append(token)
                    else:
                        logger.warning(
                            "FCM request failed",
                            status_code=response.status_code,
                            response=response.text[:200],
                        )
                        failure_count += 1

                except Exception as e:
                    logger.warning(
                        "Failed to send to FCM token",
                        error=str(e),
                    )
                    failure_count += 1

        # Clean up invalid tokens
        if invalid_tokens:
            cleanup_invalid_fcm_tokens.delay(user_id, invalid_tokens)

        result = {
            "sent": success_count > 0,
            "user_id": user_id,
            "title": title,
            "success_count": success_count,
            "failure_count": failure_count,
            "total_tokens": len(tokens),
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            "Push notification result",
            **result,
        )

        return result

    except Exception as e:
        logger.error("Push notification failed", error=str(e), user_id=user_id)
        # Retry on transient errors
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            pass
        return {
            "sent": False,
            "error": str(e),
            "user_id": user_id,
        }


@celery_app.task
def cleanup_invalid_fcm_tokens(user_id: str, invalid_tokens: list[str]) -> dict[str, Any]:
    """Remove invalid FCM tokens from user's registered tokens.

    Args:
        user_id: User ID
        invalid_tokens: List of tokens to remove

    Returns:
        Cleanup result
    """
    from backend.storage.timescale.connection import get_sync_db_context
    from backend.storage.timescale.models import User
    from sqlalchemy import select

    try:
        with get_sync_db_context() as session:
            result = session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user or not user.fcm_tokens:
                return {"cleaned": 0, "user_id": user_id}

            # Filter out invalid tokens
            original_count = len(user.fcm_tokens)
            new_tokens = []

            for token_entry in user.fcm_tokens:
                if isinstance(token_entry, dict):
                    if token_entry.get("token") not in invalid_tokens:
                        new_tokens.append(token_entry)
                elif isinstance(token_entry, str):
                    if token_entry not in invalid_tokens:
                        new_tokens.append(token_entry)

            user.fcm_tokens = new_tokens
            session.commit()

            cleaned = original_count - len(new_tokens)

            logger.info(
                "Cleaned invalid FCM tokens",
                user_id=user_id,
                cleaned=cleaned,
                remaining=len(new_tokens),
            )

            return {
                "cleaned": cleaned,
                "remaining": len(new_tokens),
                "user_id": user_id,
            }

    except Exception as e:
        logger.error("Failed to cleanup FCM tokens", error=str(e), user_id=user_id)
        return {"cleaned": 0, "error": str(e), "user_id": user_id}


@celery_app.task
def send_bulk_push_notifications(
    user_ids: list[str],
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send push notifications to multiple users.

    This task dispatches individual notification tasks for each user,
    allowing for parallel processing and better error isolation.

    Args:
        user_ids: List of user IDs
        title: Notification title
        body: Notification body
        data: Additional data payload

    Returns:
        Dispatch result
    """
    dispatched = 0
    for user_id in user_ids:
        send_push_notification_task.delay(
            user_id=user_id,
            title=title,
            body=body,
            data=data,
        )
        dispatched += 1

    logger.info(
        "Bulk push notifications dispatched",
        dispatched=dispatched,
        title=title,
    )

    return {
        "dispatched": dispatched,
        "dispatched_at": datetime.now(timezone.utc).isoformat(),
    }


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
