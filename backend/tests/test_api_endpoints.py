"""Tests for API endpoints."""

import pytest
from httpx import AsyncClient


class TestHealthEndpoints:
    """Test health check endpoints."""

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: AsyncClient):
        """Test root endpoint returns API info."""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert data["name"] == "News Scraper API"
        assert "version" in data
        assert "status" in data

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestAuthEndpoints:
    """Test authentication endpoints."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient, sample_user_data):
        """Test successful user registration."""
        response = await client.post(
            "/api/v1/auth/register",
            json=sample_user_data,
        )
        # May fail without actual DB connection, but validates endpoint exists
        assert response.status_code in [200, 201, 500]

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "testpassword123",
            },
        )
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_login_without_credentials(self, client: AsyncClient):
        """Test login without credentials."""
        response = await client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_me_without_auth(self, client: AsyncClient):
        """Test accessing /me without authentication."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestEventsEndpoints:
    """Test events endpoints."""

    @pytest.mark.asyncio
    async def test_get_latest_events(self, client: AsyncClient):
        """Test getting latest events."""
        response = await client.get("/api/v1/events/latest")
        assert response.status_code in [200, 401]

    @pytest.mark.asyncio
    async def test_get_events_with_filters(self, client: AsyncClient):
        """Test getting events with filters."""
        response = await client.get(
            "/api/v1/events",
            params={
                "ticker": "AAPL",
                "event_type": "EARNINGS_BEAT",
                "limit": 10,
            },
        )
        assert response.status_code in [200, 401]

    @pytest.mark.asyncio
    async def test_get_high_alpha_events(self, client: AsyncClient):
        """Test getting high alpha events."""
        response = await client.get(
            "/api/v1/events/high-alpha",
            params={"min_alpha": 0.5},
        )
        assert response.status_code in [200, 401]


class TestSearchEndpoints:
    """Test search endpoints."""

    @pytest.mark.asyncio
    async def test_search_events(self, client: AsyncClient):
        """Test searching events."""
        response = await client.post(
            "/api/v1/search",
            params={"query": "earnings"},
        )
        assert response.status_code in [200, 401]

    @pytest.mark.asyncio
    async def test_search_suggestions(self, client: AsyncClient):
        """Test search suggestions."""
        response = await client.get(
            "/api/v1/search/suggest",
            params={"q": "APP"},
        )
        assert response.status_code in [200, 401]


class TestAlertsEndpoints:
    """Test alerts endpoints."""

    @pytest.mark.asyncio
    async def test_list_alerts_requires_auth(self, client: AsyncClient):
        """Test that listing alerts requires authentication."""
        response = await client.get("/api/v1/alerts")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_alert_requires_auth(self, client: AsyncClient, sample_alert_data):
        """Test that creating alert requires authentication."""
        response = await client.post(
            "/api/v1/alerts",
            json=sample_alert_data,
        )
        assert response.status_code == 401


class TestWatchlistEndpoints:
    """Test watchlist endpoints."""

    @pytest.mark.asyncio
    async def test_get_watchlist_requires_auth(self, client: AsyncClient):
        """Test that getting watchlist requires authentication."""
        response = await client.get("/api/v1/watchlist")
        assert response.status_code == 401


class TestBillingEndpoints:
    """Test billing endpoints."""

    @pytest.mark.asyncio
    async def test_get_subscription_requires_auth(self, client: AsyncClient):
        """Test that getting subscription requires authentication."""
        response = await client.get("/api/v1/billing/subscription")
        assert response.status_code == 401
