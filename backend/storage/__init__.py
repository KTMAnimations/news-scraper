"""Storage layer for data persistence."""

from backend.storage.timescale.connection import (
    Base,
    async_session_maker,
    get_db_context,
    get_db_session,
    get_sync_db_context,
    get_sync_db_session,
    init_db,
    sync_session_maker,
)
from backend.storage.timescale.models import Alert, Event, User, Watchlist
from backend.storage.timescale.queries import (
    AlertQueries,
    EventQueries,
    UserQueries,
    WatchlistQueries,
)
from backend.storage.opensearch.client import OpenSearchClient, opensearch_client

__all__ = [
    # Connection
    "Base",
    "async_session_maker",
    "get_db_session",
    "get_db_context",
    "init_db",
    # Models
    "Event",
    "User",
    "Watchlist",
    "Alert",
    # Queries
    "EventQueries",
    "UserQueries",
    "WatchlistQueries",
    "AlertQueries",
    # OpenSearch
    "OpenSearchClient",
    "opensearch_client",
]
