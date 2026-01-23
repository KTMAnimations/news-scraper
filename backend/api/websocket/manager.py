"""WebSocket connection manager."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket
import structlog

logger = structlog.get_logger(__name__)

# Heartbeat configuration
HEARTBEAT_INTERVAL = 30  # seconds between pings
HEARTBEAT_TIMEOUT = 10  # seconds to wait for pong response

# Wildcard subscription constant
WILDCARD_SUBSCRIPTION = "*"


@dataclass
class Connection:
    """WebSocket connection with metadata."""

    websocket: WebSocket
    user_id: str | None = None
    subscriptions: set[str] = field(default_factory=set)
    is_authenticated: bool = False
    last_pong: float = field(default_factory=time.time)
    pending_ping: bool = False


class ConnectionManager:
    """Manages WebSocket connections and message distribution."""

    def __init__(self):
        """Initialize connection manager."""
        self._connections: dict[str, Connection] = {}
        self._ticker_subscriptions: dict[str, set[str]] = {}  # ticker -> connection_ids
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

    async def start_heartbeat(self) -> None:
        """Start the heartbeat task to monitor connection health."""
        if self._running:
            return

        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Heartbeat monitoring started")

    async def stop_heartbeat(self) -> None:
        """Stop the heartbeat task."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        logger.info("Heartbeat monitoring stopped")

    async def _heartbeat_loop(self) -> None:
        """Send periodic pings and check for stale connections."""
        while self._running:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await self._check_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in heartbeat loop", error=str(e))

    async def _check_connections(self) -> None:
        """Check all connections and disconnect stale ones."""
        current_time = time.time()
        stale_connections: list[str] = []

        async with self._lock:
            for conn_id, connection in list(self._connections.items()):
                # Check if previous ping timed out
                if connection.pending_ping:
                    time_since_pong = current_time - connection.last_pong
                    if time_since_pong > HEARTBEAT_INTERVAL + HEARTBEAT_TIMEOUT:
                        stale_connections.append(conn_id)
                        logger.warning(
                            "Connection stale - no pong received",
                            connection_id=conn_id,
                            seconds_since_pong=time_since_pong,
                        )
                        continue

                # Send new ping
                try:
                    await connection.websocket.send_json({
                        "type": "ping",
                        "timestamp": current_time,
                    })
                    connection.pending_ping = True
                except Exception as e:
                    logger.warning(
                        "Failed to send ping",
                        connection_id=conn_id,
                        error=str(e),
                    )
                    stale_connections.append(conn_id)

        # Disconnect stale connections outside the lock
        for conn_id in stale_connections:
            await self.disconnect(conn_id)
            logger.info("Disconnected stale connection", connection_id=conn_id)

    async def handle_pong(self, connection_id: str) -> None:
        """Handle pong response from client.

        Args:
            connection_id: Connection that sent the pong
        """
        async with self._lock:
            if connection_id in self._connections:
                self._connections[connection_id].last_pong = time.time()
                self._connections[connection_id].pending_ping = False
                logger.debug("Received pong", connection_id=connection_id)

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
            last_pong=time.time(),
            pending_ping=False,
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
            ticker: Ticker to subscribe to (use "*" for all events)

        Returns:
            True if subscribed
        """
        async with self._lock:
            if connection_id not in self._connections:
                return False

            # Handle wildcard subscription
            if ticker == WILDCARD_SUBSCRIPTION:
                self._connections[connection_id].subscriptions.add(WILDCARD_SUBSCRIPTION)
                if WILDCARD_SUBSCRIPTION not in self._ticker_subscriptions:
                    self._ticker_subscriptions[WILDCARD_SUBSCRIPTION] = set()
                self._ticker_subscriptions[WILDCARD_SUBSCRIPTION].add(connection_id)
            else:
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

    async def subscribe_many(self, connection_id: str, tickers: list[str]) -> list[str]:
        """Subscribe connection to multiple tickers.

        Args:
            connection_id: Connection to subscribe
            tickers: List of tickers to subscribe to (use "*" for all events)

        Returns:
            List of successfully subscribed tickers
        """
        subscribed = []
        for ticker in tickers:
            if await self.subscribe(connection_id, ticker):
                subscribed.append(ticker.upper() if ticker != WILDCARD_SUBSCRIPTION else ticker)
        return subscribed

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

            # Handle wildcard unsubscription
            if ticker == WILDCARD_SUBSCRIPTION:
                self._connections[connection_id].subscriptions.discard(WILDCARD_SUBSCRIPTION)
                if WILDCARD_SUBSCRIPTION in self._ticker_subscriptions:
                    self._ticker_subscriptions[WILDCARD_SUBSCRIPTION].discard(connection_id)
            else:
                ticker = ticker.upper()
                self._connections[connection_id].subscriptions.discard(ticker)

                if ticker in self._ticker_subscriptions:
                    self._ticker_subscriptions[ticker].discard(connection_id)

        return True

    async def unsubscribe_many(self, connection_id: str, tickers: list[str]) -> list[str]:
        """Unsubscribe connection from multiple tickers.

        Args:
            connection_id: Connection to unsubscribe
            tickers: List of tickers to unsubscribe from

        Returns:
            List of successfully unsubscribed tickers
        """
        unsubscribed = []
        for ticker in tickers:
            if await self.unsubscribe(connection_id, ticker):
                unsubscribed.append(ticker.upper() if ticker != WILDCARD_SUBSCRIPTION else ticker)
        return unsubscribed

    def get_subscriptions(self, connection_id: str) -> set[str]:
        """Get current subscriptions for a connection.

        Args:
            connection_id: Connection to get subscriptions for

        Returns:
            Set of subscribed tickers
        """
        if connection_id in self._connections:
            return self._connections[connection_id].subscriptions.copy()
        return set()

    def is_subscribed_to(self, connection_id: str, ticker: str) -> bool:
        """Check if connection is subscribed to a specific ticker.

        Args:
            connection_id: Connection to check
            ticker: Ticker to check subscription for

        Returns:
            True if subscribed (either directly or via wildcard)
        """
        if connection_id not in self._connections:
            return False

        subscriptions = self._connections[connection_id].subscriptions

        # Wildcard subscribers receive all events
        if WILDCARD_SUBSCRIPTION in subscriptions:
            return True

        return ticker.upper() in subscriptions

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
        """Broadcast message to all connections (regardless of subscriptions).

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
        """Broadcast message to ticker subscribers only (including wildcard subscribers).

        Args:
            ticker: Target ticker
            message: Message to broadcast

        Returns:
            Number of connections sent to
        """
        ticker = ticker.upper()
        sent = 0
        sent_connections: set[str] = set()

        # Send to specific ticker subscribers
        if ticker in self._ticker_subscriptions:
            for connection_id in list(self._ticker_subscriptions[ticker]):
                if connection_id not in sent_connections:
                    if await self.send_personal(connection_id, message):
                        sent += 1
                        sent_connections.add(connection_id)

        # Also send to wildcard subscribers
        if WILDCARD_SUBSCRIPTION in self._ticker_subscriptions:
            for connection_id in list(self._ticker_subscriptions[WILDCARD_SUBSCRIPTION]):
                if connection_id not in sent_connections:
                    if await self.send_personal(connection_id, message):
                        sent += 1
                        sent_connections.add(connection_id)

        return sent

    async def broadcast_to_subscribers(
        self,
        ticker: str | None,
        message: dict[str, Any],
    ) -> int:
        """Broadcast message only to connections subscribed to the ticker.

        This method respects per-ticker subscriptions:
        - Only sends to connections subscribed to the specific ticker
        - Also sends to wildcard (*) subscribers
        - Does NOT broadcast to all connections

        Args:
            ticker: Target ticker (if None, only wildcard subscribers receive)
            message: Message to broadcast

        Returns:
            Number of connections sent to
        """
        sent = 0
        sent_connections: set[str] = set()

        # Send to specific ticker subscribers
        if ticker:
            ticker = ticker.upper()
            if ticker in self._ticker_subscriptions:
                for connection_id in list(self._ticker_subscriptions[ticker]):
                    if connection_id not in sent_connections:
                        if await self.send_personal(connection_id, message):
                            sent += 1
                            sent_connections.add(connection_id)

        # Also send to wildcard subscribers
        if WILDCARD_SUBSCRIPTION in self._ticker_subscriptions:
            for connection_id in list(self._ticker_subscriptions[WILDCARD_SUBSCRIPTION]):
                if connection_id not in sent_connections:
                    if await self.send_personal(connection_id, message):
                        sent += 1
                        sent_connections.add(connection_id)

        return sent

    async def broadcast_event(self, event: dict[str, Any]) -> int:
        """Broadcast an event to relevant subscribers only.

        Only sends to:
        - Connections subscribed to the event's ticker
        - Connections subscribed to wildcard (*)

        Args:
            event: Event data

        Returns:
            Number of connections sent to
        """
        message = {
            "type": "event",
            "data": event,
        }

        ticker = event.get("ticker")
        return await self.broadcast_to_subscribers(ticker, message)

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
