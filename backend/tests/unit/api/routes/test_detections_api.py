"""Unit tests for detections API schemas and validation."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.detections import DetectionListResponse, DetectionResponse


class TestDetectionResponse:
    """Tests for DetectionResponse schema."""

    def test_valid_detection_response(self):
        """Test creating a valid detection response."""
        detection = DetectionResponse(
            id=1,
            camera_id="cam-123",
            file_path="/export/foscam/front_door/test.jpg",
            file_type="image/jpeg",
            detected_at=datetime(2025, 12, 23, 12, 0, 0),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=150,
            bbox_width=200,
            bbox_height=400,
            thumbnail_path="/data/thumbnails/1_thumb.jpg",
        )
        assert detection.id == 1
        assert detection.camera_id == "cam-123"
        assert detection.object_type == "person"
        assert detection.confidence == 0.95

    def test_minimal_detection_response(self):
        """Test creating a detection response with only required fields."""
        detection = DetectionResponse(
            id=1,
            camera_id="cam-123",
            file_path="/path/to/image.jpg",
            detected_at=datetime(2025, 12, 23, 12, 0, 0),
        )
        assert detection.id == 1
        assert detection.file_type is None
        assert detection.object_type is None
        assert detection.confidence is None

    def test_detection_response_missing_required_field(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(ValidationError):
            DetectionResponse(
                id=1,
                # missing camera_id
                file_path="/path/to/image.jpg",
                detected_at=datetime(2025, 12, 23, 12, 0, 0),
            )


class TestDetectionListResponse:
    """Tests for DetectionListResponse schema."""

    def test_valid_list_response(self):
        """Test creating a valid detection list response."""
        response = DetectionListResponse(
            detections=[
                DetectionResponse(
                    id=1,
                    camera_id="cam-123",
                    file_path="/path/1.jpg",
                    detected_at=datetime(2025, 12, 23, 12, 0, 0),
                    object_type="person",
                    confidence=0.95,
                ),
                DetectionResponse(
                    id=2,
                    camera_id="cam-123",
                    file_path="/path/2.jpg",
                    detected_at=datetime(2025, 12, 23, 12, 1, 0),
                    object_type="car",
                    confidence=0.85,
                ),
            ],
            count=2,
            limit=50,
            offset=0,
        )
        assert len(response.detections) == 2
        assert response.count == 2
        assert response.limit == 50
        assert response.offset == 0

    def test_empty_list_response(self):
        """Test creating an empty detection list response."""
        response = DetectionListResponse(
            detections=[],
            count=0,
            limit=50,
            offset=0,
        )
        assert len(response.detections) == 0
        assert response.count == 0

    def test_list_response_missing_required_field(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(ValidationError):
            DetectionListResponse(
                detections=[],
                # missing count, limit, offset
            )
