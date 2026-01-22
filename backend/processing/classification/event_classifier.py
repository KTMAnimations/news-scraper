"""Event classification for financial news."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class EventType(str, Enum):
    """Financial event types."""

    # Insider activity
    INSIDER_BUY = "INSIDER_BUY"
    INSIDER_SELL = "INSIDER_SELL"

    # Earnings
    EARNINGS_BEAT = "EARNINGS_BEAT"
    EARNINGS_MISS = "EARNINGS_MISS"
    EARNINGS_ANNOUNCE = "EARNINGS_ANNOUNCE"

    # Corporate actions
    ACQUISITION = "ACQUISITION"
    MERGER = "MERGER"
    SPINOFF = "SPINOFF"
    OFFERING = "OFFERING"
    BUYBACK = "BUYBACK"
    DIVIDEND = "DIVIDEND"
    SPLIT = "SPLIT"

    # FDA/Healthcare
    FDA_APPROVAL = "FDA_APPROVAL"
    FDA_REJECTION = "FDA_REJECTION"
    CLINICAL_TRIAL = "CLINICAL_TRIAL"

    # Regulatory
    SEC_FILING = "SEC_FILING"
    REGULATORY_ACTION = "REGULATORY_ACTION"
    LAWSUIT = "LAWSUIT"
    SETTLEMENT = "SETTLEMENT"

    # Activist/Institutional
    ACTIVIST_STAKE = "ACTIVIST_STAKE"
    INSTITUTIONAL_BUY = "INSTITUTIONAL_BUY"
    INSTITUTIONAL_SELL = "INSTITUTIONAL_SELL"

    # Management
    CEO_CHANGE = "CEO_CHANGE"
    EXECUTIVE_DEPARTURE = "EXECUTIVE_DEPARTURE"
    BOARD_CHANGE = "BOARD_CHANGE"

    # Market
    TIER_CHANGE = "TIER_CHANGE"
    DELISTING = "DELISTING"
    BANKRUPTCY = "BANKRUPTCY"

    # General
    PARTNERSHIP = "PARTNERSHIP"
    CONTRACT = "CONTRACT"
    PRODUCT_LAUNCH = "PRODUCT_LAUNCH"
    NEWS = "NEWS"
    SOCIAL_MENTION = "SOCIAL_MENTION"


@dataclass
class EventClassification:
    """Classification result for an event."""

    event_type: EventType
    confidence: float
    matched_patterns: list[str]
    is_material: bool  # Material event that moves prices
    base_signal_weight: float  # -1 to 1 base weight


class EventClassifier:
    """Classify financial events from text."""

    # Pattern -> (EventType, base_weight, is_material)
    CLASSIFICATION_RULES: list[tuple[str, EventType, float, bool]] = [
        # Insider activity (Form 4)
        (r"\bform\s*4\b.*\b(purchase|acquired|bought)\b", EventType.INSIDER_BUY, 0.9, True),
        (r"\binsider\s+(buy|purchase|buying)\b", EventType.INSIDER_BUY, 0.9, True),
        (r"\bform\s*4\b.*\b(sale|sold|dispose)\b", EventType.INSIDER_SELL, -0.7, True),
        (r"\binsider\s+(sell|sale|selling)\b", EventType.INSIDER_SELL, -0.7, True),

        # Earnings
        (r"\b(beat|beats|exceeded|surpassed)\s+(earnings|estimates|expectations)\b", EventType.EARNINGS_BEAT, 0.8, True),
        (r"\bearnings\s+(beat|surpass)\b", EventType.EARNINGS_BEAT, 0.8, True),
        (r"\b(miss|missed|below)\s+(earnings|estimates|expectations)\b", EventType.EARNINGS_MISS, -0.8, True),
        (r"\bearnings\s+(miss|disappointment)\b", EventType.EARNINGS_MISS, -0.8, True),
        (r"\b(reports|announces)\s+(q[1-4]|quarterly|annual)\s+(earnings|results)\b", EventType.EARNINGS_ANNOUNCE, 0.0, True),

        # FDA/Healthcare
        (r"\bfda\s+(approval|approved|approves|clears|clearance)\b", EventType.FDA_APPROVAL, 0.95, True),
        (r"\b(drug|device|treatment)\s+approval\b", EventType.FDA_APPROVAL, 0.95, True),
        (r"\bfda\s+(rejection|rejected|rejects|crl|complete\s+response)\b", EventType.FDA_REJECTION, -0.95, True),
        (r"\b(phase\s+[123]|clinical\s+trial)\s+(results|data|success|positive)\b", EventType.CLINICAL_TRIAL, 0.7, True),
        (r"\b(phase\s+[123]|clinical\s+trial)\s+(failure|failed|negative)\b", EventType.CLINICAL_TRIAL, -0.8, True),

        # M&A
        (r"\b(acquires|acquired|acquisition|to\s+acquire)\b", EventType.ACQUISITION, 0.7, True),
        (r"\bmerger\s+(agreement|announced|with)\b", EventType.MERGER, 0.6, True),
        (r"\bspin\s*off\b", EventType.SPINOFF, 0.3, True),

        # Offerings/Dilution
        (r"\b(secondary|public|stock)\s+offering\b", EventType.OFFERING, -0.4, True),
        (r"\bprivate\s+placement\b", EventType.OFFERING, -0.3, True),
        (r"\bdilution\b", EventType.OFFERING, -0.5, True),

        # Buyback/Dividend
        (r"\b(share|stock)\s+(repurchase|buyback)\b", EventType.BUYBACK, 0.5, True),
        (r"\bdividend\s+(increase|raised|declared|announces)\b", EventType.DIVIDEND, 0.4, True),
        (r"\bdividend\s+(cut|suspended|eliminated)\b", EventType.DIVIDEND, -0.6, True),

        # Activist/13D
        (r"\b13-?d\b", EventType.ACTIVIST_STAKE, 0.6, True),
        (r"\bactivist\s+(stake|position|investor)\b", EventType.ACTIVIST_STAKE, 0.6, True),
        (r"\b(acquires|acquired|takes)\s+\d+%\s+(stake|position)\b", EventType.ACTIVIST_STAKE, 0.5, True),

        # Regulatory/Legal
        (r"\bsec\s+(investigation|charges|enforcement)\b", EventType.REGULATORY_ACTION, -0.8, True),
        (r"\b(lawsuit|sued|sues|litigation)\b", EventType.LAWSUIT, -0.5, True),
        (r"\bsettlement\s+(agreement|reached|announces)\b", EventType.SETTLEMENT, 0.2, True),

        # Management
        (r"\b(ceo|chief\s+executive)\s+(resign|departure|steps\s+down|leaves)\b", EventType.CEO_CHANGE, -0.3, True),
        (r"\b(appoints|names|hires)\s+(new\s+)?(ceo|chief\s+executive)\b", EventType.CEO_CHANGE, 0.2, True),
        (r"\b(cfo|coo|cto)\s+(resign|departure|leaves)\b", EventType.EXECUTIVE_DEPARTURE, -0.2, True),

        # Market/Listing
        (r"\b(delisting|delisted|delist)\b", EventType.DELISTING, -0.9, True),
        (r"\b(bankruptcy|chapter\s+(7|11)|insolvent)\b", EventType.BANKRUPTCY, -0.95, True),
        (r"\b(upgraded|uplisted)\s+to\s+(nasdaq|nyse|otcqx)\b", EventType.TIER_CHANGE, 0.6, True),
        (r"\b(downgraded|moved)\s+to\s+(otc|pink|grey)\b", EventType.TIER_CHANGE, -0.6, True),

        # Business
        (r"\b(partnership|strategic\s+alliance|collaboration)\s+(with|agreement)\b", EventType.PARTNERSHIP, 0.4, False),
        (r"\b(wins|awarded|receives)\s+(contract|deal|order)\b", EventType.CONTRACT, 0.5, True),
        (r"\b(launches|introduces|unveils)\s+(new\s+)?(product|service)\b", EventType.PRODUCT_LAUNCH, 0.3, False),
    ]

    def __init__(self):
        """Initialize event classifier."""
        # Compile patterns for efficiency
        self._compiled_rules = [
            (re.compile(pattern, re.IGNORECASE), event_type, weight, material)
            for pattern, event_type, weight, material in self.CLASSIFICATION_RULES
        ]

    def classify(self, text: str, source_type: str | None = None) -> EventClassification:
        """Classify text into event type.

        Args:
            text: Text to classify
            source_type: Optional source type hint (e.g., "sec_filing", "news")

        Returns:
            EventClassification result
        """
        text_lower = text.lower()
        matches = []

        # Check all patterns
        for pattern, event_type, weight, material in self._compiled_rules:
            if pattern.search(text_lower):
                matches.append((event_type, weight, material, pattern.pattern))

        if not matches:
            # Default to NEWS for unclassified
            return EventClassification(
                event_type=EventType.NEWS,
                confidence=0.5,
                matched_patterns=[],
                is_material=False,
                base_signal_weight=0.0,
            )

        # Use highest-weighted match as primary
        matches.sort(key=lambda x: abs(x[1]), reverse=True)
        primary = matches[0]

        # Calculate confidence based on pattern specificity and match count
        confidence = min(0.95, 0.6 + len(matches) * 0.1)

        return EventClassification(
            event_type=primary[0],
            confidence=confidence,
            matched_patterns=[m[3] for m in matches],
            is_material=primary[2],
            base_signal_weight=primary[1],
        )

    def classify_filing(self, filing_type: str, content: str | None = None) -> EventClassification:
        """Classify based on SEC filing type.

        Args:
            filing_type: SEC filing type (e.g., "4", "8-K", "10-Q")
            content: Optional filing content for deeper analysis

        Returns:
            EventClassification result
        """
        # Default classifications by filing type
        filing_defaults = {
            "4": (EventType.SEC_FILING, 0.6, True),  # Form 4 - will be refined by content
            "8-K": (EventType.SEC_FILING, 0.5, True),  # 8-K - material events
            "10-Q": (EventType.EARNINGS_ANNOUNCE, 0.0, True),  # Quarterly report
            "10-K": (EventType.EARNINGS_ANNOUNCE, 0.0, True),  # Annual report
            "13D": (EventType.ACTIVIST_STAKE, 0.6, True),  # Activist stake
            "13G": (EventType.INSTITUTIONAL_BUY, 0.3, True),  # Passive stake
            "S-1": (EventType.OFFERING, -0.3, True),  # IPO registration
            "424B": (EventType.OFFERING, -0.3, True),  # Prospectus
        }

        default = filing_defaults.get(filing_type, (EventType.SEC_FILING, 0.0, False))

        # If we have content, try to classify more precisely
        if content:
            content_classification = self.classify(content)
            if content_classification.confidence > 0.7:
                return content_classification

        return EventClassification(
            event_type=default[0],
            confidence=0.7,
            matched_patterns=[f"filing_type:{filing_type}"],
            is_material=default[2],
            base_signal_weight=default[1],
        )


def classify_event(text: str, source_type: str | None = None) -> EventClassification:
    """Convenience function to classify an event.

    Args:
        text: Text to classify
        source_type: Optional source type hint

    Returns:
        EventClassification
    """
    classifier = EventClassifier()
    return classifier.classify(text, source_type)
