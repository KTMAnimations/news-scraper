"""OpenSearch integration module."""

from .client import OpenSearchClient
from .indexer import EventIndexer

__all__ = ["OpenSearchClient", "EventIndexer"]
