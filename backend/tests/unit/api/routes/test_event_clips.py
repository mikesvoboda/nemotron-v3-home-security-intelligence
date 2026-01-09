"""Unit tests for event clip API routes.

Tests the clip endpoints:
- GET /api/events/{event_id}/clip
- POST /api/events/{event_id}/clip/generate

These tests follow TDD methodology - written before implementation.
"""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.schemas.clips import (
    ClipGenerateRequest,
    ClipGenerateResponse,
    ClipInfoResponse,
    ClipStatus,
)


class TestGetEventClip:
    """Tests for GET /api/events/{event_id}/clip endpoint."""

    @pytest.mark.asyncio
    async def test_get_clip_event_not_found(self) -> None:
        """Test that clip endpoint returns 404 for non-existent event."""
        from backend.api.routes.events import get_event_clip

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(Exception) as exc_info:
            await get_event_clip(event_id=99999, db=mock_db)

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_clip_not_available(self) -> None:
        """Test clip endpoint returns correct response when no clip exists."""
        from backend.api.routes.events import get_event_clip

        mock_db = AsyncMock()

        # Mock event query - event exists but has no clip
        mock_event = MagicMock()
        mock_event.id = 123
        mock_event.clip_path = None
        mock_event.started_at = datetime.now(UTC)
        mock_event.ended_at = datetime.now(UTC)
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_event_result

        result = await get_event_clip(event_id=123, db=mock_db)

        assert isinstance(result, ClipInfoResponse)
        assert result.event_id == 123
        assert result.clip_available is False
        assert result.clip_url is None
        assert result.duration_seconds is None
        assert result.generated_at is None
        assert result.file_size_bytes is None

    @pytest.mark.asyncio
    async def test_get_clip_available(self) -> None:
        """Test clip endpoint returns clip info when clip exists."""
        from backend.api.routes.events import get_event_clip

        mock_db = AsyncMock()

        # Mock event query - event has a clip
        now = datetime.now(UTC)
        mock_event = MagicMock()
        mock_event.id = 456
        mock_event.clip_path = "/data/clips/456_clip.mp4"
        mock_event.started_at = now
        mock_event.ended_at = now
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_event_result

        # Mock Path class behavior
        mock_path_instance = MagicMock(spec=Path)
        mock_path_instance.exists.return_value = True
        mock_path_instance.name = "456_clip.mp4"
        mock_stat = MagicMock()
        mock_stat.st_size = 5242880  # 5MB
        mock_stat.st_mtime = now.timestamp()
        mock_path_instance.stat.return_value = mock_stat

        with patch("pathlib.Path", return_value=mock_path_instance):
            result = await get_event_clip(event_id=456, db=mock_db)

        assert isinstance(result, ClipInfoResponse)
        assert result.event_id == 456
        assert result.clip_available is True
        assert result.clip_url == "/api/media/clips/456_clip.mp4"
        assert result.file_size_bytes == 5242880
        assert result.generated_at is not None

    @pytest.mark.asyncio
    async def test_get_clip_file_missing(self) -> None:
        """Test clip endpoint handles missing clip file gracefully."""
        from backend.api.routes.events import get_event_clip

        mock_db = AsyncMock()

        # Mock event query - event has clip_path but file doesn't exist
        mock_event = MagicMock()
        mock_event.id = 789
        mock_event.clip_path = "/data/clips/789_clip.mp4"
        mock_event.started_at = datetime.now(UTC)
        mock_event.ended_at = datetime.now(UTC)
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_event_result

        # Mock Path class to return non-existent file
        mock_path_instance = MagicMock(spec=Path)
        mock_path_instance.exists.return_value = False

        with patch("pathlib.Path", return_value=mock_path_instance):
            result = await get_event_clip(event_id=789, db=mock_db)

        # Should return not available since file doesn't exist
        assert isinstance(result, ClipInfoResponse)
        assert result.event_id == 789
        assert result.clip_available is False


class TestGenerateEventClip:
    """Tests for POST /api/events/{event_id}/clip/generate endpoint."""

    @pytest.mark.asyncio
    async def test_generate_clip_event_not_found(self) -> None:
        """Test that generate endpoint returns 404 for non-existent event."""
        from fastapi import Response

        from backend.api.routes.events import generate_event_clip

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        request = ClipGenerateRequest()
        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}

        with pytest.raises(Exception) as exc_info:
            await generate_event_clip(
                event_id=99999, request=request, response=mock_response, db=mock_db
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_generate_clip_already_exists(self) -> None:
        """Test generate endpoint returns existing clip info without regenerating."""
        from fastapi import Response, status

        from backend.api.routes.events import generate_event_clip

        mock_db = AsyncMock()

        # Mock event query - event already has a clip
        now = datetime.now(UTC)
        mock_event = MagicMock()
        mock_event.id = 123
        mock_event.clip_path = "/data/clips/123_clip.mp4"
        mock_event.started_at = now
        mock_event.ended_at = now
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_event_result

        # Mock clip file exists
        mock_path_instance = MagicMock(spec=Path)
        mock_path_instance.exists.return_value = True
        mock_path_instance.name = "123_clip.mp4"
        mock_stat = MagicMock()
        mock_stat.st_size = 5242880
        mock_stat.st_mtime = now.timestamp()
        mock_path_instance.stat.return_value = mock_stat

        request = ClipGenerateRequest()
        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}

        with patch("pathlib.Path", return_value=mock_path_instance):
            result = await generate_event_clip(
                event_id=123, request=request, response=mock_response, db=mock_db
            )

        assert isinstance(result, ClipGenerateResponse)
        assert result.event_id == 123
        assert result.status == ClipStatus.COMPLETED
        assert result.clip_url == "/api/media/clips/123_clip.mp4"
        # When clip already exists, should return 200 OK (not 201 Created)
        assert mock_response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_generate_clip_triggers_generation(self) -> None:
        """Test generate endpoint triggers clip generation for event without clip."""
        from fastapi import Response

        from backend.api.routes.events import generate_event_clip

        mock_db = AsyncMock()

        # Mock event query - event has no clip
        now = datetime.now(UTC)
        mock_event = MagicMock()
        mock_event.id = 456
        mock_event.clip_path = None
        mock_event.started_at = now
        mock_event.ended_at = now
        mock_event.detection_ids = "[1, 2, 3]"
        mock_event.detection_id_list = [1, 2, 3]  # Property used by the route
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_db.execute = AsyncMock(return_value=mock_event_result)

        request = ClipGenerateRequest(
            start_offset_seconds=-15,
            end_offset_seconds=30,
        )
        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}

        # Mock clip generator
        mock_clip_path = MagicMock(spec=Path)
        mock_clip_path.name = "456_clip.mp4"
        mock_clip_stat = MagicMock()
        mock_clip_stat.st_mtime = now.timestamp()
        mock_clip_path.stat.return_value = mock_clip_stat

        mock_generator = MagicMock()
        mock_generator.generate_clip_from_images = AsyncMock(return_value=mock_clip_path)

        # Mock batch_fetch_file_paths to return detection image paths
        with (
            patch(
                "backend.services.clip_generator.get_clip_generator",
                return_value=mock_generator,
            ),
            patch(
                "backend.api.routes.events.batch_fetch_file_paths",
                return_value=["/path/to/image1.jpg", "/path/to/image2.jpg", "/path/to/image3.jpg"],
            ),
        ):
            result = await generate_event_clip(
                event_id=456, request=request, response=mock_response, db=mock_db
            )

        assert isinstance(result, ClipGenerateResponse)
        assert result.event_id == 456
        # Since generation is async, it may return COMPLETED
        assert result.status == ClipStatus.COMPLETED
        # New clip created should have Location header set
        assert mock_response.headers.get("Location") == "/api/media/clips/456_clip.mp4"

    @pytest.mark.asyncio
    async def test_generate_clip_with_force_regenerate(self) -> None:
        """Test generate endpoint regenerates clip when force=True."""
        from fastapi import Response

        from backend.api.routes.events import generate_event_clip

        mock_db = AsyncMock()

        # Mock event query - event has existing clip
        now = datetime.now(UTC)
        mock_event = MagicMock()
        mock_event.id = 789
        mock_event.clip_path = "/data/clips/789_clip.mp4"
        mock_event.started_at = now
        mock_event.ended_at = now
        mock_event.detection_ids = "[1, 2]"
        mock_event.detection_id_list = [1, 2]  # Property used by the route
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_db.execute = AsyncMock(return_value=mock_event_result)

        request = ClipGenerateRequest(force=True)
        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}

        # Mock clip generator
        mock_clip_path = MagicMock(spec=Path)
        mock_clip_path.name = "789_clip.mp4"
        mock_clip_stat = MagicMock()
        mock_clip_stat.st_mtime = now.timestamp()
        mock_clip_path.stat.return_value = mock_clip_stat

        mock_generator = MagicMock()
        mock_generator.generate_clip_from_images = AsyncMock(return_value=mock_clip_path)
        mock_generator.delete_clip = MagicMock(return_value=True)

        # Mock batch_fetch_file_paths to return detection image paths
        with (
            patch(
                "backend.services.clip_generator.get_clip_generator",
                return_value=mock_generator,
            ),
            patch(
                "backend.api.routes.events.batch_fetch_file_paths",
                return_value=["/path/to/image1.jpg", "/path/to/image2.jpg"],
            ),
        ):
            result = await generate_event_clip(
                event_id=789, request=request, response=mock_response, db=mock_db
            )

        # Should trigger regeneration
        mock_generator.generate_clip_from_images.assert_called_once()
        assert isinstance(result, ClipGenerateResponse)

    @pytest.mark.asyncio
    async def test_generate_clip_no_detections(self) -> None:
        """Test generate endpoint handles event with no detections."""
        from fastapi import Response

        from backend.api.routes.events import generate_event_clip

        mock_db = AsyncMock()

        # Mock event query - event has no detections
        mock_event = MagicMock()
        mock_event.id = 111
        mock_event.clip_path = None
        mock_event.started_at = datetime.now(UTC)
        mock_event.ended_at = datetime.now(UTC)
        mock_event.detection_ids = None
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_event_result

        request = ClipGenerateRequest()
        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}

        with pytest.raises(Exception) as exc_info:
            await generate_event_clip(
                event_id=111, request=request, response=mock_response, db=mock_db
            )

        # Should return error - no source material for clip
        assert exc_info.value.status_code == 400
        assert "detection" in str(exc_info.value.detail).lower()


class TestClipSchemas:
    """Tests for clip Pydantic schemas."""

    def test_clip_info_response_no_clip(self) -> None:
        """Test ClipInfoResponse schema for event without clip."""
        response = ClipInfoResponse(
            event_id=123,
            clip_available=False,
            clip_url=None,
            duration_seconds=None,
            generated_at=None,
            file_size_bytes=None,
        )
        assert response.event_id == 123
        assert response.clip_available is False
        assert response.clip_url is None

    def test_clip_info_response_with_clip(self) -> None:
        """Test ClipInfoResponse schema for event with clip."""
        now = datetime.now(UTC)
        response = ClipInfoResponse(
            event_id=456,
            clip_available=True,
            clip_url="/api/media/clips/456_clip.mp4",
            duration_seconds=30,
            generated_at=now,
            file_size_bytes=5242880,
        )
        assert response.event_id == 456
        assert response.clip_available is True
        assert response.clip_url == "/api/media/clips/456_clip.mp4"
        assert response.duration_seconds == 30
        assert response.file_size_bytes == 5242880

    def test_clip_generate_request_defaults(self) -> None:
        """Test ClipGenerateRequest schema with default values."""
        request = ClipGenerateRequest()
        assert request.start_offset_seconds == -15
        assert request.end_offset_seconds == 30
        assert request.force is False

    def test_clip_generate_request_custom_values(self) -> None:
        """Test ClipGenerateRequest schema with custom values."""
        request = ClipGenerateRequest(
            start_offset_seconds=-30,
            end_offset_seconds=60,
            force=True,
        )
        assert request.start_offset_seconds == -30
        assert request.end_offset_seconds == 60
        assert request.force is True

    def test_clip_generate_request_validation(self) -> None:
        """Test ClipGenerateRequest validates offset bounds (NEM-1355).

        Updated to use new bounds: -30 to 3600 seconds.
        """
        # Valid boundary values
        request = ClipGenerateRequest(
            start_offset_seconds=-30,
            end_offset_seconds=3600,
        )
        assert request.start_offset_seconds == -30
        assert request.end_offset_seconds == 3600

        # Invalid values should raise
        with pytest.raises(ValueError):
            ClipGenerateRequest(start_offset_seconds=-31)  # Below minimum

        with pytest.raises(ValueError):
            ClipGenerateRequest(end_offset_seconds=3601)  # Above maximum


class TestClipGenerateRequestOffsetValidation:
    """Tests for ClipGenerateRequest offset validation (NEM-1355).

    Requirements:
    - start_offset_seconds: no less than -30, no more than 3600
    - end_offset_seconds: no less than -30, no more than 3600
    - end >= start (cross-field validation)
    """

    def test_offset_minimum_boundary_minus_30(self) -> None:
        """Test that offset values accept -30 as minimum."""
        request = ClipGenerateRequest(
            start_offset_seconds=-30,
            end_offset_seconds=30,
        )
        assert request.start_offset_seconds == -30

    def test_offset_maximum_boundary_3600(self) -> None:
        """Test that offset values accept 3600 as maximum."""
        request = ClipGenerateRequest(
            start_offset_seconds=-15,
            end_offset_seconds=3600,
        )
        assert request.end_offset_seconds == 3600

    def test_offset_rejects_below_minus_30(self) -> None:
        """Test that start_offset_seconds below -30 is rejected."""
        with pytest.raises(ValueError) as exc_info:
            ClipGenerateRequest(start_offset_seconds=-31, end_offset_seconds=30)

        error_message = str(exc_info.value).lower()
        assert "-30" in error_message or "greater" in error_message or "minimum" in error_message

    def test_offset_rejects_above_3600(self) -> None:
        """Test that end_offset_seconds above 3600 is rejected."""
        with pytest.raises(ValueError) as exc_info:
            ClipGenerateRequest(start_offset_seconds=-15, end_offset_seconds=3601)

        error_message = str(exc_info.value).lower()
        assert "3600" in error_message or "less" in error_message or "maximum" in error_message

    def test_end_offset_must_be_greater_than_or_equal_to_start(self) -> None:
        """Test that end_offset_seconds >= start_offset_seconds."""
        # Valid: end > start
        request = ClipGenerateRequest(
            start_offset_seconds=-15,
            end_offset_seconds=30,
        )
        assert request.end_offset_seconds > request.start_offset_seconds

        # Valid: end == start (edge case - zero duration)
        request = ClipGenerateRequest(
            start_offset_seconds=0,
            end_offset_seconds=0,
        )
        assert request.end_offset_seconds == request.start_offset_seconds

    def test_end_before_start_is_rejected(self) -> None:
        """Test that end_offset_seconds < start_offset_seconds is rejected."""
        with pytest.raises(ValueError) as exc_info:
            ClipGenerateRequest(
                start_offset_seconds=30,
                end_offset_seconds=10,
            )

        error_message = str(exc_info.value).lower()
        assert (
            ("end" in error_message and "start" in error_message)
            or "greater" in error_message
            or "before" in error_message
        )

    def test_valid_range_zero_to_3600(self) -> None:
        """Test that a valid range from 0 to 3600 is accepted."""
        request = ClipGenerateRequest(
            start_offset_seconds=0,
            end_offset_seconds=3600,
        )
        assert request.start_offset_seconds == 0
        assert request.end_offset_seconds == 3600

    def test_valid_negative_to_positive_range(self) -> None:
        """Test that a valid range from negative to positive is accepted."""
        request = ClipGenerateRequest(
            start_offset_seconds=-30,
            end_offset_seconds=3600,
        )
        assert request.start_offset_seconds == -30
        assert request.end_offset_seconds == 3600

    def test_error_message_for_invalid_start_offset_is_helpful(self) -> None:
        """Test that error message for invalid start_offset is helpful."""
        with pytest.raises(ValueError) as exc_info:
            ClipGenerateRequest(start_offset_seconds=-100, end_offset_seconds=30)

        error_message = str(exc_info.value)
        # Should mention the limit
        assert "-30" in error_message

    def test_error_message_for_invalid_end_offset_is_helpful(self) -> None:
        """Test that error message for invalid end_offset is helpful."""
        with pytest.raises(ValueError) as exc_info:
            ClipGenerateRequest(start_offset_seconds=-15, end_offset_seconds=4000)

        error_message = str(exc_info.value)
        # Should mention the limit
        assert "3600" in error_message

    def test_error_message_for_end_before_start_is_helpful(self) -> None:
        """Test that error message for end < start is helpful."""
        with pytest.raises(ValueError) as exc_info:
            ClipGenerateRequest(
                start_offset_seconds=100,
                end_offset_seconds=50,
            )

        error_message = str(exc_info.value).lower()
        # Should explain the relationship requirement
        assert "end" in error_message or "start" in error_message or "greater" in error_message

    def test_clip_generate_response_pending(self) -> None:
        """Test ClipGenerateResponse schema for pending generation."""
        response = ClipGenerateResponse(
            event_id=123,
            status=ClipStatus.PENDING,
            message="Clip generation queued",
        )
        assert response.event_id == 123
        assert response.status == ClipStatus.PENDING
        assert response.clip_url is None

    def test_clip_generate_response_completed(self) -> None:
        """Test ClipGenerateResponse schema for completed generation."""
        now = datetime.now(UTC)
        response = ClipGenerateResponse(
            event_id=456,
            status=ClipStatus.COMPLETED,
            clip_url="/api/media/clips/456_clip.mp4",
            generated_at=now,
            message="Clip generated successfully",
        )
        assert response.event_id == 456
        assert response.status == ClipStatus.COMPLETED
        assert response.clip_url == "/api/media/clips/456_clip.mp4"

    def test_clip_status_enum_values(self) -> None:
        """Test ClipStatus enum has expected values."""
        assert ClipStatus.PENDING.value == "pending"
        assert ClipStatus.COMPLETED.value == "completed"
        assert ClipStatus.FAILED.value == "failed"
