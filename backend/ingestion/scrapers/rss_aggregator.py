"""RSS feed aggregator for news sources."""

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import feedparser
import httpx
import structlog

from .base_scraper import BaseScraper

logger = structlog.get_logger(__name__)


# Default RSS feeds for penny stock / micro-cap news
DEFAULT_FEEDS = {
    "sec_rss": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&company=&dateb=&owner=include&count=40&output=atom",
    "yahoo_finance": "https://feeds.finance.yahoo.com/rss/2.0/headline",
    "marketwatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "investing_com": "https://www.investing.com/rss/news.rss",
}


class RSSAggregator(BaseScraper):
    """Aggregator for multiple RSS feeds."""

    def __init__(
        self,
        feeds: dict[str, str] | None = None,
        rate_limit: float = 5.0,
    ):
        """Initialize RSS aggregator.

        Args:
            feeds: Dictionary of feed_name -> feed_url
            rate_limit: Seconds between requests per feed
        """
        super().__init__(rate_limit=rate_limit)
        self.feeds = feeds or DEFAULT_FEEDS

    async def scrape(self) -> list[dict[str, Any]]:
        """Scrape all configured RSS feeds.

        Returns:
            List of all feed items
        """
        all_items = []

        for feed_name, feed_url in self.feeds.items():
            try:
                items = await self._fetch_feed(feed_name, feed_url)
                all_items.extend(items)
            except Exception as e:
                logger.error("Failed to fetch feed", feed=feed_name, error=str(e))

        return all_items

    async def _fetch_feed(
        self,
        feed_name: str,
        feed_url: str,
    ) -> list[dict[str, Any]]:
        """Fetch and parse a single RSS feed.

        Args:
            feed_name: Name identifier for the feed
            feed_url: URL of the RSS feed

        Returns:
            List of parsed items
        """
        response = await self.fetch(feed_url)
        feed = feedparser.parse(response.text)

        items = []
        for entry in feed.entries:
            item = self._parse_entry(entry, feed_name)
            if item and not self._is_duplicate(item.get("headline", "")):
                items.append(item)

        logger.info("Fetched RSS feed", feed=feed_name, items=len(items))
        return items

    def _parse_entry(self, entry: Any, feed_name: str) -> dict[str, Any] | None:
        """Parse a single feed entry.

        Args:
            entry: feedparser entry object
            feed_name: Name of the source feed

        Returns:
            Parsed item dictionary or None
        """
        try:
            # Get title
            title = entry.get("title", "").strip()
            if not title:
                return None

            # Get link
            link = entry.get("link", "")

            # Get published date
            published = entry.get("published", entry.get("updated", ""))
            try:
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    published = pub_dt.isoformat()
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    pub_dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                    published = pub_dt.isoformat()
            except (TypeError, ValueError):
                published = datetime.now(timezone.utc).isoformat()

            # Get description/summary
            summary = ""
            if hasattr(entry, "summary"):
                summary = entry.summary
            elif hasattr(entry, "description"):
                summary = entry.description

            # Clean HTML from summary
            from bs4 import BeautifulSoup
            if summary:
                soup = BeautifulSoup(summary, "lxml")
                summary = soup.get_text(separator=" ", strip=True)[:1000]

            # Get author
            author = entry.get("author", "")

            # Get categories/tags
            tags = []
            if hasattr(entry, "tags"):
                tags = [t.get("term", "") for t in entry.tags if t.get("term")]

            return {
                "headline": title,
                "summary": summary,
                "url": link,
                "published_at": published,
                "author": author,
                "tags": tags,
                "source": feed_name,
                "event_type": "NEWS",
                "event_category": "RSS_NEWS",
            }

        except Exception as e:
            logger.warning("Failed to parse entry", feed=feed_name, error=str(e))
            return None

    async def stream(
        self,
        poll_interval: float = 60.0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream new items from all feeds.

        Args:
            poll_interval: Seconds between poll cycles

        Yields:
            New feed items
        """
        while True:
            for feed_name, feed_url in self.feeds.items():
                try:
                    items = await self._fetch_feed(feed_name, feed_url)

                    for item in items:
                        yield self.normalize_event(item)

                except Exception as e:
                    logger.error("Stream error", feed=feed_name, error=str(e))

            await asyncio.sleep(poll_interval)

    def add_feed(self, name: str, url: str) -> None:
        """Add a new feed to monitor.

        Args:
            name: Feed name identifier
            url: Feed URL
        """
        self.feeds[name] = url

    def remove_feed(self, name: str) -> None:
        """Remove a feed from monitoring.

        Args:
            name: Feed name to remove
        """
        self.feeds.pop(name, None)

    async def fetch_specific_feed(self, name: str) -> list[dict[str, Any]]:
        """Fetch a specific feed by name.

        Args:
            name: Feed name

        Returns:
            List of items from that feed
        """
        if name not in self.feeds:
            raise ValueError(f"Unknown feed: {name}")

        return await self._fetch_feed(name, self.feeds[name])


class TickerRSSAggregator(RSSAggregator):
    """RSS aggregator that extracts ticker symbols from content."""

    # Common ticker pattern
    TICKER_PATTERN = r"\b([A-Z]{1,5})\b"

    # Words to exclude from ticker matching
    EXCLUDED_WORDS = {
        "A", "I", "US", "UK", "EU", "CEO", "CFO", "IPO", "ETF", "SEC",
        "FDA", "FTC", "NYSE", "NASDAQ", "OTC", "PR", "IT", "AI", "EV",
        "THE", "AND", "FOR", "NEW", "INC", "LTD", "LLC", "CORP",
    }

    def __init__(
        self,
        feeds: dict[str, str] | None = None,
        ticker_list: set[str] | None = None,
        rate_limit: float = 5.0,
    ):
        """Initialize ticker RSS aggregator.

        Args:
            feeds: Dictionary of feed_name -> feed_url
            ticker_list: Set of valid tickers for matching
            rate_limit: Seconds between requests
        """
        super().__init__(feeds=feeds, rate_limit=rate_limit)
        self.ticker_list = ticker_list or set()

    def _parse_entry(self, entry: Any, feed_name: str) -> dict[str, Any] | None:
        """Parse entry and extract tickers."""
        item = super()._parse_entry(entry, feed_name)

        if item:
            # Extract tickers from headline and summary
            text = f"{item.get('headline', '')} {item.get('summary', '')}"
            tickers = self._extract_tickers(text)
            item["extracted_tickers"] = tickers

            # Set primary ticker if found
            if tickers:
                item["ticker"] = tickers[0]

        return item

    def _extract_tickers(self, text: str) -> list[str]:
        """Extract ticker symbols from text.

        Args:
            text: Text to search

        Returns:
            List of extracted tickers
        """
        import re

        matches = re.findall(self.TICKER_PATTERN, text)
        tickers = []

        for match in matches:
            # Skip excluded words
            if match in self.EXCLUDED_WORDS:
                continue

            # If we have a ticker list, validate against it
            if self.ticker_list:
                if match in self.ticker_list:
                    tickers.append(match)
            else:
                # Without a list, accept 2-5 char uppercase words
                if 2 <= len(match) <= 5:
                    tickers.append(match)

        return list(dict.fromkeys(tickers))  # Remove duplicates, preserve order


async def main():
    """Example usage of RSS aggregator."""
    async with RSSAggregator() as aggregator:
        items = await aggregator.scrape()
        print(f"Fetched {len(items)} items from RSS feeds")

        for item in items[:5]:
            print(f"- {item.get('source')}: {item.get('headline', '')[:60]}...")


if __name__ == "__main__":
    asyncio.run(main())
