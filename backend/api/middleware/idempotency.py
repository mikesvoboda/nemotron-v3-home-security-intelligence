"""Idempotency middleware for mutation endpoints.

This module provides Idempotency-Key header support for POST, PUT, PATCH, and DELETE
requests. It implements industry-standard idempotency patterns to prevent duplicate
resource creation from retried requests.

When a client sends a request with an Idempotency-Key header:
1. The middleware validates the key format and length
2. The middleware checks Redis for a cached response with that key
3. If found and the request fingerprint matches, returns the cached response
4. If found but the fingerprint differs, returns 422 (key collision)
5. If not found, processes the request and caches the response

Key Validation (NEM-2593):
    - Keys must match IDEMPOTENCY_KEY_PATTERN (alphanumeric, UUID-style, underscores, hyphens)
    - Maximum length: 256 characters
    - Minimum length: 1 character (non-empty)
    - Invalid keys return 400 Bad Request

Usage:
    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware)

    # Or with custom configuration
    app.add_middleware(IdempotencyMiddleware, ttl=3600, key_prefix="idem")
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from fastapi import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.redis import get_redis_optional

if TYPE_CHECKING:
    from starlette.types import ASGIApp

    from backend.core.redis import RedisClient

# Type alias for middleware call_next function
CallNextType = Callable[[Request], Awaitable[Response]]

logger = get_logger(__name__)

# HTTP methods that support idempotency
IDEMPOTENT_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# =============================================================================
# Idempotency Key Validation (NEM-2593)
# =============================================================================
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")
IDEMPOTENCY_KEY_MAX_LENGTH = 256
IDEMPOTENCY_KEY_MIN_LENGTH = 1


def validate_idempotency_key(key: str) -> tuple[bool, str | None]:
    """Validate an idempotency key for format and length."""
    if len(key) < IDEMPOTENCY_KEY_MIN_LENGTH:
        return False, "Idempotency-Key cannot be empty"

    if len(key) > IDEMPOTENCY_KEY_MAX_LENGTH:
        return (
            False,
            f"Idempotency-Key exceeds maximum length of {IDEMPOTENCY_KEY_MAX_LENGTH} characters",
        )

    if not IDEMPOTENCY_KEY_PATTERN.match(key):
        return (
            False,
            "Idempotency-Key contains invalid characters. "
            "Only alphanumeric characters, underscores, and hyphens are allowed.",
        )

    return True, None


def compute_request_fingerprint(method: str, path: str, body: bytes) -> str:
    """Compute a fingerprint for request collision detection."""
    signature = f"{method}:{path}:{body.decode('utf-8', errors='replace')}"
    return hashlib.sha256(signature.encode()).hexdigest()


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Middleware for idempotency key support on mutation endpoints."""

    def __init__(
        self,
        app: ASGIApp,
        ttl: int | None = None,
        key_prefix: str = "idempotency",
    ):
        super().__init__(app)
        self.key_prefix = key_prefix

        if ttl is None:
            settings = get_settings()
            self.ttl = getattr(settings, "idempotency_ttl_seconds", 86400)
        else:
            self.ttl = ttl

    def _make_cache_key(self, idempotency_key: str) -> str:
        return f"{self.key_prefix}:{idempotency_key}"

    async def _get_redis_client(self, idempotency_key: str) -> RedisClient | None:
        try:
            async for r in get_redis_optional():
                return r
        except Exception as e:
            logger.warning(
                f"Failed to get Redis client for idempotency check: {e}",
                extra={"idempotency_key": idempotency_key},
            )
        return None

    def _handle_cache_hit(
        self,
        cached_data: dict,
        fingerprint: str,
        idempotency_key: str,
        request: Request,
    ) -> Response | None:
        stored_fingerprint = cached_data.get("fingerprint")
        if stored_fingerprint and stored_fingerprint != fingerprint:
            logger.warning(
                "Idempotency key collision: different request body with same key",
                extra={
                    "idempotency_key": idempotency_key,
                    "path": request.url.path,
                    "method": request.method,
                },
            )
            return Response(
                content=json.dumps(
                    {
                        "detail": "Idempotency key collision: this key was already used "
                        "with a different request body. Each unique request must use "
                        "a unique idempotency key."
                    }
                ),
                status_code=422,
                media_type="application/json",
            )

        logger.info(
            "Returning cached idempotent response (replayed)",
            extra={
                "idempotency_key": idempotency_key,
                "path": request.url.path,
                "cached_status": cached_data.get("status_code"),
            },
        )
        return Response(
            content=cached_data.get("content", "").encode("utf-8"),
            status_code=cached_data.get("status_code", 200),
            media_type=cached_data.get("media_type", "application/json"),
            headers={"Idempotency-Replayed": "true"},
        )

    async def _cache_response(
        self,
        redis: RedisClient,
        cache_key: str,
        response: Response,
        fingerprint: str,
        idempotency_key: str,
        request: Request,
    ) -> Response:
        response_body: bytes
        if hasattr(response, "body"):
            body = response.body
            response_body = bytes(body) if isinstance(body, memoryview) else body
        elif hasattr(response, "body_iterator"):
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk
        else:
            logger.warning(
                "Unknown response type, cannot cache for idempotency",
                extra={"idempotency_key": idempotency_key},
            )
            return response

        cache_data = {
            "status_code": response.status_code,
            "content": response_body.decode("utf-8", errors="replace"),
            "media_type": response.media_type,
            "fingerprint": fingerprint,
        }

        await redis.setex(cache_key, self.ttl, json.dumps(cache_data))

        logger.debug(
            "Cached idempotent response",
            extra={
                "idempotency_key": idempotency_key,
                "path": request.url.path,
                "status_code": response.status_code,
                "ttl_seconds": self.ttl,
            },
        )

        new_headers = dict(response.headers) if response.headers else {}
        return Response(
            content=response_body,
            status_code=response.status_code,
            media_type=response.media_type,
            headers=new_headers,
        )

    async def dispatch(  # noqa: PLR0911
        self,
        request: Request,
        call_next: CallNextType,
    ) -> Response:
        if request.method not in IDEMPOTENT_METHODS:
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        # Validate idempotency key format and length (NEM-2593)
        is_valid, error_message = validate_idempotency_key(idempotency_key)
        if not is_valid:
            logger.warning(
                "Invalid Idempotency-Key header rejected",
                extra={
                    "idempotency_key": idempotency_key[:50] + "..."
                    if len(idempotency_key) > 50
                    else idempotency_key,
                    "path": request.url.path,
                    "method": request.method,
                    "error": error_message,
                },
            )
            return Response(
                content=json.dumps({"detail": error_message}),
                status_code=400,
                media_type="application/json",
            )

        redis = await self._get_redis_client(idempotency_key)
        if redis is None:
            logger.debug(
                "Redis unavailable, skipping idempotency check",
                extra={"idempotency_key": idempotency_key},
            )
            return await call_next(request)

        try:
            body = await request.body()
        except Exception as e:
            logger.warning(f"Failed to read request body: {e}")
            return await call_next(request)

        fingerprint = compute_request_fingerprint(
            request.method,
            request.url.path,
            body,
        )

        cache_key = self._make_cache_key(idempotency_key)

        try:
            cached_json = await redis.get(cache_key)
        except Exception as e:
            logger.warning(
                f"Redis get failed for idempotency key: {e}",
                extra={"idempotency_key": idempotency_key},
            )
            cached_json = None

        if cached_json:
            try:
                cached_data = json.loads(cached_json)
                cache_response = self._handle_cache_hit(
                    cached_data, fingerprint, idempotency_key, request
                )
                if cache_response:
                    return cache_response
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Invalid JSON in idempotency cache: {e}",
                    extra={"idempotency_key": idempotency_key},
                )

        response = await call_next(request)

        try:
            return await self._cache_response(
                redis, cache_key, response, fingerprint, idempotency_key, request
            )
        except Exception as e:
            logger.warning(
                f"Failed to cache idempotent response: {e}",
                extra={"idempotency_key": idempotency_key},
            )
            return response
