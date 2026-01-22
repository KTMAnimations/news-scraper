"""Tests for ingestion modules."""

import pytest
from datetime import datetime, timezone


class TestSECEdgarClient:
    """Test SEC EDGAR client."""

    def test_extract_filing_type(self):
        """Test filing type extraction from title."""
        from backend.ingestion.sec_edgar import SECStreamingClient

        client = SECStreamingClient()

        assert client._extract_filing_type("FORM 4 - APPLE INC") == "4"
        assert client._extract_filing_type("8-K filing for Company XYZ") == "8-K"
        assert client._extract_filing_type("10-Q quarterly report") == "10-Q"
        assert client._extract_filing_type("Random text") is None

    def test_extract_cik(self):
        """Test CIK extraction from URL."""
        from backend.ingestion.sec_edgar import SECStreamingClient

        client = SECStreamingClient()

        url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001234567"
        assert client._extract_cik(url) == "1234567"

        url_no_leading_zeros = "https://www.sec.gov/cgi-bin/browse-edgar?CIK=123456"
        assert client._extract_cik(url_no_leading_zeros) == "123456"

    def test_extract_company_name(self):
        """Test company name extraction from title."""
        from backend.ingestion.sec_edgar import SECStreamingClient

        client = SECStreamingClient()

        title = "FORM 4 - Apple Inc (0000320193)"
        assert "Apple Inc" in client._extract_company_name(title)


class TestRedditMonitor:
    """Test Reddit monitor."""

    def test_ticker_extraction_with_cashtag(self):
        """Test ticker extraction with cashtag."""
        from backend.ingestion.social import RedditMonitor

        monitor = RedditMonitor()
        tickers = monitor._extract_tickers("Check out $AAPL and $MSFT!")

        assert "AAPL" in tickers
        assert "MSFT" in tickers

    def test_ticker_extraction_excludes_common_words(self):
        """Test that common words are excluded."""
        from backend.ingestion.social import RedditMonitor

        monitor = RedditMonitor()
        tickers = monitor._extract_tickers("The CEO said US markets are up")

        assert "CEO" not in tickers
        assert "US" not in tickers
        assert "THE" not in tickers

    def test_parse_post(self):
        """Test Reddit post parsing."""
        from backend.ingestion.social import RedditMonitor

        monitor = RedditMonitor()

        post_data = {
            "id": "abc123",
            "title": "Check out $AAPL - great earnings!",
            "selftext": "Apple just crushed it",
            "author": "testuser",
            "score": 100,
            "upvote_ratio": 0.9,
            "num_comments": 50,
            "link_flair_text": "DD",
            "permalink": "/r/pennystocks/comments/abc123",
            "created_utc": datetime.now(timezone.utc).timestamp(),
        }

        parsed = monitor._parse_post(post_data, "pennystocks")

        assert parsed is not None
        assert parsed["post_id"] == "abc123"
        assert "AAPL" in parsed["tickers"]
        assert parsed["source"] == "reddit"


class TestTwitterStream:
    """Test Twitter stream client."""

    def test_cashtag_pattern(self):
        """Test cashtag pattern matching."""
        from backend.ingestion.social import TwitterStream

        stream = TwitterStream()
        text = "Check out $AAPL and $TSLA today!"

        matches = stream.CASHTAG_PATTERN.findall(text.upper())
        assert "AAPL" in matches
        assert "TSLA" in matches


class TestStockTwitsClient:
    """Test StockTwits client."""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initializes correctly."""
        from backend.ingestion.social import StockTwitsClient

        async with StockTwitsClient() as client:
            assert client._client is not None


class TestRateLimiter:
    """Test rate limiter."""

    @pytest.mark.asyncio
    async def test_allows_requests_under_limit(self):
        """Test that requests under limit are allowed."""
        from backend.ingestion.infrastructure import RateLimiter

        limiter = RateLimiter(requests_per_second=10)

        for _ in range(5):
            allowed = await limiter.acquire()
            assert allowed is True

    @pytest.mark.asyncio
    async def test_respects_rate_limit(self):
        """Test that rate limit is respected."""
        from backend.ingestion.infrastructure import RateLimiter
        import time

        limiter = RateLimiter(requests_per_second=1)

        start = time.time()
        await limiter.acquire()
        await limiter.acquire()
        elapsed = time.time() - start

        # Should take at least 1 second due to rate limiting
        assert elapsed >= 0.9


class TestUserAgentRotator:
    """Test user agent rotator."""

    def test_returns_valid_user_agent(self):
        """Test that rotator returns valid user agents."""
        from backend.ingestion.infrastructure import UserAgentRotator

        rotator = UserAgentRotator()
        ua = rotator.get_user_agent()

        assert ua is not None
        assert len(ua) > 0
        assert "Mozilla" in ua or "Chrome" in ua or "Safari" in ua

    def test_rotation_provides_variety(self):
        """Test that rotation provides variety."""
        from backend.ingestion.infrastructure import UserAgentRotator

        rotator = UserAgentRotator()
        user_agents = set()

        for _ in range(20):
            user_agents.add(rotator.get_user_agent())

        # Should have some variety
        assert len(user_agents) >= 2


class TestRequestClient:
    """Test request client."""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initializes correctly."""
        from backend.ingestion.infrastructure import RequestClient

        async with RequestClient() as client:
            assert client._client is not None
