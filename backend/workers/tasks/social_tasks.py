"""Social media scraping and sentiment aggregation tasks for Celery workers.

This module provides tasks for:
- Twitter/X API scraping for financial tweets
- Sentiment aggregation across social platforms (Twitter, Reddit, StockTwits)
- Caching aggregated sentiment per ticker
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from backend.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# =============================================================================
# Twitter Scraping Tasks
# =============================================================================


@celery_app.task(bind=True, max_retries=3)
def scrape_twitter_tickers(self, tickers: list[str] | None = None) -> dict[str, Any]:
    """Scrape Twitter for specific ticker mentions.

    Args:
        tickers: List of tickers to search for

    Returns:
        Dictionary with scrape results
    """
    async def _scrape():
        from backend.ingestion.social import TwitterStream
        from backend.config import settings

        results = {"tweets": [], "error": None, "tickers_searched": []}

        if not settings.twitter_bearer_token:
            results["error"] = "Twitter bearer token not configured"
            logger.warning("Twitter scraping skipped - no bearer token")
            return results

        # Default popular tickers if none provided
        target_tickers = tickers or [
            "AAPL", "TSLA", "NVDA", "AMD", "MSFT",
            "META", "GOOGL", "AMZN", "SPY", "QQQ"
        ]

        try:
            async with TwitterStream() as twitter:
                for ticker in target_tickers:
                    try:
                        tweets = await twitter.search_recent(
                            ticker,
                            limit=20,
                            include_replies=False,
                            min_likes=5,  # Filter low-quality tweets
                        )
                        results["tweets"].extend(tweets)
                        results["tickers_searched"].append(ticker)
                    except Exception as ticker_error:
                        logger.warning(
                            "Failed to search ticker",
                            ticker=ticker,
                            error=str(ticker_error)
                        )

            results["count"] = len(results["tweets"])

            # Publish each tweet for processing
            from backend.workers.tasks.scraping_tasks import process_social_mention
            for tweet in results["tweets"]:
                process_social_mention.delay(tweet)

            logger.info(
                "Twitter ticker scrape complete",
                tweet_count=results["count"],
                tickers_searched=len(results["tickers_searched"]),
            )

        except Exception as e:
            logger.error("Twitter ticker scraping failed", error=str(e))
            results["error"] = str(e)
            raise self.retry(exc=e, countdown=60)

        return results

    return run_async(_scrape())


@celery_app.task(bind=True, max_retries=2)
def scrape_twitter_influencers(self) -> dict[str, Any]:
    """Scrape tweets from financial influencers.

    Returns:
        Dictionary with scrape results
    """
    async def _scrape():
        from backend.ingestion.social import TwitterStream
        from backend.config import settings

        results = {"tweets": [], "error": None}

        if not settings.twitter_bearer_token:
            results["error"] = "Twitter bearer token not configured"
            return results

        try:
            async with TwitterStream() as twitter:
                # Get influencer tweets from last 24 hours
                tweets = await twitter.get_influencer_tweets(
                    limit_per_user=10,
                    only_with_cashtags=True,
                    hours_back=24,
                )
                results["tweets"] = tweets
                results["count"] = len(tweets)

            # Publish each tweet for processing
            from backend.workers.tasks.scraping_tasks import process_social_mention
            for tweet in results["tweets"]:
                process_social_mention.delay(tweet)

            logger.info(
                "Twitter influencer scrape complete",
                tweet_count=results["count"],
            )

        except Exception as e:
            logger.error("Twitter influencer scraping failed", error=str(e))
            results["error"] = str(e)
            raise self.retry(exc=e, countdown=300)

        return results

    return run_async(_scrape())


@celery_app.task(bind=True, max_retries=2)
def get_twitter_trending_tickers(self) -> dict[str, Any]:
    """Get trending tickers from Twitter.

    Returns:
        Dictionary with trending tickers
    """
    async def _get_trending():
        from backend.ingestion.social import TwitterStream
        from backend.config import settings

        results = {"trending": [], "error": None}

        if not settings.twitter_bearer_token:
            results["error"] = "Twitter bearer token not configured"
            return results

        try:
            async with TwitterStream() as twitter:
                trending = await twitter.get_trending_cashtags(sample_size=500)
                results["trending"] = trending
                results["count"] = len(trending)

            # Cache trending tickers in Redis
            _cache_trending_tickers("twitter", trending)

            logger.info("Twitter trending tickers fetched", count=results["count"])

        except Exception as e:
            logger.error("Failed to get Twitter trending tickers", error=str(e))
            results["error"] = str(e)
            raise self.retry(exc=e, countdown=120)

        return results

    return run_async(_get_trending())


# =============================================================================
# Sentiment Aggregation Tasks
# =============================================================================


@celery_app.task(bind=True, max_retries=2)
def aggregate_ticker_sentiment(self, ticker: str) -> dict[str, Any]:
    """Aggregate sentiment for a ticker across all social platforms.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Aggregated sentiment data
    """
    async def _aggregate():
        from backend.ingestion.social import SocialSentimentAggregator

        results = {"sentiment": None, "error": None}

        try:
            async with SocialSentimentAggregator() as aggregator:
                sentiment = await aggregator.get_aggregated_sentiment(
                    ticker,
                    include_samples=True,
                )

                # Convert to dict for serialization
                results["sentiment"] = {
                    "symbol": sentiment.symbol,
                    "timestamp": sentiment.timestamp,
                    "twitter_mentions": sentiment.twitter_mentions,
                    "reddit_mentions": sentiment.reddit_mentions,
                    "stocktwits_mentions": sentiment.stocktwits_mentions,
                    "twitter_sentiment": sentiment.twitter_sentiment,
                    "reddit_sentiment": sentiment.reddit_sentiment,
                    "stocktwits_sentiment": sentiment.stocktwits_sentiment,
                    "total_mentions": sentiment.total_mentions,
                    "overall_sentiment": sentiment.overall_sentiment,
                    "sentiment_label": sentiment.sentiment_label,
                    "mention_velocity": sentiment.mention_velocity,
                    "sentiment_momentum": sentiment.sentiment_momentum,
                    "top_influencers": sentiment.top_influencers,
                    "sample_messages": sentiment.sample_messages,
                }

                # Cache the aggregated sentiment
                _cache_ticker_sentiment(ticker, results["sentiment"])

                # Convert to event and store if significant activity
                if sentiment.total_mentions >= 10:
                    event = aggregator.sentiment_to_event(sentiment)
                    from backend.workers.tasks.scraping_tasks import process_event
                    process_event.delay(event)

            logger.info(
                "Sentiment aggregated",
                ticker=ticker,
                total_mentions=results["sentiment"]["total_mentions"],
                overall_sentiment=results["sentiment"]["overall_sentiment"],
            )

        except Exception as e:
            logger.error("Sentiment aggregation failed", ticker=ticker, error=str(e))
            results["error"] = str(e)
            raise self.retry(exc=e, countdown=30)

        return results

    return run_async(_aggregate())


@celery_app.task
def aggregate_watchlist_sentiment(user_id: str) -> dict[str, Any]:
    """Aggregate sentiment for all tickers in a user's watchlist.

    Args:
        user_id: User UUID string

    Returns:
        Dictionary of ticker -> sentiment data
    """
    from backend.storage.timescale.connection import get_sync_db_context
    from backend.storage.timescale.models import Watchlist
    from sqlalchemy import text

    results = {"sentiments": {}, "error": None}

    try:
        # Get user's watchlist
        with get_sync_db_context() as session:
            watchlist_items = session.query(Watchlist).filter(
                Watchlist.user_id == user_id
            ).all()
            tickers = [item.ticker for item in watchlist_items]

        if not tickers:
            logger.info("No tickers in watchlist", user_id=user_id)
            return results

        # Aggregate sentiment for each ticker
        for ticker in tickers:
            try:
                result = aggregate_ticker_sentiment(ticker)
                if result.get("sentiment"):
                    results["sentiments"][ticker] = result["sentiment"]
            except Exception as e:
                logger.warning(
                    "Failed to aggregate sentiment for ticker",
                    ticker=ticker,
                    error=str(e)
                )

        logger.info(
            "Watchlist sentiment aggregated",
            user_id=user_id,
            ticker_count=len(results["sentiments"]),
        )

    except Exception as e:
        logger.error("Watchlist sentiment aggregation failed", user_id=user_id, error=str(e))
        results["error"] = str(e)

    return results


@celery_app.task
def aggregate_trending_sentiment() -> dict[str, Any]:
    """Aggregate sentiment for trending tickers across platforms.

    Returns:
        Dictionary of trending tickers with sentiment
    """
    async def _aggregate():
        from backend.ingestion.social import (
            SocialSentimentAggregator,
            StockTwitsClient,
            TwitterStream,
        )
        from backend.config import settings

        results = {"trending": [], "error": None}

        try:
            # Get trending tickers from multiple sources
            trending_tickers: set[str] = set()

            # StockTwits trending
            async with StockTwitsClient() as stocktwits:
                stocktwits_trending = await stocktwits.get_trending()
                for item in stocktwits_trending[:20]:
                    trending_tickers.add(item["symbol"].upper())

            # Twitter trending (if configured)
            if settings.twitter_bearer_token:
                try:
                    async with TwitterStream() as twitter:
                        twitter_trending = await twitter.get_trending_cashtags(sample_size=200)
                        for item in twitter_trending[:20]:
                            trending_tickers.add(item["ticker"].upper())
                except Exception as e:
                    logger.warning("Failed to get Twitter trending", error=str(e))

            # Aggregate sentiment for top trending
            async with SocialSentimentAggregator() as aggregator:
                for ticker in list(trending_tickers)[:30]:  # Limit to top 30
                    try:
                        sentiment = await aggregator.get_aggregated_sentiment(
                            ticker,
                            include_samples=False,
                        )
                        results["trending"].append({
                            "ticker": ticker,
                            "total_mentions": sentiment.total_mentions,
                            "overall_sentiment": sentiment.overall_sentiment,
                            "sentiment_label": sentiment.sentiment_label,
                            "twitter_mentions": sentiment.twitter_mentions,
                            "reddit_mentions": sentiment.reddit_mentions,
                            "stocktwits_mentions": sentiment.stocktwits_mentions,
                        })

                        # Cache individual ticker sentiment
                        _cache_ticker_sentiment(ticker, {
                            "symbol": sentiment.symbol,
                            "timestamp": sentiment.timestamp,
                            "total_mentions": sentiment.total_mentions,
                            "overall_sentiment": sentiment.overall_sentiment,
                            "sentiment_label": sentiment.sentiment_label,
                        })

                    except Exception as e:
                        logger.warning(
                            "Failed to aggregate trending ticker sentiment",
                            ticker=ticker,
                            error=str(e)
                        )

            # Sort by mention count
            results["trending"].sort(
                key=lambda x: x["total_mentions"],
                reverse=True,
            )

            # Cache full trending list
            _cache_trending_sentiment(results["trending"])

            logger.info(
                "Trending sentiment aggregated",
                ticker_count=len(results["trending"]),
            )

        except Exception as e:
            logger.error("Trending sentiment aggregation failed", error=str(e))
            results["error"] = str(e)

        return results

    return run_async(_aggregate())


# =============================================================================
# Cache Helper Functions
# =============================================================================


def _get_redis_client():
    """Get Redis client for caching."""
    import redis
    from backend.config import settings
    return redis.from_url(str(settings.redis_url))


def _cache_ticker_sentiment(ticker: str, sentiment_data: dict[str, Any]) -> None:
    """Cache ticker sentiment in Redis.

    Args:
        ticker: Ticker symbol
        sentiment_data: Sentiment data dictionary
    """
    try:
        client = _get_redis_client()

        # Store with 15-minute TTL
        key = f"sentiment:ticker:{ticker.upper()}"
        client.setex(
            key,
            timedelta(minutes=15),
            json.dumps(sentiment_data),
        )

        # Also add to sorted set of recent sentiment updates
        client.zadd(
            "sentiment:recent",
            {ticker.upper(): datetime.now(timezone.utc).timestamp()},
        )
        # Keep only last 1000 entries
        client.zremrangebyrank("sentiment:recent", 0, -1001)

        client.close()
        logger.debug("Cached ticker sentiment", ticker=ticker)

    except Exception as e:
        logger.warning("Failed to cache ticker sentiment", ticker=ticker, error=str(e))


def _cache_trending_sentiment(trending_data: list[dict[str, Any]]) -> None:
    """Cache trending sentiment list in Redis.

    Args:
        trending_data: List of trending ticker sentiment
    """
    try:
        client = _get_redis_client()

        # Store with 5-minute TTL
        key = "sentiment:trending"
        client.setex(
            key,
            timedelta(minutes=5),
            json.dumps(trending_data),
        )

        client.close()
        logger.debug("Cached trending sentiment", count=len(trending_data))

    except Exception as e:
        logger.warning("Failed to cache trending sentiment", error=str(e))


def _cache_trending_tickers(source: str, trending_data: list[dict[str, Any]]) -> None:
    """Cache trending tickers from a specific source.

    Args:
        source: Source name (twitter, stocktwits, reddit)
        trending_data: List of trending ticker data
    """
    try:
        client = _get_redis_client()

        # Store with 10-minute TTL
        key = f"trending:{source}"
        client.setex(
            key,
            timedelta(minutes=10),
            json.dumps(trending_data),
        )

        client.close()
        logger.debug("Cached trending tickers", source=source, count=len(trending_data))

    except Exception as e:
        logger.warning("Failed to cache trending tickers", source=source, error=str(e))


def get_cached_ticker_sentiment(ticker: str) -> dict[str, Any] | None:
    """Get cached sentiment for a ticker.

    Args:
        ticker: Ticker symbol

    Returns:
        Cached sentiment data or None
    """
    try:
        client = _get_redis_client()
        key = f"sentiment:ticker:{ticker.upper()}"
        data = client.get(key)
        client.close()

        if data:
            return json.loads(data)

    except Exception as e:
        logger.warning("Failed to get cached sentiment", ticker=ticker, error=str(e))

    return None


def get_cached_trending_sentiment() -> list[dict[str, Any]]:
    """Get cached trending sentiment list.

    Returns:
        List of trending ticker sentiment or empty list
    """
    try:
        client = _get_redis_client()
        key = "sentiment:trending"
        data = client.get(key)
        client.close()

        if data:
            return json.loads(data)

    except Exception as e:
        logger.warning("Failed to get cached trending sentiment", error=str(e))

    return []


# =============================================================================
# Scheduled Task Wrappers
# =============================================================================


@celery_app.task
def scheduled_twitter_scrape() -> dict[str, Any]:
    """Scheduled task to scrape Twitter for popular tickers."""
    # Get trending tickers first, then scrape them
    trending_result = get_twitter_trending_tickers()

    if trending_result.get("trending"):
        tickers = [t["ticker"] for t in trending_result["trending"][:10]]
        return scrape_twitter_tickers(tickers)

    # Fallback to default tickers
    return scrape_twitter_tickers()


@celery_app.task
def scheduled_sentiment_aggregation() -> dict[str, Any]:
    """Scheduled task to aggregate sentiment for trending tickers."""
    return aggregate_trending_sentiment()


@celery_app.task
def scheduled_influencer_scrape() -> dict[str, Any]:
    """Scheduled task to scrape financial influencer tweets."""
    return scrape_twitter_influencers()
