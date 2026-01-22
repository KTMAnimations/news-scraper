"""Event indexer for OpenSearch."""

from datetime import datetime, timezone
from typing import Any

import structlog

from .client import opensearch_client

logger = structlog.get_logger(__name__)


class EventIndexer:
    """Handles indexing events to OpenSearch."""

    def __init__(self):
        """Initialize event indexer."""
        self.client = opensearch_client
        self._pending_events: list[dict[str, Any]] = []
        self._batch_size = 100

    def prepare_event(self, event_data: dict[str, Any]) -> dict[str, Any]:
        """Prepare event data for indexing.

        Args:
            event_data: Raw event data

        Returns:
            Prepared event for indexing
        """
        # Normalize and clean data
        prepared = {
            "id": str(event_data.get("id", "")),
            "ticker": event_data.get("ticker", "").upper() if event_data.get("ticker") else None,
            "event_time": event_data.get("event_time"),
            "ingest_time": event_data.get("ingest_time") or datetime.now(timezone.utc).isoformat(),
            "event_type": event_data.get("event_type"),
            "event_category": event_data.get("event_category"),
            "headline": event_data.get("headline") or event_data.get("title"),
            "summary": event_data.get("summary"),
            "content": event_data.get("content", "")[:10000] if event_data.get("content") else None,
            "source_url": event_data.get("source_url") or event_data.get("url"),
            "source_name": event_data.get("source_name") or event_data.get("source"),
            "sentiment_score": event_data.get("sentiment_score"),
            "sentiment_label": event_data.get("sentiment_label"),
            "alpha_score": event_data.get("alpha_score"),
            "direction": event_data.get("direction"),
            "urgency_level": event_data.get("urgency_level"),
            "extracted_tickers": event_data.get("extracted_tickers", []),
            "extracted_companies": event_data.get("extracted_companies", []),
            "extracted_people": event_data.get("extracted_people", []),
        }

        # Remove None values
        return {k: v for k, v in prepared.items() if v is not None}

    async def index_event(self, event_data: dict[str, Any]) -> bool:
        """Index a single event.

        Args:
            event_data: Event data to index

        Returns:
            True if indexed successfully
        """
        prepared = self.prepare_event(event_data)
        return await self.client.index_event(prepared)

    async def queue_event(self, event_data: dict[str, Any]) -> None:
        """Queue event for batch indexing.

        Args:
            event_data: Event data to queue
        """
        prepared = self.prepare_event(event_data)
        self._pending_events.append(prepared)

        if len(self._pending_events) >= self._batch_size:
            await self.flush()

    async def flush(self) -> int:
        """Flush queued events to OpenSearch.

        Returns:
            Number of events indexed
        """
        if not self._pending_events:
            return 0

        events_to_index = self._pending_events[:]
        self._pending_events = []

        count = await self.client.bulk_index(events_to_index)
        logger.info("Flushed events to OpenSearch", count=count)

        return count

    async def reindex_from_database(
        self,
        session,
        batch_size: int = 500,
    ) -> int:
        """Reindex all events from database.

        Args:
            session: Database session
            batch_size: Batch size for processing

        Returns:
            Total events indexed
        """
        from sqlalchemy import select
        from backend.storage.timescale.models import Event

        total_indexed = 0
        offset = 0

        while True:
            result = await session.execute(
                select(Event)
                .order_by(Event.event_time.desc())
                .offset(offset)
                .limit(batch_size)
            )
            events = list(result.scalars().all())

            if not events:
                break

            # Prepare events for indexing
            prepared_events = [
                self.prepare_event(event.to_dict())
                for event in events
            ]

            # Bulk index
            indexed = await self.client.bulk_index(prepared_events)
            total_indexed += indexed

            logger.info(
                "Reindexing progress",
                offset=offset,
                batch_indexed=indexed,
                total_indexed=total_indexed,
            )

            offset += batch_size

            # Allow some breathing room
            if offset % 2000 == 0:
                import asyncio
                await asyncio.sleep(0.1)

        return total_indexed


# Global indexer instance
event_indexer = EventIndexer()
