"""API Key management routes.

This module provides endpoints for users to create, list, and manage their API keys
for programmatic access to the platform.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.dependencies import CurrentUser, DBSession, require_subscription
from backend.api.security.api_key import generate_api_key, hash_api_key
from backend.storage.timescale.queries import APIKeyQueries

logger = structlog.get_logger(__name__)

router = APIRouter()

# Tier-based API key limits
API_KEY_LIMITS = {
    "free": 1,
    "starter": 2,
    "professional": 5,
    "team": 20,
    "enterprise": 100,
}

# Available scopes
AVAILABLE_SCOPES = ["read", "write", "admin"]


class APIKeyCreate(BaseModel):
    """Request model for creating an API key."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="A descriptive name for the API key",
        examples=["Production Server", "CI/CD Pipeline"],
    )
    scopes: list[Literal["read", "write", "admin"]] = Field(
        default=["read"],
        description="Permissions granted to this key",
    )
    expires_in_days: int | None = Field(
        default=None,
        ge=1,
        le=365,
        description="Number of days until key expires (null for no expiration)",
    )


class APIKeyResponse(BaseModel):
    """Response model for an API key (without the actual key)."""

    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    is_active: bool
    created_at: datetime | None
    last_used_at: datetime | None
    expires_at: datetime | None
    request_count: int


class APIKeyCreatedResponse(BaseModel):
    """Response model when creating an API key (includes the actual key)."""

    id: str
    name: str
    key: str = Field(
        ...,
        description="The full API key. Store this securely - it will not be shown again!",
    )
    key_prefix: str
    scopes: list[str]
    expires_at: datetime | None
    message: str = "Store this key securely. It will not be shown again."


@router.post(
    "",
    response_model=APIKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create API Key",
    description="Generate a new API key for programmatic access. The key is only shown once.",
    responses={
        201: {"description": "API key created successfully"},
        400: {"description": "API key limit reached for subscription tier"},
        401: {"description": "Not authenticated"},
    },
)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    """Create a new API key.

    The full API key is returned only once in the response. Store it securely
    as it cannot be retrieved later.

    Rate limits:
    - Free: 1 API key
    - Starter: 2 API keys
    - Professional: 5 API keys
    - Team: 20 API keys
    - Enterprise: 100 API keys
    """
    queries = APIKeyQueries(db)

    # Check key limit
    user_tier = current_user.subscription_tier or "free"
    max_keys = API_KEY_LIMITS.get(user_tier, 1)
    current_count = await queries.count_user_api_keys(current_user.id)

    if current_count >= max_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API key limit reached ({max_keys}) for {user_tier} tier. "
                   f"Upgrade your subscription to create more keys.",
        )

    # Validate scopes - only enterprise can create admin keys
    if "admin" in key_data.scopes and user_tier != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin scope is only available for Enterprise tier",
        )

    # Generate the key
    full_key, key_prefix = generate_api_key()
    key_hash = hash_api_key(full_key)

    # Calculate expiration
    expires_at = None
    if key_data.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=key_data.expires_in_days)

    # Create the key record
    api_key = await queries.create_api_key({
        "user_id": current_user.id,
        "name": key_data.name,
        "key_prefix": key_prefix,
        "key_hash": key_hash,
        "scopes": key_data.scopes,
        "expires_at": expires_at,
    })

    await db.commit()

    logger.info(
        "API key created",
        user_id=str(current_user.id),
        key_id=str(api_key.id),
        scopes=key_data.scopes,
    )

    return APIKeyCreatedResponse(
        id=str(api_key.id),
        name=api_key.name,
        key=full_key,
        key_prefix=key_prefix,
        scopes=api_key.scopes or [],
        expires_at=expires_at,
    )


@router.get(
    "",
    response_model=list[APIKeyResponse],
    summary="List API Keys",
    description="Get all API keys for the current user.",
)
async def list_api_keys(
    current_user: CurrentUser,
    db: DBSession,
):
    """List all API keys for the current user.

    Note: The actual key values are not returned for security reasons.
    Only the prefix is shown for identification.
    """
    queries = APIKeyQueries(db)
    keys = await queries.get_user_api_keys(current_user.id)

    return [
        APIKeyResponse(
            id=str(key.id),
            name=key.name,
            key_prefix=key.key_prefix,
            scopes=key.scopes or [],
            is_active=key.is_active,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
            expires_at=key.expires_at,
            request_count=key.request_count or 0,
        )
        for key in keys
    ]


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke API Key",
    description="Permanently revoke an API key. This action cannot be undone.",
    responses={
        204: {"description": "API key revoked successfully"},
        404: {"description": "API key not found"},
    },
)
async def revoke_api_key(
    key_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """Revoke an API key.

    This permanently deactivates the key. Any requests using this key
    will be rejected immediately.
    """
    from uuid import UUID

    try:
        key_uuid = UUID(key_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid key ID format",
        )

    queries = APIKeyQueries(db)
    success = await queries.deactivate_api_key(key_uuid, current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    await db.commit()

    logger.info(
        "API key revoked",
        user_id=str(current_user.id),
        key_id=key_id,
    )


@router.post(
    "/{key_id}/rotate",
    response_model=APIKeyCreatedResponse,
    summary="Rotate API Key",
    description="Generate a new key while keeping the same configuration. The old key is immediately revoked.",
    responses={
        200: {"description": "New API key generated"},
        404: {"description": "API key not found"},
    },
)
async def rotate_api_key(
    key_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """Rotate an API key.

    This creates a new key with the same name, scopes, and expiration settings,
    then revokes the old key. Use this for regular security rotation.
    """
    from uuid import UUID

    try:
        key_uuid = UUID(key_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid key ID format",
        )

    queries = APIKeyQueries(db)
    old_key = await queries.get_api_key_by_id(key_uuid)

    if not old_key or old_key.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    # Generate new key
    full_key, key_prefix = generate_api_key()
    key_hash = hash_api_key(full_key)

    # Create new key with same settings
    new_key = await queries.create_api_key({
        "user_id": current_user.id,
        "name": old_key.name,
        "key_prefix": key_prefix,
        "key_hash": key_hash,
        "scopes": old_key.scopes,
        "expires_at": old_key.expires_at,
        "rate_limit_override": old_key.rate_limit_override,
    })

    # Deactivate old key
    await queries.deactivate_api_key(key_uuid, current_user.id)

    await db.commit()

    logger.info(
        "API key rotated",
        user_id=str(current_user.id),
        old_key_id=key_id,
        new_key_id=str(new_key.id),
    )

    return APIKeyCreatedResponse(
        id=str(new_key.id),
        name=new_key.name,
        key=full_key,
        key_prefix=key_prefix,
        scopes=new_key.scopes or [],
        expires_at=new_key.expires_at,
    )


@router.get(
    "/limits",
    summary="Get API Key Limits",
    description="Get the API key limits for the current user's subscription tier.",
)
async def get_api_key_limits(
    current_user: CurrentUser,
    db: DBSession,
):
    """Get API key limits for the current user."""
    queries = APIKeyQueries(db)

    user_tier = current_user.subscription_tier or "free"
    max_keys = API_KEY_LIMITS.get(user_tier, 1)
    current_count = await queries.count_user_api_keys(current_user.id)

    return {
        "tier": user_tier,
        "max_keys": max_keys,
        "current_count": current_count,
        "available": max_keys - current_count,
        "available_scopes": (
            AVAILABLE_SCOPES if user_tier == "enterprise"
            else ["read", "write"]
        ),
    }
