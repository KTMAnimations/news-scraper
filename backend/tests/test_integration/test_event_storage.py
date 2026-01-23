"""Integration tests for event storage and retrieval.

Tests storing events to the database and retrieving them through the API.
Uses test database fixtures and mocks external dependencies.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.storage.timescale.models import Event


class TestEventStorage:
    """Tests for storing events to the database."""

    @pytest.fixture
    def complete_event_data(self):
        """Create complete event data for storage."""
        return {
            "ticker": "AAPL",
            "headline": "Apple announces new product line",
            "title": "Apple Product Launch",
            "content": "Apple Inc. announced a revolutionary new product lineup today.",
            "summary": "New Apple products unveiled",
            "source": "sec_edgar",
            "source_name": "SEC EDGAR",
            "source_url": "https://sec.gov/aapl-filing",
            "event_time": datetime.now(timezone.utc).isoformat(),
            "filing_time": datetime.now(timezone.utc).isoformat(),
            "event_type": "NEWS",
            "event_category": "PRODUCT_LAUNCH",
            "sentiment_label": "positive",
            "sentiment_score": 0.75,
            "sentiment_confidence": 0.88,
            "alpha_score": 0.65,
            "direction": "BULLISH",
            "urgency_level": "high",
            "extracted_tickers": ["AAPL"],
            "extracted_companies": ["Apple Inc."],
            "extracted_people": ["Tim Cook"],
            "filing_type": "8-K",
            "cik": "320193",
        }

    @pytest.mark.asyncio
    async def test_store_event_creates_database_record(
        self,
        test_session: AsyncSession,
        complete_event_data: dict,
    ):
        """Test that store_event_task creates a database record."""
        with patch("backend.workers.tasks.storage_tasks.get_sync_db_context") as mock_ctx:
            # Create a mock sync session
            mock_sync_session = MagicMock()
            mock_sync_session.execute.return_value.fetchone.return_value = None  # No duplicate
            mock_sync_session.__enter__ = MagicMock(return_value=mock_sync_session)
            mock_sync_session.__exit__ = MagicMock(return_value=None)
            mock_ctx.return_value = mock_sync_session

            with patch("backend.workers.tasks.storage_tasks._publish_to_redis_sync"):
                from backend.workers.tasks.storage_tasks import store_event_task

                result = store_event_task(complete_event_data)

                # Should have added an event
                mock_sync_session.add.assert_called_once()

                # Should have event_id in result
                assert "event_id" in result or "skipped" not in result

    @pytest.mark.asyncio
    async def test_store_event_skips_duplicates(
        self,
        test_session: AsyncSession,
        complete_event_data: dict,
    ):
        """Test that duplicate events are skipped."""
        with patch("backend.workers.tasks.storage_tasks.get_sync_db_context") as mock_ctx:
            mock_sync_session = MagicMock()
            # Simulate finding a duplicate
            mock_sync_session.execute.return_value.fetchone.return_value = (1,)
            mock_sync_session.__enter__ = MagicMock(return_value=mock_sync_session)
            mock_sync_session.__exit__ = MagicMock(return_value=None)
            mock_ctx.return_value = mock_sync_session

            from backend.workers.tasks.storage_tasks import store_event_task

            result = store_event_task(complete_event_data)

            assert result.get("skipped") is True
            assert result.get("skip_reason") == "Duplicate event"

    def test_store_event_skips_without_ticker(self):
        """Test that events without valid ticker are skipped."""
        event_no_ticker = {
            "headline": "Some news without ticker",
            "content": "Generic content",
            "source": "news",
        }

        with patch("backend.workers.tasks.storage_tasks.get_sync_db_context"):
            from backend.workers.tasks.storage_tasks import store_event_task

            result = store_event_task(event_no_ticker)

            assert result.get("skipped") is True
            assert "ticker" in result.get("skip_reason", "").lower()

    def test_store_event_skips_without_headline(self):
        """Test that events without headline are skipped."""
        event_no_headline = {
            "ticker": "AAPL",
            "headline": "",
            "content": "Some content",
            "source": "news",
        }

        with patch("backend.workers.tasks.storage_tasks.get_sync_db_context"):
            from backend.workers.tasks.storage_tasks import store_event_task

            result = store_event_task(event_no_headline)

            assert result.get("skipped") is True
            assert "headline" in result.get("skip_reason", "").lower()

    def test_extract_ticker_from_various_sources(self):
        """Test ticker extraction from different data fields."""
        from backend.workers.tasks.storage_tasks import _extract_ticker

        # Direct ticker field
        assert _extract_ticker({"ticker": "aapl"}) == "AAPL"

        # From extracted_tickers
        assert _extract_ticker({"extracted_tickers": ["MSFT", "GOOG"]}) == "MSFT"

        # From title with parentheses
        assert _extract_ticker({"title": "Company Name (TSLA) reports"}) == "TSLA"

        # From title with pattern at start
        assert _extract_ticker({"title": "NVDA - Breaking news"}) == "NVDA"

        # Unknown when no ticker found
        assert _extract_ticker({"content": "No ticker here"}) == "UNKNOWN"

    def test_parse_datetime_various_formats(self):
        """Test datetime parsing from various formats."""
        from backend.workers.tasks.storage_tasks import _parse_datetime

        # ISO format with Z
        dt = _parse_datetime("2024-01-15T10:30:00Z")
        assert dt is not None
        assert dt.tzinfo is not None

        # ISO format with offset
        dt = _parse_datetime("2024-01-15T10:30:00+00:00")
        assert dt is not None

        # datetime object
        now = datetime.now(timezone.utc)
        dt = _parse_datetime(now)
        assert dt == now

        # None input
        assert _parse_datetime(None) is None

        # Invalid format
        assert _parse_datetime("invalid") is None


class TestEventRetrieval:
    """Tests for retrieving events through the API."""

    @pytest.mark.asyncio
    async def test_get_events_empty_database(self, client: AsyncClient):
        """Test getting events from empty database returns empty list."""
        response = await client.get("/api/v1/events")

        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert isinstance(data["events"], list)
        assert data["total"] >= 0

    @pytest.mark.asyncio
    async def test_get_events_with_ticker_filter(self, client: AsyncClient):
        """Test filtering events by ticker."""
        response = await client.get("/api/v1/events", params={"ticker": "AAPL"})

        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        # All returned events should match the ticker filter
        for event in data["events"]:
            assert event["ticker"] == "AAPL"

    @pytest.mark.asyncio
    async def test_get_events_with_event_type_filter(self, client: AsyncClient):
        """Test filtering events by event type."""
        response = await client.get(
            "/api/v1/events",
            params={"event_type": "INSIDER_TRADE"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "events" in data

    @pytest.mark.asyncio
    async def test_get_events_with_min_alpha_filter(self, client: AsyncClient):
        """Test filtering events by minimum alpha score."""
        response = await client.get("/api/v1/events", params={"min_alpha": 0.7})

        assert response.status_code == 200
        data = response.json()
        # All returned events should have alpha >= 0.7
        for event in data["events"]:
            if event["alpha_score"] is not None:
                assert event["alpha_score"] >= 0.7

    @pytest.mark.asyncio
    async def test_get_events_with_direction_filter(self, client: AsyncClient):
        """Test filtering events by direction."""
        response = await client.get("/api/v1/events", params={"direction": "BULLISH"})

        assert response.status_code == 200
        data = response.json()
        for event in data["events"]:
            assert event["direction"] == "BULLISH"

    @pytest.mark.asyncio
    async def test_get_events_pagination(self, client: AsyncClient):
        """Test event pagination."""
        response = await client.get(
            "/api/v1/events",
            params={"limit": 10, "offset": 0},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert len(data["events"]) <= 10

    @pytest.mark.asyncio
    async def test_get_latest_events(self, client: AsyncClient):
        """Test getting latest events endpoint."""
        response = await client.get("/api/v1/events/latest")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_high_alpha_events(self, client: AsyncClient):
        """Test getting high alpha events."""
        response = await client.get(
            "/api/v1/events/high-alpha",
            params={"min_alpha": 0.5, "hours": 24},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_ticker_events(self, client: AsyncClient):
        """Test getting events for a specific ticker."""
        response = await client.get("/api/v1/events/ticker/AAPL")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_event_by_id_not_found(self, client: AsyncClient):
        """Test getting non-existent event returns 404."""
        fake_id = str(uuid4())
        response = await client.get(f"/api/v1/events/{fake_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_event_invalid_id_format(self, client: AsyncClient):
        """Test getting event with invalid UUID format."""
        response = await client.get("/api/v1/events/not-a-uuid")

        assert response.status_code == 422


class TestEventStorageWithDatabase:
    """Integration tests that interact with the test database."""

    @pytest.mark.asyncio
    async def test_create_and_retrieve_event(
        self,
        test_session: AsyncSession,
        sample_event_data: dict,
    ):
        """Test creating an event and retrieving it."""
        # Create event directly in database
        event = Event(
            id=uuid4(),
            ticker=sample_event_data["ticker"],
            event_time=datetime.now(timezone.utc),
            ingest_time=datetime.now(timezone.utc),
            event_type=sample_event_data["event_type"],
            event_category=sample_event_data["event_category"],
            headline=sample_event_data["headline"],
            summary=sample_event_data["summary"],
            source_url=sample_event_data["source_url"],
            source_name=sample_event_data["source_name"],
            sentiment_score=sample_event_data["sentiment_score"],
            sentiment_label=sample_event_data["sentiment_label"],
            alpha_score=sample_event_data["alpha_score"],
            direction=sample_event_data["direction"],
            urgency_level=sample_event_data["urgency_level"],
        )

        test_session.add(event)
        await test_session.commit()

        # Retrieve the event
        result = await test_session.execute(
            select(Event).where(Event.id == event.id)
        )
        retrieved = result.scalar_one_or_none()

        assert retrieved is not None
        assert retrieved.ticker == sample_event_data["ticker"]
        assert retrieved.headline == sample_event_data["headline"]
        assert retrieved.alpha_score == sample_event_data["alpha_score"]

    @pytest.mark.asyncio
    async def test_query_events_by_ticker(
        self,
        test_session: AsyncSession,
    ):
        """Test querying events by ticker."""
        # Create multiple events
        for i in range(3):
            event = Event(
                id=uuid4(),
                ticker="AAPL",
                event_time=datetime.now(timezone.utc) - timedelta(hours=i),
                ingest_time=datetime.now(timezone.utc),
                event_type="NEWS",
                headline=f"Apple news {i}",
            )
            test_session.add(event)

        # Add one event with different ticker
        other_event = Event(
            id=uuid4(),
            ticker="MSFT",
            event_time=datetime.now(timezone.utc),
            ingest_time=datetime.now(timezone.utc),
            event_type="NEWS",
            headline="Microsoft news",
        )
        test_session.add(other_event)

        await test_session.commit()

        # Query by ticker
        result = await test_session.execute(
            select(Event).where(Event.ticker == "AAPL")
        )
        aapl_events = result.scalars().all()

        assert len(aapl_events) == 3
        for event in aapl_events:
            assert event.ticker == "AAPL"

    @pytest.mark.asyncio
    async def test_query_events_by_alpha_score(
        self,
        test_session: AsyncSession,
    ):
        """Test querying events by alpha score threshold."""
        # Create events with various alpha scores
        alpha_values = [0.3, 0.5, 0.7, 0.9]
        for alpha in alpha_values:
            event = Event(
                id=uuid4(),
                ticker="TEST",
                event_time=datetime.now(timezone.utc),
                ingest_time=datetime.now(timezone.utc),
                event_type="NEWS",
                headline=f"Event with alpha {alpha}",
                alpha_score=alpha,
            )
            test_session.add(event)

        await test_session.commit()

        # Query events with alpha >= 0.6
        result = await test_session.execute(
            select(Event).where(Event.alpha_score >= 0.6)
        )
        high_alpha_events = result.scalars().all()

        assert len(high_alpha_events) == 2
        for event in high_alpha_events:
            assert event.alpha_score >= 0.6

    @pytest.mark.asyncio
    async def test_query_events_by_time_range(
        self,
        test_session: AsyncSession,
    ):
        """Test querying events within a time range."""
        now = datetime.now(timezone.utc)

        # Create events at different times
        times = [
            now - timedelta(hours=48),
            now - timedelta(hours=24),
            now - timedelta(hours=12),
            now - timedelta(hours=1),
        ]

        for i, event_time in enumerate(times):
            event = Event(
                id=uuid4(),
                ticker="TIME",
                event_time=event_time,
                ingest_time=now,
                event_type="NEWS",
                headline=f"Event {i}",
            )
            test_session.add(event)

        await test_session.commit()

        # Query events from last 24 hours
        cutoff = now - timedelta(hours=24)
        result = await test_session.execute(
            select(Event).where(
                Event.ticker == "TIME",
                Event.event_time >= cutoff,
            )
        )
        recent_events = result.scalars().all()

        assert len(recent_events) == 2  # 12h and 1h old events


class TestEventStorageAndIndexing:
    """Tests for event storage with OpenSearch indexing."""

    @pytest.fixture
    def event_with_full_data(self):
        """Create event data suitable for indexing."""
        return {
            "event_id": str(uuid4()),
            "ticker": "NVDA",
            "headline": "NVIDIA reports record AI chip revenue",
            "summary": "Strong demand for AI accelerators drives growth",
            "content": "Full article content about NVIDIA earnings...",
            "event_type": "EARNINGS_BEAT",
            "source_name": "SEC EDGAR",
            "sentiment_label": "positive",
            "alpha_score": 0.85,
            "event_time": datetime.now(timezone.utc).isoformat(),
        }

    def test_index_event_opensearch_success(self, event_with_full_data):
        """Test successful OpenSearch indexing."""
        with patch("backend.workers.tasks.storage_tasks.search_service") as mock_search:
            mock_search.ensure_index.return_value = None
            mock_search.index_event.return_value = True

            from backend.workers.tasks.storage_tasks import index_event_opensearch_task

            result = index_event_opensearch_task(event_with_full_data)

            assert result["opensearch_indexed"] is True
            mock_search.index_event.assert_called_once()

    def test_index_event_skips_already_skipped_events(self):
        """Test that already-skipped events are not indexed."""
        skipped_event = {
            "skipped": True,
            "skip_reason": "No valid ticker",
            "ticker": None,
        }

        with patch("backend.workers.tasks.storage_tasks.search_service") as mock_search:
            from backend.workers.tasks.storage_tasks import index_event_opensearch_task

            result = index_event_opensearch_task(skipped_event)

            assert result["opensearch_indexed"] is False
            mock_search.index_event.assert_not_called()

    def test_index_event_skips_without_event_id(self):
        """Test that events without event_id are not indexed."""
        event_no_id = {
            "ticker": "TEST",
            "headline": "Test event",
        }

        with patch("backend.workers.tasks.storage_tasks.search_service") as mock_search:
            from backend.workers.tasks.storage_tasks import index_event_opensearch_task

            result = index_event_opensearch_task(event_no_id)

            assert result["opensearch_indexed"] is False
            mock_search.index_event.assert_not_called()


class TestRedisPublishing:
    """Tests for Redis pub/sub publishing during storage."""

    @pytest.fixture
    def stored_event_data(self):
        """Create event data as it would be after storage."""
        return {
            "id": uuid4(),
            "ticker": "GOOG",
            "event_time": datetime.now(timezone.utc),
            "event_type": "NEWS",
            "headline": "Google announces new AI model",
            "summary": "Major AI advancement announced",
            "source_name": "TechCrunch",
            "sentiment_score": 0.8,
            "sentiment_label": "positive",
            "alpha_score": 0.75,
            "direction": "BULLISH",
            "urgency_level": "high",
        }

    def test_publish_to_redis_publishes_to_all_channel(self, stored_event_data):
        """Test that events are published to the all events channel."""
        with patch("backend.workers.tasks.storage_tasks.redis.from_url") as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client

            from backend.workers.tasks.storage_tasks import _publish_to_redis_sync

            _publish_to_redis_sync(stored_event_data)

            # Should publish to events:all
            calls = mock_client.publish.call_args_list
            channels = [call[0][0] for call in calls]
            assert "events:all" in channels

    def test_publish_to_redis_publishes_to_ticker_channel(self, stored_event_data):
        """Test that events are published to ticker-specific channel."""
        with patch("backend.workers.tasks.storage_tasks.redis.from_url") as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client

            from backend.workers.tasks.storage_tasks import _publish_to_redis_sync

            _publish_to_redis_sync(stored_event_data)

            # Should publish to events:ticker:GOOG
            calls = mock_client.publish.call_args_list
            channels = [call[0][0] for call in calls]
            assert f"events:ticker:{stored_event_data['ticker']}" in channels

    def test_publish_to_redis_publishes_to_high_alpha_channel(self, stored_event_data):
        """Test that high alpha events are published to high alpha channel."""
        stored_event_data["alpha_score"] = 0.85  # High alpha

        with patch("backend.workers.tasks.storage_tasks.redis.from_url") as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client

            from backend.workers.tasks.storage_tasks import _publish_to_redis_sync

            _publish_to_redis_sync(stored_event_data)

            # Should publish to events:high_alpha
            calls = mock_client.publish.call_args_list
            channels = [call[0][0] for call in calls]
            assert "events:high_alpha" in channels

    def test_publish_to_redis_handles_connection_error(self, stored_event_data):
        """Test that Redis connection errors are handled gracefully."""
        with patch("backend.workers.tasks.storage_tasks.redis.from_url") as mock_redis:
            mock_redis.side_effect = Exception("Connection refused")

            from backend.workers.tasks.storage_tasks import _publish_to_redis_sync

            # Should not raise, just log warning
            _publish_to_redis_sync(stored_event_data)


class TestStoreAndAlertChain:
    """Tests for the combined store and alert task chain."""

    def test_store_and_alert_chain_executes_both_tasks(self):
        """Test that store_and_alert_task executes storage then alerts."""
        event_data = {
            "ticker": "META",
            "headline": "Meta announces AI breakthrough",
            "event_type": "NEWS",
            "source": "tech_news",
            "event_time": datetime.now(timezone.utc).isoformat(),
        }

        with patch("backend.workers.tasks.storage_tasks.store_event_task") as mock_store:
            with patch("backend.workers.tasks.alerting_tasks.check_alerts_task") as mock_alerts:
                stored_data = {**event_data, "event_id": str(uuid4())}
                mock_store.return_value = stored_data
                mock_alerts.return_value = {**stored_data, "alerts_triggered": 0}

                from backend.workers.tasks.storage_tasks import store_and_alert_task

                result = store_and_alert_task(event_data)

                mock_store.assert_called_once_with(event_data)
                mock_alerts.assert_called_once_with(stored_data)

    def test_store_index_and_alert_chain_executes_all_tasks(self):
        """Test that store_index_and_alert_task executes all three tasks."""
        event_data = {
            "ticker": "AMZN",
            "headline": "Amazon expands AWS services",
            "event_type": "NEWS",
            "source": "press_release",
            "event_time": datetime.now(timezone.utc).isoformat(),
        }

        with patch("backend.workers.tasks.storage_tasks.store_event_task") as mock_store:
            with patch("backend.workers.tasks.storage_tasks.index_event_opensearch_task") as mock_index:
                with patch("backend.workers.tasks.alerting_tasks.check_alerts_task") as mock_alerts:
                    stored_data = {**event_data, "event_id": str(uuid4())}
                    mock_store.return_value = stored_data

                    indexed_data = {**stored_data, "opensearch_indexed": True}
                    mock_index.return_value = indexed_data

                    mock_alerts.return_value = {**indexed_data, "alerts_triggered": 1}

                    from backend.workers.tasks.storage_tasks import store_index_and_alert_task

                    result = store_index_and_alert_task(event_data)

                    mock_store.assert_called_once()
                    mock_index.assert_called_once()
                    mock_alerts.assert_called_once()
