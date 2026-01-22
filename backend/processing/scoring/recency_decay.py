"""Recency decay functions for alpha calculation."""

import math
from datetime import datetime, timezone
from typing import Callable

import structlog

logger = structlog.get_logger(__name__)


class RecencyDecay:
    """Calculate recency decay for event freshness.

    News becomes stale over time. This module provides decay
    functions that reduce the weight of older information.
    """

    # Decay function types
    DECAY_TYPES = {
        "exponential": "Fast initial decay, slower later",
        "linear": "Constant decay rate",
        "step": "Discrete freshness levels",
        "log": "Slow initial decay, faster later",
    }

    # Default half-life in hours for exponential decay
    DEFAULT_HALF_LIFE = 2.0

    def __init__(
        self,
        decay_type: str = "exponential",
        half_life_hours: float = 2.0,
        min_score: float = 0.1,
    ):
        """Initialize recency decay.

        Args:
            decay_type: Type of decay function
            half_life_hours: Half-life for exponential decay
            min_score: Minimum score (floor)
        """
        self.decay_type = decay_type
        self.half_life_hours = half_life_hours
        self.min_score = min_score

    def calculate(
        self,
        event_time: datetime,
        current_time: datetime | None = None,
    ) -> float:
        """Calculate recency score for an event.

        Args:
            event_time: When the event occurred
            current_time: Current time (defaults to now)

        Returns:
            Recency score (0-1, 1 = fresh)
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Ensure timezone awareness
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        # Calculate age in hours
        age_hours = (current_time - event_time).total_seconds() / 3600

        # Future events get full score
        if age_hours < 0:
            return 1.0

        # Apply decay function
        if self.decay_type == "exponential":
            score = self._exponential_decay(age_hours)
        elif self.decay_type == "linear":
            score = self._linear_decay(age_hours)
        elif self.decay_type == "step":
            score = self._step_decay(age_hours)
        elif self.decay_type == "log":
            score = self._log_decay(age_hours)
        else:
            score = self._exponential_decay(age_hours)

        return max(self.min_score, score)

    def _exponential_decay(self, age_hours: float) -> float:
        """Exponential decay function.

        Score = 0.5 ^ (age / half_life)

        Args:
            age_hours: Age in hours

        Returns:
            Decay score
        """
        return math.pow(0.5, age_hours / self.half_life_hours)

    def _linear_decay(self, age_hours: float) -> float:
        """Linear decay function.

        Score decreases linearly to min over 24 hours.

        Args:
            age_hours: Age in hours

        Returns:
            Decay score
        """
        decay_period = 24.0  # Full decay over 24 hours
        decay_rate = (1.0 - self.min_score) / decay_period

        return max(self.min_score, 1.0 - (age_hours * decay_rate))

    def _step_decay(self, age_hours: float) -> float:
        """Step decay function.

        Discrete freshness levels.

        Args:
            age_hours: Age in hours

        Returns:
            Decay score
        """
        if age_hours < 0.5:
            return 1.0  # Breaking news (< 30 min)
        elif age_hours < 2:
            return 0.9  # Very fresh (< 2 hours)
        elif age_hours < 6:
            return 0.75  # Fresh (< 6 hours)
        elif age_hours < 24:
            return 0.5  # Same day
        elif age_hours < 72:
            return 0.3  # Recent (< 3 days)
        else:
            return self.min_score  # Old

    def _log_decay(self, age_hours: float) -> float:
        """Logarithmic decay function.

        Slow initial decay, faster later.

        Args:
            age_hours: Age in hours

        Returns:
            Decay score
        """
        if age_hours <= 0:
            return 1.0

        # Log decay: 1 / (1 + log(1 + age))
        return 1.0 / (1.0 + math.log(1.0 + age_hours))

    def get_freshness_label(self, event_time: datetime) -> str:
        """Get human-readable freshness label.

        Args:
            event_time: Event timestamp

        Returns:
            Freshness label
        """
        score = self.calculate(event_time)

        if score >= 0.9:
            return "breaking"
        elif score >= 0.75:
            return "fresh"
        elif score >= 0.5:
            return "recent"
        elif score >= 0.3:
            return "aging"
        else:
            return "stale"

    def get_time_description(self, event_time: datetime) -> str:
        """Get human-readable time description.

        Args:
            event_time: Event timestamp

        Returns:
            Time description
        """
        now = datetime.now(timezone.utc)

        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)

        delta = now - event_time
        hours = delta.total_seconds() / 3600

        if hours < 0:
            return "upcoming"
        elif hours < 1:
            minutes = int(delta.total_seconds() / 60)
            return f"{minutes} minutes ago"
        elif hours < 24:
            return f"{int(hours)} hours ago"
        elif hours < 48:
            return "yesterday"
        elif hours < 168:  # 7 days
            days = int(hours / 24)
            return f"{days} days ago"
        else:
            return event_time.strftime("%Y-%m-%d")


def calculate_recency(
    event_time: datetime,
    decay_type: str = "exponential",
) -> float:
    """Convenience function to calculate recency score.

    Args:
        event_time: Event timestamp
        decay_type: Type of decay function

    Returns:
        Recency score (0-1)
    """
    decay = RecencyDecay(decay_type=decay_type)
    return decay.calculate(event_time)
