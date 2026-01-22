"""OTC Markets disclosure scraper for company news and filings."""

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx
import structlog
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import settings

logger = structlog.get_logger(__name__)

# OTC Markets endpoints
OTC_COMPANY_NEWS_URL = "https://www.otcmarkets.com/stock/{symbol}/news"
OTC_COMPANY_DISCLOSURE_URL = "https://www.otcmarkets.com/stock/{symbol}/disclosure"
OTC_COMPANY_PROFILE_URL = "https://www.otcmarkets.com/stock/{symbol}/profile"
OTC_API_COMPANY_URL = "https://backend.otcmarkets.com/otcapi/company/{symbol}/profile/full"
OTC_API_NEWS_URL = "https://backend.otcmarkets.com/otcapi/company/{symbol}/dns/news"


class OTCDisclosureScraper:
    """Scraper for OTC Markets company disclosures and news."""

    def __init__(self, rate_limit: float = 2.0):
        """Initialize OTC disclosure scraper.

        Args:
            rate_limit: Seconds between requests
        """
        self.rate_limit = rate_limit
        self._client: httpx.AsyncClient | None = None
        self._last_request: float = 0

    async def __aenter__(self) -> "OTCDisclosureScraper":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json, text/html",
            },
            timeout=30.0,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < self.rate_limit:
            await asyncio.sleep(self.rate_limit - elapsed)
        self._last_request = asyncio.get_event_loop().time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def get_company_profile(self, symbol: str) -> dict[str, Any] | None:
        """Get company profile from OTC Markets.

        Args:
            symbol: OTC stock symbol

        Returns:
            Company profile data or None
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        await self._rate_limit()

        try:
            # Try API endpoint first
            url = OTC_API_COMPANY_URL.format(symbol=symbol.upper())
            response = await self._client.get(url)

            if response.status_code == 200:
                data = response.json()
                return self._parse_profile_api(data, symbol)

        except httpx.HTTPStatusError:
            pass
        except Exception as e:
            logger.warning("API profile fetch failed", symbol=symbol, error=str(e))

        # Fall back to scraping
        try:
            url = OTC_COMPANY_PROFILE_URL.format(symbol=symbol.upper())
            response = await self._client.get(url)
            response.raise_for_status()

            return self._parse_profile_html(response.text, symbol)

        except Exception as e:
            logger.error("Profile fetch failed", symbol=symbol, error=str(e))
            return None

    def _parse_profile_api(self, data: dict[str, Any], symbol: str) -> dict[str, Any]:
        """Parse company profile from API response."""
        return {
            "symbol": symbol.upper(),
            "company_name": data.get("name", ""),
            "security_name": data.get("securityName", ""),
            "tier": data.get("tierGroup", ""),
            "tier_code": data.get("tierCode", ""),
            "market": data.get("market", ""),
            "country": data.get("countryOfIncorporation", ""),
            "state": data.get("stateOfIncorporation", ""),
            "industry": data.get("industry", ""),
            "sector": data.get("sector", ""),
            "cik": data.get("cik", ""),
            "is_caveat_emptor": data.get("isCaveatEmptor", False),
            "is_shell": data.get("isShell", False),
            "is_bankrupt": data.get("isBankrupt", False),
            "has_current_info": data.get("hasCurrentInfo", False),
            "outstanding_shares": data.get("outstandingShares"),
            "authorized_shares": data.get("authorizedShares"),
            "float_shares": data.get("float"),
            "source": "otc_markets",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def _parse_profile_html(self, html: str, symbol: str) -> dict[str, Any]:
        """Parse company profile from HTML response."""
        soup = BeautifulSoup(html, "lxml")

        profile = {
            "symbol": symbol.upper(),
            "source": "otc_markets",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

        # Extract company name
        name_elem = soup.select_one("h1.company-name, .company-header h1")
        if name_elem:
            profile["company_name"] = name_elem.get_text(strip=True)

        # Extract tier
        tier_elem = soup.select_one(".tier-badge, .market-tier")
        if tier_elem:
            profile["tier"] = tier_elem.get_text(strip=True)

        # Look for caveat emptor warning
        caveat = soup.select_one(".caveat-emptor, .skull-icon")
        profile["is_caveat_emptor"] = caveat is not None

        return profile

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def get_company_news(
        self,
        symbol: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get news for an OTC company.

        Args:
            symbol: OTC stock symbol
            limit: Maximum number of news items

        Returns:
            List of news items
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        await self._rate_limit()

        news_items = []

        try:
            # Try API endpoint first
            url = OTC_API_NEWS_URL.format(symbol=symbol.upper())
            response = await self._client.get(url)

            if response.status_code == 200:
                data = response.json()
                records = data.get("records", [])

                for record in records[:limit]:
                    news_items.append({
                        "symbol": symbol.upper(),
                        "headline": record.get("title", ""),
                        "source": record.get("sourceName", "OTC Markets"),
                        "published_at": record.get("newsDate", ""),
                        "url": record.get("link", ""),
                        "content": record.get("description", ""),
                        "news_type": record.get("newsType", ""),
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    })

                return news_items

        except Exception as e:
            logger.warning("API news fetch failed", symbol=symbol, error=str(e))

        # Fall back to scraping
        try:
            url = OTC_COMPANY_NEWS_URL.format(symbol=symbol.upper())
            response = await self._client.get(url)
            response.raise_for_status()

            return self._parse_news_html(response.text, symbol, limit)

        except Exception as e:
            logger.error("News fetch failed", symbol=symbol, error=str(e))
            return []

    def _parse_news_html(self, html: str, symbol: str, limit: int) -> list[dict[str, Any]]:
        """Parse news from HTML response."""
        soup = BeautifulSoup(html, "lxml")
        news_items = []

        # Find news entries
        entries = soup.select(".news-item, .news-row, article.news")

        for entry in entries[:limit]:
            title_elem = entry.select_one("h3, .news-title, .headline")
            date_elem = entry.select_one(".date, time, .news-date")
            link_elem = entry.select_one("a")

            if title_elem:
                news_items.append({
                    "symbol": symbol.upper(),
                    "headline": title_elem.get_text(strip=True),
                    "source": "OTC Markets",
                    "published_at": date_elem.get_text(strip=True) if date_elem else "",
                    "url": link_elem.get("href", "") if link_elem else "",
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                })

        return news_items

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def get_disclosures(
        self,
        symbol: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get company disclosures from OTC Markets.

        Args:
            symbol: OTC stock symbol
            limit: Maximum number of disclosures

        Returns:
            List of disclosure documents
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        await self._rate_limit()

        try:
            url = OTC_COMPANY_DISCLOSURE_URL.format(symbol=symbol.upper())
            response = await self._client.get(url)
            response.raise_for_status()

            return self._parse_disclosures_html(response.text, symbol, limit)

        except Exception as e:
            logger.error("Disclosure fetch failed", symbol=symbol, error=str(e))
            return []

    def _parse_disclosures_html(
        self,
        html: str,
        symbol: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Parse disclosures from HTML response."""
        soup = BeautifulSoup(html, "lxml")
        disclosures = []

        # Find disclosure entries
        entries = soup.select(".disclosure-item, .filing-row, tr.disclosure")

        for entry in entries[:limit]:
            title_elem = entry.select_one(".title, .filing-type, td:first-child")
            date_elem = entry.select_one(".date, td.date, time")
            link_elem = entry.select_one("a[href*='.pdf'], a[href*='disclosure']")

            if title_elem:
                disclosures.append({
                    "symbol": symbol.upper(),
                    "title": title_elem.get_text(strip=True),
                    "filing_date": date_elem.get_text(strip=True) if date_elem else "",
                    "document_url": link_elem.get("href", "") if link_elem else "",
                    "source": "OTC Markets",
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                })

        return disclosures

    async def monitor_symbols(
        self,
        symbols: list[str],
        poll_interval: float = 300.0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Monitor multiple OTC symbols for news and disclosures.

        Args:
            symbols: List of symbols to monitor
            poll_interval: Seconds between full cycles

        Yields:
            New news and disclosure items
        """
        seen_ids: set[str] = set()

        while True:
            for symbol in symbols:
                try:
                    # Get news
                    news = await self.get_company_news(symbol, limit=5)
                    for item in news:
                        item_id = f"{symbol}:{item.get('headline', '')[:50]}:{item.get('published_at', '')}"
                        if item_id not in seen_ids:
                            seen_ids.add(item_id)
                            item["event_type"] = "OTC_NEWS"
                            yield item

                    # Get disclosures
                    disclosures = await self.get_disclosures(symbol, limit=5)
                    for item in disclosures:
                        item_id = f"{symbol}:{item.get('title', '')[:50]}:{item.get('filing_date', '')}"
                        if item_id not in seen_ids:
                            seen_ids.add(item_id)
                            item["event_type"] = "OTC_DISCLOSURE"
                            yield item

                except Exception as e:
                    logger.error("Monitor error", symbol=symbol, error=str(e))

            # Limit seen set size
            if len(seen_ids) > 10000:
                seen_ids = set(list(seen_ids)[-5000:])

            await asyncio.sleep(poll_interval)


async def main():
    """Example usage of OTC disclosure scraper."""
    async with OTCDisclosureScraper() as scraper:
        profile = await scraper.get_company_profile("AABB")
        if profile:
            print(f"Company: {profile.get('company_name')}")
            print(f"Tier: {profile.get('tier')}")

        news = await scraper.get_company_news("AABB", limit=3)
        for item in news:
            print(f"News: {item.get('headline')}")


if __name__ == "__main__":
    asyncio.run(main())
