"""Tests for RSSAggregator and TickerRSSAggregator."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

import httpx
import pytest

from backend.ingestion.scrapers.rss_aggregator import (
    RSSAggregator,
    TickerRSSAggregator,
    DEFAULT_FEEDS,
)


class TestRSSAggregatorInit:
    """Tests for RSSAggregator initialization."""

    def test_default_feeds(self):
        """Test default feeds are loaded."""
        aggregator = RSSAggregator()
        assert aggregator.feeds == DEFAULT_FEEDS

    def test_custom_feeds(self):
        """Test custom feeds can be provided."""
        custom_feeds = {"custom": "http://custom.com/rss"}
        aggregator = RSSAggregator(feeds=custom_feeds)
        assert aggregator.feeds == custom_feeds

    def test_default_rate_limit(self):
        """Test default rate limit is 5 seconds."""
        aggregator = RSSAggregator()
        assert aggregator.rate_limit == 5.0


class TestRSSAggregatorParseEntry:
    """Tests for RSS entry parsing."""

    def test_parse_entry_basic(self):
        """Test basic entry parsing."""
        aggregator = RSSAggregator()
        entry = SimpleNamespace(
            title="Test Article",
            link="https://example.com/article",
            summary="Article summary text",
            author="Test Author",
            published_parsed=(2024, 1, 15, 10, 30, 0, 0, 0, 0),
            tags=[],
        )

        result = aggregator._parse_entry(entry, "test_feed")

        assert result is not None
        assert result["headline"] == "Test Article"
        assert result["url"] == "https://example.com/article"
        assert result["summary"] == "Article summary text"
        assert result["author"] == "Test Author"
        assert result["source"] == "test_feed"
        assert result["event_type"] == "NEWS"
        assert result["event_category"] == "RSS_NEWS"

    def test_parse_entry_empty_title(self):
        """Test parsing entry with empty title returns None."""
        aggregator = RSSAggregator()
        entry = SimpleNamespace(
            title="",
            link="https://example.com/article",
        )

        result = aggregator._parse_entry(entry, "test_feed")
        assert result is None

    def test_parse_entry_with_description(self):
        """Test parsing entry with description instead of summary."""
        aggregator = RSSAggregator()
        entry = SimpleNamespace(
            title="Test Article",
            link="https://example.com/article",
            description="Description text",
            published_parsed=None,
        )

        result = aggregator._parse_entry(entry, "test_feed")

        assert result is not None
        assert result["summary"] == "Description text"

    def test_parse_entry_with_updated_date(self):
        """Test parsing entry with updated date instead of published."""
        aggregator = RSSAggregator()
        entry = SimpleNamespace(
            title="Test Article",
            link="https://example.com/article",
            summary="Summary",
            published_parsed=None,
            updated_parsed=(2024, 2, 20, 14, 0, 0, 0, 0, 0),
        )

        result = aggregator._parse_entry(entry, "test_feed")

        assert result is not None
        assert "2024-02-20" in result["published_at"]

    def test_parse_entry_with_tags(self):
        """Test parsing entry with tags."""
        aggregator = RSSAggregator()
        entry = SimpleNamespace(
            title="Test Article",
            link="https://example.com/article",
            summary="Summary",
            published_parsed=None,
            tags=[
                {"term": "finance"},
                {"term": "stocks"},
                {"term": ""},
            ],
        )

        result = aggregator._parse_entry(entry, "test_feed")

        assert result is not None
        assert "finance" in result["tags"]
        assert "stocks" in result["tags"]
        assert "" not in result["tags"]

    def test_parse_entry_strips_html_from_summary(self):
        """Test HTML is stripped from summary."""
        aggregator = RSSAggregator()
        entry = SimpleNamespace(
            title="Test Article",
            link="https://example.com/article",
            summary="<p>Paragraph</p><strong>Bold</strong>",
            published_parsed=None,
        )

        result = aggregator._parse_entry(entry, "test_feed")

        assert result is not None
        assert "<p>" not in result["summary"]
        assert "<strong>" not in result["summary"]
        assert "Paragraph" in result["summary"]
        assert "Bold" in result["summary"]

    def test_parse_entry_truncates_long_summary(self):
        """Test summary is truncated to 1000 characters."""
        aggregator = RSSAggregator()
        long_summary = "A" * 2000
        entry = SimpleNamespace(
            title="Test Article",
            link="https://example.com/article",
            summary=long_summary,
            published_parsed=None,
        )

        result = aggregator._parse_entry(entry, "test_feed")

        assert result is not None
        assert len(result["summary"]) == 1000


class TestRSSAggregatorFeedManagement:
    """Tests for feed management methods."""

    def test_add_feed(self):
        """Test adding a new feed."""
        aggregator = RSSAggregator(feeds={})
        aggregator.add_feed("new_feed", "http://new.com/rss")
        assert "new_feed" in aggregator.feeds
        assert aggregator.feeds["new_feed"] == "http://new.com/rss"

    def test_remove_feed(self):
        """Test removing a feed."""
        aggregator = RSSAggregator(feeds={"test": "http://test.com"})
        aggregator.remove_feed("test")
        assert "test" not in aggregator.feeds

    def test_remove_nonexistent_feed(self):
        """Test removing non-existent feed doesn't raise."""
        aggregator = RSSAggregator(feeds={})
        aggregator.remove_feed("nonexistent")  # Should not raise


class TestRSSAggregatorFetchSpecificFeed:
    """Tests for fetching specific feeds."""

    @pytest.mark.asyncio
    async def test_fetch_specific_feed_unknown(self):
        """Test fetching unknown feed raises error."""
        aggregator = RSSAggregator(feeds={})

        with pytest.raises(ValueError, match="Unknown feed"):
            async with aggregator:
                await aggregator.fetch_specific_feed("unknown")


class TestRSSAggregatorScrape:
    """Tests for scraping functionality."""

    @pytest.mark.asyncio
    async def test_scrape_aggregates_feeds(self):
        """Test scrape aggregates items from all feeds."""
        custom_feeds = {
            "feed1": "http://feed1.com/rss",
            "feed2": "http://feed2.com/rss",
        }
        aggregator = RSSAggregator(feeds=custom_feeds, rate_limit=0.01)

        mock_response = MagicMock()
        mock_response.text = """<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Test Article</title>
                    <link>http://example.com/1</link>
                    <description>Test description</description>
                </item>
            </channel>
        </rss>"""

        with patch.object(aggregator, "fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response

            async with aggregator:
                items = await aggregator.scrape()

        # Should have fetched both feeds
        assert mock_fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_scrape_handles_errors(self):
        """Test scrape handles individual feed errors gracefully."""
        custom_feeds = {"feed1": "http://feed1.com/rss"}
        aggregator = RSSAggregator(feeds=custom_feeds, rate_limit=0.01)

        with patch.object(aggregator, "fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = httpx.HTTPError("Connection failed")

            async with aggregator:
                items = await aggregator.scrape()

        # Should return empty list, not raise
        assert items == []

    @pytest.mark.asyncio
    async def test_scrape_deduplicates_items(self):
        """Test scrape removes duplicate items."""
        custom_feeds = {"feed1": "http://feed1.com/rss"}
        aggregator = RSSAggregator(feeds=custom_feeds, rate_limit=0.01)

        mock_response = MagicMock()
        mock_response.text = """<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Duplicate Article</title>
                    <link>http://example.com/1</link>
                </item>
                <item>
                    <title>Duplicate Article</title>
                    <link>http://example.com/2</link>
                </item>
            </channel>
        </rss>"""

        with patch.object(aggregator, "fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response

            async with aggregator:
                items = await aggregator.scrape()

        # Only one item should be returned due to deduplication
        assert len(items) == 1


class TestTickerRSSAggregatorInit:
    """Tests for TickerRSSAggregator initialization."""

    def test_default_ticker_list(self):
        """Test default ticker list is empty."""
        aggregator = TickerRSSAggregator()
        assert aggregator.ticker_list == set()

    def test_custom_ticker_list(self):
        """Test custom ticker list can be provided."""
        tickers = {"AAPL", "MSFT", "GOOG"}
        aggregator = TickerRSSAggregator(ticker_list=tickers)
        assert aggregator.ticker_list == tickers


class TestTickerRSSAggregatorTickerExtraction:
    """Tests for ticker extraction functionality."""

    def test_extract_uppercase_ticker(self):
        """Test extraction of uppercase tickers."""
        aggregator = TickerRSSAggregator()
        tickers = aggregator._extract_tickers("AAPL is up today")
        assert "AAPL" in tickers

    def test_excludes_common_words(self):
        """Test common words are excluded."""
        aggregator = TickerRSSAggregator()
        tickers = aggregator._extract_tickers("CEO and CFO met with SEC about IPO")
        assert "CEO" not in tickers
        assert "CFO" not in tickers
        assert "SEC" not in tickers
        assert "IPO" not in tickers

    def test_excludes_single_letter(self):
        """Test single letter words are excluded."""
        aggregator = TickerRSSAggregator()
        tickers = aggregator._extract_tickers("A great I idea")
        assert "A" not in tickers
        assert "I" not in tickers

    def test_validates_against_ticker_list(self):
        """Test validation against provided ticker list."""
        ticker_list = {"AAPL", "MSFT"}
        aggregator = TickerRSSAggregator(ticker_list=ticker_list)
        tickers = aggregator._extract_tickers("AAPL GOOG MSFT mentioned")
        assert "AAPL" in tickers
        assert "MSFT" in tickers
        assert "GOOG" not in tickers

    def test_no_ticker_list_accepts_valid_format(self):
        """Test without ticker list, valid format tickers are accepted."""
        aggregator = TickerRSSAggregator()
        tickers = aggregator._extract_tickers("AAPL and GOOG mentioned")
        assert "AAPL" in tickers
        assert "GOOG" in tickers

    def test_removes_duplicates(self):
        """Test duplicate tickers are removed."""
        aggregator = TickerRSSAggregator()
        tickers = aggregator._extract_tickers("AAPL AAPL AAPL mentioned three times")
        assert tickers.count("AAPL") == 1


class TestTickerRSSAggregatorParseEntry:
    """Tests for ticker-aware entry parsing."""

    def test_parse_entry_extracts_tickers(self):
        """Test entry parsing extracts tickers."""
        aggregator = TickerRSSAggregator()
        entry = SimpleNamespace(
            title="AAPL Reports Strong Earnings",
            link="https://example.com/article",
            summary="Apple Inc AAPL beats estimates",
            published_parsed=None,
        )

        result = aggregator._parse_entry(entry, "test_feed")

        assert result is not None
        assert "extracted_tickers" in result
        assert "AAPL" in result["extracted_tickers"]

    def test_parse_entry_sets_primary_ticker(self):
        """Test first extracted ticker is set as primary."""
        aggregator = TickerRSSAggregator()
        entry = SimpleNamespace(
            title="AAPL and MSFT news",
            link="https://example.com/article",
            summary="Technology stocks update",
            published_parsed=None,
        )

        result = aggregator._parse_entry(entry, "test_feed")

        assert result is not None
        assert result["ticker"] == result["extracted_tickers"][0]

    def test_parse_entry_no_tickers(self):
        """Test entry without tickers doesn't set ticker field."""
        aggregator = TickerRSSAggregator()
        entry = SimpleNamespace(
            title="General Market News",
            link="https://example.com/article",
            summary="Markets are volatile today",
            published_parsed=None,
        )

        result = aggregator._parse_entry(entry, "test_feed")

        assert result is not None
        assert result["extracted_tickers"] == []
        assert "ticker" not in result or result.get("ticker") is None


class TestRSSAggregatorStream:
    """Tests for streaming functionality."""

    @pytest.mark.asyncio
    async def test_stream_yields_normalized_events(self):
        """Test stream yields normalized events."""
        custom_feeds = {"feed1": "http://feed1.com/rss"}
        aggregator = RSSAggregator(feeds=custom_feeds, rate_limit=0.01)

        mock_response = MagicMock()
        mock_response.text = """<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Test Article</title>
                    <link>http://example.com/1</link>
                    <description>Test description</description>
                </item>
            </channel>
        </rss>"""

        with patch.object(aggregator, "fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response

            async with aggregator:
                # Get just one event from stream then break
                event_count = 0
                async for event in aggregator.stream(poll_interval=0.01):
                    event_count += 1
                    # Check normalized event structure
                    assert "ticker" in event
                    assert "event_type" in event
                    assert "headline" in event
                    assert "source_name" in event
                    assert "event_time" in event
                    assert "ingested_at" in event
                    break

                assert event_count >= 1
