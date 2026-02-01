"""Unit tests for FaceRecognitionService.

Tests the face recognition service methods including:
- get_person_appearances: Get appearance timeline for a known person

Implements NEM-4688 Phase 1: Person Appearances Endpoint

These tests follow TDD methodology.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.camera import Camera
from backend.models.face_identity import FaceDetectionEvent, KnownPerson
from backend.services.face_recognition_service import FaceRecognitionService


class TestGetPersonAppearances:
    """Tests for FaceRecognitionService.get_person_appearances method."""

    @pytest.fixture
    def service(self) -> FaceRecognitionService:
        """Create a FaceRecognitionService instance."""
        return FaceRecognitionService()

    @pytest.mark.asyncio
    async def test_get_appearances_returns_none_for_nonexistent_person(
        self, service: FaceRecognitionService
    ) -> None:
        """Test that get_person_appearances returns None if person doesn't exist."""
        mock_session = AsyncMock()

        # Mock get_known_person to return None
        with patch.object(service, "get_known_person", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            result = await service.get_person_appearances(mock_session, person_id=999)

            assert result is None
            mock_get.assert_called_once_with(mock_session, 999)

    @pytest.mark.asyncio
    async def test_get_appearances_returns_empty_for_person_with_no_events(
        self, service: FaceRecognitionService
    ) -> None:
        """Test that get_person_appearances returns empty list if no detection events."""
        mock_session = AsyncMock()

        # Mock person exists
        mock_person = MagicMock(spec=KnownPerson)
        mock_person.id = 1
        mock_person.name = "John Doe"

        # Mock query returns empty result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        # Mock count returns 0
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

        with patch.object(service, "get_known_person", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_person

            result = await service.get_person_appearances(mock_session, person_id=1)

            assert result is not None
            appearances, total = result
            assert appearances == []
            assert total == 0

    @pytest.mark.asyncio
    async def test_get_appearances_returns_correct_structure(
        self, service: FaceRecognitionService
    ) -> None:
        """Test that appearances have correct structure with all fields."""
        mock_session = AsyncMock()

        # Mock person exists
        mock_person = MagicMock(spec=KnownPerson)
        mock_person.id = 1
        mock_person.name = "John Doe"

        # Mock camera
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door Camera"

        # Mock face detection event
        mock_event = MagicMock(spec=FaceDetectionEvent)
        mock_event.id = 100
        mock_event.camera_id = "front_door"
        mock_event.camera = mock_camera
        mock_event.timestamp = datetime(2025, 1, 31, 10, 30, 0, tzinfo=UTC)
        mock_event.match_confidence = 0.95
        mock_event.matched_person_id = 1

        # Mock query returns event
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_event]

        # Mock count returns 1
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

        with patch.object(service, "get_known_person", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_person

            result = await service.get_person_appearances(mock_session, person_id=1)

            assert result is not None
            appearances, total = result
            assert len(appearances) == 1
            assert total == 1

            # Verify appearance structure
            appearance = appearances[0]
            assert appearance["timestamp"] == datetime(2025, 1, 31, 10, 30, 0, tzinfo=UTC)
            assert appearance["camera_id"] == "front_door"
            assert appearance["camera_name"] == "Front Door Camera"
            assert appearance["detection_id"] == 100
            assert appearance["confidence"] == 0.95
            assert "thumbnail_url" in appearance

    @pytest.mark.asyncio
    async def test_get_appearances_uses_camera_id_when_no_camera_relationship(
        self, service: FaceRecognitionService
    ) -> None:
        """Test that camera_name falls back to camera_id when no camera relationship."""
        mock_session = AsyncMock()

        # Mock person exists
        mock_person = MagicMock(spec=KnownPerson)
        mock_person.id = 1

        # Mock face detection event with no camera relationship
        mock_event = MagicMock(spec=FaceDetectionEvent)
        mock_event.id = 100
        mock_event.camera_id = "front_door"
        mock_event.camera = None  # No camera relationship
        mock_event.timestamp = datetime(2025, 1, 31, 10, 0, 0, tzinfo=UTC)
        mock_event.match_confidence = 0.92
        mock_event.matched_person_id = 1

        # Mock query returns event
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_event]

        # Mock count returns 1
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

        with patch.object(service, "get_known_person", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_person

            result = await service.get_person_appearances(mock_session, person_id=1)

            assert result is not None
            appearances, _ = result
            # Should fall back to camera_id
            assert appearances[0]["camera_name"] == "front_door"

    @pytest.mark.asyncio
    async def test_get_appearances_handles_null_confidence(
        self, service: FaceRecognitionService
    ) -> None:
        """Test that appearances handle null match_confidence."""
        mock_session = AsyncMock()

        # Mock person exists
        mock_person = MagicMock(spec=KnownPerson)
        mock_person.id = 1

        # Mock camera
        mock_camera = MagicMock(spec=Camera)
        mock_camera.name = "Test Camera"

        # Mock face detection event with null confidence
        mock_event = MagicMock(spec=FaceDetectionEvent)
        mock_event.id = 100
        mock_event.camera_id = "test"
        mock_event.camera = mock_camera
        mock_event.timestamp = datetime(2025, 1, 31, 10, 0, 0, tzinfo=UTC)
        mock_event.match_confidence = None  # Null confidence
        mock_event.matched_person_id = 1

        # Mock query returns event
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_event]

        # Mock count returns 1
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

        with patch.object(service, "get_known_person", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_person

            result = await service.get_person_appearances(mock_session, person_id=1)

            assert result is not None
            appearances, _ = result
            # Should default to 0.0
            assert appearances[0]["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_get_appearances_returns_total_count_independent_of_limit(
        self, service: FaceRecognitionService
    ) -> None:
        """Test that total_count reflects all matches, not just returned items."""
        mock_session = AsyncMock()

        # Mock person exists
        mock_person = MagicMock(spec=KnownPerson)
        mock_person.id = 1

        # Mock camera
        mock_camera = MagicMock(spec=Camera)
        mock_camera.name = "Test Camera"

        # Mock single event (limit=1)
        mock_event = MagicMock(spec=FaceDetectionEvent)
        mock_event.id = 1
        mock_event.camera_id = "test"
        mock_event.camera = mock_camera
        mock_event.timestamp = datetime(2025, 1, 31, 10, 0, 0, tzinfo=UTC)
        mock_event.match_confidence = 0.9
        mock_event.matched_person_id = 1

        # Mock query returns 1 event (due to limit)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_event]

        # Mock count returns 100 (total matches)
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 100

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

        with patch.object(service, "get_known_person", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_person

            result = await service.get_person_appearances(mock_session, person_id=1, limit=1)

            assert result is not None
            appearances, total = result
            assert len(appearances) == 1  # Only 1 due to limit
            assert total == 100  # Total is all matches
