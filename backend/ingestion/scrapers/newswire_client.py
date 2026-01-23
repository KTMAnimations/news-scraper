"""Client for newswire services (PR Newswire, Business Wire, GlobeNewswire)."""

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import feedparser
import structlog
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

logger = structlog.get_logger(__name__)


# Newswire RSS feeds - comprehensive list for faster updates
NEWSWIRE_FEEDS = {
    "prnewswire": {
        "name": "PR Newswire",
        # Main RSS feeds
        "rss": "https://www.prnewswire.com/rss/news-releases-list.rss",
        # Financial services focused
        "financial_rss": "https://www.prnewswire.com/rss/financial-services-latest-news/financial-services-latest-news-list.rss",
        # Business & technology
        "business_rss": "https://www.prnewswire.com/rss/business-technology-latest-news/business-technology-latest-news-list.rss",
        # Healthcare & pharmaceuticals
        "health_rss": "https://www.prnewswire.com/rss/health-latest-news/health-latest-news-list.rss",
        # Energy & natural resources
        "energy_rss": "https://www.prnewswire.com/rss/energy-latest-news/energy-latest-news-list.rss",
        # Small cap & micro cap (high alpha potential)
        "smallcap_rss": "https://www.prnewswire.com/rss/micromarket-monitor-latest-news-list.rss",
    },
    "businesswire": {
        "name": "Business Wire",
        # Main RSS feed
        "rss": "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtXWA==",
        # Banking & financial services
        "banking_rss": "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEVpTXQ==",
        # Technology
        "tech_rss": "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEF9X",
        # Healthcare & pharmaceuticals
        "health_rss": "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEVtQ",
        # Energy & utilities
        "energy_rss": "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEV5V",
        # Retail & consumer
        "retail_rss": "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEV1RWw==",
    },
    "globenewswire": {
        "name": "GlobeNewswire",
        # Main news releases
        "rss": "https://www.globenewswire.com/RssFeed/orgclass/1/feedTitle/GlobeNewswire%20-%20News%20Releases",
        # Small cap focused (high alpha)
        "small_cap_rss": "https://www.globenewswire.com/RssFeed/subjectcode/24-Small%20Cap/feedTitle/GlobeNewswire%20-%20Small%20Cap%20News",
        # Mergers & acquisitions
        "ma_rss": "https://www.globenewswire.com/RssFeed/subjectcode/4-Mergers%20and%20Acquisitions/feedTitle/GlobeNewswire%20-%20M%26A",
        # Earnings announcements
        "earnings_rss": "https://www.globenewswire.com/RssFeed/subjectcode/7-Earnings/feedTitle/GlobeNewswire%20-%20Earnings",
        # FDA announcements
        "fda_rss": "https://www.globenewswire.com/RssFeed/subjectcode/9-FDA%20Coverage/feedTitle/GlobeNewswire%20-%20FDA",
        # IPO related
        "ipo_rss": "https://www.globenewswire.com/RssFeed/subjectcode/10-Initial%20Public%20Offering/feedTitle/GlobeNewswire%20-%20IPO",
        # Analyst recommendations
        "analyst_rss": "https://www.globenewswire.com/RssFeed/subjectcode/15-Analyst%20Ratings/feedTitle/GlobeNewswire%20-%20Analysts",
    },
    "accesswire": {
        "name": "Accesswire",
        # Main feed
        "rss": "https://www.accesswire.com/api/rss.ashx",
    },
}

# RSS feed categories for filtering and prioritization
RSS_FEED_CATEGORIES = {
    "high_alpha": [
        "small_cap_rss",
        "smallcap_rss",
        "ma_rss",
        "earnings_rss",
        "fda_rss",
        "ipo_rss",
    ],
    "financial": [
        "financial_rss",
        "banking_rss",
    ],
    "healthcare": [
        "health_rss",
        "fda_rss",
    ],
    "technology": [
        "business_rss",
        "tech_rss",
    ],
    "energy": [
        "energy_rss",
    ],
}


class NewswireClient(BaseScraper):
    """Client for aggregating press releases from newswire services.

    Supports multiple RSS feeds per newswire for comprehensive coverage
    and faster updates. Can filter by category (high_alpha, financial, etc.).
    """

    # Pattern to extract tickers from press releases
    TICKER_PATTERNS = [
        re.compile(r"\((?:NYSE|NASDAQ|OTC|OTCQB|OTCQX|TSX|TSXV|ASX):\s*([A-Z]{1,5})\)", re.IGNORECASE),
        re.compile(r"(?:NYSE|NASDAQ|OTC|OTCQB|OTCQX|TSX|TSXV|ASX):\s*([A-Z]{1,5})", re.IGNORECASE),
        re.compile(r"\(([A-Z]{1,5})\)", re.IGNORECASE),  # Fallback for tickers in parens
    ]

    def __init__(
        self,
        feeds: dict[str, dict] | None = None,
        rate_limit: float = 5.0,
        filter_small_cap: bool = True,
        feed_categories: list[str] | None = None,
    ):
        """Initialize newswire client.

        Args:
            feeds: Custom feed configuration
            rate_limit: Seconds between requests
            filter_small_cap: Prioritize small cap news
            feed_categories: List of RSS feed categories to enable
                           (e.g., ["high_alpha", "financial"])
                           If None, uses all feeds.
        """
        super().__init__(rate_limit=rate_limit)
        self.feeds = feeds or NEWSWIRE_FEEDS
        self.filter_small_cap = filter_small_cap
        self.feed_categories = feed_categories

    def get_rss_urls_for_category(self, category: str) -> list[tuple[str, str, str]]:
        """Get all RSS URLs for a specific category.

        Args:
            category: Category name (e.g., "high_alpha", "financial")

        Returns:
            List of (wire_id, wire_name, rss_url) tuples
        """
        if category not in RSS_FEED_CATEGORIES:
            logger.warning("Unknown RSS category", category=category)
            return []

        category_feeds = RSS_FEED_CATEGORIES[category]
        urls = []

        for wire_id, config in self.feeds.items():
            wire_name = config.get("name", wire_id)
            for key, value in config.items():
                if key in category_feeds or key.replace("_rss", "_rss") in category_feeds:
                    urls.append((wire_id, wire_name, value))

        return urls

    def get_all_rss_urls(self) -> list[tuple[str, str, str]]:
        """Get all configured RSS URLs.

        Returns:
            List of (wire_id, wire_name, rss_url) tuples
        """
        urls = []
        enabled_feeds = set()

        # If categories specified, only include those feeds
        if self.feed_categories:
            for category in self.feed_categories:
                if category in RSS_FEED_CATEGORIES:
                    enabled_feeds.update(RSS_FEED_CATEGORIES[category])

        for wire_id, config in self.feeds.items():
            wire_name = config.get("name", wire_id)
            for key, value in config.items():
                if key == "name":
                    continue

                # If filtering by category, check if this feed is enabled
                if enabled_feeds and key not in enabled_feeds and key != "rss":
                    continue

                if key.endswith("rss") or key == "rss":
                    urls.append((wire_id, wire_name, value))

        return urls

    async def scrape(self) -> list[dict[str, Any]]:
        """Scrape all newswire feeds.

        Returns:
            List of press releases
        """
        all_releases = []

        for wire_id, config in self.feeds.items():
            # Get all RSS URLs for this wire
            rss_urls = []
            for key, value in config.items():
                if key.endswith("rss") or key == "rss":
                    rss_urls.append(value)

            for rss_url in rss_urls:
                try:
                    releases = await self._fetch_feed(wire_id, config["name"], rss_url)
                    all_releases.extend(releases)
                except Exception as e:
                    logger.error(
                        "Failed to fetch newswire feed",
                        wire=wire_id,
                        url=rss_url,
                        error=str(e),
                    )

        return all_releases

    async def _fetch_feed(
        self,
        wire_id: str,
        wire_name: str,
        rss_url: str,
    ) -> list[dict[str, Any]]:
        """Fetch and parse a single RSS feed.

        Args:
            wire_id: Wire service identifier
            wire_name: Display name
            rss_url: RSS feed URL

        Returns:
            List of parsed releases
        """
        response = await self.fetch(rss_url)
        feed = feedparser.parse(response.text)

        releases = []

        for entry in feed.entries[:50]:  # Limit per feed
            release = self._parse_entry(entry, wire_id, wire_name)
            if release:
                # Check for duplicates
                headline = release.get("headline", "")
                if not self._is_duplicate(headline):
                    releases.append(release)

        logger.info("Fetched newswire feed", wire=wire_name, releases=len(releases))
        return releases

    def _parse_entry(
        self,
        entry: Any,
        wire_id: str,
        wire_name: str,
    ) -> dict[str, Any] | None:
        """Parse RSS entry into press release dict.

        Args:
            entry: feedparser entry object
            wire_id: Wire service identifier
            wire_name: Display name

        Returns:
            Parsed press release or None
        """
        try:
            title = entry.get("title", "").strip()
            if not title:
                return None

            # Get full content
            content = ""
            if hasattr(entry, "content") and entry.content:
                content = entry.content[0].get("value", "")
            elif hasattr(entry, "summary"):
                content = entry.summary
            elif hasattr(entry, "description"):
                content = entry.description

            # Clean HTML from content
            soup = BeautifulSoup(content, "lxml")
            clean_content = soup.get_text(separator=" ", strip=True)

            # Extract tickers from title and content
            full_text = f"{title} {clean_content[:2000]}"
            tickers = self._extract_tickers(full_text)

            # Parse published date
            published = datetime.now(timezone.utc).isoformat()
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    published = pub_dt.isoformat()
                except (TypeError, ValueError) as e:
                    logger.debug(
                        "Failed to parse published date, using current time",
                        title=title[:50],
                        error=str(e),
                    )

            # Classify the release
            event_type, event_category = self._classify_release(title, clean_content)

            return {
                "headline": title,
                "summary": clean_content[:500] if clean_content else title,
                "content": clean_content[:10000],
                "url": entry.get("link", ""),
                "published_at": published,
                "source": wire_name,
                "source_id": wire_id,
                "ticker": tickers[0] if tickers else "",
                "extracted_tickers": tickers,
                "event_type": event_type,
                "event_category": event_category,
                "metadata": {
                    "wire_service": wire_id,
                    "entry_id": entry.get("id", ""),
                },
            }

        except Exception as e:
            logger.warning("Failed to parse newswire entry", wire=wire_id, error=str(e))
            return None

    def _extract_tickers(self, text: str) -> list[str]:
        """Extract ticker symbols from text.

        Args:
            text: Text to search

        Returns:
            List of extracted tickers
        """
        tickers = []

        for pattern in self.TICKER_PATTERNS:
            matches = pattern.findall(text)
            for match in matches:
                ticker = match.upper()
                # Validate ticker (1-5 uppercase letters)
                if 1 <= len(ticker) <= 5 and ticker.isalpha():
                    tickers.append(ticker)

        # Deduplicate while preserving order
        return list(dict.fromkeys(tickers))[:10]

    def _classify_release(self, title: str, content: str) -> tuple[str, str]:
        """Classify press release by type.

        Args:
            title: Release headline
            content: Release content

        Returns:
            Tuple of (event_type, event_category)
        """
        title_lower = title.lower()
        content_lower = content[:2000].lower()
        combined = f"{title_lower} {content_lower}"

        # Earnings related
        if any(term in combined for term in [
            "earnings", "quarterly results", "financial results",
            "revenue", "net income", "eps", "fiscal quarter",
        ]):
            return ("EARNINGS", "FINANCIAL")

        # Acquisition/M&A
        if any(term in combined for term in [
            "acquisition", "acquires", "merger", "to acquire",
            "definitive agreement", "acquisition agreement",
        ]):
            return ("ACQUISITION", "CORPORATE_ACTION")

        # Offering/Financing
        if any(term in combined for term in [
            "offering", "public offering", "private placement",
            "raises capital", "financing", "stock offering",
        ]):
            return ("OFFERING", "FINANCING")

        # FDA/Healthcare
        if any(term in combined for term in [
            "fda approval", "fda clearance", "clinical trial",
            "drug approval", "phase 1", "phase 2", "phase 3",
        ]):
            return ("FDA_NEWS", "HEALTHCARE")

        # Partnership/Contract
        if any(term in combined for term in [
            "partnership", "contract", "agreement with",
            "strategic alliance", "collaboration",
        ]):
            return ("PARTNERSHIP", "BUSINESS")

        # Management changes
        if any(term in combined for term in [
            "ceo", "cfo", "appoints", "names", "resignation",
            "executive", "board of directors",
        ]):
            return ("MANAGEMENT", "CORPORATE")

        # Product launch
        if any(term in combined for term in [
            "launches", "introduces", "unveils",
            "new product", "announces new",
        ]):
            return ("PRODUCT_LAUNCH", "BUSINESS")

        # Default
        return ("PRESS_RELEASE", "NEWS")

    async def stream(
        self,
        poll_interval: float = 60.0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream new press releases.

        Args:
            poll_interval: Seconds between poll cycles

        Yields:
            New press releases
        """
        while True:
            try:
                releases = await self.scrape()

                for release in releases:
                    yield self.normalize_event(release)

            except Exception as e:
                logger.error("Stream error", error=str(e))

            await asyncio.sleep(poll_interval)

    async def search_by_ticker(
        self,
        ticker: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for press releases mentioning a ticker.

        Args:
            ticker: Stock ticker symbol
            limit: Maximum results

        Returns:
            List of matching releases
        """
        all_releases = await self.scrape()

        # Filter by ticker
        ticker_upper = ticker.upper()
        matching = [
            release for release in all_releases
            if ticker_upper in release.get("extracted_tickers", [])
        ]

        return matching[:limit]

    async def scrape_parallel(self, max_concurrent: int = 5) -> list[dict[str, Any]]:
        """Scrape all RSS feeds in parallel for faster updates.

        Uses asyncio.gather with semaphore for controlled concurrency.

        Args:
            max_concurrent: Maximum concurrent requests

        Returns:
            List of all press releases from all feeds
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        all_releases = []

        async def fetch_with_semaphore(wire_id: str, wire_name: str, rss_url: str):
            async with semaphore:
                try:
                    return await self._fetch_feed(wire_id, wire_name, rss_url)
                except Exception as e:
                    logger.error(
                        "Failed to fetch feed in parallel",
                        wire=wire_id,
                        url=rss_url,
                        error=str(e),
                    )
                    return []

        # Get all RSS URLs
        rss_urls = self.get_all_rss_urls()
        logger.info("Starting parallel RSS fetch", total_feeds=len(rss_urls))

        # Fetch all feeds in parallel
        tasks = [
            fetch_with_semaphore(wire_id, wire_name, rss_url)
            for wire_id, wire_name, rss_url in rss_urls
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_releases.extend(result)
            elif isinstance(result, Exception):
                logger.error("Feed fetch exception", error=str(result))

        logger.info("Completed parallel RSS fetch", total_releases=len(all_releases))
        return all_releases

    async def scrape_high_alpha_feeds(self) -> list[dict[str, Any]]:
        """Scrape only high-alpha potential RSS feeds.

        These feeds focus on small caps, M&A, earnings, FDA news, and IPOs
        which typically have higher alpha potential.

        Returns:
            List of press releases from high-alpha feeds
        """
        all_releases = []
        rss_urls = self.get_rss_urls_for_category("high_alpha")

        for wire_id, wire_name, rss_url in rss_urls:
            try:
                releases = await self._fetch_feed(wire_id, wire_name, rss_url)
                # Mark as high alpha source
                for release in releases:
                    release["metadata"]["high_alpha_source"] = True
                all_releases.extend(releases)
            except Exception as e:
                logger.error(
                    "Failed to fetch high-alpha feed",
                    wire=wire_id,
                    url=rss_url,
                    error=str(e),
                )

        return all_releases

    async def stream_fast(
        self,
        poll_interval: float = 30.0,
        high_alpha_only: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream press releases with faster polling using parallel fetches.

        Args:
            poll_interval: Seconds between poll cycles (default 30s for faster updates)
            high_alpha_only: Only fetch from high-alpha feeds

        Yields:
            New press releases
        """
        while True:
            try:
                if high_alpha_only:
                    releases = await self.scrape_high_alpha_feeds()
                else:
                    releases = await self.scrape_parallel()

                for release in releases:
                    yield self.normalize_event(release)

            except Exception as e:
                logger.error("Fast stream error", error=str(e))

            await asyncio.sleep(poll_interval)


async def main():
    """Example usage of newswire client."""
    async with NewswireClient() as client:
        releases = await client.scrape()
        print(f"Fetched {len(releases)} press releases")

        for release in releases[:5]:
            tickers = release.get("extracted_tickers", [])
            ticker_str = ", ".join(tickers) if tickers else "N/A"
            print(f"- [{ticker_str}] {release.get('headline', '')[:60]}...")
            print(f"  Type: {release.get('event_type')}, Source: {release.get('source')}")


if __name__ == "__main__":
    asyncio.run(main())
