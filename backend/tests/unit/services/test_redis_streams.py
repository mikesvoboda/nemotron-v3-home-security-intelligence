"""Unit tests for Redis Streams service.

NEM-3364: Tests for Redis Streams-based detection pipeline.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis import RedisClient
from backend.services.redis_streams import (
    DEFAULT_BLOCK_MS,
    DEFAULT_CLAIM_MIN_IDLE_MS,
    DEFAULT_MAX_DELIVERY_COUNT,
    DEFAULT_STREAM_MAXLEN,
    DETECTION_CONSUMER_GROUP,
    DETECTION_STREAM_KEY,
    DetectionStreamMessage,
    DetectionStreamService,
    get_detection_stream_service,
)

# ===========================================================================
# Test: DetectionStreamMessage dataclass
# ===========================================================================


class TestDetectionStreamMessage:
    """Tests for the DetectionStreamMessage dataclass."""

    def test_create_message_with_required_fields(self):
        """Test creating a message with only required fields."""
        msg = DetectionStreamMessage(
            id="1234567890123-0",
            camera_id="front_door",
            detection_id=42,
            file_path="/export/foscam/front_door/image.jpg",
        )
        assert msg.id == "1234567890123-0"
        assert msg.camera_id == "front_door"
        assert msg.detection_id == 42
        assert msg.file_path == "/export/foscam/front_door/image.jpg"
        assert msg.confidence is None
        assert msg.object_type is None
        assert msg.delivery_count == 1

    def test_create_message_with_all_fields(self):
        """Test creating a message with all fields populated."""
        timestamp = time.time()
        msg = DetectionStreamMessage(
            id="1234567890123-1",
            camera_id="backyard",
            detection_id=123,
            file_path="/export/foscam/backyard/video.mp4",
            confidence=0.95,
            object_type="person",
            timestamp=timestamp,
            delivery_count=3,
            raw_data={"extra": "data"},
        )
        assert msg.confidence == 0.95
        assert msg.object_type == "person"
        assert msg.timestamp == timestamp
        assert msg.delivery_count == 3
        assert msg.raw_data == {"extra": "data"}

    def test_from_stream_entry_basic(self):
        """Test creating a message from a Redis stream entry."""
        message_id = "1234567890123-0"
        data = {
            "camera_id": "front_door",
            "detection_id": "42",
            "file_path": "/export/foscam/front_door/image.jpg",
            "timestamp": "1700000000.0",
        }

        msg = DetectionStreamMessage.from_stream_entry(message_id, data)

        assert msg.id == message_id
        assert msg.camera_id == "front_door"
        assert msg.detection_id == 42
        assert msg.file_path == "/export/foscam/front_door/image.jpg"
        assert msg.timestamp == 1700000000.0
        assert msg.delivery_count == 1

    def test_from_stream_entry_with_optional_fields(self):
        """Test creating a message from stream entry with optional fields."""
        message_id = "1234567890123-0"
        data = {
            "camera_id": "front_door",
            "detection_id": "42",
            "file_path": "/export/foscam/front_door/image.jpg",
            "timestamp": "1700000000.0",
            "confidence": "0.92",
            "object_type": "car",
        }

        msg = DetectionStreamMessage.from_stream_entry(message_id, data, delivery_count=2)

        assert msg.confidence == 0.92
        assert msg.object_type == "car"
        assert msg.delivery_count == 2

    def test_from_stream_entry_with_missing_optional_fields(self):
        """Test that missing optional fields get proper defaults."""
        message_id = "1234567890123-0"
        data = {
            "camera_id": "front_door",
            "detection_id": "42",
            "file_path": "/export/foscam/front_door/image.jpg",
        }

        msg = DetectionStreamMessage.from_stream_entry(message_id, data)

        assert msg.confidence is None
        assert msg.object_type is None
        # timestamp should default to current time (approximately)
        assert abs(msg.timestamp - time.time()) < 1.0


# ===========================================================================
# Test: DetectionStreamService
# ===========================================================================


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client for testing."""
    mock = MagicMock(spec=RedisClient)
    mock._client = AsyncMock()
    return mock


@pytest.fixture
def stream_service(mock_redis_client):
    """Create a DetectionStreamService with mocked Redis."""
    return DetectionStreamService(
        redis_client=mock_redis_client,
        stream_key=DETECTION_STREAM_KEY,
        consumer_group=DETECTION_CONSUMER_GROUP,
    )


class TestDetectionStreamServiceInit:
    """Tests for DetectionStreamService initialization."""

    def test_default_configuration(self, mock_redis_client):
        """Test service initializes with correct defaults."""
        service = DetectionStreamService(redis_client=mock_redis_client)

        assert service._stream_key == DETECTION_STREAM_KEY
        assert service._dlq_key == f"{DETECTION_STREAM_KEY}:dlq"
        assert service._consumer_group == DETECTION_CONSUMER_GROUP
        assert service._maxlen == DEFAULT_STREAM_MAXLEN
        assert service._block_ms == DEFAULT_BLOCK_MS
        assert service._claim_min_idle_ms == DEFAULT_CLAIM_MIN_IDLE_MS
        assert service._max_delivery_count == DEFAULT_MAX_DELIVERY_COUNT

    def test_custom_configuration(self, mock_redis_client):
        """Test service accepts custom configuration."""
        service = DetectionStreamService(
            redis_client=mock_redis_client,
            stream_key="custom:stream",
            consumer_group="custom-group",
            maxlen=5000,
            block_ms=10000,
            claim_min_idle_ms=120000,
            max_delivery_count=5,
        )

        assert service._stream_key == "custom:stream"
        assert service._dlq_key == "custom:stream:dlq"
        assert service._consumer_group == "custom-group"
        assert service._maxlen == 5000
        assert service._block_ms == 10000
        assert service._claim_min_idle_ms == 120000
        assert service._max_delivery_count == 5


class TestDetectionStreamServiceEnsureConsumerGroup:
    """Tests for consumer group creation."""

    @pytest.mark.asyncio
    async def test_creates_consumer_group_once(self, stream_service, mock_redis_client):
        """Test that consumer group is created only once."""
        mock_redis_client._client.xgroup_create = AsyncMock()

        await stream_service._ensure_consumer_group()
        await stream_service._ensure_consumer_group()
        await stream_service._ensure_consumer_group()

        # Should only be called once
        assert mock_redis_client._client.xgroup_create.call_count == 1

    @pytest.mark.asyncio
    async def test_handles_existing_consumer_group(self, stream_service, mock_redis_client):
        """Test that existing consumer group (BUSYGROUP) is handled gracefully."""
        mock_redis_client._client.xgroup_create = AsyncMock(
            side_effect=Exception("BUSYGROUP Consumer Group name already exists")
        )

        # Should not raise
        await stream_service._ensure_consumer_group()

        assert stream_service._group_created is True

    @pytest.mark.asyncio
    async def test_raises_on_other_errors(self, stream_service, mock_redis_client):
        """Test that other errors are propagated."""
        mock_redis_client._client.xgroup_create = AsyncMock(
            side_effect=Exception("Some other error")
        )

        with pytest.raises(Exception, match="Some other error"):
            await stream_service._ensure_consumer_group()

    @pytest.mark.asyncio
    async def test_raises_when_not_connected(self, mock_redis_client):
        """Test that RuntimeError is raised when client not connected."""
        mock_redis_client._client = None
        service = DetectionStreamService(redis_client=mock_redis_client)

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service._ensure_consumer_group()


class TestDetectionStreamServiceAddDetection:
    """Tests for adding detections to stream."""

    @pytest.mark.asyncio
    async def test_add_detection_basic(self, stream_service, mock_redis_client):
        """Test adding a detection with required fields."""
        mock_redis_client._client.xadd = AsyncMock(return_value="1234567890123-0")

        result = await stream_service.add_detection(
            camera_id="front_door",
            detection_id=42,
            file_path="/export/foscam/front_door/image.jpg",
        )

        assert result == "1234567890123-0"
        mock_redis_client._client.xadd.assert_called_once()

        # Check the call arguments
        call_args = mock_redis_client._client.xadd.call_args
        assert call_args[0][0] == DETECTION_STREAM_KEY
        fields = call_args[0][1]
        assert fields["camera_id"] == "front_door"
        assert fields["detection_id"] == "42"
        assert fields["file_path"] == "/export/foscam/front_door/image.jpg"

    @pytest.mark.asyncio
    async def test_add_detection_with_optional_fields(self, stream_service, mock_redis_client):
        """Test adding a detection with all optional fields."""
        mock_redis_client._client.xadd = AsyncMock(return_value="1234567890123-0")
        timestamp = 1700000000.0

        await stream_service.add_detection(
            camera_id="front_door",
            detection_id=42,
            file_path="/export/foscam/front_door/image.jpg",
            confidence=0.95,
            object_type="person",
            timestamp=timestamp,
            extra_fields={"batch_id": "batch-abc123"},
        )

        call_args = mock_redis_client._client.xadd.call_args
        fields = call_args[0][1]
        assert fields["confidence"] == "0.95"
        assert fields["object_type"] == "person"
        assert fields["timestamp"] == str(timestamp)
        assert fields["batch_id"] == "batch-abc123"

    @pytest.mark.asyncio
    async def test_add_detection_uses_maxlen_trimming(self, stream_service, mock_redis_client):
        """Test that XADD uses MAXLEN for stream trimming."""
        mock_redis_client._client.xadd = AsyncMock(return_value="1234567890123-0")

        await stream_service.add_detection(
            camera_id="front_door",
            detection_id=42,
            file_path="/export/foscam/front_door/image.jpg",
        )

        call_kwargs = mock_redis_client._client.xadd.call_args[1]
        assert call_kwargs["maxlen"] == DEFAULT_STREAM_MAXLEN
        assert call_kwargs["approximate"] is True

    @pytest.mark.asyncio
    async def test_add_detection_validates_required_fields(self, stream_service):
        """Test that missing required fields raise ValueError."""
        with pytest.raises(ValueError, match="camera_id is required"):
            await stream_service.add_detection(
                camera_id="",
                detection_id=42,
                file_path="/path/to/image.jpg",
            )

        with pytest.raises(ValueError, match="detection_id is required"):
            await stream_service.add_detection(
                camera_id="front_door",
                detection_id=0,
                file_path="/path/to/image.jpg",
            )

        with pytest.raises(ValueError, match="file_path is required"):
            await stream_service.add_detection(
                camera_id="front_door",
                detection_id=42,
                file_path="",
            )

    @pytest.mark.asyncio
    async def test_add_detection_raises_when_not_connected(self, mock_redis_client):
        """Test that RuntimeError is raised when client not connected."""
        mock_redis_client._client = None
        service = DetectionStreamService(redis_client=mock_redis_client)

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service.add_detection(
                camera_id="front_door",
                detection_id=42,
                file_path="/path/to/image.jpg",
            )


class TestDetectionStreamServiceConsumeDetections:
    """Tests for consuming detections from stream."""

    @pytest.mark.asyncio
    async def test_consume_detections_returns_messages(self, stream_service, mock_redis_client):
        """Test consuming detections returns parsed messages."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xreadgroup = AsyncMock(
            return_value=[
                (
                    DETECTION_STREAM_KEY,
                    [
                        (
                            "1234567890123-0",
                            {
                                "camera_id": "front_door",
                                "detection_id": "42",
                                "file_path": "/path/to/image.jpg",
                                "timestamp": "1700000000.0",
                            },
                        ),
                    ],
                )
            ]
        )

        messages = await stream_service.consume_detections("worker-1", count=10)

        assert len(messages) == 1
        assert messages[0].id == "1234567890123-0"
        assert messages[0].camera_id == "front_door"
        assert messages[0].detection_id == 42

    @pytest.mark.asyncio
    async def test_consume_detections_empty_result(self, stream_service, mock_redis_client):
        """Test consuming detections when stream is empty."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xreadgroup = AsyncMock(return_value=None)

        messages = await stream_service.consume_detections("worker-1")

        assert messages == []

    @pytest.mark.asyncio
    async def test_consume_detections_uses_blocking(self, stream_service, mock_redis_client):
        """Test that blocking mode uses correct timeout."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xreadgroup = AsyncMock(return_value=None)

        await stream_service.consume_detections("worker-1", block=True)

        call_kwargs = mock_redis_client._client.xreadgroup.call_args[1]
        assert call_kwargs["block"] == DEFAULT_BLOCK_MS

    @pytest.mark.asyncio
    async def test_consume_detections_non_blocking(self, stream_service, mock_redis_client):
        """Test non-blocking mode."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xreadgroup = AsyncMock(return_value=None)

        await stream_service.consume_detections("worker-1", block=False)

        call_kwargs = mock_redis_client._client.xreadgroup.call_args[1]
        assert call_kwargs["block"] is None

    @pytest.mark.asyncio
    async def test_consume_detections_handles_parse_error(self, stream_service, mock_redis_client):
        """Test that parse errors are handled gracefully."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xreadgroup = AsyncMock(
            return_value=[
                (
                    DETECTION_STREAM_KEY,
                    [
                        # Invalid data (missing required fields)
                        ("1234567890123-0", {"camera_id": "front_door"}),
                        # Valid data
                        (
                            "1234567890123-1",
                            {
                                "camera_id": "backyard",
                                "detection_id": "43",
                                "file_path": "/path/to/image.jpg",
                            },
                        ),
                    ],
                )
            ]
        )

        messages = await stream_service.consume_detections("worker-1", count=10)

        # Should return the valid message and skip the invalid one
        assert len(messages) == 2  # Both parsed successfully (detection_id defaults to 0)


class TestDetectionStreamServiceAcknowledge:
    """Tests for acknowledging messages."""

    @pytest.mark.asyncio
    async def test_acknowledge_success(self, stream_service, mock_redis_client):
        """Test acknowledging a message returns True on success."""
        mock_redis_client._client.xack = AsyncMock(return_value=1)

        result = await stream_service.acknowledge("1234567890123-0")

        assert result is True
        mock_redis_client._client.xack.assert_called_once_with(
            DETECTION_STREAM_KEY,
            DETECTION_CONSUMER_GROUP,
            "1234567890123-0",
        )

    @pytest.mark.asyncio
    async def test_acknowledge_not_found(self, stream_service, mock_redis_client):
        """Test acknowledging a non-existent message returns False."""
        mock_redis_client._client.xack = AsyncMock(return_value=0)

        result = await stream_service.acknowledge("nonexistent-0")

        assert result is False


class TestDetectionStreamServiceClaimStaleMessages:
    """Tests for claiming stale messages."""

    @pytest.mark.asyncio
    async def test_claim_stale_messages_returns_claimed(self, stream_service, mock_redis_client):
        """Test claiming stale messages returns parsed messages."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xautoclaim = AsyncMock(
            return_value=(
                "0-0",  # next_id
                [
                    (
                        "1234567890123-0",
                        {
                            "camera_id": "front_door",
                            "detection_id": "42",
                            "file_path": "/path/to/image.jpg",
                        },
                    ),
                ],
                [],  # deleted_ids
            )
        )
        mock_redis_client._client.xpending_range = AsyncMock(
            return_value=[
                # message_id, consumer, idle_time, delivery_count
                ("1234567890123-0", "worker-1", 120000, 3),
            ]
        )

        messages = await stream_service.claim_stale_messages("worker-2", count=5)

        assert len(messages) == 1
        assert messages[0].id == "1234567890123-0"
        assert messages[0].delivery_count == 3

    @pytest.mark.asyncio
    async def test_claim_stale_messages_empty(self, stream_service, mock_redis_client):
        """Test claiming when no stale messages exist."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xautoclaim = AsyncMock(return_value=("0-0", [], []))

        messages = await stream_service.claim_stale_messages("worker-2")

        assert messages == []


class TestDetectionStreamServiceMoveToDlq:
    """Tests for moving messages to DLQ."""

    @pytest.mark.asyncio
    async def test_move_to_dlq_success(self, stream_service, mock_redis_client):
        """Test moving a message to DLQ."""
        mock_redis_client._client.xadd = AsyncMock(return_value="dlq-123-0")
        mock_redis_client._client.xack = AsyncMock(return_value=1)

        message = DetectionStreamMessage(
            id="1234567890123-0",
            camera_id="front_door",
            detection_id=42,
            file_path="/path/to/image.jpg",
            delivery_count=3,
            raw_data={
                "camera_id": "front_door",
                "detection_id": "42",
                "file_path": "/path/to/image.jpg",
            },
        )

        dlq_id = await stream_service.move_to_dlq(message, reason="processing_failed")

        assert dlq_id == "dlq-123-0"

        # Verify DLQ message includes metadata
        call_args = mock_redis_client._client.xadd.call_args
        assert call_args[0][0] == f"{DETECTION_STREAM_KEY}:dlq"
        fields = call_args[0][1]
        assert fields["original_message_id"] == "1234567890123-0"
        assert fields["dlq_reason"] == "processing_failed"
        assert fields["delivery_count"] == "3"

        # Verify original message was acknowledged
        mock_redis_client._client.xack.assert_called_once()


class TestDetectionStreamServiceShouldMoveToDlq:
    """Tests for DLQ threshold checking."""

    @pytest.mark.asyncio
    async def test_should_move_below_threshold(self, stream_service):
        """Test that messages below threshold should not be moved."""
        message = DetectionStreamMessage(
            id="123-0",
            camera_id="cam",
            detection_id=1,
            file_path="/path",
            delivery_count=1,
        )

        assert await stream_service.should_move_to_dlq(message) is False

    @pytest.mark.asyncio
    async def test_should_move_at_threshold(self, stream_service):
        """Test that messages at threshold should be moved."""
        message = DetectionStreamMessage(
            id="123-0",
            camera_id="cam",
            detection_id=1,
            file_path="/path",
            delivery_count=DEFAULT_MAX_DELIVERY_COUNT,
        )

        assert await stream_service.should_move_to_dlq(message) is True

    @pytest.mark.asyncio
    async def test_should_move_above_threshold(self, stream_service):
        """Test that messages above threshold should be moved."""
        message = DetectionStreamMessage(
            id="123-0",
            camera_id="cam",
            detection_id=1,
            file_path="/path",
            delivery_count=DEFAULT_MAX_DELIVERY_COUNT + 5,
        )

        assert await stream_service.should_move_to_dlq(message) is True


class TestDetectionStreamServiceGetStreamInfo:
    """Tests for getting stream information."""

    @pytest.mark.asyncio
    async def test_get_stream_info_returns_stats(self, stream_service, mock_redis_client):
        """Test getting stream information."""
        mock_redis_client._client.xinfo_stream = AsyncMock(
            return_value={
                "length": 1000,
                "radix-tree-keys": 100,
                "radix-tree-nodes": 200,
                "groups": 1,
                "last-generated-id": "1234567890123-99",
                "first-entry": ("1234567890000-0", {"data": "value"}),
            }
        )

        info = await stream_service.get_stream_info()

        assert info["length"] == 1000
        assert info["groups"] == 1
        assert info["last_entry_id"] == "1234567890123-99"

    @pytest.mark.asyncio
    async def test_get_stream_info_empty_stream(self, stream_service, mock_redis_client):
        """Test getting info for non-existent stream."""
        mock_redis_client._client.xinfo_stream = AsyncMock(side_effect=Exception("no such key"))

        info = await stream_service.get_stream_info()

        assert info["length"] == 0
        assert info["groups"] == 0


class TestDetectionStreamServiceTrimStream:
    """Tests for trimming stream."""

    @pytest.mark.asyncio
    async def test_trim_stream_removes_entries(self, stream_service, mock_redis_client):
        """Test trimming stream removes old entries."""
        mock_redis_client._client.xinfo_stream = AsyncMock(
            side_effect=[
                {"length": 15000},  # Before trim
                {"length": 10000},  # After trim
            ]
        )
        mock_redis_client._client.xtrim = AsyncMock()

        removed = await stream_service.trim_stream(maxlen=10000)

        assert removed == 5000
        mock_redis_client._client.xtrim.assert_called_once()


# ===========================================================================
# Test: get_detection_stream_service factory
# ===========================================================================


class TestGetDetectionStreamService:
    """Tests for the service factory function."""

    @pytest.mark.asyncio
    async def test_creates_singleton(self, mock_redis_client):
        """Test that factory returns the same instance."""
        # Reset global state
        import backend.services.redis_streams as module

        module._detection_stream_service = None

        with patch("backend.services.redis_streams.get_settings") as mock_settings:
            mock_settings.return_value.queue_max_size = 10000

            service1 = await get_detection_stream_service(mock_redis_client)
            service2 = await get_detection_stream_service(mock_redis_client)

            assert service1 is service2

        # Clean up
        module._detection_stream_service = None


# ===========================================================================
# Test: Additional Coverage - Error Handling and Edge Cases
# ===========================================================================


class TestDetectionStreamServiceErrorHandling:
    """Additional tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_consume_detections_raises_when_not_connected(self, mock_redis_client):
        """Test consume_detections raises when Redis not connected."""
        mock_redis_client._client = None
        service = DetectionStreamService(redis_client=mock_redis_client)

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service.consume_detections("worker-1")

    @pytest.mark.asyncio
    async def test_acknowledge_raises_when_not_connected(self, mock_redis_client):
        """Test acknowledge raises when Redis not connected."""
        mock_redis_client._client = None
        service = DetectionStreamService(redis_client=mock_redis_client)

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service.acknowledge("123-0")

    @pytest.mark.asyncio
    async def test_claim_stale_messages_raises_when_not_connected(self, mock_redis_client):
        """Test claim_stale_messages raises when Redis not connected."""
        mock_redis_client._client = None
        service = DetectionStreamService(redis_client=mock_redis_client)

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service.claim_stale_messages("worker-1")

    @pytest.mark.asyncio
    async def test_move_to_dlq_raises_when_not_connected(self, mock_redis_client):
        """Test move_to_dlq raises when Redis not connected."""
        mock_redis_client._client = None
        service = DetectionStreamService(redis_client=mock_redis_client)

        message = DetectionStreamMessage(
            id="123-0",
            camera_id="cam1",
            detection_id=1,
            file_path="/path",
        )

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service.move_to_dlq(message)

    @pytest.mark.asyncio
    async def test_get_stream_info_raises_when_not_connected(self, mock_redis_client):
        """Test get_stream_info raises when Redis not connected."""
        mock_redis_client._client = None
        service = DetectionStreamService(redis_client=mock_redis_client)

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service.get_stream_info()

    @pytest.mark.asyncio
    async def test_get_consumer_group_info_raises_when_not_connected(self, mock_redis_client):
        """Test get_consumer_group_info raises when Redis not connected."""
        mock_redis_client._client = None
        service = DetectionStreamService(redis_client=mock_redis_client)

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service.get_consumer_group_info()

    @pytest.mark.asyncio
    async def test_get_pending_count_raises_when_not_connected(self, mock_redis_client):
        """Test get_pending_count raises when Redis not connected."""
        mock_redis_client._client = None
        service = DetectionStreamService(redis_client=mock_redis_client)

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service.get_pending_count()

    @pytest.mark.asyncio
    async def test_trim_stream_raises_when_not_connected(self, mock_redis_client):
        """Test trim_stream raises when Redis not connected."""
        mock_redis_client._client = None
        service = DetectionStreamService(redis_client=mock_redis_client)

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service.trim_stream()

    @pytest.mark.asyncio
    async def test_consume_detections_raises_on_error(self, stream_service, mock_redis_client):
        """Test consume_detections raises exception on error."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xreadgroup = AsyncMock(side_effect=Exception("Stream read error"))

        with pytest.raises(Exception, match="Stream read error"):
            await stream_service.consume_detections("worker-1")

    @pytest.mark.asyncio
    async def test_claim_stale_messages_raises_on_error(self, stream_service, mock_redis_client):
        """Test claim_stale_messages raises exception on error."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xautoclaim = AsyncMock(side_effect=Exception("Claim failed"))

        with pytest.raises(Exception, match="Claim failed"):
            await stream_service.claim_stale_messages("worker-1")

    @pytest.mark.asyncio
    async def test_claim_stale_messages_handles_deleted_messages(
        self, stream_service, mock_redis_client
    ):
        """Test claim_stale_messages skips deleted messages (data=None)."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xautoclaim = AsyncMock(
            return_value=(
                "0-0",  # next_id
                [
                    ("1234567890123-0", None),  # Deleted message
                    (
                        "1234567890123-1",
                        {
                            "camera_id": "front_door",
                            "detection_id": "42",
                            "file_path": "/path/to/image.jpg",
                        },
                    ),
                ],
                [],  # deleted_ids
            )
        )
        mock_redis_client._client.xpending_range = AsyncMock(
            return_value=[
                ("1234567890123-1", "worker-1", 120000, 2),
            ]
        )

        messages = await stream_service.claim_stale_messages("worker-2")

        # Should only return the non-deleted message
        assert len(messages) == 1
        assert messages[0].id == "1234567890123-1"

    @pytest.mark.asyncio
    async def test_claim_stale_messages_handles_parse_error(
        self, stream_service, mock_redis_client
    ):
        """Test claim_stale_messages raises exception when xpending_range fails."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xautoclaim = AsyncMock(
            return_value=(
                "0-0",
                [
                    ("1234567890123-0", {"camera_id": "front_door"}),  # Missing required fields
                ],
                [],
            )
        )
        # xpending_range fails - this should propagate as an exception
        mock_redis_client._client.xpending_range = AsyncMock(
            side_effect=Exception("Pending info error")
        )

        # Should raise the exception
        with pytest.raises(Exception, match="Pending info error"):
            await stream_service.claim_stale_messages("worker-2")

    @pytest.mark.asyncio
    async def test_claim_stale_messages_handles_empty_pending_info(
        self, stream_service, mock_redis_client
    ):
        """Test claim_stale_messages handles empty pending info."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xautoclaim = AsyncMock(
            return_value=(
                "0-0",
                [
                    (
                        "1234567890123-0",
                        {
                            "camera_id": "front_door",
                            "detection_id": "42",
                            "file_path": "/path/to/image.jpg",
                        },
                    ),
                ],
                [],
            )
        )
        mock_redis_client._client.xpending_range = AsyncMock(return_value=[])  # Empty list

        messages = await stream_service.claim_stale_messages("worker-2")

        # Should default to delivery_count=1
        assert len(messages) == 1
        assert messages[0].delivery_count == 1

    @pytest.mark.asyncio
    async def test_get_consumer_group_info_stream_not_found(
        self, stream_service, mock_redis_client
    ):
        """Test get_consumer_group_info when stream doesn't exist."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xinfo_groups = AsyncMock(side_effect=Exception("no such key"))

        info = await stream_service.get_consumer_group_info()

        assert info["name"] == DETECTION_CONSUMER_GROUP
        assert info["consumers"] == 0
        assert info["pending"] == 0

    @pytest.mark.asyncio
    async def test_get_consumer_group_info_group_not_found(self, stream_service, mock_redis_client):
        """Test get_consumer_group_info when group doesn't exist in list."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xinfo_groups = AsyncMock(
            return_value=[
                {
                    "name": "other-group",
                    "consumers": 2,
                    "pending": 5,
                    "last-delivered-id": "123-0",
                }
            ]
        )

        info = await stream_service.get_consumer_group_info()

        # Should return default values for our group
        assert info["name"] == DETECTION_CONSUMER_GROUP
        assert info["consumers"] == 0
        assert info["pending"] == 0

    @pytest.mark.asyncio
    async def test_get_consumer_group_info_raises_on_other_error(
        self, stream_service, mock_redis_client
    ):
        """Test get_consumer_group_info raises on non-key-not-found error."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xinfo_groups = AsyncMock(side_effect=Exception("Other error"))

        with pytest.raises(Exception, match="Other error"):
            await stream_service.get_consumer_group_info()

    @pytest.mark.asyncio
    async def test_get_pending_count_stream_not_found(self, stream_service, mock_redis_client):
        """Test get_pending_count when stream doesn't exist."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xpending = AsyncMock(side_effect=Exception("no such key"))

        count = await stream_service.get_pending_count()

        assert count == 0

    @pytest.mark.asyncio
    async def test_get_pending_count_empty_pending(self, stream_service, mock_redis_client):
        """Test get_pending_count when pending is None or empty."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xpending = AsyncMock(return_value=None)

        count = await stream_service.get_pending_count()

        assert count == 0

    @pytest.mark.asyncio
    async def test_get_pending_count_for_specific_consumer(self, stream_service, mock_redis_client):
        """Test get_pending_count for a specific consumer."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xpending = AsyncMock(
            return_value={
                "pending": 10,
                "consumers": [
                    {"name": "worker-1", "pending": 3},
                    {"name": "worker-2", "pending": 7},
                ],
            }
        )

        count = await stream_service.get_pending_count("worker-2")

        assert count == 7

    @pytest.mark.asyncio
    async def test_get_pending_count_consumer_not_found(self, stream_service, mock_redis_client):
        """Test get_pending_count when consumer doesn't exist."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xpending = AsyncMock(
            return_value={
                "pending": 10,
                "consumers": [
                    {"name": "worker-1", "pending": 10},
                ],
            }
        )

        count = await stream_service.get_pending_count("nonexistent-worker")

        assert count == 0

    @pytest.mark.asyncio
    async def test_get_pending_count_raises_on_other_error(self, stream_service, mock_redis_client):
        """Test get_pending_count raises on non-key-not-found error."""
        mock_redis_client._client.xgroup_create = AsyncMock()
        mock_redis_client._client.xpending = AsyncMock(side_effect=Exception("Other error"))

        with pytest.raises(Exception, match="Other error"):
            await stream_service.get_pending_count()

    @pytest.mark.asyncio
    async def test_trim_stream_handles_xinfo_error(self, stream_service, mock_redis_client):
        """Test trim_stream handles xinfo_stream error gracefully."""
        # xinfo_stream fails both times (before and after trim)
        mock_redis_client._client.xinfo_stream = AsyncMock(side_effect=Exception("Info error"))
        mock_redis_client._client.xtrim = AsyncMock()

        removed = await stream_service.trim_stream()

        # Should return 0 when can't get length info
        assert removed == 0

    @pytest.mark.asyncio
    async def test_trim_stream_handles_xinfo_error_after_trim(
        self, stream_service, mock_redis_client
    ):
        """Test trim_stream handles xinfo_stream error after trim."""
        mock_redis_client._client.xinfo_stream = AsyncMock(
            side_effect=[
                {"length": 15000},  # Before trim succeeds
                Exception("Info error"),  # After trim fails
            ]
        )
        mock_redis_client._client.xtrim = AsyncMock()

        removed = await stream_service.trim_stream()

        # Should return 0 when can't get new length
        assert removed == 0

    @pytest.mark.asyncio
    async def test_trim_stream_uses_custom_maxlen(self, stream_service, mock_redis_client):
        """Test trim_stream uses custom maxlen parameter."""
        mock_redis_client._client.xinfo_stream = AsyncMock(
            side_effect=[
                {"length": 7000},  # Before trim
                {"length": 5000},  # After trim
            ]
        )
        mock_redis_client._client.xtrim = AsyncMock()

        removed = await stream_service.trim_stream(maxlen=5000)

        assert removed == 2000
        # Verify xtrim was called with custom maxlen
        mock_redis_client._client.xtrim.assert_called_once()
        call_kwargs = mock_redis_client._client.xtrim.call_args[1]
        assert call_kwargs["maxlen"] == 5000

    @pytest.mark.asyncio
    async def test_get_stream_info_raises_on_other_error(self, stream_service, mock_redis_client):
        """Test get_stream_info raises on non-key-not-found error."""
        mock_redis_client._client.xinfo_stream = AsyncMock(side_effect=Exception("Other error"))

        with pytest.raises(Exception, match="Other error"):
            await stream_service.get_stream_info()

    @pytest.mark.asyncio
    async def test_get_stream_info_handles_missing_first_entry(
        self, stream_service, mock_redis_client
    ):
        """Test get_stream_info when first-entry is None."""
        mock_redis_client._client.xinfo_stream = AsyncMock(
            return_value={
                "length": 0,
                "radix-tree-keys": 0,
                "radix-tree-nodes": 0,
                "groups": 0,
                "last-generated-id": "",
                "first-entry": None,  # No first entry
            }
        )

        info = await stream_service.get_stream_info()

        assert info["first_entry_id"] == ""
