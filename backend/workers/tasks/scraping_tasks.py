"""Scraping tasks for Celery workers."""

import asyncio
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


@celery_app.task(bind=True, max_retries=3)
def scrape_sec_filings(self) -> dict[str, Any]:
    """Scrape latest SEC EDGAR filings.

    Returns:
        Dictionary with scrape results
    """
    async def _scrape():
        from backend.ingestion.sec_edgar import SECStreamingClient

        results = {"filings": [], "error": None}

        try:
            async with SECStreamingClient(poll_interval=0) as client:
                filings = await client.fetch_recent(count=50)
                results["filings"] = filings
                results["count"] = len(filings)

                # Publish each filing for processing
                for filing in filings:
                    process_filing.delay(filing)

        except Exception as e:
            logger.error("SEC scraping failed", error=str(e))
            results["error"] = str(e)
            raise self.retry(exc=e, countdown=30)

        return results

    return run_async(_scrape())


@celery_app.task(bind=True, max_retries=3)
def scrape_news(self) -> dict[str, Any]:
    """Scrape news from configured sources.

    Returns:
        Dictionary with scrape results
    """
    async def _scrape():
        from backend.ingestion.scrapers import NewswireClient, RSSAggregator

        results = {"articles": [], "error": None}

        try:
            # Scrape newswires
            async with NewswireClient() as newswire:
                releases = await newswire.scrape()
                results["articles"].extend(releases)

            # Scrape RSS feeds
            async with RSSAggregator() as rss:
                articles = await rss.scrape()
                results["articles"].extend(articles)

            results["count"] = len(results["articles"])

            # Publish each article for processing
            for article in results["articles"]:
                process_article.delay(article)

        except Exception as e:
            logger.error("News scraping failed", error=str(e))
            results["error"] = str(e)
            raise self.retry(exc=e, countdown=60)

        return results

    return run_async(_scrape())


@celery_app.task(bind=True, max_retries=3)
def scrape_social(self) -> dict[str, Any]:
    """Scrape social media for stock mentions.

    Returns:
        Dictionary with scrape results
    """
    async def _scrape():
        from backend.ingestion.social import RedditMonitor, StockTwitsClient, TwitterStream
        from backend.config import settings

        results = {"mentions": [], "error": None}

        try:
            # Get trending tickers from StockTwits
            async with StockTwitsClient() as stocktwits:
                trending = await stocktwits.get_trending()
                tickers = [t["symbol"] for t in trending[:20]]

                for ticker in tickers[:5]:  # Limit to avoid rate limits
                    messages = await stocktwits.get_symbol_stream(ticker, limit=10)
                    results["mentions"].extend(messages)

            # Scrape Reddit
            async with RedditMonitor() as reddit:
                posts = await reddit.get_subreddit_posts("pennystocks", limit=25)
                results["mentions"].extend(posts)

            # Scrape Twitter if bearer token is configured
            if settings.twitter_bearer_token:
                try:
                    async with TwitterStream() as twitter:
                        # Search recent tweets for trending tickers
                        for ticker in tickers[:5]:
                            tweets = await twitter.search_recent(ticker, limit=10)
                            results["mentions"].extend(tweets)
                except Exception as twitter_error:
                    logger.warning("Twitter scraping failed", error=str(twitter_error))

            results["count"] = len(results["mentions"])

            # Publish each mention for processing
            for mention in results["mentions"]:
                process_social_mention.delay(mention)

        except Exception as e:
            logger.error("Social scraping failed", error=str(e))
            results["error"] = str(e)
            raise self.retry(exc=e, countdown=120)

        return results

    return run_async(_scrape())


@celery_app.task(bind=True, max_retries=2)
def scrape_twitter_stream(self, tickers: list[str] | None = None) -> dict[str, Any]:
    """Scrape Twitter for cashtag mentions.

    Args:
        tickers: Optional list of tickers to track

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
                # Default to some popular penny stock tickers if none provided
                target_tickers = tickers or ["MULN", "BBIG", "ATER", "PROG", "CEI"]

                for ticker in target_tickers[:10]:
                    tweets = await twitter.search_recent(ticker, limit=20)
                    results["tweets"].extend(tweets)

            results["count"] = len(results["tweets"])

            # Publish each tweet for processing
            for tweet in results["tweets"]:
                process_social_mention.delay(tweet)

        except Exception as e:
            logger.error("Twitter scraping failed", error=str(e))
            results["error"] = str(e)
            raise self.retry(exc=e, countdown=300)

        return results

    return run_async(_scrape())


@celery_app.task(bind=True, max_retries=2)
def check_otc_tiers(self) -> dict[str, Any]:
    """Check for OTC tier changes and generate events.

    This task monitors OTC Markets for tier changes (upgrades/downgrades)
    and creates events for each detected change. Tier changes are significant
    events for OTC stocks as they indicate changes in compliance status,
    reporting standards, and overall company health.

    OTC Tiers (from best to worst):
    - OTCQX: Best Market - highest standards
    - OTCQB: Venture Market - emerging growth
    - Pink Current: Limited information
    - Pink Limited: Minimal information
    - Pink No Information: No information
    - Grey Market: Not quoted
    - Expert Market: Restricted

    Returns:
        Dictionary with tier change results including:
        - changes: List of tier change events
        - count: Number of changes detected
        - upgrades: Count of tier upgrades
        - downgrades: Count of tier downgrades
        - error: Error message if any
    """
    async def _check():
        from backend.ingestion.otc_markets import TierMonitor

        results = {
            "changes": [],
            "count": 0,
            "upgrades": 0,
            "downgrades": 0,
            "error": None,
        }

        try:
            # Use persistence to track tiers across task runs
            async with TierMonitor(use_persistence=True) as monitor:
                # Get tier changes from the last day
                # The monitor handles deduplication via Redis persistence
                changes = await monitor.get_tier_changes(days=1)

                logger.info(
                    "OTC tier check completed",
                    changes_found=len(changes),
                )

                for change in changes:
                    # Convert to event format
                    event = monitor.tier_change_to_event(change)
                    results["changes"].append(event)

                    # Track upgrade/downgrade counts
                    if change.is_upgrade:
                        results["upgrades"] += 1
                    elif change.is_downgrade:
                        results["downgrades"] += 1

                    # Publish for processing through the pipeline
                    # Since tier changes are already classified, use process_event
                    process_event.delay(event)

                    logger.info(
                        "Tier change event queued",
                        symbol=change.symbol,
                        old_tier=change.old_tier.value,
                        new_tier=change.new_tier.value,
                        is_upgrade=change.is_upgrade,
                        signal_strength=change.signal_strength,
                    )

            results["count"] = len(results["changes"])

        except Exception as e:
            logger.error("OTC tier check failed", error=str(e), exc_info=True)
            results["error"] = str(e)
            # Retry with 5 minute delay
            raise self.retry(exc=e, countdown=300)

        return results

    return run_async(_check())


@celery_app.task
def process_filing(filing: dict[str, Any]) -> dict[str, Any]:
    """Process a single SEC filing through NLP pipeline.

    Args:
        filing: Filing data dictionary

    Returns:
        Task chain info
    """
    from backend.workers.tasks.nlp_tasks import extract_entities_task, analyze_sentiment_task
    from backend.workers.tasks.scoring_tasks import calculate_alpha_task
    from backend.workers.tasks.storage_tasks import store_event_task
    from backend.workers.tasks.alerting_tasks import check_alerts_task

    # Chain: extract entities -> analyze sentiment -> calculate alpha -> store -> check alerts
    chain = (
        extract_entities_task.s(filing) |
        analyze_sentiment_task.s() |
        calculate_alpha_task.s() |
        store_event_task.s() |
        check_alerts_task.s()
    )

    result = chain.apply_async()
    return {
        "task_id": result.id,
        "status": "processing",
        "source": filing.get("source", "sec_edgar"),
        "ticker": filing.get("ticker"),
    }


@celery_app.task
def process_article(article: dict[str, Any]) -> dict[str, Any]:
    """Process a single news article through NLP pipeline.

    Args:
        article: Article data dictionary

    Returns:
        Task chain info
    """
    from backend.workers.tasks.nlp_tasks import extract_entities_task, analyze_sentiment_task
    from backend.workers.tasks.scoring_tasks import calculate_alpha_task
    from backend.workers.tasks.storage_tasks import store_event_task
    from backend.workers.tasks.alerting_tasks import check_alerts_task

    # Chain: extract entities -> analyze sentiment -> calculate alpha -> store -> check alerts
    chain = (
        extract_entities_task.s(article) |
        analyze_sentiment_task.s() |
        calculate_alpha_task.s() |
        store_event_task.s() |
        check_alerts_task.s()
    )

    result = chain.apply_async()
    return {
        "task_id": result.id,
        "status": "processing",
        "source": article.get("source", "news"),
        "ticker": article.get("ticker"),
    }


@celery_app.task
def process_social_mention(mention: dict[str, Any]) -> dict[str, Any]:
    """Process a single social media mention through NLP pipeline.

    Args:
        mention: Mention data dictionary

    Returns:
        Task chain info
    """
    from backend.workers.tasks.nlp_tasks import analyze_sentiment_task
    from backend.workers.tasks.scoring_tasks import calculate_alpha_task
    from backend.workers.tasks.storage_tasks import store_event_task
    from backend.workers.tasks.alerting_tasks import check_alerts_task

    # Social mentions may already have ticker extracted
    # Chain: analyze sentiment -> calculate alpha -> store -> check alerts
    chain = (
        analyze_sentiment_task.s(mention) |
        calculate_alpha_task.s() |
        store_event_task.s() |
        check_alerts_task.s()
    )

    result = chain.apply_async()
    return {
        "task_id": result.id,
        "status": "processing",
        "source": mention.get("source", "social"),
        "ticker": mention.get("ticker"),
    }


@celery_app.task
def process_event(event: dict[str, Any]) -> dict[str, Any]:
    """Process a generic event (already classified, needs scoring).

    Args:
        event: Event data dictionary

    Returns:
        Task chain info
    """
    # Events already have ticker and classification
    from backend.workers.tasks.scoring_tasks import calculate_alpha_task
    from backend.workers.tasks.storage_tasks import store_event_task
    from backend.workers.tasks.alerting_tasks import check_alerts_task

    # Chain: calculate alpha -> store -> check alerts
    chain = (
        calculate_alpha_task.s(event) |
        store_event_task.s() |
        check_alerts_task.s()
    )

    result = chain.apply_async()
    return {
        "task_id": result.id,
        "status": "processing",
        "source": event.get("source", "event"),
        "ticker": event.get("ticker"),
    }


@celery_app.task
def backfill_data(ticker: str, days: int = 30) -> dict[str, Any]:
    """Backfill historical data for a ticker.

    Args:
        ticker: Stock ticker symbol
        days: Number of days to backfill

    Returns:
        Backfill results
    """
    async def _backfill():
        from backend.ingestion.sec_edgar import SECPollingClient

        results = {"filings": [], "error": None}

        try:
            async with SECPollingClient() as client:
                filings = await client.get_company_filings(
                    ticker=ticker,
                    limit=100,
                )
                results["filings"] = filings
                results["count"] = len(filings)

                # Process each filing
                for filing in filings:
                    process_filing.delay(filing)

        except Exception as e:
            logger.error("Backfill failed", ticker=ticker, error=str(e))
            results["error"] = str(e)

        return results

    return run_async(_backfill())
