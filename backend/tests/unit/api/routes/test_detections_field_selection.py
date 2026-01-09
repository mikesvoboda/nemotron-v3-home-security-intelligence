"""Unit tests for detections API field selection (sparse fieldsets).

Tests for the fields query parameter on the list detections endpoint that enables
clients to request only specific fields in the response.

TDD Approach: These tests are written FIRST, before the implementation.
"""

from datetime import UTC, datetime
from typing import ClassVar

import pytest


class TestDetectionsFieldSelectionSchema:
    """Schema-level tests for detections field selection behavior."""

    # Define the valid detection fields that can be requested
    VALID_DETECTION_FIELDS: ClassVar[set[str]] = {
        "id",
        "camera_id",
        "file_path",
        "file_type",
        "detected_at",
        "object_type",
        "confidence",
        "bbox_x",
        "bbox_y",
        "bbox_width",
        "bbox_height",
        "thumbnail_path",
        "media_type",
        "duration",
        "video_codec",
        "video_width",
        "video_height",
        "enrichment_data",
    }

    def test_detection_response_fields_documentation(self):
        """Document the fields available in DetectionResponse for field selection."""
        # This test documents the expected fields for reference
        assert "id" in self.VALID_DETECTION_FIELDS
        assert "camera_id" in self.VALID_DETECTION_FIELDS
        assert "file_path" in self.VALID_DETECTION_FIELDS
        assert "file_type" in self.VALID_DETECTION_FIELDS
        assert "detected_at" in self.VALID_DETECTION_FIELDS
        assert "object_type" in self.VALID_DETECTION_FIELDS
        assert "confidence" in self.VALID_DETECTION_FIELDS
        assert "bbox_x" in self.VALID_DETECTION_FIELDS
        assert "bbox_y" in self.VALID_DETECTION_FIELDS
        assert "bbox_width" in self.VALID_DETECTION_FIELDS
        assert "bbox_height" in self.VALID_DETECTION_FIELDS
        assert "thumbnail_path" in self.VALID_DETECTION_FIELDS
        assert "media_type" in self.VALID_DETECTION_FIELDS
        assert "enrichment_data" in self.VALID_DETECTION_FIELDS


class TestDetectionsFieldSelectionLogic:
    """Tests for field selection logic in list_detections endpoint."""

    def test_filter_detection_dict_single_field(self):
        """Test filtering detection dict to single field."""
        from backend.api.utils.field_filter import filter_fields

        detection_dict = {
            "id": 1,
            "camera_id": "front_door",
            "file_path": "/export/foscam/front_door/image.jpg",
            "file_type": "image/jpeg",
            "detected_at": datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": 100,
            "bbox_y": 150,
            "bbox_width": 200,
            "bbox_height": 400,
            "thumbnail_path": "/data/thumbnails/1_thumb.jpg",
            "media_type": "image",
        }

        result = filter_fields(detection_dict, {"id"})
        assert result == {"id": 1}

    def test_filter_detection_dict_multiple_fields(self):
        """Test filtering detection dict to multiple fields."""
        from backend.api.utils.field_filter import filter_fields

        detection_dict = {
            "id": 1,
            "camera_id": "front_door",
            "file_path": "/export/foscam/front_door/image.jpg",
            "file_type": "image/jpeg",
            "detected_at": datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": 100,
            "bbox_y": 150,
            "bbox_width": 200,
            "bbox_height": 400,
            "thumbnail_path": "/data/thumbnails/1_thumb.jpg",
            "media_type": "image",
        }

        result = filter_fields(detection_dict, {"id", "camera_id", "object_type", "confidence"})
        assert result == {
            "id": 1,
            "camera_id": "front_door",
            "object_type": "person",
            "confidence": 0.95,
        }

    def test_filter_detection_with_enrichment_data(self):
        """Test that enrichment_data nested dict is preserved when selected."""
        from backend.api.utils.field_filter import filter_fields

        detection_dict = {
            "id": 1,
            "camera_id": "front_door",
            "object_type": "person",
            "enrichment_data": {
                "vehicle": None,
                "person": {
                    "clothing_description": "dark jacket",
                    "action": "walking",
                    "carrying": ["backpack"],
                    "is_suspicious": False,
                },
                "pet": None,
            },
        }

        result = filter_fields(detection_dict, {"id", "enrichment_data"})
        assert result == {
            "id": 1,
            "enrichment_data": {
                "vehicle": None,
                "person": {
                    "clothing_description": "dark jacket",
                    "action": "walking",
                    "carrying": ["backpack"],
                    "is_suspicious": False,
                },
                "pet": None,
            },
        }

    def test_filter_detection_bbox_fields(self):
        """Test filtering to bounding box fields."""
        from backend.api.utils.field_filter import filter_fields

        detection_dict = {
            "id": 1,
            "camera_id": "front_door",
            "bbox_x": 100,
            "bbox_y": 150,
            "bbox_width": 200,
            "bbox_height": 400,
            "confidence": 0.95,
        }

        result = filter_fields(
            detection_dict, {"id", "bbox_x", "bbox_y", "bbox_width", "bbox_height"}
        )
        assert result == {
            "id": 1,
            "bbox_x": 100,
            "bbox_y": 150,
            "bbox_width": 200,
            "bbox_height": 400,
        }


class TestDetectionsFieldValidation:
    """Tests for field validation in detections endpoint."""

    VALID_DETECTION_FIELDS: ClassVar[set[str]] = {
        "id",
        "camera_id",
        "file_path",
        "file_type",
        "detected_at",
        "object_type",
        "confidence",
        "bbox_x",
        "bbox_y",
        "bbox_width",
        "bbox_height",
        "thumbnail_path",
        "media_type",
        "duration",
        "video_codec",
        "video_width",
        "video_height",
        "enrichment_data",
    }

    def test_validate_valid_fields(self):
        """Test validation passes for valid fields."""
        from backend.api.utils.field_filter import validate_fields

        requested = {"id", "camera_id", "object_type", "confidence"}
        result = validate_fields(requested, self.VALID_DETECTION_FIELDS)
        assert result == {"id", "camera_id", "object_type", "confidence"}

    def test_validate_invalid_field_raises_error(self):
        """Test validation raises error for invalid fields."""
        from backend.api.utils.field_filter import FieldFilterError, validate_fields

        requested = {"id", "invalid_field", "camera_id"}

        with pytest.raises(FieldFilterError) as exc_info:
            validate_fields(requested, self.VALID_DETECTION_FIELDS)

        assert "invalid_field" in str(exc_info.value)
        assert exc_info.value.invalid_fields == {"invalid_field"}

    def test_validate_all_fields_at_once(self):
        """Test validation with all valid detection fields."""
        from backend.api.utils.field_filter import validate_fields

        result = validate_fields(self.VALID_DETECTION_FIELDS, self.VALID_DETECTION_FIELDS)
        assert result == self.VALID_DETECTION_FIELDS


class TestDetectionsFieldSelectionUsageExample:
    """Example usage tests demonstrating the expected field selection behavior."""

    def test_typical_list_view_request(self):
        """Test typical list view request with minimal fields."""
        from backend.api.utils.field_filter import (
            filter_fields,
            parse_fields_param,
            validate_fields,
        )

        # List view typically needs: id, camera_id, object_type, confidence, detected_at
        fields_param = "id,camera_id,object_type,confidence,detected_at"
        valid_fields = {
            "id",
            "camera_id",
            "file_path",
            "file_type",
            "detected_at",
            "object_type",
            "confidence",
            "bbox_x",
            "bbox_y",
            "bbox_width",
            "bbox_height",
            "thumbnail_path",
            "media_type",
            "duration",
            "video_codec",
            "video_width",
            "video_height",
            "enrichment_data",
        }

        # Parse
        requested = parse_fields_param(fields_param)
        assert requested == {"id", "camera_id", "object_type", "confidence", "detected_at"}

        # Validate
        validated = validate_fields(requested, valid_fields)
        assert validated == {"id", "camera_id", "object_type", "confidence", "detected_at"}

        # Apply to detection data
        detection_dict = {
            "id": 123,
            "camera_id": "front_door",
            "file_path": "/export/foscam/front_door/image.jpg",
            "file_type": "image/jpeg",
            "detected_at": datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            "object_type": "person",
            "confidence": 0.95,
            "bbox_x": 100,
            "bbox_y": 150,
            "bbox_width": 200,
            "bbox_height": 400,
            "thumbnail_path": "/data/thumbnails/123_thumb.jpg",
            "media_type": "image",
            "enrichment_data": {"person": {"clothing": "dark jacket"}},
        }

        result = filter_fields(detection_dict, validated)
        assert result == {
            "id": 123,
            "camera_id": "front_door",
            "object_type": "person",
            "confidence": 0.95,
            "detected_at": datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
        }
