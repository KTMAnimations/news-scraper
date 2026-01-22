"""Per-domain rate limiting for web scraping."""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting a domain."""

    requests_per_second: float = 1.0
    burst_size: int = 5
    retry_after: float = 60.0  # Seconds to wait after 429

    @property
    def min_interval(self) -> float:
        """Minimum interval between requests."""
        return 1.0 / self.requests_per_second


@dataclass
class DomainState:
    """State tracking for a single domain."""

    config: RateLimitConfig
    last_request_time: float = 0.0
    tokens: float = 0.0
    last_token_time: float = 0.0
    retry_until: float = 0.0
    request_count: int = 0
    error_count: int = 0


class RateLimiter:
    """Token bucket rate limiter with per-domain tracking."""

    # Default rate limits for known domains
    DEFAULT_LIMITS = {
        "sec.gov": RateLimitConfig(requests_per_second=10, burst_size=10),
        "data.sec.gov": RateLimitConfig(requests_per_second=10, burst_size=10),
        "otcmarkets.com": RateLimitConfig(requests_per_second=0.5, burst_size=3),
        "reddit.com": RateLimitConfig(requests_per_second=1, burst_size=5),
        "twitter.com": RateLimitConfig(requests_per_second=0.5, burst_size=2),
        "api.stocktwits.com": RateLimitConfig(requests_per_second=1, burst_size=10),
    }

    # Global default
    DEFAULT_CONFIG = RateLimitConfig(requests_per_second=2.0, burst_size=5)

    def __init__(
        self,
        domain_limits: dict[str, RateLimitConfig] | None = None,
        default_config: RateLimitConfig | None = None,
    ):
        """Initialize rate limiter.

        Args:
            domain_limits: Custom per-domain rate limits
            default_config: Default config for unknown domains
        """
        self.domain_limits = {**self.DEFAULT_LIMITS}
        if domain_limits:
            self.domain_limits.update(domain_limits)

        self.default_config = default_config or self.DEFAULT_CONFIG
        self._domain_states: dict[str, DomainState] = {}
        self._lock = asyncio.Lock()

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL.

        Args:
            url: Full URL

        Returns:
            Domain string
        """
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        # Remove port if present
        domain = domain.split(":")[0]
        return domain.lower()

    def _get_state(self, domain: str) -> DomainState:
        """Get or create state for a domain.

        Args:
            domain: Domain string

        Returns:
            DomainState instance
        """
        if domain not in self._domain_states:
            config = self.domain_limits.get(domain, self.default_config)
            self._domain_states[domain] = DomainState(
                config=config,
                tokens=config.burst_size,
                last_token_time=time.time(),
            )
        return self._domain_states[domain]

    def _refill_tokens(self, state: DomainState) -> None:
        """Refill tokens based on elapsed time.

        Args:
            state: Domain state to update
        """
        now = time.time()
        elapsed = now - state.last_token_time
        new_tokens = elapsed * state.config.requests_per_second

        state.tokens = min(state.config.burst_size, state.tokens + new_tokens)
        state.last_token_time = now

    async def acquire(self, url: str, timeout: float = 30.0) -> bool:
        """Acquire permission to make a request.

        Args:
            url: URL to request
            timeout: Maximum time to wait

        Returns:
            True if acquired, False if timeout
        """
        domain = self._get_domain(url)
        start_time = time.time()

        while True:
            async with self._lock:
                state = self._get_state(domain)

                # Check if we're in retry-after period
                now = time.time()
                if state.retry_until > now:
                    wait_time = state.retry_until - now
                    logger.debug(
                        "Rate limited, waiting for retry-after",
                        domain=domain,
                        wait_time=wait_time,
                    )
                    # Don't hold lock while waiting
                else:
                    # Refill tokens
                    self._refill_tokens(state)

                    if state.tokens >= 1.0:
                        state.tokens -= 1.0
                        state.last_request_time = now
                        state.request_count += 1
                        return True

            # Check timeout
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                logger.warning("Rate limit acquire timeout", domain=domain)
                return False

            # Wait before retrying
            wait_time = min(
                state.config.min_interval,
                state.retry_until - time.time() if state.retry_until > time.time() else 0.1,
            )
            await asyncio.sleep(max(0.1, wait_time))

    async def wait(self, url: str) -> None:
        """Wait until a request can be made.

        Args:
            url: URL to request
        """
        await self.acquire(url, timeout=float("inf"))

    def report_rate_limit(self, url: str, retry_after: float | None = None) -> None:
        """Report that a rate limit was hit (429 response).

        Args:
            url: URL that was rate limited
            retry_after: Seconds to wait (from Retry-After header)
        """
        domain = self._get_domain(url)
        state = self._get_state(domain)

        state.error_count += 1
        retry = retry_after or state.config.retry_after
        state.retry_until = time.time() + retry

        logger.warning(
            "Rate limit hit",
            domain=domain,
            retry_after=retry,
            error_count=state.error_count,
        )

    def report_success(self, url: str) -> None:
        """Report successful request.

        Args:
            url: URL that succeeded
        """
        domain = self._get_domain(url)
        state = self._get_state(domain)
        # Reset error count on success
        state.error_count = max(0, state.error_count - 1)

    def set_domain_limit(
        self,
        domain: str,
        requests_per_second: float,
        burst_size: int | None = None,
    ) -> None:
        """Set rate limit for a domain.

        Args:
            domain: Domain to configure
            requests_per_second: Max requests per second
            burst_size: Max burst size
        """
        config = RateLimitConfig(
            requests_per_second=requests_per_second,
            burst_size=burst_size or int(requests_per_second * 5),
        )
        self.domain_limits[domain.lower()] = config

        # Update existing state if present
        if domain in self._domain_states:
            self._domain_states[domain].config = config

        logger.info(
            "Set domain rate limit",
            domain=domain,
            rps=requests_per_second,
            burst=config.burst_size,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics.

        Returns:
            Stats dictionary
        """
        stats = {
            "domains": {},
            "total_requests": 0,
            "total_errors": 0,
        }

        for domain, state in self._domain_states.items():
            stats["domains"][domain] = {
                "request_count": state.request_count,
                "error_count": state.error_count,
                "tokens": state.tokens,
                "rps_limit": state.config.requests_per_second,
            }
            stats["total_requests"] += state.request_count
            stats["total_errors"] += state.error_count

        return stats


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


class RateLimitedContext:
    """Context manager for rate-limited requests."""

    def __init__(self, url: str, limiter: RateLimiter | None = None):
        """Initialize context.

        Args:
            url: URL to rate limit
            limiter: Rate limiter instance
        """
        self.url = url
        self.limiter = limiter or get_rate_limiter()
        self._success = False

    async def __aenter__(self) -> "RateLimitedContext":
        """Acquire rate limit permission."""
        await self.limiter.wait(self.url)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Report result."""
        if exc_type is None and self._success:
            self.limiter.report_success(self.url)

    def success(self) -> None:
        """Mark request as successful."""
        self._success = True

    def rate_limited(self, retry_after: float | None = None) -> None:
        """Mark request as rate limited."""
        self.limiter.report_rate_limit(self.url, retry_after)
