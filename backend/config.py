"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    log_level: str = "INFO"

    # Database
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/newsdb"
    )
    database_sync_url: str = Field(
        default="postgresql://user:password@localhost:5432/newsdb"
    )

    # Redis
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")

    # Kafka
    kafka_brokers: str = "localhost:9092"

    # OpenSearch
    opensearch_url: str = "http://localhost:9200"

    # JWT Auth
    jwt_secret_key: str = "your-super-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""

    # SEC EDGAR
    sec_user_agent: str = "NewsScraperBot admin@example.com"

    # Twitter/X API
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_secret: str = ""
    twitter_bearer_token: str = ""

    # Reddit
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "news-scraper:v0.1.0"

    # StockTwits
    stocktwits_access_token: str = ""

    # Proxy Configuration
    proxy_enabled: bool = False
    proxy_url: str = ""
    proxy_username: str = ""
    proxy_password: str = ""

    # Email Configuration (SMTP)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "alerts@news-scraper.com"
    smtp_from_name: str = "News Scraper Alerts"
    smtp_use_tls: bool = True

    # Push Notifications (Firebase Cloud Messaging)
    fcm_server_key: str = ""
    fcm_project_id: str = ""

    # App URL for links in notifications
    app_url: str = "http://localhost:3000"

    @property
    def kafka_brokers_list(self) -> list[str]:
        """Return Kafka brokers as a list."""
        return self.kafka_brokers.split(",")

    @property
    def email_configured(self) -> bool:
        """Check if email is properly configured."""
        return bool(self.smtp_host and self.smtp_username and self.smtp_password)

    @property
    def push_notifications_configured(self) -> bool:
        """Check if push notifications are configured."""
        return bool(self.fcm_server_key and self.fcm_project_id)

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str, info) -> str:
        """Ensure JWT secret is properly configured for production."""
        if v == "your-super-secret-key-change-in-production":
            import warnings
            warnings.warn(
                "Using default JWT secret key. Change this in production!",
                UserWarning,
            )
        return v

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v):
        """Validate database URL format."""
        url_str = str(v)
        if "asyncpg" not in url_str:
            raise ValueError("Database URL must use asyncpg driver for async support")
        return v

    @model_validator(mode="after")
    def validate_production_settings(self):
        """Validate settings for production environment."""
        if self.environment == "production":
            errors = []

            # Critical security checks
            if self.jwt_secret_key == "your-super-secret-key-change-in-production":
                errors.append("JWT secret key must be changed for production")

            if self.debug:
                errors.append("Debug mode must be disabled in production")

            if not self.stripe_webhook_secret and self.stripe_secret_key:
                errors.append("Stripe webhook secret is required when Stripe is configured")

            if errors:
                import warnings
                for error in errors:
                    warnings.warn(f"Production config warning: {error}", UserWarning)

        return self

    def validate_all(self) -> dict[str, list[str]]:
        """Validate all configuration and return issues.

        Returns:
            Dict with 'errors' and 'warnings' lists
        """
        errors = []
        warnings = []

        # Database validation
        try:
            from urllib.parse import urlparse
            db_url = str(self.database_url)
            parsed = urlparse(db_url)
            if not parsed.hostname:
                errors.append("Invalid database URL: missing hostname")
        except Exception as e:
            errors.append(f"Invalid database URL: {e}")

        # Redis validation
        try:
            from urllib.parse import urlparse
            redis_url = str(self.redis_url)
            parsed = urlparse(redis_url)
            if not parsed.hostname:
                errors.append("Invalid Redis URL: missing hostname")
        except Exception as e:
            errors.append(f"Invalid Redis URL: {e}")

        # JWT validation
        if len(self.jwt_secret_key) < 32:
            warnings.append("JWT secret key should be at least 32 characters")

        # SEC API validation
        if not self.sec_user_agent or "example.com" in self.sec_user_agent:
            warnings.append("SEC user agent should include a valid contact email")

        # Email configuration
        if self.environment != "development" and not self.email_configured:
            warnings.append("Email is not configured - alert notifications will be disabled")

        # Social API configurations
        if not self.twitter_bearer_token:
            warnings.append("Twitter API not configured - social scraping limited")

        if not self.reddit_client_id or not self.reddit_client_secret:
            warnings.append("Reddit API not configured - social scraping limited")

        # OpenSearch validation
        if not self.opensearch_url:
            warnings.append("OpenSearch URL not configured - full-text search disabled")

        # Production-specific checks
        if self.environment == "production":
            if self.debug:
                errors.append("Debug mode must be disabled in production")

            if self.jwt_secret_key == "your-super-secret-key-change-in-production":
                errors.append("Default JWT secret cannot be used in production")

        return {"errors": errors, "warnings": warnings}

    def print_status(self) -> None:
        """Print configuration status for debugging."""
        import sys

        validation = self.validate_all()

        print("\n" + "=" * 60)
        print("News Scraper Configuration Status")
        print("=" * 60)
        print(f"Environment: {self.environment}")
        print(f"Debug Mode: {self.debug}")
        print(f"Log Level: {self.log_level}")
        print("-" * 60)

        # Database
        db_url = str(self.database_url)
        print(f"Database: {db_url[:50]}..." if len(db_url) > 50 else f"Database: {db_url}")

        # Services
        print(f"Redis: {'Configured' if self.redis_url else 'Not configured'}")
        print(f"OpenSearch: {'Configured' if self.opensearch_url else 'Not configured'}")
        print(f"Kafka: {'Configured' if self.kafka_brokers else 'Not configured'}")

        # API Keys
        print("-" * 60)
        print("API Configurations:")
        print(f"  Stripe: {'Configured' if self.stripe_secret_key else 'Not configured'}")
        print(f"  Twitter: {'Configured' if self.twitter_bearer_token else 'Not configured'}")
        print(f"  Reddit: {'Configured' if self.reddit_client_id else 'Not configured'}")
        print(f"  StockTwits: {'Configured' if self.stocktwits_access_token else 'Not configured'}")
        print(f"  Email (SMTP): {'Configured' if self.email_configured else 'Not configured'}")
        print(f"  Push (FCM): {'Configured' if self.push_notifications_configured else 'Not configured'}")

        # Validation results
        if validation["errors"]:
            print("-" * 60)
            print("ERRORS:")
            for error in validation["errors"]:
                print(f"  ✗ {error}")

        if validation["warnings"]:
            print("-" * 60)
            print("Warnings:")
            for warning in validation["warnings"]:
                print(f"  ⚠ {warning}")

        print("=" * 60 + "\n")

        if validation["errors"]:
            print(f"Configuration has {len(validation['errors'])} error(s)!")
            if self.environment == "production":
                sys.exit(1)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
