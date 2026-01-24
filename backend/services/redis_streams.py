"""Redis Streams service for detection pipeline.

This module provides Redis Streams-based message queuing for the detection pipeline,
replacing list-based queues with a more robust streaming architecture.

Redis Streams Features:
    - Consumer groups for worker scaling and load balancing
    - Message acknowledgment with automatic redelivery
    - Stream trimming for memory management
    - Message IDs for ordering and deduplication

NEM-3364: Implements Redis Streams for detection processing pipeline.

Usage:
    from backend.services.redis_streams import (
        DetectionStreamService,
        get_detection_stream_service,
    )

    # Add detection to stream
    service = await get_detection_stream_service(redis_client)
    message_id = await service.add_detection(detection_data)

    # Process detections with consumer group
    async for message in service.consume_detections("worker-1"):
        await process_detection(message)
        await service.acknowledge(message.id)

Stream Keys:
    - detections:stream - Main detection stream
    - detections:stream:dlq - Dead-letter stream for failed messages

Consumer Groups:
    - detection-workers - Group for detection processing workers
"""

__all__ = [
    # Classes
    "DetectionStreamMessage",
    "DetectionStreamService",
    "StreamConsumerInfo",
    # Functions
    "get_detection_stream_service",
]

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.metrics import (
    record_pipeline_error,
)
from backend.core.redis import RedisClient

logger = get_logger(__name__)

# Stream configuration constants
DETECTION_STREAM_KEY = "detections:stream"
DETECTION_DLQ_STREAM_KEY = "detections:stream:dlq"
DETECTION_CONSUMER_GROUP = "detection-workers"

# Default stream limits
DEFAULT_STREAM_MAXLEN = 10000
DEFAULT_STREAM_APPROXIMATE = True  # Use ~ for efficient trimming
DEFAULT_BLOCK_MS = 5000  # 5 seconds block timeout for XREADGROUP
DEFAULT_CLAIM_MIN_IDLE_MS = 60000  # 1 minute idle before claiming
DEFAULT_MAX_DELIVERY_COUNT = 3  # Max redeliveries before DLQ


@dataclass(slots=True)
class DetectionStreamMessage:
    """Represents a message from the detection stream.

    Attributes:
        id: Redis stream message ID (e.g., "1234567890123-0")
        camera_id: Camera identifier
        detection_id: Detection database ID
        file_path: Path to the detection image
        confidence: Detection confidence score (0.0-1.0)
        object_type: Detected object type (e.g., "person", "car")
        timestamp: Unix timestamp when detection was created
        delivery_count: Number of times this message has been delivered
        raw_data: Original message data dictionary
    """

    id: str
    camera_id: str
    detection_id: int
    file_path: str
    confidence: float | None = None
    object_type: str | None = None
    timestamp: float = field(default_factory=time.time)
    delivery_count: int = 1
    raw_data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_stream_entry(
        cls, message_id: str, data: dict[str, str], delivery_count: int = 1
    ) -> DetectionStreamMessage:
        """Create a DetectionStreamMessage from a Redis stream entry.

        Args:
            message_id: Redis stream message ID
            data: Dictionary of field-value pairs from XREADGROUP
            delivery_count: Number of times message has been delivered

        Returns:
            DetectionStreamMessage instance
        """
        return cls(
            id=message_id,
            camera_id=data.get("camera_id", ""),
            detection_id=int(data.get("detection_id", 0)),
            file_path=data.get("file_path", ""),
            confidence=float(data["confidence"]) if data.get("confidence") else None,
            object_type=data.get("object_type"),
            timestamp=float(data.get("timestamp", time.time())),
            delivery_count=delivery_count,
            raw_data=data,
        )


@dataclass(slots=True)
class StreamConsumerInfo:
    """Information about a stream consumer.

    Attributes:
        name: Consumer name
        pending: Number of pending messages
        idle: Idle time in milliseconds
    """

    name: str
    pending: int
    idle: int


class DetectionStreamService:
    """Service for managing detection streams with Redis Streams.

    This service provides a high-level interface for:
    - Adding detections to the stream
    - Consuming detections with consumer groups
    - Acknowledging processed messages
    - Claiming stale messages from failed consumers
    - Moving failed messages to DLQ

    Thread Safety:
        This service is safe for concurrent use from multiple coroutines.
        Redis operations are atomic, and the service uses proper locking
        where needed for consumer group management.
    """

    def __init__(
        self,
        redis_client: RedisClient,
        stream_key: str = DETECTION_STREAM_KEY,
        consumer_group: str = DETECTION_CONSUMER_GROUP,
        maxlen: int | None = None,
        block_ms: int = DEFAULT_BLOCK_MS,
        claim_min_idle_ms: int = DEFAULT_CLAIM_MIN_IDLE_MS,
        max_delivery_count: int = DEFAULT_MAX_DELIVERY_COUNT,
    ):
        """Initialize detection stream service.

        Args:
            redis_client: Redis client instance
            stream_key: Redis key for the detection stream
            consumer_group: Name of the consumer group
            maxlen: Maximum stream length (None uses default)
            block_ms: Block timeout for XREADGROUP in milliseconds
            claim_min_idle_ms: Minimum idle time before claiming messages
            max_delivery_count: Max deliveries before moving to DLQ
        """
        self._redis = redis_client
        self._stream_key = stream_key
        self._dlq_key = f"{stream_key}:dlq"
        self._consumer_group = consumer_group
        self._maxlen = maxlen or DEFAULT_STREAM_MAXLEN
        self._block_ms = block_ms
        self._claim_min_idle_ms = claim_min_idle_ms
        self._max_delivery_count = max_delivery_count
        self._group_created = False
        self._group_create_lock = asyncio.Lock()

    async def _ensure_consumer_group(self) -> None:
        """Ensure the consumer group exists, creating it if necessary.

        Creates the consumer group starting from the beginning of the stream
        (ID "0") if it doesn't exist. This is idempotent - calling multiple
        times is safe.

        Raises:
            RuntimeError: If Redis client not connected
        """
        if self._group_created:
            return

        async with self._group_create_lock:
            # Double-check after acquiring lock
            if self._group_created:
                return

            if not self._redis._client:
                raise RuntimeError("Redis client not connected")

            try:
                # Try to create the consumer group
                # MKSTREAM creates the stream if it doesn't exist
                await self._redis._client.xgroup_create(
                    self._stream_key,
                    self._consumer_group,
                    id="0",
                    mkstream=True,
                )
                logger.info(
                    "Created consumer group",
                    extra={
                        "stream_key": self._stream_key,
                        "consumer_group": self._consumer_group,
                    },
                )
            except Exception as e:
                # BUSYGROUP error means group already exists - that's fine
                if "BUSYGROUP" in str(e):
                    logger.debug(
                        "Consumer group already exists",
                        extra={
                            "stream_key": self._stream_key,
                            "consumer_group": self._consumer_group,
                        },
                    )
                else:
                    raise

            self._group_created = True

    async def add_detection(
        self,
        camera_id: str,
        detection_id: int,
        file_path: str,
        confidence: float | None = None,
        object_type: str | None = None,
        timestamp: float | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> str:
        """Add a detection to the stream.

        Args:
            camera_id: Camera identifier
            detection_id: Detection database ID
            file_path: Path to the detection image
            confidence: Detection confidence score (0.0-1.0)
            object_type: Detected object type
            timestamp: Unix timestamp (defaults to current time)
            extra_fields: Additional fields to include in the message

        Returns:
            Redis stream message ID (e.g., "1234567890123-0")

        Raises:
            RuntimeError: If Redis client not connected
            ValueError: If required fields are missing
        """
        if not self._redis._client:
            raise RuntimeError("Redis client not connected")

        if not camera_id:
            raise ValueError("camera_id is required")
        if not detection_id:
            raise ValueError("detection_id is required")
        if not file_path:
            raise ValueError("file_path is required")

        # Build message fields
        message_fields: dict[str, str] = {
            "camera_id": camera_id,
            "detection_id": str(detection_id),
            "file_path": file_path,
            "timestamp": str(timestamp or time.time()),
        }

        if confidence is not None:
            message_fields["confidence"] = str(confidence)
        if object_type is not None:
            message_fields["object_type"] = object_type
        if extra_fields:
            for key, value in extra_fields.items():
                message_fields[key] = str(value) if not isinstance(value, str) else value

        # Add to stream with MAXLEN for automatic trimming
        # Use approximate (~) trimming for better performance
        message_id: str = await self._redis._client.xadd(
            self._stream_key,
            message_fields,  # type: ignore[arg-type]
            maxlen=self._maxlen,
            approximate=DEFAULT_STREAM_APPROXIMATE,
        )

        logger.debug(
            "Added detection to stream",
            extra={
                "stream_key": self._stream_key,
                "message_id": message_id,
                "camera_id": camera_id,
                "detection_id": detection_id,
            },
        )

        return message_id

    async def consume_detections(
        self,
        consumer_name: str,
        count: int = 1,
        block: bool = True,
    ) -> list[DetectionStreamMessage]:
        """Consume detections from the stream using a consumer group.

        This method reads messages from the stream that haven't been
        delivered to this consumer group yet (using ">"), or pending
        messages that need to be reprocessed.

        Args:
            consumer_name: Unique name for this consumer within the group
            count: Maximum number of messages to read
            block: Whether to block waiting for messages

        Returns:
            List of DetectionStreamMessage instances (may be empty)

        Raises:
            RuntimeError: If Redis client not connected
        """
        if not self._redis._client:
            raise RuntimeError("Redis client not connected")

        await self._ensure_consumer_group()

        try:
            # Read new messages (using ">")
            block_ms = self._block_ms if block else None
            result = await self._redis._client.xreadgroup(
                self._consumer_group,
                consumer_name,
                {self._stream_key: ">"},
                count=count,
                block=block_ms,
            )

            if not result:
                return []

            # Parse messages
            messages: list[DetectionStreamMessage] = []
            for _stream_name, stream_messages in result:
                for message_id, data in stream_messages:
                    try:
                        msg = DetectionStreamMessage.from_stream_entry(
                            message_id,
                            data,
                            delivery_count=1,  # First delivery
                        )
                        messages.append(msg)
                    except (ValueError, KeyError) as e:
                        logger.warning(
                            "Failed to parse stream message",
                            extra={
                                "message_id": message_id,
                                "error": str(e),
                            },
                        )
                        record_pipeline_error("stream_parse_error")
                        continue

            return messages

        except Exception as e:
            logger.error(
                "Error consuming from stream",
                extra={
                    "stream_key": self._stream_key,
                    "consumer_group": self._consumer_group,
                    "consumer_name": consumer_name,
                    "error": str(e),
                },
            )
            raise

    async def acknowledge(self, message_id: str) -> bool:
        """Acknowledge a message as successfully processed.

        This removes the message from the consumer's pending entries list (PEL).
        Acknowledged messages will not be redelivered.

        Args:
            message_id: Redis stream message ID to acknowledge

        Returns:
            True if message was acknowledged, False if not found

        Raises:
            RuntimeError: If Redis client not connected
        """
        if not self._redis._client:
            raise RuntimeError("Redis client not connected")

        result = await self._redis._client.xack(
            self._stream_key,
            self._consumer_group,
            message_id,
        )

        if result > 0:
            logger.debug(
                "Acknowledged stream message",
                extra={
                    "stream_key": self._stream_key,
                    "message_id": message_id,
                },
            )
            return True
        return False

    async def claim_stale_messages(
        self,
        consumer_name: str,
        count: int = 10,
    ) -> list[DetectionStreamMessage]:
        """Claim messages from consumers that have been idle too long.

        This is used for recovering messages from failed/crashed consumers.
        Messages that have been pending for longer than claim_min_idle_ms
        will be claimed by this consumer.

        Args:
            consumer_name: Name of the consumer claiming messages
            count: Maximum number of messages to claim

        Returns:
            List of claimed DetectionStreamMessage instances

        Raises:
            RuntimeError: If Redis client not connected
        """
        if not self._redis._client:
            raise RuntimeError("Redis client not connected")

        await self._ensure_consumer_group()

        try:
            # Use XAUTOCLAIM for automatic claiming of idle messages
            result = await self._redis._client.xautoclaim(
                self._stream_key,
                self._consumer_group,
                consumer_name,
                self._claim_min_idle_ms,
                start_id="0-0",
                count=count,
            )

            if not result or len(result) < 2:
                return []

            # XAUTOCLAIM returns: (next_id, [(id, data), ...], deleted_ids)
            claimed_messages = result[1] if len(result) > 1 else []

            messages: list[DetectionStreamMessage] = []
            for message_id, data in claimed_messages:
                if data is None:
                    # Message was deleted
                    continue
                try:
                    # Get delivery count from pending info
                    pending_info = await self._redis._client.xpending_range(
                        self._stream_key,
                        self._consumer_group,
                        min=message_id,
                        max=message_id,
                        count=1,
                    )
                    delivery_count = pending_info[0][3] if pending_info else 1

                    msg = DetectionStreamMessage.from_stream_entry(
                        message_id,
                        data,
                        delivery_count=delivery_count,
                    )
                    messages.append(msg)
                except (ValueError, KeyError, IndexError) as e:
                    logger.warning(
                        "Failed to parse claimed message",
                        extra={
                            "message_id": message_id,
                            "error": str(e),
                        },
                    )
                    continue

            if messages:
                logger.info(
                    "Claimed stale messages",
                    extra={
                        "stream_key": self._stream_key,
                        "consumer_name": consumer_name,
                        "claimed_count": len(messages),
                    },
                )

            return messages

        except Exception as e:
            logger.error(
                "Error claiming stale messages",
                extra={
                    "stream_key": self._stream_key,
                    "consumer_name": consumer_name,
                    "error": str(e),
                },
            )
            raise

    async def move_to_dlq(
        self,
        message: DetectionStreamMessage,
        reason: str = "max_delivery_exceeded",
    ) -> str:
        """Move a failed message to the dead-letter queue.

        This acknowledges the original message and adds it to the DLQ stream
        with metadata about why it failed.

        Args:
            message: The message to move to DLQ
            reason: Reason for moving to DLQ

        Returns:
            DLQ message ID

        Raises:
            RuntimeError: If Redis client not connected
        """
        if not self._redis._client:
            raise RuntimeError("Redis client not connected")

        # Build DLQ message with original data plus metadata
        dlq_fields: dict[str, str] = {
            **{k: str(v) for k, v in message.raw_data.items()},
            "original_message_id": message.id,
            "dlq_reason": reason,
            "dlq_timestamp": str(time.time()),
            "delivery_count": str(message.delivery_count),
        }

        # Add to DLQ stream
        dlq_message_id: str = await self._redis._client.xadd(
            self._dlq_key,
            dlq_fields,  # type: ignore[arg-type]
            maxlen=self._maxlen,
            approximate=DEFAULT_STREAM_APPROXIMATE,
        )

        # Acknowledge the original message
        await self.acknowledge(message.id)

        logger.warning(
            "Moved message to DLQ",
            extra={
                "original_message_id": message.id,
                "dlq_message_id": dlq_message_id,
                "reason": reason,
                "delivery_count": message.delivery_count,
            },
        )

        record_pipeline_error("stream_dlq_move")

        return dlq_message_id

    async def should_move_to_dlq(self, message: DetectionStreamMessage) -> bool:
        """Check if a message should be moved to DLQ based on delivery count.

        Args:
            message: Message to check

        Returns:
            True if message has exceeded max delivery count
        """
        return message.delivery_count >= self._max_delivery_count

    async def get_stream_info(self) -> dict[str, Any]:
        """Get information about the detection stream.

        Returns:
            Dictionary with stream statistics including:
            - length: Number of messages in stream
            - radix_tree_keys: Number of radix tree keys
            - radix_tree_nodes: Number of radix tree nodes
            - groups: Number of consumer groups
            - last_entry_id: ID of the last entry
            - first_entry_id: ID of the first entry

        Raises:
            RuntimeError: If Redis client not connected
        """
        if not self._redis._client:
            raise RuntimeError("Redis client not connected")

        try:
            info = await self._redis._client.xinfo_stream(self._stream_key)
            return {
                "length": info.get("length", 0),
                "radix_tree_keys": info.get("radix-tree-keys", 0),
                "radix_tree_nodes": info.get("radix-tree-nodes", 0),
                "groups": info.get("groups", 0),
                "last_entry_id": info.get("last-generated-id", ""),
                "first_entry_id": info.get("first-entry", [""])[0]
                if info.get("first-entry")
                else "",
            }
        except Exception as e:
            if "no such key" in str(e).lower():
                return {
                    "length": 0,
                    "radix_tree_keys": 0,
                    "radix_tree_nodes": 0,
                    "groups": 0,
                    "last_entry_id": "",
                    "first_entry_id": "",
                }
            raise

    async def get_consumer_group_info(self) -> dict[str, Any]:
        """Get information about the consumer group.

        Returns:
            Dictionary with consumer group statistics including:
            - name: Group name
            - consumers: Number of consumers in group
            - pending: Number of pending messages
            - last_delivered_id: Last delivered message ID

        Raises:
            RuntimeError: If Redis client not connected
        """
        if not self._redis._client:
            raise RuntimeError("Redis client not connected")

        try:
            await self._ensure_consumer_group()
            groups = await self._redis._client.xinfo_groups(self._stream_key)

            for group in groups:
                if group.get("name") == self._consumer_group:
                    return {
                        "name": group.get("name", ""),
                        "consumers": group.get("consumers", 0),
                        "pending": group.get("pending", 0),
                        "last_delivered_id": group.get("last-delivered-id", ""),
                    }

            return {
                "name": self._consumer_group,
                "consumers": 0,
                "pending": 0,
                "last_delivered_id": "",
            }
        except Exception as e:
            if "no such key" in str(e).lower():
                return {
                    "name": self._consumer_group,
                    "consumers": 0,
                    "pending": 0,
                    "last_delivered_id": "",
                }
            raise

    async def get_pending_count(self, consumer_name: str | None = None) -> int:
        """Get the count of pending messages.

        Args:
            consumer_name: If provided, get pending count for specific consumer

        Returns:
            Number of pending messages

        Raises:
            RuntimeError: If Redis client not connected
        """
        if not self._redis._client:
            raise RuntimeError("Redis client not connected")

        try:
            await self._ensure_consumer_group()
            pending = await self._redis._client.xpending(
                self._stream_key,
                self._consumer_group,
            )

            if not pending:
                return 0

            if consumer_name:
                # Get pending for specific consumer from the consumers list
                consumers = pending.get("consumers", [])
                for consumer in consumers:
                    if consumer.get("name") == consumer_name:
                        pending_count: int = consumer.get("pending", 0)
                        return pending_count
                return 0

            total_pending: int = pending.get("pending", 0)
            return total_pending
        except Exception as e:
            if "no such key" in str(e).lower():
                return 0
            raise

    async def trim_stream(self, maxlen: int | None = None) -> int:
        """Manually trim the stream to a maximum length.

        Args:
            maxlen: Maximum length to trim to (uses default if None)

        Returns:
            Number of entries removed

        Raises:
            RuntimeError: If Redis client not connected
        """
        if not self._redis._client:
            raise RuntimeError("Redis client not connected")

        effective_maxlen = maxlen or self._maxlen

        # Get current length before trim
        try:
            info = await self._redis._client.xinfo_stream(self._stream_key)
            current_length: int = info.get("length", 0)
        except Exception:
            current_length = 0

        # Trim the stream
        await self._redis._client.xtrim(
            self._stream_key,
            maxlen=effective_maxlen,
            approximate=DEFAULT_STREAM_APPROXIMATE,
        )

        # Calculate removed count
        try:
            info = await self._redis._client.xinfo_stream(self._stream_key)
            new_length: int = info.get("length", 0)
            removed: int = max(0, current_length - new_length)
        except Exception:
            removed = 0
            new_length = 0

        if removed > 0:
            logger.info(
                "Trimmed stream",
                extra={
                    "stream_key": self._stream_key,
                    "removed_count": removed,
                    "new_length": new_length,
                },
            )

        return removed


# Global service instance
_detection_stream_service: DetectionStreamService | None = None


async def get_detection_stream_service(
    redis_client: RedisClient,
) -> DetectionStreamService:
    """Get or create the detection stream service.

    This function implements lazy initialization and singleton pattern
    for the detection stream service.

    Args:
        redis_client: Redis client instance

    Returns:
        DetectionStreamService instance
    """
    global _detection_stream_service  # noqa: PLW0603

    if _detection_stream_service is None:
        settings = get_settings()
        _detection_stream_service = DetectionStreamService(
            redis_client=redis_client,
            maxlen=settings.queue_max_size,
        )

    return _detection_stream_service
