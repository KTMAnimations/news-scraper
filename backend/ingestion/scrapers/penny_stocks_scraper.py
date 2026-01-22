"""Scraper for penny stock news sites."""

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import structlog
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

logger = structlog.get_logger(__name__)


# Penny stock news sources
PENNY_STOCK_SOURCES = {
    "allpennystocks": {
        "url": "https://www.allpennystocks.com/hotpennystocks/",
        "rss": "https://www.allpennystocks.com/feed/",
    },
    "pennystocks_com": {
        "url": "https://www.pennystocks.com/news/",
        "rss": "https://www.pennystocks.com/feed/",
    },
    "microcapdaily": {
        "url": "https://microcapdaily.com/",
        "rss": "https://microcapdaily.com/feed/",
    },
    "smallcaps": {
        "url": "https://smallcaps.com.au/news/",
        "rss": "https://smallcaps.com.au/feed/",
    },
}


class PennyStocksScraper(BaseScraper):
    """Scraper for penny stock and micro-cap news sites."""

    # Ticker extraction pattern
    TICKER_PATTERN = re.compile(
        r"(?:NASDAQ|NYSE|OTC|OTCQB|OTCQX|PINK)?[:\s]*\(?([A-Z]{1,5})\)?",
        re.IGNORECASE,
    )

    def __init__(
        self,
        sources: dict[str, dict] | None = None,
        rate_limit: float = 3.0,
        use_proxy: bool = True,
    ):
        """Initialize penny stocks scraper.

        Args:
            sources: Dictionary of source configs
            rate_limit: Seconds between requests
            use_proxy: Whether to use proxy
        """
        super().__init__(rate_limit=rate_limit, use_proxy=use_proxy)
        self.sources = sources or PENNY_STOCK_SOURCES

    async def scrape(self) -> list[dict[str, Any]]:
        """Scrape all penny stock news sources.

        Returns:
            List of scraped articles
        """
        all_articles = []

        for source_name, config in self.sources.items():
            try:
                # Try RSS first
                if "rss" in config:
                    articles = await self._scrape_rss(source_name, config["rss"])
                else:
                    articles = await self._scrape_html(source_name, config["url"])

                all_articles.extend(articles)

            except Exception as e:
                logger.error("Failed to scrape source", source=source_name, error=str(e))

        return all_articles

    async def _scrape_rss(
        self,
        source_name: str,
        rss_url: str,
    ) -> list[dict[str, Any]]:
        """Scrape from RSS feed.

        Args:
            source_name: Name of the source
            rss_url: RSS feed URL

        Returns:
            List of articles
        """
        import feedparser

        response = await self.fetch(rss_url)
        feed = feedparser.parse(response.text)

        articles = []

        for entry in feed.entries[:30]:  # Limit per source
            article = self._parse_rss_entry(entry, source_name)
            if article and not self._is_duplicate(article.get("headline", "")):
                articles.append(article)

        logger.info("Scraped RSS", source=source_name, count=len(articles))
        return articles

    def _parse_rss_entry(self, entry: Any, source_name: str) -> dict[str, Any] | None:
        """Parse RSS entry into article dict."""
        try:
            title = entry.get("title", "").strip()
            if not title:
                return None

            # Get content
            content = ""
            if hasattr(entry, "content") and entry.content:
                content = entry.content[0].get("value", "")
            elif hasattr(entry, "summary"):
                content = entry.summary

            # Clean HTML
            soup = BeautifulSoup(content, "lxml")
            clean_content = soup.get_text(separator=" ", strip=True)

            # Extract tickers
            full_text = f"{title} {clean_content}"
            tickers = self._extract_tickers(full_text)

            # Parse date
            published = datetime.now(timezone.utc).isoformat()
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
                except (TypeError, ValueError) as e:
                    logger.debug("Failed to parse date, using current time", title=title[:50], error=str(e))

            return {
                "headline": title,
                "summary": clean_content[:500],
                "content": clean_content,
                "url": entry.get("link", ""),
                "published_at": published,
                "source": source_name,
                "ticker": tickers[0] if tickers else "",
                "extracted_tickers": tickers,
                "event_type": "PENNY_STOCK_NEWS",
                "event_category": "NEWS",
            }

        except Exception as e:
            logger.warning("Failed to parse RSS entry", source=source_name, error=str(e))
            return None

    async def _scrape_html(
        self,
        source_name: str,
        url: str,
    ) -> list[dict[str, Any]]:
        """Scrape from HTML page.

        Args:
            source_name: Name of the source
            url: Page URL

        Returns:
            List of articles
        """
        response = await self.fetch(url)
        soup = BeautifulSoup(response.text, "lxml")

        articles = []

        # Generic article selectors
        article_selectors = [
            "article",
            ".post",
            ".news-item",
            ".article",
            ".entry",
        ]

        for selector in article_selectors:
            elements = soup.select(selector)
            if elements:
                for elem in elements[:20]:
                    article = self._parse_html_article(elem, source_name, url)
                    if article and not self._is_duplicate(article.get("headline", "")):
                        articles.append(article)
                break

        logger.info("Scraped HTML", source=source_name, count=len(articles))
        return articles

    def _parse_html_article(
        self,
        elem: Any,
        source_name: str,
        base_url: str,
    ) -> dict[str, Any] | None:
        """Parse HTML article element."""
        try:
            # Find title
            title_elem = elem.select_one("h1, h2, h3, .title, .headline")
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            if not title or len(title) < 10:
                return None

            # Find link
            link = ""
            link_elem = elem.select_one("a[href]")
            if link_elem:
                link = link_elem.get("href", "")
                if link and not link.startswith("http"):
                    from urllib.parse import urljoin
                    link = urljoin(base_url, link)

            # Find date
            date_elem = elem.select_one("time, .date, .published")
            date_str = datetime.now(timezone.utc).isoformat()
            if date_elem:
                date_text = date_elem.get("datetime", date_elem.get_text(strip=True))
                # Try to parse date
                try:
                    from dateutil import parser
                    parsed_date = parser.parse(date_text)
                    if parsed_date.tzinfo is None:
                        parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                    date_str = parsed_date.isoformat()
                except Exception as e:
                    logger.debug("Failed to parse HTML date", date_text=date_text[:30] if date_text else "", error=str(e))

            # Find summary
            summary_elem = elem.select_one("p, .summary, .excerpt, .description")
            summary = ""
            if summary_elem:
                summary = summary_elem.get_text(strip=True)[:500]

            # Extract tickers
            full_text = f"{title} {summary}"
            tickers = self._extract_tickers(full_text)

            return {
                "headline": title,
                "summary": summary,
                "url": link,
                "published_at": date_str,
                "source": source_name,
                "ticker": tickers[0] if tickers else "",
                "extracted_tickers": tickers,
                "event_type": "PENNY_STOCK_NEWS",
                "event_category": "NEWS",
            }

        except Exception as e:
            logger.warning("Failed to parse HTML article", source=source_name, error=str(e))
            return None

    def _extract_tickers(self, text: str) -> list[str]:
        """Extract ticker symbols from text.

        Args:
            text: Text to search

        Returns:
            List of ticker symbols
        """
        # Known exclusions (common words that look like tickers)
        exclusions = {
            "A", "I", "US", "UK", "EU", "CEO", "CFO", "IPO", "ETF", "SEC",
            "FDA", "FTC", "NYSE", "NASDAQ", "OTC", "OTCQB", "OTCQX", "PINK",
            "PR", "IT", "AI", "EV", "THE", "AND", "FOR", "NEW", "INC", "LTD",
            "LLC", "CORP", "CO", "BY", "OF", "TO", "IN", "ON", "AT", "AS",
            "UP", "PM", "AM", "TV", "PC", "UK", "SA", "AG", "AB", "BV",
        }

        matches = self.TICKER_PATTERN.findall(text.upper())
        tickers = []

        for match in matches:
            if match not in exclusions and 1 <= len(match) <= 5:
                tickers.append(match)

        return list(dict.fromkeys(tickers))[:10]  # Dedupe, limit to 10

    async def stream(
        self,
        poll_interval: float = 120.0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream new articles from all sources.

        Args:
            poll_interval: Seconds between poll cycles

        Yields:
            New articles
        """
        while True:
            try:
                articles = await self.scrape()

                for article in articles:
                    yield self.normalize_event(article)

            except Exception as e:
                logger.error("Stream error", error=str(e))

            await asyncio.sleep(poll_interval)


async def main():
    """Example usage of penny stocks scraper."""
    async with PennyStocksScraper() as scraper:
        articles = await scraper.scrape()
        print(f"Scraped {len(articles)} articles")

        for article in articles[:5]:
            tickers = article.get("extracted_tickers", [])
            print(f"- [{', '.join(tickers) or 'N/A'}] {article.get('headline', '')[:60]}...")


if __name__ == "__main__":
    asyncio.run(main())
