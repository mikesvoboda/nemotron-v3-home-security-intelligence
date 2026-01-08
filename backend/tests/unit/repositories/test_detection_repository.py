"""Tests for DetectionRepository detection-specific operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.detection import Detection
from backend.repositories.detection_repository import DetectionRepository


class TestDetectionRepository:
    """Test suite for DetectionRepository operations."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def detection_repository(self, mock_session: AsyncMock) -> DetectionRepository:
        """Create a detection repository instance."""
        return DetectionRepository(mock_session)

    @pytest.mark.asyncio
    async def test_get_by_id_with_camera_returns_detection_with_camera(
        self, detection_repository: DetectionRepository, mock_session: AsyncMock
    ) -> None:
        """Test get_by_id_with_camera returns detection with camera loaded."""
        detection = Detection(
            id=1, camera_id="front_door", file_path="/img.jpg", detected_at=datetime.now(UTC)
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = detection
        mock_session.execute.return_value = mock_result

        result = await detection_repository.get_by_id_with_camera(1)

        assert result == detection

    @pytest.mark.asyncio
    async def test_get_by_id_with_camera_returns_none_when_not_found(
        self, detection_repository: DetectionRepository, mock_session: AsyncMock
    ) -> None:
        """Test get_by_id_with_camera returns None when not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await detection_repository.get_by_id_with_camera(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_camera_id_returns_detections(
        self, detection_repository: DetectionRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_by_camera_id returns detections for camera."""
        detections = [
            Detection(id=1, camera_id="cam1", file_path="/img1.jpg", detected_at=datetime.now(UTC)),
            Detection(id=2, camera_id="cam1", file_path="/img2.jpg", detected_at=datetime.now(UTC)),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = detections
        mock_session.execute.return_value = mock_result

        result = await detection_repository.find_by_camera_id("cam1")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_find_by_object_type_returns_matching_detections(
        self, detection_repository: DetectionRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_by_object_type returns detections with matching type."""
        detections = [
            Detection(
                id=1,
                camera_id="cam1",
                file_path="/img.jpg",
                detected_at=datetime.now(UTC),
                object_type="person",
            )
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = detections
        mock_session.execute.return_value = mock_result

        result = await detection_repository.find_by_object_type("person")

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_find_by_time_range_returns_detections_in_range(
        self, detection_repository: DetectionRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_by_time_range returns detections within time range."""
        now = datetime.now(UTC)
        detections = [Detection(id=1, camera_id="cam1", file_path="/img.jpg", detected_at=now)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = detections
        mock_session.execute.return_value = mock_result
        start_time = now - timedelta(hours=1)
        end_time = now + timedelta(hours=1)

        result = await detection_repository.find_by_time_range(start_time, end_time)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_find_high_confidence_returns_high_confidence_detections(
        self, detection_repository: DetectionRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_high_confidence returns detections above threshold."""
        detections = [
            Detection(
                id=1,
                camera_id="cam1",
                file_path="/img.jpg",
                detected_at=datetime.now(UTC),
                confidence=0.95,
            )
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = detections
        mock_session.execute.return_value = mock_result

        result = await detection_repository.find_high_confidence(min_confidence=0.8)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_find_high_confidence_with_custom_threshold(
        self, detection_repository: DetectionRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_high_confidence respects custom min_confidence."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await detection_repository.find_high_confidence(min_confidence=0.95)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_by_file_path_returns_detection(
        self, detection_repository: DetectionRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_by_file_path returns detection when found."""
        detection = Detection(
            id=1,
            camera_id="front_door",
            file_path="/images/test.jpg",
            detected_at=datetime.now(UTC),
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = detection
        mock_session.execute.return_value = mock_result

        result = await detection_repository.find_by_file_path("/images/test.jpg")

        assert result == detection

    @pytest.mark.asyncio
    async def test_find_by_file_path_returns_none_when_not_found(
        self, detection_repository: DetectionRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_by_file_path returns None when not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await detection_repository.find_by_file_path("/nonexistent.jpg")

        assert result is None

    @pytest.mark.asyncio
    async def test_find_videos_returns_video_detections(
        self, detection_repository: DetectionRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_videos returns only video detections."""
        detections = [
            Detection(
                id=1,
                camera_id="cam1",
                file_path="/vid.mp4",
                detected_at=datetime.now(UTC),
                media_type="video",
            )
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = detections
        mock_session.execute.return_value = mock_result

        result = await detection_repository.find_videos()

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_count_by_camera_returns_count(
        self, detection_repository: DetectionRepository, mock_session: AsyncMock
    ) -> None:
        """Test count_by_camera returns detection count for camera."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 150
        mock_session.execute.return_value = mock_result

        result = await detection_repository.count_by_camera("front_door")

        assert result == 150

    @pytest.mark.asyncio
    async def test_count_by_object_type_returns_count(
        self, detection_repository: DetectionRepository, mock_session: AsyncMock
    ) -> None:
        """Test count_by_object_type returns count for object type."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 75
        mock_session.execute.return_value = mock_result

        result = await detection_repository.count_by_object_type("person")

        assert result == 75

    @pytest.mark.asyncio
    async def test_get_object_type_counts_returns_counts_dict(
        self, detection_repository: DetectionRepository, mock_session: AsyncMock
    ) -> None:
        """Test get_object_type_counts returns dictionary of type counts."""
        mock_result = MagicMock()
        mock_result.all.return_value = [("person", 100), ("car", 50), ("dog", 25)]
        mock_session.execute.return_value = mock_result

        result = await detection_repository.get_object_type_counts()

        assert result == {"person": 100, "car": 50, "dog": 25}

    @pytest.mark.asyncio
    async def test_get_latest_by_camera_returns_recent_detections(
        self, detection_repository: DetectionRepository, mock_session: AsyncMock
    ) -> None:
        """Test get_latest_by_camera returns most recent detections."""
        now = datetime.now(UTC)
        detections = [
            Detection(id=1, camera_id="cam1", file_path="/img1.jpg", detected_at=now),
            Detection(
                id=2,
                camera_id="cam1",
                file_path="/img2.jpg",
                detected_at=now - timedelta(minutes=1),
            ),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = detections
        mock_session.execute.return_value = mock_result

        result = await detection_repository.get_latest_by_camera("cam1", limit=2)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_create_batch_creates_multiple_detections(
        self, detection_repository: DetectionRepository, mock_session: AsyncMock
    ) -> None:
        """Test create_batch creates multiple detections."""
        detections = [
            Detection(id=1, camera_id="cam1", file_path="/img1.jpg", detected_at=datetime.now(UTC)),
            Detection(id=2, camera_id="cam1", file_path="/img2.jpg", detected_at=datetime.now(UTC)),
        ]

        result = await detection_repository.create_batch(detections)

        mock_session.add_all.assert_called_once_with(detections)
        mock_session.flush.assert_called_once()
        assert len(result) == 2
