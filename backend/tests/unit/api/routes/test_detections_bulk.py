"""Unit tests for detection bulk operation schemas and validation.

Tests the Pydantic schemas used for bulk detection operations including
create, update, and delete requests.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.bulk import (
    BulkItemResult,
    BulkOperationResponse,
    BulkOperationStatus,
    DetectionBulkCreateItem,
    DetectionBulkCreateRequest,
    DetectionBulkDeleteRequest,
    DetectionBulkUpdateItem,
    DetectionBulkUpdateRequest,
)


class TestBulkOperationStatus:
    """Tests for the BulkOperationStatus enum (shared with events)."""

    def test_status_values(self) -> None:
        """Test that all expected status values exist."""
        assert BulkOperationStatus.SUCCESS == "success"
        assert BulkOperationStatus.FAILED == "failed"
        assert BulkOperationStatus.SKIPPED == "skipped"


class TestBulkItemResult:
    """Tests for the BulkItemResult schema (shared with events)."""

    def test_valid_success_result(self) -> None:
        """Test creating a successful result."""
        result = BulkItemResult(
            index=0,
            status=BulkOperationStatus.SUCCESS,
            id=456,
            error=None,
        )
        assert result.index == 0
        assert result.status == BulkOperationStatus.SUCCESS
        assert result.id == 456
        assert result.error is None

    def test_valid_failed_result(self) -> None:
        """Test creating a failed result with error message."""
        result = BulkItemResult(
            index=3,
            status=BulkOperationStatus.FAILED,
            id=None,
            error="Detection not found",
        )
        assert result.index == 3
        assert result.status == BulkOperationStatus.FAILED
        assert result.id is None
        assert result.error == "Detection not found"


class TestDetectionBulkCreateItem:
    """Tests for the DetectionBulkCreateItem schema."""

    def test_valid_create_item(self) -> None:
        """Test creating a valid detection create item."""
        item = DetectionBulkCreateItem(
            camera_id="front_door",
            object_type="person",
            confidence=0.95,
            detected_at=datetime.now(UTC),
            file_path="/path/to/image.jpg",
            bbox_x=100,
            bbox_y=200,
            bbox_width=150,
            bbox_height=300,
        )
        assert item.camera_id == "front_door"
        assert item.object_type == "person"
        assert item.confidence == 0.95

    def test_camera_id_pattern_validation(self) -> None:
        """Test that camera_id follows the required pattern."""
        # Valid patterns
        DetectionBulkCreateItem(
            camera_id="front_door",
            object_type="person",
            confidence=0.9,
            detected_at=datetime.now(UTC),
            file_path="/path/to/image.jpg",
            bbox_x=0,
            bbox_y=0,
            bbox_width=100,
            bbox_height=100,
        )
        DetectionBulkCreateItem(
            camera_id="camera-1",
            object_type="vehicle",
            confidence=0.85,
            detected_at=datetime.now(UTC),
            file_path="/path/to/image.jpg",
            bbox_x=0,
            bbox_y=0,
            bbox_width=100,
            bbox_height=100,
        )

        # Invalid pattern (spaces)
        with pytest.raises(ValidationError):
            DetectionBulkCreateItem(
                camera_id="front door",
                object_type="person",
                confidence=0.9,
                detected_at=datetime.now(UTC),
                file_path="/path/to/image.jpg",
                bbox_x=0,
                bbox_y=0,
                bbox_width=100,
                bbox_height=100,
            )

    def test_confidence_range(self) -> None:
        """Test that confidence must be 0.0-1.0."""
        # Valid range
        DetectionBulkCreateItem(
            camera_id="test",
            object_type="person",
            confidence=0.0,
            detected_at=datetime.now(UTC),
            file_path="/path/to/image.jpg",
            bbox_x=0,
            bbox_y=0,
            bbox_width=100,
            bbox_height=100,
        )
        DetectionBulkCreateItem(
            camera_id="test",
            object_type="person",
            confidence=1.0,
            detected_at=datetime.now(UTC),
            file_path="/path/to/image.jpg",
            bbox_x=0,
            bbox_y=0,
            bbox_width=100,
            bbox_height=100,
        )

        # Out of range
        with pytest.raises(ValidationError):
            DetectionBulkCreateItem(
                camera_id="test",
                object_type="person",
                confidence=1.1,
                detected_at=datetime.now(UTC),
                file_path="/path/to/image.jpg",
                bbox_x=0,
                bbox_y=0,
                bbox_width=100,
                bbox_height=100,
            )
        with pytest.raises(ValidationError):
            DetectionBulkCreateItem(
                camera_id="test",
                object_type="person",
                confidence=-0.1,
                detected_at=datetime.now(UTC),
                file_path="/path/to/image.jpg",
                bbox_x=0,
                bbox_y=0,
                bbox_width=100,
                bbox_height=100,
            )

    def test_bbox_dimensions_validation(self) -> None:
        """Test bounding box dimension constraints."""
        # bbox_x and bbox_y can be 0
        DetectionBulkCreateItem(
            camera_id="test",
            object_type="person",
            confidence=0.9,
            detected_at=datetime.now(UTC),
            file_path="/path/to/image.jpg",
            bbox_x=0,
            bbox_y=0,
            bbox_width=100,
            bbox_height=100,
        )

        # bbox_x and bbox_y cannot be negative
        with pytest.raises(ValidationError):
            DetectionBulkCreateItem(
                camera_id="test",
                object_type="person",
                confidence=0.9,
                detected_at=datetime.now(UTC),
                file_path="/path/to/image.jpg",
                bbox_x=-1,
                bbox_y=0,
                bbox_width=100,
                bbox_height=100,
            )

        # bbox_width and bbox_height must be > 0
        with pytest.raises(ValidationError):
            DetectionBulkCreateItem(
                camera_id="test",
                object_type="person",
                confidence=0.9,
                detected_at=datetime.now(UTC),
                file_path="/path/to/image.jpg",
                bbox_x=0,
                bbox_y=0,
                bbox_width=0,
                bbox_height=100,
            )

    def test_enrichment_data_optional(self) -> None:
        """Test that enrichment_data is optional."""
        item = DetectionBulkCreateItem(
            camera_id="test",
            object_type="person",
            confidence=0.9,
            detected_at=datetime.now(UTC),
            file_path="/path/to/image.jpg",
            bbox_x=0,
            bbox_y=0,
            bbox_width=100,
            bbox_height=100,
        )
        assert item.enrichment_data is None

        item_with_enrichment = DetectionBulkCreateItem(
            camera_id="test",
            object_type="person",
            confidence=0.9,
            detected_at=datetime.now(UTC),
            file_path="/path/to/image.jpg",
            bbox_x=0,
            bbox_y=0,
            bbox_width=100,
            bbox_height=100,
            enrichment_data={"faces": [], "license_plates": []},
        )
        assert item_with_enrichment.enrichment_data is not None


class TestDetectionBulkCreateRequest:
    """Tests for the DetectionBulkCreateRequest schema."""

    def test_valid_request(self) -> None:
        """Test creating a valid bulk create request."""
        request = DetectionBulkCreateRequest(
            detections=[
                DetectionBulkCreateItem(
                    camera_id="front_door",
                    object_type="person",
                    confidence=0.95,
                    detected_at=datetime.now(UTC),
                    file_path="/path/to/image1.jpg",
                    bbox_x=100,
                    bbox_y=200,
                    bbox_width=150,
                    bbox_height=300,
                ),
                DetectionBulkCreateItem(
                    camera_id="back_door",
                    object_type="vehicle",
                    confidence=0.88,
                    detected_at=datetime.now(UTC),
                    file_path="/path/to/image2.jpg",
                    bbox_x=50,
                    bbox_y=100,
                    bbox_width=200,
                    bbox_height=150,
                ),
            ]
        )
        assert len(request.detections) == 2

    def test_detections_list_cannot_be_empty(self) -> None:
        """Test that detections list must have at least 1 item."""
        with pytest.raises(ValidationError):
            DetectionBulkCreateRequest(detections=[])

    def test_detections_list_max_length(self) -> None:
        """Test that detections list has max 100 items."""
        detections = [
            DetectionBulkCreateItem(
                camera_id=f"camera_{i}",
                object_type="person",
                confidence=0.9,
                detected_at=datetime.now(UTC),
                file_path=f"/path/to/image_{i}.jpg",
                bbox_x=0,
                bbox_y=0,
                bbox_width=100,
                bbox_height=100,
            )
            for i in range(101)
        ]
        with pytest.raises(ValidationError):
            DetectionBulkCreateRequest(detections=detections)


class TestDetectionBulkUpdateItem:
    """Tests for the DetectionBulkUpdateItem schema."""

    def test_valid_update_item(self) -> None:
        """Test creating a valid update item."""
        item = DetectionBulkUpdateItem(
            id=123,
            object_type="vehicle",
            confidence=0.92,
        )
        assert item.id == 123
        assert item.object_type == "vehicle"
        assert item.confidence == 0.92

    def test_id_must_be_positive(self) -> None:
        """Test that id must be > 0."""
        with pytest.raises(ValidationError):
            DetectionBulkUpdateItem(id=0)
        with pytest.raises(ValidationError):
            DetectionBulkUpdateItem(id=-1)

    def test_confidence_range_in_update(self) -> None:
        """Test that confidence in update follows 0.0-1.0 range."""
        # Valid
        DetectionBulkUpdateItem(id=1, confidence=0.5)

        # Invalid
        with pytest.raises(ValidationError):
            DetectionBulkUpdateItem(id=1, confidence=1.5)

    def test_all_fields_optional_except_id(self) -> None:
        """Test that all fields except id are optional."""
        item = DetectionBulkUpdateItem(id=1)
        assert item.object_type is None
        assert item.confidence is None
        assert item.enrichment_data is None

    def test_enrichment_data_update(self) -> None:
        """Test updating enrichment_data."""
        item = DetectionBulkUpdateItem(
            id=1,
            enrichment_data={"faces": [{"confidence": 0.98}]},
        )
        assert item.enrichment_data is not None
        assert "faces" in item.enrichment_data


class TestDetectionBulkUpdateRequest:
    """Tests for the DetectionBulkUpdateRequest schema."""

    def test_valid_request(self) -> None:
        """Test creating a valid bulk update request."""
        request = DetectionBulkUpdateRequest(
            detections=[
                DetectionBulkUpdateItem(id=1, object_type="truck"),
                DetectionBulkUpdateItem(id=2, confidence=0.75),
            ]
        )
        assert len(request.detections) == 2

    def test_detections_list_cannot_be_empty(self) -> None:
        """Test that detections list must have at least 1 item."""
        with pytest.raises(ValidationError):
            DetectionBulkUpdateRequest(detections=[])

    def test_detections_list_max_length(self) -> None:
        """Test that detections list has max 100 items."""
        detections = [DetectionBulkUpdateItem(id=i) for i in range(1, 102)]
        with pytest.raises(ValidationError):
            DetectionBulkUpdateRequest(detections=detections)


class TestDetectionBulkDeleteRequest:
    """Tests for the DetectionBulkDeleteRequest schema."""

    def test_valid_request(self) -> None:
        """Test creating a valid bulk delete request."""
        request = DetectionBulkDeleteRequest(
            detection_ids=[1, 2, 3, 4, 5],
        )
        assert len(request.detection_ids) == 5

    def test_detection_ids_cannot_be_empty(self) -> None:
        """Test that detection_ids must have at least 1 item."""
        with pytest.raises(ValidationError):
            DetectionBulkDeleteRequest(detection_ids=[])

    def test_detection_ids_max_length(self) -> None:
        """Test that detection_ids has max 100 items."""
        with pytest.raises(ValidationError):
            DetectionBulkDeleteRequest(detection_ids=list(range(1, 102)))


class TestBulkOperationResponseForDetections:
    """Tests for BulkOperationResponse used with detections."""

    def test_response_with_mixed_results(self) -> None:
        """Test response with mix of success, failed, and skipped items."""
        response = BulkOperationResponse(
            total=10,
            succeeded=6,
            failed=3,
            skipped=1,
            results=[
                BulkItemResult(index=0, status=BulkOperationStatus.SUCCESS, id=100),
                BulkItemResult(index=1, status=BulkOperationStatus.SUCCESS, id=101),
                BulkItemResult(
                    index=2, status=BulkOperationStatus.FAILED, error="Camera not found"
                ),
                BulkItemResult(index=3, status=BulkOperationStatus.SKIPPED),
            ],
        )
        assert response.total == 10
        assert response.succeeded == 6
        assert response.failed == 3
        assert response.skipped == 1

    def test_empty_results_list(self) -> None:
        """Test response with empty results list (all operations processed)."""
        response = BulkOperationResponse(
            total=0,
            succeeded=0,
            failed=0,
            skipped=0,
            results=[],
        )
        assert len(response.results) == 0
