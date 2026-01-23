"""Pytest configuration and fixtures."""

import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.storage.timescale.connection import Base


# Test database URL (use SQLite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with mocked database dependency."""
    from backend.api.main import app
    from backend.api.dependencies import get_db

    # Override the database dependency
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    # Mock the lifespan context to skip database initialization
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture
def sample_event_data() -> dict:
    """Create sample event data for testing."""
    return {
        "id": str(uuid4()),
        "ticker": "AAPL",
        "event_time": datetime.now(timezone.utc).isoformat(),
        "event_type": "EARNINGS_BEAT",
        "event_category": "EARNINGS",
        "headline": "Apple Reports Strong Q4 Earnings",
        "summary": "Apple Inc. exceeded analyst expectations with record revenue.",
        "content": "Full content of the earnings report...",
        "source_url": "https://example.com/aapl-earnings",
        "source_name": "SEC EDGAR",
        "sentiment_score": 0.75,
        "sentiment_label": "positive",
        "sentiment_confidence": 0.92,
        "alpha_score": 0.65,
        "direction": "BULLISH",
        "urgency_level": "high",
        "extracted_tickers": ["AAPL"],
        "extracted_companies": ["Apple Inc."],
        "extracted_people": ["Tim Cook"],
        "metadata": {},
    }


@pytest.fixture
def sample_user_data() -> dict:
    """Create sample user data for testing."""
    return {
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User",
    }


@pytest.fixture
def sample_alert_data() -> dict:
    """Create sample alert data for testing."""
    return {
        "name": "High Alpha Alert",
        "ticker": "AAPL",
        "min_alpha_score": 0.5,
        "urgency_levels": ["critical", "high"],
        "direction": "BULLISH",
        "delivery_method": "email",
    }


@pytest.fixture
def sample_filing_data() -> dict:
    """Create sample SEC filing data for testing."""
    return {
        "id": "0001234567-24-000001",
        "filing_type": "4",
        "filing_category": "INSIDER_TRADE",
        "cik": "1234567",
        "company_name": "Test Corp",
        "title": "FORM 4 - Test Corp",
        "link": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=1234567",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1234567/000123456724000001",
        "filing_time": datetime.now(timezone.utc).isoformat(),
        "is_critical": True,
        "source": "sec_edgar",
    }


@pytest.fixture
def sample_social_post_data() -> dict:
    """Create sample social media post data for testing."""
    return {
        "post_id": "abc123",
        "title": "Check out $AAPL - great earnings!",
        "content": "Apple just crushed earnings. This stock is going to the moon!",
        "author": "test_user",
        "subreddit": "pennystocks",
        "url": "https://reddit.com/r/pennystocks/abc123",
        "score": 150,
        "upvote_ratio": 0.92,
        "num_comments": 45,
        "tickers": ["AAPL"],
        "ticker": "AAPL",
        "engagement_score": 0.35,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "reddit",
        "event_type": "SOCIAL_MENTION",
    }


# Mocks for external services
@pytest.fixture
def mock_redis(mocker):
    """Mock Redis client."""
    mock = mocker.MagicMock()
    mock.publish = mocker.AsyncMock(return_value=1)
    mock.get = mocker.AsyncMock(return_value=None)
    mock.set = mocker.AsyncMock(return_value=True)
    mock.aclose = mocker.AsyncMock()
    return mock


@pytest.fixture
def mock_opensearch(mocker):
    """Mock OpenSearch client."""
    mock = mocker.MagicMock()
    mock.search = mocker.AsyncMock(return_value={
        "hits": {"total": {"value": 0}, "hits": []}
    })
    mock.index = mocker.AsyncMock(return_value={"result": "created"})
    mock.bulk = mocker.AsyncMock(return_value={"errors": False})
    return mock
