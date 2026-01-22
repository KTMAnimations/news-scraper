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
            except (ValueError, TypeError):
                pass

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
def recalculate_alpha(ticker: str) -> dict[str, Any]:
    """Recalculate alpha scores for all recent events of a ticker.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Results summary
    """
    # This would fetch recent events from database and recalculate
    # Placeholder for when database is implemented
    return {
        "ticker": ticker,
        "recalculated": 0,
        "status": "not_implemented",
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
        except (ValueError, TypeError):
            pass

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
