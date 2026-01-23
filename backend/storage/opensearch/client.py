"""OpenSearch client for full-text search and event indexing."""

from datetime import datetime
from typing import Any

import structlog
from opensearchpy import NotFoundError, OpenSearch

from backend.config import settings

logger = structlog.get_logger(__name__)


class OpenSearchClient:
    """OpenSearch client for event search and indexing.

    Note: Uses synchronous OpenSearch client wrapped in async methods
    since the async client has compatibility issues.
    """

    INDEX_NAME = "events"
    INDEX_SETTINGS = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "headline_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "asciifolding", "porter_stem"],
                    },
                    "ticker_analyzer": {
                        "type": "custom",
                        "tokenizer": "keyword",
                        "filter": ["uppercase"],
                    },
                }
            },
        },
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "ticker": {"type": "keyword", "normalizer": "uppercase"},
                "headline": {
                    "type": "text",
                    "analyzer": "headline_analyzer",
                    "fields": {
                        "keyword": {"type": "keyword"},
                        "suggest": {
                            "type": "completion",
                            "analyzer": "simple",
                        },
                    },
                },
                "summary": {"type": "text", "analyzer": "headline_analyzer"},
                "content": {"type": "text"},
                "event_type": {"type": "keyword"},
                "event_category": {"type": "keyword"},
                "event_time": {"type": "date"},
                "ingest_time": {"type": "date"},
                "source_name": {"type": "keyword"},
                "source_url": {"type": "keyword"},
                "sentiment_score": {"type": "float"},
                "sentiment_label": {"type": "keyword"},
                "alpha_score": {"type": "float"},
                "direction": {"type": "keyword"},
                "urgency_level": {"type": "keyword"},
                "extracted_tickers": {"type": "keyword"},
                "extracted_companies": {"type": "text"},
                "extracted_people": {"type": "text"},
            }
        },
    }

    def __init__(self, url: str | None = None):
        """Initialize OpenSearch client.

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

    async def close(self) -> None:
        """Close the client connection."""
        if self._client:
            self._client.close()
            self._client = None

    async def init_index(self) -> bool:
        """Initialize the events index if it doesn't exist.

        Returns:
            True if index was created, False if it already existed
        """
        try:
            client = self._get_client()
            exists = client.indices.exists(index=self.INDEX_NAME)

            if not exists:
                client.indices.create(
                    index=self.INDEX_NAME,
                    body=self.INDEX_SETTINGS,
                )
                logger.info("Created OpenSearch index", index=self.INDEX_NAME)
                return True

            logger.debug("OpenSearch index already exists", index=self.INDEX_NAME)
            return False

        except Exception as e:
            logger.error("Failed to initialize OpenSearch index", error=str(e))
            return False

    async def index_event(self, event_data: dict[str, Any]) -> bool:
        """Index a single event.

        Args:
            event_data: Event data to index

        Returns:
            True if successful
        """
        try:
            client = self._get_client()

            doc = {
                "id": str(event_data.get("id", "")),
                "ticker": event_data.get("ticker"),
                "headline": event_data.get("headline", ""),
                "summary": event_data.get("summary"),
                "content": event_data.get("content"),
                "event_type": event_data.get("event_type"),
                "event_category": event_data.get("event_category"),
                "event_time": event_data.get("event_time"),
                "ingest_time": event_data.get("ingest_time") or datetime.utcnow().isoformat(),
                "source_name": event_data.get("source_name"),
                "source_url": event_data.get("source_url"),
                "sentiment_score": event_data.get("sentiment_score"),
                "sentiment_label": event_data.get("sentiment_label"),
                "alpha_score": event_data.get("alpha_score"),
                "direction": event_data.get("direction"),
                "urgency_level": event_data.get("urgency_level"),
                "extracted_tickers": event_data.get("extracted_tickers", []),
                "extracted_companies": event_data.get("extracted_companies", []),
                "extracted_people": event_data.get("extracted_people", []),
            }

            client.index(
                index=self.INDEX_NAME,
                id=doc["id"],
                body=doc,
                refresh=True,
            )

            logger.debug("Indexed event", event_id=doc["id"], ticker=doc["ticker"])
            return True

        except Exception as e:
            logger.error("Failed to index event", error=str(e), event_id=event_data.get("id"))
            return False

    async def bulk_index(self, events: list[dict[str, Any]]) -> dict[str, int]:
        """Bulk index multiple events.

        Args:
            events: List of event data dictionaries

        Returns:
            Dict with success and failure counts
        """
        if not events:
            return {"success": 0, "failed": 0}

        try:
            client = self._get_client()

            actions = []
            for event in events:
                actions.append({"index": {"_index": self.INDEX_NAME, "_id": str(event.get("id", ""))}})
                actions.append({
                    "id": str(event.get("id", "")),
                    "ticker": event.get("ticker"),
                    "headline": event.get("headline", ""),
                    "summary": event.get("summary"),
                    "content": event.get("content"),
                    "event_type": event.get("event_type"),
                    "event_category": event.get("event_category"),
                    "event_time": event.get("event_time"),
                    "ingest_time": event.get("ingest_time") or datetime.utcnow().isoformat(),
                    "source_name": event.get("source_name"),
                    "source_url": event.get("source_url"),
                    "sentiment_score": event.get("sentiment_score"),
                    "sentiment_label": event.get("sentiment_label"),
                    "alpha_score": event.get("alpha_score"),
                    "direction": event.get("direction"),
                    "urgency_level": event.get("urgency_level"),
                    "extracted_tickers": event.get("extracted_tickers", []),
                    "extracted_companies": event.get("extracted_companies", []),
                    "extracted_people": event.get("extracted_people", []),
                })

            response = client.bulk(body=actions, refresh=True)

            success = sum(1 for item in response.get("items", []) if item.get("index", {}).get("status") in (200, 201))
            failed = len(events) - success

            logger.info("Bulk indexed events", success=success, failed=failed)
            return {"success": success, "failed": failed}

        except Exception as e:
            logger.error("Bulk indexing failed", error=str(e))
            return {"success": 0, "failed": len(events)}

    async def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Full-text search for events.

        Args:
            query: Search query string
            filters: Optional filters (ticker, event_type, direction, min_alpha)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Search results with total count
        """
        try:
            client = self._get_client()

            must_clauses = [
                {
                    "multi_match": {
                        "query": query,
                        "fields": ["headline^3", "summary^2", "content", "extracted_companies"],
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                    }
                }
            ]

            filter_clauses = []
            if filters:
                if filters.get("ticker"):
                    filter_clauses.append({"term": {"ticker": filters["ticker"].upper()}})
                if filters.get("event_type"):
                    filter_clauses.append({"term": {"event_type": filters["event_type"]}})
                if filters.get("direction"):
                    filter_clauses.append({"term": {"direction": filters["direction"]}})
                if filters.get("min_alpha") is not None:
                    filter_clauses.append({"range": {"alpha_score": {"gte": filters["min_alpha"]}}})

            body = {
                "query": {
                    "bool": {
                        "must": must_clauses,
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
                    }
                },
            }

            response = client.search(index=self.INDEX_NAME, body=body)

            results = []
            for hit in response.get("hits", {}).get("hits", []):
                source = hit.get("_source", {})
                source["_score"] = hit.get("_score")
                source["_highlights"] = hit.get("highlight", {})
                results.append(source)

            return {
                "results": results,
                "total": response.get("hits", {}).get("total", {}).get("value", 0),
            }

        except Exception as e:
            logger.error("Search failed", error=str(e), query=query)
            return {"error": str(e), "results": [], "total": 0}

    async def suggest(
        self,
        prefix: str,
        field: str = "headline",
        limit: int = 10,
    ) -> list[str]:
        """Get autocomplete suggestions.

        Args:
            prefix: Search prefix
            field: Field to get suggestions from
            limit: Maximum suggestions

        Returns:
            List of suggestion strings
        """
        try:
            client = self._get_client()

            body = {
                "suggest": {
                    "headline-suggest": {
                        "prefix": prefix,
                        "completion": {
                            "field": f"{field}.suggest",
                            "size": limit,
                            "skip_duplicates": True,
                        }
                    }
                }
            }

            response = client.search(index=self.INDEX_NAME, body=body)

            suggestions = []
            for option in response.get("suggest", {}).get("headline-suggest", [{}])[0].get("options", []):
                suggestions.append(option.get("text", ""))

            return suggestions

        except Exception as e:
            logger.error("Suggest failed", error=str(e), prefix=prefix)
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
        try:
            client = self._get_client()

            body = {
                "size": 0,
                "query": {
                    "prefix": {
                        "ticker": prefix.upper()
                    }
                },
                "aggs": {
                    "tickers": {
                        "terms": {
                            "field": "ticker",
                            "size": limit,
                            "order": {"_count": "desc"},
                        },
                        "aggs": {
                            "latest": {
                                "top_hits": {
                                    "size": 1,
                                    "sort": [{"event_time": "desc"}],
                                    "_source": ["headline", "direction", "alpha_score"],
                                }
                            }
                        }
                    }
                }
            }

            response = client.search(index=self.INDEX_NAME, body=body)

            suggestions = []
            for bucket in response.get("aggregations", {}).get("tickers", {}).get("buckets", []):
                latest_hit = bucket.get("latest", {}).get("hits", {}).get("hits", [{}])[0].get("_source", {})
                suggestions.append({
                    "ticker": bucket.get("key"),
                    "event_count": bucket.get("doc_count", 0),
                    "latest_headline": latest_hit.get("headline"),
                    "latest_direction": latest_hit.get("direction"),
                    "latest_alpha": latest_hit.get("alpha_score"),
                })

            return suggestions

        except Exception as e:
            logger.error("Ticker suggestions failed", error=str(e), prefix=prefix)
            return []

    async def delete_event(self, event_id: str) -> bool:
        """Delete an event from the index.

        Args:
            event_id: Event ID to delete

        Returns:
            True if successful
        """
        try:
            client = self._get_client()
            client.delete(index=self.INDEX_NAME, id=event_id)
            return True
        except NotFoundError:
            return True  # Already deleted
        except Exception as e:
            logger.error("Delete event failed", error=str(e), event_id=event_id)
            return False

    async def delete_old_events(self, days: int = 90) -> int:
        """Delete events older than specified days.

        Args:
            days: Number of days to keep

        Returns:
            Number of deleted documents
        """
        try:
            client = self._get_client()

            body = {
                "query": {
                    "range": {
                        "event_time": {
                            "lt": f"now-{days}d"
                        }
                    }
                }
            }

            response = client.delete_by_query(index=self.INDEX_NAME, body=body)
            deleted = response.get("deleted", 0)

            logger.info("Deleted old events", deleted=deleted, days=days)
            return deleted

        except Exception as e:
            logger.error("Delete old events failed", error=str(e))
            return 0


# Global client instance
opensearch_client = OpenSearchClient()
