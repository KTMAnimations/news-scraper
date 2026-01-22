"""Base scraper class with common functionality."""

import asyncio
import hashlib
import random
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    # Default rate limit (seconds between requests)
    DEFAULT_RATE_LIMIT = 2.0

    # User agent rotation pool
    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]

    def __init__(
        self,
        rate_limit: float | None = None,
        use_proxy: bool = False,
    ):
        """Initialize base scraper.

        Args:
            rate_limit: Seconds between requests (with jitter)
            use_proxy: Whether to use proxy for requests
        """
        self.rate_limit = rate_limit or self.DEFAULT_RATE_LIMIT
        self.use_proxy = use_proxy and settings.proxy_enabled
        self._client: httpx.AsyncClient | None = None
        self._last_request: float = 0
        self._seen_hashes: set[str] = set()

    async def __aenter__(self) -> "BaseScraper":
        """Async context manager entry."""
        proxy_url = None
        if self.use_proxy and settings.proxy_url:
            proxy_url = settings.proxy_url
            if settings.proxy_username and settings.proxy_password:
                # Add auth to proxy URL
                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(settings.proxy_url)
                proxy_url = urlunparse(parsed._replace(
                    netloc=f"{settings.proxy_username}:{settings.proxy_password}@{parsed.netloc}"
                ))

        self._client = httpx.AsyncClient(
            headers=self._get_headers(),
            timeout=30.0,
            follow_redirects=True,
            proxy=proxy_url,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    def _get_headers(self) -> dict[str, str]:
        """Get randomized request headers."""
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def _rate_limit_wait(self) -> None:
        """Wait for rate limit with jitter."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request

        if elapsed < self.rate_limit:
            # Add random jitter (0-50% of rate limit)
            jitter = random.uniform(0, self.rate_limit * 0.5)
            wait_time = self.rate_limit - elapsed + jitter
            await asyncio.sleep(wait_time)

        self._last_request = asyncio.get_event_loop().time()

    def _generate_hash(self, content: str) -> str:
        """Generate hash for deduplication."""
        return hashlib.md5(content.encode()).hexdigest()

    def _is_duplicate(self, content: str) -> bool:
        """Check if content has been seen before.

        Args:
            content: Content to check

        Returns:
            True if duplicate
        """
        content_hash = self._generate_hash(content)

        if content_hash in self._seen_hashes:
            return True

        self._seen_hashes.add(content_hash)

        # Limit cache size
        if len(self._seen_hashes) > 10000:
            self._seen_hashes = set(list(self._seen_hashes)[-5000:])

        return False

    async def fetch(self, url: str, **kwargs) -> httpx.Response:
        """Fetch URL with rate limiting.

        Args:
            url: URL to fetch
            **kwargs: Additional arguments for httpx

        Returns:
            HTTP response
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        await self._rate_limit_wait()

        # Rotate user agent on each request
        self._client.headers["User-Agent"] = random.choice(self.USER_AGENTS)

        response = await self._client.get(url, **kwargs)
        response.raise_for_status()

        return response

    @abstractmethod
    async def scrape(self) -> list[dict[str, Any]]:
        """Scrape data from the source.

        Returns:
            List of scraped items
        """
        pass

    @abstractmethod
    async def stream(self, poll_interval: float = 60.0) -> AsyncIterator[dict[str, Any]]:
        """Stream new items from the source.

        Args:
            poll_interval: Seconds between polls

        Yields:
            New items
        """
        pass

    def normalize_event(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Normalize scraped data to standard event format.

        Args:
            raw_data: Raw scraped data

        Returns:
            Normalized event dictionary
        """
        return {
            "ticker": raw_data.get("ticker", ""),
            "event_type": raw_data.get("event_type", "NEWS"),
            "event_category": raw_data.get("event_category", "NEWS"),
            "headline": raw_data.get("headline", raw_data.get("title", "")),
            "summary": raw_data.get("summary", raw_data.get("description", "")),
            "content": raw_data.get("content", ""),
            "source_url": raw_data.get("url", raw_data.get("link", "")),
            "source_name": raw_data.get("source", self.__class__.__name__),
            "event_time": raw_data.get("published_at", datetime.now(timezone.utc).isoformat()),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "metadata": raw_data.get("metadata", {}),
        }
