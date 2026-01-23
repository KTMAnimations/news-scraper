"""Tests for alerting Celery tasks."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from backend.workers.tasks.alerting_tasks import (
    check_alerts_task,
    dispatch_alert,
    publish_websocket_event,
    send_email_alert,
    get_redis_client,
)


class TestGetRedisClient:
    """Tests for get_redis_client helper."""

    def test_get_redis_client_creates_client(self):
        """Test Redis client creation."""
        with patch("redis.from_url") as mock_from_url, \
             patch("backend.workers.tasks.alerting_tasks.settings") as mock_settings, \
             patch("backend.workers.tasks.alerting_tasks._redis_client", None):
            mock_settings.redis_url = "redis://localhost:6379"
            mock_client = MagicMock()
            mock_from_url.return_value = mock_client

            # Reset global
            import backend.workers.tasks.alerting_tasks as module
            module._redis_client = None

            client = get_redis_client()

            assert client is not None


class TestCheckAlertsTask:
    """Tests for check_alerts_task."""

    def test_check_alerts_no_matches(self):
        """Test check_alerts with no matching alerts."""
        data = {
            "ticker": "AAPL",
            "event_type": "EARNINGS",
            "alpha_score": 0.5,
            "urgency_level": "medium",
            "direction": "BULLISH",
        }

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []  # No alerts
        mock_session.execute.return_value = mock_result

        with patch("backend.workers.tasks.alerting_tasks.get_sync_db_context") as mock_ctx, \
             patch("backend.workers.tasks.alerting_tasks.publish_websocket_event"):
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = check_alerts_task(data)

        assert result["alerts_triggered"] == 0
        assert result["watchlist_matches"] == 0
        assert "alerts_checked_at" in result

    def test_check_alerts_with_matching_alert(self):
        """Test check_alerts with a matching alert."""
        data = {
            "ticker": "AAPL",
            "event_type": "EARNINGS",
            "alpha_score": 0.7,
            "urgency_level": "high",
            "direction": "BULLISH",
        }

        # Create mock alert and user
        mock_alert = MagicMock()
        mock_alert.id = uuid4()
        mock_alert.ticker = "AAPL"
        mock_alert.event_types = None
        mock_alert.min_alpha_score = 0.5
        mock_alert.urgency_levels = None
        mock_alert.direction = None
        mock_alert.delivery_method = "email"

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.email = "test@example.com"
        mock_user.full_name = "Test User"

        mock_session = MagicMock()
        mock_alerts_result = MagicMock()
        mock_alerts_result.fetchall.return_value = [(mock_alert, mock_user)]

        mock_watchlist_result = MagicMock()
        mock_watchlist_result.fetchall.return_value = []

        mock_session.execute.side_effect = [mock_alerts_result, mock_watchlist_result]

        with patch("backend.workers.tasks.alerting_tasks.get_sync_db_context") as mock_ctx, \
             patch("backend.workers.tasks.alerting_tasks.publish_websocket_event"):
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = check_alerts_task(data)

        assert result["alerts_triggered"] == 1

    def test_check_alerts_ticker_filter(self):
        """Test alert doesn't match wrong ticker."""
        data = {
            "ticker": "AAPL",
            "event_type": "EARNINGS",
            "alpha_score": 0.7,
            "urgency_level": "high",
        }

        mock_alert = MagicMock()
        mock_alert.id = uuid4()
        mock_alert.ticker = "MSFT"  # Different ticker
        mock_alert.event_types = None
        mock_alert.min_alpha_score = None
        mock_alert.urgency_levels = None
        mock_alert.direction = None

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.email = "test@example.com"
        mock_user.full_name = "Test User"

        mock_session = MagicMock()
        mock_alerts_result = MagicMock()
        mock_alerts_result.fetchall.return_value = [(mock_alert, mock_user)]

        mock_watchlist_result = MagicMock()
        mock_watchlist_result.fetchall.return_value = []

        mock_session.execute.side_effect = [mock_alerts_result, mock_watchlist_result]

        with patch("backend.workers.tasks.alerting_tasks.get_sync_db_context") as mock_ctx, \
             patch("backend.workers.tasks.alerting_tasks.publish_websocket_event"):
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = check_alerts_task(data)

        assert result["alerts_triggered"] == 0

    def test_check_alerts_alpha_threshold(self):
        """Test alert doesn't match below alpha threshold."""
        data = {
            "ticker": "AAPL",
            "event_type": "EARNINGS",
            "alpha_score": 0.3,  # Below threshold
            "urgency_level": "high",
        }

        mock_alert = MagicMock()
        mock_alert.id = uuid4()
        mock_alert.ticker = "AAPL"
        mock_alert.event_types = None
        mock_alert.min_alpha_score = 0.5  # Threshold
        mock_alert.urgency_levels = None
        mock_alert.direction = None

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.email = "test@example.com"
        mock_user.full_name = "Test User"

        mock_session = MagicMock()
        mock_alerts_result = MagicMock()
        mock_alerts_result.fetchall.return_value = [(mock_alert, mock_user)]

        mock_watchlist_result = MagicMock()
        mock_watchlist_result.fetchall.return_value = []

        mock_session.execute.side_effect = [mock_alerts_result, mock_watchlist_result]

        with patch("backend.workers.tasks.alerting_tasks.get_sync_db_context") as mock_ctx, \
             patch("backend.workers.tasks.alerting_tasks.publish_websocket_event"):
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = check_alerts_task(data)

        assert result["alerts_triggered"] == 0


class TestDispatchAlert:
    """Tests for dispatch_alert task."""

    def test_dispatch_alert_email(self):
        """Test dispatching email alert."""
        alert = {
            "alert_id": str(uuid4()),
            "user_id": str(uuid4()),
            "user_email": "test@example.com",
            "delivery_method": "email",
        }
        event_data = {
            "ticker": "AAPL",
            "headline": "Apple Reports Earnings",
            "event_type": "EARNINGS",
            "direction": "BULLISH",
            "alpha_score": 0.75,
            "id": str(uuid4()),
        }

        with patch("backend.workers.tasks.alerting_tasks.email_service") as mock_email:
            mock_email.send_email.return_value = True

            result = dispatch_alert(alert, event_data)

        assert result["email_sent"] is True
        mock_email.send_email.assert_called_once()

    def test_dispatch_alert_no_email_for_push_only(self):
        """Test no email sent for push-only delivery."""
        alert = {
            "alert_id": str(uuid4()),
            "user_id": str(uuid4()),
            "user_email": "test@example.com",
            "delivery_method": "push",
        }
        event_data = {
            "ticker": "AAPL",
            "headline": "News",
            "event_type": "NEWS",
        }

        with patch("backend.workers.tasks.alerting_tasks.email_service") as mock_email:
            result = dispatch_alert(alert, event_data)

        assert result["email_sent"] is False
        mock_email.send_email.assert_not_called()

    def test_dispatch_alert_both_methods(self):
        """Test dispatching with both email and push."""
        alert = {
            "alert_id": str(uuid4()),
            "user_id": str(uuid4()),
            "user_email": "test@example.com",
            "delivery_method": "both",
        }
        event_data = {
            "ticker": "AAPL",
            "headline": "News",
            "event_type": "NEWS",
            "direction": "",
            "alpha_score": 0.5,
            "id": str(uuid4()),
        }

        with patch("backend.workers.tasks.alerting_tasks.email_service") as mock_email:
            mock_email.send_email.return_value = True

            result = dispatch_alert(alert, event_data)

        assert result["email_sent"] is True
        mock_email.send_email.assert_called_once()


class TestPublishWebsocketEvent:
    """Tests for publish_websocket_event task."""

    def test_publish_websocket_success(self):
        """Test successful WebSocket event publishing."""
        data = {
            "id": str(uuid4()),
            "ticker": "AAPL",
            "headline": "News",
            "event_type": "EARNINGS",
            "alpha_score": 0.5,
            "direction": "BULLISH",
            "urgency_level": "high",
            "event_time": datetime.now(timezone.utc).isoformat(),
            "source": "SEC",
        }

        mock_redis = MagicMock()

        with patch("backend.workers.tasks.alerting_tasks.get_redis_client", return_value=mock_redis):
            result = publish_websocket_event(data)

        assert result["published"] is True
        assert result["ticker"] == "AAPL"

        # Check that publish was called for events:all
        publish_calls = mock_redis.publish.call_args_list
        channels = [call[0][0] for call in publish_calls]
        assert "events:all" in channels

    def test_publish_websocket_ticker_channel(self):
        """Test publishing to ticker-specific channel."""
        data = {
            "id": str(uuid4()),
            "ticker": "MSFT",
            "headline": "Microsoft News",
            "event_type": "NEWS",
        }

        mock_redis = MagicMock()

        with patch("backend.workers.tasks.alerting_tasks.get_redis_client", return_value=mock_redis):
            result = publish_websocket_event(data)

        publish_calls = mock_redis.publish.call_args_list
        channels = [call[0][0] for call in publish_calls]
        assert "events:ticker:MSFT" in channels

    def test_publish_websocket_high_alpha_channel(self):
        """Test publishing to high-alpha channel."""
        data = {
            "id": str(uuid4()),
            "ticker": "GOOG",
            "headline": "Google News",
            "event_type": "EARNINGS",
            "alpha_score": 0.85,  # High alpha
        }

        mock_redis = MagicMock()

        with patch("backend.workers.tasks.alerting_tasks.get_redis_client", return_value=mock_redis):
            result = publish_websocket_event(data)

        publish_calls = mock_redis.publish.call_args_list
        channels = [call[0][0] for call in publish_calls]
        assert "events:high-alpha" in channels

    def test_publish_websocket_error_handling(self):
        """Test WebSocket publish handles errors gracefully."""
        data = {"ticker": "AAPL"}

        with patch("backend.workers.tasks.alerting_tasks.get_redis_client", side_effect=Exception("Redis error")):
            result = publish_websocket_event(data)

        assert result["published"] is False
        assert "error" in result


class TestSendEmailAlert:
    """Tests for send_email_alert task."""

    def test_send_email_alert_success(self):
        """Test successful email alert sending."""
        with patch("backend.workers.tasks.alerting_tasks.email_service") as mock_email:
            mock_email.send_email.return_value = True

            result = send_email_alert(
                user_email="test@example.com",
                subject="Alert: AAPL",
                body="<h1>Alert</h1>",
                event_data={"ticker": "AAPL"},
            )

        assert result["sent"] is True
        assert result["to"] == "test@example.com"
        assert result["subject"] == "Alert: AAPL"
        assert "sent_at" in result

    def test_send_email_alert_failure(self):
        """Test email alert failure."""
        with patch("backend.workers.tasks.alerting_tasks.email_service") as mock_email:
            mock_email.send_email.return_value = False

            result = send_email_alert(
                user_email="test@example.com",
                subject="Alert",
                body="<p>Content</p>",
                event_data={},
            )

        assert result["sent"] is False
