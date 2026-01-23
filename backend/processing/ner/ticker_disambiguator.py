"""Ticker disambiguation to distinguish company names from tickers.

This module provides context-aware ticker extraction to handle ambiguous cases
like "APPLE" (fruit) vs "AAPL" (Apple Inc.) or "META" (general word) vs "META" (Meta Platforms).
"""

import re
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class DisambiguatedTicker:
    """A ticker that has been disambiguated."""

    ticker: str
    confidence: float  # 0-1 confidence this is actually a ticker
    source_text: str  # Original text that led to this ticker
    disambiguation_reason: str  # Why we think it's a ticker
    context: str | None = None  # Surrounding context
    company_name: str | None = None  # Resolved company name


class TickerDisambiguator:
    """Disambiguate company names from ticker symbols using context analysis.

    Handles cases like:
    - "APPLE" could be the fruit or AAPL stock
    - "META" could be a prefix/general word or Meta Platforms stock
    - "FORD" could be the car company or a person's name
    """

    # Common words that are also valid tickers - need extra context
    AMBIGUOUS_TICKERS = {
        # Tech
        "META": {"ticker": "META", "company": "META PLATFORMS"},
        "SNAP": {"ticker": "SNAP", "company": "SNAP INC"},
        "UBER": {"ticker": "UBER", "company": "UBER TECHNOLOGIES"},
        "ZOOM": {"ticker": "ZM", "company": "ZOOM VIDEO"},
        "BLOCK": {"ticker": "SQ", "company": "BLOCK INC"},

        # Common words
        "FORD": {"ticker": "F", "company": "FORD MOTOR"},
        "GAP": {"ticker": "GPS", "company": "GAP INC"},
        "VISA": {"ticker": "V", "company": "VISA INC"},
        "ORACLE": {"ticker": "ORCL", "company": "ORACLE"},
        "TARGET": {"ticker": "TGT", "company": "TARGET"},
        "DISH": {"ticker": "DISH", "company": "DISH NETWORK"},
        "SPRINT": {"ticker": "S", "company": "SPRINT"},
        "DELTA": {"ticker": "DAL", "company": "DELTA AIR LINES"},
        "UNITED": {"ticker": "UAL", "company": "UNITED AIRLINES"},
        "AMERICAN": {"ticker": "AAL", "company": "AMERICAN AIRLINES"},
        "MARATHON": {"ticker": "MPC", "company": "MARATHON PETROLEUM"},
        "DISCOVER": {"ticker": "DFS", "company": "DISCOVER FINANCIAL"},

        # Food/Consumer - often confused with products
        "APPLE": {"ticker": "AAPL", "company": "APPLE INC"},
        "PEPSI": {"ticker": "PEP", "company": "PEPSICO"},
        "COKE": {"ticker": "KO", "company": "COCA-COLA"},
        "HERSHEY": {"ticker": "HSY", "company": "HERSHEY"},
        "KELLOGG": {"ticker": "K", "company": "KELLOGG"},
        "CAMPBELL": {"ticker": "CPB", "company": "CAMPBELL SOUP"},
        "GENERAL": {"ticker": None, "company": None},  # Too ambiguous alone
        "DOLLAR": {"ticker": None, "company": None},  # Too ambiguous alone
    }

    # Company name patterns that strongly indicate stock reference
    COMPANY_INDICATORS = [
        r"\bstock\b",
        r"\bshares\b",
        r"\bequity\b",
        r"\binvestors?\b",
        r"\bshareholders?\b",
        r"\bmarket\s*cap\b",
        r"\bearnings\b",
        r"\brevenue\b",
        r"\bprofit\b",
        r"\bquarterly\b",
        r"\bannual\s+report\b",
        r"\b(10-k|10-q|8-k|form\s*4)\b",
        r"\bsec\s+filing\b",
        r"\bipo\b",
        r"\btrading\b",
        r"\bbuy\s+rating\b",
        r"\bsell\s+rating\b",
        r"\bprice\s+target\b",
        r"\banalyst\b",
        r"\bupgrade\b",
        r"\bdowngrade\b",
        r"\bdividend\b",
        r"\bbuyback\b",
        r"\bacquisition\b",
        r"\bmerger\b",
        r"\bnasdaq\b",
        r"\bnyse\b",
        r"\botc\b",
        r"\bticker\b",
    ]

    # Patterns that indicate NOT a stock reference
    NON_STOCK_INDICATORS = [
        r"\bapple\s+(pie|juice|cider|tree|fruit|sauce)\b",
        r"\beat\s+(an?\s+)?apple\b",
        r"\bapple\s+of\s+(my|his|her)\b",
        r"\bbig\s+apple\b",  # NYC
        r"\bmeta\s+(data|analysis|tag|description)\b",
        r"\bgo\s+meta\b",
        r"\bford\s+(the\s+)?river\b",
        r"\bford\s+a\s+stream\b",
        r"\btarget\s+(audience|market|demographic)\b",
        r"\bon\s+target\b",
        r"\bgap\s+(between|in|year)\b",
        r"\bbridge\s+the\s+gap\b",
    ]

    def __init__(self, knowledge_base=None):
        """Initialize disambiguator.

        Args:
            knowledge_base: Optional TickerKnowledgeBase for validation
        """
        self.kb = knowledge_base
        self._company_patterns = [re.compile(p, re.IGNORECASE) for p in self.COMPANY_INDICATORS]
        self._non_stock_patterns = [re.compile(p, re.IGNORECASE) for p in self.NON_STOCK_INDICATORS]

    def disambiguate(
        self,
        text: str,
        candidate_tickers: list[str],
        candidate_companies: list[str] | None = None,
    ) -> list[DisambiguatedTicker]:
        """Disambiguate potential tickers and company names.

        Args:
            text: Full text for context analysis
            candidate_tickers: List of potential tickers extracted
            candidate_companies: List of company names extracted (optional)

        Returns:
            List of disambiguated tickers with confidence scores
        """
        results = []
        text_lower = text.lower()

        # Check for stock-related context
        has_stock_context = any(p.search(text_lower) for p in self._company_patterns)
        has_non_stock_context = any(p.search(text_lower) for p in self._non_stock_patterns)

        # Process explicit tickers (with $ prefix) - highest confidence
        for ticker in candidate_tickers:
            # Check if ticker appears with $ in original text
            cashtag_pattern = re.compile(rf"\${re.escape(ticker)}\b", re.IGNORECASE)
            if cashtag_pattern.search(text):
                results.append(DisambiguatedTicker(
                    ticker=ticker.upper(),
                    confidence=0.98,
                    source_text=f"${ticker}",
                    disambiguation_reason="explicit_cashtag",
                ))
                continue

            # Check if it's an ambiguous word
            ticker_upper = ticker.upper()
            if ticker_upper in self.AMBIGUOUS_TICKERS:
                ambig_info = self.AMBIGUOUS_TICKERS[ticker_upper]

                if ambig_info["ticker"] is None:
                    # Too ambiguous, skip
                    continue

                # Check context for disambiguation
                confidence = self._calculate_ambiguous_confidence(
                    text_lower,
                    ticker_upper,
                    has_stock_context,
                    has_non_stock_context,
                )

                if confidence >= 0.5:
                    results.append(DisambiguatedTicker(
                        ticker=ambig_info["ticker"],
                        confidence=confidence,
                        source_text=ticker,
                        disambiguation_reason="context_based",
                        company_name=ambig_info["company"],
                    ))
            else:
                # Regular ticker - validate if KB available
                if self.kb and self.kb.is_valid_ticker(ticker_upper):
                    results.append(DisambiguatedTicker(
                        ticker=ticker_upper,
                        confidence=0.9 if has_stock_context else 0.75,
                        source_text=ticker,
                        disambiguation_reason="validated_ticker",
                        company_name=self.kb.get_company_name(ticker_upper),
                    ))
                elif not self.kb:
                    # No KB, use moderate confidence
                    results.append(DisambiguatedTicker(
                        ticker=ticker_upper,
                        confidence=0.7 if has_stock_context else 0.5,
                        source_text=ticker,
                        disambiguation_reason="unvalidated_ticker",
                    ))

        # Process company names
        if candidate_companies:
            for company in candidate_companies:
                resolved = self._resolve_company_to_ticker(company, text_lower)
                if resolved and resolved["ticker"] not in [r.ticker for r in results]:
                    results.append(DisambiguatedTicker(
                        ticker=resolved["ticker"],
                        confidence=resolved["confidence"],
                        source_text=company,
                        disambiguation_reason="company_name_match",
                        company_name=company,
                    ))

        return results

    def _calculate_ambiguous_confidence(
        self,
        text_lower: str,
        word: str,
        has_stock_context: bool,
        has_non_stock_context: bool,
    ) -> float:
        """Calculate confidence for an ambiguous word being a ticker.

        Args:
            text_lower: Lowercased full text
            word: The ambiguous word
            has_stock_context: Whether text has stock indicators
            has_non_stock_context: Whether text has non-stock indicators

        Returns:
            Confidence score 0-1
        """
        base_confidence = 0.5

        # Strong stock context
        if has_stock_context:
            base_confidence += 0.3

        # Non-stock context is negative
        if has_non_stock_context:
            base_confidence -= 0.4

        # Check for company suffixes (Inc, Corp, etc.)
        word_lower = word.lower()
        company_suffix_pattern = re.compile(
            rf"\b{re.escape(word_lower)}\s+(inc\.?|corp\.?|co\.?|ltd\.?|plc\.?)\b",
            re.IGNORECASE,
        )
        if company_suffix_pattern.search(text_lower):
            base_confidence += 0.25

        # Check for possessive (Apple's earnings) - indicates company
        possessive_pattern = re.compile(rf"\b{re.escape(word_lower)}'s\b", re.IGNORECASE)
        if possessive_pattern.search(text_lower):
            base_confidence += 0.15

        return max(0.0, min(1.0, base_confidence))

    def _resolve_company_to_ticker(
        self,
        company_name: str,
        text_lower: str,
    ) -> dict[str, Any] | None:
        """Resolve a company name to a ticker.

        Args:
            company_name: Company name to resolve
            text_lower: Lowercased text for context

        Returns:
            Dict with ticker and confidence, or None
        """
        company_upper = company_name.upper().strip()

        # Check aliases first
        for ambig_name, info in self.AMBIGUOUS_TICKERS.items():
            if info["company"] and company_upper in info["company"]:
                return {
                    "ticker": info["ticker"],
                    "confidence": 0.85,
                }

        # Use knowledge base if available
        if self.kb:
            ticker = self.kb.resolve_company_name(company_name)
            if ticker:
                return {
                    "ticker": ticker,
                    "confidence": 0.8,
                }

        return None

    def validate_ticker_in_context(
        self,
        ticker: str,
        context: str,
        window: int = 100,
    ) -> float:
        """Validate a ticker based on surrounding context.

        Args:
            ticker: Ticker to validate
            context: Text context around the ticker
            window: Window size to analyze

        Returns:
            Confidence score 0-1
        """
        context_lower = context.lower()

        # Check for stock-related words near ticker
        stock_words = {"stock", "share", "price", "trading", "investor", "earnings"}
        context_words = set(context_lower.split())

        overlap = len(stock_words & context_words)

        if overlap >= 2:
            return 0.95
        elif overlap == 1:
            return 0.8
        else:
            # Check if ticker appears with exchange prefix
            if re.search(rf"\b(NYSE|NASDAQ|OTC)[:\s]*{ticker}\b", context, re.IGNORECASE):
                return 0.98

            return 0.6


def disambiguate_tickers(
    text: str,
    candidate_tickers: list[str],
    knowledge_base=None,
) -> list[DisambiguatedTicker]:
    """Convenience function to disambiguate tickers.

    Args:
        text: Full text for context
        candidate_tickers: List of candidate tickers
        knowledge_base: Optional knowledge base

    Returns:
        List of disambiguated tickers
    """
    disambiguator = TickerDisambiguator(knowledge_base)
    return disambiguator.disambiguate(text, candidate_tickers)
