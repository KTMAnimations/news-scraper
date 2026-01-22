"""Alpha scoring tasks."""

from datetime import datetime, timezone
from typing import Any

import structlog

from backend.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, max_retries=2)
def calculate_alpha_task(self, data: dict[str, Any]) -> dict[str, Any]:
    """Calculate alpha score for an event.

    Args:
        data: Event data with sentiment and classification

    Returns:
        Data enriched with alpha score
    """
    try:
        from backend.processing.classification import EventClassification, EventType
        from backend.processing.sentiment.finbert_service import SentimentResult
        from backend.processing.scoring import AlphaCalculator

        # Reconstruct classification
        event_type_str = data.get("event_type", "NEWS")
        try:
            event_type = EventType(event_type_str)
        except ValueError:
            event_type = EventType.NEWS

        classification = EventClassification(
            event_type=event_type,
            confidence=data.get("event_confidence", 0.5),
            matched_patterns=[],
            is_material=data.get("is_material", False),
            base_signal_weight=data.get("base_signal_weight", 0.0),
        )

        # Reconstruct sentiment
        sentiment = None
        if "sentiment_label" in data:
            sentiment = SentimentResult(
                label=data["sentiment_label"],
                score=data.get("sentiment_score", 0.0),
                confidence=data.get("sentiment_confidence", 0.5),
                probabilities=data.get("sentiment_probabilities", {}),
            )

        # Parse event time
        event_time = None
        time_str = data.get("event_time") or data.get("published_at") or data.get("created_at")
        if time_str:
            try:
                if isinstance(time_str, str):
                    event_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                elif isinstance(time_str, datetime):
                    event_time = time_str
            except (ValueError, TypeError) as e:
                logger.warning(
                    "Failed to parse event time",
                    time_str=time_str,
                    error=str(e),
                    ticker=data.get("ticker"),
                )

        # Calculate alpha
        calculator = AlphaCalculator()
        alpha = calculator.calculate(
            classification=classification,
            sentiment=sentiment,
            source=data.get("source", "unknown"),
            event_time=event_time,
            ticker=data.get("ticker"),
        )

        # Enrich data
        data["alpha_score"] = alpha.score
        data["direction"] = alpha.direction
        data["alpha_confidence"] = alpha.confidence
        data["urgency_level"] = alpha.urgency_level
        data["recommended_action"] = alpha.recommended_action
        data["alpha_factors"] = alpha.factors

        # Set processing timestamp
        data["processed_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "Alpha calculated",
            ticker=data.get("ticker"),
            alpha=alpha.score,
            direction=alpha.direction,
            urgency=alpha.urgency_level,
        )

        return data

    except Exception as e:
        logger.error("Alpha calculation failed", error=str(e))
        raise self.retry(exc=e, countdown=5)


@celery_app.task
def recalculate_alpha(ticker: str, hours: int = 168) -> dict[str, Any]:
    """Recalculate alpha scores for all recent events of a ticker.

    Args:
        ticker: Stock ticker symbol
        hours: Number of hours to look back (default 168 = 7 days)

    Returns:
        Results summary
    """
    import asyncio
    from datetime import timedelta

    from backend.storage.timescale import get_db_session, EventQueries
    from backend.processing.classification import EventClassifier, EventType
    from backend.processing.sentiment import get_sentiment_service
    from backend.processing.scoring import AlphaCalculator

    async def _recalculate():
        recalculated = 0
        errors = 0

        async for session in get_db_session():
            try:
                queries = EventQueries(session)

                # Get recent events for ticker
                cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
                events = await queries.get_events(
                    ticker=ticker.upper(),
                    start_time=cutoff,
                    limit=500,
                )

                calculator = AlphaCalculator()
                classifier = EventClassifier()
                sentiment_service = get_sentiment_service()

                for event in events:
                    try:
                        # Re-classify event
                        classification = classifier.classify(
                            headline=event.headline or "",
                            text=event.summary or "",
                            source=event.source,
                        )

                        # Re-analyze sentiment if we have text
                        sentiment = None
                        if event.summary:
                            sentiment = await sentiment_service.analyze(event.summary)

                        # Recalculate alpha
                        alpha = calculator.calculate(
                            classification=classification,
                            sentiment=sentiment,
                            source=event.source,
                            event_time=event.event_time,
                            ticker=event.ticker,
                        )

                        # Update event record
                        event.alpha_score = alpha.score
                        event.direction = alpha.direction
                        event.urgency_level = alpha.urgency_level

                        recalculated += 1

                    except Exception as e:
                        logger.warning(
                            "Failed to recalculate event",
                            event_id=str(event.id),
                            error=str(e),
                        )
                        errors += 1

                await session.commit()

            except Exception as e:
                logger.error("Recalculation failed", ticker=ticker, error=str(e))
                raise

            break  # Only need one session

        return recalculated, errors

    try:
        recalculated, errors = asyncio.run(_recalculate())

        logger.info(
            "Alpha recalculation complete",
            ticker=ticker,
            recalculated=recalculated,
            errors=errors,
        )

        return {
            "ticker": ticker,
            "recalculated": recalculated,
            "errors": errors,
            "status": "completed",
        }

    except Exception as e:
        logger.error("Recalculation task failed", ticker=ticker, error=str(e))
        return {
            "ticker": ticker,
            "recalculated": 0,
            "errors": 1,
            "status": "failed",
            "error": str(e),
        }


@celery_app.task
def score_urgency_task(data: dict[str, Any]) -> dict[str, Any]:
    """Score urgency for an event.

    Args:
        data: Event data

    Returns:
        Data enriched with urgency score
    """
    from backend.processing.classification import EventType, UrgencyScorer

    try:
        event_type = EventType(data.get("event_type", "NEWS"))
    except ValueError:
        event_type = EventType.NEWS

    # Parse event time
    event_time = None
    time_str = data.get("event_time") or data.get("published_at")
    if time_str:
        try:
            event_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except (ValueError, TypeError) as e:
            logger.warning(
                "Failed to parse event time in urgency scorer",
                time_str=time_str,
                error=str(e),
            )

    scorer = UrgencyScorer()
    urgency = scorer.score(
        event_type=event_type,
        source=data.get("source"),
        event_time=event_time,
    )

    data["urgency_score"] = urgency.score
    data["urgency_level"] = urgency.level
    data["urgency_reasons"] = urgency.reasons
    data["recommended_action"] = urgency.recommended_action

    return data


@celery_app.task
def predict_direction_task(data: dict[str, Any]) -> dict[str, Any]:
    """Predict trading direction for an event.

    Args:
        data: Event data with classification and sentiment

    Returns:
        Data enriched with direction prediction
    """
    from backend.processing.classification import (
        DirectionPredictor,
        EventClassification,
        EventType,
    )
    from backend.processing.sentiment.finbert_service import SentimentResult

    try:
        event_type = EventType(data.get("event_type", "NEWS"))
    except ValueError:
        event_type = EventType.NEWS

    classification = EventClassification(
        event_type=event_type,
        confidence=data.get("event_confidence", 0.5),
        matched_patterns=[],
        is_material=data.get("is_material", False),
        base_signal_weight=data.get("base_signal_weight", 0.0),
    )

    sentiment = None
    if "sentiment_label" in data:
        sentiment = SentimentResult(
            label=data["sentiment_label"],
            score=data.get("sentiment_score", 0.0),
            confidence=data.get("sentiment_confidence", 0.5),
            probabilities=data.get("sentiment_probabilities", {}),
        )

    predictor = DirectionPredictor()
    prediction = predictor.predict(
        classification=classification,
        sentiment=sentiment,
        source=data.get("source"),
    )

    data["direction"] = prediction.direction
    data["direction_confidence"] = prediction.confidence
    data["signal_strength"] = prediction.signal_strength
    data["direction_factors"] = prediction.factors

    return data
