"""Paywall detection and handling for news content.

This module provides utilities for detecting paywalled content and
extracting available information from partially accessible articles.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


class PaywallType(str, Enum):
    """Types of paywalls encountered."""

    NONE = "none"
    HARD = "hard"  # No content accessible without subscription
    SOFT = "soft"  # Some content available (e.g., first paragraph)
    METERED = "metered"  # Limited free articles per period
    REGISTRATION = "registration"  # Requires free registration
    UNKNOWN = "unknown"


@dataclass
class PaywallResult:
    """Result of paywall detection.

    Attributes:
        is_paywalled: Whether content is behind a paywall.
        paywall_type: Type of paywall detected.
        confidence: Confidence score (0.0 to 1.0).
        available_content: Content that is accessible.
        extracted_title: Article title if available.
        extracted_summary: Summary/excerpt if available.
        indicators_found: List of paywall indicators detected.
        metadata: Additional metadata about the paywall.
    """

    is_paywalled: bool = False
    paywall_type: PaywallType = PaywallType.NONE
    confidence: float = 0.0
    available_content: str = ""
    extracted_title: str = ""
    extracted_summary: str = ""
    indicators_found: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "is_paywalled": self.is_paywalled,
            "paywall_type": self.paywall_type.value,
            "confidence": self.confidence,
            "available_content": self.available_content[:1000] if self.available_content else "",
            "extracted_title": self.extracted_title,
            "extracted_summary": self.extracted_summary[:500] if self.extracted_summary else "",
            "indicators_found": self.indicators_found,
            "metadata": self.metadata,
        }


class PaywallDetector:
    """Detects and handles paywalled content.

    Strategies:
    1. HTML/CSS pattern matching for paywall overlays
    2. Content length analysis (truncated content)
    3. Subscription prompt detection
    4. Meta tag analysis
    5. Domain-specific rules
    """

    # Common paywall-related CSS classes and IDs
    PAYWALL_CSS_PATTERNS = [
        r"paywall",
        r"subscribe",
        r"subscription",
        r"premium-content",
        r"members-only",
        r"locked",
        r"gated",
        r"registration-wall",
        r"subscriber-only",
        r"paid-content",
        r"restricted",
        r"access-denied",
        r"piano-id",  # Piano (paywall service)
        r"tp-modal",  # TinyPass/Piano
        r"pq-modal",  # Propel paywall
        r"nytimes-pay",
        r"wsj-pay",
        r"bloomberg-pay",
    ]

    # Text patterns indicating paywall
    PAYWALL_TEXT_PATTERNS = [
        r"subscribe(?:\s+(?:now|today|to continue))?",
        r"subscription required",
        r"premium (?:content|article|access)",
        r"members(?:-|\s)?only",
        r"unlock (?:this|full) (?:article|story)",
        r"continue reading for \$",
        r"sign (?:in|up) to (?:continue|read)",
        r"already a subscriber\?",
        r"become a member",
        r"get unlimited access",
        r"free trial",
        r"you(?:'ve| have) reached your (?:free )?(?:article )?limit",
        r"(?:this|the) (?:article|story) is (?:only )?available to subscribers",
        r"please log in to view",
        r"create (?:a free )?account",
        r"register to continue",
        r"read the full (?:article|story)",
        r"view full (?:article|story)",
        r"to read (?:the |this )?(?:full )?(?:article|story)",
    ]

    # Meta tags indicating premium content
    META_INDICATORS = [
        ("meta[name='article:content_tier']", "premium"),
        ("meta[name='og:restrictions:content']", "metered"),
        ("meta[property='article:is_free']", "false"),
        ("meta[name='access']", "subscription"),
    ]

    # Domain-specific configurations
    DOMAIN_CONFIGS = {
        "wsj.com": {
            "paywall_type": PaywallType.HARD,
            "content_selector": "article",
            "truncation_marker": "...",
        },
        "ft.com": {
            "paywall_type": PaywallType.HARD,
            "content_selector": "article",
            "truncation_marker": "...",
        },
        "bloomberg.com": {
            "paywall_type": PaywallType.METERED,
            "content_selector": "article",
            "truncation_marker": None,
        },
        "nytimes.com": {
            "paywall_type": PaywallType.METERED,
            "content_selector": "article",
            "truncation_marker": None,
        },
        "reuters.com": {
            "paywall_type": PaywallType.SOFT,
            "content_selector": "article",
            "truncation_marker": None,
        },
        "barrons.com": {
            "paywall_type": PaywallType.HARD,
            "content_selector": "article",
            "truncation_marker": "...",
        },
        "seekingalpha.com": {
            "paywall_type": PaywallType.SOFT,
            "content_selector": ".paywall-article",
            "truncation_marker": "Read more",
        },
        "thestreet.com": {
            "paywall_type": PaywallType.SOFT,
            "content_selector": "article",
            "truncation_marker": None,
        },
    }

    # Minimum content length thresholds
    MIN_FULL_ARTICLE_LENGTH = 500  # Characters for a "full" article
    TRUNCATION_THRESHOLD = 0.3  # Ratio of visible to expected content

    def __init__(self):
        """Initialize paywall detector."""
        self._compiled_css = [re.compile(p, re.IGNORECASE) for p in self.PAYWALL_CSS_PATTERNS]
        self._compiled_text = [re.compile(p, re.IGNORECASE) for p in self.PAYWALL_TEXT_PATTERNS]

    def detect(
        self,
        html: str,
        url: str | None = None,
        expected_length: int | None = None,
    ) -> PaywallResult:
        """Detect if content is paywalled.

        Args:
            html: HTML content of the page.
            url: URL of the page (for domain-specific rules).
            expected_length: Expected content length (for truncation detection).

        Returns:
            PaywallResult with detection results.
        """
        result = PaywallResult()
        indicators = []
        confidence_scores = []

        soup = BeautifulSoup(html, "lxml")

        # Check domain-specific rules first
        if url:
            domain_result = self._check_domain_rules(url, soup)
            if domain_result:
                return domain_result

        # Check CSS patterns
        css_score = self._check_css_patterns(soup, indicators)
        if css_score > 0:
            confidence_scores.append(css_score)

        # Check text patterns
        text_score = self._check_text_patterns(soup, indicators)
        if text_score > 0:
            confidence_scores.append(text_score)

        # Check meta tags
        meta_score = self._check_meta_tags(soup, indicators)
        if meta_score > 0:
            confidence_scores.append(meta_score)

        # Check content truncation
        content = self._extract_main_content(soup)
        truncation_score = self._check_truncation(content, expected_length, indicators)
        if truncation_score > 0:
            confidence_scores.append(truncation_score)

        # Calculate overall confidence
        if confidence_scores:
            result.confidence = sum(confidence_scores) / len(confidence_scores)
            result.is_paywalled = result.confidence > 0.4
            result.indicators_found = indicators

            # Determine paywall type
            result.paywall_type = self._determine_paywall_type(indicators, content)

        # Extract available content
        result.extracted_title = self._extract_title(soup)
        result.extracted_summary = self._extract_summary(soup, content)
        result.available_content = content

        logger.debug(
            "Paywall detection complete",
            is_paywalled=result.is_paywalled,
            confidence=result.confidence,
            paywall_type=result.paywall_type,
            indicators=len(indicators),
        )

        return result

    def _check_domain_rules(
        self,
        url: str,
        soup: BeautifulSoup,
    ) -> PaywallResult | None:
        """Check domain-specific paywall rules.

        Args:
            url: URL of the page.
            soup: Parsed HTML.

        Returns:
            PaywallResult if domain has specific rules, None otherwise.
        """
        from urllib.parse import urlparse

        domain = urlparse(url).netloc.lower()

        # Remove 'www.' prefix
        if domain.startswith("www."):
            domain = domain[4:]

        for known_domain, config in self.DOMAIN_CONFIGS.items():
            if known_domain in domain:
                result = PaywallResult(
                    is_paywalled=True,
                    paywall_type=config["paywall_type"],
                    confidence=0.8,
                    indicators_found=[f"known_paywall_domain:{known_domain}"],
                )

                # Try to extract content using domain-specific selector
                selector = config.get("content_selector", "article")
                content_elem = soup.select_one(selector)
                if content_elem:
                    result.available_content = content_elem.get_text(separator=" ", strip=True)

                result.extracted_title = self._extract_title(soup)
                result.extracted_summary = self._extract_summary(soup, result.available_content)

                result.metadata["domain_config"] = known_domain

                return result

        return None

    def _check_css_patterns(
        self,
        soup: BeautifulSoup,
        indicators: list[str],
    ) -> float:
        """Check for paywall-related CSS patterns.

        Args:
            soup: Parsed HTML.
            indicators: List to append found indicators.

        Returns:
            Confidence score (0.0 to 1.0).
        """
        found_count = 0
        total_patterns = len(self._compiled_css)

        # Check class attributes
        for element in soup.find_all(class_=True):
            classes = " ".join(element.get("class", []))
            for pattern in self._compiled_css:
                if pattern.search(classes):
                    indicator = f"css_class:{pattern.pattern}"
                    if indicator not in indicators:
                        indicators.append(indicator)
                        found_count += 1
                    break

        # Check id attributes
        for element in soup.find_all(id=True):
            element_id = element.get("id", "")
            for pattern in self._compiled_css:
                if pattern.search(element_id):
                    indicator = f"css_id:{pattern.pattern}"
                    if indicator not in indicators:
                        indicators.append(indicator)
                        found_count += 1
                    break

        # Normalize score (cap at 1.0)
        return min(found_count / 3, 1.0) if found_count > 0 else 0.0

    def _check_text_patterns(
        self,
        soup: BeautifulSoup,
        indicators: list[str],
    ) -> float:
        """Check for paywall-related text patterns.

        Args:
            soup: Parsed HTML.
            indicators: List to append found indicators.

        Returns:
            Confidence score (0.0 to 1.0).
        """
        text = soup.get_text(separator=" ", strip=True).lower()
        found_count = 0

        for pattern in self._compiled_text:
            if pattern.search(text):
                indicator = f"text_pattern:{pattern.pattern[:30]}"
                if indicator not in indicators:
                    indicators.append(indicator)
                    found_count += 1

        # Weight based on number of patterns found
        return min(found_count / 2, 1.0) if found_count > 0 else 0.0

    def _check_meta_tags(
        self,
        soup: BeautifulSoup,
        indicators: list[str],
    ) -> float:
        """Check meta tags for paywall indicators.

        Args:
            soup: Parsed HTML.
            indicators: List to append found indicators.

        Returns:
            Confidence score (0.0 to 1.0).
        """
        found_count = 0

        for selector, expected_value in self.META_INDICATORS:
            element = soup.select_one(selector)
            if element:
                content = element.get("content", "").lower()
                if expected_value in content:
                    indicators.append(f"meta_tag:{selector}")
                    found_count += 1

        # Meta tags are strong indicators
        return min(found_count * 0.5, 1.0) if found_count > 0 else 0.0

    def _check_truncation(
        self,
        content: str,
        expected_length: int | None,
        indicators: list[str],
    ) -> float:
        """Check if content appears truncated.

        Args:
            content: Extracted content.
            expected_length: Expected content length.
            indicators: List to append found indicators.

        Returns:
            Confidence score (0.0 to 1.0).
        """
        content_length = len(content)

        # Check if content is very short
        if content_length < self.MIN_FULL_ARTICLE_LENGTH:
            indicators.append(f"short_content:{content_length}")
            return 0.6

        # Check against expected length
        if expected_length and content_length < expected_length * self.TRUNCATION_THRESHOLD:
            indicators.append(f"truncated:{content_length}/{expected_length}")
            return 0.7

        # Check for common truncation markers
        truncation_markers = ["...", "Read more", "Continue reading", "[...]"]
        for marker in truncation_markers:
            if content.rstrip().endswith(marker):
                indicators.append(f"truncation_marker:{marker}")
                return 0.5

        return 0.0

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main article content.

        Args:
            soup: Parsed HTML.

        Returns:
            Extracted content text.
        """
        # Priority order for content containers
        selectors = [
            "article",
            "[role='main']",
            "main",
            ".article-content",
            ".article-body",
            ".post-content",
            ".entry-content",
            "#content",
            ".content",
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                # Remove script and style elements
                for tag in element.find_all(["script", "style", "nav", "footer"]):
                    tag.decompose()
                return element.get_text(separator=" ", strip=True)

        # Fallback: get body text
        body = soup.find("body")
        if body:
            for tag in body.find_all(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            return body.get_text(separator=" ", strip=True)[:5000]

        return ""

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract article title.

        Args:
            soup: Parsed HTML.

        Returns:
            Extracted title.
        """
        # Priority order for title elements
        selectors = [
            "h1",
            "meta[property='og:title']",
            "meta[name='twitter:title']",
            "title",
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                if selector.startswith("meta"):
                    return element.get("content", "").strip()
                return element.get_text(strip=True)

        return ""

    def _extract_summary(self, soup: BeautifulSoup, content: str) -> str:
        """Extract article summary.

        Args:
            soup: Parsed HTML.
            content: Extracted content (fallback).

        Returns:
            Extracted summary.
        """
        # Try meta description first
        meta_selectors = [
            "meta[property='og:description']",
            "meta[name='description']",
            "meta[name='twitter:description']",
        ]

        for selector in meta_selectors:
            element = soup.select_one(selector)
            if element:
                desc = element.get("content", "").strip()
                if desc:
                    return desc[:500]

        # Try to find lead paragraph
        article = soup.select_one("article")
        if article:
            first_p = article.find("p")
            if first_p:
                return first_p.get_text(strip=True)[:500]

        # Fallback: first 500 chars of content
        return content[:500] if content else ""

    def _determine_paywall_type(
        self,
        indicators: list[str],
        content: str,
    ) -> PaywallType:
        """Determine the type of paywall.

        Args:
            indicators: List of found indicators.
            content: Extracted content.

        Returns:
            PaywallType enum value.
        """
        indicators_str = " ".join(indicators).lower()

        # Check for metered indicators
        if any(term in indicators_str for term in ["limit", "metered", "free"]):
            return PaywallType.METERED

        # Check for registration indicators
        if any(term in indicators_str for term in ["register", "sign up", "account"]):
            return PaywallType.REGISTRATION

        # Check for soft paywall (some content available)
        if content and len(content) > 200:
            return PaywallType.SOFT

        # Default to hard paywall if very little content
        return PaywallType.HARD


def normalize_event_with_paywall(
    raw_data: dict[str, Any],
    paywall_result: PaywallResult,
) -> dict[str, Any]:
    """Normalize event data with paywall information.

    Args:
        raw_data: Raw scraped data.
        paywall_result: Paywall detection result.

    Returns:
        Normalized event with paywall metadata.
    """
    normalized = raw_data.copy()

    # Add paywall metadata
    if "metadata" not in normalized:
        normalized["metadata"] = {}

    normalized["metadata"]["paywall"] = paywall_result.to_dict()

    # Use extracted content if original is limited
    if paywall_result.is_paywalled:
        # Flag as partial content
        normalized["metadata"]["is_partial_content"] = True
        normalized["metadata"]["content_completeness"] = "partial"

        # Use paywall-extracted data if better
        if paywall_result.extracted_title and not normalized.get("headline"):
            normalized["headline"] = paywall_result.extracted_title

        if paywall_result.extracted_summary and not normalized.get("summary"):
            normalized["summary"] = paywall_result.extracted_summary

        # Limit content to what's actually available
        if paywall_result.available_content:
            normalized["content"] = paywall_result.available_content

    return normalized
