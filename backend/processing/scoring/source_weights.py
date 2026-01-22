"""Source reliability weights for alpha calculation."""

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SourceWeights:
    """Manage reliability weights for information sources."""

    # Default source weights (0-1 scale, 1 = most reliable)
    DEFAULT_WEIGHTS = {
        # Official/Regulatory (highest reliability)
        "sec_edgar": 1.0,
        "sec": 1.0,
        "data.sec.gov": 1.0,
        "finra": 0.95,
        "fda": 0.98,
        "uspto": 0.95,

        # Major newswires (high reliability)
        "prnewswire": 0.95,
        "businesswire": 0.95,
        "globenewswire": 0.92,
        "accesswire": 0.88,

        # OTC/Pink sheets sources
        "otc_markets": 0.85,
        "otcmarkets": 0.85,
        "finra_otc": 0.88,

        # Financial news (medium-high reliability)
        "reuters": 0.9,
        "bloomberg": 0.9,
        "wsj": 0.88,
        "marketwatch": 0.82,
        "yahoo_finance": 0.78,
        "seekingalpha": 0.72,

        # Penny stock focused (medium reliability)
        "stock_titan": 0.75,
        "allpennystocks": 0.65,
        "pennystocks_com": 0.65,
        "microcapdaily": 0.62,

        # Social media (lower reliability - needs verification)
        "twitter": 0.55,
        "x": 0.55,
        "stocktwits": 0.58,
        "reddit": 0.52,
        "discord": 0.48,

        # General/Unknown
        "rss": 0.65,
        "scraper": 0.6,
        "unknown": 0.5,
    }

    def __init__(self, custom_weights: dict[str, float] | None = None):
        """Initialize source weights.

        Args:
            custom_weights: Custom weight overrides
        """
        self.weights = {**self.DEFAULT_WEIGHTS}
        if custom_weights:
            self.weights.update(custom_weights)

    def get_weight(self, source: str) -> float:
        """Get reliability weight for a source.

        Args:
            source: Source name

        Returns:
            Reliability weight (0-1)
        """
        source_lower = source.lower().strip()

        # Direct match
        if source_lower in self.weights:
            return self.weights[source_lower]

        # Partial match
        for key, weight in self.weights.items():
            if key in source_lower or source_lower in key:
                return weight

        # Default for unknown
        return self.weights.get("unknown", 0.5)

    def set_weight(self, source: str, weight: float) -> None:
        """Set weight for a source.

        Args:
            source: Source name
            weight: Reliability weight (0-1)
        """
        self.weights[source.lower()] = max(0.0, min(1.0, weight))

    def get_all_weights(self) -> dict[str, float]:
        """Get all source weights.

        Returns:
            Dictionary of source -> weight
        """
        return dict(sorted(self.weights.items(), key=lambda x: x[1], reverse=True))

    def categorize_source(self, source: str) -> dict[str, Any]:
        """Categorize a source by reliability tier.

        Args:
            source: Source name

        Returns:
            Category information
        """
        weight = self.get_weight(source)

        if weight >= 0.9:
            tier = "official"
            description = "Official/regulatory source - highest reliability"
        elif weight >= 0.8:
            tier = "professional"
            description = "Professional news source - high reliability"
        elif weight >= 0.65:
            tier = "financial_media"
            description = "Financial media - moderate reliability"
        elif weight >= 0.5:
            tier = "social"
            description = "Social/community source - requires verification"
        else:
            tier = "unverified"
            description = "Unverified source - use with caution"

        return {
            "source": source,
            "weight": weight,
            "tier": tier,
            "description": description,
        }

    def adjust_for_verification(
        self,
        source: str,
        is_verified: bool = False,
        has_sec_link: bool = False,
        has_official_source: bool = False,
    ) -> float:
        """Adjust weight based on verification status.

        Args:
            source: Source name
            is_verified: Whether content is verified
            has_sec_link: Whether it links to SEC filing
            has_official_source: Whether it cites official source

        Returns:
            Adjusted weight
        """
        base_weight = self.get_weight(source)

        # Boost for verification
        if is_verified:
            base_weight = min(1.0, base_weight * 1.1)

        if has_sec_link:
            base_weight = min(1.0, base_weight * 1.15)

        if has_official_source:
            base_weight = min(1.0, base_weight * 1.08)

        return base_weight
