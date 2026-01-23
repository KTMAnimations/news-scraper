"""Shared API schemas for pagination, validation, and common responses.

This module provides reusable Pydantic models for:
- Pagination metadata and parameters
- Common response wrappers
- Custom validators for API requests
"""

from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Generic type for paginated responses
T = TypeVar("T")


class PaginationParams(BaseModel):
    """Common pagination query parameters.

    Usage:
        @router.get("/items")
        async def list_items(pagination: PaginationParams = Depends()):
            ...
    """

    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of items to return",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of items to skip",
    )

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v: int) -> int:
        """Ensure limit is within bounds."""
        return min(max(v, 1), 500)

    @field_validator("offset")
    @classmethod
    def validate_offset(cls, v: int) -> int:
        """Ensure offset is non-negative."""
        return max(v, 0)


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses.

    Attributes:
        total: Total number of items matching the query
        limit: Number of items requested per page
        offset: Number of items skipped
        has_more: Whether there are more items after this page
        page: Current page number (1-indexed)
        total_pages: Total number of pages
    """

    total: int = Field(..., ge=0, description="Total number of items")
    limit: int = Field(..., ge=1, description="Items per page")
    offset: int = Field(..., ge=0, description="Items skipped")
    has_more: bool = Field(..., description="Whether more items exist")
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    total_pages: int = Field(..., ge=0, description="Total number of pages")

    @classmethod
    def create(cls, total: int, limit: int, offset: int) -> "PaginationMeta":
        """Factory method to create pagination metadata.

        Args:
            total: Total number of items
            limit: Items per page
            offset: Items skipped

        Returns:
            PaginationMeta instance with computed fields
        """
        has_more = offset + limit < total
        page = (offset // limit) + 1 if limit > 0 else 1
        total_pages = (total + limit - 1) // limit if limit > 0 else 0

        return cls(
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
            page=page,
            total_pages=total_pages,
        )


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper.

    Usage:
        class EventListResponse(PaginatedResponse[EventResponse]):
            pass

        # Or directly:
        return PaginatedResponse[EventResponse](
            items=events,
            pagination=PaginationMeta.create(total, limit, offset)
        )
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[T] = Field(..., description="List of items")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


class TickerField(BaseModel):
    """Validated ticker symbol field.

    Ensures ticker symbols are properly formatted:
    - Uppercase only
    - 1-10 characters
    - Alphanumeric with optional dots/dashes
    """

    ticker: str = Field(
        ...,
        min_length=1,
        max_length=10,
        pattern=r"^[A-Z0-9][A-Z0-9.\-]{0,9}$",
        description="Stock ticker symbol (uppercase, 1-10 chars)",
    )

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        """Convert to uppercase and validate ticker format."""
        v = v.upper().strip()
        if not v:
            raise ValueError("Ticker cannot be empty")
        # Remove common prefixes that shouldn't be there
        if v.startswith("$"):
            v = v[1:]
        return v


class ErrorResponse(BaseModel):
    """Standard error response model.

    Follows RFC 7807 Problem Details for HTTP APIs.
    """

    detail: str = Field(..., description="Human-readable error description")
    error_code: str | None = Field(None, description="Machine-readable error code")
    field: str | None = Field(None, description="Field that caused the error")
    context: dict[str, Any] | None = Field(None, description="Additional error context")


class ValidationErrorDetail(BaseModel):
    """Validation error detail for a single field."""

    loc: list[str | int] = Field(..., description="Location of the error")
    msg: str = Field(..., description="Error message")
    type: str = Field(..., description="Error type")


class ValidationErrorResponse(BaseModel):
    """Response model for validation errors (HTTP 422)."""

    detail: list[ValidationErrorDetail] = Field(..., description="List of validation errors")


class SuccessResponse(BaseModel):
    """Generic success response."""

    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(..., description="Success message")
    data: dict[str, Any] | None = Field(None, description="Optional response data")


# Common field validators that can be reused
def validate_direction(v: str | None) -> str | None:
    """Validate direction field (BULLISH, BEARISH, NEUTRAL)."""
    if v is None:
        return None
    v = v.upper()
    if v not in {"BULLISH", "BEARISH", "NEUTRAL"}:
        raise ValueError("Direction must be BULLISH, BEARISH, or NEUTRAL")
    return v


def validate_urgency(v: str | None) -> str | None:
    """Validate urgency level field."""
    if v is None:
        return None
    v = v.upper()
    valid_levels = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    if v not in valid_levels:
        raise ValueError(f"Urgency must be one of: {', '.join(valid_levels)}")
    return v


def validate_event_type(v: str | None) -> str | None:
    """Validate event type field."""
    if v is None:
        return None
    valid_types = {
        "SEC_FILING",
        "PRESS_RELEASE",
        "SOCIAL_MENTION",
        "INSIDER_TRADE",
        "EARNINGS",
        "MATERIAL_EVENT",
        "FDA_ACTION",
        "MERGER_ACQUISITION",
        "BANKRUPTCY",
        "STOCK_SPLIT",
        "DIVIDEND",
        "OTHER",
    }
    v = v.upper()
    if v not in valid_types:
        # Don't reject unknown types, just return as-is
        return v
    return v


# Annotated types for common fields with validation
TickerSymbol = Annotated[
    str,
    Field(
        ...,
        min_length=1,
        max_length=10,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,9}$",
        description="Stock ticker symbol",
    ),
]

AlphaScore = Annotated[
    float,
    Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Alpha score between 0 and 1",
    ),
]

SentimentScore = Annotated[
    float,
    Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Sentiment score between -1 and 1",
    ),
]


class SearchParams(BaseModel):
    """Common search query parameters."""

    q: str = Field(
        default="",
        max_length=500,
        description="Search query text",
    )
    ticker: str | None = Field(
        None,
        max_length=10,
        description="Filter by ticker symbol",
    )
    event_type: str | None = Field(
        None,
        max_length=50,
        description="Filter by event type",
    )
    min_alpha: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Minimum alpha score filter",
    )

    @field_validator("ticker")
    @classmethod
    def validate_ticker_param(cls, v: str | None) -> str | None:
        """Normalize ticker to uppercase."""
        if v is None:
            return None
        return v.upper().strip()

    @field_validator("event_type")
    @classmethod
    def validate_event_type_param(cls, v: str | None) -> str | None:
        """Validate event type."""
        return validate_event_type(v)
