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

            # Start heartbeat monitoring for WebSocket connections
            await self.manager.start_heartbeat()

            logger.info("Event streamer started")

        except Exception as e:
            logger.error("Failed to start event streamer", error=str(e))

    async def stop(self) -> None:
        """Stop the event streamer."""
        self._running = False

        # Stop heartbeat monitoring
        await self.manager.stop_heartbeat()

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
        """Broadcast event to subscribers only (respects per-ticker subscriptions)."""
        ticker = event.get("ticker")
        await self.manager.broadcast_to_subscribers(ticker, {
            "type": "event",
            "data": event,
        })

    async def _broadcast_high_alpha(self, event: dict[str, Any]) -> None:
        """Broadcast high-alpha event to subscribers only."""
        ticker = event.get("ticker")
        await self.manager.broadcast_to_subscribers(ticker, {
            "type": "high_alpha",
            "data": event,
        })

    async def _broadcast_ticker_event(
        self,
        ticker: str,
        event: dict[str, Any],
    ) -> None:
        """Broadcast event to ticker subscribers."""
        await self.manager.broadcast_to_subscribers(ticker, {
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
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt
import uuid

router = APIRouter()


# WebSocket close codes
WS_CLOSE_NORMAL = 1000
WS_CLOSE_UNAUTHORIZED = 4001
WS_CLOSE_FORBIDDEN = 4003
WS_CLOSE_TOKEN_EXPIRED = 4004


async def validate_websocket_token(token: str | None) -> dict | None:
    """Validate JWT token for WebSocket authentication.

    Args:
        token: JWT access token

    Returns:
        Token payload if valid, None otherwise
    """
    if not token:
        return None

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        # Verify token type
        if payload.get("type") != "access":
            logger.warning("Invalid token type for WebSocket", token_type=payload.get("type"))
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("Expired token used for WebSocket authentication")
        return None
    except JWTError as e:
        logger.warning("Invalid token for WebSocket authentication", error=str(e))
        return None


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket, token: str | None = Query(default=None)):
    """WebSocket endpoint for all events.

    Optionally accepts a JWT token for authentication. If authenticated,
    the connection can access premium features.

    Query params:
        token: Optional JWT access token for authentication
    """
    connection_id = str(uuid.uuid4())
    user_id = None

    # Validate token if provided
    if token:
        payload = await validate_websocket_token(token)
        if payload:
            user_id = payload.get("sub")
            logger.info(
                "Authenticated WebSocket connection",
                connection_id=connection_id,
                user_id=user_id,
            )

    await manager.connect(websocket, connection_id, user_id=user_id)

    # Send welcome message with connection info
    await manager.send_personal(connection_id, {
        "type": "connected",
        "connection_id": connection_id,
        "authenticated": user_id is not None,
    })

    try:
        while True:
            # Handle incoming messages (subscriptions, etc.)
            data = await websocket.receive_json()
            await _handle_client_message(connection_id, data)

    except WebSocketDisconnect:
        await manager.disconnect(connection_id)


@router.websocket("/ws/events/authenticated")
async def websocket_events_authenticated(websocket: WebSocket, token: str = Query(...)):
    """WebSocket endpoint requiring authentication.

    This endpoint requires a valid JWT access token. Connections without
    a valid token will be immediately closed.

    Query params:
        token: JWT access token (required)
    """
    # Validate token
    payload = await validate_websocket_token(token)
    if not payload:
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return

    user_id = payload.get("sub")
    connection_id = str(uuid.uuid4())

    # Verify user exists and is active
    try:
        from backend.storage.timescale import get_db_session
        from backend.storage.timescale.queries import UserQueries

        async for session in get_db_session():
            queries = UserQueries(session)
            user = await queries.get_user_by_id(user_id)

            if not user:
                logger.warning("WebSocket auth: user not found", user_id=user_id)
                await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
                return

            if not user.is_active:
                logger.warning("WebSocket auth: user inactive", user_id=user_id)
                await websocket.close(code=WS_CLOSE_FORBIDDEN)
                return

            break

    except Exception as e:
        logger.error("WebSocket auth: database error", error=str(e))
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return

    await manager.connect(websocket, connection_id, user_id=user_id)

    # Send welcome message with user info
    await manager.send_personal(connection_id, {
        "type": "connected",
        "connection_id": connection_id,
        "authenticated": True,
        "user_id": user_id,
    })

    logger.info(
        "Authenticated WebSocket connected",
        connection_id=connection_id,
        user_id=user_id,
    )

    try:
        while True:
            data = await websocket.receive_json()
            await _handle_client_message(connection_id, data)

    except WebSocketDisconnect:
        await manager.disconnect(connection_id)


@router.websocket("/ws/events/watchlist")
async def websocket_watchlist(websocket: WebSocket, token: str = Query(...)):
    """WebSocket endpoint for watchlist events (authenticated).

    Automatically subscribes to all tickers in the user's watchlist.

    Query params:
        token: JWT access token (required)
    """
    # Validate token
    payload = await validate_websocket_token(token)
    if not payload:
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return

    user_id = payload.get("sub")
    connection_id = str(uuid.uuid4())
    await manager.connect(websocket, connection_id, user_id=user_id)

    # Subscribe to user's watchlist tickers from database
    try:
        from backend.storage.timescale import get_db_session
        from backend.storage.timescale.queries import WatchlistQueries

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
                "connection_id": connection_id,
                "authenticated": True,
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
async def websocket_ticker(
    websocket: WebSocket,
    ticker: str,
    token: str | None = Query(default=None),
):
    """WebSocket endpoint for single ticker events.

    Automatically subscribes to the specified ticker. Optionally accepts
    authentication for premium features.

    Path params:
        ticker: Ticker symbol to subscribe to

    Query params:
        token: Optional JWT access token for authentication
    """
    connection_id = str(uuid.uuid4())
    user_id = None

    # Validate token if provided
    if token:
        payload = await validate_websocket_token(token)
        if payload:
            user_id = payload.get("sub")

    await manager.connect(websocket, connection_id, user_id=user_id)
    await manager.subscribe(connection_id, ticker)

    # Send welcome message
    await manager.send_personal(connection_id, {
        "type": "connected",
        "connection_id": connection_id,
        "authenticated": user_id is not None,
        "subscribed_ticker": ticker.upper(),
    })

    try:
        while True:
            data = await websocket.receive_json()
            await _handle_client_message(connection_id, data)

    except WebSocketDisconnect:
        await manager.disconnect(connection_id)


@router.websocket("/ws/events/high-alpha")
async def websocket_high_alpha(
    websocket: WebSocket,
    token: str | None = Query(default=None),
):
    """WebSocket endpoint for high-alpha events only.

    Subscribes to the wildcard to receive all high-alpha events.
    Optionally accepts authentication for premium features.

    Query params:
        token: Optional JWT access token for authentication
    """
    connection_id = str(uuid.uuid4())
    user_id = None

    # Validate token if provided
    if token:
        payload = await validate_websocket_token(token)
        if payload:
            user_id = payload.get("sub")

    await manager.connect(websocket, connection_id, user_id=user_id)

    # Subscribe to wildcard for all high-alpha events
    await manager.subscribe(connection_id, "*")

    # Send welcome message
    await manager.send_personal(connection_id, {
        "type": "connected",
        "connection_id": connection_id,
        "authenticated": user_id is not None,
        "subscription_type": "high_alpha",
    })

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

    Supported messages:
    - {"action": "subscribe", "tickers": ["AAPL", "TSLA"]} - Subscribe to multiple tickers
    - {"action": "subscribe", "ticker": "AAPL"} - Subscribe to single ticker (legacy)
    - {"action": "unsubscribe", "tickers": ["AAPL"]} - Unsubscribe from multiple tickers
    - {"action": "unsubscribe", "ticker": "AAPL"} - Unsubscribe from single ticker (legacy)
    - {"action": "subscribe", "tickers": ["*"]} - Subscribe to all events (wildcard)
    - {"type": "pong"} - Heartbeat response
    - {"action": "ping"} - Client-initiated ping (legacy)
    - {"action": "list_subscriptions"} - List current subscriptions

    Args:
        connection_id: Client connection ID
        data: Message data
    """
    action = data.get("action")
    message_type = data.get("type")

    # Handle pong response (heartbeat)
    if message_type == "pong" or action == "pong":
        await manager.handle_pong(connection_id)
        return

    if action == "subscribe":
        # Support both array format and single ticker format
        tickers = data.get("tickers", [])
        single_ticker = data.get("ticker")

        if single_ticker and not tickers:
            tickers = [single_ticker]

        if tickers:
            subscribed = await manager.subscribe_many(connection_id, tickers)
            await manager.send_personal(connection_id, {
                "type": "subscribed",
                "tickers": subscribed,
            })
            logger.info(
                "Client subscribed to tickers",
                connection_id=connection_id,
                tickers=subscribed,
            )

    elif action == "unsubscribe":
        # Support both array format and single ticker format
        tickers = data.get("tickers", [])
        single_ticker = data.get("ticker")

        if single_ticker and not tickers:
            tickers = [single_ticker]

        if tickers:
            unsubscribed = await manager.unsubscribe_many(connection_id, tickers)
            await manager.send_personal(connection_id, {
                "type": "unsubscribed",
                "tickers": unsubscribed,
            })
            logger.info(
                "Client unsubscribed from tickers",
                connection_id=connection_id,
                tickers=unsubscribed,
            )

    elif action == "ping":
        # Legacy client-initiated ping
        await manager.send_personal(connection_id, {"type": "pong"})

    elif action == "list_subscriptions":
        subscriptions = manager.get_subscriptions(connection_id)
        await manager.send_personal(connection_id, {
            "type": "subscriptions",
            "tickers": list(subscriptions),
        })
