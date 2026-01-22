"""SEC EDGAR streaming client for real-time filing ingestion."""

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable

import feedparser
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import settings

logger = structlog.get_logger(__name__)

# SEC EDGAR RSS feed URL
SEC_RSS_FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&company=&dateb=&owner=include&count=100&output=atom"

# Target filing types for alpha generation
PRIORITY_FILING_TYPES = {
    "4": "INSIDER_TRADE",  # Form 4 - Insider trading (CRITICAL)
    "8-K": "MATERIAL_EVENT",  # Material events (HIGH)
    "13D": "ACTIVIST_STAKE",  # Activist stakes (CRITICAL)
    "13G": "INSTITUTIONAL_STAKE",  # Institutional stakes
    "10-Q": "QUARTERLY_REPORT",  # Quarterly financials
    "10-K": "ANNUAL_REPORT",  # Annual financials
    "S-1": "IPO_REGISTRATION",  # IPO
    "424B": "PROSPECTUS",  # Prospectus supplement
    "DEF 14A": "PROXY_STATEMENT",  # Proxy statements
}

CRITICAL_FILINGS = {"4", "13D", "8-K"}


class SECStreamingClient:
    """Client for streaming SEC EDGAR filings in real-time via RSS polling."""

    def __init__(
        self,
        callback: Callable[[dict[str, Any]], None] | None = None,
        poll_interval: float = 10.0,
        user_agent: str | None = None,
    ):
        """Initialize SEC streaming client.

        Args:
            callback: Optional callback function for each filing
            poll_interval: Seconds between RSS feed polls (min 10s per SEC rules)
            user_agent: User agent string for SEC requests
        """
        self.callback = callback
        self.poll_interval = max(poll_interval, 10.0)  # SEC rate limit
        self.user_agent = user_agent or settings.sec_user_agent
        self._running = False
        self._seen_ids: set[str] = set()
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "SECStreamingClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/atom+xml",
            },
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def _fetch_feed(self) -> list[dict[str, Any]]:
        """Fetch and parse SEC RSS feed.

        Returns:
            List of parsed filing entries
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        response = await self._client.get(SEC_RSS_FEED_URL)
        response.raise_for_status()

        feed = feedparser.parse(response.text)
        entries = []

        for entry in feed.entries:
            filing = self._parse_entry(entry)
            if filing:
                entries.append(filing)

        return entries

    def _parse_entry(self, entry: Any) -> dict[str, Any] | None:
        """Parse a single RSS feed entry into filing data.

        Args:
            entry: feedparser entry object

        Returns:
            Parsed filing dict or None if invalid
        """
        try:
            # Extract filing type from title
            title = entry.get("title", "")
            filing_type = self._extract_filing_type(title)

            if not filing_type:
                return None

            # Parse the entry
            filing_id = entry.get("id", "")
            link = entry.get("link", "")

            # Extract CIK from link
            cik = self._extract_cik(link)

            # Parse updated time
            updated = entry.get("updated", "")
            try:
                filing_time = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                filing_time = datetime.now(timezone.utc)

            # Extract company name and ticker from title
            company_name = self._extract_company_name(title)

            return {
                "id": filing_id,
                "filing_type": filing_type,
                "filing_category": PRIORITY_FILING_TYPES.get(filing_type, "OTHER"),
                "cik": cik,
                "company_name": company_name,
                "title": title,
                "link": link,
                "filing_url": link,
                "filing_time": filing_time.isoformat(),
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "is_critical": filing_type in CRITICAL_FILINGS,
                "source": "sec_edgar",
            }

        except Exception as e:
            logger.warning("Failed to parse SEC entry", error=str(e), entry=str(entry)[:200])
            return None

    def _extract_filing_type(self, title: str) -> str | None:
        """Extract filing type from title string."""
        for form_type in PRIORITY_FILING_TYPES:
            if form_type in title.upper() or f"FORM {form_type}" in title.upper():
                return form_type
        return None

    def _extract_cik(self, link: str) -> str:
        """Extract CIK from SEC EDGAR link."""
        # Link format: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001234567
        if "CIK=" in link:
            parts = link.split("CIK=")
            if len(parts) > 1:
                cik = parts[1].split("&")[0]
                return cik.lstrip("0")
        return ""

    def _extract_company_name(self, title: str) -> str:
        """Extract company name from title."""
        # Title format: "FORM 4 - COMPANY NAME (CIK)"
        if " - " in title:
            parts = title.split(" - ", 1)
            if len(parts) > 1:
                name = parts[1]
                # Remove CIK suffix if present
                if "(" in name:
                    name = name.split("(")[0]
                return name.strip()
        return title

    async def stream_filings(self) -> AsyncIterator[dict[str, Any]]:
        """Stream filings as they become available.

        Yields:
            Filing dictionaries for new filings
        """
        self._running = True
        logger.info("Starting SEC filing stream", poll_interval=self.poll_interval)

        while self._running:
            try:
                entries = await self._fetch_feed()

                for filing in entries:
                    filing_id = filing["id"]

                    # Skip already seen filings
                    if filing_id in self._seen_ids:
                        continue

                    self._seen_ids.add(filing_id)

                    # Limit seen IDs to prevent memory growth
                    if len(self._seen_ids) > 10000:
                        # Keep most recent 5000
                        self._seen_ids = set(list(self._seen_ids)[-5000:])

                    logger.info(
                        "New SEC filing",
                        filing_type=filing["filing_type"],
                        company=filing["company_name"],
                        cik=filing["cik"],
                    )

                    if self.callback:
                        self.callback(filing)

                    yield filing

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning("SEC rate limit hit, backing off")
                    await asyncio.sleep(60)
                else:
                    logger.error("SEC HTTP error", status=e.response.status_code)
                    await asyncio.sleep(30)

            except Exception as e:
                logger.error("Error fetching SEC feed", error=str(e))
                await asyncio.sleep(30)

            await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        """Stop the streaming client."""
        self._running = False
        logger.info("SEC streaming client stopped")

    async def fetch_recent(self, count: int = 100) -> list[dict[str, Any]]:
        """Fetch recent filings without streaming.

        Args:
            count: Number of recent filings to fetch

        Returns:
            List of recent filings
        """
        entries = await self._fetch_feed()
        return entries[:count]


async def main():
    """Example usage of SEC streaming client."""
    async with SECStreamingClient(poll_interval=30) as client:
        async for filing in client.stream_filings():
            print(f"New filing: {filing['filing_type']} - {filing['company_name']}")


if __name__ == "__main__":
    asyncio.run(main())
