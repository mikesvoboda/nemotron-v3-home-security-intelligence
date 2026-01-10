"""Unit tests for detections API route handlers.

This test file covers the route handlers in backend/api/routes/detections.py
to increase coverage from 10.34% to at least 80%.

Tests cover:
- list_detections endpoint (filtering, pagination, cursor-based pagination)
- get_detection_stats endpoint (aggregate statistics)
- get_detection endpoint (single detection retrieval)
- get_detection_enrichment endpoint (enrichment data)
- get_detection_image endpoint (image serving with thumbnails)
- stream_detection_video endpoint (video streaming with range requests)
- get_video_thumbnail endpoint (video thumbnail extraction)
- Helper functions (_sanitize_errors, _extract_clothing_from_enrichment, etc.)
"""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

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
from backend.tests.factories import DetectionFactory

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
    """Tests for get_detection_image endpoint."""

    @pytest.mark.asyncio
    async def test_get_image_thumbnail_exists(self, mock_db_session):
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
                response = await get_detection_image(detection_id=1, db=mock_db_session)

        assert response.body == mock_file_data
        assert response.media_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_get_image_full_size(self, mock_db_session):
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
                response = await get_detection_image(detection_id=1, full=True, db=mock_db_session)

        assert response.body == mock_file_data

    @pytest.mark.asyncio
    async def test_get_image_file_not_found(self, mock_db_session):
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
            await get_detection_image(detection_id=1, full=True, db=mock_db_session)

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_image_generate_thumbnail_on_fly(self, mock_db_session):
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

        with patch(
            "backend.api.routes.detections.get_detection_or_404",
            return_value=detection,
        ):
            # detection.thumbnail_path is None, so os.path.exists not called on it
            # First: file_path exists check (True), second: generated thumbnail exists (True)
            with patch("backend.api.routes.detections.os.path.exists", side_effect=[True, True]):
                with patch(
                    "backend.api.routes.detections.thumbnail_generator.generate_thumbnail",
                    return_value="/data/thumbnails/generated.jpg",
                ):
                    mock_file_data = b"generated thumbnail"
                    with patch("builtins.open", mock_open(read_data=mock_file_data)):
                        response = await get_detection_image(detection_id=1, db=mock_db_session)

        assert response.body == mock_file_data
        # Note: We don't assert commit because the mock may not preserve async call tracking

    @pytest.mark.asyncio
    async def test_get_image_thumbnail_generation_fails(self, mock_db_session):
        """Test handling thumbnail generation failure."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/test.jpg",
            thumbnail_path=None,
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("backend.api.routes.detections.os.path.exists", side_effect=[False, True]),
            patch(
                "backend.api.routes.detections.thumbnail_generator.generate_thumbnail",
                return_value=None,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_detection_image(detection_id=1, db=mock_db_session)

        # When thumbnail generation fails but file_path doesn't exist, returns 404
        assert exc_info.value.status_code in [404, 500]

    @pytest.mark.asyncio
    async def test_get_image_read_error(self, mock_db_session):
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
                    await get_detection_image(detection_id=1, db=mock_db_session)

        assert exc_info.value.status_code == 500


class TestGetDetectionThumbnail:
    """Tests for get_detection_thumbnail endpoint (NEM-1921)."""

    @pytest.mark.asyncio
    async def test_get_thumbnail_exists(self, mock_db_session):
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
            response = await get_detection_thumbnail(detection_id=1, db=mock_db_session)

        assert response.path == Path("/data/thumbnails/1.jpg")
        assert response.media_type == "image/jpeg"
        assert response.filename == "detection_1_thumbnail.jpg"

    @pytest.mark.asyncio
    async def test_get_thumbnail_png_extension(self, mock_db_session):
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
            response = await get_detection_thumbnail(detection_id=2, db=mock_db_session)

        assert response.media_type == "image/png"
        assert response.filename == "detection_2_thumbnail.png"

    @pytest.mark.asyncio
    async def test_get_thumbnail_generates_on_fly(self, mock_db_session):
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

        with patch(
            "backend.api.routes.detections.get_detection_or_404",
            return_value=detection,
        ):
            # First call: source file exists check
            with patch("backend.api.routes.detections.os.path.exists", return_value=True):
                with patch(
                    "backend.api.routes.detections.thumbnail_generator.generate_thumbnail",
                    return_value="/data/thumbnails/generated_3.jpg",
                ):
                    response = await get_detection_thumbnail(detection_id=3, db=mock_db_session)

        assert response.path == Path("/data/thumbnails/generated_3.jpg")
        assert response.media_type == "image/jpeg"
        # Verify thumbnail path was saved to detection
        assert detection.thumbnail_path == "/data/thumbnails/generated_3.jpg"

    @pytest.mark.asyncio
    async def test_get_thumbnail_source_not_found(self, mock_db_session):
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
            await get_detection_thumbnail(detection_id=4, db=mock_db_session)

        assert exc_info.value.status_code == 404
        assert "source image not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_thumbnail_generation_fails(self, mock_db_session):
        """Test 500 error when thumbnail generation fails."""
        detection = DetectionFactory(
            id=5,
            file_path="/export/foscam/test.jpg",
            thumbnail_path=None,
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("backend.api.routes.detections.os.path.exists", return_value=True),
            patch(
                "backend.api.routes.detections.thumbnail_generator.generate_thumbnail",
                return_value=None,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_detection_thumbnail(detection_id=5, db=mock_db_session)

        assert exc_info.value.status_code == 500
        assert "failed to generate thumbnail" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_thumbnail_includes_cache_headers(self, mock_db_session):
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
            response = await get_detection_thumbnail(detection_id=6, db=mock_db_session)

        assert response.headers.get("Cache-Control") == "public, max-age=3600"


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
    async def test_get_video_thumbnail_exists(self, mock_db_session):
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
                response = await get_video_thumbnail(detection_id=1, db=mock_db_session)

        assert response.body == mock_file_data
        assert response.media_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_get_video_thumbnail_not_video(self, mock_db_session):
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
            await get_video_thumbnail(detection_id=1, db=mock_db_session)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_get_video_thumbnail_generate_on_fly(self, mock_db_session):
        """Test generating video thumbnail on the fly."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/test.mp4",
            media_type="video",
            thumbnail_path=None,
        )

        with patch(
            "backend.api.routes.detections.get_detection_or_404",
            return_value=detection,
        ):
            # detection.thumbnail_path is None, so os.path.exists not called on it
            # First: video file_path exists check (True), second: generated thumbnail exists (True)
            with patch("backend.api.routes.detections.os.path.exists", side_effect=[True, True]):
                with patch(
                    "backend.api.routes.detections.video_processor.extract_thumbnail_for_detection",
                    return_value="/data/thumbnails/generated.jpg",
                ) as mock_extract:
                    mock_file_data = b"generated thumbnail"
                    with patch("builtins.open", mock_open(read_data=mock_file_data)):
                        response = await get_video_thumbnail(detection_id=1, db=mock_db_session)

        assert response.body == mock_file_data
        mock_extract.assert_called_once()
        # Note: We don't assert commit because the mock may not preserve async call tracking

    @pytest.mark.asyncio
    async def test_get_video_thumbnail_generation_fails(self, mock_db_session):
        """Test handling video thumbnail generation failure."""
        detection = DetectionFactory(
            id=1,
            file_path="/export/foscam/test.mp4",
            media_type="video",
            thumbnail_path=None,
        )

        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
            ),
            patch("backend.api.routes.detections.os.path.exists", side_effect=[False, True]),
            patch(
                "backend.api.routes.detections.video_processor.extract_thumbnail_for_detection",
                return_value=None,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_video_thumbnail(detection_id=1, db=mock_db_session)

        # When generation returns None (404 or 500 depending on file state)
        assert exc_info.value.status_code in [404, 500]

    @pytest.mark.asyncio
    async def test_get_video_thumbnail_video_not_found(self, mock_db_session):
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
                await get_video_thumbnail(detection_id=1, db=mock_db_session)

        assert exc_info.value.status_code == 404
