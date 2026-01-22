"""Unified HTTP client with rate limiting and proxy support."""

import asyncio
import time
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .proxy_manager import ProxyManager, get_proxy_manager
from .rate_limiter import RateLimiter, get_rate_limiter
from .user_agent_rotator import UserAgentRotator, get_user_agent_rotator

logger = structlog.get_logger(__name__)


class RequestClient:
    """Unified HTTP client with rate limiting, proxy rotation, and retries."""

    def __init__(
        self,
        rate_limiter: RateLimiter | None = None,
        proxy_manager: ProxyManager | None = None,
        ua_rotator: UserAgentRotator | None = None,
        use_proxy: bool = False,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """Initialize request client.

        Args:
            rate_limiter: Rate limiter instance
            proxy_manager: Proxy manager instance
            ua_rotator: User agent rotator instance
            use_proxy: Whether to use proxy rotation
            timeout: Default request timeout
            max_retries: Maximum retry attempts
        """
        self.rate_limiter = rate_limiter or get_rate_limiter()
        self.proxy_manager = proxy_manager or get_proxy_manager() if use_proxy else None
        self.ua_rotator = ua_rotator or get_user_agent_rotator()
        self.use_proxy = use_proxy
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None
        self._stats = {
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "retries": 0,
            "total_time": 0.0,
        }

    async def __aenter__(self) -> "RequestClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    def _get_headers(self, url: str, headers: dict[str, str] | None = None) -> dict[str, str]:
        """Build request headers.

        Args:
            url: Target URL
            headers: Custom headers

        Returns:
            Merged headers
        """
        from urllib.parse import urlparse
        domain = urlparse(url).netloc

        default_headers = {
            "User-Agent": self.ua_rotator.get_for_domain(domain),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

        if headers:
            default_headers.update(headers)

        return default_headers

    def _get_proxy(self) -> str | None:
        """Get proxy URL if enabled.

        Returns:
            Proxy URL or None
        """
        if self.use_proxy and self.proxy_manager:
            return self.proxy_manager.get_proxy_url()
        return None

    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Make a GET request with rate limiting and retries.

        Args:
            url: Target URL
            headers: Custom headers
            params: Query parameters
            timeout: Request timeout

        Returns:
            HTTP response
        """
        return await self._request("GET", url, headers=headers, params=params, timeout=timeout)

    async def post(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Make a POST request with rate limiting and retries.

        Args:
            url: Target URL
            headers: Custom headers
            json: JSON body
            data: Form data
            timeout: Request timeout

        Returns:
            HTTP response
        """
        return await self._request(
            "POST", url, headers=headers, json=json, data=data, timeout=timeout
        )

    async def _request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Make an HTTP request.

        Args:
            method: HTTP method
            url: Target URL
            headers: Custom headers
            params: Query parameters
            json: JSON body
            data: Form data
            timeout: Request timeout

        Returns:
            HTTP response
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        # Wait for rate limit
        await self.rate_limiter.wait(url)

        request_headers = self._get_headers(url, headers)
        proxy_url = self._get_proxy()
        request_timeout = timeout or self.timeout

        start_time = time.time()
        self._stats["requests"] += 1

        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                # Create a new client for this request if using proxy
                if proxy_url:
                    async with httpx.AsyncClient(
                        proxy=proxy_url,
                        timeout=request_timeout,
                        follow_redirects=True,
                    ) as proxy_client:
                        response = await proxy_client.request(
                            method,
                            url,
                            headers=request_headers,
                            params=params,
                            json=json,
                            data=data,
                        )
                else:
                    response = await self._client.request(
                        method,
                        url,
                        headers=request_headers,
                        params=params,
                        json=json,
                        data=data,
                    )

                elapsed = time.time() - start_time
                self._stats["total_time"] += elapsed

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    retry_seconds = float(retry_after) if retry_after else 60.0

                    self.rate_limiter.report_rate_limit(url, retry_seconds)

                    if self.proxy_manager and proxy_url:
                        self.proxy_manager.report_failure(proxy_url, "429 Rate Limited")

                    logger.warning(
                        "Rate limited",
                        url=url,
                        retry_after=retry_seconds,
                        attempt=attempt + 1,
                    )

                    if attempt < self.max_retries - 1:
                        self._stats["retries"] += 1
                        await asyncio.sleep(min(retry_seconds, 60))
                        continue

                    raise httpx.HTTPStatusError(
                        "Rate limited",
                        request=response.request,
                        response=response,
                    )

                # Report success
                response.raise_for_status()
                self.rate_limiter.report_success(url)

                if self.proxy_manager and proxy_url:
                    self.proxy_manager.report_success(proxy_url, elapsed)

                self._stats["successes"] += 1

                return response

            except httpx.HTTPStatusError as e:
                last_error = e
                self._stats["failures"] += 1

                if self.proxy_manager and proxy_url:
                    self.proxy_manager.report_failure(proxy_url, str(e))

                # Don't retry client errors (4xx) except 429
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise

                if attempt < self.max_retries - 1:
                    self._stats["retries"] += 1
                    wait_time = (2 ** attempt) + (attempt * 0.5)
                    await asyncio.sleep(wait_time)

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                last_error = e
                self._stats["failures"] += 1

                if self.proxy_manager and proxy_url:
                    self.proxy_manager.report_failure(proxy_url, str(e))

                if attempt < self.max_retries - 1:
                    self._stats["retries"] += 1
                    wait_time = (2 ** attempt) + (attempt * 0.5)

                    # Get a new proxy for retry
                    proxy_url = self._get_proxy()

                    await asyncio.sleep(wait_time)

        # All retries exhausted
        if last_error:
            raise last_error

        raise RuntimeError("Request failed after all retries")

    async def fetch_text(self, url: str, **kwargs) -> str:
        """Fetch URL and return text content.

        Args:
            url: Target URL
            **kwargs: Additional request arguments

        Returns:
            Response text
        """
        response = await self.get(url, **kwargs)
        return response.text

    async def fetch_json(self, url: str, **kwargs) -> dict[str, Any]:
        """Fetch URL and return JSON content.

        Args:
            url: Target URL
            **kwargs: Additional request arguments

        Returns:
            Parsed JSON
        """
        response = await self.get(url, **kwargs)
        return response.json()

    def get_stats(self) -> dict[str, Any]:
        """Get client statistics.

        Returns:
            Stats dictionary
        """
        avg_time = (
            self._stats["total_time"] / self._stats["requests"]
            if self._stats["requests"] > 0
            else 0
        )

        return {
            **self._stats,
            "avg_response_time": avg_time,
            "success_rate": (
                self._stats["successes"] / self._stats["requests"]
                if self._stats["requests"] > 0
                else 0
            ),
        }


async def main():
    """Example usage of request client."""
    async with RequestClient(use_proxy=False) as client:
        # Fetch a page
        response = await client.get("https://httpbin.org/get")
        print(f"Status: {response.status_code}")

        # Get stats
        stats = client.get_stats()
        print(f"Stats: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
