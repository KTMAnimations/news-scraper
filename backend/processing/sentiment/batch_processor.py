"""Batch sentiment processing for efficiency."""

import asyncio
from dataclasses import dataclass
from typing import Any

import structlog

from .finbert_service import FinBERTService, SentimentResult, SimpleSentimentService

logger = structlog.get_logger(__name__)


@dataclass
class BatchItem:
    """Item in a sentiment batch."""

    id: str
    text: str
    result: SentimentResult | None = None


class SentimentBatchProcessor:
    """Batch processor for efficient sentiment analysis."""

    def __init__(
        self,
        service: FinBERTService | SimpleSentimentService | None = None,
        batch_size: int = 16,
        max_wait_ms: int = 100,
    ):
        """Initialize batch processor.

        Args:
            service: Sentiment service to use
            batch_size: Maximum batch size
            max_wait_ms: Maximum wait time in ms before processing partial batch
        """
        if service is None:
            from .finbert_service import get_sentiment_service
            service = get_sentiment_service()

        self.service = service
        self.batch_size = batch_size
        self.max_wait_ms = max_wait_ms
        self._queue: asyncio.Queue[BatchItem] = asyncio.Queue()
        self._results: dict[str, asyncio.Future] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        self._stats = {
            "total_processed": 0,
            "batches_processed": 0,
            "avg_batch_size": 0.0,
        }

    async def start(self) -> None:
        """Start the batch processor."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("Sentiment batch processor started")

    async def stop(self) -> None:
        """Stop the batch processor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Sentiment batch processor stopped")

    async def analyze(self, text: str, item_id: str | None = None) -> SentimentResult:
        """Analyze text sentiment (queued for batching).

        Args:
            text: Text to analyze
            item_id: Optional unique ID for this item

        Returns:
            SentimentResult
        """
        if not self._running:
            # Process synchronously if batch processor not running
            return self.service.analyze(text)

        import uuid

        item_id = item_id or str(uuid.uuid4())

        # Create future for result
        future: asyncio.Future[SentimentResult] = asyncio.get_event_loop().create_future()
        self._results[item_id] = future

        # Add to queue
        item = BatchItem(id=item_id, text=text)
        await self._queue.put(item)

        # Wait for result
        result = await future
        del self._results[item_id]

        return result

    async def analyze_many(self, texts: list[str]) -> list[SentimentResult]:
        """Analyze multiple texts.

        Args:
            texts: List of texts

        Returns:
            List of SentimentResults
        """
        if not self._running or len(texts) <= 1:
            # Process directly for small batches
            if isinstance(self.service, FinBERTService):
                return self.service.analyze_batch(texts)
            return [self.service.analyze(t) for t in texts]

        # Queue all items
        import uuid

        futures = []
        for text in texts:
            item_id = str(uuid.uuid4())
            future: asyncio.Future[SentimentResult] = asyncio.get_event_loop().create_future()
            self._results[item_id] = future
            futures.append((item_id, future))

            item = BatchItem(id=item_id, text=text)
            await self._queue.put(item)

        # Wait for all results
        results = []
        for item_id, future in futures:
            result = await future
            results.append(result)
            del self._results[item_id]

        return results

    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                batch = await self._collect_batch()

                if batch:
                    await self._process_batch(batch)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Batch processing error", error=str(e))
                await asyncio.sleep(1)

    async def _collect_batch(self) -> list[BatchItem]:
        """Collect items into a batch.

        Returns:
            List of batch items
        """
        batch = []

        # Wait for first item
        try:
            item = await asyncio.wait_for(
                self._queue.get(),
                timeout=self.max_wait_ms / 1000,
            )
            batch.append(item)
        except asyncio.TimeoutError:
            return []

        # Try to fill batch
        deadline = asyncio.get_event_loop().time() + (self.max_wait_ms / 1000)

        while len(batch) < self.batch_size:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break

            try:
                item = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=remaining,
                )
                batch.append(item)
            except asyncio.TimeoutError:
                break

        return batch

    async def _process_batch(self, batch: list[BatchItem]) -> None:
        """Process a batch of items.

        Args:
            batch: List of batch items
        """
        texts = [item.text for item in batch]

        try:
            # Process batch
            if isinstance(self.service, FinBERTService):
                results = self.service.analyze_batch(texts)
            else:
                results = [self.service.analyze(t) for t in texts]

            # Update stats
            self._stats["total_processed"] += len(batch)
            self._stats["batches_processed"] += 1
            self._stats["avg_batch_size"] = (
                self._stats["total_processed"] / self._stats["batches_processed"]
            )

            # Set results
            for item, result in zip(batch, results):
                if item.id in self._results:
                    self._results[item.id].set_result(result)

        except Exception as e:
            logger.error("Batch processing failed", error=str(e), batch_size=len(batch))

            # Set error on all futures
            for item in batch:
                if item.id in self._results:
                    # Return neutral sentiment on error
                    error_result = SentimentResult(
                        label="neutral",
                        score=0.0,
                        confidence=0.0,
                        probabilities={"positive": 0.33, "negative": 0.33, "neutral": 0.34},
                    )
                    self._results[item.id].set_result(error_result)

    def get_stats(self) -> dict[str, Any]:
        """Get processing statistics.

        Returns:
            Stats dictionary
        """
        return {
            **self._stats,
            "queue_size": self._queue.qsize(),
            "pending_results": len(self._results),
            "running": self._running,
        }


# Global batch processor instance
_processor: SentimentBatchProcessor | None = None


async def get_batch_processor() -> SentimentBatchProcessor:
    """Get or create global batch processor."""
    global _processor
    if _processor is None:
        _processor = SentimentBatchProcessor()
        await _processor.start()
    return _processor
