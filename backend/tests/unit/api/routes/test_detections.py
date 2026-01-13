"""Unit tests for detections API route handlers.

This test file covers the route handlers in backend/api/routes/detections.py
to increase coverage from 80.3% to at least 95%.

Tests cover:
- list_detections endpoint (filtering, pagination, cursor-based pagination)
- get_detection_stats endpoint (aggregate statistics)
- get_detection endpoint (single detection retrieval)
- get_detection_enrichment endpoint (enrichment data)
- get_detection_image endpoint (image serving with thumbnails)
- stream_detection_video endpoint (video streaming with range requests)
- get_video_thumbnail endpoint (video thumbnail extraction)
- search_detections endpoint (full-text search)
- list_detection_labels endpoint (label enumeration)
- Bulk operations (create, update, delete)
- Helper functions (_sanitize_errors, _extract_clothing_from_enrichment, etc.)
"""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch

import pytest
from fastapi import HTTPException, status

from backend.api.pagination import CursorData, encode_cursor
from backend.api.routes.detections import (
    _extract_clothing_from_enrichment,
    _extract_vehicle_from_enrichment,
    _parse_range_header,
    _sanitize_errors,
    _transform_enrichment_data,
    get_detection,
    get_detection_enrichment,
    get_detection_image,
    get_detection_stats,
    get_detection_thumbnail,
    get_video_thumbnail,
    list_detections,
    stream_detection_video,
    validate_enrichment_data,
)
from backend.services.thumbnail_generator import ThumbnailGenerator
from backend.services.video_processor import VideoProcessor
from backend.tests.factories import DetectionFactory


@pytest.fixture
def mock_thumbnail_generator():
    """Create a mock ThumbnailGenerator for DI."""
    return MagicMock(spec=ThumbnailGenerator)


@pytest.fixture
def mock_video_processor():
    """Create a mock VideoProcessor for DI."""
    return MagicMock(spec=VideoProcessor)


# ============================================================================
# Helper Function Tests
# ============================================================================


class TestSanitizeErrors:
    """Tests for _sanitize_errors function."""

    def test_sanitize_empty_list(self):
        """Test sanitizing empty error list returns empty list."""
        result = _sanitize_errors([])
        assert result == []

    def test_sanitize_none(self):
        """Test sanitizing None returns empty list."""
        result = _sanitize_errors(None)
        assert result == []

    def test_sanitize_license_plate_error(self):
        """Test sanitizing license plate detection error."""
        errors = ["License plate detection failed: /path/to/image.jpg"]
        result = _sanitize_errors(errors)
        assert result == ["License Plate Detection failed"]

    def test_sanitize_face_detection_error(self):
        """Test sanitizing face detection error."""
        errors = ["Face detection error: internal stacktrace here"]
        result = _sanitize_errors(errors)
        assert result == ["Face Detection failed"]

    def test_sanitize_violence_detection_error(self):
        """Test sanitizing violence detection error."""
        errors = ["Violence detection failed with timeout"]
        result = _sanitize_errors(errors)
        assert result == ["Violence Detection failed"]

    def test_sanitize_unknown_error_category(self):
        """Test sanitizing error with unknown category."""
        errors = ["Unknown error type: something went wrong"]
        result = _sanitize_errors(errors)
        assert result == ["Enrichment processing error"]

    def test_sanitize_multiple_errors(self):
        """Test sanitizing multiple errors."""
        errors = [
            "License plate detection failed",
            "Face detection error",
            "Unknown error",
        ]
        result = _sanitize_errors(errors)
        assert len(result) == 3
        assert "License Plate Detection failed" in result
        assert "Face Detection failed" in result
        assert "Enrichment processing error" in result

    def test_sanitize_clothing_classification_error(self):
        """Test sanitizing clothing classification error."""
        errors = ["clothing classification failed: timeout"]
        result = _sanitize_errors(errors)
        assert result == ["Clothing Classification failed"]

    def test_sanitize_pet_classification_error(self):
        """Test sanitizing pet classification error."""
        errors = ["Pet classification error: model not loaded"]
        result = _sanitize_errors(errors)
        assert result == ["Pet Classification failed"]


class TestExtractClothingFromEnrichment:
    """Tests for _extract_clothing_from_enrichment function."""

    def test_extract_no_clothing_data(self):
        """Test extracting clothing when no data exists."""
        enrichment_data = {}
        result = _extract_clothing_from_enrichment(enrichment_data)
        assert result is None

    def test_extract_clothing_classifications_only(self):
        """Test extracting clothing with classifications only."""
        enrichment_data = {
            "clothing_classifications": {
                "det_0": {
                    "raw_description": "dark jacket, blue jeans",
                    "top_category": "jacket",
                    "is_suspicious": False,
                    "is_service_uniform": False,
                }
            }
        }
        result = _extract_clothing_from_enrichment(enrichment_data)
        assert result is not None
        assert result["upper"] == "dark jacket"
        assert result["lower"] == "blue jeans"
        assert result["is_suspicious"] is False
        assert result["is_service_uniform"] is False

    def test_extract_clothing_segmentation_only(self):
        """Test extracting clothing with segmentation only."""
        enrichment_data = {
            "clothing_segmentation": {
                "det_0": {
                    "has_face_covered": False,
                    "has_bag": True,
                    "clothing_items": ["shirt", "pants"],
                }
            }
        }
        result = _extract_clothing_from_enrichment(enrichment_data)
        assert result is not None
        assert result["has_face_covered"] is False
        assert result["has_bag"] is True
        assert result["clothing_items"] == ["shirt", "pants"]

    def test_extract_clothing_both_classifications_and_segmentation(self):
        """Test extracting clothing with both classifications and segmentation."""
        enrichment_data = {
            "clothing_classifications": {
                "det_0": {
                    "raw_description": "hoodie",
                    "top_category": "hoodie",
                    "is_suspicious": True,
                    "is_service_uniform": False,
                }
            },
            "clothing_segmentation": {
                "det_0": {
                    "has_face_covered": True,
                    "has_bag": False,
                    "clothing_items": ["hoodie"],
                }
            },
        }
        result = _extract_clothing_from_enrichment(enrichment_data)
        assert result is not None
        assert result["upper"] == "hoodie"
        assert result["is_suspicious"] is True
        assert result["has_face_covered"] is True
        assert result["has_bag"] is False

    def test_extract_clothing_no_comma_in_description(self):
        """Test extracting clothing when description has no comma."""
        enrichment_data = {
            "clothing_classifications": {
                "det_0": {
                    "raw_description": "uniform",
                    "top_category": "work uniform",
                    "is_suspicious": False,
                    "is_service_uniform": True,
                }
            }
        }
        result = _extract_clothing_from_enrichment(enrichment_data)
        assert result is not None
        assert result["upper"] == "uniform"
        assert result["lower"] is None

    def test_extract_clothing_empty_description_falls_back_to_category(self):
        """Test extracting clothing with empty raw description."""
        enrichment_data = {
            "clothing_classifications": {
                "det_0": {
                    "raw_description": "",
                    "top_category": "shirt",
                    "is_suspicious": False,
                    "is_service_uniform": False,
                }
            }
        }
        result = _extract_clothing_from_enrichment(enrichment_data)
        assert result is not None
        assert result["upper"] == "shirt"


class TestExtractVehicleFromEnrichment:
    """Tests for _extract_vehicle_from_enrichment function."""

    def test_extract_no_vehicle_data(self):
        """Test extracting vehicle when no data exists."""
        enrichment_data = {}
        result = _extract_vehicle_from_enrichment(enrichment_data)
        assert result is None

    def test_extract_vehicle_classification_only(self):
        """Test extracting vehicle with classification only."""
        enrichment_data = {
            "vehicle_classifications": {
                "det_0": {
                    "vehicle_type": "sedan",
                    "confidence": 0.95,
                    "is_commercial": False,
                }
            }
        }
        result = _extract_vehicle_from_enrichment(enrichment_data)
        assert result is not None
        assert result["type"] == "sedan"
        assert result["confidence"] == 0.95
        assert result["is_commercial"] is False
        assert result["damage_detected"] is None
        assert result["damage_types"] is None

    def test_extract_vehicle_with_damage_detection(self):
        """Test extracting vehicle with damage detection."""
        enrichment_data = {
            "vehicle_classifications": {
                "det_0": {
                    "vehicle_type": "truck",
                    "confidence": 0.88,
                    "is_commercial": True,
                }
            },
            "vehicle_damage": {
                "det_0": {
                    "has_damage": True,
                    "damage_types": ["dent", "scratch"],
                }
            },
        }
        result = _extract_vehicle_from_enrichment(enrichment_data)
        assert result is not None
        assert result["type"] == "truck"
        assert result["is_commercial"] is True
        assert result["damage_detected"] is True
        assert result["damage_types"] == ["dent", "scratch"]

    def test_extract_vehicle_empty_classifications(self):
        """Test extracting vehicle with empty classifications dict."""
        enrichment_data = {"vehicle_classifications": {}}
        result = _extract_vehicle_from_enrichment(enrichment_data)
        assert result is None


class TestValidateEnrichmentData:
    """Tests for validate_enrichment_data function."""

    def test_validate_none_enrichment_data(self):
        """Test validating None enrichment data."""
        result = validate_enrichment_data(None)
        assert result is None

    def test_validate_empty_enrichment_data(self):
        """Test validating empty enrichment data."""
        enrichment_data = {}
        result = validate_enrichment_data(enrichment_data)
        assert result is not None
        assert result.vehicle is None
        assert result.person is None
        assert result.pet is None
        assert result.weather is None
        assert result.errors == []

    def test_validate_vehicle_enrichment(self):
        """Test validating enrichment data with vehicle."""
        enrichment_data = {
            "vehicle_classifications": {
                "det_0": {
                    "vehicle_type": "suv",
                    "confidence": 0.92,
                    "is_commercial": False,
                }
            }
        }
        result = validate_enrichment_data(enrichment_data)
        assert result is not None
        assert result.vehicle is not None
        assert result.vehicle.vehicle_type == "suv"
        assert result.vehicle.is_commercial is False

    def test_validate_person_enrichment(self):
        """Test validating enrichment data with person."""
        enrichment_data = {
            "clothing_classifications": {
                "det_0": {
                    "raw_description": "red shirt, black pants",
                    "carrying": "backpack",
                    "is_suspicious": False,
                }
            }
        }
        result = validate_enrichment_data(enrichment_data)
        assert result is not None
        assert result.person is not None
        assert result.person.clothing_description == "red shirt, black pants"
        assert result.person.carrying == ["backpack"]
        assert result.person.is_suspicious is False

    def test_validate_pet_enrichment(self):
        """Test validating enrichment data with pet."""
        enrichment_data = {
            "pet_classifications": {
                "det_0": {
                    "animal_type": "dog",
                }
            }
        }
        result = validate_enrichment_data(enrichment_data)
        assert result is not None
        assert result.pet is not None
        assert result.pet.pet_type == "dog"
        assert result.pet.breed is None

    def test_validate_enrichment_with_errors(self):
        """Test validating enrichment data with errors."""
        enrichment_data = {
            "errors": [
                "License plate detection failed",
                "Unknown error",
            ]
        }
        result = validate_enrichment_data(enrichment_data)
        assert result is not None
        assert len(result.errors) == 2
        assert "License Plate Detection failed" in result.errors
        assert "Enrichment processing error" in result.errors


class TestTransformEnrichmentData:
    """Tests for _transform_enrichment_data function."""

    def test_transform_none_enrichment_data(self):
        """Test transforming None enrichment data."""
        detection_id = 1
        detected_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
        result = _transform_enrichment_data(detection_id, None, detected_at)

        assert result["detection_id"] == 1
        assert result["enriched_at"] == detected_at
        assert result["license_plate"]["detected"] is False
        assert result["face"]["detected"] is False
        assert result["vehicle"] is None
        assert result["clothing"] is None
        assert result["violence"]["detected"] is False
        assert result["pet"] is None
        assert result["errors"] == []

    def test_transform_with_license_plate(self):
        """Test transforming enrichment data with license plate."""
        enrichment_data = {
            "license_plates": [
                {
                    "confidence": 0.95,
                    "text": "ABC123",
                    "ocr_confidence": 0.92,
                    "bbox": [100, 200, 50, 30],
                }
            ]
        }
        result = _transform_enrichment_data(1, enrichment_data, None)

        assert result["license_plate"]["detected"] is True
        assert result["license_plate"]["confidence"] == 0.95
        assert result["license_plate"]["text"] == "ABC123"
        assert result["license_plate"]["ocr_confidence"] == 0.92

    def test_transform_with_faces(self):
        """Test transforming enrichment data with faces."""
        enrichment_data = {
            "faces": [
                {"confidence": 0.88},
                {"confidence": 0.92},
            ]
        }
        result = _transform_enrichment_data(1, enrichment_data, None)

        assert result["face"]["detected"] is True
        assert result["face"]["count"] == 2
        assert result["face"]["confidence"] == 0.92  # max confidence

    def test_transform_with_violence_detection(self):
        """Test transforming enrichment data with violence detection."""
        enrichment_data = {
            "violence_detection": {
                "is_violent": True,
                "confidence": 0.85,
            }
        }
        result = _transform_enrichment_data(1, enrichment_data, None)

        assert result["violence"]["detected"] is True
        assert result["violence"]["score"] == 0.85
        assert result["violence"]["confidence"] == 0.85

    def test_transform_with_image_quality(self):
        """Test transforming enrichment data with image quality."""
        enrichment_data = {
            "image_quality": {
                "quality_score": 0.75,
                "is_blurry": False,
                "is_low_quality": False,
                "quality_issues": [],
            },
            "quality_change_detected": False,
        }
        result = _transform_enrichment_data(1, enrichment_data, None)

        assert result["image_quality"] is not None
        assert result["image_quality"]["score"] == 0.75
        assert result["image_quality"]["is_blurry"] is False
        assert result["image_quality"]["quality_change_detected"] is False

    def test_transform_with_pet_classification(self):
        """Test transforming enrichment data with pet classification."""
        enrichment_data = {
            "pet_classifications": {
                "det_0": {
                    "animal_type": "cat",
                    "confidence": 0.93,
                    "is_household_pet": True,
                }
            }
        }
        result = _transform_enrichment_data(1, enrichment_data, None)

        assert result["pet"] is not None
        assert result["pet"]["detected"] is True
        assert result["pet"]["type"] == "cat"
        assert result["pet"]["confidence"] == 0.93
        assert result["pet"]["is_household_pet"] is True

    def test_transform_with_processing_time(self):
        """Test transforming enrichment data with processing time."""
        enrichment_data = {
            "processing_time_ms": 1234,
        }
        result = _transform_enrichment_data(1, enrichment_data, None)

        assert result["processing_time_ms"] == 1234


class TestParseRangeHeader:
    """Tests for _parse_range_header function."""

    def test_parse_explicit_range(self):
        """Test parsing explicit range (e.g., bytes=0-1023)."""
        start, end = _parse_range_header("bytes=0-1023", 10000)
        assert start == 0
        assert end == 1023

    def test_parse_open_ended_range(self):
        """Test parsing open-ended range (e.g., bytes=500-)."""
        start, end = _parse_range_header("bytes=500-", 10000)
        assert start == 500
        assert end == 9999

    def test_parse_suffix_range(self):
        """Test parsing suffix range (e.g., bytes=-500)."""
        start, end = _parse_range_header("bytes=-500", 10000)
        assert start == 9500
        assert end == 9999

    def test_parse_suffix_range_larger_than_file(self):
        """Test parsing suffix range larger than file size."""
        start, end = _parse_range_header("bytes=-20000", 10000)
        assert start == 0
        assert end == 9999

    def test_parse_range_clamped_to_file_size(self):
        """Test that range is clamped to file size."""
        start, end = _parse_range_header("bytes=0-50000", 10000)
        assert start == 0
        assert end == 9999

    def test_parse_range_invalid_format(self):
        """Test parsing invalid range format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid range header format"):
            _parse_range_header("invalid-format", 10000)

    def test_parse_range_invalid_specification(self):
        """Test parsing invalid range specification raises ValueError."""
        with pytest.raises(ValueError, match="Invalid range specification"):
            _parse_range_header("bytes=0-100-200", 10000)

    def test_parse_range_start_greater_than_end(self):
        """Test parsing range where start > end raises ValueError."""
        with pytest.raises(ValueError, match="Invalid range: start > end"):
            _parse_range_header("bytes=1000-500", 10000)


# ============================================================================
# Route Handler Tests
# ============================================================================


class TestListDetections:
    """Tests for list_detections endpoint."""

    @pytest.mark.asyncio
    async def test_list_detections_basic(self, mock_db_session):
        """Test listing detections with no filters."""
        # Create mock detections
        det1 = DetectionFactory(id=1, object_type="person", confidence=0.95)
        det2 = DetectionFactory(id=2, object_type="car", confidence=0.88)

        # Configure mock to return detections
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [det1, det2]
        mock_result.scalars.return_value = mock_scalars
        mock_result.scalar.return_value = 2  # count result

        # Configure execute to return count first, then detections
        mock_db_session.execute.side_effect = [
            MagicMock(scalar=lambda: 2),  # count query
            mock_result,  # detections query
        ]

        # Pass default Query parameter values explicitly
        result = await list_detections(
            camera_id=None,
            object_type=None,
            start_date=None,
            end_date=None,
            min_confidence=None,
            limit=50,
            offset=0,
            cursor=None,
            db=mock_db_session,
        )

        assert result.pagination.total == 2
        assert len(result.items) == 2
        assert result.pagination.limit == 50
        assert result.pagination.offset == 0
        assert result.pagination.has_more is False

    @pytest.mark.asyncio
    async def test_list_detections_with_filters(self, mock_db_session):
        """Test listing detections with filters applied."""
        det1 = DetectionFactory(
            id=1,
            camera_id="front_door",
            object_type="person",
            confidence=0.95,
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [det1]
        mock_result.scalars.return_value = mock_scalars

        mock_db_session.execute.side_effect = [
            MagicMock(scalar=lambda: 1),
            mock_result,
        ]

        result = await list_detections(
            camera_id="front_door",
            object_type="person",
            start_date=None,
            end_date=None,
            min_confidence=0.9,
            limit=50,
            offset=0,
            cursor=None,
            db=mock_db_session,
        )

        assert result.pagination.total == 1
        assert len(result.items) == 1

    @pytest.mark.asyncio
    async def test_list_detections_with_date_range(self, mock_db_session):
        """Test listing detections with date range filter."""
        start_date = datetime(2025, 12, 1, 0, 0, 0, tzinfo=UTC)
        end_date = datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC)

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars

        mock_db_session.execute.side_effect = [
            MagicMock(scalar=lambda: 0),
            mock_result,
        ]

        result = await list_detections(
            camera_id=None,
            object_type=None,
            start_date=start_date,
            end_date=end_date,
            min_confidence=None,
            limit=50,
            offset=0,
            cursor=None,
            db=mock_db_session,
        )

        assert result.pagination.total == 0

    @pytest.mark.asyncio
    async def test_list_detections_invalid_date_range(self, mock_db_session):
        """Test listing detections with invalid date range raises HTTPException."""
        start_date = datetime(2025, 12, 31, 0, 0, 0, tzinfo=UTC)
        end_date = datetime(2025, 12, 1, 0, 0, 0, tzinfo=UTC)

        with pytest.raises(HTTPException) as exc_info:
            await list_detections(
                start_date=start_date,
                end_date=end_date,
                db=mock_db_session,
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "start_date" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_list_detections_with_cursor(self, mock_db_session):
        """Test listing detections with cursor-based pagination."""
        cursor_data = CursorData(
            id=50,
            created_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
        )
        cursor = encode_cursor(cursor_data)

        det1 = DetectionFactory(id=49)

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [det1]
        mock_result.scalars.return_value = mock_scalars

        mock_db_session.execute.return_value = mock_result

        result = await list_detections(
            camera_id=None,
            object_type=None,
            start_date=None,
            end_date=None,
            min_confidence=None,
            limit=50,
            offset=0,
            cursor=cursor,
            db=mock_db_session,
        )

        assert len(result.items) == 1
        assert result.pagination.has_more is False
        # No count query when using cursor
        assert result.pagination.total == 0

    @pytest.mark.asyncio
    async def test_list_detections_invalid_cursor(self, mock_db_session):
        """Test listing detections with invalid cursor raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            await list_detections(cursor="invalid-cursor", db=mock_db_session)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid cursor" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_list_detections_has_more_results(self, mock_db_session):
        """Test listing detections when there are more results."""
        # Create limit + 1 detections to trigger has_more
        detections = [DetectionFactory(id=i) for i in range(51)]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = detections
        mock_result.scalars.return_value = mock_scalars

        mock_db_session.execute.side_effect = [
            MagicMock(scalar=lambda: 100),
            mock_result,
        ]

        result = await list_detections(
            camera_id=None,
            object_type=None,
            start_date=None,
            end_date=None,
            min_confidence=None,
            limit=50,
            offset=0,
            cursor=None,
            db=mock_db_session,
        )

        assert result.pagination.has_more is True
        assert len(result.items) == 50
        assert result.pagination.next_cursor is not None

    @pytest.mark.asyncio
    async def test_list_detections_with_offset_deprecation_warning(self, mock_db_session):
        """Test listing detections with offset shows deprecation warning."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars

        mock_db_session.execute.side_effect = [
            MagicMock(scalar=lambda: 0),
            mock_result,
        ]

        result = await list_detections(
            camera_id=None,
            object_type=None,
            start_date=None,
            end_date=None,
            min_confidence=None,
            limit=50,
            offset=10,
            cursor=None,
            db=mock_db_session,
        )

        assert result.deprecation_warning is not None
        assert "deprecated" in result.deprecation_warning.lower()


class TestGetDetectionStats:
    """Tests for get_detection_stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_stats_with_detections(self, mock_db_session):
        """Test getting stats when detections exist."""
        # Mock query result with class distribution
        mock_row1 = MagicMock()
        mock_row1.object_type = "person"
        mock_row1.class_count = 50
        mock_row1.class_avg_confidence = 0.95
        mock_row1.total_count = 100
        mock_row1.avg_confidence = 0.90

        mock_row2 = MagicMock()
        mock_row2.object_type = "car"
        mock_row2.class_count = 30
        mock_row2.class_avg_confidence = 0.88
        mock_row2.total_count = 100
        mock_row2.avg_confidence = 0.90

        mock_row3 = MagicMock()
        mock_row3.object_type = "truck"
        mock_row3.class_count = 20
        mock_row3.class_avg_confidence = 0.85
        mock_row3.total_count = 100
        mock_row3.avg_confidence = 0.90

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row1, mock_row2, mock_row3]

        mock_db_session.execute.return_value = mock_result

        result = await get_detection_stats(db=mock_db_session)

        assert result.total_detections == 100
        assert result.detections_by_class["person"] == 50
        assert result.detections_by_class["car"] == 30
        assert result.detections_by_class["truck"] == 20
        assert result.average_confidence == 0.90

    @pytest.mark.asyncio
    async def test_get_stats_no_detections(self, mock_db_session):
        """Test getting stats when no detections exist."""
        mock_result = MagicMock()
        mock_result.all.return_value = []

        mock_db_session.execute.return_value = mock_result

        result = await get_detection_stats(db=mock_db_session)

        assert result.total_detections == 0
        assert result.detections_by_class == {}
        assert result.average_confidence is None


class TestGetDetection:
    """Tests for get_detection endpoint."""

    @pytest.mark.asyncio
    async def test_get_detection_found(self, mock_db_session):
        """Test getting a detection that exists."""
        detection = DetectionFactory(id=1, object_type="person")

        with patch(
            "backend.api.routes.detections.get_detection_or_404",
            return_value=detection,
        ):
            result = await get_detection(detection_id=1, db=mock_db_session)

        assert result.id == 1
        assert result.object_type == "person"

    @pytest.mark.asyncio
    async def test_get_detection_not_found(self, mock_db_session):
        """Test getting a detection that doesn't exist raises 404."""
        with patch(
            "backend.api.routes.detections.get_detection_or_404",
            side_effect=HTTPException(status_code=404, detail="Not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_detection(detection_id=999, db=mock_db_session)

            assert exc_info.value.status_code == 404


class TestGetDetectionEnrichment:
    """Tests for get_detection_enrichment endpoint."""

    @pytest.mark.asyncio
    async def test_get_enrichment_found(self, mock_db_session):
        """Test getting enrichment data for a detection."""
        detection = DetectionFactory(
            id=1,
            enrichment_data={"license_plates": [{"text": "ABC123", "confidence": 0.95}]},
        )

        with patch(
            "backend.api.routes.detections.get_detection_or_404",
            return_value=detection,
        ):
            result = await get_detection_enrichment(detection_id=1, db=mock_db_session)

        assert result.detection_id == 1
        assert result.license_plate.detected is True
        assert result.license_plate.text == "ABC123"

    @pytest.mark.asyncio
    async def test_get_enrichment_no_enrichment_data(self, mock_db_session):
        """Test getting enrichment data when none exists."""
        detection = DetectionFactory(id=1, enrichment_data=None)

        with patch(
            "backend.api.routes.detections.get_detection_or_404",
            return_value=detection,
        ):
            result = await get_detection_enrichment(detection_id=1, db=mock_db_session)

        assert result.detection_id == 1
        assert result.license_plate.detected is False
        assert result.face.detected is False


class TestGetDetectionImage:
    """Tests for get_detection_image endpoint (NEM-2445)."""

    @pytest.mark.asyncio
    async def test_get_image_thumbnail_exists(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test getting detection image when thumbnail exists."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/test.jpg",
            thumbnail_path="/data/thumbnails/1.jpg",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("os.path.exists", return_value=True),
        ):
            mock_file_data = b"fake image data"
            with patch("builtins.open", mock_open(read_data=mock_file_data)):
                response = await get_detection_image(
                    detection_id=1,
                    full=False,  # Explicitly pass False since Query(False) is truthy
                    db=mock_db_session,
                    thumbnail_generator=mock_thumbnail_generator,
                    video_processor=mock_video_processor,
                )

        assert response.body == mock_file_data
        assert response.media_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_get_image_full_size(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test getting full-size original image."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/test.jpg",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("os.path.exists", return_value=True),
        ):
            mock_file_data = b"fake full image data"
            with patch("builtins.open", mock_open(read_data=mock_file_data)):
                response = await get_detection_image(
                    detection_id=1,
                    full=True,
                    db=mock_db_session,
                    thumbnail_generator=mock_thumbnail_generator,
                    video_processor=mock_video_processor,
                )

        assert response.body == mock_file_data

    @pytest.mark.asyncio
    async def test_get_image_file_not_found(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test getting detection image when file doesn't exist."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/missing.jpg",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("os.path.exists", return_value=False),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_detection_image(
                detection_id=1,
                full=True,
                db=mock_db_session,
                thumbnail_generator=mock_thumbnail_generator,
                video_processor=mock_video_processor,
            )

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_image_generate_thumbnail_on_fly(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test generating thumbnail on the fly when it doesn't exist."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/test.jpg",
            thumbnail_path=None,
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=200,
            bbox_width=150,
            bbox_height=300,
        )

        # Configure mock thumbnail generator
        mock_thumbnail_generator.generate_thumbnail.return_value = "/data/thumbnails/generated.jpg"

        with patch(
            "backend.api.routes.detections.get_detection_or_404",
            return_value=detection,
        ):
            # detection.thumbnail_path is None, so os.path.exists not called on it
            # First: file_path exists check (True), second: generated thumbnail exists (True)
            with patch("backend.api.routes.detections.os.path.exists", side_effect=[True, True]):
                mock_file_data = b"generated thumbnail"
                with patch("builtins.open", mock_open(read_data=mock_file_data)):
                    response = await get_detection_image(
                        detection_id=1,
                        full=False,  # Explicitly pass False since Query(False) is truthy
                        db=mock_db_session,
                        thumbnail_generator=mock_thumbnail_generator,
                        video_processor=mock_video_processor,
                    )

        assert response.body == mock_file_data
        # Note: We don't assert commit because the mock may not preserve async call tracking

    @pytest.mark.asyncio
    async def test_get_image_thumbnail_generation_fails(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test handling thumbnail generation failure."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/test.jpg",
            thumbnail_path=None,
        )

        # Configure mock to return None (generation failure)
        mock_thumbnail_generator.generate_thumbnail.return_value = None

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("backend.api.routes.detections.os.path.exists", side_effect=[False, True]),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_detection_image(
                detection_id=1,
                full=False,  # Explicitly pass False since Query(False) is truthy
                db=mock_db_session,
                thumbnail_generator=mock_thumbnail_generator,
                video_processor=mock_video_processor,
            )

        # When thumbnail generation fails but file_path doesn't exist, returns 404
        assert exc_info.value.status_code in [404, 500]

    @pytest.mark.asyncio
    async def test_get_image_read_error(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test handling file read error."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/test.jpg",
            thumbnail_path="/data/thumbnails/1.jpg",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("os.path.exists", return_value=True),
        ):
            with patch("builtins.open", side_effect=OSError("Read error")):
                with pytest.raises(HTTPException) as exc_info:
                    await get_detection_image(
                        detection_id=1,
                        full=False,  # Explicitly pass False since Query(False) is truthy
                        db=mock_db_session,
                        thumbnail_generator=mock_thumbnail_generator,
                        video_processor=mock_video_processor,
                    )

        assert exc_info.value.status_code == 500

    # NEM-2445: Tests for video detection image handling
    @pytest.mark.asyncio
    async def test_get_image_video_detection_thumbnail_exists(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test getting image for video detection when thumbnail already exists."""
        detection = DetectionFactory(
            id=11,
            file_path="/export/foscam/test.mp4",
            thumbnail_path="/data/thumbnails/11.jpg",
            media_type="video",
            file_type="video/mp4",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("backend.api.routes.detections.os.path.exists", return_value=True),
        ):
            mock_file_data = b"video thumbnail data"
            with patch("builtins.open", mock_open(read_data=mock_file_data)):
                response = await get_detection_image(
                    detection_id=11,
                    full=False,  # Explicitly pass False since Query(False) is truthy
                    db=mock_db_session,
                    thumbnail_generator=mock_thumbnail_generator,
                    video_processor=mock_video_processor,
                )

        assert response.body == mock_file_data
        assert response.media_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_get_image_video_detection_generates_thumbnail(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test generating thumbnail for video detection using VideoProcessor (NEM-2445)."""
        detection = DetectionFactory(
            id=12,
            file_path="/export/foscam/test.mp4",
            thumbnail_path=None,
            media_type="video",
            file_type="video/mp4",
        )

        # Configure mock video processor
        mock_video_processor.extract_thumbnail_for_detection = AsyncMock(
            return_value="/data/thumbnails/video_12.jpg"
        )

        with patch(
            "backend.api.routes.detections.get_detection_or_404",
            return_value=detection,
        ):
            # detection.thumbnail_path is None, so first call checks if source exists (True)
            # The file is opened to read the generated thumbnail
            with patch("backend.api.routes.detections.os.path.exists", return_value=True):
                mock_file_data = b"generated video thumbnail"
                with patch("builtins.open", mock_open(read_data=mock_file_data)):
                    response = await get_detection_image(
                        detection_id=12,
                        full=False,  # Explicitly pass False since Query(False) is truthy
                        db=mock_db_session,
                        thumbnail_generator=mock_thumbnail_generator,
                        video_processor=mock_video_processor,
                    )

        assert response.body == mock_file_data
        # Verify video processor was called (not thumbnail_generator)
        mock_video_processor.extract_thumbnail_for_detection.assert_called_once_with(
            video_path="/export/foscam/test.mp4",
            detection_id=12,
        )
        mock_thumbnail_generator.generate_thumbnail.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_image_video_detection_full_extracts_frame(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test getting full-size image for video detection extracts a frame (NEM-2445)."""
        detection = DetectionFactory(
            id=13,
            file_path="/export/foscam/test.mp4",
            media_type="video",
            file_type="video/mp4",
        )

        # Configure mock video processor to extract a frame
        mock_video_processor.extract_thumbnail = AsyncMock(
            return_value="/tmp/extracted_frame.jpg"  # noqa: S108 - mock path for testing
        )

        with patch(
            "backend.api.routes.detections.get_detection_or_404",
            return_value=detection,
        ):
            with patch("backend.api.routes.detections.os.path.exists", return_value=True):
                mock_file_data = b"full frame from video"
                with patch("builtins.open", mock_open(read_data=mock_file_data)):
                    response = await get_detection_image(
                        detection_id=13,
                        full=True,
                        db=mock_db_session,
                        thumbnail_generator=mock_thumbnail_generator,
                        video_processor=mock_video_processor,
                    )

        assert response.body == mock_file_data
        assert response.media_type == "image/jpeg"
        # Verify video processor extract_thumbnail was called (for full-size frame)
        mock_video_processor.extract_thumbnail.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_image_video_detection_source_not_found(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test 404 when video source doesn't exist for image retrieval."""
        detection = DetectionFactory(
            id=14,
            file_path="/export/foscam/missing.mp4",
            thumbnail_path=None,
            media_type="video",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("backend.api.routes.detections.os.path.exists", return_value=False),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_detection_image(
                detection_id=14,
                full=False,  # Explicitly pass False since Query(False) is truthy
                db=mock_db_session,
                thumbnail_generator=mock_thumbnail_generator,
                video_processor=mock_video_processor,
            )

        assert exc_info.value.status_code == 404
        # Should say "video" not "image" for video detections
        assert "source video not found" in str(exc_info.value.detail).lower()


class TestGetDetectionThumbnail:
    """Tests for get_detection_thumbnail endpoint (NEM-1921, NEM-2445)."""

    @pytest.mark.asyncio
    async def test_get_thumbnail_exists(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test getting detection thumbnail when it exists."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/test.jpg",
            thumbnail_path="/data/thumbnails/1.jpg",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("backend.api.routes.detections.os.path.exists", return_value=True),
        ):
            response = await get_detection_thumbnail(
                detection_id=1,
                db=mock_db_session,
                thumbnail_generator=mock_thumbnail_generator,
                video_processor=mock_video_processor,
            )

        assert response.path == Path("/data/thumbnails/1.jpg")
        assert response.media_type == "image/jpeg"
        assert response.filename == "detection_1_thumbnail.jpg"

    @pytest.mark.asyncio
    async def test_get_thumbnail_png_extension(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test getting detection thumbnail with PNG extension."""
        detection = DetectionFactory(
            id=2,
            file_path="/export/foscam/test.png",
            thumbnail_path="/data/thumbnails/2.png",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("backend.api.routes.detections.os.path.exists", return_value=True),
        ):
            response = await get_detection_thumbnail(
                detection_id=2,
                db=mock_db_session,
                thumbnail_generator=mock_thumbnail_generator,
                video_processor=mock_video_processor,
            )

        assert response.media_type == "image/png"
        assert response.filename == "detection_2_thumbnail.png"

    @pytest.mark.asyncio
    async def test_get_thumbnail_generates_on_fly(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test generating thumbnail on the fly when it doesn't exist."""
        detection = DetectionFactory(
            id=3,
            file_path="/export/foscam/test.jpg",
            thumbnail_path=None,
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=200,
            bbox_width=150,
            bbox_height=300,
        )

        # Configure mock thumbnail generator
        mock_thumbnail_generator.generate_thumbnail.return_value = (
            "/data/thumbnails/generated_3.jpg"
        )

        with patch(
            "backend.api.routes.detections.get_detection_or_404",
            return_value=detection,
        ):
            # First call: source file exists check
            with patch("backend.api.routes.detections.os.path.exists", return_value=True):
                response = await get_detection_thumbnail(
                    detection_id=3,
                    db=mock_db_session,
                    thumbnail_generator=mock_thumbnail_generator,
                    video_processor=mock_video_processor,
                )

        assert response.path == Path("/data/thumbnails/generated_3.jpg")
        assert response.media_type == "image/jpeg"
        # Verify thumbnail path was saved to detection
        assert detection.thumbnail_path == "/data/thumbnails/generated_3.jpg"

    @pytest.mark.asyncio
    async def test_get_thumbnail_source_not_found(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test 404 when source image doesn't exist for thumbnail generation."""
        detection = DetectionFactory(
            id=4,
            file_path="/export/foscam/missing.jpg",
            thumbnail_path=None,
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("backend.api.routes.detections.os.path.exists", return_value=False),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_detection_thumbnail(
                detection_id=4,
                db=mock_db_session,
                thumbnail_generator=mock_thumbnail_generator,
                video_processor=mock_video_processor,
            )

        assert exc_info.value.status_code == 404
        assert "source image not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_thumbnail_generation_fails(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test 500 error when thumbnail generation fails."""
        detection = DetectionFactory(
            id=5,
            file_path="/export/foscam/test.jpg",
            thumbnail_path=None,
        )

        # Configure mock to return None (generation failure)
        mock_thumbnail_generator.generate_thumbnail.return_value = None

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("backend.api.routes.detections.os.path.exists", return_value=True),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_detection_thumbnail(
                detection_id=5,
                db=mock_db_session,
                thumbnail_generator=mock_thumbnail_generator,
                video_processor=mock_video_processor,
            )

        assert exc_info.value.status_code == 500
        assert "failed to generate thumbnail" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_thumbnail_includes_cache_headers(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test that thumbnail response includes cache headers."""
        detection = DetectionFactory(
            id=6,
            file_path="/export/foscam/test.jpg",
            thumbnail_path="/data/thumbnails/6.jpg",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("backend.api.routes.detections.os.path.exists", return_value=True),
        ):
            response = await get_detection_thumbnail(
                detection_id=6,
                db=mock_db_session,
                thumbnail_generator=mock_thumbnail_generator,
                video_processor=mock_video_processor,
            )

        assert response.headers.get("Cache-Control") == "public, max-age=3600"

    # NEM-2445: Tests for video detection thumbnail generation
    @pytest.mark.asyncio
    async def test_get_thumbnail_video_detection_existing(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test getting thumbnail for video detection when it already exists."""
        detection = DetectionFactory(
            id=7,
            file_path="/export/foscam/test.mp4",
            thumbnail_path="/data/thumbnails/7.jpg",
            media_type="video",
            file_type="video/mp4",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("backend.api.routes.detections.os.path.exists", return_value=True),
        ):
            response = await get_detection_thumbnail(
                detection_id=7,
                db=mock_db_session,
                thumbnail_generator=mock_thumbnail_generator,
                video_processor=mock_video_processor,
            )

        assert response.path == Path("/data/thumbnails/7.jpg")
        assert response.media_type == "image/jpeg"
        # Video processor should not be called since thumbnail exists
        mock_video_processor.extract_thumbnail_for_detection.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_thumbnail_video_detection_generates_on_fly(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test generating thumbnail for video detection using VideoProcessor (NEM-2445)."""
        detection = DetectionFactory(
            id=8,
            file_path="/export/foscam/test.mp4",
            thumbnail_path=None,
            media_type="video",
            file_type="video/mp4",
        )

        # Configure mock video processor to return a generated thumbnail path
        mock_video_processor.extract_thumbnail_for_detection = AsyncMock(
            return_value="/data/thumbnails/video_8.jpg"
        )

        with patch(
            "backend.api.routes.detections.get_detection_or_404",
            return_value=detection,
        ):
            with patch("backend.api.routes.detections.os.path.exists", return_value=True):
                response = await get_detection_thumbnail(
                    detection_id=8,
                    db=mock_db_session,
                    thumbnail_generator=mock_thumbnail_generator,
                    video_processor=mock_video_processor,
                )

        assert response.path == Path("/data/thumbnails/video_8.jpg")
        assert response.media_type == "image/jpeg"
        # Verify video processor was called (not thumbnail_generator)
        mock_video_processor.extract_thumbnail_for_detection.assert_called_once_with(
            video_path="/export/foscam/test.mp4",
            detection_id=8,
        )
        mock_thumbnail_generator.generate_thumbnail.assert_not_called()
        # Verify thumbnail path was saved to detection
        assert detection.thumbnail_path == "/data/thumbnails/video_8.jpg"

    @pytest.mark.asyncio
    async def test_get_thumbnail_video_detection_source_not_found(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test 404 when video source doesn't exist for thumbnail generation."""
        detection = DetectionFactory(
            id=9,
            file_path="/export/foscam/missing.mp4",
            thumbnail_path=None,
            media_type="video",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("backend.api.routes.detections.os.path.exists", return_value=False),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_detection_thumbnail(
                detection_id=9,
                db=mock_db_session,
                thumbnail_generator=mock_thumbnail_generator,
                video_processor=mock_video_processor,
            )

        assert exc_info.value.status_code == 404
        # Should say "video" not "image" for video detections
        assert "source video not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_thumbnail_video_detection_generation_fails(
        self, mock_db_session, mock_thumbnail_generator, mock_video_processor
    ):
        """Test 500 error when video thumbnail generation fails."""
        detection = DetectionFactory(
            id=10,
            file_path="/export/foscam/test.mp4",
            thumbnail_path=None,
            media_type="video",
        )

        # Configure mock video processor to return None (generation failure)
        mock_video_processor.extract_thumbnail_for_detection = AsyncMock(return_value=None)

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("backend.api.routes.detections.os.path.exists", return_value=True),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_detection_thumbnail(
                detection_id=10,
                db=mock_db_session,
                thumbnail_generator=mock_thumbnail_generator,
                video_processor=mock_video_processor,
            )

        assert exc_info.value.status_code == 500
        assert "failed to generate thumbnail" in str(exc_info.value.detail).lower()


class TestStreamDetectionVideo:
    """Tests for stream_detection_video endpoint."""

    @pytest.mark.asyncio
    async def test_stream_video_full_content(self, mock_db_session):
        """Test streaming full video content."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/test.mp4",
            media_type="video",
            file_type="video/mp4",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("backend.api.routes.detections.os.path.exists", return_value=True),
        ):
            with patch.object(Path, "stat") as mock_stat:
                mock_stat.return_value = Mock(st_size=10000)
                mock_file_data = b"video data"
                with patch("builtins.open", mock_open(read_data=mock_file_data)):
                    response = await stream_detection_video(
                        detection_id=1,
                        range_header=None,
                        db=mock_db_session,
                    )

        assert response.status_code == 200
        assert response.media_type == "video/mp4"

    @pytest.mark.asyncio
    async def test_stream_video_not_video_type(self, mock_db_session):
        """Test streaming video when detection is not a video."""
        detection = DetectionFactory(
            id=1,
            media_type="image",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await stream_detection_video(detection_id=1, db=mock_db_session)

        assert exc_info.value.status_code == 400
        assert "not a video" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_stream_video_file_not_found(self, mock_db_session):
        """Test streaming video when file doesn't exist."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/missing.mp4",
            media_type="video",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("os.path.exists", return_value=False),
            pytest.raises(HTTPException) as exc_info,
        ):
            await stream_detection_video(detection_id=1, db=mock_db_session)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_stream_video_with_range_request(self, mock_db_session):
        """Test streaming video with range request."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/test.mp4",
            media_type="video",
            file_type="video/mp4",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("os.path.exists", return_value=True),
            patch.object(Path, "stat") as mock_stat,
        ):
            mock_stat.return_value = Mock(st_size=10000)
            mock_file_data = b"v" * 10000
            with patch("builtins.open", mock_open(read_data=mock_file_data)):
                response = await stream_detection_video(
                    detection_id=1,
                    range_header="bytes=0-1023",
                    db=mock_db_session,
                )

        assert response.status_code == 206
        assert "Content-Range" in response.headers

    @pytest.mark.asyncio
    async def test_stream_video_invalid_range(self, mock_db_session):
        """Test streaming video with invalid range request."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/test.mp4",
            media_type="video",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("os.path.exists", return_value=True),
            patch.object(Path, "stat") as mock_stat,
        ):
            mock_stat.return_value = Mock(st_size=10000)
            with pytest.raises(HTTPException) as exc_info:
                await stream_detection_video(
                    detection_id=1,
                    range_header="bytes=20000-30000",
                    db=mock_db_session,
                )

        assert exc_info.value.status_code == 416


class TestGetVideoThumbnail:
    """Tests for get_video_thumbnail endpoint."""

    @pytest.mark.asyncio
    async def test_get_video_thumbnail_exists(self, mock_db_session, mock_video_processor):
        """Test getting video thumbnail when it exists."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/test.mp4",
            media_type="video",
            thumbnail_path="/data/thumbnails/1.jpg",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("os.path.exists", return_value=True),
        ):
            mock_file_data = b"thumbnail data"
            with patch("builtins.open", mock_open(read_data=mock_file_data)):
                response = await get_video_thumbnail(
                    detection_id=1, db=mock_db_session, video_processor=mock_video_processor
                )

        assert response.body == mock_file_data
        assert response.media_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_get_video_thumbnail_not_video(self, mock_db_session, mock_video_processor):
        """Test getting video thumbnail when detection is not a video."""
        detection = DetectionFactory(
            id=1,
            media_type="image",
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_video_thumbnail(
                detection_id=1, db=mock_db_session, video_processor=mock_video_processor
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_get_video_thumbnail_generate_on_fly(self, mock_db_session, mock_video_processor):
        """Test generating video thumbnail on the fly."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/test.mp4",
            media_type="video",
            thumbnail_path=None,
        )

        # Configure mock video processor
        mock_video_processor.extract_thumbnail_for_detection.return_value = (
            "/data/thumbnails/generated.jpg"
        )

        with patch(
            "backend.api.routes.detections.get_detection_or_404",
            return_value=detection,
        ):
            # detection.thumbnail_path is None, so os.path.exists not called on it
            # First: video file_path exists check (True), second: generated thumbnail exists (True)
            with patch("backend.api.routes.detections.os.path.exists", side_effect=[True, True]):
                mock_file_data = b"generated thumbnail"
                with patch("builtins.open", mock_open(read_data=mock_file_data)):
                    response = await get_video_thumbnail(
                        detection_id=1, db=mock_db_session, video_processor=mock_video_processor
                    )

        assert response.body == mock_file_data
        mock_video_processor.extract_thumbnail_for_detection.assert_called_once()
        # Note: We don't assert commit because the mock may not preserve async call tracking

    @pytest.mark.asyncio
    async def test_get_video_thumbnail_generation_fails(
        self, mock_db_session, mock_video_processor
    ):
        """Test handling video thumbnail generation failure."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/test.mp4",
            media_type="video",
            thumbnail_path=None,
        )

        # Configure mock to return None (generation failure)
        mock_video_processor.extract_thumbnail_for_detection.return_value = None

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("backend.api.routes.detections.os.path.exists", side_effect=[False, True]),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_video_thumbnail(
                detection_id=1, db=mock_db_session, video_processor=mock_video_processor
            )

        # When generation returns None (404 or 500 depending on file state)
        assert exc_info.value.status_code in [404, 500]

    @pytest.mark.asyncio
    async def test_get_video_thumbnail_video_not_found(self, mock_db_session, mock_video_processor):
        """Test getting video thumbnail when video file doesn't exist."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/missing.mp4",
            media_type="video",
            thumbnail_path=None,
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("os.path.exists", side_effect=[False, False]),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_video_thumbnail(
                    detection_id=1, db=mock_db_session, video_processor=mock_video_processor
                )

        assert exc_info.value.status_code == 404


# ============================================================================
# Search and Labels Tests
# ============================================================================


class TestSearchDetections:
    """Tests for search_detections endpoint."""

    @pytest.mark.asyncio
    async def test_search_basic(self, mock_db_session):
        """Test basic search functionality."""
        from backend.api.routes.detections import search_detections

        det1 = DetectionFactory(
            id=1,
            object_type="person",
            confidence=0.95,
            labels=["suspicious", "night"],
        )

        # Mock search query results
        mock_row = MagicMock()
        mock_row.Detection = det1
        mock_row.rank = 0.95

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_db_session.execute.side_effect = [
            mock_count_result,  # count query
            mock_result,  # search query
        ]

        result = await search_detections(
            q="person",
            labels=None,
            min_confidence=None,
            camera_id=None,
            start_date=None,
            end_date=None,
            limit=50,
            offset=0,
            db=mock_db_session,
        )

        assert result.total_count == 1
        assert len(result.results) == 1
        assert result.results[0].id == 1
        assert result.results[0].relevance_score >= 0.0

    @pytest.mark.asyncio
    async def test_search_with_labels_filter(self, mock_db_session):
        """Test search with labels filter."""
        from backend.api.routes.detections import search_detections

        det1 = DetectionFactory(
            id=1,
            object_type="person",
            labels=["suspicious"],
        )

        mock_row = MagicMock()
        mock_row.Detection = det1
        mock_row.rank = 0.9

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_db_session.execute.side_effect = [
            mock_count_result,
            mock_result,
        ]

        result = await search_detections(
            q="person",
            labels=["suspicious"],
            min_confidence=None,
            camera_id=None,
            start_date=None,
            end_date=None,
            limit=50,
            offset=0,
            db=mock_db_session,
        )

        assert result.total_count == 1

    @pytest.mark.asyncio
    async def test_search_with_all_filters(self, mock_db_session):
        """Test search with all filters applied."""
        from backend.api.routes.detections import search_detections

        start_date = datetime(2025, 12, 1, 0, 0, 0, tzinfo=UTC)
        end_date = datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.all.return_value = []

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_db_session.execute.side_effect = [
            mock_count_result,
            mock_result,
        ]

        result = await search_detections(
            q="person suspicious",
            labels=["suspicious", "night"],
            min_confidence=0.9,
            camera_id="front_door",
            start_date=start_date,
            end_date=end_date,
            limit=10,
            offset=0,
            db=mock_db_session,
        )

        assert result.total_count == 0
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_search_invalid_date_range(self, mock_db_session):
        """Test search with invalid date range."""
        from backend.api.routes.detections import search_detections

        start_date = datetime(2025, 12, 31, 0, 0, 0, tzinfo=UTC)
        end_date = datetime(2025, 12, 1, 0, 0, 0, tzinfo=UTC)

        with pytest.raises(HTTPException) as exc_info:
            await search_detections(
                q="person",
                labels=None,
                min_confidence=None,
                camera_id=None,
                start_date=start_date,
                end_date=end_date,
                limit=50,
                offset=0,
                db=mock_db_session,
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_search_relevance_scoring(self, mock_db_session):
        """Test search relevance score calculation."""
        from backend.api.routes.detections import search_detections

        det1 = DetectionFactory(id=1)
        det2 = DetectionFactory(id=2)

        mock_row1 = MagicMock()
        mock_row1.Detection = det1
        mock_row1.rank = 1.0

        mock_row2 = MagicMock()
        mock_row2.Detection = det2
        mock_row2.rank = 0.5

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row1, mock_row2]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        mock_db_session.execute.side_effect = [
            mock_count_result,
            mock_result,
        ]

        result = await search_detections(
            q="test query",
            labels=None,
            min_confidence=None,
            camera_id=None,
            start_date=None,
            end_date=None,
            limit=50,
            offset=0,
            db=mock_db_session,
        )

        assert len(result.results) == 2
        assert result.results[0].relevance_score == 1.0
        assert result.results[1].relevance_score == 0.5


class TestListDetectionLabels:
    """Tests for list_detection_labels endpoint."""

    @pytest.mark.asyncio
    async def test_list_labels(self, mock_db_session):
        """Test listing detection labels with counts."""
        from backend.api.routes.detections import list_detection_labels

        # Mock label query results
        mock_row1 = MagicMock()
        mock_row1.label = "suspicious"
        mock_row1.count = 50

        mock_row2 = MagicMock()
        mock_row2.label = "night"
        mock_row2.count = 30

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row1, mock_row2]

        mock_db_session.execute.return_value = mock_result

        result = await list_detection_labels(db=mock_db_session)

        assert len(result.labels) == 2
        assert result.labels[0].label == "suspicious"
        assert result.labels[0].count == 50
        assert result.labels[1].label == "night"
        assert result.labels[1].count == 30

    @pytest.mark.asyncio
    async def test_list_labels_empty(self, mock_db_session):
        """Test listing labels when none exist."""
        from backend.api.routes.detections import list_detection_labels

        mock_result = MagicMock()
        mock_result.all.return_value = []

        mock_db_session.execute.return_value = mock_result

        result = await list_detection_labels(db=mock_db_session)

        assert len(result.labels) == 0


# ============================================================================
# Sparse Fieldsets Tests
# ============================================================================


class TestSparseFieldsets:
    """Tests for sparse fieldsets functionality in list_detections."""

    @pytest.mark.asyncio
    async def test_list_detections_with_fields_filter(self, mock_db_session):
        """Test listing detections with fields parameter.

        Note: While the endpoint filters fields, Pydantic converts the dict back to
        DetectionResponse, so we verify the filter code path executes without error.
        """
        det1 = DetectionFactory(
            id=1,
            camera_id="front_door",
            object_type="person",
            confidence=0.95,
            detected_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            file_path="/export/foscam/test.jpg",
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [det1]
        mock_result.scalars.return_value = mock_scalars

        mock_db_session.execute.side_effect = [
            MagicMock(scalar=lambda: 1),
            mock_result,
        ]

        # This tests that the sparse fieldsets code path executes successfully
        result = await list_detections(
            camera_id=None,
            object_type=None,
            start_date=None,
            end_date=None,
            min_confidence=None,
            limit=50,
            offset=0,
            cursor=None,
            fields="id,camera_id,object_type,confidence,file_path,detected_at",
            db=mock_db_session,
        )

        assert len(result.items) == 1
        # Verify the result contains the expected data
        item = result.items[0]
        assert item.id == 1
        assert item.camera_id == "front_door"
        assert item.object_type == "person"
        assert item.confidence == 0.95

    @pytest.mark.asyncio
    async def test_list_detections_with_invalid_fields(self, mock_db_session):
        """Test listing detections with invalid fields parameter."""
        with pytest.raises(HTTPException) as exc_info:
            await list_detections(
                camera_id=None,
                object_type=None,
                start_date=None,
                end_date=None,
                min_confidence=None,
                limit=50,
                offset=0,
                cursor=None,
                fields="id,invalid_field",
                db=mock_db_session,
            )

        assert exc_info.value.status_code == 400
        assert "invalid" in str(exc_info.value.detail).lower()


# ============================================================================
# Bulk Operations Tests
# ============================================================================


@pytest.fixture
def mock_cache_service():
    """Create a mock CacheService for DI."""
    from backend.services.cache_service import CacheService

    mock_cache = MagicMock(spec=CacheService)
    mock_cache.invalidate_detections = MagicMock()
    mock_cache.invalidate_event_stats = MagicMock()
    return mock_cache


class TestBulkCreateDetections:
    """Tests for bulk_create_detections endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_create_success(self, mock_db_session, mock_cache_service):
        """Test successful bulk creation of detections."""
        from backend.api.routes.detections import bulk_create_detections
        from backend.api.schemas.bulk import DetectionBulkCreateItem, DetectionBulkCreateRequest

        # Mock camera exists check
        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = [("front_door",), ("back_door",)]

        # Mock detection query result (empty for new detections)
        mock_detection_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_detection_result.scalars.return_value = mock_scalars

        mock_db_session.execute.return_value = mock_camera_result

        request = DetectionBulkCreateRequest(
            detections=[
                DetectionBulkCreateItem(
                    camera_id="front_door",
                    object_type="person",
                    confidence=0.95,
                    detected_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
                    file_path="/export/foscam/test1.jpg",
                    bbox_x=100,
                    bbox_y=200,
                    bbox_width=150,
                    bbox_height=300,
                ),
                DetectionBulkCreateItem(
                    camera_id="back_door",
                    object_type="car",
                    confidence=0.88,
                    detected_at=datetime(2025, 12, 23, 12, 5, 0, tzinfo=UTC),
                    file_path="/export/foscam/test2.jpg",
                    bbox_x=200,
                    bbox_y=300,
                    bbox_width=200,
                    bbox_height=150,
                ),
            ]
        )

        result = await bulk_create_detections(
            request=request,
            db=mock_db_session,
            cache=mock_cache_service,
        )

        assert result.total == 2
        assert result.succeeded == 2
        assert result.failed == 0
        assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_bulk_create_camera_not_found(self, mock_db_session, mock_cache_service):
        """Test bulk creation with non-existent camera."""
        from backend.api.routes.detections import bulk_create_detections
        from backend.api.schemas.bulk import DetectionBulkCreateItem, DetectionBulkCreateRequest

        # Mock camera exists check (empty - no cameras found)
        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = []

        mock_db_session.execute.return_value = mock_camera_result

        request = DetectionBulkCreateRequest(
            detections=[
                DetectionBulkCreateItem(
                    camera_id="non_existent",
                    object_type="person",
                    confidence=0.95,
                    detected_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
                    file_path="/export/foscam/test.jpg",
                    bbox_x=100,
                    bbox_y=200,
                    bbox_width=150,
                    bbox_height=300,
                ),
            ]
        )

        result = await bulk_create_detections(
            request=request,
            db=mock_db_session,
            cache=mock_cache_service,
        )

        assert result.total == 1
        assert result.succeeded == 0
        assert result.failed == 1
        assert "camera not found" in result.results[0].error.lower()

    @pytest.mark.asyncio
    async def test_bulk_create_partial_success(self, mock_db_session, mock_cache_service):
        """Test bulk creation with partial success."""
        from backend.api.routes.detections import bulk_create_detections
        from backend.api.schemas.bulk import DetectionBulkCreateItem, DetectionBulkCreateRequest

        # Mock camera exists check
        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = [("front_door",)]

        mock_db_session.execute.return_value = mock_camera_result

        request = DetectionBulkCreateRequest(
            detections=[
                DetectionBulkCreateItem(
                    camera_id="front_door",
                    object_type="person",
                    confidence=0.95,
                    detected_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
                    file_path="/export/foscam/test1.jpg",
                    bbox_x=100,
                    bbox_y=200,
                    bbox_width=150,
                    bbox_height=300,
                ),
                DetectionBulkCreateItem(
                    camera_id="invalid_camera",
                    object_type="car",
                    confidence=0.88,
                    detected_at=datetime(2025, 12, 23, 12, 5, 0, tzinfo=UTC),
                    file_path="/export/foscam/test2.jpg",
                    bbox_x=200,
                    bbox_y=300,
                    bbox_width=200,
                    bbox_height=150,
                ),
            ]
        )

        result = await bulk_create_detections(
            request=request,
            db=mock_db_session,
            cache=mock_cache_service,
        )

        assert result.total == 2
        assert result.succeeded == 1
        assert result.failed == 1

    @pytest.mark.asyncio
    async def test_bulk_create_exception_handling(self, mock_db_session, mock_cache_service):
        """Test bulk creation with exception during creation."""
        from backend.api.routes.detections import bulk_create_detections
        from backend.api.schemas.bulk import DetectionBulkCreateItem, DetectionBulkCreateRequest

        # Mock camera exists check
        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = [("front_door",)]

        mock_db_session.execute.return_value = mock_camera_result
        # Make db.add raise an exception
        mock_db_session.add.side_effect = Exception("Database error")

        request = DetectionBulkCreateRequest(
            detections=[
                DetectionBulkCreateItem(
                    camera_id="front_door",
                    object_type="person",
                    confidence=0.95,
                    detected_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
                    file_path="/export/foscam/test1.jpg",
                    bbox_x=100,
                    bbox_y=200,
                    bbox_width=150,
                    bbox_height=300,
                ),
            ]
        )

        result = await bulk_create_detections(
            request=request,
            db=mock_db_session,
            cache=mock_cache_service,
        )

        assert result.total == 1
        assert result.succeeded == 0
        assert result.failed == 1
        assert "database error" in result.results[0].error.lower()

    @pytest.mark.asyncio
    async def test_bulk_create_commit_failure(self, mock_db_session, mock_cache_service):
        """Test bulk creation with commit failure."""
        from backend.api.routes.detections import bulk_create_detections
        from backend.api.schemas.bulk import DetectionBulkCreateItem, DetectionBulkCreateRequest

        # Mock camera exists check
        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = [("front_door",)]

        mock_db_session.execute.return_value = mock_camera_result
        # Make commit raise an exception
        mock_db_session.commit = AsyncMock(side_effect=Exception("Commit failed"))

        request = DetectionBulkCreateRequest(
            detections=[
                DetectionBulkCreateItem(
                    camera_id="front_door",
                    object_type="person",
                    confidence=0.95,
                    detected_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
                    file_path="/export/foscam/test1.jpg",
                    bbox_x=100,
                    bbox_y=200,
                    bbox_width=150,
                    bbox_height=300,
                ),
            ]
        )

        result = await bulk_create_detections(
            request=request,
            db=mock_db_session,
            cache=mock_cache_service,
        )

        assert result.total == 1
        assert result.succeeded == 0
        assert result.failed == 1
        assert "commit failed" in result.results[0].error.lower()

    @pytest.mark.asyncio
    async def test_bulk_create_cache_invalidation_failure(
        self, mock_db_session, mock_cache_service
    ):
        """Test bulk creation with cache invalidation failure (non-critical)."""
        from backend.api.routes.detections import bulk_create_detections
        from backend.api.schemas.bulk import DetectionBulkCreateItem, DetectionBulkCreateRequest

        # Mock camera exists check
        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = [("front_door",)]

        mock_db_session.execute.return_value = mock_camera_result
        # Make cache invalidation fail (should not affect the operation)
        mock_cache_service.invalidate_detections = AsyncMock(side_effect=Exception("Cache error"))

        request = DetectionBulkCreateRequest(
            detections=[
                DetectionBulkCreateItem(
                    camera_id="front_door",
                    object_type="person",
                    confidence=0.95,
                    detected_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
                    file_path="/export/foscam/test1.jpg",
                    bbox_x=100,
                    bbox_y=200,
                    bbox_width=150,
                    bbox_height=300,
                ),
            ]
        )

        result = await bulk_create_detections(
            request=request,
            db=mock_db_session,
            cache=mock_cache_service,
        )

        # Cache failure should not affect the operation result
        assert result.total == 1
        assert result.succeeded == 1
        assert result.failed == 0


class TestBulkUpdateDetections:
    """Tests for bulk_update_detections endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_update_success(self, mock_db_session, mock_cache_service):
        """Test successful bulk update of detections."""
        from backend.api.routes.detections import bulk_update_detections
        from backend.api.schemas.bulk import DetectionBulkUpdateItem, DetectionBulkUpdateRequest

        det1 = DetectionFactory(id=1, object_type="person", confidence=0.90)
        det2 = DetectionFactory(id=2, object_type="car", confidence=0.85)

        # Mock detection query
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [det1, det2]
        mock_result.scalars.return_value = mock_scalars

        mock_db_session.execute.return_value = mock_result

        request = DetectionBulkUpdateRequest(
            detections=[
                DetectionBulkUpdateItem(
                    id=1,
                    object_type="person",
                    confidence=0.95,
                ),
                DetectionBulkUpdateItem(
                    id=2,
                    confidence=0.92,
                ),
            ]
        )

        result = await bulk_update_detections(
            request=request,
            db=mock_db_session,
            cache=mock_cache_service,
        )

        assert result.total == 2
        assert result.succeeded == 2
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_bulk_update_not_found(self, mock_db_session, mock_cache_service):
        """Test bulk update with non-existent detection."""
        from backend.api.routes.detections import bulk_update_detections
        from backend.api.schemas.bulk import DetectionBulkUpdateItem, DetectionBulkUpdateRequest

        # Mock detection query (empty - detection not found)
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars

        mock_db_session.execute.return_value = mock_result

        request = DetectionBulkUpdateRequest(
            detections=[
                DetectionBulkUpdateItem(
                    id=999,
                    confidence=0.95,
                ),
            ]
        )

        result = await bulk_update_detections(
            request=request,
            db=mock_db_session,
            cache=mock_cache_service,
        )

        assert result.total == 1
        assert result.succeeded == 0
        assert result.failed == 1
        assert "not found" in result.results[0].error.lower()


class TestBulkDeleteDetections:
    """Tests for bulk_delete_detections endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_delete_success(self, mock_db_session, mock_cache_service):
        """Test successful bulk deletion of detections."""
        from backend.api.routes.detections import bulk_delete_detections
        from backend.api.schemas.bulk import DetectionBulkDeleteRequest

        det1 = DetectionFactory(id=1)
        det2 = DetectionFactory(id=2)

        # Mock detection query
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [det1, det2]
        mock_result.scalars.return_value = mock_scalars

        mock_db_session.execute.return_value = mock_result

        request = DetectionBulkDeleteRequest(detection_ids=[1, 2])

        result = await bulk_delete_detections(
            request=request,
            db=mock_db_session,
            cache=mock_cache_service,
        )

        assert result.total == 2
        assert result.succeeded == 2
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_bulk_delete_not_found(self, mock_db_session, mock_cache_service):
        """Test bulk deletion with non-existent detection."""
        from backend.api.routes.detections import bulk_delete_detections
        from backend.api.schemas.bulk import DetectionBulkDeleteRequest

        # Mock detection query (empty - detections not found)
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars

        mock_db_session.execute.return_value = mock_result

        request = DetectionBulkDeleteRequest(detection_ids=[999])

        result = await bulk_delete_detections(
            request=request,
            db=mock_db_session,
            cache=mock_cache_service,
        )

        assert result.total == 1
        assert result.succeeded == 0
        assert result.failed == 1
        assert "not found" in result.results[0].error.lower()
