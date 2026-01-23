"""Rate limiting middleware for the API."""

import hashlib
import time
from collections import defaultdict
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = structlog.get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token bucket rate limiting middleware.
    
    Implements per-client rate limiting with support for different
    subscription tiers.
    """

    # Tier-based rate limits (requests per minute)
    TIER_LIMITS = {
        "starter": 60,
        "professional": 300,
        "team": 600,
        "enterprise": 3000,
        "anonymous": 30,
    }

    # Paths to skip rate limiting
    SKIP_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}

    def __init__(
        self,
        app,
        default_limit: int = 60,
        window_seconds: int = 60,
    ):
        """Initialize rate limiter.

        Args:
            app: FastAPI application
            default_limit: Default requests per window
            window_seconds: Rate limit window in seconds
        """
        super().__init__(app)
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self._storage: dict[str, dict] = defaultdict(lambda: {"tokens": 0, "last_update": 0})

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response object
        """
        # Skip rate limiting for certain paths
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        # Get client identifier
        client_id = self._get_client_id(request)

        # Get rate limit for client
        limit = self._get_limit_for_request(request)

        # Check rate limit
        allowed, remaining, reset_at = self._check_rate_limit(client_id, limit)

        if not allowed:
            logger.warning(
                "Rate limit exceeded",
                client_id=client_id[:16] + "...",
                path=request.url.path,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                    "Retry-After": str(max(1, reset_at - int(time.time()))),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_at)

        return response

    def _get_client_id(self, request: Request) -> str:
        """Get unique client identifier.

        Uses auth token hash if available, otherwise falls back to IP.

        Args:
            request: Incoming request

        Returns:
            Client identifier string
        """
        # Try to use auth token for identification
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return hashlib.sha256(token.encode()).hexdigest()

        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        return hashlib.sha256(ip.encode()).hexdigest()

    def _get_limit_for_request(self, request: Request) -> int:
        """Get rate limit for the request based on subscription tier.

        Args:
            request: Incoming request

        Returns:
            Rate limit (requests per minute)
        """
        # Check if user has subscription tier in state (set by auth dependency)
        tier = getattr(request.state, "subscription_tier", None)
        if tier and tier in self.TIER_LIMITS:
            return self.TIER_LIMITS[tier]

        # Check if authenticated (has Authorization header)
        if request.headers.get("Authorization"):
            return self.TIER_LIMITS.get("starter", self.default_limit)

        # Anonymous user
        return self.TIER_LIMITS.get("anonymous", self.default_limit // 2)

    def _check_rate_limit(
        self,
        client_id: str,
        limit: int,
    ) -> tuple[bool, int, int]:
        """Check and update rate limit for client.

        Implements token bucket algorithm.

        Args:
            client_id: Client identifier
            limit: Rate limit for this client

        Returns:
            Tuple of (allowed, remaining_tokens, reset_timestamp)
        """
        now = time.time()
        window_start = now - self.window_seconds

        client_data = self._storage[client_id]
        last_update = client_data["last_update"]
        tokens = client_data["tokens"]

        # Refill tokens based on time elapsed
        if last_update < window_start:
            # Window has completely reset
            tokens = limit
        else:
            # Partial refill
            elapsed = now - last_update
            refill = int(elapsed * (limit / self.window_seconds))
            tokens = min(limit, tokens + refill)

        # Update last update time
        client_data["last_update"] = now

        # Check if request is allowed
        if tokens > 0:
            client_data["tokens"] = tokens - 1
            reset_at = int(now + self.window_seconds)
            return True, tokens - 1, reset_at
        else:
            client_data["tokens"] = 0
            reset_at = int(now + self.window_seconds)
            return False, 0, reset_at

    def _cleanup_old_entries(self):
        """Remove expired entries from storage."""
        now = time.time()
        cutoff = now - (self.window_seconds * 2)

        expired_keys = [
            key for key, data in self._storage.items()
            if data["last_update"] < cutoff
        ]

        for key in expired_keys:
            del self._storage[key]
