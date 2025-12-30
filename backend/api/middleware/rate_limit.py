"""Rate limiting middleware using Redis sliding window algorithm.

This module provides rate limiting functionality for FastAPI endpoints
using a sliding window counter algorithm implemented in Redis.

The sliding window approach provides smoother rate limiting compared to
fixed window counters, preventing request bursts at window boundaries.

Usage:
    # As a FastAPI dependency
    @router.get("/endpoint")
    async def endpoint(
        _: None = Depends(RateLimiter(requests_per_minute=60)),
    ):
        ...

    # For WebSocket connections
    if not await check_websocket_rate_limit(websocket, redis_client):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Request, WebSocket, status

from backend.core.config import get_settings
from backend.core.redis import RedisClient, get_redis

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)


class RateLimitTier(str, Enum):
    """Rate limit tiers for different endpoint types."""

    DEFAULT = "default"
    MEDIA = "media"
    WEBSOCKET = "websocket"
    SEARCH = "search"


def get_tier_limits(tier: RateLimitTier) -> tuple[int, int]:
    """Get rate limit settings for a specific tier.

    Args:
        tier: The rate limit tier

    Returns:
        Tuple of (requests_per_minute, burst_allowance)
    """
    settings = get_settings()

    if tier == RateLimitTier.MEDIA:
        return (settings.rate_limit_media_requests_per_minute, settings.rate_limit_burst)
    elif tier == RateLimitTier.WEBSOCKET:
        return (settings.rate_limit_websocket_connections_per_minute, 2)
    elif tier == RateLimitTier.SEARCH:
        return (settings.rate_limit_search_requests_per_minute, settings.rate_limit_burst)
    else:
        return (settings.rate_limit_requests_per_minute, settings.rate_limit_burst)


def get_client_ip(request: Request | WebSocket) -> str:
    """Extract client IP address from request.

    Handles X-Forwarded-For header for proxied requests.

    Args:
        request: FastAPI Request or WebSocket object

    Returns:
        Client IP address as string
    """
    # Check for X-Forwarded-For header (common with reverse proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return str(forwarded_for.split(",")[0].strip())

    # Check for X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return str(real_ip.strip())

    # Fall back to direct client IP
    if request.client:
        return str(request.client.host)

    return "unknown"


class RateLimiter:
    """FastAPI dependency for rate limiting using Redis sliding window.

    The sliding window algorithm divides time into fixed-size windows and
    tracks request counts using Redis sorted sets with timestamps as scores.

    Example:
        @router.get("/api/data")
        async def get_data(
            _: None = Depends(RateLimiter(tier=RateLimitTier.DEFAULT)),
        ):
            return {"data": "value"}
    """

    def __init__(
        self,
        tier: RateLimitTier = RateLimitTier.DEFAULT,
        requests_per_minute: int | None = None,
        burst: int | None = None,
        key_prefix: str = "rate_limit",
    ):
        """Initialize rate limiter.

        Args:
            tier: Rate limit tier (uses tier-specific defaults)
            requests_per_minute: Override requests per minute limit
            burst: Override burst allowance
            key_prefix: Redis key prefix for rate limit counters
        """
        self.tier = tier
        self._requests_per_minute = requests_per_minute
        self._burst = burst
        self.key_prefix = key_prefix
        self.window_seconds = 60  # 1 minute sliding window

    @property
    def requests_per_minute(self) -> int:
        """Get requests per minute limit."""
        if self._requests_per_minute is not None:
            return self._requests_per_minute
        limits = get_tier_limits(self.tier)
        return limits[0]

    @property
    def burst(self) -> int:
        """Get burst allowance."""
        if self._burst is not None:
            return self._burst
        limits = get_tier_limits(self.tier)
        return limits[1]

    def _make_key(self, client_ip: str) -> str:
        """Create Redis key for rate limiting.

        Args:
            client_ip: Client IP address

        Returns:
            Redis key string
        """
        return f"{self.key_prefix}:{self.tier.value}:{client_ip}"

    async def _check_rate_limit(
        self,
        redis_client: RedisClient,
        client_ip: str,
    ) -> tuple[bool, int, int]:
        """Check if request is within rate limits using sliding window.

        Args:
            redis_client: Redis client instance
            client_ip: Client IP address

        Returns:
            Tuple of (is_allowed, current_count, limit)
        """
        settings = get_settings()

        # Skip if rate limiting is disabled
        if not settings.rate_limit_enabled:
            return (True, 0, self.requests_per_minute)

        key = self._make_key(client_ip)
        now = time.time()
        window_start = now - self.window_seconds

        # Total limit including burst
        total_limit = self.requests_per_minute + self.burst

        try:
            client = redis_client._ensure_connected()

            # Use Redis pipeline for atomic operations
            pipe = client.pipeline()

            # Remove expired entries (outside the sliding window)
            pipe.zremrangebyscore(key, "-inf", window_start)

            # Count current requests in window
            pipe.zcard(key)

            # Add current request with timestamp
            pipe.zadd(key, {f"{now}": now})

            # Set expiry on the key (slightly longer than window)
            pipe.expire(key, self.window_seconds + 10)

            results = await pipe.execute()

            # Pipeline returns: removed count, current count, added count, expiry set
            current_count = results[1]

            # Check if over limit (count is before adding current request)
            is_allowed = current_count < total_limit

            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded for {client_ip} on tier {self.tier.value}: "
                    f"{current_count}/{total_limit} requests",
                    extra={
                        "client_ip": client_ip,
                        "tier": self.tier.value,
                        "current_count": current_count,
                        "limit": total_limit,
                    },
                )

            return (is_allowed, current_count, total_limit)

        except Exception as e:
            # On Redis errors, fail open (allow the request)
            logger.error(f"Rate limit check failed: {e}")
            return (True, 0, self.requests_per_minute)

    async def __call__(
        self,
        request: Request,
        redis: RedisClient = Depends(get_redis),
    ) -> None:
        """FastAPI dependency that checks rate limits.

        Args:
            request: FastAPI request
            redis: Redis client (injected)

        Raises:
            HTTPException: 429 Too Many Requests if rate limit exceeded
        """
        client_ip = get_client_ip(request)
        is_allowed, _current_count, limit = await self._check_rate_limit(redis, client_ip)

        if not is_allowed:
            # Calculate retry-after (time until next request is allowed)
            retry_after = self.window_seconds

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Too many requests",
                    "message": f"Rate limit exceeded. Maximum {limit} requests per minute.",
                    "retry_after_seconds": retry_after,
                    "tier": self.tier.value,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + retry_after),
                },
            )


async def check_websocket_rate_limit(
    websocket: WebSocket,
    redis_client: RedisClient,
) -> bool:
    """Check rate limit for WebSocket connection attempts.

    This should be called before accepting a WebSocket connection
    to prevent connection flood attacks.

    Args:
        websocket: WebSocket connection
        redis_client: Redis client instance

    Returns:
        True if connection is allowed, False if rate limited
    """
    settings = get_settings()

    # Skip if rate limiting is disabled
    if not settings.rate_limit_enabled:
        return True

    client_ip = get_client_ip(websocket)
    limiter = RateLimiter(tier=RateLimitTier.WEBSOCKET)

    is_allowed, current_count, limit = await limiter._check_rate_limit(redis_client, client_ip)

    if not is_allowed:
        logger.warning(
            f"WebSocket rate limit exceeded for {client_ip}: "
            f"{current_count}/{limit} connection attempts",
            extra={
                "client_ip": client_ip,
                "current_count": current_count,
                "limit": limit,
            },
        )

    return is_allowed


# Convenience dependencies for common use cases
def rate_limit_default() -> RateLimiter:
    """Get default rate limiter dependency."""
    return RateLimiter(tier=RateLimitTier.DEFAULT)


def rate_limit_media() -> RateLimiter:
    """Get media rate limiter dependency."""
    return RateLimiter(tier=RateLimitTier.MEDIA)


def rate_limit_search() -> RateLimiter:
    """Get search rate limiter dependency."""
    return RateLimiter(tier=RateLimitTier.SEARCH)


# Type alias for cleaner dependency injection
async def get_rate_limiter(
    request: Request,
    redis: RedisClient = Depends(get_redis),
) -> AsyncGenerator[None]:
    """Default rate limiter as a dependency generator."""
    limiter = RateLimiter(tier=RateLimitTier.DEFAULT)
    await limiter(request, redis)
    yield
