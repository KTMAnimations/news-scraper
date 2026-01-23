"""Backfill tasks for historical data retrieval.

This module provides tasks for backfilling historical SEC filings
and other data sources for analysis and training purposes.
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
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


@celery_app.task(bind=True, max_retries=3, soft_time_limit=3600, time_limit=3900)
def backfill_historical_data(
    self,
    start_date: str,
    end_date: str,
    tickers: list[str] | None = None,
    filing_types: list[str] | None = None,
    batch_size: int = 10,
) -> dict[str, Any]:
    """Backfill historical SEC filings for a date range.

    This task fetches historical filings from SEC EDGAR for the specified
    date range and processes them through the NLP pipeline.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        tickers: Optional list of specific tickers to backfill (defaults to all SEC filings)
        filing_types: Optional list of filing types to include (defaults to ["4", "8-K", "SC 13D", "SC 13G"])
        batch_size: Number of tickers to process in parallel (default 10)

    Returns:
        Dictionary with backfill results including:
        - total_filings: Number of filings fetched
        - processed: Number of filings sent for processing
        - errors: List of any errors encountered
        - duration_seconds: Total time taken

    Example:
        backfill_historical_data.delay(
            start_date="2024-01-01",
            end_date="2024-01-31",
            tickers=["AAPL", "MSFT", "GOOGL"],
            filing_types=["4", "8-K"]
        )
    """
    async def _backfill():
        from backend.ingestion.sec_edgar import SECPollingClient
        from backend.workers.tasks.scraping_tasks import process_filing

        start_time = datetime.now(timezone.utc)
        results = {
            "start_date": start_date,
            "end_date": end_date,
            "tickers_requested": tickers,
            "filing_types": filing_types,
            "total_filings": 0,
            "processed": 0,
            "skipped": 0,
            "errors": [],
            "ticker_results": {},
        }

        # Parse dates
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError as e:
            results["errors"].append(f"Invalid date format: {e}")
            return results

        # Validate date range
        if start > end:
            results["errors"].append("start_date must be before end_date")
            return results

        if (end - start).days > 365:
            results["errors"].append("Date range cannot exceed 365 days")
            return results

        # Default filing types for penny stock relevant filings
        default_filing_types = ["4", "8-K", "SC 13D", "SC 13G", "10-K", "10-Q"]
        target_filing_types = filing_types or default_filing_types

        async with SECPollingClient() as client:
            if tickers:
                # Backfill specific tickers
                for i in range(0, len(tickers), batch_size):
                    batch = tickers[i:i + batch_size]

                    # Process batch in parallel
                    tasks = [
                        _fetch_ticker_filings(
                            client, ticker, start, end, target_filing_types
                        )
                        for ticker in batch
                    ]

                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                    for ticker, result in zip(batch, batch_results):
                        if isinstance(result, Exception):
                            results["errors"].append(f"{ticker}: {str(result)}")
                            results["ticker_results"][ticker] = {"error": str(result)}
                        else:
                            results["ticker_results"][ticker] = result
                            results["total_filings"] += result.get("filings_count", 0)
                            results["processed"] += result.get("processed", 0)

                    # Rate limiting between batches
                    await asyncio.sleep(1)

                    # Update progress
                    progress = (i + batch_size) / len(tickers)
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "progress": min(progress, 1.0),
                            "current_batch": i // batch_size + 1,
                            "total_batches": (len(tickers) + batch_size - 1) // batch_size,
                        }
                    )

            else:
                # Fetch recent filings for all companies (more limited approach)
                logger.info(
                    "Backfilling all SEC filings",
                    start_date=start_date,
                    end_date=end_date,
                )

                # For broad backfill, fetch from SEC RSS feed historical data
                filings = await _fetch_bulk_filings(client, start, end, target_filing_types)

                for filing in filings:
                    try:
                        # Queue for processing
                        process_filing.delay(filing)
                        results["processed"] += 1
                    except Exception as e:
                        results["errors"].append(f"Failed to queue filing: {str(e)}")

                results["total_filings"] = len(filings)

        # Calculate duration
        end_time = datetime.now(timezone.utc)
        results["duration_seconds"] = (end_time - start_time).total_seconds()
        results["completed_at"] = end_time.isoformat()

        logger.info(
            "Backfill completed",
            total_filings=results["total_filings"],
            processed=results["processed"],
            duration=results["duration_seconds"],
            errors=len(results["errors"]),
        )

        return results

    try:
        return run_async(_backfill())
    except Exception as e:
        logger.error("Backfill task failed", error=str(e))
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


async def _fetch_ticker_filings(
    client,
    ticker: str,
    start_date: date,
    end_date: date,
    filing_types: list[str],
) -> dict[str, Any]:
    """Fetch filings for a single ticker and queue for processing.

    Args:
        client: SEC polling client
        ticker: Stock ticker symbol
        start_date: Start date
        end_date: End date
        filing_types: Filing types to include

    Returns:
        Results dictionary for this ticker
    """
    from backend.workers.tasks.scraping_tasks import process_filing

    result = {
        "ticker": ticker,
        "filings_count": 0,
        "processed": 0,
        "skipped": 0,
    }

    try:
        filings = await client.get_company_filings(
            ticker=ticker,
            filing_types=filing_types,
            start_date=start_date,
            end_date=end_date,
            limit=500,  # Max filings per ticker
        )

        result["filings_count"] = len(filings)

        for filing in filings:
            # Enrich with additional metadata for backfill
            filing["is_backfill"] = True
            filing["backfill_date"] = datetime.now(timezone.utc).isoformat()

            # Add title/headline from filing type
            filing_type = filing.get("filing_type", "")
            company_name = filing.get("company_name", ticker)
            filing["title"] = f"{company_name} ({ticker}) - Form {filing_type}"
            filing["headline"] = filing["title"]

            # Queue for NLP processing
            process_filing.delay(filing)
            result["processed"] += 1

        logger.debug(
            "Fetched ticker filings",
            ticker=ticker,
            count=len(filings),
        )

    except Exception as e:
        logger.error("Failed to fetch ticker filings", ticker=ticker, error=str(e))
        result["error"] = str(e)

    return result


async def _fetch_bulk_filings(
    client,
    start_date: date,
    end_date: date,
    filing_types: list[str],
) -> list[dict[str, Any]]:
    """Fetch bulk filings from SEC for a date range.

    This fetches filings across all companies for the given date range,
    useful for comprehensive backfill operations.

    Args:
        client: SEC polling client
        start_date: Start date
        end_date: End date
        filing_types: Filing types to include

    Returns:
        List of filing dictionaries
    """
    from backend.ingestion.sec_edgar import SECStreamingClient

    all_filings = []

    # Use streaming client to get recent filings by date
    async with SECStreamingClient(poll_interval=0) as stream_client:
        # SEC RSS only provides recent filings, so we may need multiple approaches
        filings = await stream_client.fetch_recent(count=1000)

        for filing in filings:
            # Parse filing date
            filing_date_str = filing.get("filing_time") or filing.get("published_at")
            if filing_date_str:
                try:
                    if isinstance(filing_date_str, str):
                        filing_dt = datetime.fromisoformat(
                            filing_date_str.replace("Z", "+00:00")
                        )
                    else:
                        filing_dt = filing_date_str
                    filing_date = filing_dt.date()

                    # Filter by date range
                    if start_date <= filing_date <= end_date:
                        filing_type = filing.get("filing_type", "")
                        if not filing_types or filing_type in filing_types:
                            filing["is_backfill"] = True
                            all_filings.append(filing)

                except (ValueError, TypeError):
                    pass

    logger.info("Fetched bulk filings", count=len(all_filings))
    return all_filings


@celery_app.task(bind=True, max_retries=2)
def backfill_ticker_history(
    self,
    ticker: str,
    days: int = 90,
    filing_types: list[str] | None = None,
) -> dict[str, Any]:
    """Backfill historical filings for a single ticker.

    Convenience task for backfilling a single ticker's history.

    Args:
        ticker: Stock ticker symbol
        days: Number of days to look back (default 90)
        filing_types: Optional list of filing types to include

    Returns:
        Backfill results for the ticker
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    return backfill_historical_data(
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        tickers=[ticker.upper()],
        filing_types=filing_types,
    )


@celery_app.task(bind=True, max_retries=2)
def backfill_watchlist_tickers(
    self,
    user_id: str,
    days: int = 30,
) -> dict[str, Any]:
    """Backfill historical data for all tickers in a user's watchlist.

    Args:
        user_id: User ID to fetch watchlist for
        days: Number of days to look back

    Returns:
        Backfill results
    """
    from backend.storage.timescale.connection import get_sync_db_context
    from sqlalchemy import text

    tickers = []

    with get_sync_db_context() as session:
        result = session.execute(
            text("SELECT tickers FROM watchlists WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        row = result.fetchone()
        if row and row[0]:
            tickers = row[0]

    if not tickers:
        return {
            "success": False,
            "error": "No tickers found in watchlist",
            "user_id": user_id,
        }

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    return backfill_historical_data(
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        tickers=tickers,
    )


@celery_app.task
def get_backfill_status(task_id: str) -> dict[str, Any]:
    """Get the status of a backfill task.

    Args:
        task_id: Celery task ID

    Returns:
        Task status information
    """
    from celery.result import AsyncResult

    result = AsyncResult(task_id, app=celery_app)

    status = {
        "task_id": task_id,
        "state": result.state,
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else None,
    }

    if result.state == "PROGRESS":
        status["progress"] = result.info
    elif result.ready():
        status["result"] = result.result if result.successful() else str(result.result)

    return status
