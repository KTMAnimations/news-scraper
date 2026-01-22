"""OpenSearch client for full-text search."""

from typing import Any

import structlog
from opensearchpy import AsyncOpenSearch, NotFoundError

from backend.config import settings

logger = structlog.get_logger(__name__)

# Event index mapping
EVENT_INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "ticker": {"type": "keyword"},
            "event_time": {"type": "date"},
            "ingest_time": {"type": "date"},
            "event_type": {"type": "keyword"},
            "event_category": {"type": "keyword"},
            "headline": {
                "type": "text",
                "analyzer": "english",
                "fields": {
                    "keyword": {"type": "keyword", "ignore_above": 512}
                }
            },
            "summary": {
                "type": "text",
                "analyzer": "english"
            },
            "content": {
                "type": "text",
                "analyzer": "english"
            },
            "source_url": {"type": "keyword"},
            "source_name": {"type": "keyword"},
            "sentiment_score": {"type": "float"},
            "sentiment_label": {"type": "keyword"},
            "alpha_score": {"type": "float"},
            "direction": {"type": "keyword"},
            "urgency_level": {"type": "keyword"},
            "extracted_tickers": {"type": "keyword"},
            "extracted_companies": {"type": "keyword"},
            "extracted_people": {"type": "keyword"},
        }
    },
    "settings": {
        "number_of_shards": 2,
        "number_of_replicas": 1,
        "analysis": {
            "analyzer": {
                "english": {
                    "type": "standard",
                    "stopwords": "_english_"
                }
            }
        }
    }
}


class OpenSearchClient:
    """Async OpenSearch client wrapper."""

    INDEX_NAME = "events"

    def __init__(self, url: str | None = None):
        """Initialize OpenSearch client.

        Args:
            url: OpenSearch URL (defaults to settings)
        """
        self.url = url or settings.opensearch_url
        self._client: AsyncOpenSearch | None = None

    async def _get_client(self) -> AsyncOpenSearch:
        """Get or create async client."""
        if self._client is None:
            self._client = AsyncOpenSearch(
                hosts=[self.url],
                http_compress=True,
                use_ssl=False,
                verify_certs=False,
                ssl_show_warn=False,
            )
        return self._client

    async def close(self) -> None:
        """Close the client connection."""
        if self._client:
            await self._client.close()
            self._client = None

    async def ensure_index(self) -> bool:
        """Ensure the events index exists.

        Returns:
            True if index exists or was created
        """
        client = await self._get_client()

        try:
            exists = await client.indices.exists(index=self.INDEX_NAME)
            if not exists:
                await client.indices.create(
                    index=self.INDEX_NAME,
                    body=EVENT_INDEX_MAPPING,
                )
                logger.info("Created OpenSearch index", index=self.INDEX_NAME)
            return True

        except Exception as e:
            logger.error("Failed to ensure index", error=str(e))
            return False

    async def index_event(self, event_data: dict[str, Any]) -> bool:
        """Index a single event.

        Args:
            event_data: Event data to index

        Returns:
            True if indexed successfully
        """
        client = await self._get_client()
        await self.ensure_index()

        try:
            event_id = event_data.get("id", "")
            await client.index(
                index=self.INDEX_NAME,
                id=event_id,
                body=event_data,
                refresh=True,
            )
            logger.debug("Indexed event", id=event_id)
            return True

        except Exception as e:
            logger.error("Failed to index event", error=str(e))
            return False

    async def bulk_index(self, events: list[dict[str, Any]]) -> int:
        """Bulk index multiple events.

        Args:
            events: List of event data

        Returns:
            Number of successfully indexed events
        """
        if not events:
            return 0

        client = await self._get_client()
        await self.ensure_index()

        # Build bulk request body
        bulk_body = []
        for event in events:
            event_id = event.get("id", "")
            bulk_body.append({"index": {"_index": self.INDEX_NAME, "_id": event_id}})
            bulk_body.append(event)

        try:
            response = await client.bulk(body=bulk_body, refresh=True)

            if response.get("errors"):
                error_count = sum(
                    1 for item in response.get("items", [])
                    if item.get("index", {}).get("error")
                )
                logger.warning("Bulk index had errors", errors=error_count)
                return len(events) - error_count

            return len(events)

        except Exception as e:
            logger.error("Bulk index failed", error=str(e))
            return 0

    async def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search events.

        Args:
            query: Search query text
            filters: Optional filters (ticker, event_type, etc.)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Search results with hits and total
        """
        client = await self._get_client()

        # Build search query
        must_clauses = []
        filter_clauses = []

        # Text search across headline, summary, content
        if query:
            must_clauses.append({
                "multi_match": {
                    "query": query,
                    "fields": [
                        "headline^3",  # Boost headline matches
                        "summary^2",
                        "content",
                        "extracted_companies",
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            })

        # Apply filters
        if filters:
            if filters.get("ticker"):
                filter_clauses.append({"term": {"ticker": filters["ticker"].upper()}})

            if filters.get("event_type"):
                filter_clauses.append({"term": {"event_type": filters["event_type"]}})

            if filters.get("direction"):
                filter_clauses.append({"term": {"direction": filters["direction"]}})

            if filters.get("urgency_level"):
                filter_clauses.append({"term": {"urgency_level": filters["urgency_level"]}})

            if filters.get("min_alpha"):
                filter_clauses.append({
                    "range": {"alpha_score": {"gte": filters["min_alpha"]}}
                })

            if filters.get("source_name"):
                filter_clauses.append({"term": {"source_name": filters["source_name"]}})

            if filters.get("start_time"):
                filter_clauses.append({
                    "range": {"event_time": {"gte": filters["start_time"]}}
                })

            if filters.get("end_time"):
                filter_clauses.append({
                    "range": {"event_time": {"lte": filters["end_time"]}}
                })

        # Build final query
        search_body = {
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
                    "headline": {},
                    "summary": {},
                },
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"],
            },
        }

        try:
            response = await client.search(
                index=self.INDEX_NAME,
                body=search_body,
            )

            hits = response.get("hits", {})
            total = hits.get("total", {}).get("value", 0)

            results = []
            for hit in hits.get("hits", []):
                source = hit.get("_source", {})
                source["_score"] = hit.get("_score")
                source["_highlights"] = hit.get("highlight", {})
                results.append(source)

            return {
                "results": results,
                "total": total,
                "query": query,
            }

        except Exception as e:
            logger.error("Search failed", query=query, error=str(e))
            return {"results": [], "total": 0, "query": query, "error": str(e)}

    async def suggest(
        self,
        prefix: str,
        field: str = "headline",
        limit: int = 10,
    ) -> list[str]:
        """Get autocomplete suggestions.

        Args:
            prefix: Text prefix to complete
            field: Field to suggest from
            limit: Maximum suggestions

        Returns:
            List of suggestions
        """
        client = await self._get_client()

        try:
            # Use prefix query for suggestions
            response = await client.search(
                index=self.INDEX_NAME,
                body={
                    "query": {
                        "prefix": {
                            f"{field}.keyword": {
                                "value": prefix,
                                "case_insensitive": True,
                            }
                        }
                    },
                    "size": limit,
                    "_source": [field],
                },
            )

            suggestions = []
            for hit in response.get("hits", {}).get("hits", []):
                value = hit.get("_source", {}).get(field)
                if value and value not in suggestions:
                    suggestions.append(value)

            return suggestions[:limit]

        except Exception as e:
            logger.error("Suggest failed", prefix=prefix, error=str(e))
            return []

    async def get_ticker_suggestions(
        self,
        prefix: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get ticker suggestions with metadata.

        Args:
            prefix: Ticker prefix
            limit: Maximum suggestions

        Returns:
            List of ticker suggestions with event counts
        """
        client = await self._get_client()

        try:
            response = await client.search(
                index=self.INDEX_NAME,
                body={
                    "query": {
                        "prefix": {
                            "ticker": {
                                "value": prefix.upper(),
                            }
                        }
                    },
                    "size": 0,
                    "aggs": {
                        "tickers": {
                            "terms": {
                                "field": "ticker",
                                "size": limit,
                            },
                            "aggs": {
                                "latest_event": {
                                    "top_hits": {
                                        "size": 1,
                                        "sort": [{"event_time": "desc"}],
                                        "_source": ["headline", "direction", "alpha_score"],
                                    }
                                }
                            }
                        }
                    }
                },
            )

            suggestions = []
            buckets = response.get("aggregations", {}).get("tickers", {}).get("buckets", [])

            for bucket in buckets:
                latest_hit = bucket.get("latest_event", {}).get("hits", {}).get("hits", [])
                latest_source = latest_hit[0].get("_source", {}) if latest_hit else {}

                suggestions.append({
                    "ticker": bucket["key"],
                    "event_count": bucket["doc_count"],
                    "latest_headline": latest_source.get("headline", ""),
                    "latest_direction": latest_source.get("direction"),
                    "latest_alpha": latest_source.get("alpha_score"),
                })

            return suggestions

        except Exception as e:
            logger.error("Ticker suggest failed", prefix=prefix, error=str(e))
            return []

    async def delete_event(self, event_id: str) -> bool:
        """Delete an event from the index.

        Args:
            event_id: Event ID to delete

        Returns:
            True if deleted successfully
        """
        client = await self._get_client()

        try:
            await client.delete(index=self.INDEX_NAME, id=event_id)
            return True
        except NotFoundError:
            return True  # Already deleted
        except Exception as e:
            logger.error("Delete failed", id=event_id, error=str(e))
            return False


# Global client instance
opensearch_client = OpenSearchClient()
