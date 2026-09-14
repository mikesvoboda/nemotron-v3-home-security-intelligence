"""Redis memory optimization service (NEM-3416).

This service provides memory management capabilities for Redis:

1. Memory limit configuration (maxmemory)
2. Eviction policy management (maxmemory-policy)
3. Memory statistics and analytics
4. Key protection for critical data

Eviction Policies:
- volatile-lru: Evict keys with TTL using LRU (recommended default)
- allkeys-lru: Evict any key using LRU
- volatile-ttl: Evict keys with shortest TTL first
- volatile-random: Random eviction among keys with TTL
- allkeys-random: Random eviction among all keys
- noeviction: Return errors when memory full

The 'volatile-lru' policy is recommended because:
- It protects permanent keys (without TTL) from eviction
- Cache keys with TTL are safely evictable
- LRU ensures most recently used data stays in memory

Example usage:
    memory_service = await get_redis_memory_service()

    # Apply memory configuration
    await memory_service.configure_memory_limits()

    # Get memory statistics
    stats = await memory_service.get_memory_stats()
    print(f"Used: {stats['used_memory_mb']:.2f} MB")

    # Find large keys for optimization
    large_keys = await memory_service.find_large_keys(min_size_bytes=1024)
"""

from dataclasses import dataclass
from typing import Any

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.redis import RedisClient, init_redis

logger = get_logger(__name__)


@dataclass(slots=True)
class MemoryStats:
    """Redis memory statistics."""

    used_memory_bytes: int
    used_memory_mb: float
    used_memory_peak_bytes: int
    used_memory_peak_mb: float
    maxmemory_bytes: int
    maxmemory_mb: float
    maxmemory_policy: str
    memory_fragmentation_ratio: float
    total_keys: int
    keys_with_ttl: int
    evicted_keys: int
    is_memory_limited: bool
    memory_usage_percent: float


@dataclass(slots=True)
class KeyMemoryInfo:
    """Memory information for a specific key."""

    key: str
    memory_bytes: int
    memory_kb: float
    key_type: str | None = None


class RedisMemoryService:
    """Service for managing Redis memory configuration and optimization.

    Provides:
    - Memory limit configuration
    - Eviction policy management
    - Memory statistics collection
    - Large key identification
    - Memory optimization recommendations
    """

    def __init__(self, redis_client: RedisClient):
        """Initialize the Redis memory service.

        Args:
            redis_client: Connected Redis client
        """
        self._redis = redis_client
        self._settings = get_settings()

    async def configure_memory_limits(self) -> dict[str, Any]:
        """Apply memory configuration to Redis server.

        This method sends CONFIG SET commands to configure:
        - maxmemory: Maximum memory limit
        - maxmemory-policy: Eviction policy when limit is reached

        Note: Requires Redis ACL permissions for CONFIG command.
        Only runs if redis_memory_apply_on_startup is True in settings.

        Returns:
            Dictionary with configuration results
        """
        results: dict[str, Any] = {
            "applied": False,
            "maxmemory_mb": None,
            "maxmemory_policy": None,
            "errors": [],
        }

        # Check if we should apply settings
        if not self._settings.redis_memory_apply_on_startup:
            logger.debug("Redis memory configuration skipped (apply_on_startup=False)")
            results["skipped"] = True
            results["reason"] = "redis_memory_apply_on_startup is False"
            return results

        memory_limit_mb = self._settings.redis_memory_limit_mb
        memory_policy = self._settings.redis_memory_policy

        # Apply memory limit if specified (0 means unlimited)
        if memory_limit_mb > 0:
            try:
                memory_limit_bytes = memory_limit_mb * 1024 * 1024
                await self._redis.config_set("maxmemory", str(memory_limit_bytes))
                results["maxmemory_mb"] = memory_limit_mb
                logger.info(f"Set Redis maxmemory to {memory_limit_mb} MB")
            except Exception as e:
                error_msg = f"Failed to set maxmemory: {e}"
                logger.warning(error_msg)
                results["errors"].append(error_msg)

        # Apply eviction policy
        try:
            await self._redis.config_set("maxmemory-policy", memory_policy)
            results["maxmemory_policy"] = memory_policy
            logger.info(f"Set Redis maxmemory-policy to {memory_policy}")
        except Exception as e:
            error_msg = f"Failed to set maxmemory-policy: {e}"
            logger.warning(error_msg)
            results["errors"].append(error_msg)

        results["applied"] = len(results["errors"]) == 0
        return results

    async def get_memory_stats(self) -> MemoryStats:
        """Get comprehensive memory statistics from Redis.

        Returns:
            MemoryStats dataclass with memory usage information
        """
        # Get memory info from Redis INFO command
        info = await self._redis.info("memory")
        server_info = await self._redis.info("stats")
        keyspace_info = await self._redis.info("keyspace")

        # Parse memory values
        used_memory = info.get("used_memory", 0)
        used_memory_peak = info.get("used_memory_peak", 0)
        maxmemory = info.get("maxmemory", 0)
        fragmentation_ratio = info.get("mem_fragmentation_ratio", 1.0)

        # Get eviction policy
        config = await self._redis.config_get("maxmemory-policy")
        maxmemory_policy = config.get("maxmemory-policy", "noeviction")

        # Get key counts
        total_keys = await self._redis.dbsize()

        # Parse keyspace info for keys with TTL (approximate)
        # Format: db0:keys=X,expires=Y,avg_ttl=Z
        keys_with_ttl = 0
        for _db_name, db_info in keyspace_info.items():
            if isinstance(db_info, dict) and "expires" in db_info:
                keys_with_ttl += db_info.get("expires", 0)

        # Get evicted keys count
        evicted_keys = server_info.get("evicted_keys", 0)

        # Calculate usage percentage
        memory_usage_percent = 0.0
        if maxmemory > 0:
            memory_usage_percent = (used_memory / maxmemory) * 100

        return MemoryStats(
            used_memory_bytes=used_memory,
            used_memory_mb=used_memory / (1024 * 1024),
            used_memory_peak_bytes=used_memory_peak,
            used_memory_peak_mb=used_memory_peak / (1024 * 1024),
            maxmemory_bytes=maxmemory,
            maxmemory_mb=maxmemory / (1024 * 1024) if maxmemory > 0 else 0,
            maxmemory_policy=maxmemory_policy,
            memory_fragmentation_ratio=fragmentation_ratio,
            total_keys=total_keys,
            keys_with_ttl=keys_with_ttl,
            evicted_keys=evicted_keys,
            is_memory_limited=maxmemory > 0,
            memory_usage_percent=memory_usage_percent,
        )

    async def get_current_config(self) -> dict[str, str]:
        """Get current Redis memory configuration.

        Returns:
            Dictionary with current maxmemory and maxmemory-policy values
        """
        maxmemory_config = await self._redis.config_get("maxmemory")
        policy_config = await self._redis.config_get("maxmemory-policy")

        maxmemory_bytes = int(maxmemory_config.get("maxmemory", 0))
        maxmemory_mb = maxmemory_bytes / (1024 * 1024) if maxmemory_bytes > 0 else 0

        return {
            "maxmemory_bytes": str(maxmemory_bytes),
            "maxmemory_mb": f"{maxmemory_mb:.2f}",
            "maxmemory_policy": policy_config.get("maxmemory-policy", "noeviction"),
            "maxmemory_human": f"{maxmemory_mb:.0f}MB" if maxmemory_mb > 0 else "unlimited",
        }

    async def find_large_keys(
        self,
        pattern: str = "*",
        min_size_bytes: int = 1024,
        max_keys: int = 100,
    ) -> list[KeyMemoryInfo]:
        """Find keys that use significant memory.

        Useful for identifying optimization opportunities.

        Args:
            pattern: Glob pattern to filter keys
            min_size_bytes: Minimum size in bytes to include (default: 1KB)
            max_keys: Maximum number of keys to return

        Returns:
            List of KeyMemoryInfo sorted by size (largest first)
        """
        large_keys: list[KeyMemoryInfo] = []

        # Scan for keys matching pattern
        keys = await self._redis.scan_keys(pattern=pattern, max_keys=max_keys * 10)

        for key in keys:
            try:
                memory_bytes = await self._redis.memory_usage(key)
                if memory_bytes is not None and memory_bytes >= min_size_bytes:
                    large_keys.append(
                        KeyMemoryInfo(
                            key=key,
                            memory_bytes=memory_bytes,
                            memory_kb=memory_bytes / 1024,
                        )
                    )
            except Exception as e:
                logger.debug(f"Could not get memory usage for key {key}: {e}")
                continue

            if len(large_keys) >= max_keys:
                break

        # Sort by size descending
        large_keys.sort(key=lambda x: x.memory_bytes, reverse=True)
        return large_keys[:max_keys]

    async def get_key_memory_usage(self, key: str) -> int | None:
        """Get memory usage for a specific key.

        Args:
            key: Redis key to check

        Returns:
            Memory usage in bytes, or None if key doesn't exist
        """
        return await self._redis.memory_usage(key)

    async def get_memory_recommendations(self) -> list[str]:
        """Get memory optimization recommendations based on current state.

        Returns:
            List of recommendation strings
        """
        recommendations: list[str] = []
        stats = await self.get_memory_stats()

        # Check if memory limit is set
        if not stats.is_memory_limited:
            recommendations.append(
                "Consider setting a memory limit (maxmemory) to prevent Redis "
                "from using all available system memory. Recommended: 256MB for dev, "
                "1-4GB for production."
            )

        # Check memory usage
        if stats.memory_usage_percent > 90:
            recommendations.append(
                f"Memory usage is critically high ({stats.memory_usage_percent:.1f}%). "
                "Consider increasing maxmemory or reviewing TTL settings for cached data."
            )
        elif stats.memory_usage_percent > 75:
            recommendations.append(
                f"Memory usage is elevated ({stats.memory_usage_percent:.1f}%). "
                "Monitor for potential evictions."
            )

        # Check eviction policy
        if stats.maxmemory_policy == "noeviction" and stats.is_memory_limited:
            recommendations.append(
                "Using 'noeviction' policy with a memory limit. Consider switching to "
                "'volatile-lru' to allow graceful eviction of cached data."
            )

        # Check fragmentation
        if stats.memory_fragmentation_ratio > 1.5:
            recommendations.append(
                f"High memory fragmentation detected (ratio: {stats.memory_fragmentation_ratio:.2f}). "
                "Consider running MEMORY PURGE or restarting Redis during maintenance."
            )

        # Check evicted keys
        if stats.evicted_keys > 0:
            recommendations.append(
                f"{stats.evicted_keys} keys have been evicted due to memory pressure. "
                "Consider increasing memory limit if eviction is causing performance issues."
            )

        # Check keys with TTL
        if stats.total_keys > 0:
            ttl_percent = (stats.keys_with_ttl / stats.total_keys) * 100
            if ttl_percent < 50 and stats.maxmemory_policy.startswith("volatile"):
                recommendations.append(
                    f"Only {ttl_percent:.1f}% of keys have TTL, but using volatile-* eviction policy. "
                    "Consider using 'allkeys-lru' or adding TTL to more keys."
                )

        if not recommendations:
            recommendations.append("Redis memory configuration looks healthy.")

        return recommendations


# Singleton instance
_redis_memory_service: RedisMemoryService | None = None


async def get_redis_memory_service() -> RedisMemoryService:
    """Get or create the Redis memory service singleton.

    Returns:
        RedisMemoryService instance connected to Redis
    """
    global _redis_memory_service  # noqa: PLW0603
    if _redis_memory_service is None:
        redis_client = await init_redis()
        _redis_memory_service = RedisMemoryService(redis_client)
    return _redis_memory_service


async def reset_redis_memory_service() -> None:
    """Reset the Redis memory service singleton (for testing)."""
    global _redis_memory_service  # noqa: PLW0603
    _redis_memory_service = None


async def apply_memory_configuration_on_startup() -> dict[str, Any]:
    """Apply Redis memory configuration during application startup.

    This function should be called during the FastAPI lifespan startup
    if redis_memory_apply_on_startup is True.

    Returns:
        Dictionary with configuration results
    """
    service = await get_redis_memory_service()
    return await service.configure_memory_limits()
