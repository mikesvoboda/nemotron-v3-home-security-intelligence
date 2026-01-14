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

Streaming Support (NEM-2592):
    - Large responses are cached using chunked storage in Redis
    - Memory usage is bounded by processing chunks incrementally
    - Responses exceeding max_payload_size are not cached
    - Chunked responses are stored as Redis lists for efficient retrieval

Usage:
    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware)

    # Or with custom configuration
    app.add_middleware(IdempotencyMiddleware, ttl=3600, key_prefix="idem")

    # With streaming configuration
    app.add_middleware(
        IdempotencyMiddleware,
        ttl=3600,
        max_payload_size=10485760,  # 10MB
        chunk_size=65536,  # 64KB
    )
"""

from __future__ import annotations

import base64
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
    """Middleware for idempotency key support on mutation endpoints.

    Supports streaming responses through chunked storage in Redis (NEM-2592).
    Large responses are stored as multiple chunks to bound memory usage.
    """

    def __init__(
        self,
        app: ASGIApp,
        ttl: int | None = None,
        key_prefix: str = "idempotency",
        max_payload_size: int | None = None,
        chunk_size: int | None = None,
    ):
        """Initialize IdempotencyMiddleware.

        Args:
            app: The ASGI application
            ttl: Time-to-live for cached responses in seconds
            key_prefix: Redis key prefix for idempotency keys
            max_payload_size: Maximum response size to cache (bytes). Responses
                larger than this are not cached to prevent memory pressure.
            chunk_size: Size of chunks for streaming response storage (bytes).
                Smaller chunks use less memory but require more Redis operations.
        """
        super().__init__(app)
        self.key_prefix = key_prefix

        settings = get_settings()

        if ttl is None:
            self.ttl = getattr(settings, "idempotency_ttl_seconds", 86400)
        else:
            self.ttl = ttl

        if max_payload_size is None:
            self.max_payload_size = getattr(settings, "idempotency_max_payload_size", 10485760)
        else:
            self.max_payload_size = max_payload_size

        if chunk_size is None:
            self.chunk_size = getattr(settings, "idempotency_chunk_size", 65536)
        else:
            self.chunk_size = chunk_size

    def _make_cache_key(self, idempotency_key: str) -> str:
        """Generate the main cache key for response metadata."""
        return f"{self.key_prefix}:{idempotency_key}"

    def _make_chunks_key(self, idempotency_key: str) -> str:
        """Generate the cache key for chunked response data."""
        return f"{self.key_prefix}:chunks:{idempotency_key}"

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

    async def _handle_cache_hit(
        self,
        redis: RedisClient,
        cached_data: dict,
        fingerprint: str,
        idempotency_key: str,
        request: Request,
    ) -> Response | None:
        """Handle a cache hit, returning the cached response or collision error."""
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

        # Check if response was stored with chunked storage
        is_chunked = cached_data.get("is_chunked", False)

        if is_chunked:
            # Retrieve chunked response
            return await self._replay_chunked_response(redis, cached_data, idempotency_key, request)
        else:
            # Simple response replay
            logger.info(
                "Returning cached idempotent response (replayed)",
                extra={
                    "idempotency_key": idempotency_key,
                    "path": request.url.path,
                    "cached_status": cached_data.get("status_code"),
                },
            )
            content = cached_data.get("content", "")
            # Handle binary content (base64 encoded)
            if cached_data.get("is_binary"):
                content_bytes = base64.b64decode(content)
            else:
                content_bytes = content.encode("utf-8")

            return Response(
                content=content_bytes,
                status_code=cached_data.get("status_code", 200),
                media_type=cached_data.get("media_type", "application/json"),
                headers={"Idempotency-Replayed": "true"},
            )

    async def _replay_chunked_response(
        self,
        redis: RedisClient,
        cached_data: dict,
        idempotency_key: str,
        request: Request,
    ) -> Response:
        """Replay a cached chunked streaming response."""
        chunks_key = self._make_chunks_key(idempotency_key)

        try:
            # Retrieve all chunks from Redis list
            chunk_count = cached_data.get("chunk_count", 0)
            chunks = await redis.lrange(chunks_key, 0, chunk_count - 1)

            # Reconstruct the response body
            response_body = b""
            for chunk_b64 in chunks:
                response_body += base64.b64decode(chunk_b64)

            logger.info(
                "Returning cached chunked idempotent response (replayed)",
                extra={
                    "idempotency_key": idempotency_key,
                    "path": request.url.path,
                    "cached_status": cached_data.get("status_code"),
                    "chunk_count": chunk_count,
                    "total_size": len(response_body),
                },
            )

            return Response(
                content=response_body,
                status_code=cached_data.get("status_code", 200),
                media_type=cached_data.get("media_type", "application/json"),
                headers={"Idempotency-Replayed": "true"},
            )
        except Exception as e:
            logger.error(
                f"Failed to replay chunked response: {e}",
                extra={"idempotency_key": idempotency_key},
            )
            # Return error response
            return Response(
                content=json.dumps({"detail": "Failed to replay cached response"}),
                status_code=500,
                media_type="application/json",
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
        """Cache the response for idempotency replay.

        For small responses (under chunk_size), stores directly in cache.
        For larger responses, uses chunked storage to bound memory usage.
        """
        # Check if response has body attribute (pre-rendered)
        if hasattr(response, "body"):
            body = response.body
            response_body = bytes(body) if isinstance(body, memoryview) else body

            # Check size limit for non-streaming responses
            if len(response_body) > self.max_payload_size:
                logger.debug(
                    "Response exceeds max payload size, skipping idempotency cache",
                    extra={
                        "idempotency_key": idempotency_key,
                        "response_size": len(response_body),
                        "max_size": self.max_payload_size,
                    },
                )
                return response

            # Use simple caching for small responses
            return await self._cache_simple_response(
                redis, cache_key, response_body, response, fingerprint, idempotency_key, request
            )

        elif hasattr(response, "body_iterator"):
            # Handle streaming response with chunked caching
            return await self._cache_streaming_response(
                redis, cache_key, response, fingerprint, idempotency_key, request
            )

        else:
            logger.warning(
                "Unknown response type, cannot cache for idempotency",
                extra={"idempotency_key": idempotency_key},
            )
            return response

    async def _cache_simple_response(
        self,
        redis: RedisClient,
        cache_key: str,
        response_body: bytes,
        response: Response,
        fingerprint: str,
        idempotency_key: str,
        request: Request,
    ) -> Response:
        """Cache a simple (non-streaming) response."""
        # Determine if content is binary
        is_binary = False
        try:
            content_str = response_body.decode("utf-8")
        except UnicodeDecodeError:
            # Binary content - base64 encode
            content_str = base64.b64encode(response_body).decode("ascii")
            is_binary = True

        cache_data = {
            "status_code": response.status_code,
            "content": content_str,
            "media_type": response.media_type,
            "fingerprint": fingerprint,
            "is_binary": is_binary,
        }

        await redis.setex(cache_key, self.ttl, json.dumps(cache_data))

        logger.debug(
            "Cached idempotent response",
            extra={
                "idempotency_key": idempotency_key,
                "path": request.url.path,
                "status_code": response.status_code,
                "ttl_seconds": self.ttl,
                "response_size": len(response_body),
            },
        )

        new_headers = dict(response.headers) if response.headers else {}
        return Response(
            content=response_body,
            status_code=response.status_code,
            media_type=response.media_type,
            headers=new_headers,
        )

    async def _cache_streaming_response(
        self,
        redis: RedisClient,
        cache_key: str,
        response: Response,
        fingerprint: str,
        idempotency_key: str,
        request: Request,
    ) -> Response:
        """Cache a streaming response using chunked storage.

        Processes the stream incrementally to bound memory usage.
        If the stream exceeds max_payload_size, aborts caching but still
        returns the response to the client.
        """
        chunks_key = self._make_chunks_key(idempotency_key)
        collected_chunks: list[bytes] = []
        total_size = 0
        chunk_count = 0
        exceeded_limit = False

        # Buffer for accumulating chunks to the configured chunk_size
        buffer = bytearray()

        async def process_and_cache_chunk(chunk_data: bytes) -> None:
            """Process a chunk of data, caching to Redis when buffer is full."""
            nonlocal chunk_count

            # Base64 encode for Redis storage
            chunk_b64 = base64.b64encode(chunk_data).decode("ascii")

            # Push chunk to Redis list
            await redis.rpush(chunks_key, chunk_b64)
            chunk_count += 1

        try:
            async for raw_chunk in response.body_iterator:  # type: ignore[attr-defined]
                chunk = raw_chunk.encode("utf-8") if isinstance(raw_chunk, str) else raw_chunk

                total_size += len(chunk)
                collected_chunks.append(chunk)

                # Check if we've exceeded the max payload size
                if total_size > self.max_payload_size:
                    exceeded_limit = True
                    logger.debug(
                        "Streaming response exceeded max payload size, aborting cache",
                        extra={
                            "idempotency_key": idempotency_key,
                            "total_size": total_size,
                            "max_size": self.max_payload_size,
                        },
                    )
                    # Continue collecting chunks for the response but don't cache
                    continue

                if not exceeded_limit:
                    # Add to buffer
                    buffer.extend(chunk)

                    # Flush buffer when it reaches chunk_size
                    while len(buffer) >= self.chunk_size:
                        chunk_to_cache = bytes(buffer[: self.chunk_size])
                        buffer = buffer[self.chunk_size :]
                        await process_and_cache_chunk(chunk_to_cache)

            # Flush remaining buffer
            if not exceeded_limit and buffer:
                await process_and_cache_chunk(bytes(buffer))

            # If we exceeded the limit, clean up any partial chunks and don't save metadata
            if exceeded_limit:
                try:
                    await redis.delete(chunks_key)
                except Exception:
                    logger.debug("Best effort cleanup failed for chunks_key", exc_info=True)
            else:
                # Store metadata
                cache_data = {
                    "status_code": response.status_code,
                    "media_type": response.media_type,
                    "fingerprint": fingerprint,
                    "is_chunked": True,
                    "chunk_count": chunk_count,
                    "total_size": total_size,
                }

                await redis.setex(cache_key, self.ttl, json.dumps(cache_data))
                # Set TTL on chunks list as well
                await redis.expire(chunks_key, self.ttl)

                logger.debug(
                    "Cached chunked idempotent response",
                    extra={
                        "idempotency_key": idempotency_key,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "ttl_seconds": self.ttl,
                        "total_size": total_size,
                        "chunk_count": chunk_count,
                    },
                )

        except Exception as e:
            logger.warning(
                f"Error during streaming response caching: {e}",
                extra={"idempotency_key": idempotency_key},
            )
            # Clean up partial chunks
            try:
                await redis.delete(chunks_key)
            except Exception:
                logger.debug("Best effort cleanup failed for chunks_key", exc_info=True)

        # Reconstruct response from collected chunks
        response_body = b"".join(collected_chunks)
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
                cache_response = await self._handle_cache_hit(
                    redis, cached_data, fingerprint, idempotency_key, request
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
