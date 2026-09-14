"""Snapshot tests for API response schemas (NEM-3748).

These tests use syrupy to capture and verify the JSON schema of API response
models. Any unintended changes to the response schema will cause these tests
to fail, catching breaking API changes early.

Snapshot Testing Benefits:
1. **Contract Verification**: Ensures API responses match documented contracts
2. **Breaking Change Detection**: Catches unintended field changes
3. **Documentation**: Snapshots serve as living documentation of API schemas
4. **Regression Prevention**: Prevents accidental schema modifications

Usage:
    # Run tests normally - they verify against existing snapshots
    pytest backend/tests/unit/api/schemas/test_response_schema_snapshots.py

    # Update snapshots when intentionally changing schemas
    pytest --snapshot-update backend/tests/unit/api/schemas/test_response_schema_snapshots.py

Snapshot Files:
    Snapshots are stored in __snapshots__/ directory next to this test file.
    They should be committed to version control.
"""

from datetime import UTC, datetime

import pytest

from backend.api.schemas.camera import CameraResponse
from backend.api.schemas.detections import (
    DetectionListResponse,
    DetectionResponse,
    DetectionStatsResponse,
)
from backend.api.schemas.events import (
    EventListResponse,
    EventResponse,
)
from backend.api.schemas.feedback import EventFeedbackResponse, FeedbackStatsResponse
from backend.api.schemas.health import LivenessResponse
from backend.api.schemas.pagination import PaginationMeta

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_datetime() -> datetime:
    """Fixed datetime for reproducible snapshots."""
    return datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def sample_pagination() -> PaginationMeta:
    """Sample pagination metadata."""
    return PaginationMeta(
        total=100,
        limit=50,
        offset=0,
        next_cursor="eyJpZCI6IDUwfQ==",
        has_more=True,
    )


# =============================================================================
# Camera Response Schema Snapshots
# =============================================================================


class TestCameraResponseSnapshots:
    """Snapshot tests for camera response schemas."""

    def test_camera_response_json_schema(self, snapshot):
        """Test CameraResponse JSON schema structure."""
        schema = CameraResponse.model_json_schema()
        assert schema == snapshot

    def test_camera_response_serialization(self, snapshot, sample_datetime):
        """Test CameraResponse serialization format."""
        response = CameraResponse(
            id="front_door",
            name="Front Door Camera",
            folder_path="/export/foscam/front_door",
            status="online",
            last_seen=sample_datetime,
            created_at=sample_datetime,
        )
        serialized = response.model_dump(mode="json")
        assert serialized == snapshot


# =============================================================================
# Detection Response Schema Snapshots
# =============================================================================


class TestDetectionResponseSnapshots:
    """Snapshot tests for detection response schemas."""

    def test_detection_response_json_schema(self, snapshot):
        """Test DetectionResponse JSON schema structure."""
        schema = DetectionResponse.model_json_schema()
        assert schema == snapshot

    def test_detection_response_serialization(self, snapshot, sample_datetime):
        """Test DetectionResponse serialization format."""
        response = DetectionResponse(
            id=1,
            camera_id="front_door",
            file_path="/export/foscam/front_door/20251223_120000.jpg",
            file_type="image/jpeg",
            detected_at=sample_datetime,
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=150,
            bbox_width=200,
            bbox_height=400,
            thumbnail_path="/data/thumbnails/1_thumb.jpg",
            media_type="image",
        )
        serialized = response.model_dump(mode="json")
        assert serialized == snapshot

    def test_detection_list_response_json_schema(self, snapshot):
        """Test DetectionListResponse JSON schema structure."""
        schema = DetectionListResponse.model_json_schema()
        assert schema == snapshot

    def test_detection_stats_response_json_schema(self, snapshot):
        """Test DetectionStatsResponse JSON schema structure."""
        schema = DetectionStatsResponse.model_json_schema()
        assert schema == snapshot

    def test_detection_stats_response_serialization(self, snapshot):
        """Test DetectionStatsResponse serialization format."""
        response = DetectionStatsResponse(
            total_detections=107,
            detections_by_class={"person": 50, "car": 30, "truck": 20, "bicycle": 7},
            object_class_distribution=[
                {"object_class": "person", "count": 50},
                {"object_class": "car", "count": 30},
            ],
            average_confidence=0.87,
            trends=[],
        )
        serialized = response.model_dump(mode="json")
        assert serialized == snapshot


# =============================================================================
# Event Response Schema Snapshots
# =============================================================================


class TestEventResponseSnapshots:
    """Snapshot tests for event response schemas."""

    def test_event_response_json_schema(self, snapshot):
        """Test EventResponse JSON schema structure."""
        schema = EventResponse.model_json_schema()
        assert schema == snapshot

    def test_event_response_serialization(self, snapshot, sample_datetime):
        """Test EventResponse serialization format."""
        response = EventResponse(
            id=1,
            camera_id="front_door",
            started_at=sample_datetime,
            ended_at=sample_datetime,
            risk_score=75,
            reviewed=False,
            flagged=False,
            detection_count=3,
            object_types=["person", "car"],
        )
        serialized = response.model_dump(mode="json")
        assert serialized == snapshot

    def test_event_list_response_json_schema(self, snapshot):
        """Test EventListResponse JSON schema structure."""
        schema = EventListResponse.model_json_schema()
        assert schema == snapshot


# =============================================================================
# Feedback Response Schema Snapshots
# =============================================================================


class TestFeedbackResponseSnapshots:
    """Snapshot tests for feedback response schemas."""

    def test_feedback_response_json_schema(self, snapshot):
        """Test EventFeedbackResponse JSON schema structure."""
        schema = EventFeedbackResponse.model_json_schema()
        assert schema == snapshot

    def test_feedback_response_serialization(self, snapshot, sample_datetime):
        """Test EventFeedbackResponse serialization format."""
        response = EventFeedbackResponse(
            id=1,
            event_id=123,
            feedback_type="false_positive",
            notes="This was my neighbor's car.",
            actual_threat_level="no_threat",
            suggested_score=10,
            created_at=sample_datetime,
        )
        serialized = response.model_dump(mode="json")
        assert serialized == snapshot

    def test_feedback_stats_response_json_schema(self, snapshot):
        """Test FeedbackStatsResponse JSON schema structure."""
        schema = FeedbackStatsResponse.model_json_schema()
        assert schema == snapshot

    def test_feedback_stats_response_serialization(self, snapshot):
        """Test FeedbackStatsResponse serialization format."""
        response = FeedbackStatsResponse(
            total_feedback=100,
            by_type={
                "accurate": 10,
                "false_positive": 40,
                "missed_threat": 30,
                "severity_wrong": 20,
            },
            by_camera={"front_door": 50, "back_yard": 30, "garage": 20},
        )
        serialized = response.model_dump(mode="json")
        assert serialized == snapshot


# =============================================================================
# Health Response Schema Snapshots
# =============================================================================


class TestHealthResponseSnapshots:
    """Snapshot tests for health response schemas."""

    def test_liveness_response_json_schema(self, snapshot):
        """Test LivenessResponse JSON schema structure."""
        schema = LivenessResponse.model_json_schema()
        assert schema == snapshot

    def test_liveness_response_serialization(self, snapshot):
        """Test LivenessResponse serialization format."""
        response = LivenessResponse(status="alive")
        serialized = response.model_dump(mode="json")
        assert serialized == snapshot


# =============================================================================
# Pagination Schema Snapshots
# =============================================================================


class TestPaginationSnapshots:
    """Snapshot tests for pagination schemas."""

    def test_pagination_meta_json_schema(self, snapshot):
        """Test PaginationMeta JSON schema structure."""
        schema = PaginationMeta.model_json_schema()
        assert schema == snapshot

    def test_pagination_meta_serialization(self, snapshot, sample_pagination):
        """Test PaginationMeta serialization format."""
        serialized = sample_pagination.model_dump(mode="json")
        assert serialized == snapshot

    def test_pagination_meta_without_cursor(self, snapshot):
        """Test PaginationMeta serialization without cursor."""
        pagination = PaginationMeta(
            total=10,
            limit=10,
            offset=0,
            has_more=False,
        )
        serialized = pagination.model_dump(mode="json")
        assert serialized == snapshot
