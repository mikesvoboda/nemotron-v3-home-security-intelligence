"""Unit tests for backend.api.routes.detections endpoints.

These tests cover all routes in the detections API:
- GET /api/detections - List detections with filtering and pagination
- GET /api/detections/{detection_id} - Get a specific detection
- GET /api/detections/{detection_id}/image - Get detection image with bounding box
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from fastapi import HTTPException

from backend.api.routes import detections as detections_routes
from backend.models.detection import Detection


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_detection() -> MagicMock:
    """Create a mock Detection object."""
    detection = MagicMock(spec=Detection)
    detection.id = 1
    detection.camera_id = "camera-001"
    detection.file_path = "/export/foscam/front_door/20251223_120000.jpg"
    detection.file_type = "image/jpeg"
    detection.detected_at = datetime(2025, 12, 23, 12, 0, 0)
    detection.object_type = "person"
    detection.confidence = 0.95
    detection.bbox_x = 100
    detection.bbox_y = 150
    detection.bbox_width = 200
    detection.bbox_height = 400
    detection.thumbnail_path = "/data/thumbnails/1_thumb.jpg"
    return detection


@pytest.fixture
def mock_detection_no_thumbnail() -> MagicMock:
    """Create a mock Detection object without thumbnail."""
    detection = MagicMock(spec=Detection)
    detection.id = 2
    detection.camera_id = "camera-002"
    detection.file_path = "/export/foscam/back_door/20251223_120100.jpg"
    detection.file_type = "image/jpeg"
    detection.detected_at = datetime(2025, 12, 23, 12, 1, 0)
    detection.object_type = "car"
    detection.confidence = 0.88
    detection.bbox_x = 50
    detection.bbox_y = 75
    detection.bbox_width = 300
    detection.bbox_height = 200
    detection.thumbnail_path = None
    return detection


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    return AsyncMock()


# =============================================================================
# list_detections Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_detections_no_filters(mock_db_session: AsyncMock, mock_detection: MagicMock) -> None:
    """Test listing detections without any filters."""
    # Setup mock
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection]
    mock_result.scalars.return_value = mock_scalars

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1

    mock_db_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    # Execute
    result = await detections_routes.list_detections(
        camera_id=None,
        object_type=None,
        start_date=None,
        end_date=None,
        min_confidence=None,
        limit=50,
        offset=0,
        db=mock_db_session,
    )

    # Verify
    assert result["count"] == 1
    assert result["limit"] == 50
    assert result["offset"] == 0
    assert len(result["detections"]) == 1
    assert result["detections"][0] == mock_detection


@pytest.mark.asyncio
async def test_list_detections_with_camera_filter(mock_db_session: AsyncMock, mock_detection: MagicMock) -> None:
    """Test listing detections filtered by camera_id."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection]
    mock_result.scalars.return_value = mock_scalars

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1

    mock_db_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    result = await detections_routes.list_detections(
        camera_id="camera-001",
        object_type=None,
        start_date=None,
        end_date=None,
        min_confidence=None,
        limit=50,
        offset=0,
        db=mock_db_session,
    )

    assert result["count"] == 1
    assert result["detections"][0].camera_id == "camera-001"


@pytest.mark.asyncio
async def test_list_detections_with_object_type_filter(mock_db_session: AsyncMock, mock_detection: MagicMock) -> None:
    """Test listing detections filtered by object_type."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection]
    mock_result.scalars.return_value = mock_scalars

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1

    mock_db_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    result = await detections_routes.list_detections(
        camera_id=None,
        object_type="person",
        start_date=None,
        end_date=None,
        min_confidence=None,
        limit=50,
        offset=0,
        db=mock_db_session,
    )

    assert result["count"] == 1
    assert result["detections"][0].object_type == "person"


@pytest.mark.asyncio
async def test_list_detections_with_date_range_filter(mock_db_session: AsyncMock, mock_detection: MagicMock) -> None:
    """Test listing detections filtered by date range."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection]
    mock_result.scalars.return_value = mock_scalars

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1

    mock_db_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    start_date = datetime(2025, 12, 23, 0, 0, 0)
    end_date = datetime(2025, 12, 23, 23, 59, 59)

    result = await detections_routes.list_detections(
        camera_id=None,
        object_type=None,
        start_date=start_date,
        end_date=end_date,
        min_confidence=None,
        limit=50,
        offset=0,
        db=mock_db_session,
    )

    assert result["count"] == 1


@pytest.mark.asyncio
async def test_list_detections_with_confidence_filter(mock_db_session: AsyncMock, mock_detection: MagicMock) -> None:
    """Test listing detections filtered by minimum confidence."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection]
    mock_result.scalars.return_value = mock_scalars

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1

    mock_db_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    result = await detections_routes.list_detections(
        camera_id=None,
        object_type=None,
        start_date=None,
        end_date=None,
        min_confidence=0.9,
        limit=50,
        offset=0,
        db=mock_db_session,
    )

    assert result["count"] == 1
    assert result["detections"][0].confidence >= 0.9


@pytest.mark.asyncio
async def test_list_detections_with_all_filters(mock_db_session: AsyncMock, mock_detection: MagicMock) -> None:
    """Test listing detections with all filters applied."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection]
    mock_result.scalars.return_value = mock_scalars

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1

    mock_db_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    result = await detections_routes.list_detections(
        camera_id="camera-001",
        object_type="person",
        start_date=datetime(2025, 12, 23, 0, 0, 0),
        end_date=datetime(2025, 12, 23, 23, 59, 59),
        min_confidence=0.9,
        limit=50,
        offset=0,
        db=mock_db_session,
    )

    assert result["count"] == 1


@pytest.mark.asyncio
async def test_list_detections_with_pagination(mock_db_session: AsyncMock, mock_detection: MagicMock) -> None:
    """Test listing detections with pagination."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection]
    mock_result.scalars.return_value = mock_scalars

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 100  # Total count is higher than returned

    mock_db_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    result = await detections_routes.list_detections(
        camera_id=None,
        object_type=None,
        start_date=None,
        end_date=None,
        min_confidence=None,
        limit=10,
        offset=20,
        db=mock_db_session,
    )

    assert result["count"] == 100
    assert result["limit"] == 10
    assert result["offset"] == 20


@pytest.mark.asyncio
async def test_list_detections_empty_result(mock_db_session: AsyncMock) -> None:
    """Test listing detections when no results match."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 0

    mock_db_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    result = await detections_routes.list_detections(
        camera_id=None,
        object_type=None,
        start_date=None,
        end_date=None,
        min_confidence=None,
        limit=50,
        offset=0,
        db=mock_db_session,
    )

    assert result["count"] == 0
    assert result["detections"] == []


@pytest.mark.asyncio
async def test_list_detections_count_returns_none(mock_db_session: AsyncMock) -> None:
    """Test listing detections when count query returns None."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = None  # COUNT returns None

    mock_db_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    result = await detections_routes.list_detections(
        camera_id=None,
        object_type=None,
        start_date=None,
        end_date=None,
        min_confidence=None,
        limit=50,
        offset=0,
        db=mock_db_session,
    )

    assert result["count"] == 0  # Should default to 0 when None


@pytest.mark.asyncio
async def test_list_detections_multiple_results(mock_db_session: AsyncMock) -> None:
    """Test listing detections with multiple results."""
    detection1 = MagicMock(spec=Detection)
    detection1.id = 1
    detection1.camera_id = "camera-001"
    detection1.detected_at = datetime(2025, 12, 23, 12, 0, 0)

    detection2 = MagicMock(spec=Detection)
    detection2.id = 2
    detection2.camera_id = "camera-002"
    detection2.detected_at = datetime(2025, 12, 23, 12, 1, 0)

    detection3 = MagicMock(spec=Detection)
    detection3.id = 3
    detection3.camera_id = "camera-001"
    detection3.detected_at = datetime(2025, 12, 23, 12, 2, 0)

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [detection3, detection2, detection1]  # Newest first
    mock_result.scalars.return_value = mock_scalars

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 3

    mock_db_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    result = await detections_routes.list_detections(
        camera_id=None,
        object_type=None,
        start_date=None,
        end_date=None,
        min_confidence=None,
        limit=50,
        offset=0,
        db=mock_db_session,
    )

    assert result["count"] == 3
    assert len(result["detections"]) == 3


# =============================================================================
# get_detection Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_detection_success(mock_db_session: AsyncMock, mock_detection: MagicMock) -> None:
    """Test getting a detection by ID successfully."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_detection
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    result = await detections_routes.get_detection(detection_id=1, db=mock_db_session)

    assert result == mock_detection
    assert result.id == 1


@pytest.mark.asyncio
async def test_get_detection_not_found(mock_db_session: AsyncMock) -> None:
    """Test getting a detection that doesn't exist."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc_info:
        await detections_routes.get_detection(detection_id=999, db=mock_db_session)

    assert exc_info.value.status_code == 404
    assert "Detection with id 999 not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_detection_various_ids(mock_db_session: AsyncMock, mock_detection: MagicMock) -> None:
    """Test getting detections with various ID values."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_detection
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Test with different valid IDs
    for detection_id in [1, 10, 100, 1000]:
        mock_detection.id = detection_id
        result = await detections_routes.get_detection(detection_id=detection_id, db=mock_db_session)
        assert result.id == detection_id


# =============================================================================
# get_detection_image Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_detection_image_with_existing_thumbnail(
    mock_db_session: AsyncMock, mock_detection: MagicMock
) -> None:
    """Test getting detection image when thumbnail already exists."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_detection
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    image_data = b"\xff\xd8\xff\xe0fake_jpeg_data"

    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=image_data)),
    ):
        result = await detections_routes.get_detection_image(detection_id=1, db=mock_db_session)

    assert result.status_code == 200
    assert result.media_type == "image/jpeg"
    assert result.body == image_data
    assert result.headers["Cache-Control"] == "public, max-age=3600"


@pytest.mark.asyncio
async def test_get_detection_image_not_found(mock_db_session: AsyncMock) -> None:
    """Test getting detection image when detection doesn't exist."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc_info:
        await detections_routes.get_detection_image(detection_id=999, db=mock_db_session)

    assert exc_info.value.status_code == 404
    assert "Detection with id 999 not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_detection_image_generate_thumbnail_on_fly(
    mock_db_session: AsyncMock, mock_detection_no_thumbnail: MagicMock
) -> None:
    """Test generating thumbnail on the fly when it doesn't exist."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_detection_no_thumbnail
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.commit = AsyncMock()

    generated_thumbnail_path = "/data/thumbnails/2_thumb.jpg"
    image_data = b"\xff\xd8\xff\xe0fake_jpeg_data"

    mock_thumbnail_gen = MagicMock()
    mock_thumbnail_gen.generate_thumbnail.return_value = generated_thumbnail_path

    def path_exists(path: str) -> bool:
        # Thumbnail doesn't exist, but source image does
        if path == mock_detection_no_thumbnail.thumbnail_path:
            return False
        if path == mock_detection_no_thumbnail.file_path:
            return True
        if path == generated_thumbnail_path:
            return True
        return False

    with (
        patch.object(detections_routes, "thumbnail_generator", mock_thumbnail_gen),
        patch("os.path.exists", side_effect=path_exists),
        patch("builtins.open", mock_open(read_data=image_data)),
    ):
        result = await detections_routes.get_detection_image(detection_id=2, db=mock_db_session)

    assert result.status_code == 200
    assert result.media_type == "image/jpeg"
    assert result.body == image_data

    # Verify thumbnail was generated with correct parameters
    mock_thumbnail_gen.generate_thumbnail.assert_called_once()
    call_kwargs = mock_thumbnail_gen.generate_thumbnail.call_args.kwargs
    assert call_kwargs["image_path"] == mock_detection_no_thumbnail.file_path
    assert call_kwargs["detection_id"] == str(mock_detection_no_thumbnail.id)

    # Verify detection was updated with thumbnail path
    assert mock_detection_no_thumbnail.thumbnail_path == generated_thumbnail_path
    mock_db_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_get_detection_image_source_not_found(
    mock_db_session: AsyncMock, mock_detection_no_thumbnail: MagicMock
) -> None:
    """Test error when source image doesn't exist and thumbnail needs generation."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_detection_no_thumbnail
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Both thumbnail and source image don't exist
    with patch("os.path.exists", return_value=False):
        with pytest.raises(HTTPException) as exc_info:
            await detections_routes.get_detection_image(detection_id=2, db=mock_db_session)

    assert exc_info.value.status_code == 404
    assert "Source image not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_detection_image_thumbnail_generation_fails(
    mock_db_session: AsyncMock, mock_detection_no_thumbnail: MagicMock
) -> None:
    """Test error when thumbnail generation fails."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_detection_no_thumbnail
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    mock_thumbnail_gen = MagicMock()
    mock_thumbnail_gen.generate_thumbnail.return_value = None  # Generation failed

    def path_exists(path: str) -> bool:
        if path == mock_detection_no_thumbnail.file_path:
            return True  # Source exists
        return False  # Thumbnail doesn't exist

    with (
        patch.object(detections_routes, "thumbnail_generator", mock_thumbnail_gen),
        patch("os.path.exists", side_effect=path_exists),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await detections_routes.get_detection_image(detection_id=2, db=mock_db_session)

    assert exc_info.value.status_code == 500
    assert "Failed to generate thumbnail image" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_detection_image_read_error(mock_db_session: AsyncMock, mock_detection: MagicMock) -> None:
    """Test error when reading thumbnail file fails."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_detection
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", side_effect=IOError("Permission denied")),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await detections_routes.get_detection_image(detection_id=1, db=mock_db_session)

    assert exc_info.value.status_code == 500
    assert "Failed to read thumbnail image" in exc_info.value.detail
    assert "Permission denied" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_detection_image_thumbnail_path_exists_but_file_missing(
    mock_db_session: AsyncMock, mock_detection: MagicMock
) -> None:
    """Test when thumbnail_path is set but file doesn't exist on disk."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_detection
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.commit = AsyncMock()

    generated_thumbnail_path = "/data/thumbnails/1_new_thumb.jpg"
    image_data = b"\xff\xd8\xff\xe0fake_jpeg_data"

    mock_thumbnail_gen = MagicMock()
    mock_thumbnail_gen.generate_thumbnail.return_value = generated_thumbnail_path

    call_count = [0]

    def path_exists(path: str) -> bool:
        call_count[0] += 1
        # First check: thumbnail_path exists check returns False (file missing)
        if path == mock_detection.thumbnail_path:
            return False
        # Source image exists
        if path == mock_detection.file_path:
            return True
        # Generated thumbnail exists
        if path == generated_thumbnail_path:
            return True
        return False

    with (
        patch.object(detections_routes, "thumbnail_generator", mock_thumbnail_gen),
        patch("os.path.exists", side_effect=path_exists),
        patch("builtins.open", mock_open(read_data=image_data)),
    ):
        result = await detections_routes.get_detection_image(detection_id=1, db=mock_db_session)

    assert result.status_code == 200
    # Thumbnail should be regenerated
    mock_thumbnail_gen.generate_thumbnail.assert_called_once()


@pytest.mark.asyncio
async def test_get_detection_image_verifies_detection_data_for_thumbnail(
    mock_db_session: AsyncMock, mock_detection_no_thumbnail: MagicMock
) -> None:
    """Test that correct detection data is passed to thumbnail generator."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_detection_no_thumbnail
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.commit = AsyncMock()

    generated_thumbnail_path = "/data/thumbnails/2_thumb.jpg"
    image_data = b"\xff\xd8\xff\xe0fake_jpeg_data"

    mock_thumbnail_gen = MagicMock()
    mock_thumbnail_gen.generate_thumbnail.return_value = generated_thumbnail_path

    def path_exists(path: str) -> bool:
        if path == mock_detection_no_thumbnail.file_path:
            return True
        if path == generated_thumbnail_path:
            return True
        return False

    with (
        patch.object(detections_routes, "thumbnail_generator", mock_thumbnail_gen),
        patch("os.path.exists", side_effect=path_exists),
        patch("builtins.open", mock_open(read_data=image_data)),
    ):
        await detections_routes.get_detection_image(detection_id=2, db=mock_db_session)

    # Verify detection data passed to thumbnail generator
    call_kwargs = mock_thumbnail_gen.generate_thumbnail.call_args.kwargs
    detection_data = call_kwargs["detections"][0]

    assert detection_data["object_type"] == mock_detection_no_thumbnail.object_type
    assert detection_data["confidence"] == mock_detection_no_thumbnail.confidence
    assert detection_data["bbox_x"] == mock_detection_no_thumbnail.bbox_x
    assert detection_data["bbox_y"] == mock_detection_no_thumbnail.bbox_y
    assert detection_data["bbox_width"] == mock_detection_no_thumbnail.bbox_width
    assert detection_data["bbox_height"] == mock_detection_no_thumbnail.bbox_height


@pytest.mark.asyncio
async def test_get_detection_image_cache_header(mock_db_session: AsyncMock, mock_detection: MagicMock) -> None:
    """Test that cache control header is properly set."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_detection
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    image_data = b"\xff\xd8\xff\xe0fake_jpeg_data"

    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=image_data)),
    ):
        result = await detections_routes.get_detection_image(detection_id=1, db=mock_db_session)

    # Cache for 1 hour
    assert "Cache-Control" in result.headers
    assert result.headers["Cache-Control"] == "public, max-age=3600"


# =============================================================================
# Router Configuration Tests
# =============================================================================


def test_router_prefix() -> None:
    """Test that router has correct prefix."""
    assert detections_routes.router.prefix == "/api/detections"


def test_router_tags() -> None:
    """Test that router has correct tags."""
    assert "detections" in detections_routes.router.tags


# =============================================================================
# Edge Cases
# =============================================================================


@pytest.mark.asyncio
async def test_list_detections_with_zero_confidence_filter(mock_db_session: AsyncMock) -> None:
    """Test filtering with min_confidence=0 (edge case for None check)."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 0

    mock_db_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    # min_confidence=0.0 should still apply the filter (not be treated as None)
    result = await detections_routes.list_detections(
        camera_id=None,
        object_type=None,
        start_date=None,
        end_date=None,
        min_confidence=0.0,
        limit=50,
        offset=0,
        db=mock_db_session,
    )

    assert result["count"] == 0


@pytest.mark.asyncio
async def test_list_detections_with_start_date_only(mock_db_session: AsyncMock, mock_detection: MagicMock) -> None:
    """Test filtering with only start_date (no end_date)."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection]
    mock_result.scalars.return_value = mock_scalars

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1

    mock_db_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    result = await detections_routes.list_detections(
        camera_id=None,
        object_type=None,
        start_date=datetime(2025, 12, 1),
        end_date=None,
        min_confidence=None,
        limit=50,
        offset=0,
        db=mock_db_session,
    )

    assert result["count"] == 1


@pytest.mark.asyncio
async def test_list_detections_with_end_date_only(mock_db_session: AsyncMock, mock_detection: MagicMock) -> None:
    """Test filtering with only end_date (no start_date)."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection]
    mock_result.scalars.return_value = mock_scalars

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1

    mock_db_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    result = await detections_routes.list_detections(
        camera_id=None,
        object_type=None,
        start_date=None,
        end_date=datetime(2025, 12, 31),
        min_confidence=None,
        limit=50,
        offset=0,
        db=mock_db_session,
    )

    assert result["count"] == 1


@pytest.mark.asyncio
async def test_get_detection_image_with_none_thumbnail_path(mock_db_session: AsyncMock) -> None:
    """Test image endpoint when detection.thumbnail_path is None."""
    detection = MagicMock(spec=Detection)
    detection.id = 3
    detection.thumbnail_path = None
    detection.file_path = "/export/foscam/camera/image.jpg"
    detection.object_type = "person"
    detection.confidence = 0.9
    detection.bbox_x = 10
    detection.bbox_y = 20
    detection.bbox_width = 100
    detection.bbox_height = 200

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = detection
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    mock_db_session.commit = AsyncMock()

    generated_path = "/data/thumbnails/3_thumb.jpg"
    image_data = b"\xff\xd8\xff\xe0fake"

    mock_thumbnail_gen = MagicMock()
    mock_thumbnail_gen.generate_thumbnail.return_value = generated_path

    def path_exists(path: str) -> bool:
        if path == detection.file_path:
            return True
        if path == generated_path:
            return True
        return False

    with (
        patch.object(detections_routes, "thumbnail_generator", mock_thumbnail_gen),
        patch("os.path.exists", side_effect=path_exists),
        patch("builtins.open", mock_open(read_data=image_data)),
    ):
        result = await detections_routes.get_detection_image(detection_id=3, db=mock_db_session)

    assert result.status_code == 200


@pytest.mark.asyncio
async def test_list_detections_large_offset(mock_db_session: AsyncMock) -> None:
    """Test listing detections with large offset beyond total count."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []  # No results at this offset
    mock_result.scalars.return_value = mock_scalars

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 10  # Only 10 total

    mock_db_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    result = await detections_routes.list_detections(
        camera_id=None,
        object_type=None,
        start_date=None,
        end_date=None,
        min_confidence=None,
        limit=50,
        offset=1000,  # Way beyond total count
        db=mock_db_session,
    )

    assert result["count"] == 10
    assert result["offset"] == 1000
    assert result["detections"] == []


@pytest.mark.asyncio
async def test_list_detections_max_limit(mock_db_session: AsyncMock, mock_detection: MagicMock) -> None:
    """Test listing detections with maximum limit."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection]
    mock_result.scalars.return_value = mock_scalars

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1

    mock_db_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    result = await detections_routes.list_detections(
        camera_id=None,
        object_type=None,
        start_date=None,
        end_date=None,
        min_confidence=None,
        limit=1000,  # Maximum allowed
        offset=0,
        db=mock_db_session,
    )

    assert result["limit"] == 1000


@pytest.mark.asyncio
async def test_list_detections_min_limit(mock_db_session: AsyncMock, mock_detection: MagicMock) -> None:
    """Test listing detections with minimum limit."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection]
    mock_result.scalars.return_value = mock_scalars

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 100

    mock_db_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    result = await detections_routes.list_detections(
        camera_id=None,
        object_type=None,
        start_date=None,
        end_date=None,
        min_confidence=None,
        limit=1,  # Minimum allowed
        offset=0,
        db=mock_db_session,
    )

    assert result["limit"] == 1


# =============================================================================
# Integration with Module-Level Variables
# =============================================================================


def test_thumbnail_generator_initialized() -> None:
    """Test that thumbnail_generator is initialized at module level."""
    assert detections_routes.thumbnail_generator is not None
    assert hasattr(detections_routes.thumbnail_generator, "generate_thumbnail")
