"""SEC EDGAR polling client for batch filing retrieval."""

import asyncio
from datetime import date, datetime, timezone
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import settings

logger = structlog.get_logger(__name__)

# SEC EDGAR API endpoints
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_FILING_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{filename}"


class SECPollingClient:
    """Client for polling SEC EDGAR for specific company filings."""

    def __init__(self, user_agent: str | None = None):
        """Initialize SEC polling client.

        Args:
            user_agent: User agent string for SEC requests
        """
        self.user_agent = user_agent or settings.sec_user_agent
        self._client: httpx.AsyncClient | None = None
        self._ticker_to_cik: dict[str, str] = {}
        self._cik_to_ticker: dict[str, str] = {}

    async def __aenter__(self) -> "SECPollingClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            headers={"User-Agent": self.user_agent},
            timeout=60.0,
        )
        await self._load_ticker_mapping()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def _load_ticker_mapping(self) -> None:
        """Load ticker to CIK mapping from SEC."""
        if not self._client:
            raise RuntimeError("Client not initialized")

        try:
            response = await self._client.get(SEC_COMPANY_TICKERS_URL)
            response.raise_for_status()

            data = response.json()

            for entry in data.values():
                ticker = entry.get("ticker", "").upper()
                cik = str(entry.get("cik_str", ""))

                if ticker and cik:
                    self._ticker_to_cik[ticker] = cik
                    self._cik_to_ticker[cik] = ticker

            logger.info("Loaded SEC ticker mapping", count=len(self._ticker_to_cik))

        except Exception as e:
            logger.error("Failed to load ticker mapping", error=str(e))

    def get_cik(self, ticker: str) -> str | None:
        """Get CIK for a ticker symbol.

        Args:
            ticker: Stock ticker symbol

        Returns:
            CIK string or None
        """
        return self._ticker_to_cik.get(ticker.upper())

    def get_ticker(self, cik: str) -> str | None:
        """Get ticker for a CIK.

        Args:
            cik: SEC CIK number

        Returns:
            Ticker symbol or None
        """
        # Normalize CIK (remove leading zeros)
        cik = str(int(cik))
        return self._cik_to_ticker.get(cik)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def get_company_filings(
        self,
        ticker: str | None = None,
        cik: str | None = None,
        filing_types: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get filings for a company.

        Args:
            ticker: Stock ticker symbol
            cik: SEC CIK number (alternative to ticker)
            filing_types: List of filing types to filter (e.g., ["4", "8-K"])
            start_date: Start date for filtering
            end_date: End date for filtering
            limit: Maximum number of filings to return

        Returns:
            List of filing dictionaries
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        # Resolve CIK
        if ticker and not cik:
            cik = self.get_cik(ticker)

        if not cik:
            logger.warning("Could not resolve CIK", ticker=ticker, cik=cik)
            return []

        # Pad CIK to 10 digits
        cik_padded = str(cik).zfill(10)

        url = SEC_SUBMISSIONS_URL.format(cik=cik_padded)

        try:
            response = await self._client.get(url)
            response.raise_for_status()

            data = response.json()
            company_name = data.get("name", "")
            ticker = ticker or self.get_ticker(cik) or ""

            filings = []
            recent = data.get("filings", {}).get("recent", {})

            # Extract filing arrays
            forms = recent.get("form", [])
            filing_dates = recent.get("filingDate", [])
            accessions = recent.get("accessionNumber", [])
            primary_docs = recent.get("primaryDocument", [])

            for i in range(min(len(forms), limit)):
                form_type = forms[i]

                # Filter by filing type if specified
                if filing_types and form_type not in filing_types:
                    continue

                filing_date_str = filing_dates[i]
                filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d").date()

                # Filter by date range
                if start_date and filing_date < start_date:
                    continue
                if end_date and filing_date > end_date:
                    continue

                accession = accessions[i].replace("-", "")
                primary_doc = primary_docs[i]

                filing_url = SEC_FILING_URL.format(
                    cik=cik,
                    accession=accession,
                    filename=primary_doc,
                )

                filings.append({
                    "ticker": ticker,
                    "cik": cik,
                    "company_name": company_name,
                    "filing_type": form_type,
                    "filing_date": filing_date_str,
                    "accession_number": accessions[i],
                    "filing_url": filing_url,
                    "primary_document": primary_doc,
                    "source": "sec_edgar",
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                })

                if len(filings) >= limit:
                    break

            logger.info(
                "Fetched company filings",
                ticker=ticker,
                cik=cik,
                count=len(filings),
            )

            return filings

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("Company not found", cik=cik)
                return []
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def get_filing_content(self, filing_url: str) -> str:
        """Fetch the raw content of a filing.

        Args:
            filing_url: URL to the filing document

        Returns:
            Raw filing content as string
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        response = await self._client.get(filing_url)
        response.raise_for_status()

        # Rate limit compliance
        await asyncio.sleep(0.1)

        return response.text

    async def get_insider_trades(
        self,
        ticker: str | None = None,
        cik: str | None = None,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Get Form 4 insider trading filings.

        Args:
            ticker: Stock ticker symbol
            cik: SEC CIK number
            days: Number of days to look back

        Returns:
            List of Form 4 filings
        """
        from datetime import timedelta

        start_date = date.today() - timedelta(days=days)

        return await self.get_company_filings(
            ticker=ticker,
            cik=cik,
            filing_types=["4"],
            start_date=start_date,
            limit=50,
        )


async def main():
    """Example usage of SEC polling client."""
    async with SECPollingClient() as client:
        # Get recent Form 4 filings for Apple
        filings = await client.get_insider_trades(ticker="AAPL", days=7)
        for filing in filings[:5]:
            print(f"{filing['filing_date']}: {filing['filing_type']} - {filing['filing_url']}")


if __name__ == "__main__":
    asyncio.run(main())
