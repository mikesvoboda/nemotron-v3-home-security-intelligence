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
