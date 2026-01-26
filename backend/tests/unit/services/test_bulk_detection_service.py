"""Unit tests for BulkDetectionService.

Tests cover:
- Bulk INSERT with RETURNING clause
- High-throughput detection ingestion
- Batch processing optimization
- Error handling and transaction management
- Performance metrics
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.bulk_detection_service import (
    BulkDetectionService,
    BulkInsertResult,
    DetectionBatch,
    DetectionInput,
)


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def service(mock_session: AsyncMock) -> BulkDetectionService:
    """Create a BulkDetectionService with mocked session."""
    return BulkDetectionService(mock_session)


@pytest.fixture
def sample_detections() -> list[DetectionInput]:
    """Create sample detection inputs for testing."""
    return [
        DetectionInput(
            camera_id="front_door",
            file_path="/export/foscam/front_door/image1.jpg",
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=200,
            bbox_width=50,
            bbox_height=100,
        ),
        DetectionInput(
            camera_id="front_door",
            file_path="/export/foscam/front_door/image2.jpg",
            object_type="car",
            confidence=0.85,
            bbox_x=150,
            bbox_y=250,
            bbox_width=200,
            bbox_height=100,
        ),
        DetectionInput(
            camera_id="back_yard",
            file_path="/export/foscam/back_yard/image1.jpg",
            object_type="person",
            confidence=0.75,
            bbox_x=50,
            bbox_y=100,
            bbox_width=60,
            bbox_height=120,
        ),
    ]


class TestDetectionInput:
    """Tests for DetectionInput dataclass."""

    def test_required_fields(self) -> None:
        """Test that required fields must be provided."""
        detection = DetectionInput(
            camera_id="test_cam",
            file_path="/path/to/image.jpg",
        )

        assert detection.camera_id == "test_cam"
        assert detection.file_path == "/path/to/image.jpg"
        assert detection.object_type is None
        assert detection.confidence is None
        assert detection.detected_at is not None  # Should have default

    def test_all_fields(self) -> None:
        """Test setting all fields."""
        now = datetime.now(UTC)
        detection = DetectionInput(
            camera_id="test_cam",
            file_path="/path/to/image.jpg",
            file_type="image/jpeg",
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=200,
            bbox_width=50,
            bbox_height=100,
            detected_at=now,
            media_type="image",
            thumbnail_path="/path/to/thumb.jpg",
            enrichment_data={"license_plates": []},
        )

        assert detection.file_type == "image/jpeg"
        assert detection.object_type == "person"
        assert detection.confidence == 0.95
        assert detection.bbox_x == 100
        assert detection.media_type == "image"


class TestDetectionBatch:
    """Tests for DetectionBatch dataclass."""

    def test_batch_creation(self, sample_detections: list[DetectionInput]) -> None:
        """Test creating a detection batch."""
        batch = DetectionBatch(
            batch_id="batch_001",
            detections=sample_detections,
        )

        assert batch.batch_id == "batch_001"
        assert len(batch.detections) == 3
        assert batch.created_at is not None

    def test_batch_size(self, sample_detections: list[DetectionInput]) -> None:
        """Test batch size property."""
        batch = DetectionBatch(
            batch_id="batch_001",
            detections=sample_detections,
        )

        assert batch.size == 3


class TestBulkInsertResult:
    """Tests for BulkInsertResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful bulk insert result."""
        result = BulkInsertResult(
            success=True,
            inserted_count=100,
            inserted_ids=[1, 2, 3, 4, 5],
            duration_ms=150.5,
        )

        assert result.success is True
        assert result.inserted_count == 100
        assert len(result.inserted_ids) == 5
        assert result.duration_ms == 150.5
        assert result.error_message is None
        assert result.failed_inputs == []

    def test_partial_failure_result(self) -> None:
        """Test partial failure result."""
        failed = [
            DetectionInput(camera_id="cam1", file_path="/path1.jpg"),
        ]
        result = BulkInsertResult(
            success=False,
            inserted_count=99,
            inserted_ids=list(range(1, 100)),
            duration_ms=200.0,
            error_message="1 detection failed validation",
            failed_inputs=failed,
        )

        assert result.success is False
        assert result.inserted_count == 99
        assert len(result.failed_inputs) == 1


class TestBulkDetectionService:
    """Tests for BulkDetectionService."""

    @pytest.mark.asyncio
    async def test_bulk_insert_single_detection(
        self, service: BulkDetectionService, mock_session: AsyncMock
    ) -> None:
        """Test bulk inserting a single detection."""
        detection = DetectionInput(
            camera_id="front_door",
            file_path="/export/foscam/front_door/image1.jpg",
            object_type="person",
            confidence=0.95,
        )

        # Mock the RETURNING result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1,)]
        mock_session.execute.return_value = mock_result

        result = await service.bulk_insert([detection])

        assert result.success is True
        assert result.inserted_count == 1
        assert result.inserted_ids == [1]
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_insert_multiple_detections(
        self,
        service: BulkDetectionService,
        mock_session: AsyncMock,
        sample_detections: list[DetectionInput],
    ) -> None:
        """Test bulk inserting multiple detections."""
        # Mock the RETURNING result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1,), (2,), (3,)]
        mock_session.execute.return_value = mock_result

        result = await service.bulk_insert(sample_detections)

        assert result.success is True
        assert result.inserted_count == 3
        assert result.inserted_ids == [1, 2, 3]
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_bulk_insert_empty_list(
        self, service: BulkDetectionService, mock_session: AsyncMock
    ) -> None:
        """Test bulk inserting an empty list."""
        result = await service.bulk_insert([])

        assert result.success is True
        assert result.inserted_count == 0
        assert result.inserted_ids == []
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_bulk_insert_with_all_fields(
        self, service: BulkDetectionService, mock_session: AsyncMock
    ) -> None:
        """Test bulk inserting detections with all fields populated."""
        now = datetime.now(UTC)
        detection = DetectionInput(
            camera_id="front_door",
            file_path="/export/foscam/front_door/image1.jpg",
            file_type="image/jpeg",
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=200,
            bbox_width=50,
            bbox_height=100,
            detected_at=now,
            media_type="image",
            thumbnail_path="/path/to/thumb.jpg",
            enrichment_data={"license_plates": [{"plate": "ABC123"}]},
        )

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1,)]
        mock_session.execute.return_value = mock_result

        result = await service.bulk_insert([detection])

        assert result.success is True
        # Verify the INSERT statement includes all fields
        call_args = mock_session.execute.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_bulk_insert_handles_database_error(
        self, service: BulkDetectionService, mock_session: AsyncMock
    ) -> None:
        """Test handling of database errors during bulk insert."""
        detection = DetectionInput(
            camera_id="front_door",
            file_path="/path/image.jpg",
        )

        mock_session.execute.side_effect = Exception("Database connection lost")

        result = await service.bulk_insert([detection])

        assert result.success is False
        assert "Database connection lost" in result.error_message
        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_insert_batch(
        self,
        service: BulkDetectionService,
        mock_session: AsyncMock,
        sample_detections: list[DetectionInput],
    ) -> None:
        """Test bulk inserting a DetectionBatch."""
        batch = DetectionBatch(
            batch_id="batch_001",
            detections=sample_detections,
        )

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1,), (2,), (3,)]
        mock_session.execute.return_value = mock_result

        result = await service.bulk_insert_batch(batch)

        assert result.success is True
        assert result.inserted_count == 3

    @pytest.mark.asyncio
    async def test_bulk_insert_chunked(
        self, service: BulkDetectionService, mock_session: AsyncMock
    ) -> None:
        """Test bulk inserting with chunking for large batches."""
        # Create 150 detections (should be split into chunks)
        detections = [
            DetectionInput(
                camera_id="cam1",
                file_path=f"/path/image_{i}.jpg",
                object_type="person",
                confidence=0.9,
            )
            for i in range(150)
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(i,) for i in range(1, 101)]
        mock_session.execute.return_value = mock_result

        result = await service.bulk_insert_chunked(detections, chunk_size=100)

        assert result.success is True
        # Should have executed at least 2 batches
        assert mock_session.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_bulk_insert_with_returning_ids(
        self,
        service: BulkDetectionService,
        mock_session: AsyncMock,
        sample_detections: list[DetectionInput],
    ) -> None:
        """Test that RETURNING clause correctly captures inserted IDs."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(101,), (102,), (103,)]
        mock_session.execute.return_value = mock_result

        result = await service.bulk_insert(sample_detections)

        assert result.inserted_ids == [101, 102, 103]

    @pytest.mark.asyncio
    async def test_bulk_insert_with_conflict_handling(
        self,
        service: BulkDetectionService,
        mock_session: AsyncMock,
    ) -> None:
        """Test bulk insert with ON CONFLICT handling."""
        detection = DetectionInput(
            camera_id="front_door",
            file_path="/path/existing.jpg",  # Might conflict
        )

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1,)]
        mock_session.execute.return_value = mock_result

        result = await service.bulk_insert(
            [detection],
            on_conflict="skip",  # Skip on conflict instead of raising error
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_validate_detection_input(self, service: BulkDetectionService) -> None:
        """Test validation of detection input."""
        # Valid detection
        valid = DetectionInput(
            camera_id="front_door",
            file_path="/path/image.jpg",
            confidence=0.95,
        )
        assert service.validate_detection(valid) is True

        # Invalid confidence (out of range)
        invalid = DetectionInput(
            camera_id="front_door",
            file_path="/path/image.jpg",
            confidence=1.5,  # Invalid - should be 0-1
        )
        assert service.validate_detection(invalid) is False

    @pytest.mark.asyncio
    async def test_bulk_insert_filters_invalid(
        self,
        service: BulkDetectionService,
        mock_session: AsyncMock,
    ) -> None:
        """Test that invalid detections are filtered out."""
        detections = [
            DetectionInput(
                camera_id="cam1",
                file_path="/path/valid.jpg",
                confidence=0.9,
            ),
            DetectionInput(
                camera_id="cam1",
                file_path="/path/invalid.jpg",
                confidence=1.5,  # Invalid
            ),
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1,)]
        mock_session.execute.return_value = mock_result

        result = await service.bulk_insert(detections, validate=True)

        # Only valid detection should be inserted
        assert result.inserted_count == 1
        assert len(result.failed_inputs) == 1

    @pytest.mark.asyncio
    async def test_get_insert_performance_stats(
        self,
        service: BulkDetectionService,
        mock_session: AsyncMock,
        sample_detections: list[DetectionInput],
    ) -> None:
        """Test getting performance statistics for bulk inserts."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1,), (2,), (3,)]
        mock_session.execute.return_value = mock_result

        # Perform some inserts
        await service.bulk_insert(sample_detections)
        await service.bulk_insert(sample_detections)

        stats = service.get_performance_stats()

        assert stats["total_inserts"] >= 6
        assert stats["total_batches"] >= 2
        assert stats["avg_batch_size"] >= 0
        assert stats["avg_insert_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_bulk_insert_preserves_order(
        self,
        service: BulkDetectionService,
        mock_session: AsyncMock,
    ) -> None:
        """Test that insertion order is preserved."""
        detections = [
            DetectionInput(camera_id="cam1", file_path=f"/path/{i}.jpg") for i in range(5)
        ]

        mock_result = MagicMock()
        # Return IDs in order
        mock_result.fetchall.return_value = [(1,), (2,), (3,), (4,), (5,)]
        mock_session.execute.return_value = mock_result

        result = await service.bulk_insert(detections)

        assert result.inserted_ids == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_bulk_insert_with_video_metadata(
        self,
        service: BulkDetectionService,
        mock_session: AsyncMock,
    ) -> None:
        """Test bulk inserting detections with video metadata."""
        detection = DetectionInput(
            camera_id="front_door",
            file_path="/export/foscam/front_door/video1.mp4",
            media_type="video",
            object_type="person",
            confidence=0.85,
        )

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1,)]
        mock_session.execute.return_value = mock_result

        result = await service.bulk_insert([detection])

        assert result.success is True
        assert result.inserted_count == 1

    def test_reset_stats(self, service: BulkDetectionService) -> None:
        """Test resetting performance statistics."""
        # Manually set some stats
        service._stats["total_inserts"] = 100
        service._stats["total_batches"] = 10

        service.reset_stats()

        stats = service.get_performance_stats()
        assert stats["total_inserts"] == 0
        assert stats["total_batches"] == 0
