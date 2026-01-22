"""Urgency scoring for financial events."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import structlog

from .event_classifier import EventType

logger = structlog.get_logger(__name__)


@dataclass
class UrgencyScore:
    """Urgency assessment for an event."""

    score: float  # 0-1 scale, 1 = most urgent
    level: str  # "critical", "high", "medium", "low"
    reasons: list[str]
    recommended_action: str


class UrgencyScorer:
    """Score the time-sensitivity of financial events."""

    # Event type urgency weights
    TYPE_URGENCY = {
        # Critical - immediate action required
        EventType.INSIDER_BUY: 0.95,
        EventType.FDA_APPROVAL: 0.95,
        EventType.FDA_REJECTION: 0.95,
        EventType.BANKRUPTCY: 0.95,
        EventType.ACTIVIST_STAKE: 0.9,
        EventType.EARNINGS_BEAT: 0.9,
        EventType.EARNINGS_MISS: 0.9,

        # High - act within minutes
        EventType.ACQUISITION: 0.85,
        EventType.MERGER: 0.85,
        EventType.INSIDER_SELL: 0.8,
        EventType.DELISTING: 0.85,
        EventType.REGULATORY_ACTION: 0.8,
        EventType.CEO_CHANGE: 0.75,

        # Medium - act within hours
        EventType.OFFERING: 0.6,
        EventType.CLINICAL_TRIAL: 0.7,
        EventType.CONTRACT: 0.6,
        EventType.PARTNERSHIP: 0.5,
        EventType.TIER_CHANGE: 0.65,
        EventType.BUYBACK: 0.5,
        EventType.DIVIDEND: 0.5,

        # Low - informational
        EventType.SEC_FILING: 0.4,
        EventType.EARNINGS_ANNOUNCE: 0.4,
        EventType.PRODUCT_LAUNCH: 0.35,
        EventType.NEWS: 0.3,
        EventType.SOCIAL_MENTION: 0.25,
    }

    # Source urgency modifiers
    SOURCE_MODIFIERS = {
        "sec_edgar": 1.2,  # SEC filings are authoritative
        "newswire": 1.1,  # Official press releases
        "twitter": 0.9,  # Social needs verification
        "reddit": 0.85,  # Lower reliability
        "stocktwits": 0.85,
    }

    def __init__(self):
        """Initialize urgency scorer."""
        pass

    def score(
        self,
        event_type: EventType,
        source: str | None = None,
        event_time: datetime | None = None,
        market_hours: bool = True,
        ticker_volume: str = "normal",  # "high", "normal", "low"
    ) -> UrgencyScore:
        """Calculate urgency score for an event.

        Args:
            event_type: Type of event
            source: Source of the information
            event_time: Time the event occurred
            market_hours: Whether markets are open
            ticker_volume: Typical trading volume

        Returns:
            UrgencyScore
        """
        reasons = []

        # Base urgency from event type
        base_score = self.TYPE_URGENCY.get(event_type, 0.3)
        reasons.append(f"Event type: {event_type.value}")

        # Source modifier
        if source:
            modifier = self.SOURCE_MODIFIERS.get(source.lower(), 1.0)
            base_score *= modifier
            if modifier != 1.0:
                reasons.append(f"Source modifier: {modifier:.1f}x ({source})")

        # Time decay
        if event_time:
            age_hours = self._get_age_hours(event_time)

            if age_hours < 0.5:
                # Breaking news (< 30 min)
                base_score *= 1.2
                reasons.append("Breaking news (< 30 min old)")
            elif age_hours < 2:
                # Recent (< 2 hours)
                base_score *= 1.0
                reasons.append("Recent news (< 2 hours)")
            elif age_hours < 24:
                # Same day
                base_score *= 0.8
                reasons.append("Same day news")
            else:
                # Older
                base_score *= 0.5
                reasons.append(f"Older news ({age_hours:.0f} hours)")

        # Market hours bonus
        if market_hours:
            base_score *= 1.1
            reasons.append("Market hours active")
        else:
            base_score *= 0.85
            reasons.append("After hours")

        # Volume adjustment
        if ticker_volume == "low":
            base_score *= 1.15  # More urgent for illiquid stocks
            reasons.append("Low volume stock (higher impact)")
        elif ticker_volume == "high":
            base_score *= 0.9  # Less urgent for liquid stocks
            reasons.append("High volume stock")

        # Cap at 1.0
        final_score = min(1.0, max(0.0, base_score))

        # Determine level
        if final_score >= 0.8:
            level = "critical"
            action = "Immediate action - consider position entry/exit"
        elif final_score >= 0.6:
            level = "high"
            action = "Act within minutes - verify and assess"
        elif final_score >= 0.4:
            level = "medium"
            action = "Review within hours - add to watchlist"
        else:
            level = "low"
            action = "Informational - monitor if in watchlist"

        return UrgencyScore(
            score=final_score,
            level=level,
            reasons=reasons,
            recommended_action=action,
        )

    def _get_age_hours(self, event_time: datetime) -> float:
        """Calculate age of event in hours.

        Args:
            event_time: Event timestamp

        Returns:
            Age in hours
        """
        now = datetime.now(timezone.utc)

        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)

        delta = now - event_time
        return delta.total_seconds() / 3600

    def is_market_hours(self) -> bool:
        """Check if US markets are currently open.

        Returns:
            True if market hours (9:30 AM - 4:00 PM ET)
        """
        now = datetime.now(timezone.utc)

        # Convert to ET (UTC-5 or UTC-4 for DST)
        # Simplified - doesn't account for holidays
        et_hour = (now.hour - 5) % 24  # Rough EST conversion

        # Weekday check
        if now.weekday() >= 5:  # Saturday or Sunday
            return False

        # Hour check (9:30 AM - 4:00 PM ET)
        if et_hour < 9 or et_hour >= 16:
            return False

        if et_hour == 9:
            return now.minute >= 30

        return True


def score_urgency(
    event_type: EventType,
    source: str | None = None,
    event_time: datetime | None = None,
) -> UrgencyScore:
    """Convenience function to score urgency.

    Args:
        event_type: Type of event
        source: Source of information
        event_time: Event timestamp

    Returns:
        UrgencyScore
    """
    scorer = UrgencyScorer()
    return scorer.score(event_type, source, event_time)
