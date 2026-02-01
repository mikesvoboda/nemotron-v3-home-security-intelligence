"""Unit tests for face recognition API routes.

Tests the face recognition endpoints including:
- GET /api/known-persons/{id}/appearances - Get person appearance timeline
- GET /api/face-events/stats - Face detection statistics
- POST /api/known-persons/{id}/enroll-from-detection - Enroll face from detection
- POST /api/face-events/{event_id}/identify - Manually identify unknown face

Implements NEM-4688 Phase 1: Face Recognition UI Backend Support
Implements NEM-4688 Phase 2: Face Event Identify Endpoint

These tests follow TDD methodology - tests written before implementation.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from backend.models.detection import Detection
from backend.models.face_identity import FaceDetectionEvent, FaceEmbedding, KnownPerson


class TestGetPersonAppearances:
    """Tests for GET /api/known-persons/{id}/appearances endpoint."""

    @pytest.mark.asyncio
    async def test_get_appearances_success(self) -> None:
        """Test getting appearances returns timeline for known person."""
        from backend.api.routes.face_recognition import get_person_appearances

        mock_db = AsyncMock()

        # Mock the service response
        mock_appearances = [
            {
                "timestamp": datetime(2025, 1, 31, 10, 30, 0, tzinfo=UTC),
                "camera_id": "front_door",
                "camera_name": "Front Door",
                "detection_id": 1,
                "confidence": 0.95,
                "thumbnail_url": "/api/thumbnails/face_1.jpg",
            },
            {
                "timestamp": datetime(2025, 1, 31, 8, 15, 0, tzinfo=UTC),
                "camera_id": "driveway",
                "camera_name": "Driveway",
                "detection_id": 2,
                "confidence": 0.92,
                "thumbnail_url": "/api/thumbnails/face_2.jpg",
            },
        ]

        with patch(
            "backend.api.routes.face_recognition.get_face_recognition_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_person_appearances = AsyncMock(return_value=(mock_appearances, 2))
            mock_get_service.return_value = mock_service

            result = await get_person_appearances(
                person_id=1,
                session=mock_db,
            )

            assert result.total_count == 2
            assert len(result.appearances) == 2
            assert result.appearances[0].camera_id == "front_door"
            assert result.appearances[0].confidence == 0.95
            assert result.appearances[1].camera_id == "driveway"

            # Verify service was called with correct person_id
            mock_service.get_person_appearances.assert_called_once()
            call_kwargs = mock_service.get_person_appearances.call_args[1]
            assert call_kwargs["person_id"] == 1

    @pytest.mark.asyncio
    async def test_get_appearances_with_date_filter(self) -> None:
        """Test getting appearances with date range filter."""
        from backend.api.routes.face_recognition import get_person_appearances

        mock_db = AsyncMock()
        start = datetime(2025, 1, 30, 0, 0, 0, tzinfo=UTC)
        end = datetime(2025, 1, 31, 23, 59, 59, tzinfo=UTC)

        with patch(
            "backend.api.routes.face_recognition.get_face_recognition_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_person_appearances = AsyncMock(return_value=([], 0))
            mock_get_service.return_value = mock_service

            result = await get_person_appearances(
                person_id=1,
                start_date=start,
                end_date=end,
                session=mock_db,
            )

            # Verify service was called with correct date filters
            mock_service.get_person_appearances.assert_called_once()
            call_kwargs = mock_service.get_person_appearances.call_args[1]
            assert call_kwargs["person_id"] == 1
            assert call_kwargs["start_date"] == start
            assert call_kwargs["end_date"] == end
            assert result.total_count == 0
            assert len(result.appearances) == 0

    @pytest.mark.asyncio
    async def test_get_appearances_with_camera_filter(self) -> None:
        """Test getting appearances filtered by camera ID."""
        from backend.api.routes.face_recognition import get_person_appearances

        mock_db = AsyncMock()

        with patch(
            "backend.api.routes.face_recognition.get_face_recognition_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_person_appearances = AsyncMock(return_value=([], 0))
            mock_get_service.return_value = mock_service

            await get_person_appearances(
                person_id=1,
                camera_id="front_door",
                session=mock_db,
            )

            # Verify service was called with correct camera filter
            mock_service.get_person_appearances.assert_called_once()
            call_kwargs = mock_service.get_person_appearances.call_args[1]
            assert call_kwargs["person_id"] == 1
            assert call_kwargs["camera_id"] == "front_door"

    @pytest.mark.asyncio
    async def test_get_appearances_with_pagination(self) -> None:
        """Test getting appearances with limit and offset pagination."""
        from backend.api.routes.face_recognition import get_person_appearances

        mock_db = AsyncMock()

        with patch(
            "backend.api.routes.face_recognition.get_face_recognition_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_person_appearances = AsyncMock(return_value=([], 0))
            mock_get_service.return_value = mock_service

            await get_person_appearances(
                person_id=1,
                limit=10,
                offset=20,
                session=mock_db,
            )

            # Verify service was called with correct pagination
            mock_service.get_person_appearances.assert_called_once()
            call_kwargs = mock_service.get_person_appearances.call_args[1]
            assert call_kwargs["person_id"] == 1
            assert call_kwargs["limit"] == 10
            assert call_kwargs["offset"] == 20

    @pytest.mark.asyncio
    async def test_get_appearances_person_not_found(self) -> None:
        """Test get appearances returns 404 if person doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.face_recognition import get_person_appearances

        mock_db = AsyncMock()

        with patch(
            "backend.api.routes.face_recognition.get_face_recognition_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_person_appearances = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await get_person_appearances(
                    person_id=999,
                    session=mock_db,
                )

            assert exc_info.value.status_code == 404
            assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_appearances_ordered_by_timestamp_desc(self) -> None:
        """Test appearances are ordered by timestamp descending (most recent first)."""
        from backend.api.routes.face_recognition import get_person_appearances

        mock_db = AsyncMock()

        # Appearances should already be ordered by service
        mock_appearances = [
            {
                "timestamp": datetime(2025, 1, 31, 15, 0, 0, tzinfo=UTC),
                "camera_id": "front_door",
                "camera_name": "Front Door",
                "detection_id": 3,
                "confidence": 0.93,
                "thumbnail_url": None,
            },
            {
                "timestamp": datetime(2025, 1, 31, 10, 0, 0, tzinfo=UTC),
                "camera_id": "driveway",
                "camera_name": "Driveway",
                "detection_id": 2,
                "confidence": 0.91,
                "thumbnail_url": None,
            },
            {
                "timestamp": datetime(2025, 1, 31, 8, 0, 0, tzinfo=UTC),
                "camera_id": "backyard",
                "camera_name": "Backyard",
                "detection_id": 1,
                "confidence": 0.89,
                "thumbnail_url": None,
            },
        ]

        with patch(
            "backend.api.routes.face_recognition.get_face_recognition_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_person_appearances = AsyncMock(return_value=(mock_appearances, 3))
            mock_get_service.return_value = mock_service

            result = await get_person_appearances(
                person_id=1,
                session=mock_db,
            )

            # Verify order - most recent first
            assert result.appearances[0].timestamp > result.appearances[1].timestamp
            assert result.appearances[1].timestamp > result.appearances[2].timestamp

    @pytest.mark.asyncio
    async def test_get_appearances_empty_result(self) -> None:
        """Test getting appearances for person with no detections."""
        from backend.api.routes.face_recognition import get_person_appearances

        mock_db = AsyncMock()

        with patch(
            "backend.api.routes.face_recognition.get_face_recognition_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_person_appearances = AsyncMock(return_value=([], 0))
            mock_get_service.return_value = mock_service

            result = await get_person_appearances(
                person_id=1,
                session=mock_db,
            )

            assert result.total_count == 0
            assert len(result.appearances) == 0

    @pytest.mark.asyncio
    async def test_get_appearances_includes_camera_name(self) -> None:
        """Test that appearances include camera name from relationship."""
        from backend.api.routes.face_recognition import get_person_appearances

        mock_db = AsyncMock()

        mock_appearances = [
            {
                "timestamp": datetime(2025, 1, 31, 10, 0, 0, tzinfo=UTC),
                "camera_id": "front_door",
                "camera_name": "Front Door Camera",
                "detection_id": 1,
                "confidence": 0.95,
                "thumbnail_url": "/api/thumbnails/face_1.jpg",
            },
        ]

        with patch(
            "backend.api.routes.face_recognition.get_face_recognition_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_person_appearances = AsyncMock(return_value=(mock_appearances, 1))
            mock_get_service.return_value = mock_service

            result = await get_person_appearances(
                person_id=1,
                session=mock_db,
            )

            assert result.appearances[0].camera_name == "Front Door Camera"


class TestPersonAppearancesSchemas:
    """Tests for person appearances response schemas."""

    def test_person_appearance_schema_fields(self) -> None:
        """Test PersonAppearance schema has all required fields."""
        from backend.api.schemas.face_recognition import PersonAppearance

        appearance = PersonAppearance(
            timestamp=datetime(2025, 1, 31, 10, 0, 0, tzinfo=UTC),
            camera_id="front_door",
            camera_name="Front Door",
            detection_id=1,
            confidence=0.95,
            thumbnail_url="/api/thumbnails/face_1.jpg",
        )

        assert appearance.timestamp == datetime(2025, 1, 31, 10, 0, 0, tzinfo=UTC)
        assert appearance.camera_id == "front_door"
        assert appearance.camera_name == "Front Door"
        assert appearance.detection_id == 1
        assert appearance.confidence == 0.95
        assert appearance.thumbnail_url == "/api/thumbnails/face_1.jpg"

    def test_person_appearance_optional_thumbnail(self) -> None:
        """Test PersonAppearance allows None thumbnail_url."""
        from backend.api.schemas.face_recognition import PersonAppearance

        appearance = PersonAppearance(
            timestamp=datetime(2025, 1, 31, 10, 0, 0, tzinfo=UTC),
            camera_id="front_door",
            camera_name="Front Door",
            detection_id=1,
            confidence=0.95,
            thumbnail_url=None,
        )

        assert appearance.thumbnail_url is None

    def test_person_appearances_response_schema(self) -> None:
        """Test PersonAppearancesResponse schema structure."""
        from backend.api.schemas.face_recognition import (
            PersonAppearance,
            PersonAppearancesResponse,
        )

        response = PersonAppearancesResponse(
            appearances=[
                PersonAppearance(
                    timestamp=datetime(2025, 1, 31, 10, 0, 0, tzinfo=UTC),
                    camera_id="front_door",
                    camera_name="Front Door",
                    detection_id=1,
                    confidence=0.95,
                    thumbnail_url=None,
                )
            ],
            total_count=1,
        )

        assert len(response.appearances) == 1
        assert response.total_count == 1


class TestFaceEventsStats:
    """Tests for GET /api/face-events/stats endpoint.

    Implements NEM-4688 Phase 2: Add Face Events Stats Endpoint.
    """

    @pytest.mark.asyncio
    async def test_face_events_stats_with_data(self, mock_db_session: AsyncMock) -> None:
        """Test face events stats returns correct counts when data exists."""
        from backend.api.routes.face_recognition import get_face_events_stats
        from backend.api.schemas.face_recognition import FaceEventsStatsResponse

        # Mock database query result with face event counts
        # Each row represents: camera_id, total, known_count, unknown_count
        mock_row_1 = MagicMock()
        mock_row_1.camera_id = "front_door"
        mock_row_1.total = 15
        mock_row_1.known_count = 10
        mock_row_1.unknown_count = 5

        mock_row_2 = MagicMock()
        mock_row_2.camera_id = "back_door"
        mock_row_2.total = 8
        mock_row_2.known_count = 3
        mock_row_2.unknown_count = 5

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row_1, mock_row_2]
        mock_db_session.execute.return_value = mock_result

        result = await get_face_events_stats(session=mock_db_session)

        # Verify response structure
        assert isinstance(result, FaceEventsStatsResponse)
        assert result.total_today == 23  # 15 + 8
        assert result.known_count == 13  # 10 + 3
        assert result.unknown_count == 10  # 5 + 5

        # Verify by_camera breakdown
        assert len(result.by_camera) == 2
        assert result.by_camera["front_door"].total == 15
        assert result.by_camera["front_door"].known == 10
        assert result.by_camera["front_door"].unknown == 5
        assert result.by_camera["back_door"].total == 8
        assert result.by_camera["back_door"].known == 3
        assert result.by_camera["back_door"].unknown == 5

    @pytest.mark.asyncio
    async def test_face_events_stats_no_data(self, mock_db_session: AsyncMock) -> None:
        """Test face events stats returns zeros when no face events exist today."""
        from backend.api.routes.face_recognition import get_face_events_stats
        from backend.api.schemas.face_recognition import FaceEventsStatsResponse

        # Mock empty database query result
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        result = await get_face_events_stats(session=mock_db_session)

        # Verify response has zero counts
        assert isinstance(result, FaceEventsStatsResponse)
        assert result.total_today == 0
        assert result.known_count == 0
        assert result.unknown_count == 0
        assert result.by_camera == {}

    @pytest.mark.asyncio
    async def test_face_events_stats_single_camera(self, mock_db_session: AsyncMock) -> None:
        """Test face events stats works with single camera data."""
        from backend.api.routes.face_recognition import get_face_events_stats

        mock_row = MagicMock()
        mock_row.camera_id = "front_door"
        mock_row.total = 42
        mock_row.known_count = 30
        mock_row.unknown_count = 12

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db_session.execute.return_value = mock_result

        result = await get_face_events_stats(session=mock_db_session)

        assert result.total_today == 42
        assert result.known_count == 30
        assert result.unknown_count == 12
        assert len(result.by_camera) == 1
        assert result.by_camera["front_door"].total == 42
        assert result.by_camera["front_door"].known == 30
        assert result.by_camera["front_door"].unknown == 12

    @pytest.mark.asyncio
    async def test_face_events_stats_all_known(self, mock_db_session: AsyncMock) -> None:
        """Test face events stats when all faces are known (no unknowns)."""
        from backend.api.routes.face_recognition import get_face_events_stats

        mock_row = MagicMock()
        mock_row.camera_id = "front_door"
        mock_row.total = 20
        mock_row.known_count = 20
        mock_row.unknown_count = 0

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db_session.execute.return_value = mock_result

        result = await get_face_events_stats(session=mock_db_session)

        assert result.total_today == 20
        assert result.known_count == 20
        assert result.unknown_count == 0
        assert result.by_camera["front_door"].unknown == 0

    @pytest.mark.asyncio
    async def test_face_events_stats_all_unknown(self, mock_db_session: AsyncMock) -> None:
        """Test face events stats when all faces are unknown (strangers)."""
        from backend.api.routes.face_recognition import get_face_events_stats

        mock_row = MagicMock()
        mock_row.camera_id = "front_door"
        mock_row.total = 15
        mock_row.known_count = 0
        mock_row.unknown_count = 15

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db_session.execute.return_value = mock_result

        result = await get_face_events_stats(session=mock_db_session)

        assert result.total_today == 15
        assert result.known_count == 0
        assert result.unknown_count == 15
        assert result.by_camera["front_door"].known == 0

    @pytest.mark.asyncio
    async def test_face_events_stats_many_cameras(self, mock_db_session: AsyncMock) -> None:
        """Test face events stats handles many cameras correctly."""
        from backend.api.routes.face_recognition import get_face_events_stats

        # Create mock data for 5 cameras
        camera_data = [
            ("front_door", 100, 80, 20),
            ("back_door", 50, 30, 20),
            ("garage", 25, 15, 10),
            ("side_yard", 10, 5, 5),
            ("driveway", 5, 2, 3),
        ]

        mock_rows = []
        for camera_id, total, known, unknown in camera_data:
            mock_row = MagicMock()
            mock_row.camera_id = camera_id
            mock_row.total = total
            mock_row.known_count = known
            mock_row.unknown_count = unknown
            mock_rows.append(mock_row)

        mock_result = MagicMock()
        mock_result.all.return_value = mock_rows
        mock_db_session.execute.return_value = mock_result

        result = await get_face_events_stats(session=mock_db_session)

        # Verify totals
        assert result.total_today == 190  # Sum of all totals
        assert result.known_count == 132  # Sum of all known
        assert result.unknown_count == 58  # Sum of all unknown

        # Verify all cameras are present
        assert len(result.by_camera) == 5
        for camera_id, total, known, unknown in camera_data:
            assert result.by_camera[camera_id].total == total
            assert result.by_camera[camera_id].known == known
            assert result.by_camera[camera_id].unknown == unknown

    @pytest.mark.asyncio
    async def test_face_events_stats_null_counts_handled(self, mock_db_session: AsyncMock) -> None:
        """Test face events stats handles NULL counts from database (converts to 0)."""
        from backend.api.routes.face_recognition import get_face_events_stats

        mock_row = MagicMock()
        mock_row.camera_id = "front_door"
        mock_row.total = 0
        mock_row.known_count = None  # NULL from database
        mock_row.unknown_count = None  # NULL from database

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db_session.execute.return_value = mock_result

        result = await get_face_events_stats(session=mock_db_session)

        # Verify NULL is converted to 0
        assert result.total_today == 0
        assert result.known_count == 0
        assert result.unknown_count == 0
        assert result.by_camera["front_door"].known == 0
        assert result.by_camera["front_door"].unknown == 0


class TestFaceEventsStatsResponseSchema:
    """Tests for FaceEventsStatsResponse schema validation."""

    def test_schema_valid_data(self) -> None:
        """Test schema accepts valid data."""
        from backend.api.schemas.face_recognition import (
            CameraFaceStats,
            FaceEventsStatsResponse,
        )

        stats = FaceEventsStatsResponse(
            total_today=100,
            known_count=70,
            unknown_count=30,
            by_camera={
                "front_door": CameraFaceStats(total=60, known=40, unknown=20),
                "back_door": CameraFaceStats(total=40, known=30, unknown=10),
            },
        )

        assert stats.total_today == 100
        assert stats.known_count == 70
        assert stats.unknown_count == 30
        assert len(stats.by_camera) == 2

    def test_schema_empty_by_camera(self) -> None:
        """Test schema accepts empty by_camera dict."""
        from backend.api.schemas.face_recognition import FaceEventsStatsResponse

        stats = FaceEventsStatsResponse(
            total_today=0,
            known_count=0,
            unknown_count=0,
            by_camera={},
        )

        assert stats.by_camera == {}

    def test_camera_face_stats_schema(self) -> None:
        """Test CameraFaceStats schema validation."""
        from backend.api.schemas.face_recognition import CameraFaceStats

        stats = CameraFaceStats(total=50, known=30, unknown=20)

        assert stats.total == 50
        assert stats.known == 30
        assert stats.unknown == 20


# =============================================================================
# Enroll From Detection Tests (NEM-4688 Phase 1)
# =============================================================================


class TestEnrollFromDetection:
    """Tests for POST /api/known-persons/{id}/enroll-from-detection endpoint."""

    @pytest.mark.asyncio
    async def test_enroll_from_detection_success_high_quality(self) -> None:
        """Test successfully enrolling face from detection with high quality (>= 0.8)."""
        from backend.api.routes.face_recognition import enroll_from_detection
        from backend.api.schemas.face_recognition import EnrollFromDetectionRequest

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        # Mock known person exists with fewer than 10 embeddings
        mock_person = MagicMock(spec=KnownPerson)
        mock_person.id = 1
        mock_person.name = "John Doe"
        mock_person.embeddings = []  # No existing embeddings

        # Mock detection exists with a face
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 100
        mock_detection.file_path = "/data/images/test_detection.jpg"
        mock_detection.object_type = "person"
        mock_detection.bbox_x = 100
        mock_detection.bbox_y = 50
        mock_detection.bbox_width = 200
        mock_detection.bbox_height = 400

        # Mock embedding extraction returns high quality
        mock_embedding = np.random.rand(512).astype(np.float32).tolist()
        mock_quality_score = 0.92

        # First call returns person, second call returns detection
        mock_result_person = MagicMock()
        mock_result_person.scalar_one_or_none.return_value = mock_person
        mock_result_detection = MagicMock()
        mock_result_detection.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.side_effect = [mock_result_person, mock_result_detection]

        request_data = EnrollFromDetectionRequest(detection_id="100")

        # Mock the face embedding extraction
        with patch(
            "backend.api.routes.face_recognition.extract_face_embedding_from_detection"
        ) as mock_extract:
            mock_extract.return_value = (mock_embedding, mock_quality_score)

            # Mock the service
            mock_face_embedding = MagicMock(spec=FaceEmbedding)
            mock_face_embedding.id = 1
            mock_face_embedding.person_id = 1
            mock_face_embedding.quality_score = mock_quality_score
            mock_face_embedding.source_image_path = mock_detection.file_path

            with patch(
                "backend.api.routes.face_recognition.get_face_recognition_service"
            ) as mock_get_service:
                mock_service = MagicMock()
                mock_service.add_face_embedding = AsyncMock(return_value=mock_face_embedding)
                mock_get_service.return_value = mock_service

                result = await enroll_from_detection(
                    person_id=1,
                    data=request_data,
                    session=mock_db,
                )

        assert result.success is True
        assert result.embedding_id == 1
        assert result.quality_score == 0.92
        assert result.warning is None  # No warning for high quality

    @pytest.mark.asyncio
    async def test_enroll_from_detection_success_with_warning(self) -> None:
        """Test enrolling face with quality between 0.7-0.8 returns warning."""
        from backend.api.routes.face_recognition import enroll_from_detection
        from backend.api.schemas.face_recognition import EnrollFromDetectionRequest

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        mock_person = MagicMock(spec=KnownPerson)
        mock_person.id = 1
        mock_person.name = "John Doe"
        mock_person.embeddings = []

        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 100
        mock_detection.file_path = "/data/images/test_detection.jpg"
        mock_detection.object_type = "person"
        mock_detection.bbox_x = 100
        mock_detection.bbox_y = 50
        mock_detection.bbox_width = 200
        mock_detection.bbox_height = 400

        mock_embedding = np.random.rand(512).astype(np.float32).tolist()
        mock_quality_score = 0.75  # Between 0.7-0.8 triggers warning

        mock_result_person = MagicMock()
        mock_result_person.scalar_one_or_none.return_value = mock_person
        mock_result_detection = MagicMock()
        mock_result_detection.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.side_effect = [mock_result_person, mock_result_detection]

        request_data = EnrollFromDetectionRequest(detection_id="100")

        with patch(
            "backend.api.routes.face_recognition.extract_face_embedding_from_detection"
        ) as mock_extract:
            mock_extract.return_value = (mock_embedding, mock_quality_score)

            mock_face_embedding = MagicMock(spec=FaceEmbedding)
            mock_face_embedding.id = 2
            mock_face_embedding.person_id = 1
            mock_face_embedding.quality_score = mock_quality_score
            mock_face_embedding.source_image_path = mock_detection.file_path

            with patch(
                "backend.api.routes.face_recognition.get_face_recognition_service"
            ) as mock_get_service:
                mock_service = MagicMock()
                mock_service.add_face_embedding = AsyncMock(return_value=mock_face_embedding)
                mock_get_service.return_value = mock_service

                result = await enroll_from_detection(
                    person_id=1,
                    data=request_data,
                    session=mock_db,
                )

        assert result.success is True
        assert result.embedding_id == 2
        assert result.quality_score == 0.75
        assert result.warning is not None
        assert "quality" in result.warning.lower()

    @pytest.mark.asyncio
    async def test_enroll_from_detection_rejected_low_quality(self) -> None:
        """Test enrollment rejected when quality score < 0.7."""
        from fastapi import HTTPException

        from backend.api.routes.face_recognition import enroll_from_detection
        from backend.api.schemas.face_recognition import EnrollFromDetectionRequest

        mock_db = AsyncMock()

        mock_person = MagicMock(spec=KnownPerson)
        mock_person.id = 1
        mock_person.name = "John Doe"
        mock_person.embeddings = []

        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 100
        mock_detection.file_path = "/data/images/test_detection.jpg"
        mock_detection.object_type = "person"
        mock_detection.bbox_x = 100
        mock_detection.bbox_y = 50
        mock_detection.bbox_width = 200
        mock_detection.bbox_height = 400

        mock_embedding = np.random.rand(512).astype(np.float32).tolist()
        mock_quality_score = 0.65  # Below 0.7 threshold

        mock_result_person = MagicMock()
        mock_result_person.scalar_one_or_none.return_value = mock_person
        mock_result_detection = MagicMock()
        mock_result_detection.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.side_effect = [mock_result_person, mock_result_detection]

        request_data = EnrollFromDetectionRequest(detection_id="100")

        with patch(
            "backend.api.routes.face_recognition.extract_face_embedding_from_detection"
        ) as mock_extract:
            mock_extract.return_value = (mock_embedding, mock_quality_score)

            with pytest.raises(HTTPException) as exc_info:
                await enroll_from_detection(
                    person_id=1,
                    data=request_data,
                    session=mock_db,
                )

        assert exc_info.value.status_code == 400
        assert "quality" in exc_info.value.detail.lower()
        assert "0.7" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_enroll_from_detection_person_not_found(self) -> None:
        """Test enrollment returns 404 when known person doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.face_recognition import enroll_from_detection
        from backend.api.schemas.face_recognition import EnrollFromDetectionRequest

        mock_db = AsyncMock()

        mock_result_person = MagicMock()
        mock_result_person.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result_person

        request_data = EnrollFromDetectionRequest(detection_id="100")

        with pytest.raises(HTTPException) as exc_info:
            await enroll_from_detection(
                person_id=999,
                data=request_data,
                session=mock_db,
            )

        assert exc_info.value.status_code == 404
        assert "person" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_enroll_from_detection_detection_not_found(self) -> None:
        """Test enrollment returns 404 when detection doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.face_recognition import enroll_from_detection
        from backend.api.schemas.face_recognition import EnrollFromDetectionRequest

        mock_db = AsyncMock()

        mock_person = MagicMock(spec=KnownPerson)
        mock_person.id = 1
        mock_person.name = "John Doe"
        mock_person.embeddings = []

        mock_result_person = MagicMock()
        mock_result_person.scalar_one_or_none.return_value = mock_person
        mock_result_detection = MagicMock()
        mock_result_detection.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [mock_result_person, mock_result_detection]

        request_data = EnrollFromDetectionRequest(detection_id="999")

        with pytest.raises(HTTPException) as exc_info:
            await enroll_from_detection(
                person_id=1,
                data=request_data,
                session=mock_db,
            )

        assert exc_info.value.status_code == 404
        assert "detection" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_enroll_from_detection_no_face_in_detection(self) -> None:
        """Test enrollment returns 400 when detection has no face."""
        from fastapi import HTTPException

        from backend.api.routes.face_recognition import enroll_from_detection
        from backend.api.schemas.face_recognition import EnrollFromDetectionRequest

        mock_db = AsyncMock()

        mock_person = MagicMock(spec=KnownPerson)
        mock_person.id = 1
        mock_person.name = "John Doe"
        mock_person.embeddings = []

        # Detection exists but is not a person
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 100
        mock_detection.file_path = "/data/images/test_detection.jpg"
        mock_detection.object_type = "car"  # Not a person
        mock_detection.bbox_x = 100
        mock_detection.bbox_y = 50
        mock_detection.bbox_width = 200
        mock_detection.bbox_height = 400

        mock_result_person = MagicMock()
        mock_result_person.scalar_one_or_none.return_value = mock_person
        mock_result_detection = MagicMock()
        mock_result_detection.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.side_effect = [mock_result_person, mock_result_detection]

        request_data = EnrollFromDetectionRequest(detection_id="100")

        with patch(
            "backend.api.routes.face_recognition.extract_face_embedding_from_detection"
        ) as mock_extract:
            # No face found in detection
            mock_extract.return_value = (None, None)

            with pytest.raises(HTTPException) as exc_info:
                await enroll_from_detection(
                    person_id=1,
                    data=request_data,
                    session=mock_db,
                )

        assert exc_info.value.status_code == 400
        assert "face" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_enroll_from_detection_max_embeddings_reached(self) -> None:
        """Test enrollment returns 400 when person has max 10 embeddings."""
        from fastapi import HTTPException

        from backend.api.routes.face_recognition import enroll_from_detection
        from backend.api.schemas.face_recognition import EnrollFromDetectionRequest

        mock_db = AsyncMock()

        # Person already has 10 embeddings
        mock_person = MagicMock(spec=KnownPerson)
        mock_person.id = 1
        mock_person.name = "John Doe"
        mock_person.embeddings = [MagicMock(spec=FaceEmbedding) for _ in range(10)]

        mock_result_person = MagicMock()
        mock_result_person.scalar_one_or_none.return_value = mock_person
        mock_db.execute.return_value = mock_result_person

        request_data = EnrollFromDetectionRequest(detection_id="100")

        with pytest.raises(HTTPException) as exc_info:
            await enroll_from_detection(
                person_id=1,
                data=request_data,
                session=mock_db,
            )

        assert exc_info.value.status_code == 400
        assert "maximum" in exc_info.value.detail.lower() or "10" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_enroll_from_detection_embedding_extraction_failure(self) -> None:
        """Test enrollment returns 500 when embedding extraction fails."""
        from fastapi import HTTPException

        from backend.api.routes.face_recognition import enroll_from_detection
        from backend.api.schemas.face_recognition import EnrollFromDetectionRequest

        mock_db = AsyncMock()

        mock_person = MagicMock(spec=KnownPerson)
        mock_person.id = 1
        mock_person.name = "John Doe"
        mock_person.embeddings = []

        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 100
        mock_detection.file_path = "/data/images/test_detection.jpg"
        mock_detection.object_type = "person"
        mock_detection.bbox_x = 100
        mock_detection.bbox_y = 50
        mock_detection.bbox_width = 200
        mock_detection.bbox_height = 400

        mock_result_person = MagicMock()
        mock_result_person.scalar_one_or_none.return_value = mock_person
        mock_result_detection = MagicMock()
        mock_result_detection.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.side_effect = [mock_result_person, mock_result_detection]

        request_data = EnrollFromDetectionRequest(detection_id="100")

        with patch(
            "backend.api.routes.face_recognition.extract_face_embedding_from_detection"
        ) as mock_extract:
            mock_extract.side_effect = RuntimeError("Model not available")

            with pytest.raises(HTTPException) as exc_info:
                await enroll_from_detection(
                    person_id=1,
                    data=request_data,
                    session=mock_db,
                )

        assert exc_info.value.status_code == 500
        assert (
            "embedding" in exc_info.value.detail.lower()
            or "extraction" in exc_info.value.detail.lower()
        )


class TestEnrollFromDetectionSchemas:
    """Tests for EnrollFromDetection request/response schemas."""

    def test_request_schema_valid(self) -> None:
        """Test EnrollFromDetectionRequest accepts valid data."""
        from backend.api.schemas.face_recognition import EnrollFromDetectionRequest

        request = EnrollFromDetectionRequest(detection_id="123")
        assert request.detection_id == "123"

    def test_request_schema_detection_id_required(self) -> None:
        """Test EnrollFromDetectionRequest requires detection_id."""
        from pydantic import ValidationError

        from backend.api.schemas.face_recognition import EnrollFromDetectionRequest

        with pytest.raises(ValidationError):
            EnrollFromDetectionRequest()  # type: ignore[call-arg]

    def test_response_schema_success_no_warning(self) -> None:
        """Test EnrollFromDetectionResponse for successful enrollment."""
        from backend.api.schemas.face_recognition import EnrollFromDetectionResponse

        response = EnrollFromDetectionResponse(
            success=True,
            embedding_id=1,
            quality_score=0.92,
            warning=None,
        )
        assert response.success is True
        assert response.embedding_id == 1
        assert response.quality_score == 0.92
        assert response.warning is None

    def test_response_schema_success_with_warning(self) -> None:
        """Test EnrollFromDetectionResponse with quality warning."""
        from backend.api.schemas.face_recognition import EnrollFromDetectionResponse

        response = EnrollFromDetectionResponse(
            success=True,
            embedding_id=2,
            quality_score=0.75,
            warning="Face quality is moderate (0.75). Consider adding higher quality images.",
        )
        assert response.success is True
        assert response.quality_score == 0.75
        assert response.warning is not None


# =============================================================================
# Face Event Identify Endpoint Tests (NEM-4688 Phase 2)
# =============================================================================


class TestIdentifyFaceEvent:
    """Tests for POST /api/face-events/{event_id}/identify endpoint."""

    @pytest.mark.asyncio
    async def test_identify_face_event_success(self) -> None:
        """Test successfully identifying an unknown face as a known person."""
        from backend.api.routes.face_recognition import identify_face_event
        from backend.api.schemas.face_recognition import (
            IdentifyFaceEventRequest,
            IdentifyFaceEventResponse,
        )

        mock_db = AsyncMock()
        mock_service = MagicMock()

        # Mock service method to return success result
        mock_service.identify_face_event = AsyncMock(
            return_value={
                "success": True,
                "created_embedding": False,
            }
        )

        request = IdentifyFaceEventRequest(known_person_id=1)

        with patch(
            "backend.api.routes.face_recognition.get_face_recognition_service",
            return_value=mock_service,
        ):
            result = await identify_face_event(
                event_id=100,
                data=request,
                session=mock_db,
            )

        assert isinstance(result, IdentifyFaceEventResponse)
        assert result.success is True
        assert result.created_embedding is False
        mock_service.identify_face_event.assert_called_once_with(
            mock_db, event_id=100, known_person_id=1
        )

    @pytest.mark.asyncio
    async def test_identify_face_event_with_embedding_creation(self) -> None:
        """Test identifying a face and creating an embedding when quality >= 0.7."""
        from backend.api.routes.face_recognition import identify_face_event
        from backend.api.schemas.face_recognition import (
            IdentifyFaceEventRequest,
            IdentifyFaceEventResponse,
        )

        mock_db = AsyncMock()
        mock_service = MagicMock()

        # Mock service method to return success with embedding created
        mock_service.identify_face_event = AsyncMock(
            return_value={
                "success": True,
                "created_embedding": True,
            }
        )

        request = IdentifyFaceEventRequest(known_person_id=1)

        with patch(
            "backend.api.routes.face_recognition.get_face_recognition_service",
            return_value=mock_service,
        ):
            result = await identify_face_event(
                event_id=100,
                data=request,
                session=mock_db,
            )

        assert isinstance(result, IdentifyFaceEventResponse)
        assert result.success is True
        assert result.created_embedding is True

    @pytest.mark.asyncio
    async def test_identify_face_event_not_found(self) -> None:
        """Test identify returns 404 if face event doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.face_recognition import identify_face_event
        from backend.api.schemas.face_recognition import IdentifyFaceEventRequest

        mock_db = AsyncMock()
        mock_service = MagicMock()

        # Mock service to raise exception for non-existent event
        mock_service.identify_face_event = AsyncMock(
            side_effect=ValueError("Face event with id 999 not found")
        )

        request = IdentifyFaceEventRequest(known_person_id=1)

        with patch(
            "backend.api.routes.face_recognition.get_face_recognition_service",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await identify_face_event(
                    event_id=999,
                    data=request,
                    session=mock_db,
                )

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_identify_face_event_known_person_not_found(self) -> None:
        """Test identify returns 404 if known person doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.face_recognition import identify_face_event
        from backend.api.schemas.face_recognition import IdentifyFaceEventRequest

        mock_db = AsyncMock()
        mock_service = MagicMock()

        # Mock service to raise exception for non-existent person
        mock_service.identify_face_event = AsyncMock(
            side_effect=ValueError("Known person with id 999 not found")
        )

        request = IdentifyFaceEventRequest(known_person_id=999)

        with patch(
            "backend.api.routes.face_recognition.get_face_recognition_service",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await identify_face_event(
                    event_id=100,
                    data=request,
                    session=mock_db,
                )

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_identify_face_event_already_identified(self) -> None:
        """Test identify returns 400 if face event is already identified (not unknown)."""
        from fastapi import HTTPException

        from backend.api.routes.face_recognition import identify_face_event
        from backend.api.schemas.face_recognition import IdentifyFaceEventRequest

        mock_db = AsyncMock()
        mock_service = MagicMock()

        # Mock service to raise exception for already identified event
        mock_service.identify_face_event = AsyncMock(
            side_effect=ValueError("Face event 100 is already identified")
        )

        request = IdentifyFaceEventRequest(known_person_id=1)

        with patch(
            "backend.api.routes.face_recognition.get_face_recognition_service",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await identify_face_event(
                    event_id=100,
                    data=request,
                    session=mock_db,
                )

        assert exc_info.value.status_code == 400
        assert "already identified" in exc_info.value.detail.lower()


class TestIdentifyFaceEventSchema:
    """Tests for IdentifyFaceEventRequest and IdentifyFaceEventResponse schemas."""

    def test_request_schema_valid(self) -> None:
        """Test creating a valid request schema."""
        from backend.api.schemas.face_recognition import IdentifyFaceEventRequest

        request = IdentifyFaceEventRequest(known_person_id=1)
        assert request.known_person_id == 1

    def test_request_schema_requires_known_person_id(self) -> None:
        """Test that known_person_id is required."""
        from pydantic import ValidationError

        from backend.api.schemas.face_recognition import IdentifyFaceEventRequest

        with pytest.raises(ValidationError):
            IdentifyFaceEventRequest()  # type: ignore[call-arg]

    def test_response_schema_valid(self) -> None:
        """Test creating a valid response schema."""
        from backend.api.schemas.face_recognition import IdentifyFaceEventResponse

        response = IdentifyFaceEventResponse(success=True, created_embedding=False)
        assert response.success is True
        assert response.created_embedding is False

    def test_response_schema_defaults(self) -> None:
        """Test response schema with explicit values."""
        from backend.api.schemas.face_recognition import IdentifyFaceEventResponse

        response = IdentifyFaceEventResponse(success=True, created_embedding=True)
        assert response.success is True
        assert response.created_embedding is True


class TestIdentifyFaceEventService:
    """Tests for the FaceRecognitionService.identify_face_event method."""

    @pytest.mark.asyncio
    async def test_service_identify_face_event_success(self) -> None:
        """Test service method successfully identifies an unknown face."""
        from backend.services.face_recognition_service import FaceRecognitionService

        service = FaceRecognitionService()
        mock_db = AsyncMock()

        # Mock face event - unknown with low quality (no embedding creation)
        mock_event = MagicMock(spec=FaceDetectionEvent)
        mock_event.id = 100
        mock_event.is_unknown = True
        mock_event.quality_score = 0.5  # Below 0.7 threshold
        mock_event.embedding = np.zeros(512, dtype=np.float32).tobytes()

        # Mock known person
        mock_person = MagicMock(spec=KnownPerson)
        mock_person.id = 1
        mock_person.name = "John Doe"

        # Setup mock query results
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_person_result = MagicMock()
        mock_person_result.scalar_one_or_none.return_value = mock_person

        mock_db.execute.side_effect = [mock_event_result, mock_person_result]

        result = await service.identify_face_event(mock_db, event_id=100, known_person_id=1)

        assert result["success"] is True
        assert result["created_embedding"] is False
        assert mock_event.matched_person_id == 1
        assert mock_event.is_unknown is False
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_identify_face_event_creates_embedding(self) -> None:
        """Test service creates embedding when quality >= 0.7."""
        from backend.services.face_recognition_service import FaceRecognitionService

        service = FaceRecognitionService()
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        # Mock face event - unknown with high quality
        mock_event = MagicMock(spec=FaceDetectionEvent)
        mock_event.id = 100
        mock_event.is_unknown = True
        mock_event.quality_score = 0.85  # Above 0.7 threshold
        mock_event.embedding = np.zeros(512, dtype=np.float32).tobytes()

        # Mock known person
        mock_person = MagicMock(spec=KnownPerson)
        mock_person.id = 1
        mock_person.name = "John Doe"

        # Setup mock query results
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_person_result = MagicMock()
        mock_person_result.scalar_one_or_none.return_value = mock_person

        mock_db.execute.side_effect = [mock_event_result, mock_person_result]

        result = await service.identify_face_event(mock_db, event_id=100, known_person_id=1)

        assert result["success"] is True
        assert result["created_embedding"] is True
        assert mock_event.matched_person_id == 1
        assert mock_event.is_unknown is False
        # Verify embedding was added
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_identify_face_event_not_found(self) -> None:
        """Test service raises ValueError when face event not found."""
        from backend.services.face_recognition_service import FaceRecognitionService

        service = FaceRecognitionService()
        mock_db = AsyncMock()

        # Mock query returns None for event
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError) as exc_info:
            await service.identify_face_event(mock_db, event_id=999, known_person_id=1)

        assert "Face event with id 999 not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_service_identify_face_event_known_person_not_found(self) -> None:
        """Test service raises ValueError when known person not found."""
        from backend.services.face_recognition_service import FaceRecognitionService

        service = FaceRecognitionService()
        mock_db = AsyncMock()

        # Mock face event exists
        mock_event = MagicMock(spec=FaceDetectionEvent)
        mock_event.id = 100
        mock_event.is_unknown = True

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        # Mock known person not found
        mock_person_result = MagicMock()
        mock_person_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_event_result, mock_person_result]

        with pytest.raises(ValueError) as exc_info:
            await service.identify_face_event(mock_db, event_id=100, known_person_id=999)

        assert "Known person with id 999 not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_service_identify_face_event_already_identified(self) -> None:
        """Test service raises ValueError when face is already identified."""
        from backend.services.face_recognition_service import FaceRecognitionService

        service = FaceRecognitionService()
        mock_db = AsyncMock()

        # Mock face event that is already identified
        mock_event = MagicMock(spec=FaceDetectionEvent)
        mock_event.id = 100
        mock_event.is_unknown = False  # Already identified
        mock_event.matched_person_id = 2

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError) as exc_info:
            await service.identify_face_event(mock_db, event_id=100, known_person_id=1)

        assert "Face event 100 is already identified" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_service_identify_face_event_quality_threshold(self) -> None:
        """Test service correctly applies 0.7 quality threshold for embedding creation."""
        from backend.services.face_recognition_service import FaceRecognitionService

        service = FaceRecognitionService()

        # Test quality exactly at threshold (0.7) - should create embedding
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        mock_event = MagicMock(spec=FaceDetectionEvent)
        mock_event.id = 100
        mock_event.is_unknown = True
        mock_event.quality_score = 0.7  # Exactly at threshold
        mock_event.embedding = np.zeros(512, dtype=np.float32).tobytes()

        mock_person = MagicMock(spec=KnownPerson)
        mock_person.id = 1
        mock_person.name = "John Doe"

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event
        mock_person_result = MagicMock()
        mock_person_result.scalar_one_or_none.return_value = mock_person

        mock_db.execute.side_effect = [mock_event_result, mock_person_result]

        result = await service.identify_face_event(mock_db, event_id=100, known_person_id=1)

        assert result["created_embedding"] is True

    @pytest.mark.asyncio
    async def test_service_identify_face_event_quality_below_threshold(self) -> None:
        """Test service does not create embedding when quality < 0.7."""
        from backend.services.face_recognition_service import FaceRecognitionService

        service = FaceRecognitionService()
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        mock_event = MagicMock(spec=FaceDetectionEvent)
        mock_event.id = 100
        mock_event.is_unknown = True
        mock_event.quality_score = 0.69  # Just below threshold
        mock_event.embedding = np.zeros(512, dtype=np.float32).tobytes()

        mock_person = MagicMock(spec=KnownPerson)
        mock_person.id = 1
        mock_person.name = "John Doe"

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event
        mock_person_result = MagicMock()
        mock_person_result.scalar_one_or_none.return_value = mock_person

        mock_db.execute.side_effect = [mock_event_result, mock_person_result]

        result = await service.identify_face_event(mock_db, event_id=100, known_person_id=1)

        assert result["created_embedding"] is False
        mock_db.add.assert_not_called()
