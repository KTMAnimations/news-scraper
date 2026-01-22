"""Predict trading direction from events."""

from dataclasses import dataclass
from typing import Any

import structlog

from .event_classifier import EventClassification, EventType
from backend.processing.sentiment.finbert_service import SentimentResult

logger = structlog.get_logger(__name__)


@dataclass
class DirectionPrediction:
    """Trading direction prediction."""

    direction: str  # "BULLISH", "BEARISH", "NEUTRAL"
    confidence: float  # 0-1 confidence
    signal_strength: float  # -1 to 1 scale
    factors: list[dict[str, Any]]


class DirectionPredictor:
    """Predict trading direction from event classification and sentiment."""

    # Weights for different signal components
    WEIGHTS = {
        "event_type": 0.35,
        "sentiment": 0.25,
        "source_reliability": 0.15,
        "recency": 0.15,
        "market_context": 0.10,
    }

    # Source reliability scores
    SOURCE_RELIABILITY = {
        "sec_edgar": 1.0,
        "sec": 1.0,
        "newswire": 0.95,
        "prnewswire": 0.95,
        "businesswire": 0.95,
        "globenewswire": 0.9,
        "otc_markets": 0.85,
        "twitter": 0.7,
        "stocktwits": 0.7,
        "reddit": 0.65,
    }

    def __init__(self):
        """Initialize direction predictor."""
        pass

    def predict(
        self,
        classification: EventClassification,
        sentiment: SentimentResult | None = None,
        source: str | None = None,
        recency_score: float = 1.0,  # 0-1, 1 = fresh
    ) -> DirectionPrediction:
        """Predict trading direction.

        Args:
            classification: Event classification result
            sentiment: Optional sentiment analysis result
            source: Information source
            recency_score: How fresh the information is (0-1)

        Returns:
            DirectionPrediction
        """
        factors = []

        # Event type signal
        event_signal = classification.base_signal_weight
        event_confidence = classification.confidence

        factors.append({
            "factor": "event_type",
            "signal": event_signal,
            "confidence": event_confidence,
            "weight": self.WEIGHTS["event_type"],
            "detail": f"{classification.event_type.value}",
        })

        # Sentiment signal
        sentiment_signal = 0.0
        sentiment_confidence = 0.5

        if sentiment:
            sentiment_signal = sentiment.score
            sentiment_confidence = sentiment.confidence

            factors.append({
                "factor": "sentiment",
                "signal": sentiment_signal,
                "confidence": sentiment_confidence,
                "weight": self.WEIGHTS["sentiment"],
                "detail": f"{sentiment.label} ({sentiment.confidence:.2f})",
            })

        # Source reliability
        source_reliability = self.SOURCE_RELIABILITY.get(
            (source or "").lower(),
            0.75,
        )

        factors.append({
            "factor": "source_reliability",
            "signal": 0.0,  # Doesn't affect direction, only confidence
            "confidence": source_reliability,
            "weight": self.WEIGHTS["source_reliability"],
            "detail": f"{source or 'unknown'} ({source_reliability:.2f})",
        })

        # Recency factor
        factors.append({
            "factor": "recency",
            "signal": 0.0,  # Doesn't affect direction
            "confidence": recency_score,
            "weight": self.WEIGHTS["recency"],
            "detail": f"Recency: {recency_score:.2f}",
        })

        # Calculate weighted signal
        weighted_signal = (
            event_signal * self.WEIGHTS["event_type"] * event_confidence +
            sentiment_signal * self.WEIGHTS["sentiment"] * sentiment_confidence
        )

        # Normalize by weights that affect direction
        direction_weights = (
            self.WEIGHTS["event_type"] * event_confidence +
            self.WEIGHTS["sentiment"] * sentiment_confidence
        )

        if direction_weights > 0:
            normalized_signal = weighted_signal / direction_weights
        else:
            normalized_signal = 0.0

        # Calculate overall confidence
        overall_confidence = (
            event_confidence * self.WEIGHTS["event_type"] +
            sentiment_confidence * self.WEIGHTS["sentiment"] +
            source_reliability * self.WEIGHTS["source_reliability"] +
            recency_score * self.WEIGHTS["recency"]
        )

        # Apply materiality boost
        if classification.is_material:
            overall_confidence = min(1.0, overall_confidence * 1.1)
            factors.append({
                "factor": "materiality",
                "signal": 0.0,
                "confidence": 1.0,
                "weight": 0.0,
                "detail": "Material event (confidence boosted)",
            })

        # Determine direction
        if normalized_signal > 0.25:
            direction = "BULLISH"
        elif normalized_signal < -0.25:
            direction = "BEARISH"
        else:
            direction = "NEUTRAL"

        return DirectionPrediction(
            direction=direction,
            confidence=min(1.0, overall_confidence),
            signal_strength=normalized_signal,
            factors=factors,
        )

    def predict_from_text(
        self,
        text: str,
        source: str | None = None,
    ) -> DirectionPrediction:
        """Predict direction directly from text.

        Args:
            text: Event text
            source: Information source

        Returns:
            DirectionPrediction
        """
        from .event_classifier import classify_event
        from backend.processing.sentiment.finbert_service import SimpleSentimentService

        # Classify event
        classification = classify_event(text, source)

        # Get sentiment
        sentiment_service = SimpleSentimentService()
        sentiment = sentiment_service.analyze(text)

        return self.predict(
            classification=classification,
            sentiment=sentiment,
            source=source,
            recency_score=1.0,
        )


def predict_direction(
    classification: EventClassification,
    sentiment: SentimentResult | None = None,
    source: str | None = None,
) -> DirectionPrediction:
    """Convenience function to predict direction.

    Args:
        classification: Event classification
        sentiment: Sentiment result
        source: Information source

    Returns:
        DirectionPrediction
    """
    predictor = DirectionPredictor()
    return predictor.predict(classification, sentiment, source)
