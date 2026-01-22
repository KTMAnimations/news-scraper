"""FINRA OTC daily list parser."""

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)

# FINRA OTC daily list URL
FINRA_DAILY_LIST_URL = "https://otce.finra.org/otce/dailyList"


@dataclass
class DailyListEntry:
    """Entry from FINRA OTC daily list."""

    symbol: str
    security_name: str
    market: str
    reason_code: str
    reason_description: str
    effective_date: str
    is_addition: bool
    is_deletion: bool
    is_change: bool

    @property
    def signal(self) -> str:
        """Get trading signal from entry type."""
        # Deletions (delistings) are bearish
        if self.is_deletion:
            return "BEARISH"
        # Additions can be bullish (new listing) or neutral
        if self.is_addition:
            return "NEUTRAL"
        return "NEUTRAL"


class DailyListParser:
    """Parser for FINRA OTC daily lists."""

    # Reason codes that indicate significant events
    SIGNIFICANT_REASONS = {
        "ADD": "Security added to OTC",
        "DEL": "Security deleted from OTC",
        "NC": "Name change",
        "SC": "Symbol change",
        "REV": "Reverse split",
        "FWD": "Forward split",
        "CH11": "Chapter 11 bankruptcy",
        "CH7": "Chapter 7 bankruptcy",
        "CE": "Caveat emptor",
        "CEX": "Caveat emptor removed",
    }

    def __init__(self):
        """Initialize daily list parser."""
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "DailyListParser":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "Accept": "text/csv, application/csv, text/plain",
            },
            timeout=60.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def fetch_daily_list(
        self,
        date: str | None = None,
    ) -> list[DailyListEntry]:
        """Fetch and parse FINRA OTC daily list.

        Args:
            date: Date in YYYY-MM-DD format, or None for today

        Returns:
            List of daily list entries
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        params = {}
        if date:
            params["date"] = date

        try:
            response = await self._client.get(FINRA_DAILY_LIST_URL, params=params)
            response.raise_for_status()

            return self._parse_csv(response.text)

        except httpx.HTTPStatusError as e:
            logger.error("Failed to fetch daily list", status=e.response.status_code)
            return []
        except Exception as e:
            logger.error("Error fetching daily list", error=str(e))
            return []

    def _parse_csv(self, content: str) -> list[DailyListEntry]:
        """Parse CSV content into daily list entries."""
        entries = []

        try:
            reader = csv.DictReader(io.StringIO(content))

            for row in reader:
                symbol = row.get("Symbol", row.get("SYMBOL", "")).strip()
                if not symbol:
                    continue

                reason_code = row.get("ReasonCode", row.get("REASON_CODE", "")).strip()
                effective_date = row.get("EffectiveDate", row.get("EFFECTIVE_DATE", "")).strip()

                entry = DailyListEntry(
                    symbol=symbol.upper(),
                    security_name=row.get("SecurityName", row.get("SECURITY_NAME", "")).strip(),
                    market=row.get("Market", row.get("MARKET", "")).strip(),
                    reason_code=reason_code,
                    reason_description=self.SIGNIFICANT_REASONS.get(
                        reason_code,
                        row.get("ReasonDescription", "").strip(),
                    ),
                    effective_date=effective_date,
                    is_addition=reason_code == "ADD",
                    is_deletion=reason_code == "DEL",
                    is_change=reason_code in ("NC", "SC", "REV", "FWD"),
                )

                entries.append(entry)

        except Exception as e:
            logger.error("Failed to parse daily list CSV", error=str(e))

        return entries

    async def get_significant_events(
        self,
        date: str | None = None,
    ) -> list[DailyListEntry]:
        """Get significant events from daily list.

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            List of significant events
        """
        entries = await self.fetch_daily_list(date)

        # Filter to significant events only
        significant = [
            entry for entry in entries
            if entry.reason_code in self.SIGNIFICANT_REASONS
        ]

        return significant

    def entry_to_event(self, entry: DailyListEntry) -> dict[str, Any]:
        """Convert daily list entry to event dictionary.

        Args:
            entry: DailyListEntry object

        Returns:
            Event dictionary
        """
        # Determine event type and sentiment
        event_type = "OTC_LISTING"
        sentiment = "neutral"
        alpha_score = 0.0

        if entry.is_deletion:
            event_type = "OTC_DELISTING"
            sentiment = "negative"
            alpha_score = -0.7
        elif entry.reason_code == "CH11":
            event_type = "BANKRUPTCY"
            sentiment = "negative"
            alpha_score = -0.9
        elif entry.reason_code == "CH7":
            event_type = "BANKRUPTCY"
            sentiment = "negative"
            alpha_score = -0.95
        elif entry.reason_code == "CE":
            event_type = "CAVEAT_EMPTOR"
            sentiment = "negative"
            alpha_score = -0.8
        elif entry.reason_code == "CEX":
            event_type = "CAVEAT_REMOVED"
            sentiment = "positive"
            alpha_score = 0.6
        elif entry.reason_code == "REV":
            event_type = "REVERSE_SPLIT"
            sentiment = "negative"
            alpha_score = -0.4
        elif entry.is_addition:
            event_type = "OTC_LISTING"
            sentiment = "neutral"
            alpha_score = 0.1

        headline = f"{entry.symbol}: {entry.reason_description}"

        return {
            "ticker": entry.symbol,
            "event_type": event_type,
            "event_category": "OTC_ACTION",
            "headline": headline,
            "summary": f"{entry.security_name} ({entry.symbol}): {entry.reason_description}. Effective date: {entry.effective_date}",
            "source_name": "FINRA OTC",
            "sentiment_label": sentiment,
            "alpha_score": alpha_score,
            "direction": entry.signal,
            "metadata": {
                "reason_code": entry.reason_code,
                "market": entry.market,
                "effective_date": entry.effective_date,
            },
            "event_time": entry.effective_date or datetime.now(timezone.utc).isoformat(),
            "source": "finra_otc",
        }


async def main():
    """Example usage of daily list parser."""
    async with DailyListParser() as parser:
        events = await parser.get_significant_events()
        print(f"Found {len(events)} significant events")

        for entry in events[:10]:
            print(f"{entry.symbol}: {entry.reason_code} - {entry.reason_description}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
