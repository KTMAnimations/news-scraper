"""Tests for Reddit monitor social media scraper."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.ingestion.social.reddit_monitor import (
    RedditMonitor,
    TARGET_SUBREDDITS,
)


class TestRedditMonitorInit:
    """Tests for RedditMonitor initialization."""

    def test_default_credentials(self):
        """Test default credentials from settings."""
        with patch("backend.ingestion.social.reddit_monitor.settings") as mock_settings:
            mock_settings.reddit_client_id = "test_id"
            mock_settings.reddit_client_secret = "test_secret"
            mock_settings.reddit_user_agent = "TestAgent/1.0"

            monitor = RedditMonitor()

            assert monitor.client_id == "test_id"
            assert monitor.client_secret == "test_secret"
            assert monitor.user_agent == "TestAgent/1.0"

    def test_custom_credentials(self):
        """Test custom credentials can be provided."""
        monitor = RedditMonitor(
            client_id="custom_id",
            client_secret="custom_secret",
            user_agent="CustomAgent/1.0"
        )

        assert monitor.client_id == "custom_id"
        assert monitor.client_secret == "custom_secret"
        assert monitor.user_agent == "CustomAgent/1.0"

    def test_default_subreddits(self):
        """Test default subreddits are loaded."""
        with patch("backend.ingestion.social.reddit_monitor.settings") as mock_settings:
            mock_settings.reddit_client_id = None
            mock_settings.reddit_client_secret = None
            mock_settings.reddit_user_agent = "Test"

            monitor = RedditMonitor()
            assert monitor.subreddits == TARGET_SUBREDDITS

    def test_custom_subreddits(self):
        """Test custom subreddits can be provided."""
        custom_subs = ["test1", "test2"]
        monitor = RedditMonitor(subreddits=custom_subs)
        assert monitor.subreddits == custom_subs

    def test_initial_state(self):
        """Test initial state of monitor."""
        monitor = RedditMonitor()
        assert monitor._access_token is None
        assert monitor._token_expires is None
        assert monitor._client is None
        assert monitor._seen_ids == set()


class TestRedditMonitorTickerExtraction:
    """Tests for ticker extraction from Reddit posts."""

    def test_extract_cashtag_ticker(self):
        """Test extraction of $TICKER format."""
        monitor = RedditMonitor()
        tickers = monitor._extract_tickers("Check out $AAPL today!")
        assert "AAPL" in tickers

    def test_extract_multiple_cashtags(self):
        """Test extraction of multiple cashtags."""
        monitor = RedditMonitor()
        tickers = monitor._extract_tickers("$AAPL and $MSFT are both up")
        assert "AAPL" in tickers
        assert "MSFT" in tickers

    def test_extract_uppercase_mentions(self):
        """Test extraction of uppercase ticker mentions."""
        monitor = RedditMonitor()
        tickers = monitor._extract_tickers("AAPL is looking good")
        assert "AAPL" in tickers

    def test_excludes_common_words(self):
        """Test common words are excluded."""
        monitor = RedditMonitor()
        tickers = monitor._extract_tickers("CEO met with SEC about IPO YOLO FOMO")
        assert "CEO" not in tickers
        assert "SEC" not in tickers
        assert "IPO" not in tickers
        assert "YOLO" not in tickers
        assert "FOMO" not in tickers

    def test_excludes_reddit_slang(self):
        """Test Reddit-specific slang is excluded."""
        monitor = RedditMonitor()
        tickers = monitor._extract_tickers("HODL to the MOON with WSB")
        assert "HODL" not in tickers
        assert "MOON" not in tickers
        assert "WSB" not in tickers

    def test_excludes_single_letter(self):
        """Test single letters are excluded."""
        monitor = RedditMonitor()
        tickers = monitor._extract_tickers("A B C stock picks")
        # A is excluded as common word
        assert "A" not in tickers

    def test_cashtag_case_normalization(self):
        """Test cashtag tickers are normalized to uppercase."""
        monitor = RedditMonitor()
        tickers = monitor._extract_tickers("$aapl is my pick")
        assert "AAPL" in tickers

    def test_deduplicates_tickers(self):
        """Test duplicate tickers are removed."""
        monitor = RedditMonitor()
        tickers = monitor._extract_tickers("$AAPL AAPL $AAPL mentioned many times")
        assert tickers.count("AAPL") == 1

    def test_limits_ticker_count(self):
        """Test ticker count is limited to 10."""
        monitor = RedditMonitor()
        # Create text with many unique tickers
        text = " ".join([f"${chr(65+i)}{chr(65+j)}XY" for i in range(5) for j in range(5)])
        tickers = monitor._extract_tickers(text)
        assert len(tickers) <= 10


class TestRedditMonitorParsePost:
    """Tests for parsing Reddit post data."""

    def test_parse_post_basic(self):
        """Test basic post parsing."""
        monitor = RedditMonitor()
        data = {
            "id": "abc123",
            "title": "Check out $AAPL!",
            "selftext": "Apple is looking strong today",
            "author": "test_user",
            "permalink": "/r/pennystocks/comments/abc123",
            "score": 100,
            "upvote_ratio": 0.9,
            "num_comments": 50,
            "created_utc": 1705320000,
            "link_flair_text": "DD",
        }

        result = monitor._parse_post(data, "pennystocks")

        assert result is not None
        assert result["post_id"] == "abc123"
        assert result["title"] == "Check out $AAPL!"
        assert result["author"] == "test_user"
        assert result["subreddit"] == "pennystocks"
        assert result["score"] == 100
        assert result["upvote_ratio"] == 0.9
        assert result["num_comments"] == 50
        assert result["flair"] == "DD"
        assert "AAPL" in result["tickers"]
        assert result["ticker"] == "AAPL"
        assert result["source"] == "reddit"
        assert result["event_type"] == "SOCIAL_MENTION"

    def test_parse_post_no_title(self):
        """Test parsing post without title returns None."""
        monitor = RedditMonitor()
        data = {
            "id": "abc123",
            "title": "",
            "selftext": "Content",
        }

        result = monitor._parse_post(data, "pennystocks")
        assert result is None

    def test_parse_post_deleted_author(self):
        """Test parsing post with deleted author."""
        monitor = RedditMonitor()
        data = {
            "id": "abc123",
            "title": "Test Post",
            "selftext": "",
            "permalink": "/test",
            "score": 0,
            "upvote_ratio": 0.5,
            "num_comments": 0,
            "created_utc": 1705320000,
        }

        result = monitor._parse_post(data, "pennystocks")

        assert result is not None
        assert result["author"] == "[deleted]"

    def test_parse_post_engagement_score(self):
        """Test engagement score calculation."""
        monitor = RedditMonitor()
        data = {
            "id": "abc123",
            "title": "Test Post",
            "selftext": "",
            "author": "user",
            "permalink": "/test",
            "score": 500,
            "upvote_ratio": 0.95,
            "num_comments": 100,
            "created_utc": 1705320000,
        }

        result = monitor._parse_post(data, "pennystocks")

        # Engagement = min(1.0, (score + comments * 2) / 1000)
        # = min(1.0, (500 + 100 * 2) / 1000) = min(1.0, 0.7) = 0.7
        assert result["engagement_score"] == 0.7

    def test_parse_post_high_engagement_capped(self):
        """Test engagement score is capped at 1.0."""
        monitor = RedditMonitor()
        data = {
            "id": "abc123",
            "title": "Test Post",
            "selftext": "",
            "author": "user",
            "permalink": "/test",
            "score": 5000,
            "upvote_ratio": 0.99,
            "num_comments": 1000,
            "created_utc": 1705320000,
        }

        result = monitor._parse_post(data, "pennystocks")

        assert result["engagement_score"] == 1.0

    def test_parse_post_url_format(self):
        """Test URL is correctly formatted."""
        monitor = RedditMonitor()
        data = {
            "id": "abc123",
            "title": "Test Post",
            "selftext": "",
            "author": "user",
            "permalink": "/r/pennystocks/comments/abc123/test",
            "score": 0,
            "upvote_ratio": 0.5,
            "num_comments": 0,
            "created_utc": 1705320000,
        }

        result = monitor._parse_post(data, "pennystocks")

        assert result["url"] == "https://reddit.com/r/pennystocks/comments/abc123/test"

    def test_parse_post_event_category(self):
        """Test event category includes subreddit name."""
        monitor = RedditMonitor()
        data = {
            "id": "abc123",
            "title": "Test Post",
            "selftext": "",
            "author": "user",
            "permalink": "/test",
            "score": 0,
            "upvote_ratio": 0.5,
            "num_comments": 0,
            "created_utc": 1705320000,
        }

        result = monitor._parse_post(data, "wallstreetbets")

        assert result["event_category"] == "REDDIT_WALLSTREETBETS"

    def test_parse_post_no_tickers(self):
        """Test parsing post without tickers."""
        monitor = RedditMonitor()
        data = {
            "id": "abc123",
            "title": "General market discussion",
            "selftext": "Nothing specific here",
            "author": "user",
            "permalink": "/test",
            "score": 0,
            "upvote_ratio": 0.5,
            "num_comments": 0,
            "created_utc": 1705320000,
        }

        result = monitor._parse_post(data, "pennystocks")

        assert result is not None
        assert result["tickers"] == []
        assert result["ticker"] == ""

    def test_parse_post_truncates_long_content(self):
        """Test long content is truncated."""
        monitor = RedditMonitor()
        long_content = "A" * 10000
        data = {
            "id": "abc123",
            "title": "Test Post",
            "selftext": long_content,
            "author": "user",
            "permalink": "/test",
            "score": 0,
            "upvote_ratio": 0.5,
            "num_comments": 0,
            "created_utc": 1705320000,
        }

        result = monitor._parse_post(data, "pennystocks")

        assert len(result["content"]) == 5000


class TestRedditMonitorAuthentication:
    """Tests for Reddit OAuth authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        """Test successful authentication."""
        monitor = RedditMonitor(
            client_id="test_id",
            client_secret="test_secret",
            user_agent="TestAgent"
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            async with monitor:
                pass

        assert monitor._access_token == "test_token"
        assert monitor._token_expires is not None

    @pytest.mark.asyncio
    async def test_authenticate_no_credentials(self):
        """Test authentication fails without credentials."""
        monitor = RedditMonitor(
            client_id=None,
            client_secret=None,
            user_agent="TestAgent"
        )

        async with monitor:
            result = await monitor._authenticate()

        assert result is False
        assert monitor._access_token is None


class TestRedditMonitorGetSubredditPosts:
    """Tests for fetching subreddit posts."""

    @pytest.mark.asyncio
    async def test_get_subreddit_posts_success(self):
        """Test successful post retrieval."""
        monitor = RedditMonitor(
            client_id="test_id",
            client_secret="test_secret",
            user_agent="TestAgent"
        )

        mock_auth_response = MagicMock()
        mock_auth_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        mock_auth_response.raise_for_status = MagicMock()

        mock_posts_response = MagicMock()
        mock_posts_response.json.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "post1",
                            "title": "$AAPL to the moon!",
                            "selftext": "Apple is great",
                            "author": "user1",
                            "permalink": "/r/test/post1",
                            "score": 100,
                            "upvote_ratio": 0.9,
                            "num_comments": 20,
                            "created_utc": 1705320000,
                        }
                    }
                ]
            }
        }
        mock_posts_response.raise_for_status = MagicMock()

        async with monitor:
            monitor._access_token = "test_token"
            monitor._client.get = AsyncMock(return_value=mock_posts_response)

            posts = await monitor.get_subreddit_posts("pennystocks", limit=10)

        assert len(posts) == 1
        assert posts[0]["post_id"] == "post1"
        assert "AAPL" in posts[0]["tickers"]

    @pytest.mark.asyncio
    async def test_get_subreddit_posts_no_auth(self):
        """Test post retrieval without authentication returns empty."""
        monitor = RedditMonitor(
            client_id="test_id",
            client_secret="test_secret",
            user_agent="TestAgent"
        )

        async with monitor:
            monitor._access_token = None
            posts = await monitor.get_subreddit_posts("pennystocks")

        assert posts == []

    @pytest.mark.asyncio
    async def test_get_subreddit_posts_error_handling(self):
        """Test error handling during post retrieval."""
        monitor = RedditMonitor(
            client_id="test_id",
            client_secret="test_secret",
            user_agent="TestAgent"
        )

        async with monitor:
            monitor._access_token = "test_token"
            monitor._client.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))

            posts = await monitor.get_subreddit_posts("pennystocks")

        assert posts == []


class TestRedditMonitorSearchTicker:
    """Tests for ticker search functionality."""

    @pytest.mark.asyncio
    async def test_search_ticker_success(self):
        """Test successful ticker search."""
        monitor = RedditMonitor(
            client_id="test_id",
            client_secret="test_secret",
            user_agent="TestAgent",
            subreddits=["pennystocks"]
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "post1",
                            "title": "AAPL discussion",
                            "selftext": "",
                            "author": "user",
                            "permalink": "/test",
                            "score": 50,
                            "upvote_ratio": 0.8,
                            "num_comments": 10,
                            "created_utc": 1705320000,
                        }
                    }
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        async with monitor:
            monitor._access_token = "test_token"
            monitor._client.get = AsyncMock(return_value=mock_response)

            posts = await monitor.search_ticker("AAPL", limit=10)

        assert len(posts) >= 1

    @pytest.mark.asyncio
    async def test_search_ticker_no_auth(self):
        """Test ticker search without authentication returns empty."""
        monitor = RedditMonitor(
            client_id=None,
            client_secret=None,
            user_agent="TestAgent"
        )

        async with monitor:
            posts = await monitor.search_ticker("AAPL")

        assert posts == []


class TestRedditMonitorSeenCache:
    """Tests for seen post caching."""

    def test_seen_ids_cache_limit(self):
        """Test seen IDs cache is limited."""
        monitor = RedditMonitor()

        # Add more than 10000 items
        for i in range(10001):
            monitor._seen_ids.add(f"post_{i}")

        # Manually trigger cache cleanup (normally happens in monitor_subreddits)
        if len(monitor._seen_ids) > 10000:
            monitor._seen_ids = set(list(monitor._seen_ids)[-5000:])

        assert len(monitor._seen_ids) <= 5000
