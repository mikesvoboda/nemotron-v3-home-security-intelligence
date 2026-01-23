"""Rate limiting middleware using Redis sliding window algorithm.

This module provides rate limiting functionality for FastAPI endpoints
using a sliding window counter algorithm implemented in Redis.

The sliding window approach provides smoother rate limiting compared to
fixed window counters, preventing request bursts at window boundaries.

Rate limiting is implemented using an atomic Lua script to prevent race
conditions. Unlike Redis pipelines which execute commands sequentially
but non-atomically, the Lua script ensures that the check-and-increment
operation happens as a single atomic operation.

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

import ipaddress
import time
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Request, WebSocket, status

from backend.core.config import get_settings
from backend.core.logging import get_logger, mask_ip
from backend.core.redis import RedisClient, get_redis

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = get_logger(__name__)

# Path to the Lua script for atomic rate limiting
_LUA_SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "sliding_window_rate_limit.lua"

# Cache for the loaded Lua script content
_lua_script_content: str | None = None

# Cache for the script SHA (set after SCRIPT LOAD)
_lua_script_sha: str | None = None


def _load_lua_script() -> str:
    """Load the Lua script content from disk.

    Returns:
        The Lua script content as a string.

    Raises:
        FileNotFoundError: If the script file doesn't exist.
    """
    global _lua_script_content  # noqa: PLW0603
    if _lua_script_content is None:
        _lua_script_content = _LUA_SCRIPT_PATH.read_text()
    return _lua_script_content


async def _get_script_sha(redis_client: RedisClient) -> str:
    """Get the SHA of the rate limiting Lua script, loading it if necessary.

    This function caches the script SHA to avoid reloading the script on
    every rate limit check. If the script is not loaded, it will be loaded
    using SCRIPT LOAD.

    Args:
        redis_client: Redis client instance.

    Returns:
        The SHA1 hash of the loaded script.

    Raises:
        Exception: If script loading fails.
    """
    global _lua_script_sha  # noqa: PLW0603
    if _lua_script_sha is None:
        script_content = _load_lua_script()
        client = redis_client._ensure_connected()
        _lua_script_sha = await client.script_load(script_content)
        logger.info("Loaded rate limiting Lua script", extra={"sha": _lua_script_sha})
    return _lua_script_sha


async def _execute_rate_limit_script(
    redis_client: RedisClient,
    key: str,
    now: float,
    window_seconds: int,
    limit: int,
) -> tuple[bool, int]:
    """Execute the atomic rate limiting Lua script.

    Args:
        redis_client: Redis client instance.
        key: The rate limit key.
        now: Current timestamp.
        window_seconds: Size of the sliding window in seconds.
        limit: Maximum number of requests allowed in the window.

    Returns:
        Tuple of (is_allowed, current_count).
    """
    from typing import Any, cast

    client = redis_client._ensure_connected()
    sha = await _get_script_sha(redis_client)

    try:
        result = cast(
            "list[Any]",
            await client.evalsha(sha, 1, key, str(now), str(window_seconds), str(limit)),  # type: ignore[misc]
        )
        is_allowed = result[0] == 1
        current_count = int(result[1])
        return is_allowed, current_count
    except Exception as e:
        # If NOSCRIPT error (script was flushed), reload and retry
        if "NOSCRIPT" in str(e):
            global _lua_script_sha  # noqa: PLW0603
            _lua_script_sha = None
            sha = await _get_script_sha(redis_client)
            result = cast(
                "list[Any]",
                await client.evalsha(sha, 1, key, str(now), str(window_seconds), str(limit)),  # type: ignore[misc]
            )
            is_allowed = result[0] == 1
            current_count = int(result[1])
            return is_allowed, current_count
        raise


def clear_lua_script_cache() -> None:
    """Clear the cached Lua script SHA.

    Useful for testing or when Redis is restarted and SCRIPT FLUSH occurs.
    """
    global _lua_script_sha, _lua_script_content  # noqa: PLW0603
    _lua_script_sha = None
    _lua_script_content = None


# Cache for pre-compiled trusted proxy networks
# Key: tuple of trusted IPs (for cache invalidation on config change)
# Value: tuple of (compiled_networks, compiled_ips)
_trusted_proxy_cache: dict[
    tuple[str, ...],
    tuple[
        list[ipaddress.IPv4Network | ipaddress.IPv6Network],
        list[ipaddress.IPv4Address | ipaddress.IPv6Address],
    ],
] = {}


def _mask_ip_for_logging(ip_string: str) -> str:
    """Mask an IP address for secure logging.

    Preserves the first octet/segment for debugging while masking
    the rest to protect potentially sensitive network topology.

    Args:
        ip_string: IP address or CIDR notation string

    Returns:
        Masked string like "192.xxx.xxx.xxx" or "2001:xxx:..."
    """
    # Strip CIDR suffix if present
    ip_part = ip_string.split("/")[0]

    if ":" in ip_part:
        # IPv6: mask all but first segment
        parts = ip_part.split(":")
        if parts:
            return f"{parts[0]}:xxx:..."
        return "xxx:..."
    else:
        # IPv4: mask all but first octet
        parts = ip_part.split(".")
        if parts:
            return f"{parts[0]}.xxx.xxx.xxx"
        return "xxx.xxx.xxx.xxx"


def _get_compiled_trusted_proxies(
    trusted_ips: list[str],
) -> tuple[
    list[ipaddress.IPv4Network | ipaddress.IPv6Network],
    list[ipaddress.IPv4Address | ipaddress.IPv6Address],
]:
    """Get pre-compiled trusted proxy networks and IPs.

    This function caches the compiled IP networks and addresses to avoid
    re-parsing CIDR notation on every request. The cache is keyed by the
    tuple of trusted IPs, so it automatically invalidates when the
    configuration changes.

    Args:
        trusted_ips: List of trusted IPs or CIDR ranges

    Returns:
        Tuple of (compiled_networks, compiled_ips) for efficient lookup
    """
    cache_key = tuple(trusted_ips)

    if cache_key in _trusted_proxy_cache:
        return _trusted_proxy_cache[cache_key]

    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []

    for trusted in trusted_ips:
        try:
            if "/" in trusted:
                # CIDR notation - compile as network
                networks.append(ipaddress.ip_network(trusted, strict=False))
            else:
                # Individual IP - compile as address
                ips.append(ipaddress.ip_address(trusted))
        except ValueError:
            # Invalid entry, log and skip (mask IP for security)
            masked_ip = _mask_ip_for_logging(trusted)
            logger.warning(
                "Invalid CIDR notation in trusted proxy configuration",
                extra={"invalid_trusted_ip_masked": masked_ip},
            )
            continue

    _trusted_proxy_cache[cache_key] = (networks, ips)
    return networks, ips


def clear_trusted_proxy_cache() -> None:
    """Clear the trusted proxy cache.

    Useful for testing or when configuration changes at runtime.
    """
    _trusted_proxy_cache.clear()


def _is_ip_trusted(client_ip: str, trusted_ips: list[str]) -> bool:
    """Check if an IP address is in the trusted proxy list.

    Supports both individual IPs and CIDR notation (e.g., '10.0.0.0/8').
    Uses pre-compiled networks for performance - CIDR parsing is done once
    and cached, not on every request.

    Args:
        client_ip: The IP address to check
        trusted_ips: List of trusted IPs or CIDR ranges

    Returns:
        True if the IP is trusted, False otherwise
    """
    try:
        ip_obj = ipaddress.ip_address(client_ip)
    except ValueError:
        # Invalid IP, not trusted
        return False

    # Get pre-compiled networks and IPs from cache
    networks, ips = _get_compiled_trusted_proxies(trusted_ips)

    # Check against individual IPs first (faster)
    if ip_obj in ips:
        return True

    # Check against CIDR networks
    return any(ip_obj in network for network in networks)


class RateLimitTier(str, Enum):
    """Rate limit tiers for different endpoint types."""

    DEFAULT = "default"
    MEDIA = "media"
    WEBSOCKET = "websocket"
    SEARCH = "search"
    EXPORT = "export"
    AI_INFERENCE = "ai_inference"
    BULK = "bulk"


def get_tier_limits(tier: RateLimitTier) -> tuple[int, int]:  # noqa: PLR0911
    """Get rate limit settings for a specific tier.

    Args:
        tier: The rate limit tier

    Returns:
        Tuple of (requests_per_minute, burst_allowance)
    """
    settings = get_settings()

    match tier:
        case RateLimitTier.MEDIA:
            return (settings.rate_limit_media_requests_per_minute, settings.rate_limit_burst)
        case RateLimitTier.WEBSOCKET:
            return (settings.rate_limit_websocket_connections_per_minute, 2)
        case RateLimitTier.SEARCH:
            return (settings.rate_limit_search_requests_per_minute, settings.rate_limit_burst)
        case RateLimitTier.EXPORT:
            # Export tier has no burst allowance to prevent abuse
            return (settings.rate_limit_export_requests_per_minute, 0)
        case RateLimitTier.AI_INFERENCE:
            # AI inference tier has strict limits due to computational cost
            return (
                settings.rate_limit_ai_inference_requests_per_minute,
                settings.rate_limit_ai_inference_burst,
            )
        case RateLimitTier.BULK:
            # Bulk tier has strict limits to prevent DoS via bulk operations
            return (
                settings.rate_limit_bulk_requests_per_minute,
                settings.rate_limit_bulk_burst,
            )
        case _:
            return (settings.rate_limit_requests_per_minute, settings.rate_limit_burst)


def get_client_ip(request: Request | WebSocket) -> str:
    """Extract client IP address from request.

    Handles X-Forwarded-For header for proxied requests, but ONLY when the
    direct client IP is from a trusted proxy. This prevents IP spoofing attacks
    where attackers forge X-Forwarded-For headers to bypass rate limits.

    Security:
        - X-Forwarded-For is only trusted when the request comes from a trusted proxy
        - Trusted proxies are configured via TRUSTED_PROXY_IPS setting
        - Default trusted proxies: 127.0.0.1, ::1 (localhost)
        - Supports CIDR notation (e.g., '10.0.0.0/8')

    Args:
        request: FastAPI Request or WebSocket object

    Returns:
        Client IP address as string
    """
    settings = get_settings()

    # Get direct client IP first
    direct_ip = "unknown"
    if request.client:
        direct_ip = str(request.client.host)

    # Only process X-Forwarded-For/X-Real-IP if the direct client is a trusted proxy
    if direct_ip != "unknown" and _is_ip_trusted(direct_ip, settings.trusted_proxy_ips):
        # Check for X-Forwarded-For header (common with reverse proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain (original client)
            client_ip = str(forwarded_for.split(",")[0].strip())
            if client_ip:
                return client_ip

        # Check for X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            client_ip = str(real_ip.strip())
            if client_ip:
                return client_ip

    # Return direct client IP (or "unknown" if not available)
    return direct_ip


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

        Uses an atomic Lua script to ensure the check-and-increment operation
        is performed atomically, preventing race conditions where multiple
        concurrent requests might all pass the count check before any of them
        increment the counter.

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

        # Total limit including burst
        total_limit = self.requests_per_minute + self.burst

        try:
            # Use atomic Lua script for rate limiting
            is_allowed, current_count = await _execute_rate_limit_script(
                redis_client,
                key,
                now,
                self.window_seconds,
                total_limit,
            )

            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded for {mask_ip(client_ip)} on tier {self.tier.value}: "
                    f"{current_count}/{total_limit} requests",
                    extra={
                        "client_ip": mask_ip(client_ip),
                        "tier": self.tier.value,
                        "current_count": current_count,
                        "limit": total_limit,
                    },
                )

            return (is_allowed, current_count, total_limit)

        except Exception as e:
            # On Redis errors, fail open (allow the request)
            logger.error(f"Rate limit check failed: {e}", exc_info=True)
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
            f"WebSocket rate limit exceeded for {mask_ip(client_ip)}: "
            f"{current_count}/{limit} connection attempts",
            extra={
                "client_ip": mask_ip(client_ip),
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


def rate_limit_export() -> RateLimiter:
    """Get export rate limiter dependency.

    The export tier has stricter limits (10 requests/minute, no burst)
    to prevent abuse of the CSV export functionality which could be used
    to overload the server or exfiltrate large amounts of data.
    """
    return RateLimiter(tier=RateLimitTier.EXPORT)


def rate_limit_ai_inference() -> RateLimiter:
    """Get AI inference rate limiter dependency.

    The AI inference tier has strict limits (10 requests/minute, burst of 3)
    to prevent abuse of computationally expensive AI endpoints like prompt
    testing which runs LLM inference. These endpoints consume significant
    GPU resources and could degrade system performance if abused.
    """
    return RateLimiter(tier=RateLimitTier.AI_INFERENCE)


def rate_limit_bulk() -> RateLimiter:
    """Get bulk operations rate limiter dependency.

    The bulk tier has strict limits (10 requests/minute, burst of 2) to
    prevent abuse of bulk operation endpoints (bulk_create_events,
    bulk_update_events, bulk_delete_events, and similar detection endpoints).
    These endpoints process up to 100 items per request, making them
    potential vectors for denial-of-service attacks.
    """
    return RateLimiter(tier=RateLimitTier.BULK)


# Type alias for cleaner dependency injection
async def get_rate_limiter(
    request: Request,
    redis: RedisClient = Depends(get_redis),
) -> AsyncGenerator[None]:
    """Default rate limiter as a dependency generator."""
    limiter = RateLimiter(tier=RateLimitTier.DEFAULT)
    await limiter(request, redis)
    yield
