"""API Key authentication module.

This module provides utilities for generating, hashing, and validating API keys
for programmatic access to the API.
"""

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_db
from backend.storage.timescale.models import APIKey, User
from backend.storage.timescale.queries import APIKeyQueries

logger = structlog.get_logger(__name__)

# API Key header name
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Key format: prefix_secret (e.g., "malf_a1b2c3d4e5f6g7h8...")
API_KEY_PREFIX = "malf"  # Micro-Alpha Financial
API_KEY_LENGTH = 32  # Length of the secret portion


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (full_key, key_prefix) where:
        - full_key: The complete API key to give to the user (only shown once)
        - key_prefix: First 8 characters for identification
    """
    # Generate cryptographically secure random bytes
    secret = secrets.token_hex(API_KEY_LENGTH)

    # Create full key with prefix
    full_key = f"{API_KEY_PREFIX}_{secret}"

    # Extract prefix for storage (first 8 chars of secret for display)
    key_prefix = secret[:8]

    return full_key, key_prefix


def hash_api_key(api_key: str) -> str:
    """Hash an API key for secure storage.

    Args:
        api_key: The full API key string

    Returns:
        SHA256 hash of the API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """Verify an API key against a stored hash.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        provided_key: The API key provided by the user
        stored_hash: The stored hash to compare against

    Returns:
        True if the key is valid
    """
    provided_hash = hash_api_key(provided_key)
    return secrets.compare_digest(provided_hash, stored_hash)


class APIKeyAuth:
    """API Key authentication dependency for FastAPI.

    Usage:
        @router.get("/endpoint")
        async def endpoint(
            api_key_data: APIKeyData = Depends(APIKeyAuth())
        ):
            ...

        @router.get("/scoped-endpoint")
        async def scoped_endpoint(
            api_key_data: APIKeyData = Depends(APIKeyAuth(required_scopes=["write"]))
        ):
            ...
    """

    def __init__(
        self,
        required_scopes: list[str] | None = None,
        auto_error: bool = True,
    ):
        """Initialize API Key auth dependency.

        Args:
            required_scopes: List of required scopes (e.g., ["read", "write"])
            auto_error: Whether to raise HTTPException on auth failure
        """
        self.required_scopes = required_scopes or []
        self.auto_error = auto_error

    async def __call__(
        self,
        request: Request,
        api_key: str | None = Depends(API_KEY_HEADER),
        db: AsyncSession = Depends(get_db),
    ) -> tuple[User, APIKey] | None:
        """Validate API key and return user and key data.

        Args:
            request: FastAPI request object
            api_key: API key from header
            db: Database session

        Returns:
            Tuple of (User, APIKey) if valid, None if auto_error is False

        Raises:
            HTTPException: If authentication fails and auto_error is True
        """
        if not api_key:
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key required",
                    headers={"WWW-Authenticate": "ApiKey"},
                )
            return None

        # Validate key format
        if not api_key.startswith(f"{API_KEY_PREFIX}_"):
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key format",
                    headers={"WWW-Authenticate": "ApiKey"},
                )
            return None

        # Hash the key and look it up
        key_hash = hash_api_key(api_key)
        queries = APIKeyQueries(db)
        api_key_record = await queries.get_api_key_by_hash(key_hash)

        if not api_key_record:
            logger.warning("Invalid API key attempted", key_prefix=api_key[5:13])
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or inactive API key",
                    headers={"WWW-Authenticate": "ApiKey"},
                )
            return None

        # Check expiration
        if api_key_record.expires_at:
            if api_key_record.expires_at < datetime.now(timezone.utc):
                logger.warning(
                    "Expired API key used",
                    key_id=str(api_key_record.id),
                    expired_at=api_key_record.expires_at.isoformat(),
                )
                if self.auto_error:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="API key has expired",
                        headers={"WWW-Authenticate": "ApiKey"},
                    )
                return None

        # Check scopes
        key_scopes = api_key_record.scopes or []
        for required_scope in self.required_scopes:
            if required_scope not in key_scopes and "admin" not in key_scopes:
                logger.warning(
                    "Insufficient API key scope",
                    key_id=str(api_key_record.id),
                    required=required_scope,
                    has_scopes=key_scopes,
                )
                if self.auto_error:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"API key missing required scope: {required_scope}",
                    )
                return None

        # Get the user
        from backend.storage.timescale.queries import UserQueries
        user_queries = UserQueries(db)
        user = await user_queries.get_user_by_id(api_key_record.user_id)

        if not user or not user.is_active:
            logger.warning(
                "API key for inactive/missing user",
                key_id=str(api_key_record.id),
                user_id=str(api_key_record.user_id),
            )
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User account is inactive",
                    headers={"WWW-Authenticate": "ApiKey"},
                )
            return None

        # Update usage tracking (non-blocking)
        client_ip = request.client.host if request.client else None
        await queries.update_api_key_usage(api_key_record.id, client_ip)

        # Store subscription tier in request state for rate limiting
        request.state.subscription_tier = user.subscription_tier
        request.state.api_key_rate_limit = api_key_record.rate_limit_override

        logger.debug(
            "API key authenticated",
            key_id=str(api_key_record.id),
            user_id=str(user.id),
            scopes=key_scopes,
        )

        return user, api_key_record


# Type alias for cleaner function signatures
APIKeyData = Annotated[tuple[User, APIKey], Depends(APIKeyAuth())]
APIKeyDataOptional = Annotated[tuple[User, APIKey] | None, Depends(APIKeyAuth(auto_error=False))]
