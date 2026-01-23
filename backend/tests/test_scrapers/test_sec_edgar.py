"""Tests for SEC EDGAR polling client."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import json

import httpx
import pytest

from backend.ingestion.sec_edgar.polling_client import (
    SECPollingClient,
    SEC_COMPANY_TICKERS_URL,
    SEC_SUBMISSIONS_URL,
)


class TestSECPollingClientInit:
    """Tests for SECPollingClient initialization."""

    def test_default_user_agent(self):
        """Test default user agent from settings."""
        with patch("backend.ingestion.sec_edgar.polling_client.settings") as mock_settings:
            mock_settings.sec_user_agent = "Test User Agent"
            client = SECPollingClient()
            assert client.user_agent == "Test User Agent"

    def test_custom_user_agent(self):
        """Test custom user agent can be provided."""
        client = SECPollingClient(user_agent="Custom Agent")
        assert client.user_agent == "Custom Agent"

    def test_initial_state(self):
        """Test initial state of client."""
        client = SECPollingClient()
        assert client._client is None
        assert client._ticker_to_cik == {}
        assert client._cik_to_ticker == {}


class TestSECPollingClientTickerMapping:
    """Tests for ticker/CIK mapping functionality."""

    @pytest.mark.asyncio
    async def test_load_ticker_mapping_success(self):
        """Test successful loading of ticker mapping."""
        client = SECPollingClient(user_agent="Test Agent")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "0": {"ticker": "AAPL", "cik_str": "320193"},
            "1": {"ticker": "MSFT", "cik_str": "789019"},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async with client:
                pass

        assert client._ticker_to_cik.get("AAPL") == "320193"
        assert client._ticker_to_cik.get("MSFT") == "789019"
        assert client._cik_to_ticker.get("320193") == "AAPL"
        assert client._cik_to_ticker.get("789019") == "MSFT"

    def test_get_cik_existing_ticker(self):
        """Test getting CIK for existing ticker."""
        client = SECPollingClient()
        client._ticker_to_cik = {"AAPL": "320193"}

        cik = client.get_cik("AAPL")
        assert cik == "320193"

    def test_get_cik_case_insensitive(self):
        """Test CIK lookup is case insensitive."""
        client = SECPollingClient()
        client._ticker_to_cik = {"AAPL": "320193"}

        cik = client.get_cik("aapl")
        assert cik == "320193"

    def test_get_cik_unknown_ticker(self):
        """Test getting CIK for unknown ticker returns None."""
        client = SECPollingClient()
        client._ticker_to_cik = {}

        cik = client.get_cik("UNKNOWN")
        assert cik is None

    def test_get_ticker_existing_cik(self):
        """Test getting ticker for existing CIK."""
        client = SECPollingClient()
        client._cik_to_ticker = {"320193": "AAPL"}

        ticker = client.get_ticker("320193")
        assert ticker == "AAPL"

    def test_get_ticker_normalizes_cik(self):
        """Test CIK is normalized (leading zeros removed)."""
        client = SECPollingClient()
        client._cik_to_ticker = {"320193": "AAPL"}

        ticker = client.get_ticker("0000320193")
        assert ticker == "AAPL"

    def test_get_ticker_unknown_cik(self):
        """Test getting ticker for unknown CIK returns None."""
        client = SECPollingClient()
        client._cik_to_ticker = {}

        ticker = client.get_ticker("999999")
        assert ticker is None


class TestSECPollingClientGetFilings:
    """Tests for getting company filings."""

    @pytest.mark.asyncio
    async def test_get_company_filings_by_ticker(self):
        """Test fetching filings by ticker symbol."""
        client = SECPollingClient(user_agent="Test Agent")
        client._ticker_to_cik = {"AAPL": "320193"}
        client._cik_to_ticker = {"320193": "AAPL"}

        mock_ticker_response = MagicMock()
        mock_ticker_response.json.return_value = {"0": {"ticker": "AAPL", "cik_str": "320193"}}
        mock_ticker_response.raise_for_status = MagicMock()

        mock_filings_response = MagicMock()
        mock_filings_response.json.return_value = {
            "name": "Apple Inc.",
            "filings": {
                "recent": {
                    "form": ["4", "8-K", "10-Q"],
                    "filingDate": ["2024-01-15", "2024-01-10", "2024-01-05"],
                    "accessionNumber": ["0001-24-000001", "0001-24-000002", "0001-24-000003"],
                    "primaryDocument": ["doc1.htm", "doc2.htm", "doc3.htm"],
                }
            }
        }
        mock_filings_response.raise_for_status = MagicMock()

        async with client:
            client._client.get = AsyncMock(side_effect=[mock_ticker_response, mock_filings_response])

            filings = await client.get_company_filings(ticker="AAPL", limit=10)

        assert len(filings) == 3
        assert filings[0]["ticker"] == "AAPL"
        assert filings[0]["company_name"] == "Apple Inc."
        assert filings[0]["filing_type"] == "4"
        assert filings[0]["source"] == "sec_edgar"

    @pytest.mark.asyncio
    async def test_get_company_filings_by_cik(self):
        """Test fetching filings by CIK."""
        client = SECPollingClient(user_agent="Test Agent")
        client._cik_to_ticker = {"320193": "AAPL"}

        mock_ticker_response = MagicMock()
        mock_ticker_response.json.return_value = {}
        mock_ticker_response.raise_for_status = MagicMock()

        mock_filings_response = MagicMock()
        mock_filings_response.json.return_value = {
            "name": "Apple Inc.",
            "filings": {
                "recent": {
                    "form": ["4"],
                    "filingDate": ["2024-01-15"],
                    "accessionNumber": ["0001-24-000001"],
                    "primaryDocument": ["doc1.htm"],
                }
            }
        }
        mock_filings_response.raise_for_status = MagicMock()

        async with client:
            client._client.get = AsyncMock(side_effect=[mock_ticker_response, mock_filings_response])

            filings = await client.get_company_filings(cik="320193", limit=10)

        assert len(filings) == 1
        assert filings[0]["cik"] == "320193"

    @pytest.mark.asyncio
    async def test_get_company_filings_filter_by_type(self):
        """Test filtering filings by type."""
        client = SECPollingClient(user_agent="Test Agent")
        client._ticker_to_cik = {"AAPL": "320193"}
        client._cik_to_ticker = {"320193": "AAPL"}

        mock_ticker_response = MagicMock()
        mock_ticker_response.json.return_value = {}
        mock_ticker_response.raise_for_status = MagicMock()

        mock_filings_response = MagicMock()
        mock_filings_response.json.return_value = {
            "name": "Apple Inc.",
            "filings": {
                "recent": {
                    "form": ["4", "8-K", "4", "10-Q"],
                    "filingDate": ["2024-01-15", "2024-01-10", "2024-01-08", "2024-01-05"],
                    "accessionNumber": ["0001", "0002", "0003", "0004"],
                    "primaryDocument": ["d1.htm", "d2.htm", "d3.htm", "d4.htm"],
                }
            }
        }
        mock_filings_response.raise_for_status = MagicMock()

        async with client:
            client._client.get = AsyncMock(side_effect=[mock_ticker_response, mock_filings_response])

            filings = await client.get_company_filings(
                ticker="AAPL",
                filing_types=["4"],
                limit=100
            )

        assert len(filings) == 2
        assert all(f["filing_type"] == "4" for f in filings)

    @pytest.mark.asyncio
    async def test_get_company_filings_filter_by_date_range(self):
        """Test filtering filings by date range."""
        client = SECPollingClient(user_agent="Test Agent")
        client._ticker_to_cik = {"AAPL": "320193"}
        client._cik_to_ticker = {"320193": "AAPL"}

        mock_ticker_response = MagicMock()
        mock_ticker_response.json.return_value = {}
        mock_ticker_response.raise_for_status = MagicMock()

        mock_filings_response = MagicMock()
        mock_filings_response.json.return_value = {
            "name": "Apple Inc.",
            "filings": {
                "recent": {
                    "form": ["4", "4", "4"],
                    "filingDate": ["2024-01-15", "2024-01-10", "2024-01-05"],
                    "accessionNumber": ["0001", "0002", "0003"],
                    "primaryDocument": ["d1.htm", "d2.htm", "d3.htm"],
                }
            }
        }
        mock_filings_response.raise_for_status = MagicMock()

        async with client:
            client._client.get = AsyncMock(side_effect=[mock_ticker_response, mock_filings_response])

            filings = await client.get_company_filings(
                ticker="AAPL",
                start_date=date(2024, 1, 8),
                end_date=date(2024, 1, 12),
                limit=100
            )

        assert len(filings) == 1
        assert filings[0]["filing_date"] == "2024-01-10"

    @pytest.mark.asyncio
    async def test_get_company_filings_unknown_ticker(self):
        """Test fetching filings for unknown ticker returns empty list."""
        client = SECPollingClient(user_agent="Test Agent")
        client._ticker_to_cik = {}

        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        async with client:
            client._client.get = AsyncMock(return_value=mock_response)

            filings = await client.get_company_filings(ticker="UNKNOWN")

        assert filings == []

    @pytest.mark.asyncio
    async def test_get_company_filings_respects_limit(self):
        """Test filing limit is respected."""
        client = SECPollingClient(user_agent="Test Agent")
        client._ticker_to_cik = {"AAPL": "320193"}
        client._cik_to_ticker = {"320193": "AAPL"}

        mock_ticker_response = MagicMock()
        mock_ticker_response.json.return_value = {}
        mock_ticker_response.raise_for_status = MagicMock()

        mock_filings_response = MagicMock()
        mock_filings_response.json.return_value = {
            "name": "Apple Inc.",
            "filings": {
                "recent": {
                    "form": ["4"] * 100,
                    "filingDate": ["2024-01-15"] * 100,
                    "accessionNumber": [f"000{i}" for i in range(100)],
                    "primaryDocument": [f"d{i}.htm" for i in range(100)],
                }
            }
        }
        mock_filings_response.raise_for_status = MagicMock()

        async with client:
            client._client.get = AsyncMock(side_effect=[mock_ticker_response, mock_filings_response])

            filings = await client.get_company_filings(ticker="AAPL", limit=5)

        assert len(filings) == 5

    @pytest.mark.asyncio
    async def test_get_company_filings_404_returns_empty(self):
        """Test 404 response returns empty list."""
        client = SECPollingClient(user_agent="Test Agent")
        client._ticker_to_cik = {"TEST": "123456"}

        mock_ticker_response = MagicMock()
        mock_ticker_response.json.return_value = {}
        mock_ticker_response.raise_for_status = MagicMock()

        mock_error_response = MagicMock()
        mock_error_response.status_code = 404
        http_error = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=mock_error_response
        )

        async with client:
            client._client.get = AsyncMock(side_effect=[mock_ticker_response, http_error])

            filings = await client.get_company_filings(ticker="TEST")

        assert filings == []


class TestSECPollingClientGetFilingContent:
    """Tests for fetching filing content."""

    @pytest.mark.asyncio
    async def test_get_filing_content_success(self):
        """Test successful filing content retrieval."""
        client = SECPollingClient(user_agent="Test Agent")

        mock_ticker_response = MagicMock()
        mock_ticker_response.json.return_value = {}
        mock_ticker_response.raise_for_status = MagicMock()

        mock_content_response = MagicMock()
        mock_content_response.text = "<html>Filing content here</html>"
        mock_content_response.raise_for_status = MagicMock()

        async with client:
            client._client.get = AsyncMock(side_effect=[mock_ticker_response, mock_content_response])

            content = await client.get_filing_content(
                "https://www.sec.gov/Archives/edgar/data/123/000123/filing.htm"
            )

        assert content == "<html>Filing content here</html>"

    @pytest.mark.asyncio
    async def test_get_filing_content_requires_client(self):
        """Test filing content requires initialized client."""
        client = SECPollingClient(user_agent="Test Agent")

        with pytest.raises(RuntimeError, match="Client not initialized"):
            await client.get_filing_content("https://example.com/filing.htm")


class TestSECPollingClientInsiderTrades:
    """Tests for insider trade functionality."""

    @pytest.mark.asyncio
    async def test_get_insider_trades(self):
        """Test getting Form 4 insider trades."""
        client = SECPollingClient(user_agent="Test Agent")
        client._ticker_to_cik = {"AAPL": "320193"}
        client._cik_to_ticker = {"320193": "AAPL"}

        mock_ticker_response = MagicMock()
        mock_ticker_response.json.return_value = {}
        mock_ticker_response.raise_for_status = MagicMock()

        # Create filings within the date range
        today = datetime.now(timezone.utc).date()
        mock_filings_response = MagicMock()
        mock_filings_response.json.return_value = {
            "name": "Apple Inc.",
            "filings": {
                "recent": {
                    "form": ["4", "8-K", "4"],
                    "filingDate": [
                        today.strftime("%Y-%m-%d"),
                        today.strftime("%Y-%m-%d"),
                        today.strftime("%Y-%m-%d"),
                    ],
                    "accessionNumber": ["0001", "0002", "0003"],
                    "primaryDocument": ["d1.htm", "d2.htm", "d3.htm"],
                }
            }
        }
        mock_filings_response.raise_for_status = MagicMock()

        async with client:
            client._client.get = AsyncMock(side_effect=[mock_ticker_response, mock_filings_response])

            filings = await client.get_insider_trades(ticker="AAPL", days=30)

        # Should only return Form 4 filings
        assert all(f["filing_type"] == "4" for f in filings)


class TestSECPollingClientFilingURL:
    """Tests for filing URL construction."""

    @pytest.mark.asyncio
    async def test_filing_url_format(self):
        """Test filing URL is correctly constructed."""
        client = SECPollingClient(user_agent="Test Agent")
        client._ticker_to_cik = {"AAPL": "320193"}
        client._cik_to_ticker = {"320193": "AAPL"}

        mock_ticker_response = MagicMock()
        mock_ticker_response.json.return_value = {}
        mock_ticker_response.raise_for_status = MagicMock()

        mock_filings_response = MagicMock()
        mock_filings_response.json.return_value = {
            "name": "Apple Inc.",
            "filings": {
                "recent": {
                    "form": ["4"],
                    "filingDate": ["2024-01-15"],
                    "accessionNumber": ["0001234567-24-000001"],
                    "primaryDocument": ["filing.htm"],
                }
            }
        }
        mock_filings_response.raise_for_status = MagicMock()

        async with client:
            client._client.get = AsyncMock(side_effect=[mock_ticker_response, mock_filings_response])

            filings = await client.get_company_filings(ticker="AAPL", limit=1)

        assert len(filings) == 1
        # URL should contain CIK and accession number without dashes
        filing_url = filings[0]["filing_url"]
        assert "320193" in filing_url
        assert "000123456724000001" in filing_url
        assert "filing.htm" in filing_url
