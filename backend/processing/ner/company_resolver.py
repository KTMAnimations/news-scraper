"""Fuzzy company name resolution to ticker symbols."""

import re
from dataclasses import dataclass
from typing import Any

import structlog

from .knowledge_base import TickerKnowledgeBase

logger = structlog.get_logger(__name__)


@dataclass
class CompanyMatch:
    """A matched company name."""

    ticker: str
    company_name: str
    confidence: float
    match_type: str  # "exact", "normalized", "fuzzy", "alias"


class CompanyResolver:
    """Resolve company names to ticker symbols using fuzzy matching."""

    # Common suffixes to remove
    SUFFIXES = [
        r"\s+INC\.?$",
        r"\s+CORP\.?$",
        r"\s+CORPORATION$",
        r"\s+CO\.?$",
        r"\s+COMPANY$",
        r"\s+LTD\.?$",
        r"\s+LIMITED$",
        r"\s+LLC\.?$",
        r"\s+LP\.?$",
        r"\s+PLC\.?$",
        r"\s+SA\.?$",
        r"\s+AG\.?$",
        r"\s+NV\.?$",
        r"\s+BV\.?$",
        r",\s*INC\.?$",
        r",\s*LLC\.?$",
    ]

    # Common prefixes to remove
    PREFIXES = [
        r"^THE\s+",
    ]

    def __init__(
        self,
        knowledge_base: TickerKnowledgeBase,
        min_confidence: float = 0.7,
    ):
        """Initialize company resolver.

        Args:
            knowledge_base: Ticker knowledge base
            min_confidence: Minimum confidence for matches
        """
        self.kb = knowledge_base
        self.min_confidence = min_confidence
        self._normalized_cache: dict[str, str] = {}

    def normalize_name(self, name: str) -> str:
        """Normalize a company name for matching.

        Args:
            name: Company name

        Returns:
            Normalized name
        """
        if name in self._normalized_cache:
            return self._normalized_cache[name]

        normalized = name.upper().strip()

        # Remove suffixes
        for suffix in self.SUFFIXES:
            normalized = re.sub(suffix, "", normalized, flags=re.IGNORECASE)

        # Remove prefixes
        for prefix in self.PREFIXES:
            normalized = re.sub(prefix, "", normalized, flags=re.IGNORECASE)

        # Remove extra whitespace
        normalized = " ".join(normalized.split())

        # Remove special characters (keep spaces)
        normalized = re.sub(r"[^\w\s]", "", normalized)

        self._normalized_cache[name] = normalized
        return normalized

    def resolve(self, name: str) -> CompanyMatch | None:
        """Resolve a company name to a ticker.

        Args:
            name: Company name to resolve

        Returns:
            CompanyMatch or None
        """
        if not name or len(name) < 2:
            return None

        # Try exact match first
        match = self._exact_match(name)
        if match and match.confidence >= self.min_confidence:
            return match

        # Try normalized match
        match = self._normalized_match(name)
        if match and match.confidence >= self.min_confidence:
            return match

        # Try fuzzy match
        match = self._fuzzy_match(name)
        if match and match.confidence >= self.min_confidence:
            return match

        return None

    def _exact_match(self, name: str) -> CompanyMatch | None:
        """Try exact match against knowledge base.

        Args:
            name: Company name

        Returns:
            CompanyMatch or None
        """
        # Direct KB lookup
        ticker = self.kb.resolve_company_name(name)
        if ticker:
            return CompanyMatch(
                ticker=ticker,
                company_name=self.kb.get_company_name(ticker) or name,
                confidence=1.0,
                match_type="exact",
            )

        return None

    def _normalized_match(self, name: str) -> CompanyMatch | None:
        """Try matching with normalized names.

        Args:
            name: Company name

        Returns:
            CompanyMatch or None
        """
        normalized = self.normalize_name(name)

        # Try KB with normalized name
        ticker = self.kb.resolve_company_name(normalized)
        if ticker:
            return CompanyMatch(
                ticker=ticker,
                company_name=self.kb.get_company_name(ticker) or name,
                confidence=0.95,
                match_type="normalized",
            )

        return None

    def _fuzzy_match(self, name: str) -> CompanyMatch | None:
        """Try fuzzy matching.

        Args:
            name: Company name

        Returns:
            CompanyMatch or None
        """
        normalized = self.normalize_name(name)

        if len(normalized) < 3:
            return None

        # Search KB for partial matches
        results = self.kb.search_tickers(normalized[:10], limit=5)

        best_match = None
        best_score = 0.0

        for result in results:
            ticker = result["ticker"]
            kb_name = result.get("name", "")

            if not kb_name:
                continue

            kb_normalized = self.normalize_name(kb_name)

            # Calculate similarity
            score = self._calculate_similarity(normalized, kb_normalized)

            if score > best_score and score >= self.min_confidence:
                best_score = score
                best_match = CompanyMatch(
                    ticker=ticker,
                    company_name=kb_name,
                    confidence=score,
                    match_type="fuzzy",
                )

        return best_match

    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity.

        Uses simple containment and length ratio.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Similarity score (0-1)
        """
        if not s1 or not s2:
            return 0.0

        # Exact match
        if s1 == s2:
            return 1.0

        # One contains the other
        if s1 in s2:
            return 0.85 + (0.15 * len(s1) / len(s2))
        if s2 in s1:
            return 0.85 + (0.15 * len(s2) / len(s1))

        # Word overlap
        words1 = set(s1.split())
        words2 = set(s2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        jaccard = intersection / union

        # Bonus for first word matching
        first_word_match = s1.split()[0] == s2.split()[0] if s1.split() and s2.split() else False

        if first_word_match:
            jaccard = min(1.0, jaccard + 0.2)

        return jaccard

    def resolve_batch(self, names: list[str]) -> list[CompanyMatch | None]:
        """Resolve a batch of company names.

        Args:
            names: List of company names

        Returns:
            List of matches (or None for no match)
        """
        return [self.resolve(name) for name in names]

    def add_custom_mapping(self, name: str, ticker: str) -> None:
        """Add a custom company name mapping.

        Args:
            name: Company name or alias
            ticker: Ticker symbol
        """
        self.kb.add_alias(name, ticker)
        logger.info("Added custom company mapping", name=name, ticker=ticker)
