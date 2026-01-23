"""Tests for storage Celery tasks."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from backend.workers.tasks.storage_tasks import (
    store_event_task,
    _parse_datetime,
    _extract_ticker,
    _publish_to_redis_sync,
    store_and_alert_task,
    store_and_index_task,
)


class TestParseDatetime:
    """Tests for _parse_datetime helper function."""

    def test_parse_none(self):
        """Test parsing None returns None."""
        assert _parse_datetime(None) is None

    def test_parse_datetime_object(self):
        """Test parsing datetime object returns it unchanged."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = _parse_datetime(dt)
        assert result == dt

    def test_parse_iso_string(self):
        """Test parsing ISO format string."""
        result = _parse_datetime("2024-01-15T10:30:00+00:00")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_iso_string_with_z(self):
        """Test parsing ISO format string with Z suffix."""
        result = _parse_datetime("2024-01-15T10:30:00Z")
        assert result is not None
        assert result.year == 2024

    def test_parse_invalid_string(self):
        """Test parsing invalid string returns None."""
        result = _parse_datetime("not a date")
        assert result is None


class TestExtractTicker:
    """Tests for _extract_ticker helper function."""

    def test_extract_direct_ticker(self):
        """Test extraction from direct ticker field."""
        data = {"ticker": "AAPL"}
        assert _extract_ticker(data) == "AAPL"

    def test_extract_ticker_uppercase(self):
        """Test ticker is converted to uppercase."""
        data = {"ticker": "aapl"}
        assert _extract_ticker(data) == "AAPL"

    def test_extract_from_extracted_tickers(self):
        """Test extraction from extracted_tickers list."""
        data = {"extracted_tickers": ["MSFT", "GOOG"]}
        assert _extract_ticker(data) == "MSFT"

    def test_extract_from_title_parens(self):
        """Test extraction from title with ticker in parentheses."""
        data = {"title": "Apple Inc. (AAPL) announces earnings"}
        assert _extract_ticker(data) == "AAPL"

    def test_extract_from_company_name_parens(self):
        """Test extraction from company_name with ticker in parentheses."""
        data = {"company_name": "Microsoft Corporation (MSFT)"}
        assert _extract_ticker(data) == "MSFT"

    def test_extract_from_title_prefix(self):
        """Test extraction from title with ticker prefix."""
        data = {"title": "GOOG - Google announces new product"}
        assert _extract_ticker(data) == "GOOG"

    def test_extract_from_title_colon_prefix(self):
        """Test extraction from title with ticker:colon prefix."""
        data = {"title": "TSLA: Tesla reports Q4 earnings"}
        assert _extract_ticker(data) == "TSLA"

    def test_extract_returns_unknown(self):
        """Test returns UNKNOWN when no ticker found."""
        data = {"headline": "General market news"}
        assert _extract_ticker(data) == "UNKNOWN"

    def test_extract_empty_data(self):
        """Test returns UNKNOWN for empty data."""
        assert _extract_ticker({}) == "UNKNOWN"


class TestStoreEventTask:
    """Tests for store_event_task."""

    def test_store_event_skips_unknown_ticker(self):
        """Test event with unknown ticker is skipped."""
        data = {"headline": "News without ticker"}

        result = store_event_task(data)

        assert result["skipped"] is True
        assert result["skip_reason"] == "No valid ticker"

    def test_store_event_skips_empty_headline(self):
        """Test event with empty headline is skipped."""
        data = {"ticker": "AAPL", "headline": ""}

        result = store_event_task(data)

        assert result["skipped"] is True
        assert result["skip_reason"] == "No valid headline"

    def test_store_event_skips_no_headline(self):
        """Test event with 'No headline' is skipped."""
        data = {"ticker": "AAPL", "headline": "No headline"}

        result = store_event_task(data)

        assert result["skipped"] is True
        assert result["skip_reason"] == "No valid headline"

    def test_store_event_success(self):
        """Test successful event storage."""
        data = {
            "ticker": "AAPL",
            "headline": "Apple Reports Q4 Earnings",
            "event_type": "EARNINGS",
            "summary": "Strong results beat expectations",
        }

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None  # No duplicate
        mock_session.execute.return_value = mock_result

        with patch("backend.workers.tasks.storage_tasks.get_sync_db_context") as mock_ctx, \
             patch("backend.workers.tasks.storage_tasks._publish_to_redis_sync"):
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = store_event_task(data)

        assert "event_id" in result
        assert "stored_at" in result
        mock_session.add.assert_called_once()

    def test_store_event_detects_duplicate(self):
        """Test duplicate detection skips storage."""
        data = {
            "ticker": "AAPL",
            "headline": "Duplicate News",
        }

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)  # Duplicate found
        mock_session.execute.return_value = mock_result

        with patch("backend.workers.tasks.storage_tasks.get_sync_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = store_event_task(data)

        assert result["skipped"] is True
        assert result["skip_reason"] == "Duplicate event"

    def test_store_event_maps_filing_types(self):
        """Test filing type to event type mapping."""
        data = {
            "ticker": "AAPL",
            "headline": "Form 4 Filing",
            "filing_type": "4",
        }

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("backend.workers.tasks.storage_tasks.get_sync_db_context") as mock_ctx, \
             patch("backend.workers.tasks.storage_tasks._publish_to_redis_sync"), \
             patch("backend.workers.tasks.storage_tasks.Event") as MockEvent:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_event = MagicMock()
            mock_event.id = uuid4()
            MockEvent.return_value = mock_event

            result = store_event_task(data)

        # Check that Event was called with INSIDER_TRADE event type
        call_kwargs = MockEvent.call_args[1]
        assert call_kwargs["event_type"] == "INSIDER_TRADE"

    def test_store_event_maps_13d_filing(self):
        """Test SC 13D filing type mapping."""
        data = {
            "ticker": "AAPL",
            "headline": "13D Filing",
            "filing_type": "SC 13D",
        }

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("backend.workers.tasks.storage_tasks.get_sync_db_context") as mock_ctx, \
             patch("backend.workers.tasks.storage_tasks._publish_to_redis_sync"), \
             patch("backend.workers.tasks.storage_tasks.Event") as MockEvent:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_event = MagicMock()
            mock_event.id = uuid4()
            MockEvent.return_value = mock_event

            result = store_event_task(data)

        call_kwargs = MockEvent.call_args[1]
        assert call_kwargs["event_type"] == "ACTIVIST_STAKE"


class TestPublishToRedisSync:
    """Tests for _publish_to_redis_sync helper."""

    def test_publish_to_all_channel(self):
        """Test publishing to events:all channel."""
        event_data = {
            "id": uuid4(),
            "ticker": "AAPL",
            "event_time": datetime.now(timezone.utc),
            "event_type": "EARNINGS",
            "headline": "Earnings Report",
            "summary": "Summary",
            "source_name": "SEC",
            "sentiment_score": 0.5,
            "sentiment_label": "positive",
            "alpha_score": 0.7,
            "direction": "BULLISH",
            "urgency_level": "high",
        }

        mock_client = MagicMock()

        with patch("redis.from_url", return_value=mock_client):
            _publish_to_redis_sync(event_data)

        # Should publish to at least events:all
        publish_calls = mock_client.publish.call_args_list
        channels = [call[0][0] for call in publish_calls]
        assert "events:all" in channels

    def test_publish_to_ticker_channel(self):
        """Test publishing to ticker-specific channel."""
        event_data = {
            "id": uuid4(),
            "ticker": "AAPL",
            "event_time": datetime.now(timezone.utc),
            "event_type": "EARNINGS",
            "headline": "Earnings Report",
            "summary": None,
            "source_name": "SEC",
            "sentiment_score": None,
            "sentiment_label": None,
            "alpha_score": None,
            "direction": None,
            "urgency_level": None,
        }

        mock_client = MagicMock()

        with patch("redis.from_url", return_value=mock_client):
            _publish_to_redis_sync(event_data)

        publish_calls = mock_client.publish.call_args_list
        channels = [call[0][0] for call in publish_calls]
        assert "events:ticker:AAPL" in channels

    def test_publish_to_high_alpha_channel(self):
        """Test publishing to high_alpha channel for high-scoring events."""
        event_data = {
            "id": uuid4(),
            "ticker": "AAPL",
            "event_time": datetime.now(timezone.utc),
            "event_type": "EARNINGS",
            "headline": "Major Earnings Beat",
            "summary": None,
            "source_name": "SEC",
            "sentiment_score": None,
            "sentiment_label": None,
            "alpha_score": 0.85,  # High alpha
            "direction": "BULLISH",
            "urgency_level": "critical",
        }

        mock_client = MagicMock()

        with patch("redis.from_url", return_value=mock_client):
            _publish_to_redis_sync(event_data)

        publish_calls = mock_client.publish.call_args_list
        channels = [call[0][0] for call in publish_calls]
        assert "events:high_alpha" in channels

    def test_publish_handles_error(self):
        """Test publish handles Redis errors gracefully."""
        event_data = {
            "id": uuid4(),
            "ticker": "AAPL",
            "event_time": datetime.now(timezone.utc),
            "event_type": "NEWS",
            "headline": "News",
            "summary": None,
            "source_name": "News",
            "sentiment_score": None,
            "sentiment_label": None,
            "alpha_score": None,
            "direction": None,
            "urgency_level": None,
        }

        with patch("redis.from_url", side_effect=Exception("Redis connection failed")):
            # Should not raise, just log warning
            _publish_to_redis_sync(event_data)


class TestStoreAndAlertTask:
    """Tests for store_and_alert_task."""

    def test_store_and_alert_chains_tasks(self):
        """Test store_and_alert chains storage and alerting."""
        data = {"ticker": "AAPL", "headline": "News"}

        with patch("backend.workers.tasks.storage_tasks.store_event_task") as mock_store, \
             patch("backend.workers.tasks.storage_tasks.check_alerts_task") as mock_alerts:
            mock_store.return_value = {"event_id": "123", **data}
            mock_alerts.return_value = {"alerts_triggered": 0, **data}

            result = store_and_alert_task(data)

        mock_store.assert_called_once_with(data)
        mock_alerts.assert_called_once()


class TestStoreAndIndexTask:
    """Tests for store_and_index_task."""

    def test_store_and_index_chains_tasks(self):
        """Test store_and_index chains storage and indexing."""
        data = {"ticker": "AAPL", "headline": "News"}

        with patch("backend.workers.tasks.storage_tasks.store_event_task") as mock_store, \
             patch("backend.workers.tasks.storage_tasks.index_event_opensearch_task") as mock_index:
            mock_store.return_value = {"event_id": "123", **data}
            mock_index.return_value = {"opensearch_indexed": True, **data}

            result = store_and_index_task(data)

        mock_store.assert_called_once_with(data)
        mock_index.assert_called_once()
