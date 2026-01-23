"""FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.storage.timescale import get_db_session
from backend.storage.timescale.models import User
from backend.storage.timescale.queries import UserQueries

# Security scheme
security = HTTPBearer()


async def get_db() -> AsyncSession:
    """Get database session dependency."""
    async for session in get_db_session():
        yield session


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get current authenticated user.

    Args:
        credentials: Bearer token credentials
        db: Database session

    Returns:
        Current user

    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # Get user from database
    queries = UserQueries(db)
    user = await queries.get_user_by_id(user_id)

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current active user.

    Args:
        current_user: Current user from token

    Returns:
        Active user

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return current_user


def require_subscription(min_tier: str = "starter"):
    """Dependency factory for subscription tier checking.

    Args:
        min_tier: Minimum required subscription tier

    Returns:
        Dependency function
    """
    tier_levels = {
        "starter": 1,
        "professional": 2,
        "team": 3,
        "enterprise": 4,
    }

    async def check_subscription(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        user_tier = current_user.subscription_tier or "starter"
        user_level = tier_levels.get(user_tier, 0)
        required_level = tier_levels.get(min_tier, 1)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires {min_tier} tier or higher",
            )

        return current_user

    return check_subscription


async def get_optional_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    """Get current authenticated user optionally.

    Returns None if not authenticated instead of raising an exception.
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = payload.get("sub")
        if user_id is None:
            return None

    except JWTError:
        return None

    # Get user from database
    queries = UserQueries(db)
    user = await queries.get_user_by_id(user_id)

    if user is None or not user.is_active:
        return None

    return user


# Type aliases for cleaner signatures
DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
ActiveUser = Annotated[User, Depends(get_current_active_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_current_user)]
