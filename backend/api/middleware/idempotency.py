"""Idempotency middleware for mutation endpoints.

This module provides Idempotency-Key header support for POST, PUT, PATCH, and DELETE
requests. It implements industry-standard idempotency patterns to prevent duplicate
resource creation from retried requests.

When a client sends a request with an Idempotency-Key header:
1. The middleware checks Redis for a cached response with that key
2. If found and the request fingerprint matches, returns the cached response
3. If found but the fingerprint differs, returns 422 (key collision)
4. If not found, processes the request and caches the response

Usage:
    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware)

    # Or with custom configuration
    app.add_middleware(IdempotencyMiddleware, ttl=3600, key_prefix="idem")
"""

from __future__ import annotations

import hashlib
import json
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


def compute_request_fingerprint(method: str, path: str, body: bytes) -> str:
    """Compute a fingerprint for request collision detection.

    The fingerprint uniquely identifies a request based on its method, path,
    and body. This is used to detect when a client reuses an idempotency key
    with a different request (which is an error).

    Args:
        method: HTTP method (POST, PUT, etc.)
        path: Request path
        body: Request body bytes

    Returns:
        SHA-256 hex digest of the request signature
    """
    signature = f"{method}:{path}:{body.decode('utf-8', errors='replace')}"
    return hashlib.sha256(signature.encode()).hexdigest()


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Middleware for idempotency key support on mutation endpoints.

    Implements Idempotency-Key header processing per industry standards:
    - Caches responses for requests with idempotency keys
    - Returns cached response on replay (with Idempotency-Replayed header)
    - Returns 422 if same key is used with different request body
    - Fails open (passes through) if Redis is unavailable

    Attributes:
        ttl: Time-to-live for cached responses in seconds (default: 24 hours)
        key_prefix: Redis key prefix for idempotency cache
    """

    def __init__(
        self,
        app: ASGIApp,
        ttl: int | None = None,
        key_prefix: str = "idempotency",
    ):
        """Initialize the idempotency middleware.

        Args:
            app: The ASGI application
            ttl: Time-to-live for cached responses in seconds.
                If None, uses the value from settings (default: 86400 = 24 hours)
            key_prefix: Redis key prefix for idempotency cache
        """
        super().__init__(app)
        self.key_prefix = key_prefix

        # Use settings TTL if not explicitly provided
        if ttl is None:
            settings = get_settings()
            self.ttl = getattr(settings, "idempotency_ttl_seconds", 86400)
        else:
            self.ttl = ttl

    def _make_cache_key(self, idempotency_key: str) -> str:
        """Create Redis cache key from idempotency key.

        Args:
            idempotency_key: Client-provided idempotency key

        Returns:
            Redis cache key with prefix
        """
        return f"{self.key_prefix}:{idempotency_key}"

    async def _get_redis_client(self, idempotency_key: str) -> RedisClient | None:
        """Get Redis client with fail-soft behavior.

        Args:
            idempotency_key: For logging context

        Returns:
            Redis client or None if unavailable
        """
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
        """Handle a cache hit - return cached response or 422 on collision.

        Args:
            cached_data: The cached response data
            fingerprint: Current request fingerprint
            idempotency_key: The idempotency key
            request: The incoming request (for logging)

        Returns:
            Response to return, or None to continue processing
        """
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

        # Return cached response
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
        """Cache response and return a new response with the same body.

        Args:
            redis: Redis client
            cache_key: Redis cache key
            response: The original response
            fingerprint: Request fingerprint
            idempotency_key: The idempotency key
            request: The request (for logging)

        Returns:
            New response with the same body
        """
        # Read response body for caching
        # Handle both regular Response (with .body) and StreamingResponse (with .body_iterator)
        response_body: bytes
        if hasattr(response, "body"):
            body = response.body
            # Handle memoryview case by converting to bytes
            response_body = bytes(body) if isinstance(body, memoryview) else body
        elif hasattr(response, "body_iterator"):
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk
        else:
            # Unknown response type, skip caching
            logger.warning(
                "Unknown response type, cannot cache for idempotency",
                extra={"idempotency_key": idempotency_key},
            )
            return response

        # Prepare cache data
        cache_data = {
            "status_code": response.status_code,
            "content": response_body.decode("utf-8", errors="replace"),
            "media_type": response.media_type,
            "fingerprint": fingerprint,
        }

        # Store in Redis with TTL
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

        # Return new response with the same body (preserving headers)
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
        """Process request with idempotency support.

        Args:
            request: The incoming request
            call_next: The next middleware/route handler

        Returns:
            Response (cached or fresh)
        """
        # Only apply to mutation methods
        if request.method not in IDEMPOTENT_METHODS:
            return await call_next(request)

        # Check for Idempotency-Key header
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        # Get Redis client (fail-soft if unavailable)
        redis = await self._get_redis_client(idempotency_key)
        if redis is None:
            logger.debug(
                "Redis unavailable, skipping idempotency check",
                extra={"idempotency_key": idempotency_key},
            )
            return await call_next(request)

        # Read request body for fingerprinting
        try:
            body = await request.body()
        except Exception as e:
            logger.warning(f"Failed to read request body: {e}")
            return await call_next(request)

        # Compute request fingerprint for collision detection
        fingerprint = compute_request_fingerprint(
            request.method,
            request.url.path,
            body,
        )

        cache_key = self._make_cache_key(idempotency_key)

        # Check for cached response
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
                # Fall through to process request normally

        # Process request and cache response
        response = await call_next(request)

        # Cache the response
        try:
            return await self._cache_response(
                redis, cache_key, response, fingerprint, idempotency_key, request
            )
        except Exception as e:
            logger.warning(
                f"Failed to cache idempotent response: {e}",
                extra={"idempotency_key": idempotency_key},
            )
            # Return response anyway (fail open)
            return response
