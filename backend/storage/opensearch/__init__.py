"""OpenSearch storage module."""

from backend.storage.opensearch.client import OpenSearchClient, opensearch_client
from backend.storage.opensearch.search_service import SearchService, search_service

__all__ = [
    "OpenSearchClient",
    "opensearch_client",
    "SearchService",
    "search_service",
]
