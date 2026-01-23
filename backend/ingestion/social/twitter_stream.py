"""Twitter/X API client for streaming cashtag mentions.

This module provides a comprehensive Twitter/X API client for:
- Searching recent tweets for stock ticker mentions ($AAPL, etc.)
- Tracking financial influencers
- Handling Twitter API v2 rate limits
- Streaming filtered cashtag mentions
"""

import asyncio
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Callable

import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)


# Financial influencers to track (Twitter usernames)
FINANCIAL_INFLUENCERS = [
    "jimcramer",           # Jim Cramer - CNBC
    "elikieba",            # Eli Lilly - Bloomberg
    "unusual_whales",      # Unusual Whales - Options flow
    "DeItaone",            # Walter Bloomberg - Breaking news
    "zaborsky",            # Zack Vorhies - Finance
    "realwillmeade",       # Will Meade - Finance
    "SquawkCNBC",          # Squawk Box CNBC
    "staborsky",           # Sam Taborsky - Finance
    "saxena_puru",         # Puru Saxena - Finance
    "charlottes_pod",      # Charlotte - Options
    "chaikieffect",        # Steve Chaik - Technical
    "traderferg",          # Trader Ferg - Technical
    "spotgamma",           # SpotGamma - Options flow
    "dikieffect",          # Finance analyst
    "hedgeye",             # Hedgeye - Research
    "stocksdaytrade",      # Day trading alerts
    "mtrade",              # Market trade alerts
    "biaboratory",         # BIA Market Laboratory
    "mmturan",             # Momentum trader
    "financialjuice",      # Financial Juice - News
]

# Penny stock focused accounts
PENNY_STOCK_INFLUENCERS = [
    "saborsky",            # Penny stocks focus
    "pennystocking",       # Penny stock alerts
    "otcmarkets",          # Official OTC Markets
    "timothy_sykes",       # Timothy Sykes - Penny stocks
]


class RateLimiter:
    """Token bucket rate limiter for Twitter API."""

    def __init__(
        self,
        requests_per_window: int = 450,
        window_seconds: int = 900,  # 15 minutes
    ):
        """Initialize rate limiter.

        Args:
            requests_per_window: Maximum requests per window
            window_seconds: Window duration in seconds
        """
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.tokens = requests_per_window
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update

            # Replenish tokens based on elapsed time
            tokens_to_add = elapsed * (self.requests_per_window / self.window_seconds)
            self.tokens = min(self.requests_per_window, self.tokens + tokens_to_add)
            self.last_update = now

            if self.tokens < 1:
                # Calculate wait time
                wait_time = (1 - self.tokens) * (self.window_seconds / self.requests_per_window)
                logger.warning("Rate limit reached, waiting", wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
                self.tokens = 1

            self.tokens -= 1

    @property
    def available_tokens(self) -> float:
        """Get current available tokens."""
        now = time.monotonic()
        elapsed = now - self.last_update
        tokens_to_add = elapsed * (self.requests_per_window / self.window_seconds)
        return min(self.requests_per_window, self.tokens + tokens_to_add)


class TwitterStream:
    """Client for streaming Twitter/X cashtag mentions using API v2.

    Features:
    - Search recent tweets for ticker mentions
    - Track financial influencers
    - Rate limit handling with backoff
    - Filtered streaming for cashtags
    """

    STREAM_URL = "https://api.twitter.com/2/tweets/search/stream"
    RULES_URL = "https://api.twitter.com/2/tweets/search/stream/rules"
    RECENT_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"
    USER_TWEETS_URL = "https://api.twitter.com/2/users/{user_id}/tweets"
    USERS_BY_USERNAME_URL = "https://api.twitter.com/2/users/by"

    # Cashtag pattern
    CASHTAG_PATTERN = re.compile(r"\$([A-Z]{1,5})\b")

    def __init__(
        self,
        bearer_token: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        callback: Callable[[dict[str, Any]], None] | None = None,
    ):
        """Initialize Twitter stream client.

        Args:
            bearer_token: Twitter API bearer token (for app-only auth)
            api_key: Twitter API key (optional, for user auth)
            api_secret: Twitter API secret (optional, for user auth)
            callback: Optional callback for each tweet
        """
        self.bearer_token = bearer_token or settings.twitter_bearer_token
        self.api_key = api_key or settings.twitter_api_key
        self.api_secret = api_secret or settings.twitter_api_secret
        self.callback = callback
        self._running = False
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = RateLimiter(requests_per_window=450, window_seconds=900)
        self._user_id_cache: dict[str, str] = {}  # username -> user_id cache
        self._influencer_ids: list[str] = []  # Cached influencer user IDs

    async def __aenter__(self) -> "TwitterStream":
        """Async context manager entry."""
        if not self.bearer_token:
            logger.warning("Twitter bearer token not configured")

        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.bearer_token}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0, read=None),  # Read timeout None for streaming
        )

        # Pre-fetch influencer user IDs for tracking
        await self._cache_influencer_ids()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        self._running = False
        if self._client:
            await self._client.aclose()

    async def _cache_influencer_ids(self) -> None:
        """Cache user IDs for financial influencers."""
        if not self._client or not self.bearer_token:
            return

        all_influencers = FINANCIAL_INFLUENCERS + PENNY_STOCK_INFLUENCERS

        # Fetch user IDs in batches of 100 (API limit)
        for i in range(0, len(all_influencers), 100):
            batch = all_influencers[i:i + 100]
            try:
                await self._rate_limiter.acquire()
                response = await self._client.get(
                    self.USERS_BY_USERNAME_URL,
                    params={"usernames": ",".join(batch)},
                )

                if response.status_code == 200:
                    data = response.json()
                    for user in data.get("data", []):
                        user_id = user.get("id")
                        username = user.get("username", "").lower()
                        if user_id and username:
                            self._user_id_cache[username] = user_id
                            self._influencer_ids.append(user_id)

                elif response.status_code == 429:
                    # Rate limited - wait and retry
                    reset_time = int(response.headers.get("x-rate-limit-reset", 0))
                    wait_time = max(0, reset_time - time.time()) + 1
                    logger.warning("Rate limited while caching influencer IDs", wait_seconds=wait_time)
                    await asyncio.sleep(min(wait_time, 60))

            except Exception as e:
                logger.warning("Failed to cache influencer IDs", batch_start=i, error=str(e))

        logger.info("Cached influencer IDs", count=len(self._influencer_ids))

    async def set_stream_rules(self, tickers: list[str]) -> bool:
        """Set filtered stream rules for cashtags.

        Args:
            tickers: List of ticker symbols to track

        Returns:
            True if rules were set successfully
        """
        if not self._client or not self.bearer_token:
            return False

        try:
            # First, delete existing rules
            existing = await self._client.get(self.RULES_URL)
            existing_data = existing.json()

            if existing_data.get("data"):
                rule_ids = [rule["id"] for rule in existing_data["data"]]
                await self._client.post(
                    self.RULES_URL,
                    json={"delete": {"ids": rule_ids}},
                )

            # Create new rules for cashtags
            rules = []
            # Group tickers into rules (Twitter has rule length limits)
            batch_size = 10
            for i in range(0, len(tickers), batch_size):
                batch = tickers[i:i + batch_size]
                cashtags = " OR ".join(f"${t}" for t in batch)
                rules.append({
                    "value": cashtags,
                    "tag": f"cashtags_batch_{i // batch_size}",
                })

            if rules:
                response = await self._client.post(
                    self.RULES_URL,
                    json={"add": rules},
                )
                response.raise_for_status()

                logger.info("Set Twitter stream rules", rule_count=len(rules))
                return True

        except Exception as e:
            logger.error("Failed to set stream rules", error=str(e))

        return False

    async def stream_cashtags(
        self,
        tickers: list[str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream tweets containing cashtags.

        Args:
            tickers: Optional list of specific tickers to track

        Yields:
            Tweet data dictionaries
        """
        if not self._client or not self.bearer_token:
            logger.error("Twitter client not initialized or no bearer token")
            return

        # Set rules if tickers provided
        if tickers:
            await self.set_stream_rules(tickers)

        self._running = True

        params = {
            "tweet.fields": "created_at,author_id,public_metrics,entities",
            "expansions": "author_id",
            "user.fields": "username,verified,public_metrics",
        }

        while self._running:
            try:
                async with self._client.stream("GET", self.STREAM_URL, params=params) as response:
                    if response.status_code != 200:
                        logger.error("Stream error", status=response.status_code)
                        await asyncio.sleep(30)
                        continue

                    async for line in response.aiter_lines():
                        if not self._running:
                            break

                        if not line:
                            continue

                        try:
                            import json
                            data = json.loads(line)

                            if "data" in data:
                                tweet = self._parse_tweet(data)
                                if tweet:
                                    if self.callback:
                                        self.callback(tweet)
                                    yield tweet

                        except Exception as e:
                            logger.warning("Failed to parse tweet", error=str(e))

            except httpx.ReadTimeout:
                logger.info("Stream timeout, reconnecting...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error("Stream error", error=str(e))
                await asyncio.sleep(30)

    def _parse_tweet(self, data: dict[str, Any]) -> dict[str, Any] | None:
        """Parse raw tweet data into structured format.

        Args:
            data: Raw Twitter API response

        Returns:
            Parsed tweet dict or None
        """
        try:
            tweet_data = data.get("data", {})
            includes = data.get("includes", {})
            users = {u["id"]: u for u in includes.get("users", [])}

            text = tweet_data.get("text", "")
            author_id = tweet_data.get("author_id", "")
            author = users.get(author_id, {})

            # Extract cashtags
            cashtags = self.CASHTAG_PATTERN.findall(text.upper())

            # Get metrics
            metrics = tweet_data.get("public_metrics", {})
            author_metrics = author.get("public_metrics", {})

            # Calculate influence score
            followers = author_metrics.get("followers_count", 0)
            influence_score = min(1.0, followers / 100000)  # Normalize to 0-1

            return {
                "tweet_id": tweet_data.get("id", ""),
                "text": text,
                "author_id": author_id,
                "author_username": author.get("username", ""),
                "author_verified": author.get("verified", False),
                "author_followers": followers,
                "created_at": tweet_data.get("created_at", ""),
                "cashtags": cashtags,
                "ticker": cashtags[0] if cashtags else "",
                "retweet_count": metrics.get("retweet_count", 0),
                "like_count": metrics.get("like_count", 0),
                "reply_count": metrics.get("reply_count", 0),
                "influence_score": influence_score,
                "source": "twitter",
                "event_type": "SOCIAL_MENTION",
                "event_category": "TWITTER",
                "event_time": tweet_data.get("created_at", datetime.now(timezone.utc).isoformat()),
            }

        except Exception as e:
            logger.warning("Tweet parse error", error=str(e))
            return None

    async def search_recent(
        self,
        ticker: str,
        limit: int = 100,
        include_replies: bool = False,
        min_likes: int = 0,
    ) -> list[dict[str, Any]]:
        """Search recent tweets for a ticker.

        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of tweets
            include_replies: Include replies (default False)
            min_likes: Minimum likes filter (default 0)

        Returns:
            List of matching tweets
        """
        if not self._client or not self.bearer_token:
            return []

        try:
            await self._rate_limiter.acquire()

            # Build query with filters
            query_parts = [f"${ticker.upper()}"]
            if not include_replies:
                query_parts.append("-is:retweet")
                query_parts.append("-is:reply")

            query = " ".join(query_parts)

            params = {
                "query": query,
                "max_results": min(limit, 100),
                "tweet.fields": "created_at,author_id,public_metrics,context_annotations,entities",
                "expansions": "author_id,referenced_tweets.id",
                "user.fields": "username,verified,public_metrics,description",
            }

            response = await self._client.get(self.RECENT_SEARCH_URL, params=params)

            # Handle rate limiting
            if response.status_code == 429:
                reset_time = int(response.headers.get("x-rate-limit-reset", 0))
                wait_time = max(0, reset_time - time.time()) + 1
                logger.warning("Rate limited on search", ticker=ticker, wait_seconds=wait_time)
                await asyncio.sleep(min(wait_time, 60))
                return []

            response.raise_for_status()

            data = response.json()
            tweets = []

            includes = data.get("includes", {})
            users = {u["id"]: u for u in includes.get("users", [])}

            for tweet_data in data.get("data", []):
                # Apply min_likes filter
                metrics = tweet_data.get("public_metrics", {})
                if metrics.get("like_count", 0) < min_likes:
                    continue

                parsed = self._parse_tweet({
                    "data": tweet_data,
                    "includes": {"users": list(users.values())},
                })
                if parsed:
                    tweets.append(parsed)

            logger.debug("Searched recent tweets", ticker=ticker, found=len(tweets))
            return tweets

        except httpx.HTTPStatusError as e:
            logger.error("Search HTTP error", ticker=ticker, status=e.response.status_code)
            return []
        except Exception as e:
            logger.error("Search error", ticker=ticker, error=str(e))
            return []

    async def search_multiple_tickers(
        self,
        tickers: list[str],
        limit_per_ticker: int = 20,
    ) -> dict[str, list[dict[str, Any]]]:
        """Search recent tweets for multiple tickers.

        Args:
            tickers: List of ticker symbols
            limit_per_ticker: Maximum tweets per ticker

        Returns:
            Dictionary mapping ticker to list of tweets
        """
        results: dict[str, list[dict[str, Any]]] = {}

        for ticker in tickers:
            tweets = await self.search_recent(ticker, limit=limit_per_ticker)
            results[ticker.upper()] = tweets

            # Small delay between requests to be nice to API
            await asyncio.sleep(0.5)

        return results

    async def get_influencer_tweets(
        self,
        limit_per_user: int = 10,
        only_with_cashtags: bool = True,
        hours_back: int = 24,
    ) -> list[dict[str, Any]]:
        """Get recent tweets from financial influencers.

        Args:
            limit_per_user: Maximum tweets per influencer
            only_with_cashtags: Only return tweets with cashtags
            hours_back: How many hours back to search

        Returns:
            List of tweets from influencers
        """
        if not self._client or not self.bearer_token:
            return []

        all_tweets: list[dict[str, Any]] = []
        start_time = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()

        for user_id in self._influencer_ids[:20]:  # Limit to top 20 influencers
            try:
                await self._rate_limiter.acquire()

                params = {
                    "max_results": min(limit_per_user, 100),
                    "start_time": start_time,
                    "tweet.fields": "created_at,author_id,public_metrics,entities",
                    "expansions": "author_id",
                    "user.fields": "username,verified,public_metrics",
                    "exclude": "retweets,replies",
                }

                url = self.USER_TWEETS_URL.format(user_id=user_id)
                response = await self._client.get(url, params=params)

                if response.status_code == 429:
                    # Rate limited - stop fetching more users
                    logger.warning("Rate limited on influencer tweets")
                    break

                if response.status_code != 200:
                    continue

                data = response.json()
                includes = data.get("includes", {})
                users = {u["id"]: u for u in includes.get("users", [])}

                for tweet_data in data.get("data", []):
                    parsed = self._parse_tweet({
                        "data": tweet_data,
                        "includes": {"users": list(users.values())},
                    })

                    if parsed:
                        # Filter by cashtags if requested
                        if only_with_cashtags and not parsed.get("cashtags"):
                            continue

                        parsed["is_influencer"] = True
                        all_tweets.append(parsed)

                await asyncio.sleep(0.2)  # Small delay between users

            except Exception as e:
                logger.warning("Failed to get influencer tweets", user_id=user_id, error=str(e))

        logger.info("Fetched influencer tweets", total=len(all_tweets))
        return all_tweets

    async def get_trending_cashtags(
        self,
        sample_size: int = 500,
    ) -> list[dict[str, Any]]:
        """Get trending cashtags by sampling recent financial tweets.

        Args:
            sample_size: Number of tweets to sample

        Returns:
            List of trending cashtags with mention counts
        """
        if not self._client or not self.bearer_token:
            return []

        try:
            await self._rate_limiter.acquire()

            # Search for tweets with any cashtag
            params = {
                "query": "$ lang:en -is:retweet",
                "max_results": min(sample_size, 100),
                "tweet.fields": "created_at,public_metrics,entities",
            }

            response = await self._client.get(self.RECENT_SEARCH_URL, params=params)

            if response.status_code != 200:
                return []

            data = response.json()

            # Count cashtag mentions
            cashtag_counts: dict[str, dict[str, Any]] = {}

            for tweet_data in data.get("data", []):
                text = tweet_data.get("text", "")
                cashtags = self.CASHTAG_PATTERN.findall(text.upper())
                metrics = tweet_data.get("public_metrics", {})

                for tag in cashtags:
                    if tag not in cashtag_counts:
                        cashtag_counts[tag] = {
                            "ticker": tag,
                            "mention_count": 0,
                            "total_likes": 0,
                            "total_retweets": 0,
                        }
                    cashtag_counts[tag]["mention_count"] += 1
                    cashtag_counts[tag]["total_likes"] += metrics.get("like_count", 0)
                    cashtag_counts[tag]["total_retweets"] += metrics.get("retweet_count", 0)

            # Sort by mention count
            trending = sorted(
                cashtag_counts.values(),
                key=lambda x: x["mention_count"],
                reverse=True,
            )

            return trending[:50]  # Top 50 trending

        except Exception as e:
            logger.error("Failed to get trending cashtags", error=str(e))
            return []

    def stop(self) -> None:
        """Stop the stream."""
        self._running = False


async def main():
    """Example usage of Twitter stream."""
    async with TwitterStream() as stream:
        # Search for recent AAPL mentions
        print("Searching for $AAPL tweets...")
        tweets = await stream.search_recent("AAPL", limit=10)
        print(f"Found {len(tweets)} tweets for AAPL")

        for tweet in tweets[:5]:
            print(f"@{tweet['author_username']}: {tweet['text'][:80]}...")

        # Get influencer tweets
        print("\nFetching influencer tweets...")
        influencer_tweets = await stream.get_influencer_tweets(
            limit_per_user=5,
            only_with_cashtags=True,
            hours_back=24,
        )
        print(f"Found {len(influencer_tweets)} influencer tweets with cashtags")

        for tweet in influencer_tweets[:5]:
            tickers = ", ".join(tweet.get("cashtags", []))
            print(f"@{tweet['author_username']} [{tickers}]: {tweet['text'][:60]}...")

        # Get trending cashtags
        print("\nFetching trending cashtags...")
        trending = await stream.get_trending_cashtags(sample_size=100)
        print(f"Top trending cashtags:")
        for tag in trending[:10]:
            print(f"  ${tag['ticker']}: {tag['mention_count']} mentions, {tag['total_likes']} likes")


if __name__ == "__main__":
    asyncio.run(main())
