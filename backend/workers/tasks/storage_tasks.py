"""Storage tasks for persisting events to database."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

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


@celery_app.task(bind=True, max_retries=3)
def store_event_task(self, data: dict[str, Any]) -> dict[str, Any]:
    """Store processed event to database and publish to WebSocket.

    Args:
        data: Processed event data

    Returns:
        Data with storage confirmation
    """
    async def _store():
        from backend.storage.timescale.connection import get_db_context
        from backend.storage.timescale.queries import EventQueries

        try:
            # Extract ticker - try multiple fields
            ticker = _extract_ticker(data)

            # Get headline from title or headline field
            headline = data.get("headline") or data.get("title") or ""

            # Validate - skip events without proper ticker or headline
            if ticker == "UNKNOWN":
                logger.debug("Skipping event without valid ticker")
                data["skipped"] = True
                data["skip_reason"] = "No valid ticker"
                return data

            if not headline.strip() or headline == "No headline":
                logger.debug("Skipping event without valid headline", ticker=ticker)
                data["skipped"] = True
                data["skip_reason"] = "No valid headline"
                return data

            # Extract event time from various possible fields
            event_time = _parse_datetime(
                data.get("event_time") or data.get("filing_time") or
                data.get("published_at") or data.get("created_at") or
                data.get("ingested_at")
            ) or datetime.now(timezone.utc)

            # Determine event type - map filing types to event types
            event_type = data.get("event_type") or data.get("filing_category") or "NEWS"
            if data.get("filing_type") == "4":
                event_type = "INSIDER_TRADE"
            elif data.get("filing_type") == "SC 13D":
                event_type = "ACTIVIST_STAKE"
            elif data.get("filing_type") == "SC 13G":
                event_type = "INSTITUTIONAL_FILING"

            # Prepare event data for database
            event_data = {
                "id": uuid4(),
                "ticker": ticker,
                "event_time": event_time,
                "ingest_time": datetime.now(timezone.utc),
                "event_type": event_type,
                "event_category": data.get("event_category") or "SEC_FILING",
                "headline": headline,
                "summary": data.get("summary") or data.get("description"),
                "content": data.get("content") or data.get("body"),
                "source_url": data.get("source_url") or data.get("filing_url") or data.get("link") or data.get("url"),
                "source_name": data.get("source_name") or data.get("source", "SEC EDGAR"),
                "sentiment_score": data.get("sentiment_score"),
                "sentiment_label": data.get("sentiment_label"),
                "sentiment_confidence": data.get("sentiment_confidence"),
                "alpha_score": data.get("alpha_score"),
                "direction": data.get("direction"),
                "urgency_level": data.get("urgency_level"),
                "extracted_tickers": data.get("extracted_tickers") or [ticker] if ticker != "UNKNOWN" else [],
                "extracted_companies": data.get("extracted_companies") or ([data.get("company_name")] if data.get("company_name") else []),
                "extracted_people": data.get("extracted_people") or [],
                "extracted_amounts": data.get("extracted_amounts") or [],
                "event_metadata": {
                    "alpha_factors": data.get("alpha_factors"),
                    "recommended_action": data.get("recommended_action"),
                    "processed_at": data.get("processed_at"),
                    "filing_type": data.get("filing_type"),
                    "cik": data.get("cik"),
                    "is_critical": data.get("is_critical"),
                },
            }

            # Store in database (with duplicate check)
            async with get_db_context() as session:
                from sqlalchemy import text

                # Check for duplicate
                result = await session.execute(
                    text("SELECT 1 FROM events WHERE ticker = :ticker AND headline = :headline LIMIT 1"),
                    {"ticker": ticker, "headline": headline}
                )
                if result.fetchone():
                    logger.debug("Skipping duplicate event", ticker=ticker)
                    data["skipped"] = True
                    data["skip_reason"] = "Duplicate event"
                    return data

                queries = EventQueries(session)
                event = await queries.create_event(event_data)

                logger.info(
                    "Event stored",
                    event_id=str(event.id),
                    ticker=event.ticker,
                    event_type=event.event_type,
                    alpha_score=event.alpha_score,
                )

                # Add event ID to data for downstream tasks
                data["event_id"] = str(event.id)
                data["stored_at"] = datetime.now(timezone.utc).isoformat()

            # Publish to Redis for WebSocket distribution
            await _publish_to_redis(event_data)

            return data

        except Exception as e:
            logger.error("Failed to store event", error=str(e), ticker=data.get("ticker"))
            raise

    try:
        return run_async(_store())
    except Exception as e:
        raise self.retry(exc=e, countdown=5)


def _parse_datetime(time_value) -> datetime | None:
    """Parse datetime from various formats."""
    if time_value is None:
        return None

    if isinstance(time_value, datetime):
        return time_value

    if isinstance(time_value, str):
        try:
            return datetime.fromisoformat(time_value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    return None


def _extract_ticker(data: dict[str, Any]) -> str:
    """Extract ticker symbol from event data.

    Args:
        data: Event data dictionary

    Returns:
        Ticker symbol or 'UNKNOWN'
    """
    import re

    # Direct ticker field
    if data.get("ticker"):
        return data["ticker"].upper()

    # Check extracted_tickers list
    if data.get("extracted_tickers") and len(data["extracted_tickers"]) > 0:
        return data["extracted_tickers"][0].upper()

    # Try to extract from company name using common patterns
    company_name = data.get("company_name", "")
    title = data.get("title", "")

    # Look for ticker in parentheses like "Company Name (TICK)"
    ticker_match = re.search(r'\(([A-Z]{1,5})\)', title) or re.search(r'\(([A-Z]{1,5})\)', company_name)
    if ticker_match:
        return ticker_match.group(1)

    # Look for "TICK -" pattern at the start
    ticker_match = re.search(r'^([A-Z]{1,5})\s*[-:]', title)
    if ticker_match:
        return ticker_match.group(1)

    return "UNKNOWN"


async def _publish_to_redis(event_data: dict[str, Any]) -> None:
    """Publish event to Redis pub/sub for WebSocket distribution."""
    try:
        import redis.asyncio as redis
        from backend.config import settings

        client = redis.from_url(str(settings.redis_url))

        # Prepare serializable data
        publish_data = {
            "id": str(event_data["id"]),
            "ticker": event_data["ticker"],
            "event_time": event_data["event_time"].isoformat() if event_data["event_time"] else None,
            "event_type": event_data["event_type"],
            "headline": event_data["headline"],
            "summary": event_data["summary"],
            "source_name": event_data["source_name"],
            "sentiment_score": event_data["sentiment_score"],
            "sentiment_label": event_data["sentiment_label"],
            "alpha_score": event_data["alpha_score"],
            "direction": event_data["direction"],
            "urgency_level": event_data["urgency_level"],
        }

        # Publish to channels
        await client.publish("events:all", json.dumps(publish_data))
        await client.publish(f"events:ticker:{event_data['ticker']}", json.dumps(publish_data))

        # Publish to high-alpha channel if applicable
        if event_data.get("alpha_score") and abs(event_data["alpha_score"]) >= 0.7:
            await client.publish("events:high_alpha", json.dumps(publish_data))

        await client.aclose()

        logger.debug(
            "Event published to Redis",
            ticker=event_data["ticker"],
            event_type=event_data["event_type"],
        )

    except Exception as e:
        logger.warning("Failed to publish to Redis", error=str(e))
        # Don't fail the task if Redis publish fails


@celery_app.task
def store_and_alert_task(data: dict[str, Any]) -> dict[str, Any]:
    """Store event and then check alerts.

    This is a convenience task that chains storage with alerting.

    Args:
        data: Processed event data

    Returns:
        Data with storage and alert results
    """
    from backend.workers.tasks.alerting_tasks import check_alerts_task

    # First store the event
    stored_data = store_event_task(data)

    # Then check alerts
    return check_alerts_task(stored_data)
