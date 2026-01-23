"""Alpha score calculator combining all signals."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

from backend.processing.classification.event_classifier import EventClassification
from backend.processing.classification.direction_predictor import DirectionPrediction
from backend.processing.classification.urgency_scorer import UrgencyScore
from backend.processing.sentiment.finbert_service import SentimentResult
from .liquidity_scorer import LiquidityScorer
from .recency_decay import RecencyDecay
from .source_weights import SourceWeights

logger = structlog.get_logger(__name__)


@dataclass
class AlphaScore:
    """Comprehensive alpha score for an event."""

    score: float  # -1 to 1 final alpha score
    direction: str  # "BULLISH", "BEARISH", "NEUTRAL"
    confidence: float  # 0-1 overall confidence
    urgency_level: str  # "critical", "high", "medium", "low"

    # Component scores
    event_score: float
    sentiment_score: float
    source_score: float
    recency_score: float
    liquidity_factor: float

    # Metadata
    factors: list[dict[str, Any]] = field(default_factory=list)
    recommended_action: str = ""


class AlphaCalculator:
    """Calculate alpha scores for financial events."""

    # Component weights
    WEIGHTS = {
        "event": 0.35,
        "sentiment": 0.25,
        "source": 0.15,
        "recency": 0.15,
        "liquidity": 0.10,
    }

    def __init__(
        self,
        source_weights: SourceWeights | None = None,
        liquidity_scorer: LiquidityScorer | None = None,
        recency_decay: RecencyDecay | None = None,
    ):
        """Initialize alpha calculator.

        Args:
            source_weights: Custom source weights
            liquidity_scorer: Custom liquidity scorer
            recency_decay: Custom recency decay function
        """
        self.source_weights = source_weights or SourceWeights()
        self.liquidity_scorer = liquidity_scorer or LiquidityScorer()
        self.recency_decay = recency_decay or RecencyDecay()

    def calculate(
        self,
        classification: EventClassification,
        sentiment: SentimentResult | None = None,
        source: str = "unknown",
        event_time: datetime | None = None,
        ticker: str | None = None,
        market_cap: float | None = None,
        avg_volume: float | None = None,
    ) -> AlphaScore:
        """Calculate alpha score for an event.

        Args:
            classification: Event classification result
            sentiment: Sentiment analysis result
            source: Information source
            event_time: Event timestamp
            ticker: Stock ticker symbol
            market_cap: Market capitalization (for liquidity)
            avg_volume: Average trading volume (for liquidity)

        Returns:
            AlphaScore
        """
        factors = []

        # Event type score
        event_score = classification.base_signal_weight
        event_confidence = classification.confidence

        factors.append({
            "component": "event",
            "score": event_score,
            "confidence": event_confidence,
            "weight": self.WEIGHTS["event"],
            "detail": f"{classification.event_type.value}",
        })

        # Sentiment score
        if sentiment:
            sentiment_score = sentiment.score
            sentiment_confidence = sentiment.confidence
        else:
            sentiment_score = 0.0
            sentiment_confidence = 0.5

        factors.append({
            "component": "sentiment",
            "score": sentiment_score,
            "confidence": sentiment_confidence,
            "weight": self.WEIGHTS["sentiment"],
            "detail": f"{sentiment.label if sentiment else 'none'} ({sentiment_confidence:.2f})",
        })

        # Source reliability score
        source_reliability = self.source_weights.get_weight(source)

        factors.append({
            "component": "source",
            "score": source_reliability,
            "confidence": source_reliability,
            "weight": self.WEIGHTS["source"],
            "detail": f"{source} ({source_reliability:.2f})",
        })

        # Recency score
        if event_time:
            recency_score = self.recency_decay.calculate(event_time)
        else:
            recency_score = 1.0

        factors.append({
            "component": "recency",
            "score": recency_score,
            "confidence": recency_score,
            "weight": self.WEIGHTS["recency"],
            "detail": f"Freshness: {recency_score:.2f}",
        })

        # Liquidity factor
        liquidity_info = self.liquidity_scorer.score(
            ticker=ticker,
            market_cap=market_cap,
            avg_volume=avg_volume,
        )

        factors.append({
            "component": "liquidity",
            "score": liquidity_info["alpha_multiplier"],
            "confidence": liquidity_info["confidence"],
            "weight": self.WEIGHTS["liquidity"],
            "detail": f"{liquidity_info['category']} ({liquidity_info['alpha_multiplier']:.2f}x)",
        })

        # Calculate weighted alpha score
        alpha = self._calculate_weighted_score(
            event_score=event_score,
            sentiment_score=sentiment_score,
            source_reliability=source_reliability,
            recency_score=recency_score,
            liquidity_multiplier=liquidity_info["alpha_multiplier"],
            event_confidence=event_confidence,
            sentiment_confidence=sentiment_confidence,
        )

        # Calculate overall confidence
        confidence = self._calculate_confidence(
            event_confidence=event_confidence,
            sentiment_confidence=sentiment_confidence,
            source_reliability=source_reliability,
            recency_score=recency_score,
            is_material=classification.is_material,
        )

        # Determine direction - use sentiment as primary signal when alpha is weak
        # but sentiment signal is clear
        sentiment_driven_direction = "NEUTRAL"
        if sentiment and sentiment.confidence > 0.5:
            if sentiment.score > 0.3:
                sentiment_driven_direction = "BULLISH"
            elif sentiment.score < -0.3:
                sentiment_driven_direction = "BEARISH"

        # Primary direction from combined alpha score
        if alpha > 0.15:
            direction = "BULLISH"
        elif alpha < -0.15:
            direction = "BEARISH"
        elif sentiment_driven_direction != "NEUTRAL":
            # Fall back to sentiment-driven direction when alpha is neutral
            direction = sentiment_driven_direction
        else:
            direction = "NEUTRAL"

        # Determine urgency level
        urgency = self._determine_urgency(
            classification=classification,
            recency_score=recency_score,
            liquidity_category=liquidity_info["category"],
        )

        # Generate recommendation
        recommendation = self._generate_recommendation(
            direction=direction,
            alpha=alpha,
            confidence=confidence,
            urgency=urgency,
        )

        return AlphaScore(
            score=alpha,
            direction=direction,
            confidence=confidence,
            urgency_level=urgency,
            event_score=event_score,
            sentiment_score=sentiment_score,
            source_score=source_reliability,
            recency_score=recency_score,
            liquidity_factor=liquidity_info["alpha_multiplier"],
            factors=factors,
            recommended_action=recommendation,
        )

    def _calculate_weighted_score(
        self,
        event_score: float,
        sentiment_score: float,
        source_reliability: float,
        recency_score: float,
        liquidity_multiplier: float,
        event_confidence: float,
        sentiment_confidence: float,
    ) -> float:
        """Calculate the weighted alpha score."""

        # Direction signals (affect alpha direction)
        direction_signal = (
            event_score * self.WEIGHTS["event"] * event_confidence +
            sentiment_score * self.WEIGHTS["sentiment"] * sentiment_confidence
        )

        # Normalize direction signal
        direction_weight = (
            self.WEIGHTS["event"] * event_confidence +
            self.WEIGHTS["sentiment"] * sentiment_confidence
        )

        if direction_weight > 0:
            base_alpha = direction_signal / direction_weight
        else:
            base_alpha = 0.0

        # Apply modifiers
        # Source reliability affects confidence in the signal
        modified_alpha = base_alpha * source_reliability

        # Recency decay
        modified_alpha *= recency_score

        # Liquidity multiplier (illiquid = higher alpha potential)
        modified_alpha *= liquidity_multiplier

        # Clamp to -1 to 1
        return max(-1.0, min(1.0, modified_alpha))

    def _calculate_confidence(
        self,
        event_confidence: float,
        sentiment_confidence: float,
        source_reliability: float,
        recency_score: float,
        is_material: bool,
    ) -> float:
        """Calculate overall confidence score."""

        confidence = (
            event_confidence * 0.35 +
            sentiment_confidence * 0.25 +
            source_reliability * 0.25 +
            recency_score * 0.15
        )

        # Material event boost
        if is_material:
            confidence = min(1.0, confidence * 1.1)

        return confidence

    def _determine_urgency(
        self,
        classification: EventClassification,
        recency_score: float,
        liquidity_category: str,
    ) -> str:
        """Determine urgency level."""

        # Critical events
        critical_types = {
            "INSIDER_BUY", "FDA_APPROVAL", "FDA_REJECTION", "BANKRUPTCY",
            "ACTIVIST_STAKE", "EARNINGS_BEAT", "EARNINGS_MISS",
        }

        if classification.event_type.value in critical_types and recency_score > 0.8:
            return "critical"

        # High urgency
        if classification.is_material and recency_score > 0.6:
            return "high"

        # Medium urgency
        if recency_score > 0.4 or liquidity_category in ["micro_cap", "penny"]:
            return "medium"

        return "low"

    def _generate_recommendation(
        self,
        direction: str,
        alpha: float,
        confidence: float,
        urgency: str,
    ) -> str:
        """Generate action recommendation."""

        if urgency == "critical":
            if direction == "BULLISH" and alpha > 0.5 and confidence > 0.7:
                return "STRONG BUY SIGNAL - Consider immediate entry"
            elif direction == "BEARISH" and alpha < -0.5 and confidence > 0.7:
                return "STRONG SELL SIGNAL - Consider immediate exit or short"
            else:
                return "CRITICAL EVENT - Verify and assess position"

        elif urgency == "high":
            if direction == "BULLISH":
                return "BULLISH SIGNAL - Review for entry within minutes"
            elif direction == "BEARISH":
                return "BEARISH SIGNAL - Review for exit within minutes"
            else:
                return "HIGH PRIORITY - Monitor closely"

        elif urgency == "medium":
            if direction != "NEUTRAL":
                return f"{direction} BIAS - Add to watchlist for further analysis"
            else:
                return "MODERATE INTEREST - Monitor if relevant to positions"

        else:
            return "INFORMATIONAL - Review at convenience"


def calculate_alpha(
    classification: EventClassification,
    sentiment: SentimentResult | None = None,
    source: str = "unknown",
    event_time: datetime | None = None,
    ticker: str | None = None,
) -> AlphaScore:
    """Convenience function to calculate alpha score.

    Args:
        classification: Event classification
        sentiment: Sentiment result
        source: Information source
        event_time: Event timestamp
        ticker: Stock ticker

    Returns:
        AlphaScore
    """
    calculator = AlphaCalculator()
    return calculator.calculate(
        classification=classification,
        sentiment=sentiment,
        source=source,
        event_time=event_time,
        ticker=ticker,
    )
