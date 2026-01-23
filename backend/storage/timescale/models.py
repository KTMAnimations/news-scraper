"""SQLAlchemy models for TimescaleDB."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship

from .connection import Base


def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


class Event(Base):
    """Event model - main table for all scraped events."""

    __tablename__ = "events"

    # Composite primary key required for TimescaleDB hypertable
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_time = Column(DateTime(timezone=True), primary_key=True, nullable=False, index=True)
    ticker = Column(String(10), index=True)
    ingest_time = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Classification
    event_type = Column(String(50), nullable=False, index=True)
    event_category = Column(String(50))

    # Content
    headline = Column(Text, nullable=False)
    summary = Column(Text)
    content = Column(Text)
    source_url = Column(Text)
    source_name = Column(String(100), index=True)

    # Sentiment & Scoring
    sentiment_score = Column(Float)
    sentiment_label = Column(String(20))
    sentiment_confidence = Column(Float)
    alpha_score = Column(Float, index=True)
    direction = Column(String(10))
    urgency_level = Column(String(20))

    # Entities
    extracted_tickers = Column(ARRAY(String))
    extracted_companies = Column(ARRAY(String))
    extracted_people = Column(ARRAY(String))
    extracted_amounts = Column(JSON)

    # Extra metadata (named 'extra_data' to avoid SQLAlchemy reserved 'metadata')
    extra_data = Column("metadata", JSON, default=dict)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_events_ticker_time", "ticker", "event_time"),
        Index("idx_events_type_time", "event_type", "event_time"),
        Index("idx_events_alpha_desc", "alpha_score", postgresql_ops={"alpha_score": "DESC"}),
        Index("idx_events_urgency", "urgency_level", "event_time"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "ticker": self.ticker,
            "event_time": self.event_time.isoformat() if self.event_time else None,
            "ingest_time": self.ingest_time.isoformat() if self.ingest_time else None,
            "event_type": self.event_type,
            "event_category": self.event_category,
            "headline": self.headline,
            "summary": self.summary,
            "source_url": self.source_url,
            "source_name": self.source_name,
            "sentiment_score": self.sentiment_score,
            "sentiment_label": self.sentiment_label,
            "sentiment_confidence": self.sentiment_confidence,
            "alpha_score": self.alpha_score,
            "direction": self.direction,
            "urgency_level": self.urgency_level,
            "extracted_tickers": self.extracted_tickers,
            "metadata": self.extra_data,
        }


class User(Base):
    """User model."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))

    # Subscription
    subscription_tier = Column(String(50), default="starter")
    subscription_status = Column(String(50), default="active")
    stripe_customer_id = Column(String(255))
    stripe_subscription_id = Column(String(255))

    # Push notifications
    fcm_tokens = Column(JSON, default=list)  # List of FCM device tokens

    # Password reset
    password_reset_token = Column(String(255), nullable=True, index=True)
    password_reset_expires = Column(DateTime(timezone=True), nullable=True)

    # Email verification
    email_verification_token = Column(String(255), nullable=True, index=True)
    email_verification_expires = Column(DateTime(timezone=True), nullable=True)

    # Settings
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    watchlists = relationship("Watchlist", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "email": self.email,
            "full_name": self.full_name,
            "subscription_tier": self.subscription_tier,
            "subscription_status": self.subscription_status,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Watchlist(Base):
    """User watchlist model."""

    __tablename__ = "watchlists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ticker = Column(String(10), nullable=False)
    added_at = Column(DateTime(timezone=True), default=utc_now)
    notes = Column(Text)
    alert_enabled = Column(Boolean, default=True)

    # Relationship
    user = relationship("User", back_populates="watchlists")

    __table_args__ = (
        Index("idx_watchlist_user_ticker", "user_id", "ticker", unique=True),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "ticker": self.ticker,
            "added_at": self.added_at.isoformat() if self.added_at else None,
            "notes": self.notes,
            "alert_enabled": self.alert_enabled,
        }


class APIKey(Base):
    """API Key model for programmatic access."""

    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)  # User-provided name for the key

    # Key storage (we store hashed version, prefix for display)
    key_prefix = Column(String(8), nullable=False)  # First 8 chars for identification
    key_hash = Column(String(255), nullable=False, unique=True, index=True)

    # Permissions and limits
    scopes = Column(ARRAY(String), default=["read"])  # Available: read, write, admin
    rate_limit_override = Column(Integer, nullable=True)  # Custom rate limit, null = use tier default

    # Metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Usage tracking
    request_count = Column(Integer, default=0)
    last_ip = Column(String(45), nullable=True)  # IPv6 max length

    # Relationship
    user = relationship("User", back_populates="api_keys")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excludes sensitive data)."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "name": self.name,
            "key_prefix": self.key_prefix,
            "scopes": self.scopes,
            "rate_limit_override": self.rate_limit_override,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "request_count": self.request_count,
        }


class Alert(Base):
    """User alert rule model."""

    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)

    # Alert conditions
    ticker = Column(String(10))  # Null = all tickers
    event_types = Column(ARRAY(String))  # Null = all types
    min_alpha_score = Column(Float)  # Trigger if alpha >= this
    urgency_levels = Column(ARRAY(String))  # Null = all levels
    direction = Column(String(10))  # "BULLISH", "BEARISH", or null

    # Delivery
    delivery_method = Column(String(50), default="push")  # "email", "push", "both"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    last_triggered_at = Column(DateTime(timezone=True))

    # Relationship
    user = relationship("User", back_populates="alerts")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "name": self.name,
            "ticker": self.ticker,
            "event_types": self.event_types,
            "min_alpha_score": self.min_alpha_score,
            "urgency_levels": self.urgency_levels,
            "direction": self.direction,
            "delivery_method": self.delivery_method,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
