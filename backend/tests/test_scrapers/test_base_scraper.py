"""Tests for BaseScraper class."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.ingestion.scrapers.base_scraper import BaseScraper


class ConcreteScraper(BaseScraper):
    """Concrete implementation of BaseScraper for testing."""

    async def scrape(self):
        return []

    async def stream(self, poll_interval: float = 60.0):
        yield {}


class TestBaseScraperInit:
    """Tests for BaseScraper initialization."""

    def test_default_rate_limit(self):
        """Test default rate limit is set correctly."""
        scraper = ConcreteScraper()
        assert scraper.rate_limit == BaseScraper.DEFAULT_RATE_LIMIT

    def test_custom_rate_limit(self):
        """Test custom rate limit is respected."""
        scraper = ConcreteScraper(rate_limit=5.0)
        assert scraper.rate_limit == 5.0

    def test_use_proxy_default_false(self):
        """Test proxy is disabled by default."""
        with patch("backend.ingestion.scrapers.base_scraper.settings") as mock_settings:
            mock_settings.proxy_enabled = True
            scraper = ConcreteScraper(use_proxy=False)
            assert scraper.use_proxy is False

    def test_initial_state(self):
        """Test initial state of scraper."""
        scraper = ConcreteScraper()
        assert scraper._client is None
        assert scraper._last_request == 0
        assert scraper._seen_hashes == set()


class TestBaseScraperContextManager:
    """Tests for async context manager functionality."""

    @pytest.mark.asyncio
    async def test_context_manager_creates_client(self):
        """Test context manager creates HTTP client."""
        with patch("backend.ingestion.scrapers.base_scraper.settings") as mock_settings:
            mock_settings.proxy_enabled = False
            mock_settings.proxy_url = None

            async with ConcreteScraper() as scraper:
                assert scraper._client is not None
                assert isinstance(scraper._client, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self):
        """Test context manager closes HTTP client on exit."""
        with patch("backend.ingestion.scrapers.base_scraper.settings") as mock_settings:
            mock_settings.proxy_enabled = False
            mock_settings.proxy_url = None

            scraper = ConcreteScraper()
            async with scraper:
                client = scraper._client
                assert client is not None

            # After exit, client should be closed
            assert client.is_closed


class TestBaseScraperHeaders:
    """Tests for header generation."""

    def test_get_headers_returns_dict(self):
        """Test headers returns a dictionary."""
        scraper = ConcreteScraper()
        headers = scraper._get_headers()
        assert isinstance(headers, dict)

    def test_headers_include_user_agent(self):
        """Test headers include User-Agent."""
        scraper = ConcreteScraper()
        headers = scraper._get_headers()
        assert "User-Agent" in headers
        assert headers["User-Agent"] in BaseScraper.USER_AGENTS

    def test_headers_include_accept(self):
        """Test headers include Accept header."""
        scraper = ConcreteScraper()
        headers = scraper._get_headers()
        assert "Accept" in headers

    def test_headers_include_language(self):
        """Test headers include Accept-Language."""
        scraper = ConcreteScraper()
        headers = scraper._get_headers()
        assert "Accept-Language" in headers


class TestBaseScraperDeduplication:
    """Tests for deduplication functionality."""

    def test_generate_hash_consistency(self):
        """Test hash generation is consistent."""
        scraper = ConcreteScraper()
        content = "Test content"
        hash1 = scraper._generate_hash(content)
        hash2 = scraper._generate_hash(content)
        assert hash1 == hash2

    def test_generate_hash_different_content(self):
        """Test different content produces different hashes."""
        scraper = ConcreteScraper()
        hash1 = scraper._generate_hash("Content 1")
        hash2 = scraper._generate_hash("Content 2")
        assert hash1 != hash2

    def test_is_duplicate_first_time(self):
        """Test first occurrence is not a duplicate."""
        scraper = ConcreteScraper()
        result = scraper._is_duplicate("New content")
        assert result is False

    def test_is_duplicate_second_time(self):
        """Test second occurrence is a duplicate."""
        scraper = ConcreteScraper()
        content = "Duplicate content"
        scraper._is_duplicate(content)  # First time
        result = scraper._is_duplicate(content)  # Second time
        assert result is True

    def test_is_duplicate_different_content(self):
        """Test different content is not duplicate."""
        scraper = ConcreteScraper()
        scraper._is_duplicate("Content 1")
        result = scraper._is_duplicate("Content 2")
        assert result is False

    def test_seen_hashes_cache_limit(self):
        """Test seen hashes cache is limited."""
        scraper = ConcreteScraper()

        # Add more than 10000 items
        for i in range(10001):
            scraper._is_duplicate(f"Content {i}")

        # Cache should be reduced
        assert len(scraper._seen_hashes) <= 10000


class TestBaseScraperFetch:
    """Tests for fetch method."""

    @pytest.mark.asyncio
    async def test_fetch_requires_client(self):
        """Test fetch raises error without initialized client."""
        scraper = ConcreteScraper()
        with pytest.raises(RuntimeError, match="Client not initialized"):
            await scraper.fetch("http://example.com")

    @pytest.mark.asyncio
    async def test_fetch_success(self):
        """Test successful fetch returns response."""
        with patch("backend.ingestion.scrapers.base_scraper.settings") as mock_settings:
            mock_settings.proxy_enabled = False
            mock_settings.proxy_url = None

            scraper = ConcreteScraper(rate_limit=0.01)
            async with scraper:
                # Mock the client's get method
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.raise_for_status = MagicMock()
                scraper._client.get = AsyncMock(return_value=mock_response)

                response = await scraper.fetch("http://example.com")

                assert response == mock_response
                scraper._client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_applies_rate_limit(self):
        """Test fetch applies rate limiting."""
        with patch("backend.ingestion.scrapers.base_scraper.settings") as mock_settings:
            mock_settings.proxy_enabled = False
            mock_settings.proxy_url = None

            scraper = ConcreteScraper(rate_limit=0.1)
            async with scraper:
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()
                scraper._client.get = AsyncMock(return_value=mock_response)

                # Make first request
                start_time = asyncio.get_event_loop().time()
                await scraper.fetch("http://example.com/1")

                # Make second request - should be delayed
                await scraper.fetch("http://example.com/2")
                elapsed = asyncio.get_event_loop().time() - start_time

                # Should have waited at least the rate limit time
                assert elapsed >= 0.1


class TestBaseScraperNormalizeEvent:
    """Tests for event normalization."""

    def test_normalize_basic_event(self):
        """Test basic event normalization."""
        scraper = ConcreteScraper()
        raw_data = {
            "ticker": "AAPL",
            "event_type": "EARNINGS",
            "headline": "Apple Reports Q4 Earnings",
            "url": "https://example.com/news/1",
        }

        result = scraper.normalize_event(raw_data)

        assert result["ticker"] == "AAPL"
        assert result["event_type"] == "EARNINGS"
        assert result["headline"] == "Apple Reports Q4 Earnings"
        assert result["source_url"] == "https://example.com/news/1"
        assert "event_time" in result
        assert "ingested_at" in result

    def test_normalize_event_with_title_fallback(self):
        """Test normalization uses title as fallback for headline."""
        scraper = ConcreteScraper()
        raw_data = {
            "title": "News Title",
        }

        result = scraper.normalize_event(raw_data)
        assert result["headline"] == "News Title"

    def test_normalize_event_with_description_fallback(self):
        """Test normalization uses description as fallback for summary."""
        scraper = ConcreteScraper()
        raw_data = {
            "description": "News Description",
        }

        result = scraper.normalize_event(raw_data)
        assert result["summary"] == "News Description"

    def test_normalize_event_with_link_fallback(self):
        """Test normalization uses link as fallback for source_url."""
        scraper = ConcreteScraper()
        raw_data = {
            "link": "https://example.com/news",
        }

        result = scraper.normalize_event(raw_data)
        assert result["source_url"] == "https://example.com/news"

    def test_normalize_event_default_values(self):
        """Test normalization provides default values."""
        scraper = ConcreteScraper()
        raw_data = {}

        result = scraper.normalize_event(raw_data)

        assert result["ticker"] == ""
        assert result["event_type"] == "NEWS"
        assert result["event_category"] == "NEWS"
        assert result["headline"] == ""
        assert result["summary"] == ""
        assert result["content"] == ""
        assert result["source_url"] == ""
        assert result["source_name"] == "ConcreteScraper"
        assert result["metadata"] == {}

    def test_normalize_event_preserves_metadata(self):
        """Test normalization preserves metadata."""
        scraper = ConcreteScraper()
        raw_data = {
            "metadata": {"custom_field": "value"},
        }

        result = scraper.normalize_event(raw_data)
        assert result["metadata"] == {"custom_field": "value"}
