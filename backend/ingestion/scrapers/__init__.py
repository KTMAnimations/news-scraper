"""News scrapers module."""

from .base_scraper import BaseScraper
from .newswire_client import NewswireClient, NEWSWIRE_FEEDS, RSS_FEED_CATEGORIES
from .penny_stocks_scraper import PennyStocksScraper
from .rss_aggregator import RSSAggregator
from .paywall_detector import (
    PaywallDetector,
    PaywallResult,
    PaywallType,
    normalize_event_with_paywall,
)

__all__ = [
    "BaseScraper",
    "RSSAggregator",
    "PennyStocksScraper",
    "NewswireClient",
    "NEWSWIRE_FEEDS",
    "RSS_FEED_CATEGORIES",
    "PaywallDetector",
    "PaywallResult",
    "PaywallType",
    "normalize_event_with_paywall",
]
