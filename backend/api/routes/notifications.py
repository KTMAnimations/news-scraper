"""Notification routes for FCM token management and preferences."""

from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.dependencies import CurrentUser, DBSession
from backend.config import settings
from backend.storage.timescale.models import User

logger = structlog.get_logger(__name__)

router = APIRouter()


# Request/Response models
class FCMTokenRegister(BaseModel):
    """FCM token registration request."""

    token: str = Field(..., min_length=10, description="FCM device token")
    device_info: dict[str, Any] | None = Field(
        default=None,
        description="Optional device information (platform, browser, etc.)"
    )


class FCMTokenUnregister(BaseModel):
    """FCM token unregistration request."""

    token: str = Field(..., min_length=10, description="FCM device token to remove")


class NotificationPreferences(BaseModel):
    """Notification preferences model."""

    push_enabled: bool | None = Field(default=None, description="Enable push notifications")
    realtime_alerts: bool | None = Field(default=None, description="Real-time alert notifications")
    high_alpha_signals: bool | None = Field(default=None, description="High alpha signal notifications")
    email_alerts: bool | None = Field(default=None, description="Email alert notifications")
    daily_digest: bool | None = Field(default=None, description="Daily digest emails")
    weekly_report: bool | None = Field(default=None, description="Weekly report emails")
    product_updates: bool | None = Field(default=None, description="Product update emails")
    min_alpha_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum alpha score for notifications"
    )


class NotificationPreferencesResponse(BaseModel):
    """Notification preferences response."""

    push_enabled: bool
    realtime_alerts: bool
    high_alpha_signals: bool
    email_alerts: bool
    daily_digest: bool
    weekly_report: bool
    product_updates: bool
    min_alpha_score: float


class StatusResponse(BaseModel):
    """Generic status response."""

    status: str
    message: str | None = None


# Default notification preferences
DEFAULT_PREFERENCES = {
    "push_enabled": True,
    "realtime_alerts": True,
    "high_alpha_signals": True,
    "email_alerts": True,
    "daily_digest": True,
    "weekly_report": False,
    "product_updates": False,
    "min_alpha_score": 0.7,
}


@router.post("/fcm/register", response_model=StatusResponse)
async def register_fcm_token(
    data: FCMTokenRegister,
    current_user: CurrentUser,
    db: DBSession,
):
    """Register an FCM token for push notifications.

    This endpoint stores the FCM token for the current user, allowing
    push notifications to be sent to their device.

    Args:
        data: FCM token registration data
        current_user: Authenticated user
        db: Database session

    Returns:
        Status response
    """
    try:
        # Get current tokens
        current_tokens = current_user.fcm_tokens or []

        # Check if token already exists
        token_exists = False
        for i, existing in enumerate(current_tokens):
            if isinstance(existing, dict) and existing.get("token") == data.token:
                # Update existing token info
                current_tokens[i] = {
                    "token": data.token,
                    "device_info": data.device_info,
                    "registered_at": existing.get("registered_at"),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                token_exists = True
                break
            elif isinstance(existing, str) and existing == data.token:
                # Migrate old format to new format
                current_tokens[i] = {
                    "token": data.token,
                    "device_info": data.device_info,
                    "registered_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                token_exists = True
                break

        if not token_exists:
            # Add new token
            new_token = {
                "token": data.token,
                "device_info": data.device_info,
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            current_tokens.append(new_token)

        # Update user's FCM tokens
        current_user.fcm_tokens = current_tokens
        await db.commit()

        logger.info(
            "FCM token registered",
            user_id=str(current_user.id),
            token_count=len(current_tokens),
        )

        return StatusResponse(
            status="success",
            message="FCM token registered successfully",
        )

    except Exception as e:
        logger.error(
            "Failed to register FCM token",
            user_id=str(current_user.id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register FCM token",
        )


@router.post("/fcm/unregister", response_model=StatusResponse)
async def unregister_fcm_token(
    data: FCMTokenUnregister,
    current_user: CurrentUser,
    db: DBSession,
):
    """Unregister an FCM token.

    This endpoint removes the FCM token from the user's registered tokens,
    stopping push notifications to that device.

    Args:
        data: FCM token unregistration data
        current_user: Authenticated user
        db: Database session

    Returns:
        Status response
    """
    try:
        current_tokens = current_user.fcm_tokens or []

        # Filter out the token to remove
        new_tokens = []
        removed = False
        for existing in current_tokens:
            if isinstance(existing, dict):
                if existing.get("token") != data.token:
                    new_tokens.append(existing)
                else:
                    removed = True
            elif isinstance(existing, str):
                if existing != data.token:
                    new_tokens.append(existing)
                else:
                    removed = True

        if not removed:
            return StatusResponse(
                status="not_found",
                message="Token not found in registered tokens",
            )

        # Update user's FCM tokens
        current_user.fcm_tokens = new_tokens
        await db.commit()

        logger.info(
            "FCM token unregistered",
            user_id=str(current_user.id),
            token_count=len(new_tokens),
        )

        return StatusResponse(
            status="success",
            message="FCM token unregistered successfully",
        )

    except Exception as e:
        logger.error(
            "Failed to unregister FCM token",
            user_id=str(current_user.id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unregister FCM token",
        )


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    current_user: CurrentUser,
):
    """Get notification preferences for the current user.

    Args:
        current_user: Authenticated user

    Returns:
        Notification preferences
    """
    # Get preferences from user's metadata or use defaults
    # Note: In a real implementation, preferences would be stored in the User model
    # For now, we'll use a simple approach with defaults
    prefs = DEFAULT_PREFERENCES.copy()

    # You could store preferences in a JSON field on the User model
    # or in a separate UserPreferences table

    return NotificationPreferencesResponse(**prefs)


@router.put("/preferences", response_model=StatusResponse)
async def update_notification_preferences(
    preferences: NotificationPreferences,
    current_user: CurrentUser,
    db: DBSession,
):
    """Update notification preferences for the current user.

    Args:
        preferences: Updated preferences (only non-null fields are updated)
        current_user: Authenticated user
        db: Database session

    Returns:
        Status response
    """
    try:
        # Build update dict from non-null fields
        updates = {
            k: v for k, v in preferences.model_dump().items()
            if v is not None
        }

        if not updates:
            return StatusResponse(
                status="no_change",
                message="No preferences to update",
            )

        # Note: In a real implementation, store these in the database
        # For now, log the update

        logger.info(
            "Notification preferences updated",
            user_id=str(current_user.id),
            updates=updates,
        )

        return StatusResponse(
            status="success",
            message="Notification preferences updated",
        )

    except Exception as e:
        logger.error(
            "Failed to update notification preferences",
            user_id=str(current_user.id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification preferences",
        )


@router.post("/test", response_model=StatusResponse)
async def send_test_notification(
    current_user: CurrentUser,
):
    """Send a test push notification to the current user.

    This endpoint triggers a test notification to verify that
    push notifications are working correctly.

    Args:
        current_user: Authenticated user

    Returns:
        Status response
    """
    from backend.workers.tasks.alerting_tasks import send_push_notification_task

    if not current_user.fcm_tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No FCM tokens registered. Please enable push notifications first.",
        )

    # Queue the test notification
    send_push_notification_task.delay(
        user_id=str(current_user.id),
        title="Test Notification",
        body="This is a test notification from Micro-Alpha News Scraper.",
        data={
            "type": "system",
            "test": True,
        },
    )

    logger.info(
        "Test notification queued",
        user_id=str(current_user.id),
    )

    return StatusResponse(
        status="success",
        message="Test notification queued for delivery",
    )
