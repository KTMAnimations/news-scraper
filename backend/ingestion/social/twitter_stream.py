"""Twitter/X API client for streaming cashtag mentions."""

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable

import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)


class TwitterStream:
    """Client for streaming Twitter/X cashtag mentions using API v2."""

    STREAM_URL = "https://api.twitter.com/2/tweets/search/stream"
    RULES_URL = "https://api.twitter.com/2/tweets/search/stream/rules"
    RECENT_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"

    # Cashtag pattern
    CASHTAG_PATTERN = re.compile(r"\$([A-Z]{1,5})\b")

    def __init__(
        self,
        bearer_token: str | None = None,
        callback: Callable[[dict[str, Any]], None] | None = None,
    ):
        """Initialize Twitter stream client.

        Args:
            bearer_token: Twitter API bearer token
            callback: Optional callback for each tweet
        """
        self.bearer_token = bearer_token or settings.twitter_bearer_token
        self.callback = callback
        self._running = False
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "TwitterStream":
        """Async context manager entry."""
        if not self.bearer_token:
            logger.warning("Twitter bearer token not configured")

        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.bearer_token}",
                "Content-Type": "application/json",
            },
            timeout=None,  # Streaming requires no timeout
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        self._running = False
        if self._client:
            await self._client.aclose()

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
    ) -> list[dict[str, Any]]:
        """Search recent tweets for a ticker.

        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of tweets

        Returns:
            List of matching tweets
        """
        if not self._client or not self.bearer_token:
            return []

        try:
            params = {
                "query": f"${ticker.upper()} -is:retweet",
                "max_results": min(limit, 100),
                "tweet.fields": "created_at,author_id,public_metrics",
                "expansions": "author_id",
                "user.fields": "username,verified,public_metrics",
            }

            response = await self._client.get(self.RECENT_SEARCH_URL, params=params)
            response.raise_for_status()

            data = response.json()
            tweets = []

            includes = data.get("includes", {})
            users = {u["id"]: u for u in includes.get("users", [])}

            for tweet_data in data.get("data", []):
                parsed = self._parse_tweet({
                    "data": tweet_data,
                    "includes": {"users": list(users.values())},
                })
                if parsed:
                    tweets.append(parsed)

            return tweets

        except Exception as e:
            logger.error("Search error", ticker=ticker, error=str(e))
            return []

    def stop(self) -> None:
        """Stop the stream."""
        self._running = False


async def main():
    """Example usage of Twitter stream."""
    async with TwitterStream() as stream:
        # Search for recent AAPL mentions
        tweets = await stream.search_recent("AAPL", limit=10)
        print(f"Found {len(tweets)} tweets")

        for tweet in tweets[:5]:
            print(f"@{tweet['author_username']}: {tweet['text'][:80]}...")


if __name__ == "__main__":
    asyncio.run(main())
