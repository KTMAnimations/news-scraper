"""Rate limiting middleware for API endpoints."""

import time
from typing import Callable

import structlog
from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import settings

logger = structlog.get_logger(__name__)


# Rate limits per subscription tier (requests per minute)
TIER_LIMITS = {
    "starter": 60,       # 1 req/sec
    "professional": 300,  # 5 req/sec
    "team": 600,         # 10 req/sec
    "enterprise": 3000,  # 50 req/sec
    "anonymous": 30,     # 0.5 req/sec (unauthenticated)
}

# In-memory rate limit storage (use Redis in production)
_rate_limit_storage: dict[str, dict] = {}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using sliding window algorithm."""

    def __init__(self, app, default_limit: int = 60, window_seconds: int = 60):
        """Initialize rate limiter.

        Args:
            app: FastAPI application
            default_limit: Default requests per window
            window_seconds: Window size in seconds
        """
        super().__init__(app)
        self.default_limit = default_limit
        self.window_seconds = window_seconds

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response
        """
        # Skip rate limiting for health checks and docs
        if request.url.path in ("/health", "/", "/docs", "/openapi.json"):
            return await call_next(request)

        # Get client identifier
        client_id = self._get_client_id(request)

        # Get rate limit for this client
        limit = self._get_limit(request)

        # Check rate limit
        is_allowed, remaining, reset_time = self._check_rate_limit(client_id, limit)

        if not is_allowed:
            logger.warning(
                "Rate limit exceeded",
                client_id=client_id[:20] + "...",
                limit=limit,
                path=request.url.path,
            )
            return Response(
                content='{"detail": "Rate limit exceeded. Please try again later."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(reset_time - int(time.time())),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response

    def _get_client_id(self, request: Request) -> str:
        """Get unique client identifier.

        Args:
            request: Request object

        Returns:
            Client identifier string
        """
        # Try to get user ID from auth token
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            # Use token hash as identifier (don't store actual token)
            import hashlib
            return f"user:{hashlib.md5(token.encode()).hexdigest()}"

        # Fall back to IP address
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        return f"ip:{ip}"

    def _get_limit(self, request: Request) -> int:
        """Get rate limit for request based on subscription tier.

        Args:
            request: Request object

        Returns:
            Rate limit (requests per minute)
        """
        # In production, decode JWT and get tier
        # For now, use default or anonymous limit
        auth_header = request.headers.get("authorization", "")

        if auth_header.startswith("Bearer "):
            # Authenticated user - would look up tier from JWT
            # Default to starter tier
            return TIER_LIMITS.get("starter", self.default_limit)

        return TIER_LIMITS.get("anonymous", 30)

    def _check_rate_limit(
        self,
        client_id: str,
        limit: int,
    ) -> tuple[bool, int, int]:
        """Check if request is within rate limit.

        Args:
            client_id: Client identifier
            limit: Rate limit

        Returns:
            Tuple of (is_allowed, remaining_requests, reset_timestamp)
        """
        current_time = int(time.time())
        window_start = current_time - self.window_seconds + 1
        window_end = current_time + self.window_seconds

        # Get or create client record
        if client_id not in _rate_limit_storage:
            _rate_limit_storage[client_id] = {
                "requests": [],
                "window_start": current_time,
            }

        record = _rate_limit_storage[client_id]

        # Remove expired requests
        record["requests"] = [
            ts for ts in record["requests"]
            if ts >= window_start
        ]

        # Check if limit exceeded
        request_count = len(record["requests"])

        if request_count >= limit:
            reset_time = record["requests"][0] + self.window_seconds
            return False, 0, reset_time

        # Add current request
        record["requests"].append(current_time)
        remaining = limit - len(record["requests"])

        # Calculate reset time
        reset_time = current_time + self.window_seconds

        # Cleanup old entries periodically
        if len(_rate_limit_storage) > 10000:
            self._cleanup_storage()

        return True, remaining, reset_time

    def _cleanup_storage(self) -> None:
        """Remove old entries from storage."""
        current_time = int(time.time())
        cutoff = current_time - self.window_seconds * 2

        keys_to_remove = []
        for client_id, record in _rate_limit_storage.items():
            if not record["requests"] or max(record["requests"]) < cutoff:
                keys_to_remove.append(client_id)

        for key in keys_to_remove:
            del _rate_limit_storage[key]

        logger.debug("Rate limit storage cleanup", removed=len(keys_to_remove))


class RedisRateLimiter:
    """Rate limiter using Redis for distributed rate limiting."""

    def __init__(
        self,
        redis_url: str | None = None,
        default_limit: int = 60,
        window_seconds: int = 60,
    ):
        """Initialize Redis rate limiter.

        Args:
            redis_url: Redis connection URL
            default_limit: Default requests per window
            window_seconds: Window size in seconds
        """
        self.redis_url = redis_url or str(settings.redis_url)
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self._redis = None

    async def _get_redis(self):
        """Get Redis client."""
        if self._redis is None:
            import redis.asyncio as redis
            self._redis = redis.from_url(self.redis_url)
        return self._redis

    async def is_allowed(
        self,
        client_id: str,
        limit: int | None = None,
    ) -> tuple[bool, int, int]:
        """Check if request is within rate limit.

        Args:
            client_id: Client identifier
            limit: Rate limit (uses default if not specified)

        Returns:
            Tuple of (is_allowed, remaining_requests, reset_timestamp)
        """
        limit = limit or self.default_limit
        redis_client = await self._get_redis()

        current_time = int(time.time())
        key = f"ratelimit:{client_id}"

        # Use Redis sorted set for sliding window
        pipe = redis_client.pipeline()

        # Remove old entries
        window_start = current_time - self.window_seconds
        pipe.zremrangebyscore(key, 0, window_start)

        # Count current requests
        pipe.zcard(key)

        # Add current request
        pipe.zadd(key, {str(current_time): current_time})

        # Set expiry
        pipe.expire(key, self.window_seconds * 2)

        results = await pipe.execute()
        request_count = results[1]

        if request_count >= limit:
            # Get oldest request time for reset
            oldest = await redis_client.zrange(key, 0, 0, withscores=True)
            if oldest:
                reset_time = int(oldest[0][1]) + self.window_seconds
            else:
                reset_time = current_time + self.window_seconds
            return False, 0, reset_time

        remaining = limit - request_count - 1
        reset_time = current_time + self.window_seconds

        return True, remaining, reset_time

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()


# Dependency for route-level rate limiting
async def rate_limit_dependency(
    request: Request,
    limit: int = 60,
    window: int = 60,
) -> None:
    """FastAPI dependency for rate limiting specific routes.

    Args:
        request: Request object
        limit: Requests per window
        window: Window size in seconds

    Raises:
        HTTPException: If rate limit exceeded
    """
    # Get client ID
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        import hashlib
        client_id = f"user:{hashlib.md5(auth_header[7:].encode()).hexdigest()}"
    else:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        client_id = f"ip:{ip}"

    # Check rate limit
    key = f"{client_id}:{request.url.path}"
    current_time = int(time.time())

    if key not in _rate_limit_storage:
        _rate_limit_storage[key] = {"requests": [], "window_start": current_time}

    record = _rate_limit_storage[key]
    window_start = current_time - window

    # Remove expired
    record["requests"] = [ts for ts in record["requests"] if ts >= window_start]

    if len(record["requests"]) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for this endpoint",
        )

    record["requests"].append(current_time)
