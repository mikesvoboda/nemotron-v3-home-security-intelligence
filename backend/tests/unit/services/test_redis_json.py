"""Unit tests for Redis JSON service.

NEM-3366: Tests for Redis JSON-based batch metadata storage.
"""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis import RedisClient
from backend.services.redis_json import (
    BATCH_META_PREFIX,
    DEFAULT_BATCH_META_TTL,
    BatchMetadata,
    BatchMetadataService,
    get_batch_metadata_service,
)

# ===========================================================================
# Test: BatchMetadata dataclass
# ===========================================================================


class TestBatchMetadata:
    """Tests for the BatchMetadata dataclass."""

    def test_create_with_required_fields(self):
        """Test creating BatchMetadata with only required fields."""
        metadata = BatchMetadata(
            batch_id="batch-abc12345",
            camera_id="front_door",
        )

        assert metadata.batch_id == "batch-abc12345"
        assert metadata.camera_id == "front_door"
        assert metadata.status == "open"
        assert metadata.detection_ids == []
        assert metadata.detection_count == 0
        assert metadata.closed_at is None

    def test_create_with_all_fields(self):
        """Test creating BatchMetadata with all fields."""
        timestamp = time.time()
        metadata = BatchMetadata(
            batch_id="batch-abc12345",
            camera_id="front_door",
            status="closed",
            detection_ids=[1, 2, 3, 4, 5],
            detection_count=5,
            started_at=timestamp,
            last_activity=timestamp + 30,
            closed_at=timestamp + 60,
            pipeline_start_time="2024-01-15T10:00:00Z",
            close_reason="timeout",
            processing_metadata={"analyzed": True},
        )

        assert metadata.status == "closed"
        assert metadata.detection_ids == [1, 2, 3, 4, 5]
        assert metadata.detection_count == 5
        assert metadata.closed_at == timestamp + 60
        assert metadata.close_reason == "timeout"

    def test_to_dict(self):
        """Test converting BatchMetadata to dictionary."""
        metadata = BatchMetadata(
            batch_id="batch-abc12345",
            camera_id="front_door",
            detection_ids=[1, 2],
            detection_count=2,
        )

        data = metadata.to_dict()

        assert data["batch_id"] == "batch-abc12345"
        assert data["camera_id"] == "front_door"
        assert data["detection_ids"] == [1, 2]
        assert data["detection_count"] == 2
        assert data["status"] == "open"

    def test_from_dict(self):
        """Test creating BatchMetadata from dictionary."""
        data = {
            "batch_id": "batch-xyz789",
            "camera_id": "backyard",
            "status": "closing",
            "detection_ids": [10, 20, 30],
            "detection_count": 3,
            "started_at": 1700000000.0,
            "last_activity": 1700000030.0,
            "closed_at": None,
            "pipeline_start_time": None,
            "close_reason": None,
            "processing_metadata": {"key": "value"},
        }

        metadata = BatchMetadata.from_dict(data)

        assert metadata.batch_id == "batch-xyz789"
        assert metadata.camera_id == "backyard"
        assert metadata.status == "closing"
        assert metadata.detection_ids == [10, 20, 30]
        assert metadata.detection_count == 3
        assert metadata.processing_metadata == {"key": "value"}

    def test_from_dict_with_missing_optional_fields(self):
        """Test creating BatchMetadata from dict with missing optional fields."""
        data = {
            "batch_id": "batch-minimal",
            "camera_id": "cam1",
        }

        metadata = BatchMetadata.from_dict(data)

        assert metadata.batch_id == "batch-minimal"
        assert metadata.camera_id == "cam1"
        assert metadata.status == "open"
        assert metadata.detection_ids == []
        assert metadata.detection_count == 0

    def test_roundtrip_to_dict_from_dict(self):
        """Test that to_dict/from_dict roundtrip preserves data."""
        original = BatchMetadata(
            batch_id="batch-roundtrip",
            camera_id="test_cam",
            status="open",
            detection_ids=[1, 2, 3],
            detection_count=3,
            started_at=1700000000.0,
            last_activity=1700000010.0,
            processing_metadata={"nested": {"data": True}},
        )

        data = original.to_dict()
        restored = BatchMetadata.from_dict(data)

        assert restored.batch_id == original.batch_id
        assert restored.camera_id == original.camera_id
        assert restored.status == original.status
        assert restored.detection_ids == original.detection_ids
        assert restored.detection_count == original.detection_count
        assert restored.processing_metadata == original.processing_metadata


# ===========================================================================
# Test: BatchMetadataService
# ===========================================================================


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client for testing."""
    mock = MagicMock(spec=RedisClient)
    mock._client = AsyncMock()
    return mock


@pytest.fixture
def metadata_service(mock_redis_client):
    """Create a BatchMetadataService with mocked Redis."""
    return BatchMetadataService(
        redis_client=mock_redis_client,
        key_prefix=BATCH_META_PREFIX,
        default_ttl=DEFAULT_BATCH_META_TTL,
    )


class TestBatchMetadataServiceInit:
    """Tests for BatchMetadataService initialization."""

    def test_default_configuration(self, mock_redis_client):
        """Test service initializes with correct defaults."""
        service = BatchMetadataService(redis_client=mock_redis_client)

        assert service._key_prefix == BATCH_META_PREFIX
        assert service._default_ttl == DEFAULT_BATCH_META_TTL
        assert service._json_available is None

    def test_custom_configuration(self, mock_redis_client):
        """Test service accepts custom configuration."""
        service = BatchMetadataService(
            redis_client=mock_redis_client,
            key_prefix="custom:prefix:",
            default_ttl=7200,
        )

        assert service._key_prefix == "custom:prefix:"
        assert service._default_ttl == 7200


class TestBatchMetadataServiceGetKey:
    """Tests for key generation."""

    def test_get_key_generates_correct_key(self, metadata_service):
        """Test that _get_key generates the correct key."""
        key = metadata_service._get_key("batch-abc12345")

        assert key == f"{BATCH_META_PREFIX}batch-abc12345"

    def test_get_key_with_custom_prefix(self, mock_redis_client):
        """Test key generation with custom prefix."""
        service = BatchMetadataService(
            redis_client=mock_redis_client,
            key_prefix="my:batches:",
        )

        key = service._get_key("batch-xyz")

        assert key == "my:batches:batch-xyz"


class TestBatchMetadataServiceCheckJsonAvailable:
    """Tests for RedisJSON availability checking."""

    @pytest.mark.asyncio
    async def test_json_available_when_module_exists(self, metadata_service, mock_redis_client):
        """Test detection when RedisJSON module is available."""
        mock_redis_client._client.execute_command = AsyncMock(return_value="OK")
        mock_redis_client._client.delete = AsyncMock()

        result = await metadata_service._check_json_available()

        assert result is True
        assert metadata_service._json_available is True

    @pytest.mark.asyncio
    async def test_json_not_available_when_module_missing(
        self, metadata_service, mock_redis_client
    ):
        """Test detection when RedisJSON module is not available."""
        mock_redis_client._client.execute_command = AsyncMock(
            side_effect=Exception("ERR unknown command `JSON.SET`")
        )

        result = await metadata_service._check_json_available()

        assert result is False
        assert metadata_service._json_available is False

    @pytest.mark.asyncio
    async def test_caches_json_availability(self, metadata_service, mock_redis_client):
        """Test that JSON availability is cached."""
        mock_redis_client._client.execute_command = AsyncMock(return_value="OK")
        mock_redis_client._client.delete = AsyncMock()

        await metadata_service._check_json_available()
        await metadata_service._check_json_available()
        await metadata_service._check_json_available()

        # Should only be called once for the test
        assert mock_redis_client._client.execute_command.call_count == 1


class TestBatchMetadataServiceSetBatchMetadata:
    """Tests for storing batch metadata."""

    @pytest.mark.asyncio
    async def test_set_batch_metadata_with_json(self, metadata_service, mock_redis_client):
        """Test storing metadata with RedisJSON."""
        metadata_service._json_available = True
        mock_redis_client._client.execute_command = AsyncMock()
        mock_redis_client._client.expire = AsyncMock()

        metadata = BatchMetadata(
            batch_id="batch-abc12345",
            camera_id="front_door",
            detection_ids=[1, 2],
        )

        result = await metadata_service.set_batch_metadata("batch-abc12345", metadata)

        assert result is True
        mock_redis_client._client.execute_command.assert_called_once()

        # Verify JSON.SET was called with correct arguments
        call_args = mock_redis_client._client.execute_command.call_args
        assert call_args[0][0] == "JSON.SET"
        assert call_args[0][1] == f"{BATCH_META_PREFIX}batch-abc12345"
        assert call_args[0][2] == "$"

    @pytest.mark.asyncio
    async def test_set_batch_metadata_fallback_to_string(self, metadata_service, mock_redis_client):
        """Test storing metadata falls back to string when JSON unavailable."""
        metadata_service._json_available = False
        mock_redis_client._client.setex = AsyncMock()

        metadata = BatchMetadata(
            batch_id="batch-abc12345",
            camera_id="front_door",
        )

        result = await metadata_service.set_batch_metadata("batch-abc12345", metadata)

        assert result is True
        mock_redis_client._client.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_batch_metadata_with_dict(self, metadata_service, mock_redis_client):
        """Test storing metadata from dictionary."""
        metadata_service._json_available = False
        mock_redis_client._client.setex = AsyncMock()

        data = {
            "batch_id": "batch-dict",
            "camera_id": "backyard",
            "detection_ids": [10, 20],
        }

        result = await metadata_service.set_batch_metadata("batch-dict", data)

        assert result is True

    @pytest.mark.asyncio
    async def test_set_batch_metadata_custom_ttl(self, metadata_service, mock_redis_client):
        """Test storing metadata with custom TTL."""
        metadata_service._json_available = False
        mock_redis_client._client.setex = AsyncMock()

        metadata = BatchMetadata(batch_id="batch-ttl", camera_id="cam1")

        await metadata_service.set_batch_metadata("batch-ttl", metadata, ttl=7200)

        # Verify custom TTL was used
        call_args = mock_redis_client._client.setex.call_args
        assert call_args[0][1] == 7200  # TTL is second argument

    @pytest.mark.asyncio
    async def test_set_batch_metadata_raises_when_not_connected(self, mock_redis_client):
        """Test that RuntimeError is raised when client not connected."""
        mock_redis_client._client = None
        service = BatchMetadataService(redis_client=mock_redis_client)

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service.set_batch_metadata(
                "batch-error",
                BatchMetadata(batch_id="batch-error", camera_id="cam1"),
            )


class TestBatchMetadataServiceGetBatchMetadata:
    """Tests for retrieving batch metadata."""

    @pytest.mark.asyncio
    async def test_get_batch_metadata_with_json(self, metadata_service, mock_redis_client):
        """Test retrieving metadata with RedisJSON."""
        metadata_service._json_available = True
        data = {
            "batch_id": "batch-get",
            "camera_id": "front_door",
            "status": "open",
            "detection_ids": [1, 2, 3],
            "detection_count": 3,
            "started_at": 1700000000.0,
            "last_activity": 1700000000.0,
            "closed_at": None,
            "pipeline_start_time": None,
            "close_reason": None,
            "processing_metadata": {},
        }
        mock_redis_client._client.execute_command = AsyncMock(return_value=json.dumps(data))

        result = await metadata_service.get_batch_metadata("batch-get")

        assert result is not None
        assert result.batch_id == "batch-get"
        assert result.camera_id == "front_door"
        assert result.detection_ids == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_get_batch_metadata_fallback_to_string(self, metadata_service, mock_redis_client):
        """Test retrieving metadata falls back to string when JSON unavailable."""
        metadata_service._json_available = False
        data = {
            "batch_id": "batch-fallback",
            "camera_id": "backyard",
            "status": "closed",
            "detection_ids": [],
            "detection_count": 0,
            "started_at": 1700000000.0,
            "last_activity": 1700000000.0,
            "closed_at": 1700000060.0,
            "pipeline_start_time": None,
            "close_reason": "timeout",
            "processing_metadata": {},
        }
        mock_redis_client._client.get = AsyncMock(return_value=json.dumps(data))

        result = await metadata_service.get_batch_metadata("batch-fallback")

        assert result is not None
        assert result.batch_id == "batch-fallback"
        assert result.status == "closed"
        assert result.close_reason == "timeout"

    @pytest.mark.asyncio
    async def test_get_batch_metadata_not_found(self, metadata_service, mock_redis_client):
        """Test retrieving non-existent metadata returns None."""
        metadata_service._json_available = False
        mock_redis_client._client.get = AsyncMock(return_value=None)

        result = await metadata_service.get_batch_metadata("batch-nonexistent")

        assert result is None


class TestBatchMetadataServiceGetBatchField:
    """Tests for getting specific fields."""

    @pytest.mark.asyncio
    async def test_get_batch_field_with_json(self, metadata_service, mock_redis_client):
        """Test getting a field with RedisJSON."""
        metadata_service._json_available = True
        mock_redis_client._client.execute_command = AsyncMock(return_value='["closed"]')

        result = await metadata_service.get_batch_field("batch-field", "$.status")

        assert result == "closed"

    @pytest.mark.asyncio
    async def test_get_batch_field_nested_path(self, metadata_service, mock_redis_client):
        """Test getting a nested field."""
        metadata_service._json_available = True
        mock_redis_client._client.execute_command = AsyncMock(return_value="[5]")

        result = await metadata_service.get_batch_field("batch-field", "$.detection_count")

        assert result == 5

    @pytest.mark.asyncio
    async def test_get_batch_field_fallback(self, metadata_service, mock_redis_client):
        """Test getting a field with fallback."""
        metadata_service._json_available = False
        data = {
            "batch_id": "batch-fallback-field",
            "camera_id": "cam1",
            "status": "open",
            "detection_ids": [1, 2, 3],
            "detection_count": 3,
            "started_at": 1700000000.0,
            "last_activity": 1700000000.0,
            "closed_at": None,
            "pipeline_start_time": None,
            "close_reason": None,
            "processing_metadata": {},
        }
        mock_redis_client._client.get = AsyncMock(return_value=json.dumps(data))

        result = await metadata_service.get_batch_field("batch-fallback-field", "$.status")

        assert result == "open"

    @pytest.mark.asyncio
    async def test_get_batch_field_not_found(self, metadata_service, mock_redis_client):
        """Test getting field from non-existent batch."""
        metadata_service._json_available = False
        mock_redis_client._client.get = AsyncMock(return_value=None)

        result = await metadata_service.get_batch_field("batch-nonexistent", "$.status")

        assert result is None


class TestBatchMetadataServiceUpdateBatchField:
    """Tests for updating specific fields."""

    @pytest.mark.asyncio
    async def test_update_batch_field_with_json(self, metadata_service, mock_redis_client):
        """Test updating a field with RedisJSON."""
        metadata_service._json_available = True
        mock_redis_client._client.execute_command = AsyncMock()
        mock_redis_client._client.expire = AsyncMock()

        result = await metadata_service.update_batch_field("batch-update", "$.status", "closing")

        assert result is True

        # Verify JSON.SET was called with path
        call_args = mock_redis_client._client.execute_command.call_args
        assert call_args[0][0] == "JSON.SET"
        assert call_args[0][2] == "$.status"
        assert call_args[0][3] == '"closing"'

    @pytest.mark.asyncio
    async def test_update_batch_field_numeric(self, metadata_service, mock_redis_client):
        """Test updating a numeric field."""
        metadata_service._json_available = True
        mock_redis_client._client.execute_command = AsyncMock()
        mock_redis_client._client.expire = AsyncMock()

        result = await metadata_service.update_batch_field("batch-update", "$.detection_count", 42)

        assert result is True

    @pytest.mark.asyncio
    async def test_update_batch_field_refresh_ttl(self, metadata_service, mock_redis_client):
        """Test updating field refreshes TTL."""
        metadata_service._json_available = True
        mock_redis_client._client.execute_command = AsyncMock()
        mock_redis_client._client.expire = AsyncMock()

        await metadata_service.update_batch_field(
            "batch-update", "$.status", "closing", refresh_ttl=True
        )

        mock_redis_client._client.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_batch_field_no_refresh_ttl(self, metadata_service, mock_redis_client):
        """Test updating field without TTL refresh."""
        metadata_service._json_available = True
        mock_redis_client._client.execute_command = AsyncMock()

        await metadata_service.update_batch_field(
            "batch-update", "$.status", "closing", refresh_ttl=False
        )

        mock_redis_client._client.expire.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_batch_field_not_found(self, metadata_service, mock_redis_client):
        """Test updating field of non-existent batch."""
        metadata_service._json_available = True
        mock_redis_client._client.execute_command = AsyncMock(side_effect=Exception("no such key"))

        result = await metadata_service.update_batch_field(
            "batch-nonexistent", "$.status", "closed"
        )

        assert result is False


class TestBatchMetadataServiceAppendDetectionId:
    """Tests for appending detection IDs."""

    @pytest.mark.asyncio
    async def test_append_detection_id_with_json(self, metadata_service, mock_redis_client):
        """Test appending detection ID with RedisJSON."""
        metadata_service._json_available = True
        mock_redis_client._client.execute_command = AsyncMock(
            side_effect=[
                None,  # JSON.ARRAPPEND
                None,  # JSON.NUMINCRBY
                None,  # JSON.SET last_activity
                "[5]",  # JSON.GET detection_count
            ]
        )
        mock_redis_client._client.expire = AsyncMock()

        result = await metadata_service.append_detection_id("batch-append", 42)

        assert result == 5

    @pytest.mark.asyncio
    async def test_append_detection_id_fallback(self, metadata_service, mock_redis_client):
        """Test appending detection ID with fallback."""
        metadata_service._json_available = False
        data = {
            "batch_id": "batch-append-fallback",
            "camera_id": "cam1",
            "status": "open",
            "detection_ids": [1, 2],
            "detection_count": 2,
            "started_at": 1700000000.0,
            "last_activity": 1700000000.0,
            "closed_at": None,
            "pipeline_start_time": None,
            "close_reason": None,
            "processing_metadata": {},
        }
        mock_redis_client._client.get = AsyncMock(return_value=json.dumps(data))
        mock_redis_client._client.setex = AsyncMock()

        result = await metadata_service.append_detection_id("batch-append-fallback", 3)

        assert result == 3  # New count after appending

    @pytest.mark.asyncio
    async def test_append_detection_id_not_found(self, metadata_service, mock_redis_client):
        """Test appending to non-existent batch."""
        metadata_service._json_available = True
        mock_redis_client._client.execute_command = AsyncMock(side_effect=Exception("no such key"))

        result = await metadata_service.append_detection_id("batch-nonexistent", 42)

        assert result == -1


class TestBatchMetadataServiceCloseBatch:
    """Tests for closing batches."""

    @pytest.mark.asyncio
    async def test_close_batch_with_json(self, metadata_service, mock_redis_client):
        """Test closing batch with RedisJSON."""
        metadata_service._json_available = True
        mock_redis_client._client.exists = AsyncMock(return_value=1)

        # Mock pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.execute_command = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock()
        mock_redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        result = await metadata_service.close_batch("batch-close", reason="timeout")

        assert result is True

    @pytest.mark.asyncio
    async def test_close_batch_fallback(self, metadata_service, mock_redis_client):
        """Test closing batch with fallback."""
        metadata_service._json_available = False
        data = {
            "batch_id": "batch-close-fallback",
            "camera_id": "cam1",
            "status": "open",
            "detection_ids": [1, 2, 3],
            "detection_count": 3,
            "started_at": 1700000000.0,
            "last_activity": 1700000000.0,
            "closed_at": None,
            "pipeline_start_time": None,
            "close_reason": None,
            "processing_metadata": {},
        }
        mock_redis_client._client.get = AsyncMock(return_value=json.dumps(data))
        mock_redis_client._client.setex = AsyncMock()

        result = await metadata_service.close_batch("batch-close-fallback", reason="max_size")

        assert result is True

        # Verify the closed metadata was stored
        call_args = mock_redis_client._client.setex.call_args
        stored_data = json.loads(call_args[0][2])
        assert stored_data["status"] == "closed"
        assert stored_data["close_reason"] == "max_size"
        assert stored_data["closed_at"] is not None

    @pytest.mark.asyncio
    async def test_close_batch_not_found(self, metadata_service, mock_redis_client):
        """Test closing non-existent batch."""
        metadata_service._json_available = False
        mock_redis_client._client.get = AsyncMock(return_value=None)

        result = await metadata_service.close_batch("batch-nonexistent")

        assert result is False


class TestBatchMetadataServiceDeleteBatchMetadata:
    """Tests for deleting batch metadata."""

    @pytest.mark.asyncio
    async def test_delete_batch_metadata_success(self, metadata_service, mock_redis_client):
        """Test deleting metadata successfully."""
        mock_redis_client._client.delete = AsyncMock(return_value=1)

        result = await metadata_service.delete_batch_metadata("batch-delete")

        assert result is True
        mock_redis_client._client.delete.assert_called_once_with(f"{BATCH_META_PREFIX}batch-delete")

    @pytest.mark.asyncio
    async def test_delete_batch_metadata_not_found(self, metadata_service, mock_redis_client):
        """Test deleting non-existent metadata."""
        mock_redis_client._client.delete = AsyncMock(return_value=0)

        result = await metadata_service.delete_batch_metadata("batch-nonexistent")

        assert result is False


# ===========================================================================
# Test: get_batch_metadata_service factory
# ===========================================================================


class TestGetBatchMetadataService:
    """Tests for the service factory function."""

    @pytest.mark.asyncio
    async def test_creates_singleton(self, mock_redis_client):
        """Test that factory returns the same instance."""
        # Reset global state
        import backend.services.redis_json as module

        module._batch_metadata_service = None

        with patch("backend.services.redis_json.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            service1 = await get_batch_metadata_service(mock_redis_client)
            service2 = await get_batch_metadata_service(mock_redis_client)

            assert service1 is service2

        # Clean up
        module._batch_metadata_service = None


# ===========================================================================
# Test: Additional Coverage - Error Handling and Edge Cases
# ===========================================================================


class TestBatchMetadataServiceErrorHandling:
    """Additional tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_check_json_available_returns_false_when_client_none(
        self, metadata_service, mock_redis_client
    ):
        """Test JSON availability check when Redis client is None."""
        mock_redis_client._client = None

        result = await metadata_service._check_json_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_json_available_handles_transient_errors(
        self, metadata_service, mock_redis_client
    ):
        """Test JSON availability check handles transient errors."""
        mock_redis_client._client.execute_command = AsyncMock(
            side_effect=Exception("Transient error")
        )

        result = await metadata_service._check_json_available()

        assert result is False
        assert metadata_service._json_available is False

    @pytest.mark.asyncio
    async def test_set_batch_metadata_json_fallback_on_error(
        self, metadata_service, mock_redis_client
    ):
        """Test fallback to string storage when JSON.SET fails."""
        metadata_service._json_available = True
        # First call (JSON.SET) fails, then setex succeeds
        mock_redis_client._client.execute_command = AsyncMock(
            side_effect=Exception("JSON SET failed")
        )
        mock_redis_client._client.setex = AsyncMock()

        metadata = BatchMetadata(batch_id="batch-fallback", camera_id="cam1")
        result = await metadata_service.set_batch_metadata("batch-fallback", metadata)

        assert result is True
        mock_redis_client._client.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_batch_metadata_json_fallback_on_error(
        self, metadata_service, mock_redis_client
    ):
        """Test fallback to string storage when JSON.GET fails."""
        metadata_service._json_available = True
        data = {
            "batch_id": "batch-fallback-get",
            "camera_id": "cam1",
            "status": "open",
            "detection_ids": [],
            "detection_count": 0,
            "started_at": 1700000000.0,
            "last_activity": 1700000000.0,
            "closed_at": None,
            "pipeline_start_time": None,
            "close_reason": None,
            "processing_metadata": {},
        }

        # JSON.GET fails, fall back to string GET
        mock_redis_client._client.execute_command = AsyncMock(
            side_effect=Exception("JSON GET failed")
        )
        mock_redis_client._client.get = AsyncMock(return_value=json.dumps(data))

        result = await metadata_service.get_batch_metadata("batch-fallback-get")

        assert result is not None
        assert result.batch_id == "batch-fallback-get"
        mock_redis_client._client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_batch_field_handles_missing_field_in_fallback(
        self, metadata_service, mock_redis_client
    ):
        """Test get_batch_field returns None for missing nested field."""
        metadata_service._json_available = False
        data = {
            "batch_id": "batch-no-nested",
            "camera_id": "cam1",
            "status": "open",
            "detection_ids": [],
            "detection_count": 0,
            "started_at": 1700000000.0,
            "last_activity": 1700000000.0,
            "closed_at": None,
            "pipeline_start_time": None,
            "close_reason": None,
            "processing_metadata": {},
        }
        mock_redis_client._client.get = AsyncMock(return_value=json.dumps(data))

        # Try to access nested field that doesn't exist
        result = await metadata_service.get_batch_field(
            "batch-no-nested", "$.processing_metadata.nonexistent"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_update_batch_field_fallback_missing_nested_path(
        self, metadata_service, mock_redis_client
    ):
        """Test update_batch_field fallback returns False for invalid path."""
        metadata_service._json_available = False
        data = {
            "batch_id": "batch-invalid-path",
            "camera_id": "cam1",
            "status": "open",
            "detection_ids": [],
            "detection_count": 0,
            "started_at": 1700000000.0,
            "last_activity": 1700000000.0,
            "closed_at": None,
            "pipeline_start_time": None,
            "close_reason": None,
            "processing_metadata": {},
        }
        mock_redis_client._client.get = AsyncMock(return_value=json.dumps(data))

        # Try to update nested field that doesn't exist
        result = await metadata_service.update_batch_field(
            "batch-invalid-path", "$.nonexistent.field", "value"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_update_batch_field_fallback_with_refresh_ttl_none(
        self, metadata_service, mock_redis_client
    ):
        """Test update_batch_field fallback with None TTL when refresh_ttl is False."""
        metadata_service._json_available = False
        data = {
            "batch_id": "batch-no-refresh",
            "camera_id": "cam1",
            "status": "open",
            "detection_ids": [],
            "detection_count": 0,
            "started_at": 1700000000.0,
            "last_activity": 1700000000.0,
            "closed_at": None,
            "pipeline_start_time": None,
            "close_reason": None,
            "processing_metadata": {},
        }
        mock_redis_client._client.get = AsyncMock(return_value=json.dumps(data))
        mock_redis_client._client.setex = AsyncMock()

        result = await metadata_service.update_batch_field(
            "batch-no-refresh", "$.status", "closing", refresh_ttl=False
        )

        assert result is True
        # Verify setex was called with None TTL (will use default)
        call_args = mock_redis_client._client.setex.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_append_detection_id_fallback_not_found(
        self, metadata_service, mock_redis_client
    ):
        """Test append_detection_id fallback returns -1 for missing batch."""
        metadata_service._json_available = False
        mock_redis_client._client.get = AsyncMock(return_value=None)

        result = await metadata_service.append_detection_id("batch-nonexistent", 42)

        assert result == -1

    @pytest.mark.asyncio
    async def test_close_batch_json_not_exists(self, metadata_service, mock_redis_client):
        """Test close_batch with RedisJSON when batch doesn't exist."""
        metadata_service._json_available = True
        mock_redis_client._client.exists = AsyncMock(return_value=0)

        result = await metadata_service.close_batch("batch-nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_close_batch_json_fallback_on_error(self, metadata_service, mock_redis_client):
        """Test close_batch falls back on error."""
        metadata_service._json_available = True
        mock_redis_client._client.exists = AsyncMock(return_value=1)

        # Mock pipeline to raise error
        mock_pipeline = MagicMock()
        mock_pipeline.execute_command = MagicMock()
        mock_pipeline.execute = AsyncMock(side_effect=Exception("Pipeline failed"))
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock()
        mock_redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        # Fallback to string get/set
        data = {
            "batch_id": "batch-pipeline-error",
            "camera_id": "cam1",
            "status": "open",
            "detection_ids": [1, 2],
            "detection_count": 2,
            "started_at": 1700000000.0,
            "last_activity": 1700000000.0,
            "closed_at": None,
            "pipeline_start_time": None,
            "close_reason": None,
            "processing_metadata": {},
        }
        mock_redis_client._client.get = AsyncMock(return_value=json.dumps(data))
        mock_redis_client._client.setex = AsyncMock()

        result = await metadata_service.close_batch("batch-pipeline-error", reason="error")

        assert result is True

    @pytest.mark.asyncio
    async def test_get_open_batches_for_camera_handles_decode_error(
        self, metadata_service, mock_redis_client
    ):
        """Test get_open_batches_for_camera handles errors gracefully."""
        metadata_service._json_available = False

        # Mock scan_iter to return a key that causes an error
        async def mock_scan_iter(**kwargs):
            yield b"batch:meta:batch-error"
            yield b"batch:meta:batch-valid"

        mock_redis_client._client.scan_iter = mock_scan_iter

        # First batch causes error, second batch is valid
        data_valid = {
            "batch_id": "batch-valid",
            "camera_id": "front_door",
            "status": "open",
            "detection_ids": [],
            "detection_count": 0,
            "started_at": 1700000000.0,
            "last_activity": 1700000000.0,
            "closed_at": None,
            "pipeline_start_time": None,
            "close_reason": None,
            "processing_metadata": {},
        }

        mock_redis_client._client.get = AsyncMock(
            side_effect=[Exception("Decode error"), json.dumps(data_valid)]
        )

        batches = await metadata_service.get_open_batches_for_camera("front_door")

        # Should only return the valid batch, error batch skipped
        assert len(batches) == 1
        assert batches[0].batch_id == "batch-valid"

    @pytest.mark.asyncio
    async def test_get_open_batches_filters_by_camera_and_status(
        self, metadata_service, mock_redis_client
    ):
        """Test get_open_batches_for_camera filters correctly."""
        metadata_service._json_available = False

        # Mock scan_iter to return multiple keys
        async def mock_scan_iter(**kwargs):
            yield b"batch:meta:batch-1"
            yield b"batch:meta:batch-2"
            yield b"batch:meta:batch-3"

        mock_redis_client._client.scan_iter = mock_scan_iter

        # Different scenarios: right camera+open, wrong camera, right camera+closed
        data_1 = {
            "batch_id": "batch-1",
            "camera_id": "front_door",
            "status": "open",
            "detection_ids": [],
            "detection_count": 0,
            "started_at": 1700000000.0,
            "last_activity": 1700000000.0,
            "closed_at": None,
            "pipeline_start_time": None,
            "close_reason": None,
            "processing_metadata": {},
        }
        data_2 = {
            "batch_id": "batch-2",
            "camera_id": "backyard",
            "status": "open",
            "detection_ids": [],
            "detection_count": 0,
            "started_at": 1700000000.0,
            "last_activity": 1700000000.0,
            "closed_at": None,
            "pipeline_start_time": None,
            "close_reason": None,
            "processing_metadata": {},
        }
        data_3 = {
            "batch_id": "batch-3",
            "camera_id": "front_door",
            "status": "closed",
            "detection_ids": [],
            "detection_count": 0,
            "started_at": 1700000000.0,
            "last_activity": 1700000000.0,
            "closed_at": 1700000060.0,
            "pipeline_start_time": None,
            "close_reason": "timeout",
            "processing_metadata": {},
        }

        mock_redis_client._client.get = AsyncMock(
            side_effect=[json.dumps(data_1), json.dumps(data_2), json.dumps(data_3)]
        )

        batches = await metadata_service.get_open_batches_for_camera("front_door")

        # Should only return batch-1 (correct camera and open)
        assert len(batches) == 1
        assert batches[0].batch_id == "batch-1"
        assert batches[0].camera_id == "front_door"
        assert batches[0].status == "open"

    @pytest.mark.asyncio
    async def test_get_open_batches_raises_when_not_connected(self, mock_redis_client):
        """Test get_open_batches raises when Redis not connected."""
        mock_redis_client._client = None
        service = BatchMetadataService(redis_client=mock_redis_client)

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service.get_open_batches_for_camera("cam1")

    @pytest.mark.asyncio
    async def test_delete_batch_metadata_raises_when_not_connected(self, mock_redis_client):
        """Test delete raises when Redis not connected."""
        mock_redis_client._client = None
        service = BatchMetadataService(redis_client=mock_redis_client)

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service.delete_batch_metadata("batch-1")

    @pytest.mark.asyncio
    async def test_get_batch_metadata_raises_when_not_connected(self, mock_redis_client):
        """Test get_batch_metadata raises when Redis not connected."""
        mock_redis_client._client = None
        service = BatchMetadataService(redis_client=mock_redis_client)

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service.get_batch_metadata("batch-1")

    @pytest.mark.asyncio
    async def test_get_batch_field_raises_when_not_connected(self, mock_redis_client):
        """Test get_batch_field raises when Redis not connected."""
        mock_redis_client._client = None
        service = BatchMetadataService(redis_client=mock_redis_client)

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service.get_batch_field("batch-1", "$.status")

    @pytest.mark.asyncio
    async def test_update_batch_field_raises_when_not_connected(self, mock_redis_client):
        """Test update_batch_field raises when Redis not connected."""
        mock_redis_client._client = None
        service = BatchMetadataService(redis_client=mock_redis_client)

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service.update_batch_field("batch-1", "$.status", "closed")

    @pytest.mark.asyncio
    async def test_append_detection_id_raises_when_not_connected(self, mock_redis_client):
        """Test append_detection_id raises when Redis not connected."""
        mock_redis_client._client = None
        service = BatchMetadataService(redis_client=mock_redis_client)

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service.append_detection_id("batch-1", 42)

    @pytest.mark.asyncio
    async def test_close_batch_raises_when_not_connected(self, mock_redis_client):
        """Test close_batch raises when Redis not connected."""
        mock_redis_client._client = None
        service = BatchMetadataService(redis_client=mock_redis_client)

        with pytest.raises(RuntimeError, match="Redis client not connected"):
            await service.close_batch("batch-1")

    @pytest.mark.asyncio
    async def test_append_detection_id_json_get_count_returns_empty_list(
        self, metadata_service, mock_redis_client
    ):
        """Test append_detection_id when JSON.GET returns empty list for count."""
        metadata_service._json_available = True
        mock_redis_client._client.execute_command = AsyncMock(
            side_effect=[
                None,  # JSON.ARRAPPEND
                None,  # JSON.NUMINCRBY
                None,  # JSON.SET last_activity
                "[]",  # JSON.GET detection_count - empty list
            ]
        )
        mock_redis_client._client.expire = AsyncMock()

        result = await metadata_service.append_detection_id("batch-empty-count", 42)

        assert result == -1

    @pytest.mark.asyncio
    async def test_get_batch_field_json_returns_non_list_result(
        self, metadata_service, mock_redis_client
    ):
        """Test get_batch_field when JSON.GET returns non-list result."""
        metadata_service._json_available = True
        # Return a dict instead of list
        mock_redis_client._client.execute_command = AsyncMock(return_value='{"status": "open"}')

        result = await metadata_service.get_batch_field("batch-dict", "$.status")

        # Should return the dict as-is (not extract first element)
        assert result == {"status": "open"}

    @pytest.mark.asyncio
    async def test_get_batch_field_json_returns_none(self, metadata_service, mock_redis_client):
        """Test get_batch_field when JSON.GET returns None."""
        metadata_service._json_available = True
        mock_redis_client._client.execute_command = AsyncMock(return_value=None)

        result = await metadata_service.get_batch_field("batch-none", "$.status")

        assert result is None
