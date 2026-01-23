"""Storage tasks for persisting events to database."""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

from backend.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, max_retries=3)
def store_event_task(self, data: dict[str, Any]) -> dict[str, Any]:
    """Store processed event to database and publish to WebSocket.

    Uses synchronous database operations to avoid asyncio event loop issues in Celery.

    Args:
        data: Processed event data

    Returns:
        Data with storage confirmation
    """
    from backend.storage.timescale.connection import get_sync_db_context
    from backend.storage.timescale.models import Event
    from sqlalchemy import text

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
        event_id = uuid4()
        event_data = {
            "id": event_id,
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
            "extra_data": {
                "alpha_factors": data.get("alpha_factors"),
                "recommended_action": data.get("recommended_action"),
                "processed_at": data.get("processed_at"),
                "filing_type": data.get("filing_type"),
                "cik": data.get("cik"),
                "is_critical": data.get("is_critical"),
            },
        }

        # Store in database using sync session (with duplicate check)
        with get_sync_db_context() as session:
            # Check for duplicate
            result = session.execute(
                text("SELECT 1 FROM events WHERE ticker = :ticker AND headline = :headline LIMIT 1"),
                {"ticker": ticker, "headline": headline}
            )
            if result.fetchone():
                logger.debug("Skipping duplicate event", ticker=ticker)
                data["skipped"] = True
                data["skip_reason"] = "Duplicate event"
                return data

            # Create event using ORM
            event = Event(
                id=event_data["id"],
                ticker=event_data["ticker"],
                event_time=event_data["event_time"],
                ingest_time=event_data["ingest_time"],
                event_type=event_data["event_type"],
                event_category=event_data["event_category"],
                headline=event_data["headline"],
                summary=event_data["summary"],
                content=event_data["content"],
                source_url=event_data["source_url"],
                source_name=event_data["source_name"],
                sentiment_score=event_data["sentiment_score"],
                sentiment_label=event_data["sentiment_label"],
                sentiment_confidence=event_data["sentiment_confidence"],
                alpha_score=event_data["alpha_score"],
                direction=event_data["direction"],
                urgency_level=event_data["urgency_level"],
                extracted_tickers=event_data["extracted_tickers"],
                extracted_companies=event_data["extracted_companies"],
                extracted_people=event_data["extracted_people"],
                extracted_amounts=event_data["extracted_amounts"],
                extra_data=event_data["extra_data"],
            )
            session.add(event)
            # Commit happens automatically via context manager

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

        # Publish to Redis for WebSocket distribution (sync)
        _publish_to_redis_sync(event_data)

        # Publish to Redpanda for event streaming
        _publish_to_redpanda_sync(event_data)

        return data

    except Exception as e:
        logger.error("Failed to store event", error=str(e), ticker=data.get("ticker"))
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


def _publish_to_redis_sync(event_data: dict[str, Any]) -> None:
    """Publish event to Redis pub/sub for WebSocket distribution (synchronous)."""
    try:
        import redis
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
        client.publish("events:all", json.dumps(publish_data))
        client.publish(f"events:ticker:{event_data['ticker']}", json.dumps(publish_data))

        # Publish to high-alpha channel if applicable
        if event_data.get("alpha_score") and abs(event_data["alpha_score"]) >= 0.7:
            client.publish("events:high_alpha", json.dumps(publish_data))

        client.close()

        logger.debug(
            "Event published to Redis",
            ticker=event_data["ticker"],
            event_type=event_data["event_type"],
        )

    except Exception as e:
        logger.warning("Failed to publish to Redis", error=str(e))
        # Don't fail the task if Redis publish fails


def _publish_to_redpanda_sync(event_data: dict[str, Any]) -> None:
    """Publish event to Redpanda (Kafka) for event streaming (synchronous).

    Events are published to:
    - events.all: All events
    - events.high-alpha: High alpha events (|alpha_score| >= 0.7)
    - events.ticker.{TICKER}: Per-ticker events
    """
    try:
        from backend.services.streaming import (
            TOPIC_ALL_EVENTS,
            TOPIC_HIGH_ALPHA,
            get_ticker_topic,
        )
        from backend.config import settings
        from kafka import KafkaProducer
        from kafka.errors import KafkaError

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
            "source_url": event_data.get("source_url"),
            "ingest_time": event_data["ingest_time"].isoformat() if event_data.get("ingest_time") else None,
        }

        # Create Kafka producer
        producer = KafkaProducer(
            bootstrap_servers=settings.kafka_brokers_list,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            compression_type="gzip",
        )

        ticker = event_data["ticker"]
        key = ticker.upper()

        # Publish to all events topic
        producer.send(TOPIC_ALL_EVENTS, value=publish_data, key=key)

        # Publish to ticker-specific topic
        if ticker and ticker != "UNKNOWN":
            ticker_topic = get_ticker_topic(ticker)
            producer.send(ticker_topic, value=publish_data, key=key)

        # Publish to high-alpha topic if applicable
        alpha_score = event_data.get("alpha_score")
        if alpha_score is not None:
            try:
                if abs(float(alpha_score)) >= 0.7:
                    producer.send(TOPIC_HIGH_ALPHA, value=publish_data, key=key)
            except (ValueError, TypeError):
                pass

        # Flush and close
        producer.flush(timeout=5)
        producer.close(timeout=5)

        logger.debug(
            "Event published to Redpanda",
            ticker=ticker,
            event_type=event_data["event_type"],
        )

    except KafkaError as e:
        logger.warning("Failed to publish to Redpanda (Kafka error)", error=str(e))
        # Don't fail the task if Redpanda publish fails
    except Exception as e:
        logger.warning("Failed to publish to Redpanda", error=str(e))
        # Don't fail the task if Redpanda publish fails


@celery_app.task(bind=True, max_retries=3)
def index_event_opensearch_task(self, data: dict[str, Any]) -> dict[str, Any]:
    """Index event to OpenSearch for full-text search.

    This task should be called after storing the event to the database.
    Uses the SearchService to index events.

    Args:
        data: Event data to index containing:
            - event_id: Unique event ID (required)
            - ticker: Stock ticker symbol
            - headline: Event headline
            - summary: Event summary
            - content: Full event content
            - event_type: Type of event
            - source_name: Source name
            - sentiment_label: Sentiment classification
            - alpha_score: Alpha score
            - event_time: Event timestamp

    Returns:
        Data with indexing confirmation
    """
    from backend.storage.opensearch.search_service import search_service

    try:
        # Skip if event was skipped during storage
        if data.get("skipped"):
            logger.debug("Skipping OpenSearch indexing for skipped event")
            data["opensearch_indexed"] = False
            data["opensearch_skip_reason"] = data.get("skip_reason")
            return data

        # Skip if no event_id (not stored)
        event_id = data.get("event_id") or data.get("id")
        if not event_id:
            logger.debug("Skipping OpenSearch indexing - no event ID")
            data["opensearch_indexed"] = False
            data["opensearch_skip_reason"] = "No event ID"
            return data

        # Prepare event data for indexing
        event_data = {
            "id": str(event_id),
            "ticker": data.get("ticker"),
            "headline": data.get("headline") or data.get("title"),
            "summary": data.get("summary") or data.get("description"),
            "content": data.get("content") or data.get("body"),
            "event_type": data.get("event_type"),
            "source_name": data.get("source_name") or data.get("source"),
            "sentiment_label": data.get("sentiment_label"),
            "alpha_score": data.get("alpha_score"),
            "event_time": data.get("event_time") or data.get("filing_time"),
        }

        # Ensure index exists
        search_service.ensure_index()

        # Index the event
        success = search_service.index_event(event_data)

        data["opensearch_indexed"] = success
        data["opensearch_indexed_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "Event indexed to OpenSearch",
            event_id=event_id,
            ticker=data.get("ticker"),
            success=success,
        )

        return data

    except Exception as e:
        logger.error(
            "Failed to index event to OpenSearch",
            error=str(e),
            event_id=data.get("event_id"),
        )
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=5 * (self.request.retries + 1))


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


@celery_app.task
def store_and_index_task(data: dict[str, Any]) -> dict[str, Any]:
    """Store event to database and index to OpenSearch.

    This is a convenience task that chains storage with OpenSearch indexing.

    Args:
        data: Processed event data

    Returns:
        Data with storage and indexing results
    """
    # First store the event
    stored_data = store_event_task(data)

    # Then index to OpenSearch
    return index_event_opensearch_task(stored_data)


@celery_app.task
def store_index_and_alert_task(data: dict[str, Any]) -> dict[str, Any]:
    """Store event, index to OpenSearch, and check alerts.

    This is the complete pipeline task for event processing.

    Args:
        data: Processed event data

    Returns:
        Data with storage, indexing, and alert results
    """
    from backend.workers.tasks.alerting_tasks import check_alerts_task

    # Store the event
    stored_data = store_event_task(data)

    # Index to OpenSearch
    indexed_data = index_event_opensearch_task(stored_data)

    # Check alerts
    return check_alerts_task(indexed_data)
