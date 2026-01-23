"""Real-time alpha decay for financial events.

Alpha signals decay over time as information gets priced in.
Different event types have different decay characteristics.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import structlog

from backend.processing.classification.event_classifier import EventType

logger = structlog.get_logger(__name__)


class DecayProfile(str, Enum):
    """Alpha decay profiles for different event types."""

    # Very fast decay - information priced in within minutes
    INSTANT = "instant"  # ~30 min half-life

    # Fast decay - priced in within hours
    FAST = "fast"  # ~2 hour half-life

    # Standard decay - priced in over a day
    STANDARD = "standard"  # ~6 hour half-life

    # Slow decay - takes multiple days
    SLOW = "slow"  # ~24 hour half-life

    # Very slow decay - long-term information
    GRADUAL = "gradual"  # ~72 hour half-life


# Map event types to decay profiles
EVENT_DECAY_PROFILES: dict[EventType, DecayProfile] = {
    # Instant decay - breaking news, time-critical
    EventType.FDA_APPROVAL: DecayProfile.INSTANT,
    EventType.FDA_REJECTION: DecayProfile.INSTANT,
    EventType.EARNINGS_BEAT: DecayProfile.INSTANT,
    EventType.EARNINGS_MISS: DecayProfile.INSTANT,
    EventType.BANKRUPTCY: DecayProfile.INSTANT,
    EventType.DELISTING: DecayProfile.INSTANT,

    # Fast decay - still time-sensitive but slightly slower
    EventType.INSIDER_BUY: DecayProfile.FAST,
    EventType.INSIDER_SELL: DecayProfile.FAST,
    EventType.CLINICAL_TRIAL: DecayProfile.FAST,
    EventType.ACTIVIST_STAKE: DecayProfile.FAST,

    # Standard decay - important but less time-critical
    EventType.ACQUISITION: DecayProfile.STANDARD,
    EventType.MERGER: DecayProfile.STANDARD,
    EventType.SPINOFF: DecayProfile.STANDARD,
    EventType.BUYBACK: DecayProfile.STANDARD,
    EventType.OFFERING: DecayProfile.STANDARD,
    EventType.REGULATORY_ACTION: DecayProfile.STANDARD,
    EventType.LAWSUIT: DecayProfile.STANDARD,
    EventType.SETTLEMENT: DecayProfile.STANDARD,
    EventType.CEO_CHANGE: DecayProfile.STANDARD,
    EventType.EXECUTIVE_DEPARTURE: DecayProfile.STANDARD,
    EventType.TIER_CHANGE: DecayProfile.STANDARD,

    # Slow decay - long-term information value
    EventType.EARNINGS_ANNOUNCE: DecayProfile.SLOW,
    EventType.DIVIDEND: DecayProfile.SLOW,
    EventType.SPLIT: DecayProfile.SLOW,
    EventType.CONTRACT: DecayProfile.SLOW,
    EventType.PARTNERSHIP: DecayProfile.SLOW,
    EventType.PRODUCT_LAUNCH: DecayProfile.SLOW,
    EventType.BOARD_CHANGE: DecayProfile.SLOW,
    EventType.INSTITUTIONAL_BUY: DecayProfile.SLOW,
    EventType.INSTITUTIONAL_SELL: DecayProfile.SLOW,

    # Gradual decay - general news/context
    EventType.SEC_FILING: DecayProfile.GRADUAL,
    EventType.NEWS: DecayProfile.GRADUAL,
    EventType.SOCIAL_MENTION: DecayProfile.GRADUAL,
}


# Half-life in hours for each decay profile
DECAY_HALF_LIVES: dict[DecayProfile, float] = {
    DecayProfile.INSTANT: 0.5,  # 30 minutes
    DecayProfile.FAST: 2.0,  # 2 hours
    DecayProfile.STANDARD: 6.0,  # 6 hours
    DecayProfile.SLOW: 24.0,  # 24 hours
    DecayProfile.GRADUAL: 72.0,  # 72 hours
}


@dataclass
class DecayResult:
    """Result of alpha decay calculation."""

    original_alpha: float
    decayed_alpha: float
    decay_factor: float
    age_hours: float
    half_life_hours: float
    decay_profile: DecayProfile
    is_stale: bool  # True if alpha has decayed below threshold
    time_to_stale: float | None  # Hours until stale (None if already stale)
    details: dict[str, Any]


class AlphaDecayCalculator:
    """Calculate real-time alpha decay for financial events."""

    # Minimum alpha threshold - below this, signal is considered stale
    STALE_THRESHOLD = 0.05

    # Minimum decay factor - alpha never fully disappears
    MIN_DECAY_FACTOR = 0.01

    def __init__(
        self,
        custom_half_lives: dict[DecayProfile, float] | None = None,
        stale_threshold: float = 0.05,
    ):
        """Initialize alpha decay calculator.

        Args:
            custom_half_lives: Custom half-lives for decay profiles
            stale_threshold: Threshold below which alpha is stale
        """
        self.half_lives = DECAY_HALF_LIVES.copy()
        if custom_half_lives:
            self.half_lives.update(custom_half_lives)

        self.stale_threshold = stale_threshold

    def calculate_decay(
        self,
        alpha_score: float,
        event_type: EventType,
        event_time: datetime,
        current_time: datetime | None = None,
    ) -> DecayResult:
        """Calculate decayed alpha score.

        Args:
            alpha_score: Original alpha score (-1 to 1)
            event_type: Type of event
            event_time: When the event occurred
            current_time: Current time (defaults to now)

        Returns:
            DecayResult with decayed alpha
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Ensure timezone awareness
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        # Get decay profile for this event type
        decay_profile = EVENT_DECAY_PROFILES.get(event_type, DecayProfile.STANDARD)
        half_life = self.half_lives[decay_profile]

        # Calculate age in hours
        age_hours = (current_time - event_time).total_seconds() / 3600

        # Future events don't decay
        if age_hours < 0:
            return DecayResult(
                original_alpha=alpha_score,
                decayed_alpha=alpha_score,
                decay_factor=1.0,
                age_hours=0,
                half_life_hours=half_life,
                decay_profile=decay_profile,
                is_stale=False,
                time_to_stale=self._time_to_stale(alpha_score, half_life),
                details={"note": "Future event, no decay applied"},
            )

        # Calculate decay factor using exponential decay
        decay_factor = self._exponential_decay(age_hours, half_life)

        # Ensure minimum decay factor
        decay_factor = max(self.MIN_DECAY_FACTOR, decay_factor)

        # Apply decay to alpha (preserving sign)
        decayed_alpha = alpha_score * decay_factor

        # Determine if stale
        is_stale = abs(decayed_alpha) < self.stale_threshold

        # Calculate time until stale (if not already)
        time_to_stale = None
        if not is_stale:
            remaining = self._time_to_stale(
                alpha_score,
                half_life,
                current_decay_factor=decay_factor,
            )
            if remaining:
                time_to_stale = remaining

        return DecayResult(
            original_alpha=alpha_score,
            decayed_alpha=decayed_alpha,
            decay_factor=decay_factor,
            age_hours=age_hours,
            half_life_hours=half_life,
            decay_profile=decay_profile,
            is_stale=is_stale,
            time_to_stale=time_to_stale,
            details={
                "event_type": event_type.value,
                "age_minutes": int(age_hours * 60),
                "decay_percent": round((1 - decay_factor) * 100, 1),
            },
        )

    def _exponential_decay(self, age_hours: float, half_life: float) -> float:
        """Calculate exponential decay factor.

        Uses formula: decay = 0.5 ^ (age / half_life)

        Args:
            age_hours: Age in hours
            half_life: Half-life in hours

        Returns:
            Decay factor (0 to 1)
        """
        if age_hours <= 0:
            return 1.0

        return math.pow(0.5, age_hours / half_life)

    def _time_to_stale(
        self,
        alpha_score: float,
        half_life: float,
        current_decay_factor: float = 1.0,
    ) -> float | None:
        """Calculate time until alpha becomes stale.

        Args:
            alpha_score: Original alpha score
            half_life: Half-life in hours
            current_decay_factor: Current decay factor

        Returns:
            Hours until stale, or None if already stale
        """
        current_alpha = abs(alpha_score * current_decay_factor)

        if current_alpha < self.stale_threshold:
            return None

        # Solve for t when |alpha * 0.5^(t/half_life)| = threshold
        # t = half_life * log2(|alpha| / threshold)
        try:
            time_hours = half_life * math.log2(current_alpha / self.stale_threshold)
            return max(0, time_hours)
        except (ValueError, ZeroDivisionError):
            return None

    def get_decay_profile(self, event_type: EventType) -> DecayProfile:
        """Get the decay profile for an event type.

        Args:
            event_type: Event type

        Returns:
            DecayProfile
        """
        return EVENT_DECAY_PROFILES.get(event_type, DecayProfile.STANDARD)

    def get_half_life(self, event_type: EventType) -> float:
        """Get the half-life in hours for an event type.

        Args:
            event_type: Event type

        Returns:
            Half-life in hours
        """
        profile = self.get_decay_profile(event_type)
        return self.half_lives[profile]

    def batch_decay(
        self,
        events: list[dict[str, Any]],
        current_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Apply decay to multiple events.

        Args:
            events: List of event dicts with alpha_score, event_type, event_time
            current_time: Current time (defaults to now)

        Returns:
            Events with decayed alpha scores
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        results = []
        for event in events:
            alpha = event.get("alpha_score", 0)
            event_type_str = event.get("event_type", "NEWS")

            try:
                event_type = EventType(event_type_str)
            except ValueError:
                event_type = EventType.NEWS

            # Parse event time
            event_time = event.get("event_time")
            if isinstance(event_time, str):
                try:
                    event_time = datetime.fromisoformat(
                        event_time.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    event_time = current_time  # Default to now if unparseable
            elif not isinstance(event_time, datetime):
                event_time = current_time

            # Calculate decay
            decay_result = self.calculate_decay(
                alpha_score=alpha,
                event_type=event_type,
                event_time=event_time,
                current_time=current_time,
            )

            # Update event with decayed values
            event_copy = event.copy()
            event_copy["alpha_score"] = decay_result.decayed_alpha
            event_copy["alpha_original"] = decay_result.original_alpha
            event_copy["alpha_decay_factor"] = decay_result.decay_factor
            event_copy["alpha_is_stale"] = decay_result.is_stale
            event_copy["alpha_age_hours"] = decay_result.age_hours

            results.append(event_copy)

        return results


class PeriodicAlphaDecayUpdater:
    """Update alpha scores periodically for stored events."""

    def __init__(
        self,
        decay_calculator: AlphaDecayCalculator | None = None,
        update_interval_minutes: int = 5,
    ):
        """Initialize the periodic updater.

        Args:
            decay_calculator: Custom decay calculator
            update_interval_minutes: How often to update (for scheduling)
        """
        self.decay_calculator = decay_calculator or AlphaDecayCalculator()
        self.update_interval_minutes = update_interval_minutes

    def update_event_alpha(
        self,
        event: dict[str, Any],
        current_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Update a single event's alpha score.

        Args:
            event: Event dict
            current_time: Current time

        Returns:
            Updated event dict
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Get original alpha (stored or current)
        original_alpha = event.get("alpha_original") or event.get("alpha_score", 0)

        # Get event type
        event_type_str = event.get("event_type", "NEWS")
        try:
            event_type = EventType(event_type_str)
        except ValueError:
            event_type = EventType.NEWS

        # Parse event time
        event_time = event.get("event_time") or event.get("published_at")
        if isinstance(event_time, str):
            try:
                event_time = datetime.fromisoformat(
                    event_time.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                event_time = current_time
        elif not isinstance(event_time, datetime):
            event_time = current_time

        # Calculate new decay
        decay_result = self.decay_calculator.calculate_decay(
            alpha_score=original_alpha,
            event_type=event_type,
            event_time=event_time,
            current_time=current_time,
        )

        # Update event
        event["alpha_score"] = decay_result.decayed_alpha
        event["alpha_original"] = original_alpha
        event["alpha_decay_factor"] = decay_result.decay_factor
        event["alpha_is_stale"] = decay_result.is_stale
        event["alpha_age_hours"] = decay_result.age_hours
        event["alpha_decay_profile"] = decay_result.decay_profile.value
        event["alpha_updated_at"] = current_time.isoformat()

        return event

    def get_events_needing_update(
        self,
        events: list[dict[str, Any]],
        min_age_minutes: int = 5,
    ) -> list[dict[str, Any]]:
        """Filter events that need alpha updates.

        Args:
            events: List of events
            min_age_minutes: Minimum age for update

        Returns:
            Events needing update
        """
        now = datetime.now(timezone.utc)
        min_age = timedelta(minutes=min_age_minutes)
        needs_update = []

        for event in events:
            # Skip if already stale
            if event.get("alpha_is_stale"):
                continue

            # Check last update time
            last_update = event.get("alpha_updated_at")
            if last_update:
                if isinstance(last_update, str):
                    try:
                        last_update = datetime.fromisoformat(
                            last_update.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        last_update = None

                if last_update and (now - last_update) < min_age:
                    continue

            needs_update.append(event)

        return needs_update


# Module-level convenience functions
def calculate_alpha_decay(
    alpha_score: float,
    event_type: EventType,
    event_time: datetime,
    current_time: datetime | None = None,
) -> DecayResult:
    """Convenience function to calculate alpha decay.

    Args:
        alpha_score: Original alpha score
        event_type: Type of event
        event_time: When event occurred
        current_time: Current time

    Returns:
        DecayResult
    """
    calculator = AlphaDecayCalculator()
    return calculator.calculate_decay(
        alpha_score=alpha_score,
        event_type=event_type,
        event_time=event_time,
        current_time=current_time,
    )


def get_decay_profile_for_event(event_type: EventType) -> tuple[DecayProfile, float]:
    """Get decay profile and half-life for an event type.

    Args:
        event_type: Event type

    Returns:
        Tuple of (DecayProfile, half_life_hours)
    """
    profile = EVENT_DECAY_PROFILES.get(event_type, DecayProfile.STANDARD)
    half_life = DECAY_HALF_LIVES[profile]
    return profile, half_life
