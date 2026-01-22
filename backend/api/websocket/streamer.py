"""WebSocket event streamer with Redis pub/sub."""

import asyncio
import json
from typing import Any

import structlog

from backend.config import settings
from .manager import ConnectionManager, manager

logger = structlog.get_logger(__name__)


class EventStreamer:
    """Streams events to WebSocket clients via Redis pub/sub."""

    # Redis channels
    CHANNEL_ALL_EVENTS = "events:all"
    CHANNEL_HIGH_ALPHA = "events:high_alpha"
    CHANNEL_TICKER_PREFIX = "events:ticker:"

    def __init__(self, connection_manager: ConnectionManager | None = None):
        """Initialize event streamer.

        Args:
            connection_manager: WebSocket connection manager
        """
        self.manager = connection_manager or manager
        self._running = False
        self._redis = None
        self._pubsub = None

    async def start(self) -> None:
        """Start the event streamer."""
        if self._running:
            return

        try:
            import redis.asyncio as redis

            self._redis = redis.from_url(str(settings.redis_url))
            self._pubsub = self._redis.pubsub()

            # Subscribe to channels
            await self._pubsub.subscribe(
                self.CHANNEL_ALL_EVENTS,
                self.CHANNEL_HIGH_ALPHA,
            )

            self._running = True
            asyncio.create_task(self._listen())

            logger.info("Event streamer started")

        except Exception as e:
            logger.error("Failed to start event streamer", error=str(e))

    async def stop(self) -> None:
        """Stop the event streamer."""
        self._running = False

        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()

        if self._redis:
            await self._redis.close()

        logger.info("Event streamer stopped")

    async def _listen(self) -> None:
        """Listen for Redis pub/sub messages."""
        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )

                if message and message["type"] == "message":
                    await self._handle_message(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in event listener", error=str(e))
                await asyncio.sleep(1)

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """Handle incoming pub/sub message.

        Args:
            message: Redis pub/sub message
        """
        try:
            channel = message["channel"]
            if isinstance(channel, bytes):
                channel = channel.decode("utf-8")

            data = message["data"]
            if isinstance(data, bytes):
                data = json.loads(data.decode("utf-8"))
            elif isinstance(data, str):
                data = json.loads(data)

            # Route to appropriate handler
            if channel == self.CHANNEL_ALL_EVENTS:
                await self._broadcast_event(data)
            elif channel == self.CHANNEL_HIGH_ALPHA:
                await self._broadcast_high_alpha(data)
            elif channel.startswith(self.CHANNEL_TICKER_PREFIX):
                ticker = channel[len(self.CHANNEL_TICKER_PREFIX):]
                await self._broadcast_ticker_event(ticker, data)

        except Exception as e:
            logger.error("Failed to handle message", error=str(e))

    async def _broadcast_event(self, event: dict[str, Any]) -> None:
        """Broadcast event to all connections."""
        await self.manager.broadcast({
            "type": "event",
            "data": event,
        })

    async def _broadcast_high_alpha(self, event: dict[str, Any]) -> None:
        """Broadcast high-alpha event."""
        await self.manager.broadcast({
            "type": "high_alpha",
            "data": event,
        })

    async def _broadcast_ticker_event(
        self,
        ticker: str,
        event: dict[str, Any],
    ) -> None:
        """Broadcast event to ticker subscribers."""
        await self.manager.broadcast_to_ticker(ticker, {
            "type": "ticker_event",
            "ticker": ticker,
            "data": event,
        })

    async def publish_event(self, event: dict[str, Any]) -> None:
        """Publish event to Redis pub/sub.

        Args:
            event: Event data to publish
        """
        if not self._redis:
            return

        try:
            event_json = json.dumps(event)

            # Publish to all events channel
            await self._redis.publish(self.CHANNEL_ALL_EVENTS, event_json)

            # Publish to ticker channel if applicable
            ticker = event.get("ticker")
            if ticker:
                await self._redis.publish(
                    f"{self.CHANNEL_TICKER_PREFIX}{ticker.upper()}",
                    event_json,
                )

            # Publish to high alpha channel if applicable
            alpha_score = event.get("alpha_score", 0)
            if alpha_score and abs(alpha_score) >= 0.5:
                await self._redis.publish(self.CHANNEL_HIGH_ALPHA, event_json)

        except Exception as e:
            logger.error("Failed to publish event", error=str(e))


# FastAPI WebSocket endpoint
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
import uuid

router = APIRouter()


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """WebSocket endpoint for all events."""
    connection_id = str(uuid.uuid4())

    await manager.connect(websocket, connection_id)

    try:
        while True:
            # Handle incoming messages (subscriptions, etc.)
            data = await websocket.receive_json()
            await _handle_client_message(connection_id, data)

    except WebSocketDisconnect:
        await manager.disconnect(connection_id)


@router.websocket("/ws/events/watchlist")
async def websocket_watchlist(websocket: WebSocket, token: str):
    """WebSocket endpoint for watchlist events (authenticated)."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001)
            return
    except JWTError:
        await websocket.close(code=4001)
        return

    connection_id = str(uuid.uuid4())
    await manager.connect(websocket, connection_id, user_id=user_id)

    # Subscribe to user's watchlist tickers from database
    try:
        from backend.storage.timescale import get_db_session, WatchlistQueries

        async for session in get_db_session():
            queries = WatchlistQueries(session)
            watchlist_items = await queries.get_user_watchlist(user_id)

            for item in watchlist_items:
                await manager.subscribe(connection_id, item.ticker)
                logger.info(
                    "Subscribed to watchlist ticker",
                    connection_id=connection_id,
                    ticker=item.ticker,
                )

            # Send confirmation with subscribed tickers
            await manager.send_personal(connection_id, {
                "type": "watchlist_loaded",
                "tickers": [item.ticker for item in watchlist_items],
            })
            break  # Only need one session

    except Exception as e:
        logger.error("Failed to load watchlist", error=str(e))
        await manager.send_personal(connection_id, {
            "type": "error",
            "message": "Failed to load watchlist subscriptions",
        })

    try:
        while True:
            data = await websocket.receive_json()
            await _handle_client_message(connection_id, data)

    except WebSocketDisconnect:
        await manager.disconnect(connection_id)


@router.websocket("/ws/events/ticker/{ticker}")
async def websocket_ticker(websocket: WebSocket, ticker: str):
    """WebSocket endpoint for single ticker events."""
    connection_id = str(uuid.uuid4())

    await manager.connect(websocket, connection_id)
    await manager.subscribe(connection_id, ticker)

    try:
        while True:
            data = await websocket.receive_json()
            await _handle_client_message(connection_id, data)

    except WebSocketDisconnect:
        await manager.disconnect(connection_id)


@router.websocket("/ws/events/high-alpha")
async def websocket_high_alpha(websocket: WebSocket):
    """WebSocket endpoint for high-alpha events only."""
    connection_id = str(uuid.uuid4())

    await manager.connect(websocket, connection_id)

    # This connection only receives high-alpha broadcasts
    # Implementation would filter in _handle_client_message

    try:
        while True:
            data = await websocket.receive_json()
            await _handle_client_message(connection_id, data)

    except WebSocketDisconnect:
        await manager.disconnect(connection_id)


async def _handle_client_message(
    connection_id: str,
    data: dict[str, Any],
) -> None:
    """Handle message from WebSocket client.

    Args:
        connection_id: Client connection ID
        data: Message data
    """
    action = data.get("action")

    if action == "subscribe":
        ticker = data.get("ticker")
        if ticker:
            await manager.subscribe(connection_id, ticker)
            await manager.send_personal(connection_id, {
                "type": "subscribed",
                "ticker": ticker,
            })

    elif action == "unsubscribe":
        ticker = data.get("ticker")
        if ticker:
            await manager.unsubscribe(connection_id, ticker)
            await manager.send_personal(connection_id, {
                "type": "unsubscribed",
                "ticker": ticker,
            })

    elif action == "ping":
        await manager.send_personal(connection_id, {"type": "pong"})
