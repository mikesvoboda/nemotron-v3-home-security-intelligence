"""Redis JSON service for batch metadata storage.

This module provides RedisJSON-based storage for complex batch metadata,
enabling efficient nested structure storage and partial updates.

RedisJSON Features:
    - Native JSON storage without serialization overhead
    - JSONPath queries for partial reads
    - Atomic partial updates
    - Type preservation for nested structures

NEM-3366: Implements Redis JSON for batch metadata storage.

Usage:
    from backend.services.redis_json import (
        BatchMetadataService,
        get_batch_metadata_service,
    )

    # Store batch metadata
    service = await get_batch_metadata_service(redis_client)
    await service.set_batch_metadata(batch_id, metadata)

    # Query specific fields
    status = await service.get_batch_field(batch_id, "$.status")

    # Update partial metadata
    await service.update_batch_field(batch_id, "$.processed_count", 42)

Key Schema:
    batch:meta:{batch_id} - JSON document containing batch metadata

Fallback Behavior:
    If RedisJSON module is not available, falls back to standard
    Redis string storage with JSON serialization.
"""

__all__ = [
    # Classes
    "BatchMetadata",
    "BatchMetadataService",
    # Functions
    "get_batch_metadata_service",
]

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.redis import RedisClient

logger = get_logger(__name__)

# Key prefix for batch metadata
BATCH_META_PREFIX = "batch:meta:"

# Default TTL for batch metadata (1 hour)
DEFAULT_BATCH_META_TTL = 3600


@dataclass
class BatchMetadata:
    """Structured batch metadata stored in Redis JSON.

    Attributes:
        batch_id: Unique batch identifier
        camera_id: Camera identifier
        status: Current batch status (open, closing, closed, failed)
        detection_ids: List of detection IDs in this batch
        detection_count: Number of detections in batch
        started_at: Unix timestamp when batch was created
        last_activity: Unix timestamp of last activity
        closed_at: Unix timestamp when batch was closed (None if open)
        pipeline_start_time: ISO timestamp for pipeline latency tracking
        close_reason: Reason for batch closure (timeout, idle, max_size)
        processing_metadata: Additional processing metadata
    """

    batch_id: str
    camera_id: str
    status: str = "open"
    detection_ids: list[int] = field(default_factory=list)
    detection_count: int = 0
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    closed_at: float | None = None
    pipeline_start_time: str | None = None
    close_reason: str | None = None
    processing_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BatchMetadata:
        """Create BatchMetadata from dictionary."""
        return cls(
            batch_id=data.get("batch_id", ""),
            camera_id=data.get("camera_id", ""),
            status=data.get("status", "open"),
            detection_ids=data.get("detection_ids", []),
            detection_count=data.get("detection_count", 0),
            started_at=data.get("started_at", time.time()),
            last_activity=data.get("last_activity", time.time()),
            closed_at=data.get("closed_at"),
            pipeline_start_time=data.get("pipeline_start_time"),
            close_reason=data.get("close_reason"),
            processing_metadata=data.get("processing_metadata", {}),
        )


class BatchMetadataService:
    """Service for managing batch metadata with Redis JSON.

    This service provides a high-level interface for:
    - Storing batch metadata as JSON documents
    - Querying specific fields with JSONPath
    - Atomic partial updates
    - Automatic TTL management

    Fallback Behavior:
        If RedisJSON module is not available, the service falls back to
        standard Redis string operations with manual JSON serialization.
        All public methods work identically regardless of backend.
    """

    def __init__(
        self,
        redis_client: RedisClient,
        key_prefix: str = BATCH_META_PREFIX,
        default_ttl: int = DEFAULT_BATCH_META_TTL,
    ):
        """Initialize batch metadata service.

        Args:
            redis_client: Redis client instance
            key_prefix: Prefix for batch metadata keys
            default_ttl: Default TTL for metadata in seconds
        """
        self._redis = redis_client
        self._key_prefix = key_prefix
        self._default_ttl = default_ttl
        self._json_available: bool | None = None

    def _get_key(self, batch_id: str) -> str:
        """Get the Redis key for a batch's metadata.

        Args:
            batch_id: Batch identifier

        Returns:
            Redis key string
        """
        return f"{self._key_prefix}{batch_id}"

    async def _check_json_available(self) -> bool:
        """Check if RedisJSON module is available.

        Returns:
            True if RedisJSON is available, False otherwise
        """
        if self._json_available is not None:
            return self._json_available

        if not self._redis._client:
            return False

        try:
            # Try to execute a simple JSON command
            await self._redis._client.execute_command("JSON.SET", "_test_json", "$", "{}")
            await self._redis._client.delete("_test_json")
            self._json_available = True
            logger.info("RedisJSON module is available")
        except Exception as e:
            if "unknown command" in str(e).lower() or "ERR" in str(e):
                self._json_available = False
                logger.info("RedisJSON module not available, using fallback")
            else:
                # Some other error, assume JSON is available but had a transient issue
                self._json_available = False
                logger.warning(
                    "Error checking RedisJSON availability, using fallback",
                    extra={"error": str(e)},
                )

        return self._json_available

    async def set_batch_metadata(
        self,
        batch_id: str,
        metadata: BatchMetadata | dict[str, Any],
        ttl: int | None = None,
    ) -> bool:
        """Store batch metadata in Redis.

        Args:
            batch_id: Batch identifier
            metadata: BatchMetadata instance or dictionary
            ttl: TTL in seconds (uses default if None)

        Returns:
            True if successful

        Raises:
            RuntimeError: If Redis client not connected
        """
        if not self._redis._client:
            raise RuntimeError("Redis client not connected")

        key = self._get_key(batch_id)
        effective_ttl = ttl or self._default_ttl

        # Convert to dict if needed
        data = metadata.to_dict() if isinstance(metadata, BatchMetadata) else metadata

        if await self._check_json_available():
            # Use RedisJSON
            try:
                await self._redis._client.execute_command(
                    "JSON.SET",
                    key,
                    "$",
                    json.dumps(data),
                )
                await self._redis._client.expire(key, effective_ttl)
                logger.debug(
                    "Stored batch metadata with RedisJSON",
                    extra={"batch_id": batch_id, "key": key},
                )
                return True
            except Exception as e:
                logger.warning(
                    "RedisJSON SET failed, falling back to string",
                    extra={"error": str(e)},
                )
                # Fall through to string fallback

        # Fallback: Use standard Redis string
        json_str = json.dumps(data)
        await self._redis._client.setex(key, effective_ttl, json_str)
        logger.debug(
            "Stored batch metadata with string fallback",
            extra={"batch_id": batch_id, "key": key},
        )
        return True

    async def get_batch_metadata(self, batch_id: str) -> BatchMetadata | None:
        """Retrieve batch metadata from Redis.

        Args:
            batch_id: Batch identifier

        Returns:
            BatchMetadata instance or None if not found

        Raises:
            RuntimeError: If Redis client not connected
        """
        if not self._redis._client:
            raise RuntimeError("Redis client not connected")

        key = self._get_key(batch_id)

        if await self._check_json_available():
            try:
                result = await self._redis._client.execute_command(
                    "JSON.GET",
                    key,
                )
                if result:
                    data = json.loads(result)
                    return BatchMetadata.from_dict(data)
                return None
            except Exception as e:
                if "no such key" not in str(e).lower():
                    logger.warning(
                        "RedisJSON GET failed, falling back to string",
                        extra={"error": str(e)},
                    )
                # Fall through to string fallback

        # Fallback: Use standard Redis string
        result = await self._redis._client.get(key)
        if result:
            data = json.loads(result)
            return BatchMetadata.from_dict(data)
        return None

    async def get_batch_field(
        self,
        batch_id: str,
        json_path: str,
    ) -> Any | None:
        """Get a specific field from batch metadata using JSONPath.

        Args:
            batch_id: Batch identifier
            json_path: JSONPath expression (e.g., "$.status", "$.detection_ids")

        Returns:
            Field value or None if not found

        Raises:
            RuntimeError: If Redis client not connected
        """
        if not self._redis._client:
            raise RuntimeError("Redis client not connected")

        key = self._get_key(batch_id)

        if await self._check_json_available():
            try:
                result = await self._redis._client.execute_command(
                    "JSON.GET",
                    key,
                    json_path,
                )
                if result:
                    # JSON.GET returns a JSON array for path results
                    parsed = json.loads(result)
                    return parsed[0] if isinstance(parsed, list) and parsed else parsed
                return None
            except Exception as e:
                if "no such key" not in str(e).lower():
                    logger.warning(
                        "RedisJSON GET path failed, falling back to full fetch",
                        extra={"error": str(e)},
                    )
                # Fall through to fallback

        # Fallback: Fetch full document and extract path
        metadata = await self.get_batch_metadata(batch_id)
        if metadata is None:
            return None

        # Simple JSONPath extraction (supports $.field format)
        data = metadata.to_dict()
        path_parts = json_path.replace("$.", "").split(".")
        value: Any = data
        for part in path_parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value

    async def update_batch_field(
        self,
        batch_id: str,
        json_path: str,
        value: Any,
        refresh_ttl: bool = True,
    ) -> bool:
        """Update a specific field in batch metadata.

        Args:
            batch_id: Batch identifier
            json_path: JSONPath expression (e.g., "$.status", "$.detection_count")
            value: New value to set
            refresh_ttl: Whether to refresh TTL on update

        Returns:
            True if successful, False if batch not found

        Raises:
            RuntimeError: If Redis client not connected
        """
        if not self._redis._client:
            raise RuntimeError("Redis client not connected")

        key = self._get_key(batch_id)

        if await self._check_json_available():
            try:
                # Use JSON.SET with path for atomic partial update
                await self._redis._client.execute_command(
                    "JSON.SET",
                    key,
                    json_path,
                    json.dumps(value),
                )
                if refresh_ttl:
                    await self._redis._client.expire(key, self._default_ttl)
                logger.debug(
                    "Updated batch field with RedisJSON",
                    extra={"batch_id": batch_id, "path": json_path},
                )
                return True
            except Exception as e:
                if "no such key" in str(e).lower():
                    return False
                logger.warning(
                    "RedisJSON SET path failed, falling back to full update",
                    extra={"error": str(e)},
                )
                # Fall through to fallback

        # Fallback: Fetch, update, and store full document
        metadata = await self.get_batch_metadata(batch_id)
        if metadata is None:
            return False

        # Simple JSONPath update (supports $.field format)
        data = metadata.to_dict()
        path_parts = json_path.replace("$.", "").split(".")
        target = data
        for part in path_parts[:-1]:
            if isinstance(target, dict) and part in target:
                target = target[part]
            else:
                return False
        if isinstance(target, dict):
            target[path_parts[-1]] = value

        await self.set_batch_metadata(batch_id, data, self._default_ttl if refresh_ttl else None)
        return True

    async def append_detection_id(
        self,
        batch_id: str,
        detection_id: int,
    ) -> int:
        """Append a detection ID to batch metadata.

        This is an optimized operation for the common case of adding
        a detection to a batch.

        Args:
            batch_id: Batch identifier
            detection_id: Detection ID to append

        Returns:
            New count of detection IDs, or -1 if batch not found

        Raises:
            RuntimeError: If Redis client not connected
        """
        if not self._redis._client:
            raise RuntimeError("Redis client not connected")

        key = self._get_key(batch_id)

        if await self._check_json_available():
            try:
                # Use JSON.ARRAPPEND for atomic array append
                await self._redis._client.execute_command(
                    "JSON.ARRAPPEND",
                    key,
                    "$.detection_ids",
                    str(detection_id),
                )
                # Also increment detection_count
                await self._redis._client.execute_command(
                    "JSON.NUMINCRBY",
                    key,
                    "$.detection_count",
                    "1",
                )
                # Update last_activity
                await self._redis._client.execute_command(
                    "JSON.SET",
                    key,
                    "$.last_activity",
                    str(time.time()),
                )
                await self._redis._client.expire(key, self._default_ttl)

                # Get new count
                result = await self._redis._client.execute_command(
                    "JSON.GET",
                    key,
                    "$.detection_count",
                )
                if result:
                    counts = json.loads(result)
                    return counts[0] if counts else -1
                return -1
            except Exception as e:
                if "no such key" in str(e).lower():
                    return -1
                logger.warning(
                    "RedisJSON ARRAPPEND failed, falling back to full update",
                    extra={"error": str(e)},
                )
                # Fall through to fallback

        # Fallback: Fetch, update, store
        metadata = await self.get_batch_metadata(batch_id)
        if metadata is None:
            return -1

        metadata.detection_ids.append(detection_id)
        metadata.detection_count = len(metadata.detection_ids)
        metadata.last_activity = time.time()

        await self.set_batch_metadata(batch_id, metadata)
        return metadata.detection_count

    async def close_batch(
        self,
        batch_id: str,
        reason: str = "timeout",
    ) -> bool:
        """Mark a batch as closed.

        Args:
            batch_id: Batch identifier
            reason: Close reason (timeout, idle, max_size, manual)

        Returns:
            True if successful, False if batch not found

        Raises:
            RuntimeError: If Redis client not connected
        """
        if not self._redis._client:
            raise RuntimeError("Redis client not connected")

        key = self._get_key(batch_id)
        close_time = time.time()

        if await self._check_json_available():
            try:
                # Check if key exists first
                exists = await self._redis._client.exists(key)
                if not exists:
                    return False

                # Atomic multi-field update using JSON.MSET (if available) or pipeline
                async with self._redis._client.pipeline(transaction=True) as pipe:
                    pipe.execute_command("JSON.SET", key, "$.status", '"closed"')
                    pipe.execute_command("JSON.SET", key, "$.closed_at", str(close_time))
                    pipe.execute_command("JSON.SET", key, "$.close_reason", f'"{reason}"')
                    await pipe.execute()

                logger.debug(
                    "Closed batch with RedisJSON",
                    extra={"batch_id": batch_id, "reason": reason},
                )
                return True
            except Exception as e:
                logger.warning(
                    "RedisJSON close failed, falling back to full update",
                    extra={"error": str(e)},
                )
                # Fall through to fallback

        # Fallback: Fetch, update, store
        metadata = await self.get_batch_metadata(batch_id)
        if metadata is None:
            return False

        metadata.status = "closed"
        metadata.closed_at = close_time
        metadata.close_reason = reason

        await self.set_batch_metadata(batch_id, metadata)
        return True

    async def delete_batch_metadata(self, batch_id: str) -> bool:
        """Delete batch metadata from Redis.

        Args:
            batch_id: Batch identifier

        Returns:
            True if deleted, False if not found

        Raises:
            RuntimeError: If Redis client not connected
        """
        if not self._redis._client:
            raise RuntimeError("Redis client not connected")

        key = self._get_key(batch_id)
        result: int = await self._redis._client.delete(key)
        return result > 0

    async def get_open_batches_for_camera(self, camera_id: str) -> list[BatchMetadata]:
        """Get all open batches for a specific camera.

        Note: This requires scanning keys, which can be slow for large datasets.
        Consider using a secondary index (e.g., a set per camera) for production.

        Args:
            camera_id: Camera identifier

        Returns:
            List of open BatchMetadata instances for the camera

        Raises:
            RuntimeError: If Redis client not connected
        """
        if not self._redis._client:
            raise RuntimeError("Redis client not connected")

        batches: list[BatchMetadata] = []

        # Scan for all batch metadata keys
        async for key in self._redis._client.scan_iter(
            match=f"{self._key_prefix}*",
            count=100,
        ):
            try:
                key_str = key.decode() if isinstance(key, bytes) else key
                batch_id = key_str.replace(self._key_prefix, "")
                metadata = await self.get_batch_metadata(batch_id)

                if metadata and metadata.camera_id == camera_id and metadata.status == "open":
                    batches.append(metadata)
            except Exception as e:
                logger.debug(
                    "Error reading batch metadata during scan",
                    extra={"key": key, "error": str(e)},
                )
                continue

        return batches


# Global service instance
_batch_metadata_service: BatchMetadataService | None = None


async def get_batch_metadata_service(
    redis_client: RedisClient,
) -> BatchMetadataService:
    """Get or create the batch metadata service.

    This function implements lazy initialization and singleton pattern
    for the batch metadata service.

    Args:
        redis_client: Redis client instance

    Returns:
        BatchMetadataService instance
    """
    global _batch_metadata_service  # noqa: PLW0603

    if _batch_metadata_service is None:
        settings = get_settings()
        _batch_metadata_service = BatchMetadataService(
            redis_client=redis_client,
            default_ttl=settings.batch_metadata_ttl
            if hasattr(settings, "batch_metadata_ttl")
            else DEFAULT_BATCH_META_TTL,
        )

    return _batch_metadata_service
