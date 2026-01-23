"""Market data enrichment tasks.

This module provides tasks for enriching events with market data including:
- Stock price at event time
- Market capitalization
- Trading volume
- Price changes (daily, weekly)
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog

from backend.config import settings
from backend.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================================
# Market Data Service
# ============================================================================

class MarketDataService:
    """Service for fetching market data from various sources.

    Uses free APIs like Yahoo Finance, Alpha Vantage (if configured),
    and polygon.io (if configured) to fetch market data.
    """

    # Yahoo Finance API (unofficial, no key required)
    YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    YAHOO_QUOTE_SUMMARY_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"

    def __init__(self):
        """Initialize market data service."""
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "MarketDataService":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; NewsScraperBot/1.0)",
            },
            timeout=30.0,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def get_quote(self, ticker: str) -> dict[str, Any] | None:
        """Get current quote for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Quote data or None if not found
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        try:
            # Try Yahoo Finance first
            url = self.YAHOO_QUOTE_URL.format(symbol=ticker.upper())
            params = {
                "interval": "1d",
                "range": "5d",
                "includePrePost": "false",
            }

            response = await self._client.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                result = data.get("chart", {}).get("result", [])

                if result:
                    meta = result[0].get("meta", {})
                    indicators = result[0].get("indicators", {})
                    quotes = indicators.get("quote", [{}])[0]
                    timestamps = result[0].get("timestamp", [])

                    # Get latest data
                    if timestamps:
                        close_prices = quotes.get("close", [])
                        volumes = quotes.get("volume", [])
                        open_prices = quotes.get("open", [])
                        high_prices = quotes.get("high", [])
                        low_prices = quotes.get("low", [])

                        # Filter out None values
                        close_prices = [p for p in close_prices if p is not None]
                        volumes = [v for v in volumes if v is not None]

                        current_price = meta.get("regularMarketPrice") or (
                            close_prices[-1] if close_prices else None
                        )
                        prev_close = meta.get("previousClose") or (
                            close_prices[-2] if len(close_prices) > 1 else None
                        )

                        return {
                            "ticker": ticker.upper(),
                            "price": current_price,
                            "previous_close": prev_close,
                            "open": open_prices[-1] if open_prices else None,
                            "high": high_prices[-1] if high_prices else None,
                            "low": low_prices[-1] if low_prices else None,
                            "volume": volumes[-1] if volumes else None,
                            "market_cap": meta.get("marketCap"),
                            "currency": meta.get("currency", "USD"),
                            "exchange": meta.get("exchangeName"),
                            "exchange_timezone": meta.get("exchangeTimezoneName"),
                            "regular_market_time": meta.get("regularMarketTime"),
                            "price_change": (
                                current_price - prev_close
                                if current_price and prev_close
                                else None
                            ),
                            "price_change_pct": (
                                ((current_price - prev_close) / prev_close * 100)
                                if current_price and prev_close
                                else None
                            ),
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                        }

            logger.debug("No quote data found", ticker=ticker)
            return None

        except Exception as e:
            logger.error("Failed to fetch quote", ticker=ticker, error=str(e))
            return None

    async def get_historical_price(
        self,
        ticker: str,
        target_date: datetime,
    ) -> dict[str, Any] | None:
        """Get historical price for a ticker at a specific date.

        Args:
            ticker: Stock ticker symbol
            target_date: Target datetime for price lookup

        Returns:
            Historical price data or None
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        try:
            # Calculate date range (get a few days around target)
            start_date = target_date - timedelta(days=5)
            end_date = target_date + timedelta(days=1)

            url = self.YAHOO_QUOTE_URL.format(symbol=ticker.upper())
            params = {
                "period1": int(start_date.timestamp()),
                "period2": int(end_date.timestamp()),
                "interval": "1d",
                "includePrePost": "false",
            }

            response = await self._client.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                result = data.get("chart", {}).get("result", [])

                if result:
                    timestamps = result[0].get("timestamp", [])
                    indicators = result[0].get("indicators", {})
                    quotes = indicators.get("quote", [{}])[0]

                    close_prices = quotes.get("close", [])
                    volumes = quotes.get("volume", [])

                    # Find closest date
                    target_ts = target_date.timestamp()
                    closest_idx = None
                    min_diff = float("inf")

                    for i, ts in enumerate(timestamps):
                        diff = abs(ts - target_ts)
                        if diff < min_diff:
                            min_diff = diff
                            closest_idx = i

                    if closest_idx is not None and closest_idx < len(close_prices):
                        return {
                            "ticker": ticker.upper(),
                            "target_date": target_date.isoformat(),
                            "actual_date": datetime.fromtimestamp(
                                timestamps[closest_idx], tz=timezone.utc
                            ).isoformat(),
                            "price": close_prices[closest_idx],
                            "volume": volumes[closest_idx] if closest_idx < len(volumes) else None,
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                        }

            return None

        except Exception as e:
            logger.error(
                "Failed to fetch historical price",
                ticker=ticker,
                target_date=str(target_date),
                error=str(e),
            )
            return None

    async def get_summary_data(self, ticker: str) -> dict[str, Any] | None:
        """Get summary data including market cap, shares outstanding, etc.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Summary data or None
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        try:
            url = self.YAHOO_QUOTE_SUMMARY_URL.format(symbol=ticker.upper())
            params = {
                "modules": "summaryDetail,defaultKeyStatistics,price",
            }

            response = await self._client.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                result = data.get("quoteSummary", {}).get("result", [])

                if result:
                    summary = result[0].get("summaryDetail", {})
                    key_stats = result[0].get("defaultKeyStatistics", {})
                    price_info = result[0].get("price", {})

                    return {
                        "ticker": ticker.upper(),
                        "market_cap": price_info.get("marketCap", {}).get("raw"),
                        "enterprise_value": key_stats.get("enterpriseValue", {}).get("raw"),
                        "shares_outstanding": key_stats.get("sharesOutstanding", {}).get("raw"),
                        "float_shares": key_stats.get("floatShares", {}).get("raw"),
                        "short_ratio": key_stats.get("shortRatio", {}).get("raw"),
                        "short_percent_of_float": key_stats.get("shortPercentOfFloat", {}).get("raw"),
                        "beta": summary.get("beta", {}).get("raw"),
                        "pe_ratio": summary.get("trailingPE", {}).get("raw"),
                        "forward_pe": summary.get("forwardPE", {}).get("raw"),
                        "avg_volume": summary.get("averageVolume", {}).get("raw"),
                        "avg_volume_10day": summary.get("averageVolume10days", {}).get("raw"),
                        "fifty_two_week_high": summary.get("fiftyTwoWeekHigh", {}).get("raw"),
                        "fifty_two_week_low": summary.get("fiftyTwoWeekLow", {}).get("raw"),
                        "fifty_day_average": summary.get("fiftyDayAverage", {}).get("raw"),
                        "two_hundred_day_average": summary.get("twoHundredDayAverage", {}).get("raw"),
                        "currency": price_info.get("currency", "USD"),
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    }

            return None

        except Exception as e:
            logger.error("Failed to fetch summary data", ticker=ticker, error=str(e))
            return None


# ============================================================================
# Enrichment Tasks
# ============================================================================

@celery_app.task(bind=True, max_retries=3)
def enrich_with_market_data_task(
    self,
    event_id: str,
    ticker: str | None = None,
    event_time: str | None = None,
) -> dict[str, Any]:
    """Enrich an event with market data.

    Fetches current price, market cap, volume, and other market metrics
    for the event's ticker and stores them in the event metadata.

    Args:
        event_id: UUID of the event to enrich
        ticker: Stock ticker (if not provided, fetched from event)
        event_time: Event timestamp for historical price lookup

    Returns:
        Enrichment results including market data
    """
    async def _enrich():
        from backend.storage.timescale.connection import get_sync_db_context
        from sqlalchemy import text
        import json

        results = {
            "event_id": event_id,
            "ticker": ticker,
            "enriched": False,
            "market_data": None,
            "error": None,
        }

        # Get event details if ticker not provided
        event_ticker = ticker
        event_datetime = None

        if not event_ticker or not event_time:
            with get_sync_db_context() as session:
                result = session.execute(
                    text(
                        "SELECT ticker, event_time, extra_data FROM events WHERE id = :id"
                    ),
                    {"id": event_id}
                )
                row = result.fetchone()
                if row:
                    event_ticker = event_ticker or row[0]
                    event_datetime = row[1]
                else:
                    results["error"] = "Event not found"
                    return results

        # Parse event time
        if event_time:
            try:
                event_datetime = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        if not event_ticker:
            results["error"] = "No ticker available"
            return results

        results["ticker"] = event_ticker

        # Fetch market data
        async with MarketDataService() as market:
            # Get current quote
            quote = await market.get_quote(event_ticker)

            # Get summary data
            summary = await market.get_summary_data(event_ticker)

            # Get historical price at event time if available
            historical = None
            if event_datetime:
                historical = await market.get_historical_price(event_ticker, event_datetime)

            if quote or summary:
                results["enriched"] = True
                results["market_data"] = {
                    "current_quote": quote,
                    "summary": summary,
                    "historical_at_event": historical,
                }

                # Update event in database
                try:
                    with get_sync_db_context() as session:
                        # Fetch current extra_data
                        result = session.execute(
                            text("SELECT extra_data FROM events WHERE id = :id"),
                            {"id": event_id}
                        )
                        row = result.fetchone()
                        current_extra_data = row[0] if row and row[0] else {}

                        # Merge market data
                        current_extra_data["market_data"] = {
                            "price_at_event": historical.get("price") if historical else quote.get("price") if quote else None,
                            "volume_at_event": historical.get("volume") if historical else quote.get("volume") if quote else None,
                            "market_cap": summary.get("market_cap") if summary else quote.get("market_cap") if quote else None,
                            "float_shares": summary.get("float_shares") if summary else None,
                            "short_interest": summary.get("short_percent_of_float") if summary else None,
                            "avg_volume": summary.get("avg_volume") if summary else None,
                            "fifty_two_week_high": summary.get("fifty_two_week_high") if summary else None,
                            "fifty_two_week_low": summary.get("fifty_two_week_low") if summary else None,
                            "enriched_at": datetime.now(timezone.utc).isoformat(),
                        }

                        # Update event
                        session.execute(
                            text(
                                "UPDATE events SET extra_data = :extra_data WHERE id = :id"
                            ),
                            {
                                "id": event_id,
                                "extra_data": json.dumps(current_extra_data),
                            }
                        )
                        session.commit()

                        logger.info(
                            "Event enriched with market data",
                            event_id=event_id,
                            ticker=event_ticker,
                        )

                except Exception as db_error:
                    logger.error(
                        "Failed to update event with market data",
                        event_id=event_id,
                        error=str(db_error),
                    )
                    results["db_error"] = str(db_error)
            else:
                results["error"] = "Could not fetch market data"

        return results

    try:
        return run_async(_enrich())
    except Exception as e:
        logger.error("Market data enrichment failed", event_id=event_id, error=str(e))
        raise self.retry(exc=e, countdown=30 * (self.request.retries + 1))


@celery_app.task(bind=True, max_retries=2)
def enrich_events_batch(
    self,
    event_ids: list[str],
    include_historical: bool = True,
) -> dict[str, Any]:
    """Enrich multiple events with market data in batch.

    Args:
        event_ids: List of event UUIDs to enrich
        include_historical: Whether to include historical price at event time

    Returns:
        Batch enrichment results
    """
    results = {
        "total": len(event_ids),
        "enriched": 0,
        "failed": 0,
        "details": [],
    }

    for event_id in event_ids:
        try:
            result = enrich_with_market_data_task(event_id)
            if result.get("enriched"):
                results["enriched"] += 1
            else:
                results["failed"] += 1
            results["details"].append(result)
        except Exception as e:
            results["failed"] += 1
            results["details"].append({
                "event_id": event_id,
                "error": str(e),
            })

    results["completed_at"] = datetime.now(timezone.utc).isoformat()
    return results


@celery_app.task
def get_market_data_for_ticker(ticker: str) -> dict[str, Any]:
    """Get comprehensive market data for a ticker.

    This is a utility task for fetching market data without event association.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Market data dictionary
    """
    async def _fetch():
        async with MarketDataService() as market:
            quote = await market.get_quote(ticker)
            summary = await market.get_summary_data(ticker)

            return {
                "ticker": ticker.upper(),
                "quote": quote,
                "summary": summary,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

    return run_async(_fetch())


@celery_app.task(bind=True, max_retries=2)
def enrich_high_alpha_events(
    self,
    min_alpha_score: float = 0.7,
    hours: int = 24,
) -> dict[str, Any]:
    """Enrich recent high-alpha events with market data.

    This task finds high-alpha events from the last N hours
    that haven't been enriched and enriches them with market data.

    Args:
        min_alpha_score: Minimum alpha score threshold
        hours: Look back period in hours

    Returns:
        Enrichment results
    """
    from backend.storage.timescale.connection import get_sync_db_context
    from sqlalchemy import text

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    results = {
        "found": 0,
        "enriched": 0,
        "failed": 0,
        "event_ids": [],
    }

    with get_sync_db_context() as session:
        # Find high-alpha events without market data
        query = text("""
            SELECT id, ticker, event_time
            FROM events
            WHERE alpha_score >= :min_alpha
              AND event_time >= :cutoff
              AND (extra_data IS NULL OR extra_data->>'market_data' IS NULL)
            ORDER BY alpha_score DESC
            LIMIT 100
        """)

        result = session.execute(
            query,
            {"min_alpha": min_alpha_score, "cutoff": cutoff}
        )
        events = result.fetchall()
        results["found"] = len(events)

    for event in events:
        event_id = str(event[0])
        ticker = event[1]
        event_time = event[2].isoformat() if event[2] else None

        try:
            enrich_result = enrich_with_market_data_task(
                event_id=event_id,
                ticker=ticker,
                event_time=event_time,
            )
            if enrich_result.get("enriched"):
                results["enriched"] += 1
            else:
                results["failed"] += 1
            results["event_ids"].append(event_id)
        except Exception as e:
            logger.error(
                "Failed to enrich high-alpha event",
                event_id=event_id,
                error=str(e),
            )
            results["failed"] += 1

    results["completed_at"] = datetime.now(timezone.utc).isoformat()
    return results


@celery_app.task
def get_liquidity_score_for_ticker(ticker: str) -> dict[str, Any]:
    """Get liquidity score for a ticker using live market data.

    Uses the LiquidityScorer with automatic market data lookup to
    determine liquidity category and alpha multiplier.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Liquidity score with market data
    """
    try:
        from backend.processing.scoring import LiquidityScorer

        scorer = LiquidityScorer(use_market_data_service=True)
        result = scorer.score_with_market_data(ticker)

        logger.info(
            "Liquidity score calculated",
            ticker=ticker,
            category=result.get("category"),
            market_cap=result.get("market_cap"),
        )

        return result

    except Exception as e:
        logger.error("Failed to get liquidity score", ticker=ticker, error=str(e))
        return {
            "ticker": ticker.upper(),
            "error": str(e),
            "category": "unknown",
            "alpha_multiplier": 1.0,
        }


@celery_app.task
def get_batch_market_caps(tickers: list[str]) -> dict[str, float | None]:
    """Get market caps for multiple tickers.

    Uses the MarketDataService to fetch market caps in batch for
    liquidity scoring and alpha calculation.

    Args:
        tickers: List of stock ticker symbols

    Returns:
        Dictionary mapping tickers to market caps (None if unavailable)
    """
    try:
        from backend.processing.scoring import get_market_data_service

        service = get_market_data_service()
        result = {}

        for ticker in tickers:
            market_cap = service.get_market_cap(ticker.upper())
            result[ticker.upper()] = market_cap

        logger.info(
            "Batch market caps fetched",
            count=len(tickers),
            successful=sum(1 for v in result.values() if v is not None),
        )

        return result

    except Exception as e:
        logger.error("Failed to get batch market caps", error=str(e))
        return {ticker.upper(): None for ticker in tickers}
