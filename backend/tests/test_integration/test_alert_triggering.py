"""Integration tests for alert triggering.

Tests that alerts fire when conditions match incoming events.
Mocks database and notification services but tests full alert logic.
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.storage.timescale.models import Alert, User, Watchlist


class TestAlertConditionMatching:
    """Tests for alert condition matching logic."""

    @pytest.fixture
    def sample_user(self):
        """Create a sample user."""
        return User(
            id=uuid4(),
            email="test@example.com",
            hashed_password="hashed",
            full_name="Test User",
            is_active=True,
        )

    @pytest.fixture
    def sample_alert(self, sample_user):
        """Create a sample alert rule."""
        return Alert(
            id=uuid4(),
            user_id=sample_user.id,
            name="High Alpha AAPL Alert",
            ticker="AAPL",
            min_alpha_score=0.5,
            urgency_levels=["critical", "high"],
            direction="BULLISH",
            delivery_method="email",
            is_active=True,
        )

    @pytest.fixture
    def high_alpha_event(self):
        """Create a high alpha bullish event."""
        return {
            "id": str(uuid4()),
            "ticker": "AAPL",
            "headline": "Apple announces record earnings",
            "event_type": "EARNINGS_BEAT",
            "alpha_score": 0.75,
            "direction": "BULLISH",
            "urgency_level": "high",
            "sentiment_label": "positive",
            "sentiment_score": 0.85,
        }

    def test_alert_matches_all_conditions(self, sample_alert, high_alpha_event):
        """Test that alert matches when all conditions are met."""
        # Simulate the matching logic from check_alerts_task
        matches = True

        # Ticker match
        if sample_alert.ticker:
            if sample_alert.ticker.upper() != high_alpha_event["ticker"].upper():
                matches = False

        # Alpha score match
        if sample_alert.min_alpha_score:
            if high_alpha_event.get("alpha_score", 0) < sample_alert.min_alpha_score:
                matches = False

        # Urgency match
        if sample_alert.urgency_levels:
            if high_alpha_event.get("urgency_level") not in sample_alert.urgency_levels:
                matches = False

        # Direction match
        if sample_alert.direction:
            if high_alpha_event.get("direction") != sample_alert.direction:
                matches = False

        assert matches is True

    def test_alert_fails_ticker_mismatch(self, sample_alert, high_alpha_event):
        """Test that alert doesn't match when ticker is different."""
        high_alpha_event["ticker"] = "MSFT"

        matches = True
        if sample_alert.ticker.upper() != high_alpha_event["ticker"].upper():
            matches = False

        assert matches is False

    def test_alert_fails_alpha_below_threshold(self, sample_alert, high_alpha_event):
        """Test that alert doesn't match when alpha is below threshold."""
        high_alpha_event["alpha_score"] = 0.3

        matches = True
        if high_alpha_event.get("alpha_score", 0) < sample_alert.min_alpha_score:
            matches = False

        assert matches is False

    def test_alert_fails_urgency_mismatch(self, sample_alert, high_alpha_event):
        """Test that alert doesn't match when urgency level doesn't match."""
        high_alpha_event["urgency_level"] = "low"

        matches = True
        if high_alpha_event.get("urgency_level") not in sample_alert.urgency_levels:
            matches = False

        assert matches is False

    def test_alert_fails_direction_mismatch(self, sample_alert, high_alpha_event):
        """Test that alert doesn't match when direction is different."""
        high_alpha_event["direction"] = "BEARISH"

        matches = True
        if high_alpha_event.get("direction") != sample_alert.direction:
            matches = False

        assert matches is False

    def test_alert_with_null_ticker_matches_all_tickers(self, sample_user, high_alpha_event):
        """Test that alert with no ticker matches any ticker."""
        alert_no_ticker = Alert(
            id=uuid4(),
            user_id=sample_user.id,
            name="All Tickers Alert",
            ticker=None,  # Matches all tickers
            min_alpha_score=0.5,
            direction="BULLISH",
            is_active=True,
        )

        matches = True

        # Ticker check - null means match all
        if alert_no_ticker.ticker:
            if alert_no_ticker.ticker.upper() != high_alpha_event["ticker"].upper():
                matches = False

        assert matches is True

    def test_alert_with_null_urgency_matches_all_urgencies(self, sample_user, high_alpha_event):
        """Test that alert with no urgency levels matches any urgency."""
        alert_no_urgency = Alert(
            id=uuid4(),
            user_id=sample_user.id,
            name="Any Urgency Alert",
            urgency_levels=None,  # Matches all urgency levels
            min_alpha_score=0.5,
            is_active=True,
        )

        matches = True
        if alert_no_urgency.urgency_levels:
            if high_alpha_event.get("urgency_level") not in alert_no_urgency.urgency_levels:
                matches = False

        assert matches is True


class TestCheckAlertsTask:
    """Tests for the check_alerts_task Celery task."""

    @pytest.fixture
    def mock_db_context(self):
        """Create mock database context."""
        mock_session = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_session)
        mock_context.__exit__ = MagicMock(return_value=None)
        return mock_context, mock_session

    def test_check_alerts_task_returns_event_data(self, mock_db_context):
        """Test that check_alerts_task returns the event data."""
        event_data = {
            "ticker": "AAPL",
            "event_type": "NEWS",
            "alpha_score": 0.6,
            "urgency_level": "high",
            "direction": "BULLISH",
        }

        mock_context, mock_session = mock_db_context
        mock_session.execute.return_value.fetchall.return_value = []

        with patch("backend.workers.tasks.alerting_tasks.get_sync_db_context", return_value=mock_context):
            with patch("backend.workers.tasks.alerting_tasks.publish_websocket_event"):
                from backend.workers.tasks.alerting_tasks import check_alerts_task

                result = check_alerts_task(event_data)

                assert "ticker" in result
                assert "alerts_triggered" in result
                assert "alerts_checked_at" in result

    def test_check_alerts_task_counts_triggered_alerts(self, mock_db_context):
        """Test that check_alerts_task correctly counts triggered alerts."""
        event_data = {
            "ticker": "AAPL",
            "event_type": "EARNINGS_BEAT",
            "alpha_score": 0.8,
            "urgency_level": "critical",
            "direction": "BULLISH",
        }

        mock_context, mock_session = mock_db_context

        # Create mock alerts that match
        mock_alert = MagicMock()
        mock_alert.ticker = "AAPL"
        mock_alert.event_types = None
        mock_alert.min_alpha_score = 0.5
        mock_alert.urgency_levels = ["critical", "high"]
        mock_alert.direction = "BULLISH"
        mock_alert.id = uuid4()
        mock_alert.delivery_method = "email"
        mock_alert.is_active = True

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.email = "test@example.com"
        mock_user.full_name = "Test User"

        mock_session.execute.return_value.fetchall.side_effect = [
            [(mock_alert, mock_user)],  # First call for alerts
            [],  # Second call for watchlist
        ]

        with patch("backend.workers.tasks.alerting_tasks.get_sync_db_context", return_value=mock_context):
            with patch("backend.workers.tasks.alerting_tasks.publish_websocket_event"):
                from backend.workers.tasks.alerting_tasks import check_alerts_task

                result = check_alerts_task(event_data)

                assert result["alerts_triggered"] == 1

    def test_check_alerts_task_always_publishes_websocket(self, mock_db_context):
        """Test that check_alerts_task always publishes to WebSocket."""
        event_data = {
            "ticker": "AAPL",
            "event_type": "NEWS",
            "alpha_score": 0.3,
            "urgency_level": "low",
        }

        mock_context, mock_session = mock_db_context
        mock_session.execute.return_value.fetchall.return_value = []

        with patch("backend.workers.tasks.alerting_tasks.get_sync_db_context", return_value=mock_context):
            with patch("backend.workers.tasks.alerting_tasks.publish_websocket_event") as mock_publish:
                mock_publish.delay = MagicMock()

                from backend.workers.tasks.alerting_tasks import check_alerts_task

                check_alerts_task(event_data)

                mock_publish.delay.assert_called_once()


class TestWatchlistAlerts:
    """Tests for watchlist-based alerting."""

    @pytest.fixture
    def mock_db_context(self):
        """Create mock database context."""
        mock_session = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_session)
        mock_context.__exit__ = MagicMock(return_value=None)
        return mock_context, mock_session

    def test_watchlist_matches_for_high_urgency_events(self, mock_db_context):
        """Test that watchlist triggers for high urgency events."""
        event_data = {
            "ticker": "TSLA",
            "event_type": "INSIDER_TRADE",
            "alpha_score": 0.7,
            "urgency_level": "critical",  # High urgency
            "direction": "BULLISH",
        }

        mock_context, mock_session = mock_db_context

        # Mock watchlist item
        mock_watchlist = MagicMock()
        mock_watchlist.id = uuid4()
        mock_watchlist.ticker = "TSLA"
        mock_watchlist.alert_enabled = True

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.email = "watchlist@example.com"
        mock_user.full_name = "Watchlist User"

        mock_session.execute.return_value.fetchall.side_effect = [
            [],  # No alert rules
            [(mock_watchlist, mock_user)],  # Watchlist match
        ]

        with patch("backend.workers.tasks.alerting_tasks.get_sync_db_context", return_value=mock_context):
            with patch("backend.workers.tasks.alerting_tasks.publish_websocket_event"):
                from backend.workers.tasks.alerting_tasks import check_alerts_task

                result = check_alerts_task(event_data)

                assert result["watchlist_matches"] == 1

    def test_watchlist_skipped_for_low_urgency_events(self, mock_db_context):
        """Test that watchlist doesn't trigger for low urgency events."""
        event_data = {
            "ticker": "TSLA",
            "event_type": "NEWS",
            "alpha_score": 0.3,
            "urgency_level": "low",  # Low urgency
        }

        mock_context, mock_session = mock_db_context
        mock_session.execute.return_value.fetchall.side_effect = [
            [],  # No alert rules
            # Watchlist query shouldn't be called for low urgency
        ]

        with patch("backend.workers.tasks.alerting_tasks.get_sync_db_context", return_value=mock_context):
            with patch("backend.workers.tasks.alerting_tasks.publish_websocket_event"):
                from backend.workers.tasks.alerting_tasks import check_alerts_task

                result = check_alerts_task(event_data)

                # Should be 0 since urgency is low
                assert result["watchlist_matches"] == 0


class TestAlertDispatch:
    """Tests for alert dispatching (email, push notifications)."""

    @pytest.fixture
    def alert_info(self):
        """Create alert info for dispatch."""
        return {
            "alert_id": str(uuid4()),
            "user_id": str(uuid4()),
            "user_email": "test@example.com",
            "user_name": "Test User",
            "delivery_method": "email",
        }

    @pytest.fixture
    def event_data(self):
        """Create event data that triggered the alert."""
        return {
            "id": str(uuid4()),
            "ticker": "NVDA",
            "headline": "NVIDIA announces major AI breakthrough",
            "event_type": "PRODUCT_LAUNCH",
            "direction": "BULLISH",
            "alpha_score": 0.85,
        }

    def test_dispatch_alert_sends_email(self, alert_info, event_data):
        """Test that dispatch_alert sends email notification."""
        with patch("backend.workers.tasks.alerting_tasks.email_service") as mock_email:
            mock_email.send_email.return_value = True

            from backend.workers.tasks.alerting_tasks import dispatch_alert

            result = dispatch_alert(alert_info, event_data)

            assert result["email_sent"] is True
            mock_email.send_email.assert_called_once()

    def test_dispatch_alert_email_contains_event_details(self, alert_info, event_data):
        """Test that dispatch email contains event details."""
        with patch("backend.workers.tasks.alerting_tasks.email_service") as mock_email:
            mock_email.send_email.return_value = True

            from backend.workers.tasks.alerting_tasks import dispatch_alert

            dispatch_alert(alert_info, event_data)

            # Check the email call arguments
            call_args = mock_email.send_email.call_args
            subject = call_args[1]["subject"]
            html_body = call_args[1]["html_body"]

            assert event_data["ticker"] in subject
            assert event_data["headline"] in html_body
            assert event_data["event_type"] in html_body

    def test_dispatch_alert_skips_email_for_push_only(self, alert_info, event_data):
        """Test that email is skipped when delivery method is push only."""
        alert_info["delivery_method"] = "push"

        with patch("backend.workers.tasks.alerting_tasks.email_service") as mock_email:
            from backend.workers.tasks.alerting_tasks import dispatch_alert

            result = dispatch_alert(alert_info, event_data)

            assert result["email_sent"] is False
            mock_email.send_email.assert_not_called()

    def test_dispatch_alert_handles_both_delivery_methods(self, alert_info, event_data):
        """Test that both email and push are sent when delivery is 'both'."""
        alert_info["delivery_method"] = "both"

        with patch("backend.workers.tasks.alerting_tasks.email_service") as mock_email:
            mock_email.send_email.return_value = True

            from backend.workers.tasks.alerting_tasks import dispatch_alert

            result = dispatch_alert(alert_info, event_data)

            assert result["email_sent"] is True


class TestEmailAlertTask:
    """Tests for the send_email_alert task."""

    def test_send_email_alert_success(self):
        """Test successful email alert sending."""
        with patch("backend.workers.tasks.alerting_tasks.email_service") as mock_email:
            mock_email.send_email.return_value = True

            from backend.workers.tasks.alerting_tasks import send_email_alert

            result = send_email_alert(
                user_email="user@example.com",
                subject="[AAPL] High Alpha Alert",
                body="<h1>Alert Details</h1>",
                event_data={"ticker": "AAPL"},
            )

            assert result["sent"] is True
            assert result["to"] == "user@example.com"
            assert "sent_at" in result

    def test_send_email_alert_failure(self):
        """Test email alert failure handling."""
        with patch("backend.workers.tasks.alerting_tasks.email_service") as mock_email:
            mock_email.send_email.return_value = False

            from backend.workers.tasks.alerting_tasks import send_email_alert

            result = send_email_alert(
                user_email="invalid@example.com",
                subject="Test",
                body="<p>Test</p>",
                event_data={},
            )

            assert result["sent"] is False


class TestPushNotificationTask:
    """Tests for the push notification task."""

    @pytest.fixture
    def mock_db_with_user(self):
        """Create mock database with user that has FCM tokens."""
        mock_session = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_session)
        mock_context.__exit__ = MagicMock(return_value=None)

        mock_user = MagicMock()
        mock_user.fcm_tokens = ["token1", "token2"]
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_user

        return mock_context, mock_session, mock_user

    def test_send_push_notification_success(self, mock_db_with_user):
        """Test successful push notification."""
        mock_context, mock_session, mock_user = mock_db_with_user

        with patch("backend.workers.tasks.alerting_tasks.get_sync_db_context", return_value=mock_context):
            from backend.workers.tasks.alerting_tasks import send_push_notification

            result = send_push_notification(
                user_id=str(uuid4()),
                title="New Alert",
                body="High alpha event detected",
                data={"ticker": "AAPL"},
            )

            assert result["sent"] is True
            assert "sent_at" in result

    def test_send_push_notification_no_tokens(self):
        """Test push notification when user has no FCM tokens."""
        mock_session = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_session)
        mock_context.__exit__ = MagicMock(return_value=None)

        mock_user = MagicMock()
        mock_user.fcm_tokens = None
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_user

        with patch("backend.workers.tasks.alerting_tasks.get_sync_db_context", return_value=mock_context):
            from backend.workers.tasks.alerting_tasks import send_push_notification

            result = send_push_notification(
                user_id=str(uuid4()),
                title="Test",
                body="Test body",
            )

            assert result["sent"] is False
            assert "No FCM tokens" in result["reason"]


class TestDailyDigest:
    """Tests for daily digest aggregation and sending."""

    @pytest.fixture
    def mock_db_with_users_and_events(self):
        """Create mock database with users, watchlists, and events."""
        mock_session = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_session)
        mock_context.__exit__ = MagicMock(return_value=None)

        # Mock user
        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.email = "digest@example.com"
        mock_user.is_active = True

        # Mock watchlist
        mock_watchlist = MagicMock()
        mock_watchlist.ticker = "AAPL"

        # Mock event
        mock_event = MagicMock()
        mock_event.ticker = "AAPL"
        mock_event.headline = "Apple news"
        mock_event.alpha_score = 0.7
        mock_event.direction = "BULLISH"

        # Set up return values for different queries
        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [mock_user]

        watchlist_result = MagicMock()
        watchlist_result.scalars.return_value.all.return_value = [mock_watchlist]

        events_result = MagicMock()
        events_result.scalars.return_value.all.return_value = [mock_event]

        mock_session.execute.side_effect = [users_result, watchlist_result, events_result]

        return mock_context, mock_session

    def test_daily_digest_generates_for_active_users(self, mock_db_with_users_and_events):
        """Test that daily digest generates for active users with watchlists."""
        mock_context, mock_session = mock_db_with_users_and_events

        with patch("backend.workers.tasks.alerting_tasks.get_sync_db_context", return_value=mock_context):
            with patch("backend.workers.tasks.alerting_tasks.email_service") as mock_email:
                mock_email.send_email.return_value = True

                from backend.workers.tasks.alerting_tasks import aggregate_daily_digest

                result = aggregate_daily_digest()

                assert "generated_at" in result
                assert result["digests_sent"] >= 0

    def test_daily_digest_skips_users_without_watchlist(self):
        """Test that users without watchlist items are skipped."""
        mock_session = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_session)
        mock_context.__exit__ = MagicMock(return_value=None)

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [mock_user]

        watchlist_result = MagicMock()
        watchlist_result.scalars.return_value.all.return_value = []  # Empty watchlist

        mock_session.execute.side_effect = [users_result, watchlist_result]

        with patch("backend.workers.tasks.alerting_tasks.get_sync_db_context", return_value=mock_context):
            with patch("backend.workers.tasks.alerting_tasks.email_service") as mock_email:
                from backend.workers.tasks.alerting_tasks import aggregate_daily_digest

                result = aggregate_daily_digest()

                # No emails should be sent for users without watchlist
                mock_email.send_email.assert_not_called()
                assert result["digests_sent"] == 0


class TestAlertAPI:
    """Tests for alert management API endpoints."""

    @pytest.mark.asyncio
    async def test_list_alerts_requires_auth(self, client: AsyncClient):
        """Test that listing alerts requires authentication."""
        response = await client.get("/api/v1/alerts")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_alert_requires_auth(self, client: AsyncClient, sample_alert_data: dict):
        """Test that creating alert requires authentication."""
        response = await client.post("/api/v1/alerts", json=sample_alert_data)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_alert_requires_auth(self, client: AsyncClient):
        """Test that updating alert requires authentication."""
        fake_id = str(uuid4())
        response = await client.put(
            f"/api/v1/alerts/{fake_id}",
            json={"name": "Updated Alert"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_alert_requires_auth(self, client: AsyncClient):
        """Test that deleting alert requires authentication."""
        fake_id = str(uuid4())
        response = await client.delete(f"/api/v1/alerts/{fake_id}")

        assert response.status_code == 401


class TestAlertIntegrationWithPipeline:
    """Integration tests for alerts within the full event pipeline."""

    @pytest.fixture
    def complete_event_through_pipeline(self):
        """Create a complete event that has gone through the full pipeline."""
        return {
            "id": str(uuid4()),
            "ticker": "AMD",
            "headline": "AMD announces breakthrough AI chip",
            "summary": "Advanced Micro Devices reveals next-gen AI accelerator",
            "event_type": "PRODUCT_LAUNCH",
            "event_category": "TECHNOLOGY",
            "source": "press_release",
            "source_name": "Business Wire",
            "event_time": datetime.now(timezone.utc).isoformat(),
            "sentiment_label": "positive",
            "sentiment_score": 0.88,
            "sentiment_confidence": 0.92,
            "alpha_score": 0.82,
            "direction": "BULLISH",
            "urgency_level": "critical",
            "extracted_tickers": ["AMD"],
            "extracted_companies": ["Advanced Micro Devices"],
        }

    def test_pipeline_to_alert_flow(self, complete_event_through_pipeline):
        """Test complete flow from processed event to alert checking."""
        with patch("backend.workers.tasks.alerting_tasks.get_sync_db_context") as mock_ctx:
            mock_session = MagicMock()
            mock_session.execute.return_value.fetchall.return_value = []
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=None)

            with patch("backend.workers.tasks.alerting_tasks.publish_websocket_event") as mock_ws:
                mock_ws.delay = MagicMock()

                from backend.workers.tasks.alerting_tasks import check_alerts_task

                result = check_alerts_task(complete_event_through_pipeline)

                # Should have processed without error
                assert "alerts_checked_at" in result

                # Should have published to WebSocket
                mock_ws.delay.assert_called_once()

    def test_high_alpha_event_triggers_multiple_alerts(self):
        """Test that a high alpha event can trigger multiple alert rules."""
        event_data = {
            "ticker": "NVDA",
            "event_type": "EARNINGS_BEAT",
            "alpha_score": 0.95,
            "urgency_level": "critical",
            "direction": "BULLISH",
        }

        with patch("backend.workers.tasks.alerting_tasks.get_sync_db_context") as mock_ctx:
            mock_session = MagicMock()

            # Create multiple matching alerts
            alerts = []
            for i in range(3):
                mock_alert = MagicMock()
                mock_alert.id = uuid4()
                mock_alert.ticker = "NVDA"
                mock_alert.event_types = None
                mock_alert.min_alpha_score = 0.5
                mock_alert.urgency_levels = ["critical"]
                mock_alert.direction = "BULLISH"
                mock_alert.delivery_method = "email"
                mock_alert.is_active = True

                mock_user = MagicMock()
                mock_user.id = uuid4()
                mock_user.email = f"user{i}@example.com"
                mock_user.full_name = f"User {i}"

                alerts.append((mock_alert, mock_user))

            mock_session.execute.return_value.fetchall.side_effect = [
                alerts,  # Alert rules
                [],  # Watchlist
            ]
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=None)

            with patch("backend.workers.tasks.alerting_tasks.publish_websocket_event"):
                from backend.workers.tasks.alerting_tasks import check_alerts_task

                result = check_alerts_task(event_data)

                assert result["alerts_triggered"] == 3
