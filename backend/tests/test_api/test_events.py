"""Tests for events API endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from backend.storage.timescale.models import Event


class TestListEventsEndpoint:
    """Tests for GET /api/v1/events endpoint."""

    @pytest.mark.asyncio
    async def test_list_events_returns_empty_list(self, client: AsyncClient):
        """Test listing events when no events exist."""
        response = await client.get("/api/v1/events")
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["events"], list)

    @pytest.mark.asyncio
    async def test_list_events_with_ticker_filter(self, client: AsyncClient):
        """Test listing events with ticker filter."""
        response = await client.get("/api/v1/events", params={"ticker": "AAPL"})
        assert response.status_code == 200
        data = response.json()
        assert "events" in data

    @pytest.mark.asyncio
    async def test_list_events_with_event_type_filter(self, client: AsyncClient):
        """Test listing events with event_type filter."""
        response = await client.get("/api/v1/events", params={"event_type": "EARNINGS_BEAT"})
        assert response.status_code == 200
        data = response.json()
        assert "events" in data

    @pytest.mark.asyncio
    async def test_list_events_with_min_alpha_filter(self, client: AsyncClient):
        """Test listing events with minimum alpha score filter."""
        response = await client.get("/api/v1/events", params={"min_alpha": 0.5})
        assert response.status_code == 200
        data = response.json()
        assert "events" in data

    @pytest.mark.asyncio
    async def test_list_events_with_direction_filter(self, client: AsyncClient):
        """Test listing events with direction filter."""
        response = await client.get("/api/v1/events", params={"direction": "BULLISH"})
        assert response.status_code == 200
        data = response.json()
        assert "events" in data

    @pytest.mark.asyncio
    async def test_list_events_with_urgency_filter(self, client: AsyncClient):
        """Test listing events with urgency level filter."""
        response = await client.get("/api/v1/events", params={"urgency_level": "high"})
        assert response.status_code == 200
        data = response.json()
        assert "events" in data

    @pytest.mark.asyncio
    async def test_list_events_pagination(self, client: AsyncClient):
        """Test listing events with pagination parameters."""
        response = await client.get("/api/v1/events", params={"limit": 10, "offset": 5})
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 5

    @pytest.mark.asyncio
    async def test_list_events_limit_validation(self, client: AsyncClient):
        """Test that limit parameter is validated."""
        # Test limit exceeding maximum
        response = await client.get("/api/v1/events", params={"limit": 1000})
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_list_events_multiple_filters(self, client: AsyncClient):
        """Test listing events with multiple filters combined."""
        response = await client.get(
            "/api/v1/events",
            params={
                "ticker": "AAPL",
                "event_type": "EARNINGS_BEAT",
                "min_alpha": 0.3,
                "direction": "BULLISH",
                "limit": 50,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "events" in data


class TestLatestEventsEndpoint:
    """Tests for GET /api/v1/events/latest endpoint."""

    @pytest.mark.asyncio
    async def test_get_latest_events(self, client: AsyncClient):
        """Test getting latest events."""
        response = await client.get("/api/v1/events/latest")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_latest_events_with_limit(self, client: AsyncClient):
        """Test getting latest events with custom limit."""
        response = await client.get("/api/v1/events/latest", params={"limit": 25})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_latest_events_limit_validation(self, client: AsyncClient):
        """Test that limit parameter is validated for latest events."""
        response = await client.get("/api/v1/events/latest", params={"limit": 200})
        assert response.status_code == 422  # Limit max is 100


class TestHighAlphaEventsEndpoint:
    """Tests for GET /api/v1/events/high-alpha endpoint."""

    @pytest.mark.asyncio
    async def test_get_high_alpha_events(self, client: AsyncClient):
        """Test getting high alpha events with default parameters."""
        response = await client.get("/api/v1/events/high-alpha")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_high_alpha_events_custom_min_alpha(self, client: AsyncClient):
        """Test getting high alpha events with custom minimum alpha."""
        response = await client.get("/api/v1/events/high-alpha", params={"min_alpha": 0.7})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_high_alpha_events_custom_hours(self, client: AsyncClient):
        """Test getting high alpha events with custom time window."""
        response = await client.get("/api/v1/events/high-alpha", params={"hours": 48})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_high_alpha_events_alpha_validation(self, client: AsyncClient):
        """Test that alpha parameter is validated."""
        # Alpha must be between 0 and 1
        response = await client.get("/api/v1/events/high-alpha", params={"min_alpha": 1.5})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_high_alpha_events_hours_validation(self, client: AsyncClient):
        """Test that hours parameter is validated."""
        # Hours max is 168 (1 week)
        response = await client.get("/api/v1/events/high-alpha", params={"hours": 500})
        assert response.status_code == 422


class TestTickerEventsEndpoint:
    """Tests for GET /api/v1/events/ticker/{ticker} endpoint."""

    @pytest.mark.asyncio
    async def test_get_ticker_events(self, client: AsyncClient):
        """Test getting events for a specific ticker."""
        response = await client.get("/api/v1/events/ticker/AAPL")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_ticker_events_with_limit(self, client: AsyncClient):
        """Test getting ticker events with custom limit."""
        response = await client.get("/api/v1/events/ticker/MSFT", params={"limit": 25})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_ticker_events_unknown_ticker(self, client: AsyncClient):
        """Test getting events for unknown ticker returns empty list."""
        response = await client.get("/api/v1/events/ticker/XXXXX")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0


class TestSingleEventEndpoint:
    """Tests for GET /api/v1/events/{event_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_event_not_found(self, client: AsyncClient):
        """Test getting non-existent event returns 404."""
        fake_uuid = str(uuid4())
        response = await client.get(f"/api/v1/events/{fake_uuid}")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_event_invalid_uuid(self, client: AsyncClient):
        """Test getting event with invalid UUID returns 422."""
        response = await client.get("/api/v1/events/not-a-valid-uuid")
        assert response.status_code == 422


class TestEventResponseSchema:
    """Tests for event response schema validation."""

    def test_event_response_fields(self, sample_event_data: dict):
        """Test that sample event data has all expected fields."""
        expected_fields = [
            "id",
            "ticker",
            "event_time",
            "event_type",
            "event_category",
            "headline",
            "summary",
            "source_url",
            "source_name",
            "sentiment_score",
            "sentiment_label",
            "alpha_score",
            "direction",
            "urgency_level",
            "extracted_tickers",
        ]
        for field in expected_fields:
            assert field in sample_event_data, f"Missing field: {field}"

    def test_event_data_types(self, sample_event_data: dict):
        """Test that sample event data has correct types."""
        assert isinstance(sample_event_data["id"], str)
        assert isinstance(sample_event_data["ticker"], str)
        assert isinstance(sample_event_data["headline"], str)
        assert isinstance(sample_event_data["sentiment_score"], (int, float))
        assert isinstance(sample_event_data["alpha_score"], (int, float))
        assert isinstance(sample_event_data["extracted_tickers"], list)
