"""News scrapers module."""

from .base_scraper import BaseScraper
from .newswire_client import NewswireClient
from .penny_stocks_scraper import PennyStocksScraper
from .rss_aggregator import RSSAggregator

__all__ = [
    "BaseScraper",
    "RSSAggregator",
    "PennyStocksScraper",
    "NewswireClient",
]
