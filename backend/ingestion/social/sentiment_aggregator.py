"""Aggregator for cross-platform social sentiment."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

from .reddit_monitor import RedditMonitor
from .stocktwits_client import StockTwitsClient
from .twitter_stream import TwitterStream

logger = structlog.get_logger(__name__)


@dataclass
class AggregatedSentiment:
    """Aggregated sentiment across platforms."""

    symbol: str
    timestamp: str

    # Per-platform counts
    twitter_mentions: int = 0
    reddit_mentions: int = 0
    stocktwits_mentions: int = 0

    # Per-platform sentiment
    twitter_sentiment: float = 0.5  # 0-1 scale
    reddit_sentiment: float = 0.5
    stocktwits_sentiment: float = 0.5

    # Aggregated metrics
    total_mentions: int = 0
    overall_sentiment: float = 0.5
    sentiment_label: str = "neutral"

    # Trend indicators
    mention_velocity: float = 0.0  # mentions per hour
    sentiment_momentum: float = 0.0  # change from previous period

    # Raw data
    top_influencers: list[dict[str, Any]] = field(default_factory=list)
    sample_messages: list[dict[str, Any]] = field(default_factory=list)


class SocialSentimentAggregator:
    """Aggregates social sentiment from multiple platforms."""

    # Platform weights for overall sentiment calculation
    PLATFORM_WEIGHTS = {
        "twitter": 0.4,
        "stocktwits": 0.35,
        "reddit": 0.25,
    }

    def __init__(
        self,
        twitter_client: TwitterStream | None = None,
        reddit_client: RedditMonitor | None = None,
        stocktwits_client: StockTwitsClient | None = None,
    ):
        """Initialize sentiment aggregator.

        Args:
            twitter_client: Optional Twitter client instance
            reddit_client: Optional Reddit client instance
            stocktwits_client: Optional StockTwits client instance
        """
        self._twitter = twitter_client
        self._reddit = reddit_client
        self._stocktwits = stocktwits_client
        self._own_clients = False

    async def __aenter__(self) -> "SocialSentimentAggregator":
        """Async context manager entry."""
        # Initialize clients if not provided
        if self._twitter is None:
            self._twitter = TwitterStream()
            await self._twitter.__aenter__()
            self._own_clients = True

        if self._reddit is None:
            self._reddit = RedditMonitor()
            await self._reddit.__aenter__()
            self._own_clients = True

        if self._stocktwits is None:
            self._stocktwits = StockTwitsClient()
            await self._stocktwits.__aenter__()
            self._own_clients = True

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._own_clients:
            if self._twitter:
                await self._twitter.__aexit__(exc_type, exc_val, exc_tb)
            if self._reddit:
                await self._reddit.__aexit__(exc_type, exc_val, exc_tb)
            if self._stocktwits:
                await self._stocktwits.__aexit__(exc_type, exc_val, exc_tb)

    async def get_aggregated_sentiment(
        self,
        symbol: str,
        include_samples: bool = True,
    ) -> AggregatedSentiment:
        """Get aggregated sentiment for a symbol across all platforms.

        Args:
            symbol: Stock ticker symbol
            include_samples: Whether to include sample messages

        Returns:
            AggregatedSentiment object
        """
        symbol = symbol.upper()

        # Fetch from all platforms concurrently
        results = await asyncio.gather(
            self._get_twitter_sentiment(symbol),
            self._get_reddit_sentiment(symbol),
            self._get_stocktwits_sentiment(symbol),
            return_exceptions=True,
        )

        twitter_data, reddit_data, stocktwits_data = results

        # Handle any exceptions
        if isinstance(twitter_data, Exception):
            logger.warning("Twitter fetch failed", symbol=symbol, error=str(twitter_data))
            twitter_data = {"mentions": 0, "sentiment": 0.5, "messages": []}

        if isinstance(reddit_data, Exception):
            logger.warning("Reddit fetch failed", symbol=symbol, error=str(reddit_data))
            reddit_data = {"mentions": 0, "sentiment": 0.5, "posts": []}

        if isinstance(stocktwits_data, Exception):
            logger.warning("StockTwits fetch failed", symbol=symbol, error=str(stocktwits_data))
            stocktwits_data = {"mentions": 0, "sentiment": 0.5, "messages": []}

        # Calculate totals
        total_mentions = (
            twitter_data.get("mentions", 0) +
            reddit_data.get("mentions", 0) +
            stocktwits_data.get("mentions", 0)
        )

        # Calculate weighted overall sentiment
        overall_sentiment = self._calculate_overall_sentiment(
            twitter_data.get("sentiment", 0.5),
            reddit_data.get("sentiment", 0.5),
            stocktwits_data.get("sentiment", 0.5),
            twitter_data.get("mentions", 0),
            reddit_data.get("mentions", 0),
            stocktwits_data.get("mentions", 0),
        )

        # Determine sentiment label
        if overall_sentiment > 0.6:
            label = "bullish"
        elif overall_sentiment < 0.4:
            label = "bearish"
        else:
            label = "neutral"

        # Collect sample messages
        samples = []
        if include_samples:
            for msg in twitter_data.get("messages", [])[:3]:
                samples.append({
                    "platform": "twitter",
                    "text": msg.get("text", "")[:200],
                    "author": msg.get("author_username", ""),
                    "influence": msg.get("influence_score", 0),
                })

            for post in reddit_data.get("posts", [])[:3]:
                samples.append({
                    "platform": "reddit",
                    "text": post.get("title", "")[:200],
                    "author": post.get("author", ""),
                    "influence": post.get("engagement_score", 0),
                })

            for msg in stocktwits_data.get("messages", [])[:3]:
                samples.append({
                    "platform": "stocktwits",
                    "text": msg.get("body", "")[:200],
                    "author": msg.get("username", ""),
                    "influence": msg.get("influence_score", 0),
                })

        # Find top influencers
        all_authors = []
        for msg in twitter_data.get("messages", []):
            all_authors.append({
                "platform": "twitter",
                "username": msg.get("author_username", ""),
                "influence": msg.get("influence_score", 0),
            })
        for post in reddit_data.get("posts", []):
            all_authors.append({
                "platform": "reddit",
                "username": post.get("author", ""),
                "influence": post.get("engagement_score", 0),
            })
        for msg in stocktwits_data.get("messages", []):
            all_authors.append({
                "platform": "stocktwits",
                "username": msg.get("username", ""),
                "influence": msg.get("influence_score", 0),
            })

        top_influencers = sorted(
            all_authors,
            key=lambda x: x.get("influence", 0),
            reverse=True,
        )[:10]

        return AggregatedSentiment(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc).isoformat(),
            twitter_mentions=twitter_data.get("mentions", 0),
            reddit_mentions=reddit_data.get("mentions", 0),
            stocktwits_mentions=stocktwits_data.get("mentions", 0),
            twitter_sentiment=twitter_data.get("sentiment", 0.5),
            reddit_sentiment=reddit_data.get("sentiment", 0.5),
            stocktwits_sentiment=stocktwits_data.get("sentiment", 0.5),
            total_mentions=total_mentions,
            overall_sentiment=overall_sentiment,
            sentiment_label=label,
            top_influencers=top_influencers,
            sample_messages=samples,
        )

    async def _get_twitter_sentiment(self, symbol: str) -> dict[str, Any]:
        """Get Twitter sentiment for symbol."""
        if not self._twitter:
            return {"mentions": 0, "sentiment": 0.5, "messages": []}

        try:
            tweets = await self._twitter.search_recent(symbol, limit=50)

            if not tweets:
                return {"mentions": 0, "sentiment": 0.5, "messages": []}

            # Simple sentiment based on engagement
            # In production, would use FinBERT or similar
            positive_indicators = ["buy", "bullish", "moon", "long", "calls", "up"]
            negative_indicators = ["sell", "bearish", "short", "puts", "down", "dump"]

            bullish = 0
            bearish = 0

            for tweet in tweets:
                text = tweet.get("text", "").lower()
                if any(ind in text for ind in positive_indicators):
                    bullish += 1
                elif any(ind in text for ind in negative_indicators):
                    bearish += 1

            total = bullish + bearish
            sentiment = bullish / total if total > 0 else 0.5

            return {
                "mentions": len(tweets),
                "sentiment": sentiment,
                "messages": tweets,
            }

        except Exception as e:
            logger.error("Twitter sentiment error", symbol=symbol, error=str(e))
            return {"mentions": 0, "sentiment": 0.5, "messages": []}

    async def _get_reddit_sentiment(self, symbol: str) -> dict[str, Any]:
        """Get Reddit sentiment for symbol."""
        if not self._reddit:
            return {"mentions": 0, "sentiment": 0.5, "posts": []}

        try:
            posts = await self._reddit.search_ticker(symbol, limit=30)

            if not posts:
                return {"mentions": 0, "sentiment": 0.5, "posts": []}

            # Score-based sentiment (upvotes correlate with agreement)
            total_score = sum(p.get("score", 0) for p in posts)
            total_comments = sum(p.get("num_comments", 0) for p in posts)

            # Higher engagement suggests interest/bullishness
            engagement = (total_score + total_comments * 2) / len(posts)
            sentiment = min(1.0, 0.4 + engagement / 1000)

            return {
                "mentions": len(posts),
                "sentiment": sentiment,
                "posts": posts,
            }

        except Exception as e:
            logger.error("Reddit sentiment error", symbol=symbol, error=str(e))
            return {"mentions": 0, "sentiment": 0.5, "posts": []}

    async def _get_stocktwits_sentiment(self, symbol: str) -> dict[str, Any]:
        """Get StockTwits sentiment for symbol."""
        if not self._stocktwits:
            return {"mentions": 0, "sentiment": 0.5, "messages": []}

        try:
            sentiment_data = await self._stocktwits.get_symbol_sentiment(symbol)
            messages = await self._stocktwits.get_symbol_stream(symbol, limit=30)

            return {
                "mentions": sentiment_data.get("message_count", 0),
                "sentiment": sentiment_data.get("sentiment_ratio", 0.5),
                "messages": messages,
            }

        except Exception as e:
            logger.error("StockTwits sentiment error", symbol=symbol, error=str(e))
            return {"mentions": 0, "sentiment": 0.5, "messages": []}

    def _calculate_overall_sentiment(
        self,
        twitter_sentiment: float,
        reddit_sentiment: float,
        stocktwits_sentiment: float,
        twitter_mentions: int,
        reddit_mentions: int,
        stocktwits_mentions: int,
    ) -> float:
        """Calculate weighted overall sentiment.

        Weights are adjusted based on mention counts.
        """
        total_mentions = twitter_mentions + reddit_mentions + stocktwits_mentions

        if total_mentions == 0:
            return 0.5

        # Calculate mention-adjusted weights
        weights = {}
        for platform, base_weight in self.PLATFORM_WEIGHTS.items():
            if platform == "twitter":
                mentions = twitter_mentions
            elif platform == "reddit":
                mentions = reddit_mentions
            else:
                mentions = stocktwits_mentions

            # Adjust weight based on mention count
            mention_factor = min(2.0, 1 + mentions / 50)
            weights[platform] = base_weight * mention_factor

        # Normalize weights
        total_weight = sum(weights.values())
        for platform in weights:
            weights[platform] /= total_weight

        # Calculate weighted sentiment
        overall = (
            weights["twitter"] * twitter_sentiment +
            weights["reddit"] * reddit_sentiment +
            weights["stocktwits"] * stocktwits_sentiment
        )

        return overall

    def sentiment_to_event(self, sentiment: AggregatedSentiment) -> dict[str, Any]:
        """Convert aggregated sentiment to event format.

        Args:
            sentiment: AggregatedSentiment object

        Returns:
            Event dictionary
        """
        return {
            "ticker": sentiment.symbol,
            "event_type": "SOCIAL_SENTIMENT",
            "event_category": "SENTIMENT_AGGREGATE",
            "headline": f"{sentiment.symbol} social sentiment: {sentiment.sentiment_label} ({sentiment.total_mentions} mentions)",
            "summary": f"Cross-platform sentiment for {sentiment.symbol}: Twitter ({sentiment.twitter_mentions} mentions, {sentiment.twitter_sentiment:.0%}), Reddit ({sentiment.reddit_mentions} mentions), StockTwits ({sentiment.stocktwits_mentions} mentions, {sentiment.stocktwits_sentiment:.0%})",
            "sentiment_score": sentiment.overall_sentiment * 2 - 1,  # Convert to -1 to 1 scale
            "sentiment_label": sentiment.sentiment_label,
            "alpha_score": (sentiment.overall_sentiment - 0.5) * 0.6,  # Map to alpha score
            "direction": "BULLISH" if sentiment.overall_sentiment > 0.6 else "BEARISH" if sentiment.overall_sentiment < 0.4 else "NEUTRAL",
            "metadata": {
                "twitter_mentions": sentiment.twitter_mentions,
                "reddit_mentions": sentiment.reddit_mentions,
                "stocktwits_mentions": sentiment.stocktwits_mentions,
                "total_mentions": sentiment.total_mentions,
                "top_influencers": sentiment.top_influencers[:5],
            },
            "event_time": sentiment.timestamp,
            "source": "social_aggregate",
        }


async def main():
    """Example usage of sentiment aggregator."""
    async with SocialSentimentAggregator() as aggregator:
        sentiment = await aggregator.get_aggregated_sentiment("AAPL")

        print(f"Symbol: {sentiment.symbol}")
        print(f"Overall Sentiment: {sentiment.sentiment_label} ({sentiment.overall_sentiment:.2%})")
        print(f"Total Mentions: {sentiment.total_mentions}")
        print(f"  Twitter: {sentiment.twitter_mentions}")
        print(f"  Reddit: {sentiment.reddit_mentions}")
        print(f"  StockTwits: {sentiment.stocktwits_mentions}")


if __name__ == "__main__":
    asyncio.run(main())
