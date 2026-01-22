"""WebSocket connection manager."""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Connection:
    """WebSocket connection with metadata."""

    websocket: WebSocket
    user_id: str | None = None
    subscriptions: set[str] = field(default_factory=set)
    is_authenticated: bool = False


class ConnectionManager:
    """Manages WebSocket connections and message distribution."""

    def __init__(self):
        """Initialize connection manager."""
        self._connections: dict[str, Connection] = {}
        self._ticker_subscriptions: dict[str, set[str]] = {}  # ticker -> connection_ids
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        connection_id: str,
        user_id: str | None = None,
    ) -> Connection:
        """Accept and register a new connection.

        Args:
            websocket: WebSocket connection
            connection_id: Unique connection identifier
            user_id: Optional authenticated user ID

        Returns:
            Connection object
        """
        await websocket.accept()

        connection = Connection(
            websocket=websocket,
            user_id=user_id,
            is_authenticated=user_id is not None,
        )

        async with self._lock:
            self._connections[connection_id] = connection

        logger.info(
            "WebSocket connected",
            connection_id=connection_id,
            user_id=user_id,
        )

        return connection

    async def disconnect(self, connection_id: str) -> None:
        """Remove a connection.

        Args:
            connection_id: Connection to remove
        """
        async with self._lock:
            if connection_id in self._connections:
                connection = self._connections[connection_id]

                # Remove from ticker subscriptions
                for ticker in connection.subscriptions:
                    if ticker in self._ticker_subscriptions:
                        self._ticker_subscriptions[ticker].discard(connection_id)

                del self._connections[connection_id]

        logger.info("WebSocket disconnected", connection_id=connection_id)

    async def subscribe(self, connection_id: str, ticker: str) -> bool:
        """Subscribe connection to a ticker.

        Args:
            connection_id: Connection to subscribe
            ticker: Ticker to subscribe to

        Returns:
            True if subscribed
        """
        async with self._lock:
            if connection_id not in self._connections:
                return False

            ticker = ticker.upper()
            self._connections[connection_id].subscriptions.add(ticker)

            if ticker not in self._ticker_subscriptions:
                self._ticker_subscriptions[ticker] = set()

            self._ticker_subscriptions[ticker].add(connection_id)

        logger.debug(
            "Subscribed to ticker",
            connection_id=connection_id,
            ticker=ticker,
        )

        return True

    async def unsubscribe(self, connection_id: str, ticker: str) -> bool:
        """Unsubscribe connection from a ticker.

        Args:
            connection_id: Connection to unsubscribe
            ticker: Ticker to unsubscribe from

        Returns:
            True if unsubscribed
        """
        async with self._lock:
            if connection_id not in self._connections:
                return False

            ticker = ticker.upper()
            self._connections[connection_id].subscriptions.discard(ticker)

            if ticker in self._ticker_subscriptions:
                self._ticker_subscriptions[ticker].discard(connection_id)

        return True

    async def send_personal(
        self,
        connection_id: str,
        message: dict[str, Any],
    ) -> bool:
        """Send message to specific connection.

        Args:
            connection_id: Target connection
            message: Message to send

        Returns:
            True if sent
        """
        if connection_id not in self._connections:
            return False

        try:
            websocket = self._connections[connection_id].websocket
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.warning(
                "Failed to send message",
                connection_id=connection_id,
                error=str(e),
            )
            return False

    async def broadcast(self, message: dict[str, Any]) -> int:
        """Broadcast message to all connections.

        Args:
            message: Message to broadcast

        Returns:
            Number of connections sent to
        """
        sent = 0

        for connection_id in list(self._connections.keys()):
            if await self.send_personal(connection_id, message):
                sent += 1

        return sent

    async def broadcast_to_ticker(
        self,
        ticker: str,
        message: dict[str, Any],
    ) -> int:
        """Broadcast message to ticker subscribers.

        Args:
            ticker: Target ticker
            message: Message to broadcast

        Returns:
            Number of connections sent to
        """
        ticker = ticker.upper()
        sent = 0

        if ticker not in self._ticker_subscriptions:
            return 0

        for connection_id in list(self._ticker_subscriptions[ticker]):
            if await self.send_personal(connection_id, message):
                sent += 1

        return sent

    async def broadcast_event(self, event: dict[str, Any]) -> int:
        """Broadcast an event to relevant subscribers.

        Args:
            event: Event data

        Returns:
            Number of connections sent to
        """
        message = {
            "type": "event",
            "data": event,
        }

        sent = 0

        # Send to all connections first (for "all events" subscribers)
        sent += await self.broadcast(message)

        # Send to specific ticker subscribers
        ticker = event.get("ticker")
        if ticker:
            # These may be duplicates but most clients will dedupe
            sent += await self.broadcast_to_ticker(ticker, message)

        return sent

    def get_connection_count(self) -> int:
        """Get number of active connections."""
        return len(self._connections)

    def get_ticker_subscriber_count(self, ticker: str) -> int:
        """Get number of subscribers for a ticker."""
        return len(self._ticker_subscriptions.get(ticker.upper(), set()))

    def get_stats(self) -> dict[str, Any]:
        """Get connection statistics."""
        return {
            "total_connections": len(self._connections),
            "authenticated_connections": sum(
                1 for c in self._connections.values() if c.is_authenticated
            ),
            "ticker_subscriptions": {
                ticker: len(subs)
                for ticker, subs in self._ticker_subscriptions.items()
            },
        }


# Global connection manager instance
manager = ConnectionManager()
