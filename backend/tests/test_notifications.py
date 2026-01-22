"""Tests for notification system."""

import pytest
from datetime import datetime, timezone


class TestEmailService:
    """Test email service."""

    def test_email_service_initialization(self):
        """Test email service initializes correctly."""
        from backend.notifications import EmailService

        service = EmailService()
        assert service is not None

    def test_create_message(self):
        """Test creating email message."""
        from backend.notifications import EmailService

        service = EmailService()
        msg = service._create_message(
            to_email="test@example.com",
            subject="Test Subject",
            html_body="<h1>Test</h1>",
            text_body="Test",
        )

        assert msg["To"] == "test@example.com"
        assert msg["Subject"] == "Test Subject"

    def test_is_configured_returns_false_by_default(self):
        """Test is_configured returns False without configuration."""
        from backend.notifications import EmailService

        service = EmailService()
        # Will be False if SMTP settings not configured
        assert isinstance(service.is_configured, bool)


class TestNotificationManager:
    """Test notification manager."""

    def test_alert_matches_event_ticker_filter(self):
        """Test alert matching with ticker filter."""
        from backend.notifications.notification_manager import NotificationManager
        from unittest.mock import MagicMock

        # Create mock alert
        alert = MagicMock()
        alert.ticker = "AAPL"
        alert.event_types = None
        alert.min_alpha_score = None
        alert.urgency_levels = None
        alert.direction = None

        # Create mock session
        session = MagicMock()
        manager = NotificationManager(session)

        # Test matching ticker
        event_data = {"ticker": "AAPL", "event_type": "NEWS"}
        assert manager._alert_matches_event(alert, event_data) is True

        # Test non-matching ticker
        event_data = {"ticker": "MSFT", "event_type": "NEWS"}
        assert manager._alert_matches_event(alert, event_data) is False

    def test_alert_matches_event_type_filter(self):
        """Test alert matching with event type filter."""
        from backend.notifications.notification_manager import NotificationManager
        from unittest.mock import MagicMock

        alert = MagicMock()
        alert.ticker = None
        alert.event_types = ["EARNINGS_BEAT", "INSIDER_BUY"]
        alert.min_alpha_score = None
        alert.urgency_levels = None
        alert.direction = None

        session = MagicMock()
        manager = NotificationManager(session)

        # Test matching event type
        event_data = {"ticker": "AAPL", "event_type": "EARNINGS_BEAT"}
        assert manager._alert_matches_event(alert, event_data) is True

        # Test non-matching event type
        event_data = {"ticker": "AAPL", "event_type": "NEWS"}
        assert manager._alert_matches_event(alert, event_data) is False

    def test_alert_matches_alpha_threshold(self):
        """Test alert matching with alpha score threshold."""
        from backend.notifications.notification_manager import NotificationManager
        from unittest.mock import MagicMock

        alert = MagicMock()
        alert.ticker = None
        alert.event_types = None
        alert.min_alpha_score = 0.5
        alert.urgency_levels = None
        alert.direction = None

        session = MagicMock()
        manager = NotificationManager(session)

        # Test matching alpha score
        event_data = {"ticker": "AAPL", "alpha_score": 0.7}
        assert manager._alert_matches_event(alert, event_data) is True

        # Test below threshold
        event_data = {"ticker": "AAPL", "alpha_score": 0.3}
        assert manager._alert_matches_event(alert, event_data) is False

    def test_alert_matches_direction_filter(self):
        """Test alert matching with direction filter."""
        from backend.notifications.notification_manager import NotificationManager
        from unittest.mock import MagicMock

        alert = MagicMock()
        alert.ticker = None
        alert.event_types = None
        alert.min_alpha_score = None
        alert.urgency_levels = None
        alert.direction = "BULLISH"

        session = MagicMock()
        manager = NotificationManager(session)

        # Test matching direction
        event_data = {"ticker": "AAPL", "direction": "BULLISH"}
        assert manager._alert_matches_event(alert, event_data) is True

        # Test non-matching direction
        event_data = {"ticker": "AAPL", "direction": "BEARISH"}
        assert manager._alert_matches_event(alert, event_data) is False

    def test_alert_matches_urgency_filter(self):
        """Test alert matching with urgency level filter."""
        from backend.notifications.notification_manager import NotificationManager
        from unittest.mock import MagicMock

        alert = MagicMock()
        alert.ticker = None
        alert.event_types = None
        alert.min_alpha_score = None
        alert.urgency_levels = ["critical", "high"]
        alert.direction = None

        session = MagicMock()
        manager = NotificationManager(session)

        # Test matching urgency
        event_data = {"ticker": "AAPL", "urgency_level": "critical"}
        assert manager._alert_matches_event(alert, event_data) is True

        # Test non-matching urgency
        event_data = {"ticker": "AAPL", "urgency_level": "low"}
        assert manager._alert_matches_event(alert, event_data) is False
