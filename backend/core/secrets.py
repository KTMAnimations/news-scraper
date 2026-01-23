"""Secrets management module.

This module provides utilities for managing sensitive configuration values,
validating secrets on startup, and supporting secrets rotation.
"""

import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SecretSeverity(Enum):
    """Severity level for secret validation issues."""
    CRITICAL = "critical"  # Will prevent startup in production
    WARNING = "warning"    # Will log a warning
    INFO = "info"          # Informational only


@dataclass
class SecretValidationResult:
    """Result of a secret validation check."""
    name: str
    is_valid: bool
    severity: SecretSeverity
    message: str
    remediation: str | None = None


class SecretsManager:
    """Manager for application secrets with validation and rotation support.

    This class provides:
    - Validation of required secrets on startup
    - Detection of default/weak secrets
    - Support for secrets rotation
    - Secure logging (masks sensitive values)
    """

    # Patterns that indicate a default/placeholder value
    DEFAULT_PATTERNS = [
        r"^your[-_]",
        r"^change[-_]me",
        r"^replace[-_]this",
        r"^xxx+$",
        r"^placeholder",
        r"^example",
        r"^test[-_]?key",
        r"sk_test_",  # Stripe test keys
        r"pk_test_",  # Stripe test keys
    ]

    # Minimum lengths for various secret types
    MIN_LENGTHS = {
        "jwt_secret": 32,
        "api_key": 32,
        "database_password": 12,
        "encryption_key": 32,
    }

    def __init__(self):
        """Initialize the secrets manager."""
        self._validation_results: list[SecretValidationResult] = []
        self._secrets_last_validated: datetime | None = None

    def validate_secret(
        self,
        name: str,
        value: str | None,
        required: bool = True,
        min_length: int | None = None,
        severity: SecretSeverity = SecretSeverity.CRITICAL,
        pattern: str | None = None,
        disallowed_patterns: list[str] | None = None,
    ) -> SecretValidationResult:
        """Validate a single secret.

        Args:
            name: Name of the secret (for logging)
            value: The secret value to validate
            required: Whether the secret is required
            min_length: Minimum required length
            severity: Severity if validation fails
            pattern: Regex pattern the secret must match
            disallowed_patterns: Regex patterns that indicate invalid values

        Returns:
            SecretValidationResult with validation details
        """
        disallowed = disallowed_patterns or self.DEFAULT_PATTERNS

        # Check if missing
        if not value or value.strip() == "":
            if required:
                return SecretValidationResult(
                    name=name,
                    is_valid=False,
                    severity=severity,
                    message=f"Required secret '{name}' is not set",
                    remediation=f"Set the {name.upper()} environment variable",
                )
            return SecretValidationResult(
                name=name,
                is_valid=True,
                severity=SecretSeverity.INFO,
                message=f"Optional secret '{name}' is not set",
            )

        # Check for default/placeholder values
        for pattern_str in disallowed:
            if re.match(pattern_str, value, re.IGNORECASE):
                return SecretValidationResult(
                    name=name,
                    is_valid=False,
                    severity=severity,
                    message=f"Secret '{name}' appears to be a default/placeholder value",
                    remediation=f"Replace {name.upper()} with a secure, randomly generated value",
                )

        # Check minimum length
        if min_length and len(value) < min_length:
            return SecretValidationResult(
                name=name,
                is_valid=False,
                severity=severity,
                message=f"Secret '{name}' is too short (minimum {min_length} characters)",
                remediation=f"Generate a longer value for {name.upper()} (at least {min_length} characters)",
            )

        # Check required pattern
        if pattern and not re.match(pattern, value):
            return SecretValidationResult(
                name=name,
                is_valid=False,
                severity=severity,
                message=f"Secret '{name}' does not match required format",
                remediation=f"Ensure {name.upper()} matches the expected format",
            )

        return SecretValidationResult(
            name=name,
            is_valid=True,
            severity=SecretSeverity.INFO,
            message=f"Secret '{name}' validated successfully",
        )

    def validate_all(self, settings: Any) -> list[SecretValidationResult]:
        """Validate all application secrets.

        Args:
            settings: Application settings object

        Returns:
            List of validation results
        """
        results = []
        is_production = getattr(settings, "environment", "development") == "production"

        # JWT Secret - Critical for auth
        results.append(self.validate_secret(
            name="jwt_secret_key",
            value=getattr(settings, "jwt_secret_key", None),
            required=True,
            min_length=32,
            severity=SecretSeverity.CRITICAL if is_production else SecretSeverity.WARNING,
        ))

        # Database URL - Check for password
        db_url = str(getattr(settings, "database_url", ""))
        if "@" in db_url:
            # Extract password portion for validation
            try:
                password_part = db_url.split("@")[0].split(":")[-1]
                results.append(self.validate_secret(
                    name="database_password",
                    value=password_part,
                    required=True,
                    min_length=8 if is_production else 4,
                    severity=SecretSeverity.CRITICAL if is_production else SecretSeverity.WARNING,
                ))
            except (IndexError, ValueError):
                results.append(SecretValidationResult(
                    name="database_password",
                    is_valid=False,
                    severity=SecretSeverity.CRITICAL,
                    message="Could not parse database password from URL",
                    remediation="Ensure DATABASE_URL is properly formatted",
                ))

        # Stripe secrets (only required if Stripe is configured)
        stripe_key = getattr(settings, "stripe_secret_key", "")
        if stripe_key:
            results.append(self.validate_secret(
                name="stripe_secret_key",
                value=stripe_key,
                required=False,
                severity=SecretSeverity.WARNING,
                pattern=r"^sk_(test|live)_[A-Za-z0-9]+$",
            ))

            # Warn about test keys in production
            if is_production and stripe_key.startswith("sk_test_"):
                results.append(SecretValidationResult(
                    name="stripe_secret_key",
                    is_valid=False,
                    severity=SecretSeverity.CRITICAL,
                    message="Using Stripe test key in production",
                    remediation="Replace with live Stripe key for production",
                ))

            # Webhook secret required if Stripe is configured
            results.append(self.validate_secret(
                name="stripe_webhook_secret",
                value=getattr(settings, "stripe_webhook_secret", None),
                required=is_production,
                severity=SecretSeverity.CRITICAL if is_production else SecretSeverity.WARNING,
                pattern=r"^whsec_[A-Za-z0-9]+$",
            ))

        # Social API keys (optional but warn if missing)
        for api_name, attr_name in [
            ("Twitter Bearer Token", "twitter_bearer_token"),
            ("Reddit Client Secret", "reddit_client_secret"),
        ]:
            value = getattr(settings, attr_name, None)
            results.append(self.validate_secret(
                name=attr_name,
                value=value,
                required=False,
                severity=SecretSeverity.INFO,
            ))

        # SMTP password (required for email alerts)
        smtp_configured = bool(getattr(settings, "smtp_host", ""))
        if smtp_configured:
            results.append(self.validate_secret(
                name="smtp_password",
                value=getattr(settings, "smtp_password", None),
                required=True,
                min_length=8,
                severity=SecretSeverity.WARNING,
            ))

        self._validation_results = results
        self._secrets_last_validated = datetime.now(timezone.utc)

        return results

    def get_validation_summary(self) -> dict[str, Any]:
        """Get a summary of the last validation run.

        Returns:
            Dictionary with validation summary
        """
        if not self._validation_results:
            return {"status": "not_validated", "results": []}

        critical_failures = [r for r in self._validation_results
                          if not r.is_valid and r.severity == SecretSeverity.CRITICAL]
        warnings = [r for r in self._validation_results
                   if not r.is_valid and r.severity == SecretSeverity.WARNING]
        passed = [r for r in self._validation_results if r.is_valid]

        return {
            "status": "failed" if critical_failures else ("warning" if warnings else "passed"),
            "validated_at": self._secrets_last_validated.isoformat() if self._secrets_last_validated else None,
            "summary": {
                "total": len(self._validation_results),
                "passed": len(passed),
                "warnings": len(warnings),
                "critical_failures": len(critical_failures),
            },
            "critical_failures": [
                {"name": r.name, "message": r.message, "remediation": r.remediation}
                for r in critical_failures
            ],
            "warnings": [
                {"name": r.name, "message": r.message, "remediation": r.remediation}
                for r in warnings
            ],
        }

    @staticmethod
    def mask_secret(value: str, visible_chars: int = 4) -> str:
        """Mask a secret value for safe logging.

        Args:
            value: The secret value
            visible_chars: Number of characters to show at start and end

        Returns:
            Masked string (e.g., "sk_t...xyz")
        """
        if not value or len(value) <= visible_chars * 2:
            return "*" * 8

        return f"{value[:visible_chars]}...{value[-visible_chars:]}"


def validate_secrets_on_startup(settings: Any, exit_on_failure: bool = True) -> bool:
    """Validate all secrets on application startup.

    This function should be called early in the application startup process.
    In production, it will exit the application if critical secrets are invalid.

    Args:
        settings: Application settings object
        exit_on_failure: Whether to exit on critical failures (production only)

    Returns:
        True if validation passed, False otherwise
    """
    manager = SecretsManager()
    results = manager.validate_all(settings)
    summary = manager.get_validation_summary()

    is_production = getattr(settings, "environment", "development") == "production"

    # Log results
    logger.info(
        "Secrets validation completed",
        status=summary["status"],
        passed=summary["summary"]["passed"],
        warnings=summary["summary"]["warnings"],
        critical_failures=summary["summary"]["critical_failures"],
    )

    # Log critical failures
    for failure in summary["critical_failures"]:
        logger.error(
            "Secret validation failed",
            secret=failure["name"],
            message=failure["message"],
            remediation=failure["remediation"],
        )

    # Log warnings
    for warning in summary["warnings"]:
        logger.warning(
            "Secret validation warning",
            secret=warning["name"],
            message=warning["message"],
            remediation=warning["remediation"],
        )

    # Exit on critical failures in production
    if summary["status"] == "failed" and is_production and exit_on_failure:
        logger.critical(
            "Application startup blocked due to secret validation failures",
            failures=len(summary["critical_failures"]),
        )
        print("\n" + "=" * 60)
        print("CRITICAL: Secret validation failed!")
        print("=" * 60)
        for failure in summary["critical_failures"]:
            print(f"\n  - {failure['name']}: {failure['message']}")
            if failure["remediation"]:
                print(f"    Fix: {failure['remediation']}")
        print("\n" + "=" * 60)
        print("Application cannot start with invalid secrets in production.")
        print("=" * 60 + "\n")
        sys.exit(1)

    return summary["status"] != "failed"


def generate_secure_secret(length: int = 32) -> str:
    """Generate a cryptographically secure secret.

    Args:
        length: Length of the secret in bytes (will be hex-encoded to 2x length)

    Returns:
        Hex-encoded random string
    """
    import secrets
    return secrets.token_hex(length)


def get_rotation_recommendations() -> dict[str, Any]:
    """Get recommendations for secret rotation schedules.

    Returns:
        Dictionary with rotation recommendations
    """
    return {
        "jwt_secret_key": {
            "rotation_interval_days": 90,
            "description": "JWT signing key - rotate quarterly",
            "rotation_procedure": [
                "Generate new JWT secret",
                "Update environment variable",
                "Restart API servers (will invalidate existing tokens)",
                "Users will need to re-authenticate",
            ],
        },
        "api_keys": {
            "rotation_interval_days": 365,
            "description": "User API keys - encourage yearly rotation",
            "rotation_procedure": [
                "User generates new key via /api/v1/api-keys/rotate",
                "Old key is immediately invalidated",
                "Update key in client applications",
            ],
        },
        "database_password": {
            "rotation_interval_days": 180,
            "description": "Database password - rotate semi-annually",
            "rotation_procedure": [
                "Create new database user with new password",
                "Update connection strings in all services",
                "Deploy changes with rolling restart",
                "Remove old database user",
            ],
        },
        "stripe_keys": {
            "rotation_interval_days": 365,
            "description": "Stripe API keys - rotate annually",
            "rotation_procedure": [
                "Generate new keys in Stripe Dashboard",
                "Update webhook endpoints",
                "Update environment variables",
                "Verify webhook signatures work",
                "Roll old keys in Stripe Dashboard",
            ],
        },
    }
