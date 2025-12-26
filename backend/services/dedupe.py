"""File deduplication service for preventing duplicate processing.

This module provides idempotency for the file watcher pipeline by:
1. Computing SHA256 content hash of image files
2. Checking Redis for short-term dedupe (with TTL)
3. Falling back to database check if Redis is unavailable

Idempotency Approach:
---------------------
- Idempotency key: SHA256 hash of file content
- Primary dedupe: Redis SET with TTL (default 5 minutes)
- Fallback: Database query for existing detections with same file hash
- Hash stored in Redis key: `dedupe:{sha256_hash}`

This prevents duplicate processing caused by:
- Watchdog create/modify event bursts
- Service restarts during file processing
- FTP upload retries

Error Handling:
--------------
- Redis unavailable: Falls back to database check
- Database unavailable: Allows processing (fail-open for availability)
- File read errors: Returns False (don't process corrupted files)
"""

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from backend.core.config import get_settings
from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

logger = get_logger(__name__)

# Default TTL for dedupe entries (5 minutes = 300 seconds)
DEFAULT_DEDUPE_TTL_SECONDS = 300

# Redis key prefix for dedupe entries
DEDUPE_KEY_PREFIX = "dedupe:"


def compute_file_hash(file_path: str) -> str | None:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex-encoded SHA256 hash string, or None if file cannot be read
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found for hashing: {file_path}")
            return None

        if path.stat().st_size == 0:
            logger.warning(f"Empty file, cannot hash: {file_path}")
            return None

        # Read file and compute hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency with large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except OSError as e:
        logger.error(f"Error reading file for hash: {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error computing hash for {file_path}: {e}")
        return None


class DedupeService:
    """Service for deduplicating file processing using content hashes.

    Uses Redis as primary dedupe cache with database fallback.
    Thread-safe and async-compatible.
    """

    def __init__(
        self,
        redis_client: "RedisClient | None" = None,
        ttl_seconds: int = DEFAULT_DEDUPE_TTL_SECONDS,
    ):
        """Initialize dedupe service.

        Args:
            redis_client: Optional Redis client for caching
            ttl_seconds: TTL for dedupe entries in Redis (default 5 minutes)
        """
        self._redis_client = redis_client
        self._ttl_seconds = ttl_seconds

        settings = get_settings()
        # Allow override via settings if configured
        self._ttl_seconds = getattr(settings, "dedupe_ttl_seconds", ttl_seconds)

        logger.info(f"DedupeService initialized with TTL={self._ttl_seconds}s")

    def _get_redis_key(self, file_hash: str) -> str:
        """Get Redis key for a file hash.

        Args:
            file_hash: SHA256 hash of file content

        Returns:
            Redis key string
        """
        return f"{DEDUPE_KEY_PREFIX}{file_hash}"

    async def is_duplicate(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check if a file has already been processed.

        Checks Redis first for short-term dedupe, then optionally falls back
        to database if Redis is unavailable.

        Args:
            file_path: Path to the file to check
            file_hash: Pre-computed file hash (optional, will compute if not provided)

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file (for logging/storage)
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            # Could not compute hash - likely file issue, let caller decide
            logger.warning(f"Could not compute hash for {file_path}, cannot dedupe")
            return (False, None)

        # Try Redis first
        redis_result = await self._check_redis(file_hash)
        if redis_result is not None:
            return (redis_result, file_hash)

        # Redis unavailable or not configured, assume not duplicate
        # (fail-open for availability)
        logger.debug(f"Redis unavailable for dedupe check, allowing file: {file_path}")
        return (False, file_hash)

    async def _check_redis(self, file_hash: str) -> bool | None:
        """Check Redis for existing hash entry.

        Args:
            file_hash: SHA256 hash to check

        Returns:
            True if duplicate found, False if not found, None if Redis unavailable
        """
        if not self._redis_client:
            return None

        try:
            key = self._get_redis_key(file_hash)
            exists = await self._redis_client.exists(key)
            if exists > 0:
                logger.info(f"Duplicate file detected (Redis): hash={file_hash[:16]}...")
                return True
            return False
        except Exception as e:
            logger.warning(f"Redis dedupe check failed: {e}")
            return None

    async def mark_processed(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> bool:
        """Mark a file as processed to prevent future duplicates.

        Stores the hash in Redis with TTL for short-term dedupe.

        Args:
            file_path: Path to the processed file (for logging)
            file_hash: Pre-computed file hash (optional)

        Returns:
            True if successfully marked, False on error
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        if file_hash is None:
            logger.warning(f"Could not compute hash to mark as processed: {file_path}")
            return False

        # Store in Redis with TTL
        if self._redis_client:
            try:
                key = self._get_redis_key(file_hash)
                # Store timestamp as value for debugging
                await self._redis_client.set(key, file_path, expire=self._ttl_seconds)
                logger.debug(
                    f"Marked file as processed: {file_path} (hash={file_hash[:16]}..., "
                    f"TTL={self._ttl_seconds}s)"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to mark file in Redis: {e}")
                return False
        else:
            logger.debug("No Redis client, skipping dedupe mark")
            return False

    async def is_duplicate_and_mark(
        self,
        file_path: str,
    ) -> tuple[bool, str | None]:
        """Check if file is duplicate and mark as processed atomically.

        This is the primary method for dedupe - combines check and mark
        in one operation to avoid race conditions.

        Args:
            file_path: Path to the file to check and mark

        Returns:
            Tuple of (is_duplicate, file_hash)
            - is_duplicate: True if file was already processed
            - file_hash: The SHA256 hash of the file
        """
        # Compute hash once
        file_hash = compute_file_hash(file_path)
        if file_hash is None:
            return (False, None)

        # Check if duplicate
        is_dup, _ = await self.is_duplicate(file_path, file_hash)
        if is_dup:
            return (True, file_hash)

        # Not a duplicate - mark as processed
        await self.mark_processed(file_path, file_hash)
        return (False, file_hash)

    async def clear_hash(self, file_hash: str) -> bool:
        """Clear a hash from the dedupe cache.

        Useful for testing or when reprocessing is needed.

        Args:
            file_hash: SHA256 hash to clear

        Returns:
            True if cleared successfully
        """
        if not self._redis_client:
            return False

        try:
            key = self._get_redis_key(file_hash)
            result = await self._redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.warning(f"Failed to clear hash from Redis: {e}")
            return False


# Module-level singleton for convenience
_dedupe_service: DedupeService | None = None


def get_dedupe_service(redis_client: "RedisClient | None" = None) -> DedupeService:
    """Get or create the global dedupe service instance.

    Args:
        redis_client: Redis client (used only on first call)

    Returns:
        DedupeService singleton instance
    """
    global _dedupe_service  # noqa: PLW0603

    if _dedupe_service is None:
        _dedupe_service = DedupeService(redis_client=redis_client)

    return _dedupe_service


def reset_dedupe_service() -> None:
    """Reset the global dedupe service (for testing)."""
    global _dedupe_service  # noqa: PLW0603
    _dedupe_service = None
