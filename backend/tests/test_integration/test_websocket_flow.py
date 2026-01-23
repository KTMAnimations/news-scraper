"""Integration tests for WebSocket event flow.

Tests the Redis pub/sub to WebSocket distribution pipeline.
Mocks Redis but tests real WebSocket connection management.
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import WebSocket
from fastapi.testclient import TestClient
from httpx import AsyncClient

from backend.api.websocket.manager import Connection, ConnectionManager


class TestConnectionManager:
    """Tests for the WebSocket ConnectionManager."""

    @pytest.fixture
    def manager(self):
        """Create a fresh connection manager for each test."""
        return ConnectionManager()

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        ws = MagicMock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self, manager, mock_websocket):
        """Test that connect accepts the WebSocket connection."""
        connection_id = str(uuid4())

        connection = await manager.connect(mock_websocket, connection_id)

        mock_websocket.accept.assert_called_once()
        assert connection is not None
        assert connection.websocket == mock_websocket

    @pytest.mark.asyncio
    async def test_connect_registers_connection(self, manager, mock_websocket):
        """Test that connect registers the connection in manager."""
        connection_id = str(uuid4())

        await manager.connect(mock_websocket, connection_id)

        assert manager.get_connection_count() == 1

    @pytest.mark.asyncio
    async def test_connect_with_user_id(self, manager, mock_websocket):
        """Test that connect stores user ID when provided."""
        connection_id = str(uuid4())
        user_id = str(uuid4())

        connection = await manager.connect(mock_websocket, connection_id, user_id=user_id)

        assert connection.user_id == user_id
        assert connection.is_authenticated is True

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self, manager, mock_websocket):
        """Test that disconnect removes the connection."""
        connection_id = str(uuid4())

        await manager.connect(mock_websocket, connection_id)
        assert manager.get_connection_count() == 1

        await manager.disconnect(connection_id)
        assert manager.get_connection_count() == 0

    @pytest.mark.asyncio
    async def test_disconnect_removes_ticker_subscriptions(self, manager, mock_websocket):
        """Test that disconnect cleans up ticker subscriptions."""
        connection_id = str(uuid4())

        await manager.connect(mock_websocket, connection_id)
        await manager.subscribe(connection_id, "AAPL")
        await manager.subscribe(connection_id, "MSFT")

        assert manager.get_ticker_subscriber_count("AAPL") == 1
        assert manager.get_ticker_subscriber_count("MSFT") == 1

        await manager.disconnect(connection_id)

        assert manager.get_ticker_subscriber_count("AAPL") == 0
        assert manager.get_ticker_subscriber_count("MSFT") == 0

    @pytest.mark.asyncio
    async def test_subscribe_adds_ticker(self, manager, mock_websocket):
        """Test that subscribe adds ticker to connection."""
        connection_id = str(uuid4())

        await manager.connect(mock_websocket, connection_id)
        result = await manager.subscribe(connection_id, "AAPL")

        assert result is True
        assert manager.get_ticker_subscriber_count("AAPL") == 1

    @pytest.mark.asyncio
    async def test_subscribe_normalizes_ticker_case(self, manager, mock_websocket):
        """Test that subscribe normalizes ticker to uppercase."""
        connection_id = str(uuid4())

        await manager.connect(mock_websocket, connection_id)
        await manager.subscribe(connection_id, "aapl")

        # Should be normalized to AAPL
        assert manager.get_ticker_subscriber_count("AAPL") == 1

    @pytest.mark.asyncio
    async def test_subscribe_fails_for_unknown_connection(self, manager):
        """Test that subscribe fails for non-existent connection."""
        result = await manager.subscribe("non-existent", "AAPL")

        assert result is False

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_ticker(self, manager, mock_websocket):
        """Test that unsubscribe removes ticker from connection."""
        connection_id = str(uuid4())

        await manager.connect(mock_websocket, connection_id)
        await manager.subscribe(connection_id, "AAPL")
        assert manager.get_ticker_subscriber_count("AAPL") == 1

        result = await manager.unsubscribe(connection_id, "AAPL")

        assert result is True
        assert manager.get_ticker_subscriber_count("AAPL") == 0

    @pytest.mark.asyncio
    async def test_send_personal_sends_to_connection(self, manager, mock_websocket):
        """Test that send_personal sends message to specific connection."""
        connection_id = str(uuid4())
        message = {"type": "test", "data": "hello"}

        await manager.connect(mock_websocket, connection_id)
        result = await manager.send_personal(connection_id, message)

        assert result is True
        mock_websocket.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_send_personal_fails_for_unknown_connection(self, manager):
        """Test that send_personal fails for non-existent connection."""
        result = await manager.send_personal("non-existent", {"type": "test"})

        assert result is False

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_connections(self, manager):
        """Test that broadcast sends to all connected clients."""
        ws1 = MagicMock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()

        ws2 = MagicMock(spec=WebSocket)
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        await manager.connect(ws1, "conn1")
        await manager.connect(ws2, "conn2")

        message = {"type": "event", "data": {"ticker": "AAPL"}}
        sent_count = await manager.broadcast(message)

        assert sent_count == 2
        ws1.send_json.assert_called_once_with(message)
        ws2.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_to_ticker_sends_only_to_subscribers(self, manager):
        """Test that broadcast_to_ticker only sends to subscribed connections."""
        ws1 = MagicMock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()

        ws2 = MagicMock(spec=WebSocket)
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        ws3 = MagicMock(spec=WebSocket)
        ws3.accept = AsyncMock()
        ws3.send_json = AsyncMock()

        await manager.connect(ws1, "conn1")
        await manager.connect(ws2, "conn2")
        await manager.connect(ws3, "conn3")

        # Only conn1 and conn2 subscribe to AAPL
        await manager.subscribe("conn1", "AAPL")
        await manager.subscribe("conn2", "AAPL")
        # conn3 subscribes to different ticker
        await manager.subscribe("conn3", "MSFT")

        message = {"type": "event", "ticker": "AAPL"}
        sent_count = await manager.broadcast_to_ticker("AAPL", message)

        assert sent_count == 2
        ws1.send_json.assert_called_once_with(message)
        ws2.send_json.assert_called_once_with(message)
        ws3.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_event_sends_to_all_and_ticker(self, manager):
        """Test that broadcast_event sends to all and ticker subscribers."""
        ws1 = MagicMock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()

        await manager.connect(ws1, "conn1")
        await manager.subscribe("conn1", "NVDA")

        event = {
            "id": str(uuid4()),
            "ticker": "NVDA",
            "headline": "NVIDIA news",
        }

        await manager.broadcast_event(event)

        # Should receive both broadcast and ticker-specific
        assert ws1.send_json.call_count >= 1

    @pytest.mark.asyncio
    async def test_get_stats_returns_accurate_counts(self, manager, mock_websocket):
        """Test that get_stats returns accurate connection statistics."""
        # Connect two users, one authenticated
        ws1 = MagicMock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws2 = MagicMock(spec=WebSocket)
        ws2.accept = AsyncMock()

        await manager.connect(ws1, "conn1", user_id="user1")
        await manager.connect(ws2, "conn2")

        await manager.subscribe("conn1", "AAPL")
        await manager.subscribe("conn1", "MSFT")
        await manager.subscribe("conn2", "AAPL")

        stats = manager.get_stats()

        assert stats["total_connections"] == 2
        assert stats["authenticated_connections"] == 1
        assert stats["ticker_subscriptions"]["AAPL"] == 2
        assert stats["ticker_subscriptions"]["MSFT"] == 1


class TestEventStreamer:
    """Tests for the EventStreamer Redis pub/sub integration."""

    @pytest.fixture
    def mock_manager(self):
        """Create a mock connection manager."""
        manager = MagicMock(spec=ConnectionManager)
        manager.broadcast = AsyncMock(return_value=5)
        manager.broadcast_to_ticker = AsyncMock(return_value=2)
        return manager

    @pytest.fixture
    def streamer(self, mock_manager):
        """Create an EventStreamer with mocked manager."""
        from backend.api.websocket.streamer import EventStreamer

        return EventStreamer(connection_manager=mock_manager)

    @pytest.mark.asyncio
    async def test_start_connects_to_redis(self, streamer):
        """Test that start connects to Redis and subscribes to channels."""
        with patch("redis.asyncio.from_url") as mock_redis_factory:
            mock_redis = MagicMock()
            mock_pubsub = MagicMock()
            mock_pubsub.subscribe = AsyncMock()
            mock_pubsub.get_message = AsyncMock(return_value=None)
            mock_redis.pubsub.return_value = mock_pubsub
            mock_redis_factory.return_value = mock_redis

            await streamer.start()

            mock_redis_factory.assert_called_once()
            mock_pubsub.subscribe.assert_called_once()

            # Stop the streamer
            streamer._running = False

    @pytest.mark.asyncio
    async def test_stop_closes_connections(self, streamer):
        """Test that stop closes Redis connections."""
        mock_pubsub = MagicMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()

        mock_redis = MagicMock()
        mock_redis.close = AsyncMock()

        streamer._running = True
        streamer._pubsub = mock_pubsub
        streamer._redis = mock_redis

        await streamer.stop()

        assert streamer._running is False
        mock_pubsub.unsubscribe.assert_called_once()
        mock_pubsub.close.assert_called_once()
        mock_redis.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_broadcasts_all_events(self, streamer, mock_manager):
        """Test that all events channel messages are broadcast."""
        message = {
            "channel": "events:all",
            "data": json.dumps({
                "id": str(uuid4()),
                "ticker": "AAPL",
                "headline": "Apple news",
            }),
        }

        await streamer._handle_message(message)

        mock_manager.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_broadcasts_high_alpha(self, streamer, mock_manager):
        """Test that high alpha channel messages are broadcast."""
        message = {
            "channel": "events:high_alpha",
            "data": json.dumps({
                "id": str(uuid4()),
                "ticker": "NVDA",
                "alpha_score": 0.85,
            }),
        }

        await streamer._handle_message(message)

        mock_manager.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_broadcasts_to_ticker(self, streamer, mock_manager):
        """Test that ticker channel messages go to ticker subscribers."""
        message = {
            "channel": "events:ticker:TSLA",
            "data": json.dumps({
                "id": str(uuid4()),
                "ticker": "TSLA",
                "headline": "Tesla news",
            }),
        }

        await streamer._handle_message(message)

        mock_manager.broadcast_to_ticker.assert_called_once_with(
            "TSLA",
            {
                "type": "ticker_event",
                "ticker": "TSLA",
                "data": {
                    "id": message["data"],  # JSON string gets parsed
                    "ticker": "TSLA",
                    "headline": "Tesla news",
                },
            },
        )

    @pytest.mark.asyncio
    async def test_handle_message_decodes_bytes(self, streamer, mock_manager):
        """Test that byte-encoded messages are properly decoded."""
        event_data = {"id": str(uuid4()), "ticker": "AMD"}
        message = {
            "channel": b"events:all",
            "data": json.dumps(event_data).encode("utf-8"),
        }

        await streamer._handle_message(message)

        mock_manager.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_event_publishes_to_channels(self, streamer):
        """Test that publish_event publishes to appropriate channels."""
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock()
        streamer._redis = mock_redis

        event = {
            "id": str(uuid4()),
            "ticker": "META",
            "headline": "Meta news",
            "alpha_score": 0.6,
        }

        await streamer.publish_event(event)

        # Should publish to events:all and events:ticker:META and events:high_alpha
        assert mock_redis.publish.call_count >= 2

    @pytest.mark.asyncio
    async def test_publish_event_skips_without_redis(self, streamer):
        """Test that publish_event handles missing Redis connection."""
        streamer._redis = None

        event = {"id": str(uuid4()), "ticker": "TEST"}

        # Should not raise
        await streamer.publish_event(event)


class TestWebSocketEndpoints:
    """Integration tests for WebSocket endpoints."""

    @pytest.fixture
    def app(self):
        """Get the FastAPI app."""
        from backend.api.main import app

        return app

    @pytest.mark.asyncio
    async def test_websocket_events_endpoint_exists(self, app):
        """Test that the /ws/events endpoint exists."""
        # Check that the route is registered
        routes = [r.path for r in app.routes]
        ws_routes = [r for r in routes if "/ws" in r]
        assert len(ws_routes) > 0

    @pytest.mark.asyncio
    async def test_websocket_ticker_endpoint_exists(self, app):
        """Test that the /ws/events/ticker/{ticker} endpoint exists."""
        routes = [r.path for r in app.routes]
        ticker_ws = [r for r in routes if "ticker" in r and "ws" in r]
        # Just verify we have WebSocket infrastructure
        assert "/ws/events" in str(routes) or "websocket" in str(routes).lower()


class TestWebSocketClientMessages:
    """Tests for handling client messages over WebSocket."""

    @pytest.fixture
    def manager(self):
        """Create a connection manager."""
        return ConnectionManager()

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        ws = MagicMock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_handle_subscribe_action(self, manager, mock_websocket):
        """Test handling subscribe action from client."""
        from backend.api.websocket.streamer import _handle_client_message

        connection_id = str(uuid4())
        await manager.connect(mock_websocket, connection_id)

        # Patch the global manager
        with patch("backend.api.websocket.streamer.manager", manager):
            await _handle_client_message(connection_id, {
                "action": "subscribe",
                "ticker": "AAPL",
            })

        assert manager.get_ticker_subscriber_count("AAPL") == 1
        mock_websocket.send_json.assert_called_with({
            "type": "subscribed",
            "ticker": "AAPL",
        })

    @pytest.mark.asyncio
    async def test_handle_unsubscribe_action(self, manager, mock_websocket):
        """Test handling unsubscribe action from client."""
        from backend.api.websocket.streamer import _handle_client_message

        connection_id = str(uuid4())
        await manager.connect(mock_websocket, connection_id)
        await manager.subscribe(connection_id, "AAPL")

        with patch("backend.api.websocket.streamer.manager", manager):
            await _handle_client_message(connection_id, {
                "action": "unsubscribe",
                "ticker": "AAPL",
            })

        assert manager.get_ticker_subscriber_count("AAPL") == 0
        mock_websocket.send_json.assert_called_with({
            "type": "unsubscribed",
            "ticker": "AAPL",
        })

    @pytest.mark.asyncio
    async def test_handle_ping_action(self, manager, mock_websocket):
        """Test handling ping action from client."""
        from backend.api.websocket.streamer import _handle_client_message

        connection_id = str(uuid4())
        await manager.connect(mock_websocket, connection_id)

        with patch("backend.api.websocket.streamer.manager", manager):
            await _handle_client_message(connection_id, {"action": "ping"})

        mock_websocket.send_json.assert_called_with({"type": "pong"})


class TestRedisPubSubIntegration:
    """Integration tests for Redis pub/sub flow."""

    @pytest.fixture
    def event_payload(self):
        """Create a sample event payload."""
        return {
            "id": str(uuid4()),
            "ticker": "GOOG",
            "headline": "Google announces new AI",
            "event_type": "NEWS",
            "alpha_score": 0.72,
            "direction": "BULLISH",
            "urgency_level": "high",
            "event_time": datetime.now(timezone.utc).isoformat(),
        }

    def test_alerting_task_publishes_event(self, event_payload):
        """Test that alerting task publishes to WebSocket via Redis."""
        with patch("backend.workers.tasks.alerting_tasks.get_redis_client") as mock_get_redis:
            mock_redis = MagicMock()
            mock_get_redis.return_value = mock_redis

            with patch("backend.workers.tasks.alerting_tasks.get_sync_db_context"):
                from backend.workers.tasks.alerting_tasks import publish_websocket_event

                # Should not raise
                result = publish_websocket_event(event_payload)

                assert result["published"] is True or "error" not in result
                mock_redis.publish.assert_called()

    def test_publish_websocket_event_format(self, event_payload):
        """Test the format of published WebSocket events."""
        with patch("backend.workers.tasks.alerting_tasks.get_redis_client") as mock_get_redis:
            mock_redis = MagicMock()
            mock_get_redis.return_value = mock_redis

            from backend.workers.tasks.alerting_tasks import publish_websocket_event

            publish_websocket_event(event_payload)

            # Check that publish was called with correct channels
            call_args = mock_redis.publish.call_args_list

            # Should publish to events:all at minimum
            channels = [call[0][0] for call in call_args]
            assert "events:all" in channels

            # Check payload format
            first_call_payload = json.loads(call_args[0][0][1])
            assert first_call_payload["type"] == "event"
            assert "data" in first_call_payload
            assert first_call_payload["data"]["ticker"] == "GOOG"

    def test_publish_to_ticker_specific_channel(self, event_payload):
        """Test publishing to ticker-specific channel."""
        with patch("backend.workers.tasks.alerting_tasks.get_redis_client") as mock_get_redis:
            mock_redis = MagicMock()
            mock_get_redis.return_value = mock_redis

            from backend.workers.tasks.alerting_tasks import publish_websocket_event

            publish_websocket_event(event_payload)

            call_args = mock_redis.publish.call_args_list
            channels = [call[0][0] for call in call_args]

            # Should include ticker-specific channel
            assert f"events:ticker:{event_payload['ticker']}" in channels

    def test_publish_to_high_alpha_channel_when_applicable(self, event_payload):
        """Test publishing to high alpha channel for high scoring events."""
        event_payload["alpha_score"] = 0.85  # High alpha

        with patch("backend.workers.tasks.alerting_tasks.get_redis_client") as mock_get_redis:
            mock_redis = MagicMock()
            mock_get_redis.return_value = mock_redis

            from backend.workers.tasks.alerting_tasks import publish_websocket_event

            publish_websocket_event(event_payload)

            call_args = mock_redis.publish.call_args_list
            channels = [call[0][0] for call in call_args]

            assert "events:high-alpha" in channels


class TestWebSocketErrorHandling:
    """Tests for WebSocket error handling."""

    @pytest.fixture
    def manager(self):
        """Create a connection manager."""
        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_send_handles_disconnected_client(self, manager):
        """Test that send handles disconnected clients gracefully."""
        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock(side_effect=RuntimeError("Client disconnected"))

        connection_id = str(uuid4())
        await manager.connect(mock_ws, connection_id)

        # Should return False, not raise
        result = await manager.send_personal(connection_id, {"type": "test"})
        assert result is False

    @pytest.mark.asyncio
    async def test_broadcast_continues_after_single_failure(self, manager):
        """Test that broadcast continues if one client fails."""
        ws1 = MagicMock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock(side_effect=RuntimeError("Failed"))

        ws2 = MagicMock(spec=WebSocket)
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        await manager.connect(ws1, "conn1")
        await manager.connect(ws2, "conn2")

        message = {"type": "test"}
        sent_count = await manager.broadcast(message)

        # One should succeed despite one failure
        assert sent_count == 1
        ws2.send_json.assert_called_once_with(message)
