"""Sub-category classification for financial events."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import structlog

from .event_classifier import EventType

logger = structlog.get_logger(__name__)


class InsiderSubCategory(str, Enum):
    """Sub-categories for insider trading events."""

    BUY = "buy"
    SELL = "sell"
    OPTIONS_EXERCISE = "options_exercise"
    GIFT = "gift"
    AUTOMATIC_PLAN = "automatic_plan"  # 10b5-1 plans
    FORFEITURE = "forfeiture"
    UNKNOWN = "unknown"


class EarningsSubCategory(str, Enum):
    """Sub-categories for earnings events."""

    BEAT = "beat"
    MISS = "miss"
    MEET = "meet"  # In-line with expectations
    GUIDANCE_RAISED = "guidance_raised"
    GUIDANCE_LOWERED = "guidance_lowered"
    GUIDANCE_MAINTAINED = "guidance_maintained"
    PREANNOUNCE = "preannounce"
    UNKNOWN = "unknown"


class FDASubCategory(str, Enum):
    """Sub-categories for FDA events."""

    APPROVAL = "approval"
    REJECTION = "rejection"
    DELAY = "delay"
    CRL = "complete_response_letter"  # Complete Response Letter
    PRIORITY_REVIEW = "priority_review"
    BREAKTHROUGH = "breakthrough_designation"
    FAST_TRACK = "fast_track"
    ADVISORY_POSITIVE = "advisory_positive"
    ADVISORY_NEGATIVE = "advisory_negative"
    UNKNOWN = "unknown"


class MAndASubCategory(str, Enum):
    """Sub-categories for M&A events."""

    ACQUISITION = "acquisition"
    MERGER = "merger"
    DIVESTITURE = "divestiture"
    SPINOFF = "spinoff"
    TAKEOVER_HOSTILE = "takeover_hostile"
    TAKEOVER_FRIENDLY = "takeover_friendly"
    JOINT_VENTURE = "joint_venture"
    STRATEGIC_INVESTMENT = "strategic_investment"
    UNKNOWN = "unknown"


class OfferingSubCategory(str, Enum):
    """Sub-categories for offering/dilution events."""

    SECONDARY = "secondary"
    PRIMARY = "primary"
    PRIVATE_PLACEMENT = "private_placement"
    ATM = "at_the_market"
    PIPE = "pipe"  # Private Investment in Public Equity
    RIGHTS_OFFERING = "rights_offering"
    IPO = "ipo"
    DIRECT_LISTING = "direct_listing"
    SPAC = "spac"
    UNKNOWN = "unknown"


class ClinicalTrialSubCategory(str, Enum):
    """Sub-categories for clinical trial events."""

    PHASE_1_INITIATED = "phase_1_initiated"
    PHASE_1_RESULTS = "phase_1_results"
    PHASE_2_INITIATED = "phase_2_initiated"
    PHASE_2_RESULTS = "phase_2_results"
    PHASE_3_INITIATED = "phase_3_initiated"
    PHASE_3_RESULTS = "phase_3_results"
    POSITIVE_RESULTS = "positive_results"
    NEGATIVE_RESULTS = "negative_results"
    INTERIM_DATA = "interim_data"
    TRIAL_HALTED = "trial_halted"
    ENDPOINT_MET = "endpoint_met"
    ENDPOINT_MISSED = "endpoint_missed"
    UNKNOWN = "unknown"


@dataclass
class SubCategoryResult:
    """Result of sub-category classification."""

    event_type: EventType
    sub_category: str
    confidence: float
    matched_patterns: list[str]
    details: dict[str, Any]


class SubCategoryClassifier:
    """Classify events into sub-categories."""

    # Insider trade patterns
    INSIDER_PATTERNS = {
        InsiderSubCategory.BUY: [
            r"\b(purchase|purchased|buying|bought|acquired|acquisition)\b",
            r"\bopen\s+market\s+(purchase|buy)\b",
            r"\bdirect\s+purchase\b",
        ],
        InsiderSubCategory.SELL: [
            r"\b(sale|sold|selling|disposed|disposition|liquidat)\b",
            r"\bopen\s+market\s+sale\b",
        ],
        InsiderSubCategory.OPTIONS_EXERCISE: [
            r"\b(option|options)\s+(exercise|exercised)\b",
            r"\bexercise\s+of\s+(stock\s+)?options\b",
            r"\bconversion\s+of\s+(derivative|options)\b",
            r"\bstock\s+option\s+(exercise|conversion)\b",
        ],
        InsiderSubCategory.GIFT: [
            r"\b(gift|gifted|donation|donated|charitable)\b",
            r"\btransfer\s+by\s+gift\b",
            r"\bbona\s+fide\s+gift\b",
        ],
        InsiderSubCategory.AUTOMATIC_PLAN: [
            r"\b10b5-1\b",
            r"\b10b-5-1\b",
            r"\brule\s+10b5-1\b",
            r"\bpre-?arranged\s+(trading\s+)?plan\b",
            r"\bautomatic\s+(trading\s+)?plan\b",
        ],
        InsiderSubCategory.FORFEITURE: [
            r"\b(forfeit|forfeited|forfeiture|cancelled|canceled)\b",
            r"\bfailed\s+to\s+vest\b",
        ],
    }

    # Earnings patterns
    EARNINGS_PATTERNS = {
        EarningsSubCategory.BEAT: [
            r"\b(beat|beats|exceeded|surpassed|topped|outperformed)\b",
            r"\babove\s+(consensus|expectations|estimates)\b",
            r"\bbetter\s+than\s+expected\b",
            r"\bupside\s+surprise\b",
            r"\bstrong(er)?\s+(results|quarter|earnings)\b",
        ],
        EarningsSubCategory.MISS: [
            r"\b(miss|missed|below|under|short|shortfall)\b",
            r"\bdisappoint(ed|ing|ment)?\b",
            r"\bworse\s+than\s+expected\b",
            r"\bdownside\b",
            r"\bweak(er)?\s+(results|quarter|earnings)\b",
        ],
        EarningsSubCategory.MEET: [
            r"\b(met|meets|in-?line|inline)\b",
            r"\bmatched\s+(expectations|estimates)\b",
            r"\bas\s+expected\b",
        ],
        EarningsSubCategory.GUIDANCE_RAISED: [
            r"\b(guidance|outlook)\s+(raised|increased|lifted|boosted)\b",
            r"\brais(ed|es|ing)\s+(guidance|outlook|forecast)\b",
            r"\bupward\s+revision\b",
            r"\bhigher\s+guidance\b",
        ],
        EarningsSubCategory.GUIDANCE_LOWERED: [
            r"\b(guidance|outlook)\s+(lowered|reduced|cut|decreased)\b",
            r"\blower(ed|s|ing)\s+(guidance|outlook|forecast)\b",
            r"\bdownward\s+revision\b",
            r"\bwarning\b",
        ],
        EarningsSubCategory.GUIDANCE_MAINTAINED: [
            r"\b(guidance|outlook)\s+(maintained|reaffirmed|reiterated|unchanged)\b",
            r"\bmaintain(ed|s|ing)\s+(guidance|outlook)\b",
        ],
        EarningsSubCategory.PREANNOUNCE: [
            r"\bpre-?announce\b",
            r"\bpreliminary\s+(results|earnings)\b",
            r"\b(profit|earnings)\s+warning\b",
        ],
    }

    # FDA patterns
    FDA_PATTERNS = {
        FDASubCategory.APPROVAL: [
            r"\bfda\s+(approval|approved|approves|clears|clearance)\b",
            r"\b(nda|bla|pma|510k)\s+(approval|approved)\b",
            r"\bgreen\s+light\b",
        ],
        FDASubCategory.REJECTION: [
            r"\bfda\s+(reject|rejected|rejects|decline|declined|refuses)\b",
            r"\bapproval\s+(denied|rejected)\b",
            r"\bnot\s+approv(ed|able)\b",
        ],
        FDASubCategory.DELAY: [
            r"\bfda\s+(delay|delayed|postpone|postponed)\b",
            r"\bpdufa\s+(date\s+)?(delay|extended|pushed)\b",
            r"\breview\s+(extended|delayed)\b",
            r"\brequests?\s+additional\s+(data|information|time)\b",
        ],
        FDASubCategory.CRL: [
            r"\bcomplete\s+response\s+letter\b",
            r"\bcrl\b",
            r"\brefuse\s+to\s+file\b",
        ],
        FDASubCategory.PRIORITY_REVIEW: [
            r"\bpriority\s+review\b",
            r"\baccelerated\s+approval\b",
        ],
        FDASubCategory.BREAKTHROUGH: [
            r"\bbreakthrough\s+(therapy\s+)?designation\b",
            r"\bbreakthrough\s+status\b",
        ],
        FDASubCategory.FAST_TRACK: [
            r"\bfast\s+track\b",
            r"\bexpedited\s+review\b",
        ],
        FDASubCategory.ADVISORY_POSITIVE: [
            r"\badvisory\s+(committee|panel).{0,30}(recommends?|favorable|positive|votes?\s+(yes|for))\b",
            r"\badcom.{0,30}(positive|favorable)\b",
        ],
        FDASubCategory.ADVISORY_NEGATIVE: [
            r"\badvisory\s+(committee|panel).{0,30}(against|negative|votes?\s+(no|against))\b",
            r"\badcom.{0,30}(negative|against)\b",
        ],
    }

    # M&A patterns
    MA_PATTERNS = {
        MAndASubCategory.ACQUISITION: [
            r"\b(acquir(e|es|ed|ing)|acquisition|takeover|buyout)\b",
            r"\bto\s+be\s+acquired\b",
            r"\bbuy(s|ing)?\s+(out|company|business)\b",
        ],
        MAndASubCategory.MERGER: [
            r"\bmerger\b",
            r"\bmerge(s|d|ing)?\s+with\b",
            r"\bmerger\s+of\s+equals\b",
            r"\bcombine\s+(operations|businesses)\b",
        ],
        MAndASubCategory.DIVESTITURE: [
            r"\bdivest(iture|s|ed|ing)?\b",
            r"\bsell(s|ing)?\s+(unit|division|business|subsidiary)\b",
            r"\bdispos(e|es|ed|ing|al)\b",
        ],
        MAndASubCategory.SPINOFF: [
            r"\bspin-?off\b",
            r"\bseparation\s+(of|into)\b",
            r"\bcarve-?out\b",
        ],
        MAndASubCategory.TAKEOVER_HOSTILE: [
            r"\bhostile\s+(takeover|bid|offer)\b",
            r"\bunsolicited\s+(bid|offer|proposal)\b",
            r"\bpoison\s+pill\b",
        ],
        MAndASubCategory.TAKEOVER_FRIENDLY: [
            r"\bfriendly\s+(takeover|merger|deal)\b",
            r"\bnegotiated\s+deal\b",
            r"\bagreed\s+merger\b",
        ],
        MAndASubCategory.JOINT_VENTURE: [
            r"\bjoint\s+venture\b",
            r"\bjv\b",
            r"\bstrategic\s+partnership\b",
        ],
        MAndASubCategory.STRATEGIC_INVESTMENT: [
            r"\bstrategic\s+investment\b",
            r"\bminority\s+(stake|investment)\b",
        ],
    }

    # Offering patterns
    OFFERING_PATTERNS = {
        OfferingSubCategory.SECONDARY: [
            r"\bsecondary\s+offering\b",
            r"\bfollow-?on\s+offering\b",
            r"\bseasoned\s+offering\b",
        ],
        OfferingSubCategory.PRIMARY: [
            r"\bprimary\s+offering\b",
            r"\bnew\s+share\s+issuance\b",
        ],
        OfferingSubCategory.PRIVATE_PLACEMENT: [
            r"\bprivate\s+placement\b",
            r"\bprivately\s+placed\b",
            r"\breg\s+d\b",
        ],
        OfferingSubCategory.ATM: [
            r"\bat-?the-?market\b",
            r"\batm\s+offering\b",
        ],
        OfferingSubCategory.PIPE: [
            r"\bpipe\b",
            r"\bprivate\s+investment\s+in\s+public\s+equity\b",
        ],
        OfferingSubCategory.RIGHTS_OFFERING: [
            r"\brights\s+offering\b",
            r"\brights\s+issue\b",
        ],
        OfferingSubCategory.IPO: [
            r"\bipo\b",
            r"\binitial\s+public\s+offering\b",
            r"\bgoing\s+public\b",
        ],
        OfferingSubCategory.DIRECT_LISTING: [
            r"\bdirect\s+listing\b",
            r"\bdirect\s+floor\s+listing\b",
        ],
        OfferingSubCategory.SPAC: [
            r"\bspac\b",
            r"\bspecial\s+purpose\s+acquisition\b",
            r"\bblank\s+check\s+company\b",
            r"\bde-?spac\b",
        ],
    }

    # Clinical trial patterns
    CLINICAL_PATTERNS = {
        ClinicalTrialSubCategory.PHASE_1_INITIATED: [
            r"\bphase\s*1\b.{0,30}\b(initiat|begin|start|commenc|launch)\b",
            r"\b(initiat|begin|start|commenc|launch).{0,30}\bphase\s*1\b",
            r"\bfirst\s+patient\s+(dosed|enrolled).{0,30}phase\s*1\b",
        ],
        ClinicalTrialSubCategory.PHASE_1_RESULTS: [
            r"\bphase\s*1\b.{0,30}\b(results?|data|readout)\b",
            r"\b(results?|data|readout).{0,30}\bphase\s*1\b",
        ],
        ClinicalTrialSubCategory.PHASE_2_INITIATED: [
            r"\bphase\s*2\b.{0,30}\b(initiat|begin|start|commenc|launch)\b",
            r"\b(initiat|begin|start|commenc|launch).{0,30}\bphase\s*2\b",
        ],
        ClinicalTrialSubCategory.PHASE_2_RESULTS: [
            r"\bphase\s*2\b.{0,30}\b(results?|data|readout)\b",
            r"\b(results?|data|readout).{0,30}\bphase\s*2\b",
        ],
        ClinicalTrialSubCategory.PHASE_3_INITIATED: [
            r"\bphase\s*3\b.{0,30}\b(initiat|begin|start|commenc|launch)\b",
            r"\b(initiat|begin|start|commenc|launch).{0,30}\bphase\s*3\b",
            r"\bpivotal\s+(trial|study)\s+(initiat|begin|start)\b",
        ],
        ClinicalTrialSubCategory.PHASE_3_RESULTS: [
            r"\bphase\s*3\b.{0,30}\b(results?|data|readout)\b",
            r"\b(results?|data|readout).{0,30}\bphase\s*3\b",
            r"\bpivotal\s+(trial|study)\s+(results?|data)\b",
        ],
        ClinicalTrialSubCategory.POSITIVE_RESULTS: [
            r"\b(positive|favorable|promising|successful)\s+(results?|data|outcome)\b",
            r"\b(results?|data).{0,20}(positive|favorable|promising)\b",
            r"\bdemonstrat(ed|es)\s+efficacy\b",
            r"\bstatistically\s+significant\b",
        ],
        ClinicalTrialSubCategory.NEGATIVE_RESULTS: [
            r"\b(negative|disappointing|failed|unsuccessful)\s+(results?|data|outcome)\b",
            r"\b(results?|data).{0,20}(negative|disappointing)\b",
            r"\bfailed\s+to\s+(show|demonstrate|meet)\b",
            r"\bnot\s+statistically\s+significant\b",
        ],
        ClinicalTrialSubCategory.INTERIM_DATA: [
            r"\binterim\s+(data|results?|analysis)\b",
            r"\bpreliminary\s+(data|results?)\b",
        ],
        ClinicalTrialSubCategory.TRIAL_HALTED: [
            r"\btrial\s+(halt|stopped|terminated|discontinued)\b",
            r"\b(halt|stop|terminat|discontinu).{0,20}trial\b",
            r"\bclinical\s+hold\b",
        ],
        ClinicalTrialSubCategory.ENDPOINT_MET: [
            r"\b(primary\s+)?endpoint\s+(met|achieved|reached)\b",
            r"\bmet\s+(primary\s+)?endpoint\b",
            r"\bachieved\s+primary\s+(efficacy\s+)?endpoint\b",
        ],
        ClinicalTrialSubCategory.ENDPOINT_MISSED: [
            r"\b(primary\s+)?endpoint\s+(missed|not\s+met|failed)\b",
            r"\bfailed\s+to\s+meet\s+(primary\s+)?endpoint\b",
            r"\bdid\s+not\s+meet\s+(primary\s+)?endpoint\b",
        ],
    }

    def __init__(self):
        """Initialize sub-category classifier."""
        # Compile all patterns
        self._compiled_patterns = {}

        for category, patterns_dict in [
            ("insider", self.INSIDER_PATTERNS),
            ("earnings", self.EARNINGS_PATTERNS),
            ("fda", self.FDA_PATTERNS),
            ("ma", self.MA_PATTERNS),
            ("offering", self.OFFERING_PATTERNS),
            ("clinical", self.CLINICAL_PATTERNS),
        ]:
            self._compiled_patterns[category] = {
                sub_cat: [
                    re.compile(pattern, re.IGNORECASE)
                    for pattern in patterns
                ]
                for sub_cat, patterns in patterns_dict.items()
            }

    def classify(self, text: str, event_type: EventType) -> SubCategoryResult:
        """Classify an event into sub-categories.

        Args:
            text: Text to classify
            event_type: Main event type

        Returns:
            SubCategoryResult
        """
        text_lower = text.lower()

        # Route to appropriate sub-category classifier
        if event_type in (EventType.INSIDER_BUY, EventType.INSIDER_SELL):
            return self._classify_insider(text_lower, event_type)
        elif event_type in (
            EventType.EARNINGS_BEAT,
            EventType.EARNINGS_MISS,
            EventType.EARNINGS_ANNOUNCE,
        ):
            return self._classify_earnings(text_lower, event_type)
        elif event_type in (EventType.FDA_APPROVAL, EventType.FDA_REJECTION):
            return self._classify_fda(text_lower, event_type)
        elif event_type in (
            EventType.ACQUISITION,
            EventType.MERGER,
            EventType.SPINOFF,
        ):
            return self._classify_ma(text_lower, event_type)
        elif event_type == EventType.OFFERING:
            return self._classify_offering(text_lower, event_type)
        elif event_type == EventType.CLINICAL_TRIAL:
            return self._classify_clinical(text_lower, event_type)
        else:
            # No sub-category for this event type
            return SubCategoryResult(
                event_type=event_type,
                sub_category="none",
                confidence=1.0,
                matched_patterns=[],
                details={},
            )

    def _classify_insider(
        self,
        text: str,
        event_type: EventType,
    ) -> SubCategoryResult:
        """Classify insider trading sub-category."""
        matches = self._match_patterns(text, "insider")

        # Default based on event type
        if event_type == EventType.INSIDER_BUY:
            default_sub = InsiderSubCategory.BUY
        else:
            default_sub = InsiderSubCategory.SELL

        if not matches:
            return SubCategoryResult(
                event_type=event_type,
                sub_category=default_sub.value,
                confidence=0.7,
                matched_patterns=[],
                details={"inferred": True},
            )

        # Get best match
        best_match = max(matches, key=lambda x: x[1])
        sub_category = best_match[0]
        confidence = best_match[1]
        patterns = [m[2] for m in matches if m[0] == sub_category]

        # Extract transaction details
        details = self._extract_transaction_details(text)

        return SubCategoryResult(
            event_type=event_type,
            sub_category=sub_category.value,
            confidence=confidence,
            matched_patterns=patterns,
            details=details,
        )

    def _classify_earnings(
        self,
        text: str,
        event_type: EventType,
    ) -> SubCategoryResult:
        """Classify earnings sub-category."""
        matches = self._match_patterns(text, "earnings")

        # Check for guidance in addition to beat/miss
        guidance_matches = [m for m in matches if "guidance" in m[0].value]
        result_matches = [m for m in matches if "guidance" not in m[0].value]

        # Default based on event type
        if event_type == EventType.EARNINGS_BEAT:
            default_sub = EarningsSubCategory.BEAT
        elif event_type == EventType.EARNINGS_MISS:
            default_sub = EarningsSubCategory.MISS
        else:
            default_sub = EarningsSubCategory.UNKNOWN

        if not result_matches:
            sub_category = default_sub
            confidence = 0.7
            patterns = []
        else:
            best = max(result_matches, key=lambda x: x[1])
            sub_category = best[0]
            confidence = best[1]
            patterns = [m[2] for m in result_matches if m[0] == sub_category]

        details = {}

        # Add guidance info if present
        if guidance_matches:
            guidance_best = max(guidance_matches, key=lambda x: x[1])
            details["guidance"] = guidance_best[0].value
            details["guidance_confidence"] = guidance_best[1]

        return SubCategoryResult(
            event_type=event_type,
            sub_category=sub_category.value,
            confidence=confidence,
            matched_patterns=patterns,
            details=details,
        )

    def _classify_fda(
        self,
        text: str,
        event_type: EventType,
    ) -> SubCategoryResult:
        """Classify FDA sub-category."""
        matches = self._match_patterns(text, "fda")

        # Default based on event type
        if event_type == EventType.FDA_APPROVAL:
            default_sub = FDASubCategory.APPROVAL
        else:
            default_sub = FDASubCategory.REJECTION

        if not matches:
            return SubCategoryResult(
                event_type=event_type,
                sub_category=default_sub.value,
                confidence=0.7,
                matched_patterns=[],
                details={},
            )

        # Get best match
        best_match = max(matches, key=lambda x: x[1])
        sub_category = best_match[0]
        confidence = best_match[1]
        patterns = [m[2] for m in matches if m[0] == sub_category]

        return SubCategoryResult(
            event_type=event_type,
            sub_category=sub_category.value,
            confidence=confidence,
            matched_patterns=patterns,
            details={},
        )

    def _classify_ma(
        self,
        text: str,
        event_type: EventType,
    ) -> SubCategoryResult:
        """Classify M&A sub-category."""
        matches = self._match_patterns(text, "ma")

        # Default based on event type
        if event_type == EventType.ACQUISITION:
            default_sub = MAndASubCategory.ACQUISITION
        elif event_type == EventType.MERGER:
            default_sub = MAndASubCategory.MERGER
        else:
            default_sub = MAndASubCategory.SPINOFF

        if not matches:
            return SubCategoryResult(
                event_type=event_type,
                sub_category=default_sub.value,
                confidence=0.7,
                matched_patterns=[],
                details={},
            )

        best_match = max(matches, key=lambda x: x[1])
        sub_category = best_match[0]
        confidence = best_match[1]
        patterns = [m[2] for m in matches if m[0] == sub_category]

        # Extract deal value if present
        details = self._extract_deal_value(text)

        return SubCategoryResult(
            event_type=event_type,
            sub_category=sub_category.value,
            confidence=confidence,
            matched_patterns=patterns,
            details=details,
        )

    def _classify_offering(
        self,
        text: str,
        event_type: EventType,
    ) -> SubCategoryResult:
        """Classify offering sub-category."""
        matches = self._match_patterns(text, "offering")

        if not matches:
            return SubCategoryResult(
                event_type=event_type,
                sub_category=OfferingSubCategory.UNKNOWN.value,
                confidence=0.5,
                matched_patterns=[],
                details={},
            )

        best_match = max(matches, key=lambda x: x[1])
        sub_category = best_match[0]
        confidence = best_match[1]
        patterns = [m[2] for m in matches if m[0] == sub_category]

        # Extract offering details
        details = self._extract_offering_details(text)

        return SubCategoryResult(
            event_type=event_type,
            sub_category=sub_category.value,
            confidence=confidence,
            matched_patterns=patterns,
            details=details,
        )

    def _classify_clinical(
        self,
        text: str,
        event_type: EventType,
    ) -> SubCategoryResult:
        """Classify clinical trial sub-category."""
        matches = self._match_patterns(text, "clinical")

        if not matches:
            return SubCategoryResult(
                event_type=event_type,
                sub_category=ClinicalTrialSubCategory.UNKNOWN.value,
                confidence=0.5,
                matched_patterns=[],
                details={},
            )

        # For clinical trials, we might have multiple relevant sub-categories
        # (e.g., phase + result type)
        best_match = max(matches, key=lambda x: x[1])
        sub_category = best_match[0]
        confidence = best_match[1]
        patterns = [m[2] for m in matches if m[0] == sub_category]

        # Check for result indicators
        details = {}
        positive_matches = [
            m for m in matches
            if m[0] in (
                ClinicalTrialSubCategory.POSITIVE_RESULTS,
                ClinicalTrialSubCategory.ENDPOINT_MET,
            )
        ]
        negative_matches = [
            m for m in matches
            if m[0] in (
                ClinicalTrialSubCategory.NEGATIVE_RESULTS,
                ClinicalTrialSubCategory.ENDPOINT_MISSED,
                ClinicalTrialSubCategory.TRIAL_HALTED,
            )
        ]

        if positive_matches:
            details["sentiment"] = "positive"
        elif negative_matches:
            details["sentiment"] = "negative"

        return SubCategoryResult(
            event_type=event_type,
            sub_category=sub_category.value,
            confidence=confidence,
            matched_patterns=patterns,
            details=details,
        )

    def _match_patterns(
        self,
        text: str,
        category: str,
    ) -> list[tuple[Any, float, str]]:
        """Match patterns for a category.

        Args:
            text: Text to match
            category: Pattern category

        Returns:
            List of (sub_category, confidence, pattern) tuples
        """
        matches = []

        for sub_cat, patterns in self._compiled_patterns.get(category, {}).items():
            for pattern in patterns:
                if pattern.search(text):
                    # Higher confidence for more specific patterns
                    pattern_len = len(pattern.pattern)
                    confidence = min(0.95, 0.7 + pattern_len / 100)
                    matches.append((sub_cat, confidence, pattern.pattern))

        return matches

    def _extract_transaction_details(self, text: str) -> dict[str, Any]:
        """Extract transaction details from insider trading text."""
        details = {}

        # Try to extract share count
        share_match = re.search(
            r"(\d{1,3}(?:,\d{3})*|\d+)\s*(shares?|common\s+stock)",
            text,
            re.IGNORECASE,
        )
        if share_match:
            try:
                details["shares"] = int(share_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # Try to extract price
        price_match = re.search(
            r"\$(\d+(?:\.\d{2})?)\s*(per\s+share)?",
            text,
            re.IGNORECASE,
        )
        if price_match:
            try:
                details["price"] = float(price_match.group(1))
            except ValueError:
                pass

        # Try to extract total value
        value_match = re.search(
            r"\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(worth|value|total)",
            text,
            re.IGNORECASE,
        )
        if value_match:
            try:
                details["value"] = float(value_match.group(1).replace(",", ""))
            except ValueError:
                pass

        return details

    def _extract_deal_value(self, text: str) -> dict[str, Any]:
        """Extract deal value from M&A text."""
        details = {}

        # Try to extract deal value (billions or millions)
        value_match = re.search(
            r"\$(\d+(?:\.\d+)?)\s*(billion|million|B|M)\b",
            text,
            re.IGNORECASE,
        )
        if value_match:
            try:
                value = float(value_match.group(1))
                unit = value_match.group(2).lower()
                if unit in ("billion", "b"):
                    value *= 1_000_000_000
                elif unit in ("million", "m"):
                    value *= 1_000_000
                details["deal_value"] = value
            except ValueError:
                pass

        # Try to extract premium
        premium_match = re.search(
            r"(\d+(?:\.\d+)?)\s*%\s*premium",
            text,
            re.IGNORECASE,
        )
        if premium_match:
            try:
                details["premium_percent"] = float(premium_match.group(1))
            except ValueError:
                pass

        return details

    def _extract_offering_details(self, text: str) -> dict[str, Any]:
        """Extract offering details from text."""
        details = {}

        # Try to extract share count
        share_match = re.search(
            r"(\d{1,3}(?:,\d{3})*|\d+)\s*(million\s+)?(shares?|units?)",
            text,
            re.IGNORECASE,
        )
        if share_match:
            try:
                shares = int(share_match.group(1).replace(",", ""))
                if share_match.group(2):  # "million"
                    shares *= 1_000_000
                details["shares"] = shares
            except ValueError:
                pass

        # Try to extract price
        price_match = re.search(
            r"(priced|pricing|at)\s+\$(\d+(?:\.\d{2})?)",
            text,
            re.IGNORECASE,
        )
        if price_match:
            try:
                details["price"] = float(price_match.group(2))
            except ValueError:
                pass

        # Try to extract proceeds
        proceeds_match = re.search(
            r"(gross\s+)?proceeds\s+of\s+\$(\d+(?:\.\d+)?)\s*(million|billion)?",
            text,
            re.IGNORECASE,
        )
        if proceeds_match:
            try:
                proceeds = float(proceeds_match.group(2))
                unit = (proceeds_match.group(3) or "").lower()
                if unit == "billion":
                    proceeds *= 1_000_000_000
                elif unit == "million":
                    proceeds *= 1_000_000
                details["proceeds"] = proceeds
            except ValueError:
                pass

        return details


# Module-level convenience function
def classify_subcategory(text: str, event_type: EventType) -> SubCategoryResult:
    """Convenience function to classify event sub-category.

    Args:
        text: Text to classify
        event_type: Main event type

    Returns:
        SubCategoryResult
    """
    classifier = SubCategoryClassifier()
    return classifier.classify(text, event_type)
