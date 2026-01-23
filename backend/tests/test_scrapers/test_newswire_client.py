"""Tests for NewswireClient scraper."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

import httpx
import pytest

from backend.ingestion.scrapers.newswire_client import NewswireClient, NEWSWIRE_FEEDS


class TestNewswireClientInit:
    """Tests for NewswireClient initialization."""

    def test_default_feeds(self):
        """Test default feeds are loaded."""
        client = NewswireClient()
        assert client.feeds == NEWSWIRE_FEEDS

    def test_custom_feeds(self):
        """Test custom feeds can be provided."""
        custom_feeds = {"test_wire": {"name": "Test Wire", "rss": "http://test.com/rss"}}
        client = NewswireClient(feeds=custom_feeds)
        assert client.feeds == custom_feeds

    def test_default_rate_limit(self):
        """Test default rate limit is 5 seconds."""
        client = NewswireClient()
        assert client.rate_limit == 5.0

    def test_filter_small_cap_default(self):
        """Test small cap filter is enabled by default."""
        client = NewswireClient()
        assert client.filter_small_cap is True


class TestNewswireClientTickerExtraction:
    """Tests for ticker extraction from press releases."""

    def test_extract_nyse_ticker(self):
        """Test extraction of NYSE prefixed ticker."""
        client = NewswireClient()
        text = "Company Inc. (NYSE: AAPL) announces earnings"
        tickers = client._extract_tickers(text)
        assert "AAPL" in tickers

    def test_extract_nasdaq_ticker(self):
        """Test extraction of NASDAQ prefixed ticker."""
        client = NewswireClient()
        text = "Tech Corp (NASDAQ: MSFT) reports Q4 results"
        tickers = client._extract_tickers(text)
        assert "MSFT" in tickers

    def test_extract_otc_ticker(self):
        """Test extraction of OTC prefixed ticker."""
        client = NewswireClient()
        text = "Small Co (OTC: SMCO) announces partnership"
        tickers = client._extract_tickers(text)
        assert "SMCO" in tickers

    def test_extract_otcqb_ticker(self):
        """Test extraction of OTCQB prefixed ticker."""
        client = NewswireClient()
        text = "Micro Corp (OTCQB: MCRO) files quarterly report"
        tickers = client._extract_tickers(text)
        assert "MCRO" in tickers

    def test_extract_multiple_tickers(self):
        """Test extraction of multiple tickers."""
        client = NewswireClient()
        text = "Company A (NYSE: AAPL) and Company B (NASDAQ: MSFT) announce merger"
        tickers = client._extract_tickers(text)
        assert "AAPL" in tickers
        assert "MSFT" in tickers

    def test_extract_ticker_in_parens_fallback(self):
        """Test fallback pattern for tickers in parentheses."""
        client = NewswireClient()
        text = "Apple Inc. (AAPL) reports strong earnings"
        tickers = client._extract_tickers(text)
        assert "AAPL" in tickers

    def test_deduplicate_tickers(self):
        """Test that duplicate tickers are removed."""
        client = NewswireClient()
        text = "Company (NYSE: AAPL) and again (NASDAQ: AAPL) mentioned twice"
        tickers = client._extract_tickers(text)
        assert tickers.count("AAPL") == 1

    def test_limit_ticker_count(self):
        """Test that ticker count is limited to 10."""
        client = NewswireClient()
        # Create text with many tickers
        tickers_text = " ".join([f"(NYSE: {chr(65+i)}{chr(65+j)})" for i in range(5) for j in range(5)])
        tickers = client._extract_tickers(tickers_text)
        assert len(tickers) <= 10

    def test_uppercase_conversion(self):
        """Test tickers are converted to uppercase."""
        client = NewswireClient()
        text = "Company (NYSE: aapl) with lowercase"
        tickers = client._extract_tickers(text)
        assert "AAPL" in tickers

    def test_validate_ticker_length(self):
        """Test only 1-5 character tickers are extracted."""
        client = NewswireClient()
        text = "(NYSE: A) (NYSE: AB) (NYSE: ABCDE) (NYSE: ABCDEF)"
        tickers = client._extract_tickers(text)
        assert "A" in tickers
        assert "AB" in tickers
        assert "ABCDE" in tickers
        assert "ABCDEF" not in tickers


class TestNewswireClientClassification:
    """Tests for press release classification."""

    def test_classify_earnings(self):
        """Test classification of earnings-related releases."""
        client = NewswireClient()
        event_type, category = client._classify_release(
            "Company Reports Strong Q4 Earnings",
            "Revenue exceeded expectations with net income up 15%."
        )
        assert event_type == "EARNINGS"
        assert category == "FINANCIAL"

    def test_classify_quarterly_results(self):
        """Test classification of quarterly results."""
        client = NewswireClient()
        event_type, category = client._classify_release(
            "Quarterly Results Announcement",
            "EPS of $1.50 beats estimates."
        )
        assert event_type == "EARNINGS"
        assert category == "FINANCIAL"

    def test_classify_acquisition(self):
        """Test classification of M&A announcements."""
        client = NewswireClient()
        event_type, category = client._classify_release(
            "Company to Acquire Competitor",
            "Definitive agreement signed for $500 million acquisition."
        )
        assert event_type == "ACQUISITION"
        assert category == "CORPORATE_ACTION"

    def test_classify_merger(self):
        """Test classification of merger announcements."""
        client = NewswireClient()
        event_type, category = client._classify_release(
            "Merger Agreement Announced",
            "All-stock merger creates industry leader."
        )
        assert event_type == "ACQUISITION"
        assert category == "CORPORATE_ACTION"

    def test_classify_offering(self):
        """Test classification of stock offerings."""
        client = NewswireClient()
        event_type, category = client._classify_release(
            "Public Offering Announced",
            "Company raises capital through stock offering."
        )
        assert event_type == "OFFERING"
        assert category == "FINANCING"

    def test_classify_private_placement(self):
        """Test classification of private placements."""
        client = NewswireClient()
        event_type, category = client._classify_release(
            "Private Placement Completed",
            "Company secures financing through private placement."
        )
        assert event_type == "OFFERING"
        assert category == "FINANCING"

    def test_classify_fda_news(self):
        """Test classification of FDA-related news."""
        client = NewswireClient()
        event_type, category = client._classify_release(
            "FDA Approval Received",
            "Drug candidate receives FDA clearance for Phase 3 trials."
        )
        assert event_type == "FDA_NEWS"
        assert category == "HEALTHCARE"

    def test_classify_clinical_trial(self):
        """Test classification of clinical trial news."""
        client = NewswireClient()
        event_type, category = client._classify_release(
            "Phase 2 Trial Results",
            "Clinical trial shows positive outcomes."
        )
        assert event_type == "FDA_NEWS"
        assert category == "HEALTHCARE"

    def test_classify_partnership(self):
        """Test classification of partnership announcements."""
        client = NewswireClient()
        event_type, category = client._classify_release(
            "Strategic Partnership Announced",
            "Companies enter strategic alliance for collaboration."
        )
        assert event_type == "PARTNERSHIP"
        assert category == "BUSINESS"

    def test_classify_management_change(self):
        """Test classification of management changes."""
        client = NewswireClient()
        event_type, category = client._classify_release(
            "New CEO Appointed",
            "Board of directors names new executive leadership."
        )
        assert event_type == "MANAGEMENT"
        assert category == "CORPORATE"

    def test_classify_product_launch(self):
        """Test classification of product launches."""
        client = NewswireClient()
        event_type, category = client._classify_release(
            "Company Launches New Product",
            "Introduces revolutionary new technology."
        )
        assert event_type == "PRODUCT_LAUNCH"
        assert category == "BUSINESS"

    def test_classify_default(self):
        """Test default classification for generic releases."""
        client = NewswireClient()
        event_type, category = client._classify_release(
            "Company Update",
            "General information about company activities."
        )
        assert event_type == "PRESS_RELEASE"
        assert category == "NEWS"


class TestNewswireClientParseEntry:
    """Tests for RSS entry parsing."""

    def test_parse_entry_basic(self):
        """Test basic entry parsing."""
        client = NewswireClient()
        entry = SimpleNamespace(
            title="Company (NYSE: TEST) Announces News",
            link="https://example.com/news",
            summary="Company announces important news.",
            published_parsed=(2024, 1, 15, 10, 30, 0, 0, 0, 0),
        )
        entry.content = None

        result = client._parse_entry(entry, "test_wire", "Test Wire")

        assert result is not None
        assert result["headline"] == "Company (NYSE: TEST) Announces News"
        assert result["url"] == "https://example.com/news"
        assert "TEST" in result["extracted_tickers"]
        assert result["source"] == "Test Wire"
        assert result["source_id"] == "test_wire"

    def test_parse_entry_empty_title(self):
        """Test parsing entry with empty title returns None."""
        client = NewswireClient()
        entry = SimpleNamespace(
            title="",
            link="https://example.com/news",
        )

        result = client._parse_entry(entry, "test_wire", "Test Wire")
        assert result is None

    def test_parse_entry_no_title(self):
        """Test parsing entry without title returns None."""
        client = NewswireClient()
        entry = SimpleNamespace(
            link="https://example.com/news",
        )
        entry.title = None

        result = client._parse_entry(entry, "test_wire", "Test Wire")
        assert result is None

    def test_parse_entry_with_content(self):
        """Test parsing entry with content field."""
        client = NewswireClient()
        entry = SimpleNamespace(
            title="Test News",
            link="https://example.com/news",
            content=[{"value": "<p>Full content here</p>"}],
            published_parsed=None,
        )

        result = client._parse_entry(entry, "test_wire", "Test Wire")

        assert result is not None
        assert "Full content here" in result["content"]

    def test_parse_entry_with_description(self):
        """Test parsing entry with description field."""
        client = NewswireClient()
        entry = SimpleNamespace(
            title="Test News",
            link="https://example.com/news",
            description="<p>Description content</p>",
            published_parsed=None,
        )

        result = client._parse_entry(entry, "test_wire", "Test Wire")

        assert result is not None
        assert "Description content" in result["content"]

    def test_parse_entry_strips_html(self):
        """Test HTML is stripped from content."""
        client = NewswireClient()
        entry = SimpleNamespace(
            title="Test News",
            link="https://example.com/news",
            summary="<strong>Bold</strong> and <em>italic</em> text",
            published_parsed=None,
        )
        entry.content = None

        result = client._parse_entry(entry, "test_wire", "Test Wire")

        assert result is not None
        assert "<strong>" not in result["content"]
        assert "<em>" not in result["content"]
        assert "Bold" in result["content"]

    def test_parse_entry_includes_metadata(self):
        """Test metadata is included in parsed entry."""
        client = NewswireClient()
        entry = SimpleNamespace(
            title="Test News",
            link="https://example.com/news",
            summary="News summary",
            published_parsed=None,
            id="entry-12345",
        )
        entry.content = None

        result = client._parse_entry(entry, "test_wire", "Test Wire")

        assert result is not None
        assert result["metadata"]["wire_service"] == "test_wire"
        assert result["metadata"]["entry_id"] == "entry-12345"


class TestNewswireClientScrape:
    """Tests for scraping functionality."""

    @pytest.mark.asyncio
    async def test_scrape_aggregates_all_feeds(self):
        """Test scrape aggregates releases from all configured feeds."""
        custom_feeds = {
            "wire1": {"name": "Wire 1", "rss": "http://wire1.com/rss"},
            "wire2": {"name": "Wire 2", "rss": "http://wire2.com/rss"},
        }
        client = NewswireClient(feeds=custom_feeds, rate_limit=0.01)

        # Mock the fetch method
        mock_response = MagicMock()
        mock_response.text = """<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Test Release (NYSE: TEST)</title>
                    <link>http://example.com/1</link>
                    <description>Test description</description>
                </item>
            </channel>
        </rss>"""

        with patch.object(client, "fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response

            async with client:
                releases = await client.scrape()

        # Should have fetched both feeds
        assert mock_fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_scrape_handles_feed_errors(self):
        """Test scrape handles errors from individual feeds."""
        custom_feeds = {
            "wire1": {"name": "Wire 1", "rss": "http://wire1.com/rss"},
        }
        client = NewswireClient(feeds=custom_feeds, rate_limit=0.01)

        with patch.object(client, "fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = httpx.HTTPError("Connection failed")

            async with client:
                releases = await client.scrape()

        # Should return empty list on error, not raise
        assert releases == []


class TestNewswireClientSearchByTicker:
    """Tests for ticker search functionality."""

    @pytest.mark.asyncio
    async def test_search_by_ticker_filters_results(self):
        """Test search filters results by ticker."""
        client = NewswireClient(rate_limit=0.01)

        # Mock scrape to return test data
        mock_releases = [
            {"headline": "News 1", "extracted_tickers": ["AAPL", "MSFT"]},
            {"headline": "News 2", "extracted_tickers": ["GOOG"]},
            {"headline": "News 3", "extracted_tickers": ["AAPL"]},
        ]

        with patch.object(client, "scrape", new_callable=AsyncMock) as mock_scrape:
            mock_scrape.return_value = mock_releases

            async with client:
                results = await client.search_by_ticker("AAPL")

        assert len(results) == 2
        assert all("AAPL" in r["extracted_tickers"] for r in results)

    @pytest.mark.asyncio
    async def test_search_by_ticker_case_insensitive(self):
        """Test search is case insensitive."""
        client = NewswireClient(rate_limit=0.01)

        mock_releases = [
            {"headline": "News", "extracted_tickers": ["AAPL"]},
        ]

        with patch.object(client, "scrape", new_callable=AsyncMock) as mock_scrape:
            mock_scrape.return_value = mock_releases

            async with client:
                results = await client.search_by_ticker("aapl")

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_by_ticker_respects_limit(self):
        """Test search respects limit parameter."""
        client = NewswireClient(rate_limit=0.01)

        mock_releases = [
            {"headline": f"News {i}", "extracted_tickers": ["AAPL"]}
            for i in range(30)
        ]

        with patch.object(client, "scrape", new_callable=AsyncMock) as mock_scrape:
            mock_scrape.return_value = mock_releases

            async with client:
                results = await client.search_by_ticker("AAPL", limit=5)

        assert len(results) == 5
