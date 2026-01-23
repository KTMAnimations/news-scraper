"""Request validation middleware for FastAPI.

This middleware provides:
- Request body size limits
- Content-Type validation
- Request ID tracking
- Input sanitization for query parameters
"""

import re
import time
import uuid
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = structlog.get_logger(__name__)

# Maximum request body size (1MB default)
MAX_BODY_SIZE = 1 * 1024 * 1024  # 1MB

# Paths that don't require Content-Type validation
CONTENT_TYPE_EXEMPT_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}

# Allowed Content-Types for POST/PUT/PATCH requests
ALLOWED_CONTENT_TYPES = {
    "application/json",
    "application/x-www-form-urlencoded",
    "multipart/form-data",
}


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for validating incoming requests.

    Features:
    - Adds unique request ID to each request
    - Validates Content-Type for requests with body
    - Enforces request body size limits
    - Logs request details for debugging
    - Adds processing time header to responses
    """

    def __init__(
        self,
        app,
        max_body_size: int = MAX_BODY_SIZE,
        require_content_type: bool = True,
    ):
        """Initialize validation middleware.

        Args:
            app: FastAPI application
            max_body_size: Maximum allowed request body size in bytes
            require_content_type: Whether to require Content-Type header
        """
        super().__init__(app)
        self.max_body_size = max_body_size
        self.require_content_type = require_content_type

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process and validate incoming request.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response object
        """
        start_time = time.time()

        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        # Log incoming request
        logger.debug(
            "Request received",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else "unknown",
        )

        # Skip validation for exempt paths
        if request.url.path in CONTENT_TYPE_EXEMPT_PATHS:
            response = await call_next(request)
            self._add_response_headers(response, request_id, start_time)
            return response

        # Validate Content-Type for requests with body
        if request.method in {"POST", "PUT", "PATCH"}:
            content_type_error = self._validate_content_type(request)
            if content_type_error:
                return content_type_error

        # Check Content-Length for body size
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                body_size = int(content_length)
                if body_size > self.max_body_size:
                    logger.warning(
                        "Request body too large",
                        request_id=request_id,
                        body_size=body_size,
                        max_size=self.max_body_size,
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"Request body too large. Maximum size is {self.max_body_size // 1024}KB",
                            "error_code": "BODY_TOO_LARGE",
                        },
                        headers={"X-Request-ID": request_id},
                    )
            except ValueError:
                pass  # Invalid Content-Length, let downstream handle it

        # Validate query parameters for injection attempts
        query_validation_error = self._validate_query_params(request)
        if query_validation_error:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "Invalid characters in query parameters",
                    "error_code": "INVALID_QUERY_PARAMS",
                },
                headers={"X-Request-ID": request_id},
            )

        try:
            response = await call_next(request)
            self._add_response_headers(response, request_id, start_time)
            return response

        except Exception as e:
            logger.error(
                "Request processing error",
                request_id=request_id,
                error=str(e),
                exc_info=True,
            )
            raise

    def _validate_content_type(self, request: Request) -> JSONResponse | None:
        """Validate Content-Type header for requests with body.

        Args:
            request: Incoming request

        Returns:
            Error response if validation fails, None otherwise
        """
        if not self.require_content_type:
            return None

        content_type = request.headers.get("Content-Type", "")

        # Extract base content type (ignore charset, boundary, etc.)
        base_content_type = content_type.split(";")[0].strip().lower()

        # Check if content type is allowed
        if base_content_type and base_content_type not in ALLOWED_CONTENT_TYPES:
            logger.warning(
                "Invalid Content-Type",
                content_type=content_type,
                path=request.url.path,
            )
            return JSONResponse(
                status_code=415,
                content={
                    "detail": f"Unsupported Content-Type: {content_type}",
                    "error_code": "UNSUPPORTED_MEDIA_TYPE",
                    "allowed_types": list(ALLOWED_CONTENT_TYPES),
                },
            )

        return None

    def _validate_query_params(self, request: Request) -> bool:
        """Check query parameters for potential injection attacks.

        Args:
            request: Incoming request

        Returns:
            True if validation fails, False otherwise
        """
        # Patterns that might indicate injection attempts
        dangerous_patterns = [
            r"<script",  # XSS
            r"javascript:",  # XSS
            r"--",  # SQL comment
            r";.*(?:drop|delete|insert|update|select)",  # SQL injection
            r"\$\{",  # Template injection
            r"\{\{",  # Template injection
        ]

        combined_pattern = "|".join(dangerous_patterns)

        for key, value in request.query_params.items():
            if re.search(combined_pattern, value, re.IGNORECASE):
                logger.warning(
                    "Potentially malicious query parameter detected",
                    param=key,
                    value=value[:50],  # Log first 50 chars only
                )
                return True

        return False

    def _add_response_headers(
        self,
        response: Response,
        request_id: str,
        start_time: float,
    ) -> None:
        """Add standard headers to response.

        Args:
            response: Response object
            request_id: Unique request ID
            start_time: Request start timestamp
        """
        processing_time = time.time() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Processing-Time"] = f"{processing_time:.3f}s"


class ContentTypeValidationMiddleware(BaseHTTPMiddleware):
    """Lightweight middleware for Content-Type validation only.

    Use this when you only need Content-Type validation without
    full request validation.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate Content-Type and process request."""
        if request.method in {"POST", "PUT", "PATCH"}:
            content_type = request.headers.get("Content-Type", "")
            base_content_type = content_type.split(";")[0].strip().lower()

            if base_content_type and base_content_type not in ALLOWED_CONTENT_TYPES:
                return JSONResponse(
                    status_code=415,
                    content={
                        "detail": f"Unsupported Content-Type: {content_type}",
                        "error_code": "UNSUPPORTED_MEDIA_TYPE",
                    },
                )

        return await call_next(request)
