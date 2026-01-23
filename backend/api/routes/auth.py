"""Authentication routes.

This module provides user authentication endpoints including registration,
login, token refresh, password reset, and user profile retrieval.
"""

import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.api.dependencies import CurrentUser, DBSession
from backend.config import settings
from backend.notifications.email_service import email_service
from backend.storage.timescale.models import User
from backend.storage.timescale.queries import UserQueries

router = APIRouter()
logger = structlog.get_logger(__name__)

# Token expiry constants
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = 24
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS = 48


# Request/Response models
class UserCreate(BaseModel):
    """User registration request model.

    Attributes:
        email: Valid email address for the account.
        password: Account password (minimum 8 characters with complexity requirements).
        full_name: Optional display name for the user.
    """

    email: EmailStr = Field(
        ..., description="User's email address", examples=["user@example.com"]
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Account password (min 8 chars, must include upper, lower, digit)",
        examples=["SecurePass123"],
    )
    full_name: str | None = Field(
        None, description="User's full name", examples=["John Doe"]
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets minimum security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    """User login request model.

    Attributes:
        email: Email address associated with the account.
        password: Account password.
    """

    email: EmailStr = Field(
        ..., description="User's email address", examples=["user@example.com"]
    )
    password: str = Field(
        ..., description="Account password", examples=["SecurePass123"]
    )


class Token(BaseModel):
    """Authentication token response model.

    Attributes:
        access_token: JWT token for API authentication (expires in 30 minutes).
        refresh_token: JWT token for obtaining new access tokens (expires in 7 days).
        token_type: Token type, always "bearer".
    """

    access_token: str = Field(
        ..., description="JWT access token for API authentication"
    )
    refresh_token: str = Field(
        ..., description="JWT refresh token for obtaining new access tokens"
    )
    token_type: str = Field(default="bearer", description="Token type")


class TokenRefresh(BaseModel):
    """Token refresh request model."""

    refresh_token: str = Field(..., description="JWT refresh token")


class UserResponse(BaseModel):
    """User profile response model.

    Attributes:
        id: Unique user identifier (UUID).
        email: User's email address.
        full_name: User's display name.
        subscription_tier: Current subscription tier (starter, professional, team, enterprise).
        is_verified: Whether the email has been verified.
        created_at: Account creation timestamp.
    """

    id: str = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User's email address")
    full_name: str | None = Field(None, description="User's full name")
    subscription_tier: str = Field(..., description="Subscription tier")
    is_verified: bool = Field(..., description="Email verification status")
    created_at: datetime | None = Field(None, description="Account creation timestamp")


class ForgotPasswordRequest(BaseModel):
    """Forgot password request model."""

    email: EmailStr = Field(
        ...,
        description="Email address to send reset link",
        examples=["user@example.com"],
    )


class ResetPasswordRequest(BaseModel):
    """Reset password request model."""

    token: str = Field(..., description="Password reset token from email")
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password (min 8 chars, must include upper, lower, digit)",
        examples=["NewSecurePass456"],
    )

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets minimum security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class ChangePasswordRequest(BaseModel):
    """Change password request model (for authenticated users)."""

    current_password: str = Field(..., description="Current account password")
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password (min 8 chars, must include upper, lower, digit)",
        examples=["NewSecurePass456"],
    )

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets minimum security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class MessageResponse(BaseModel):
    """Simple message response model."""

    message: str = Field(..., description="Response message")


# Utility functions
def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    """Create JWT access token.

    Args:
        user_id: User's unique identifier
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT access token
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )

    to_encode = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }

    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user_id: str) -> str:
    """Create JWT refresh token.

    Args:
        user_id: User's unique identifier

    Returns:
        Encoded JWT refresh token
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_expire_days
    )

    to_encode = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    }

    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Stored bcrypt hash

    Returns:
        True if password matches, False otherwise
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    """Hash password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Bcrypt hashed password
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def generate_secure_token() -> str:
    """Generate a cryptographically secure random token.

    Returns:
        URL-safe random token string
    """
    return secrets.token_urlsafe(32)


def decode_jwt_token(token: str) -> dict:
    """Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


# API Endpoints
@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email and password. The user will start on the 'starter' subscription tier.",
    response_description="The newly created user profile",
    responses={
        201: {"description": "User successfully created"},
        400: {"description": "Email already registered or invalid data"},
    },
)
async def register(
    user_data: UserCreate,
    db: DBSession,
):
    """Register a new user account.

    Creates a new user with the provided email and password. The password is
    securely hashed using bcrypt before storage.

    Args:
        user_data: User registration data including email, password, and optional name.
        db: Database session (injected).

    Returns:
        UserResponse: The newly created user profile.

    Raises:
        HTTPException: 400 if the email is already registered.
    """
    queries = UserQueries(db)

    # Check if user exists
    existing = await queries.get_user_by_email(user_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user
    user = await queries.create_user(
        {
            "email": user_data.email.lower(),
            "hashed_password": get_password_hash(user_data.password),
            "full_name": user_data.full_name,
        }
    )

    await db.commit()

    logger.info("User registered", user_id=str(user.id), email=user.email)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        subscription_tier=user.subscription_tier,
        is_verified=user.is_verified,
        created_at=user.created_at,
    )


@router.post(
    "/login",
    response_model=Token,
    summary="Login and obtain tokens",
    description="Authenticate with email and password to receive access and refresh tokens.",
    response_description="JWT access and refresh tokens",
    responses={
        200: {"description": "Successfully authenticated"},
        401: {"description": "Invalid email or password"},
        403: {"description": "User account is inactive"},
    },
)
async def login(
    credentials: UserLogin,
    db: DBSession,
):
    """Authenticate user and return JWT tokens.

    Validates the user's credentials and returns both an access token
    (for API authentication) and a refresh token (for obtaining new access tokens).

    Args:
        credentials: Login credentials (email and password).
        db: Database session (injected).

    Returns:
        Token: Access and refresh tokens for authentication.

    Raises:
        HTTPException: 401 if credentials are invalid, 403 if account is inactive.
    """
    queries = UserQueries(db)

    user = await queries.get_user_by_email(credentials.email)

    if not user or not verify_password(credentials.password, user.hashed_password):
        logger.warning("Failed login attempt", email=credentials.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    logger.info("User logged in", user_id=str(user.id))

    return Token(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token",
    description="Exchange a valid refresh token for new access and refresh tokens.",
    response_description="New JWT access and refresh tokens",
    responses={
        200: {"description": "Tokens successfully refreshed"},
        401: {"description": "Invalid or expired refresh token"},
    },
)
async def refresh_token(
    token_data: TokenRefresh,
    db: DBSession,
):
    """Refresh authentication tokens.

    Exchanges a valid refresh token for a new pair of access and refresh tokens.
    This allows users to maintain their session without re-authenticating.

    Args:
        token_data: Token refresh request containing the refresh token.
        db: Database session (injected).

    Returns:
        Token: New access and refresh tokens.

    Raises:
        HTTPException: 401 if refresh token is invalid, expired, or wrong type.
    """
    try:
        payload = jwt.decode(
            token_data.refresh_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        user_id = payload.get("sub")

        queries = UserQueries(db)
        user = await queries.get_user_by_id(user_id)

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        return Token(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request password reset",
    description="Send a password reset link to the user's email address.",
    response_description="Confirmation message",
    responses={
        200: {"description": "Password reset email sent (if email exists)"},
    },
)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: DBSession,
):
    """Request a password reset.

    Generates a password reset token and sends it to the user's email.
    For security, always returns success even if email doesn't exist.

    Args:
        request: Forgot password request containing email.
        db: Database session (injected).

    Returns:
        MessageResponse: Confirmation message.
    """
    queries = UserQueries(db)
    user = await queries.get_user_by_email(request.email)

    # Always return success message to prevent email enumeration
    success_message = (
        "If an account with that email exists, a password reset link has been sent."
    )

    if not user:
        logger.info(
            "Password reset requested for non-existent email", email=request.email
        )
        return MessageResponse(message=success_message)

    if not user.is_active:
        logger.info(
            "Password reset requested for inactive user", user_id=str(user.id)
        )
        return MessageResponse(message=success_message)

    # Generate reset token
    reset_token = generate_secure_token()
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=PASSWORD_RESET_TOKEN_EXPIRE_HOURS
    )

    # Store token in database
    await queries.set_password_reset_token(user.id, reset_token, expires_at)
    await db.commit()

    # Send password reset email
    reset_url = f"{settings.app_url}/auth/reset-password?token={reset_token}"

    user_name_display = f" {user.full_name}" if user.full_name else ""

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(to right, #1e293b, #334155); border-radius: 12px; padding: 24px; border: 1px solid #475569;">
            <div style="text-align: center; margin-bottom: 24px;">
                <h1 style="color: #f8fafc; margin: 0; font-size: 24px;">Password Reset Request</h1>
            </div>

            <div style="background: #0f172a; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                <p style="color: #e2e8f0; margin: 0 0 16px 0; line-height: 1.6;">
                    Hi{user_name_display},
                </p>
                <p style="color: #e2e8f0; margin: 0 0 16px 0; line-height: 1.6;">
                    We received a request to reset your password. Click the button below to create a new password.
                </p>
                <p style="color: #94a3b8; margin: 0 0 16px 0; font-size: 14px;">
                    This link will expire in {PASSWORD_RESET_TOKEN_EXPIRE_HOURS} hours.
                </p>
            </div>

            <div style="text-align: center; margin-bottom: 20px;">
                <a href="{reset_url}" style="display: inline-block; background: #3b82f6; color: white; padding: 12px 32px; border-radius: 6px; text-decoration: none; font-weight: 600;">
                    Reset Password
                </a>
            </div>

            <div style="background: #0f172a; border-radius: 8px; padding: 16px;">
                <p style="color: #94a3b8; margin: 0; font-size: 12px; line-height: 1.6;">
                    If you didn't request this password reset, you can safely ignore this email.
                    Your password will remain unchanged.
                </p>
            </div>

            <div style="text-align: center; margin-top: 24px; padding-top: 20px; border-top: 1px solid #334155;">
                <p style="color: #64748b; font-size: 12px; margin: 0;">
                    News Scraper - Micro-Alpha Intelligence
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""

    text_body = f"""
Password Reset Request

Hi{user_name_display},

We received a request to reset your password. Visit the link below to create a new password:

{reset_url}

This link will expire in {PASSWORD_RESET_TOKEN_EXPIRE_HOURS} hours.

If you didn't request this password reset, you can safely ignore this email. Your password will remain unchanged.

---
News Scraper - Micro-Alpha Intelligence
"""

    if email_service.is_configured:
        email_service.send_email(
            to_email=user.email,
            subject="Password Reset Request - News Scraper",
            html_body=html_body,
            text_body=text_body,
        )
        logger.info("Password reset email sent", user_id=str(user.id))
    else:
        logger.warning(
            "Email not configured, password reset token generated but not sent",
            user_id=str(user.id),
            token=reset_token,
        )

    return MessageResponse(message=success_message)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password with token",
    description="Reset the user's password using a valid reset token.",
    response_description="Confirmation message",
    responses={
        200: {"description": "Password successfully reset"},
        400: {"description": "Invalid or expired reset token"},
    },
)
async def reset_password(
    request: ResetPasswordRequest,
    db: DBSession,
):
    """Reset password using a reset token.

    Validates the reset token and updates the user's password.

    Args:
        request: Reset password request with token and new password.
        db: Database session (injected).

    Returns:
        MessageResponse: Confirmation message.

    Raises:
        HTTPException: 400 if token is invalid or expired.
    """
    queries = UserQueries(db)
    user = await queries.get_user_by_password_reset_token(request.token)

    if not user:
        logger.warning("Invalid password reset token used")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Update password
    hashed_password = get_password_hash(request.new_password)
    await queries.update_password(user.id, hashed_password)
    await db.commit()

    logger.info("Password reset successful", user_id=str(user.id))

    return MessageResponse(message="Password has been reset successfully")


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change password (authenticated)",
    description="Change the authenticated user's password.",
    response_description="Confirmation message",
    responses={
        200: {"description": "Password successfully changed"},
        401: {"description": "Current password is incorrect"},
    },
)
async def change_password(
    request: ChangePasswordRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Change the current user's password.

    Requires the user to provide their current password for verification.

    Args:
        request: Change password request with current and new passwords.
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        MessageResponse: Confirmation message.

    Raises:
        HTTPException: 401 if current password is incorrect.
    """
    # Verify current password
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Update password
    queries = UserQueries(db)
    hashed_password = get_password_hash(request.new_password)
    await queries.update_password(current_user.id, hashed_password)
    await db.commit()

    logger.info("Password changed", user_id=str(current_user.id))

    return MessageResponse(message="Password has been changed successfully")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Retrieve the authenticated user's profile information.",
    response_description="User profile",
    responses={
        200: {"description": "User profile retrieved"},
        401: {"description": "Not authenticated"},
    },
)
async def get_me(current_user: CurrentUser):
    """Get current user profile information.

    Returns the profile of the currently authenticated user.

    Args:
        current_user: Authenticated user (injected).

    Returns:
        UserResponse: User profile information.
    """
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        subscription_tier=current_user.subscription_tier,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
    )


@router.post(
    "/verify-token",
    response_model=UserResponse,
    summary="Verify access token",
    description="Verify an access token and return user information.",
    response_description="User profile if token is valid",
    responses={
        200: {"description": "Token is valid"},
        401: {"description": "Token is invalid or expired"},
    },
)
async def verify_token(current_user: CurrentUser):
    """Verify an access token.

    This endpoint can be used to validate an access token and retrieve
    the associated user information.

    Args:
        current_user: Authenticated user (injected via token).

    Returns:
        UserResponse: User profile if token is valid.
    """
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        subscription_tier=current_user.subscription_tier,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
    )
