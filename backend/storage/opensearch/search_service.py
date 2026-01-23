"""Search service for OpenSearch event indexing and querying.

Provides a clean interface for indexing, searching, and deleting events
from the OpenSearch index.
"""

from datetime import datetime
from typing import Any

import structlog
from opensearchpy import NotFoundError, OpenSearch

from backend.config import settings

logger = structlog.get_logger(__name__)


class SearchService:
    """Service class for OpenSearch event operations.

    Provides methods for:
    - index_event: Index a single event
    - search_events: Full-text search with filters
    - delete_event: Delete an event by ID
    """

    INDEX_NAME = "events"

    # Index mappings matching the required schema
    INDEX_MAPPINGS = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "normalizer": {
                    "uppercase": {
                        "type": "custom",
                        "filter": ["uppercase"],
                    }
                }
            },
        },
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "ticker": {"type": "keyword", "normalizer": "uppercase"},
                "headline": {
                    "type": "text",
                    "analyzer": "english",
                    "fields": {
                        "keyword": {"type": "keyword"},
                    },
                },
                "summary": {"type": "text"},
                "content": {"type": "text"},
                "event_type": {"type": "keyword"},
                "source_name": {"type": "keyword"},
                "sentiment_label": {"type": "keyword"},
                "alpha_score": {"type": "float"},
                "event_time": {"type": "date"},
            }
        },
    }

    def __init__(self, url: str | None = None):
        """Initialize search service.

        Args:
            url: OpenSearch URL. Defaults to settings.opensearch_url
        """
        self.url = url or settings.opensearch_url
        self._client: OpenSearch | None = None

    def _get_client(self) -> OpenSearch:
        """Get or create OpenSearch client."""
        if self._client is None:
            self._client = OpenSearch(
                hosts=[self.url],
                use_ssl=self.url.startswith("https"),
                verify_certs=False,
                ssl_show_warn=False,
            )
        return self._client

    def close(self) -> None:
        """Close the client connection."""
        if self._client:
            self._client.close()
            self._client = None

    def ensure_index(self) -> bool:
        """Ensure the events index exists with proper mappings.

        Returns:
            True if index was created, False if it already existed
        """
        try:
            client = self._get_client()
            exists = client.indices.exists(index=self.INDEX_NAME)

            if not exists:
                client.indices.create(
                    index=self.INDEX_NAME,
                    body=self.INDEX_MAPPINGS,
                )
                logger.info("Created events index", index=self.INDEX_NAME)
                return True

            logger.debug("Events index already exists", index=self.INDEX_NAME)
            return False

        except Exception as e:
            logger.error("Failed to ensure index exists", error=str(e))
            raise

    def index_event(self, event_data: dict[str, Any]) -> bool:
        """Index a single event document.

        Args:
            event_data: Event data containing:
                - id: Unique event identifier
                - ticker: Stock ticker symbol
                - headline: Event headline (text with english analyzer)
                - summary: Event summary (text)
                - content: Full event content (text)
                - event_type: Type of event (keyword)
                - source_name: Source name (keyword)
                - sentiment_label: Sentiment classification (keyword)
                - alpha_score: Alpha score (float)
                - event_time: Event timestamp (date)

        Returns:
            True if indexing was successful

        Raises:
            Exception: If indexing fails
        """
        try:
            client = self._get_client()

            # Prepare document for indexing
            doc = {
                "id": str(event_data.get("id", "")),
                "ticker": event_data.get("ticker"),
                "headline": event_data.get("headline", ""),
                "summary": event_data.get("summary"),
                "content": event_data.get("content"),
                "event_type": event_data.get("event_type"),
                "source_name": event_data.get("source_name"),
                "sentiment_label": event_data.get("sentiment_label"),
                "alpha_score": event_data.get("alpha_score"),
                "event_time": self._format_datetime(event_data.get("event_time")),
            }

            # Remove None values
            doc = {k: v for k, v in doc.items() if v is not None}

            client.index(
                index=self.INDEX_NAME,
                id=doc.get("id"),
                body=doc,
                refresh=True,
            )

            logger.debug(
                "Indexed event",
                event_id=doc.get("id"),
                ticker=doc.get("ticker"),
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to index event",
                error=str(e),
                event_id=event_data.get("id"),
            )
            raise

    def search_events(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search events using full-text search with optional filters.

        Args:
            query: Search query string for full-text search
            filters: Optional filters:
                - ticker: Filter by ticker symbol
                - event_type: Filter by event type
                - source_name: Filter by source name
                - sentiment_label: Filter by sentiment
                - min_alpha: Minimum alpha score
                - max_alpha: Maximum alpha score
                - start_date: Events after this date
                - end_date: Events before this date
            limit: Maximum number of results (default 50)
            offset: Pagination offset (default 0)

        Returns:
            Dictionary containing:
                - results: List of matching events
                - total: Total number of matches
                - query: Original search query
        """
        try:
            client = self._get_client()

            # Build query
            must_clauses = []
            filter_clauses = []

            # Full-text search across headline, summary, and content
            if query:
                must_clauses.append({
                    "multi_match": {
                        "query": query,
                        "fields": ["headline^3", "summary^2", "content"],
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                    }
                })

            # Apply filters
            if filters:
                if filters.get("ticker"):
                    filter_clauses.append({
                        "term": {"ticker": filters["ticker"].upper()}
                    })

                if filters.get("event_type"):
                    filter_clauses.append({
                        "term": {"event_type": filters["event_type"]}
                    })

                if filters.get("source_name"):
                    filter_clauses.append({
                        "term": {"source_name": filters["source_name"]}
                    })

                if filters.get("sentiment_label"):
                    filter_clauses.append({
                        "term": {"sentiment_label": filters["sentiment_label"]}
                    })

                # Alpha score range filter
                alpha_range = {}
                if filters.get("min_alpha") is not None:
                    alpha_range["gte"] = filters["min_alpha"]
                if filters.get("max_alpha") is not None:
                    alpha_range["lte"] = filters["max_alpha"]
                if alpha_range:
                    filter_clauses.append({
                        "range": {"alpha_score": alpha_range}
                    })

                # Date range filter
                date_range = {}
                if filters.get("start_date"):
                    date_range["gte"] = self._format_datetime(filters["start_date"])
                if filters.get("end_date"):
                    date_range["lte"] = self._format_datetime(filters["end_date"])
                if date_range:
                    filter_clauses.append({
                        "range": {"event_time": date_range}
                    })

            # Build the final query
            query_body = {
                "query": {
                    "bool": {
                        "must": must_clauses if must_clauses else [{"match_all": {}}],
                        "filter": filter_clauses,
                    }
                },
                "sort": [
                    {"_score": "desc"},
                    {"event_time": "desc"},
                ],
                "from": offset,
                "size": limit,
                "highlight": {
                    "fields": {
                        "headline": {"number_of_fragments": 0},
                        "summary": {"number_of_fragments": 2},
                        "content": {"number_of_fragments": 3},
                    }
                },
            }

            response = client.search(index=self.INDEX_NAME, body=query_body)

            # Process results
            results = []
            for hit in response.get("hits", {}).get("hits", []):
                source = hit.get("_source", {})
                source["_score"] = hit.get("_score")
                source["_highlights"] = hit.get("highlight", {})
                results.append(source)

            total = response.get("hits", {}).get("total", {})
            if isinstance(total, dict):
                total = total.get("value", 0)

            logger.debug(
                "Search completed",
                query=query,
                total=total,
                returned=len(results),
            )

            return {
                "results": results,
                "total": total,
                "query": query,
            }

        except Exception as e:
            logger.error("Search failed", error=str(e), query=query)
            return {
                "results": [],
                "total": 0,
                "query": query,
                "error": str(e),
            }

    def delete_event(self, event_id: str) -> bool:
        """Delete an event from the index.

        Args:
            event_id: ID of the event to delete

        Returns:
            True if deletion was successful or event didn't exist
        """
        try:
            client = self._get_client()
            client.delete(
                index=self.INDEX_NAME,
                id=event_id,
                refresh=True,
            )
            logger.debug("Deleted event", event_id=event_id)
            return True

        except NotFoundError:
            logger.debug("Event not found for deletion", event_id=event_id)
            return True  # Already deleted

        except Exception as e:
            logger.error("Failed to delete event", error=str(e), event_id=event_id)
            raise

    def bulk_index(self, events: list[dict[str, Any]]) -> dict[str, int]:
        """Bulk index multiple events.

        Args:
            events: List of event data dictionaries

        Returns:
            Dictionary with success and failed counts
        """
        if not events:
            return {"success": 0, "failed": 0}

        try:
            client = self._get_client()

            actions = []
            for event in events:
                doc = {
                    "id": str(event.get("id", "")),
                    "ticker": event.get("ticker"),
                    "headline": event.get("headline", ""),
                    "summary": event.get("summary"),
                    "content": event.get("content"),
                    "event_type": event.get("event_type"),
                    "source_name": event.get("source_name"),
                    "sentiment_label": event.get("sentiment_label"),
                    "alpha_score": event.get("alpha_score"),
                    "event_time": self._format_datetime(event.get("event_time")),
                }

                # Remove None values
                doc = {k: v for k, v in doc.items() if v is not None}

                actions.append({
                    "index": {"_index": self.INDEX_NAME, "_id": doc.get("id")}
                })
                actions.append(doc)

            response = client.bulk(body=actions, refresh=True)

            success = sum(
                1 for item in response.get("items", [])
                if item.get("index", {}).get("status") in (200, 201)
            )
            failed = len(events) - success

            logger.info("Bulk indexed events", success=success, failed=failed)
            return {"success": success, "failed": failed}

        except Exception as e:
            logger.error("Bulk indexing failed", error=str(e))
            return {"success": 0, "failed": len(events)}

    def _format_datetime(self, dt_value: Any) -> str | None:
        """Format datetime value for OpenSearch.

        Args:
            dt_value: Datetime value (datetime, string, or None)

        Returns:
            ISO formatted string or None
        """
        if dt_value is None:
            return None

        if isinstance(dt_value, datetime):
            return dt_value.isoformat()

        if isinstance(dt_value, str):
            return dt_value

        return None


# Global service instance
search_service = SearchService()
