"""Tests for domain-specific Hypothesis strategies.

This test module validates that the hypothesis_strategies module generates
valid data that matches domain constraints and business rules.

Run with different profiles:
    pytest backend/tests/unit/test_hypothesis_strategies.py --hypothesis-profile=fast
    pytest backend/tests/unit/test_hypothesis_strategies.py --hypothesis-profile=ci
"""

from __future__ import annotations

import re
from datetime import datetime

from hypothesis import given

from backend.tests.hypothesis_strategies import (
    camera_dict_strategy,
    detection_dict_strategy,
    edge_case_bbox,
    edge_case_confidence,
    edge_case_risk_scores,
    edge_case_timestamp,
    event_dict_strategy,
    example_high_risk_event,
    example_person_detection,
    example_vehicle_detection,
    valid_camera_folder_path,
    valid_camera_id,
    valid_camera_name,
    valid_camera_status,
    valid_confidence,
    valid_detection_bbox,
    valid_detection_label,
    valid_detection_labels_list,
    valid_event_summary,
    valid_normalized_bbox,
    valid_polygon_coordinates,
    valid_risk_level,
    valid_risk_score,
    valid_rtsp_url,
    valid_severity,
    valid_timestamp_range,
    valid_timezone,
    valid_utc_timestamp,
    valid_uuid4,
    valid_uuid_hex,
    zone_dict_strategy,
)

# =============================================================================
# Camera Strategy Tests
# =============================================================================


@given(camera_id=valid_camera_id())
def test_valid_camera_id_format(camera_id: str):
    """Test that generated camera IDs match normalized format."""
    # Must be lowercase alphanumeric with underscores
    assert re.match(r"^[a-z][a-z0-9_]*$", camera_id)
    # No consecutive underscores
    assert "__" not in camera_id
    # No leading/trailing underscores
    assert not camera_id.startswith("_")
    assert not camera_id.endswith("_")
    # Length constraint
    assert 1 <= len(camera_id) <= 50


@given(camera_name=valid_camera_name())
def test_valid_camera_name_format(camera_name: str):
    """Test that generated camera names are valid display names."""
    # Not empty or only whitespace
    assert camera_name.strip()
    assert len(camera_name.strip()) > 0
    # Length constraint
    assert 1 <= len(camera_name) <= 255


@given(folder_path=valid_camera_folder_path())
def test_valid_camera_folder_path_format(folder_path: str):
    """Test that generated folder paths follow expected pattern."""
    # Must start with /export/foscam/
    assert folder_path.startswith("/export/foscam/")
    # No path traversal
    assert ".." not in folder_path
    # Length constraint
    assert len(folder_path) <= 255


@given(status=valid_camera_status())
def test_valid_camera_status_enum(status: str):
    """Test that generated camera status values are valid enum values."""
    assert status in ["online", "offline", "error", "unknown"]


# =============================================================================
# UUID and ID Strategy Tests
# =============================================================================


@given(uuid_str=valid_uuid4())
def test_valid_uuid4_format(uuid_str: str):
    """Test that generated UUIDs are valid UUID4 format."""
    # Standard UUID format with dashes
    assert re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        uuid_str,
    )


@given(uuid_hex=valid_uuid_hex())
def test_valid_uuid_hex_format(uuid_hex: str):
    """Test that generated UUID hex strings are valid."""
    # 32 hex characters
    assert re.match(r"^[0-9a-f]{32}$", uuid_hex)
    assert len(uuid_hex) == 32


# =============================================================================
# Detection and Bounding Box Strategy Tests
# =============================================================================


@given(bbox=valid_detection_bbox())
def test_valid_detection_bbox_constraints(bbox: dict[str, int]):
    """Test that generated bounding boxes satisfy all constraints."""
    # Has required keys
    assert set(bbox.keys()) == {"x", "y", "width", "height"}
    # All values are non-negative
    assert bbox["x"] >= 0
    assert bbox["y"] >= 0
    assert bbox["width"] >= 1
    assert bbox["height"] >= 1
    # Within frame bounds (default 1920x1080)
    assert bbox["x"] + bbox["width"] <= 1920
    assert bbox["y"] + bbox["height"] <= 1080


@given(bbox=valid_normalized_bbox())
def test_valid_normalized_bbox_constraints(bbox: dict[str, float]):
    """Test that generated normalized bounding boxes are in [0, 1] range."""
    # Has required keys
    assert set(bbox.keys()) == {"x", "y", "width", "height"}
    # All values in [0, 1] range
    assert 0.0 <= bbox["x"] <= 1.0
    assert 0.0 <= bbox["y"] <= 1.0
    assert 0.0 < bbox["width"] <= 1.0
    assert 0.0 < bbox["height"] <= 1.0
    # Stays within bounds
    assert bbox["x"] + bbox["width"] <= 1.0
    assert bbox["y"] + bbox["height"] <= 1.0


# =============================================================================
# Risk Score and Confidence Strategy Tests
# =============================================================================


@given(risk_score=valid_risk_score())
def test_valid_risk_score_range(risk_score: int):
    """Test that generated risk scores are in valid range [0, 100]."""
    assert 0 <= risk_score <= 100


@given(confidence=valid_confidence())
def test_valid_confidence_range(confidence: float):
    """Test that generated confidence scores are in valid range [0.0, 1.0]."""
    assert 0.0 <= confidence <= 1.0


@given(risk_level=valid_risk_level())
def test_valid_risk_level_enum(risk_level: str):
    """Test that generated risk levels are valid enum values."""
    assert risk_level in ["low", "medium", "high", "critical"]


@given(severity=valid_severity())
def test_valid_severity_enum(severity):
    """Test that generated severity values are valid Severity enum."""
    from backend.models.enums import Severity

    assert severity in [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]


# =============================================================================
# Detection Label Strategy Tests
# =============================================================================


@given(label=valid_detection_label())
def test_valid_detection_label_values(label: str):
    """Test that generated detection labels are known object types."""
    known_labels = [
        "person",
        "vehicle",
        "car",
        "truck",
        "motorcycle",
        "bicycle",
        "bus",
        "dog",
        "cat",
        "bird",
        "horse",
        "cow",
        "bear",
        "deer",
        "package",
        "unknown",
    ]
    assert label in known_labels


@given(labels_list=valid_detection_labels_list())
def test_valid_detection_labels_list_unique(labels_list: list[str]):
    """Test that generated label lists contain unique values."""
    # All labels are unique
    assert len(labels_list) == len(set(labels_list))
    # At least one label
    assert len(labels_list) >= 1


# =============================================================================
# Timestamp Strategy Tests
# =============================================================================


@given(timestamp=valid_utc_timestamp())
def test_valid_utc_timestamp_timezone(timestamp: datetime):
    """Test that generated timestamps are timezone-aware UTC."""
    # Has timezone info
    assert timestamp.tzinfo is not None
    # Is UTC
    from datetime import UTC

    assert timestamp.tzinfo == UTC


@given(timestamp_range=valid_timestamp_range())
def test_valid_timestamp_range_ordering(timestamp_range: tuple[datetime, datetime]):
    """Test that generated timestamp ranges have start < end."""
    start, end = timestamp_range
    # Start is before end
    assert start < end
    # Both are UTC
    from datetime import UTC

    assert start.tzinfo == UTC
    assert end.tzinfo == UTC


# =============================================================================
# Timezone Strategy Tests
# =============================================================================


@given(timezone=valid_timezone())
def test_valid_timezone_format(timezone: str):
    """Test that generated timezones are valid IANA timezone names."""
    # Should be able to construct zoneinfo with it
    from zoneinfo import ZoneInfo

    zone = ZoneInfo(timezone)
    assert zone is not None


# =============================================================================
# RTSP URL Strategy Tests
# =============================================================================


@given(rtsp_url=valid_rtsp_url())
def test_valid_rtsp_url_format(rtsp_url: str):
    """Test that generated RTSP URLs have valid format."""
    # Must start with rtsp://
    assert rtsp_url.startswith("rtsp://")
    # Should have at least a host after rtsp://
    assert len(rtsp_url) > len("rtsp://")


# =============================================================================
# Event Summary Strategy Tests
# =============================================================================


@given(summary=valid_event_summary())
def test_valid_event_summary_format(summary: str):
    """Test that generated event summaries are realistic."""
    # Not empty
    assert summary.strip()
    # Reasonable length
    assert 20 <= len(summary) <= 200


# =============================================================================
# Polygon Coordinates Strategy Tests
# =============================================================================


@given(polygon=valid_polygon_coordinates())
def test_valid_polygon_coordinates_format(polygon: list[list[float]]):
    """Test that generated polygon coordinates are valid."""
    # At least 3 points (triangle)
    assert len(polygon) >= 3
    # Each point is [x, y]
    for point in polygon:
        assert len(point) == 2
        # Normalized coordinates
        assert 0.0 <= point[0] <= 1.0
        assert 0.0 <= point[1] <= 1.0


# =============================================================================
# Composite Model Strategy Tests
# =============================================================================


@given(camera_data=camera_dict_strategy())
def test_camera_dict_strategy_completeness(camera_data: dict):
    """Test that camera dict strategy generates all required fields."""
    required_fields = {
        "id",
        "name",
        "folder_path",
        "status",
        "created_at",
        "last_seen_at",
        "deleted_at",
        "property_id",
    }
    assert set(camera_data.keys()) == required_fields


@given(detection_data=detection_dict_strategy())
def test_detection_dict_strategy_completeness(detection_data: dict):
    """Test that detection dict strategy generates all required fields."""
    required_fields = {
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
    }
    assert set(detection_data.keys()) == required_fields


@given(event_data=event_dict_strategy())
def test_event_dict_strategy_completeness(event_data: dict):
    """Test that event dict strategy generates all required fields."""
    required_fields = {
        "batch_id",
        "camera_id",
        "started_at",
        "ended_at",
        "risk_score",
        "risk_level",
        "summary",
        "reasoning",
        "llm_prompt",
        "reviewed",
        "notes",
        "is_fast_path",
        "object_types",
        "clip_path",
        "deleted_at",
        "snooze_until",
    }
    assert set(event_data.keys()) == required_fields


@given(event_data=event_dict_strategy())
def test_event_dict_strategy_risk_level_consistency(event_data: dict):
    """Test that risk_level matches risk_score ranges."""
    risk_score = event_data["risk_score"]
    risk_level = event_data["risk_level"]

    if risk_score is not None:
        if risk_score <= 25:
            assert risk_level == "low"
        elif risk_score <= 50:
            assert risk_level == "medium"
        elif risk_score <= 75:
            assert risk_level == "high"
        else:
            assert risk_level == "critical"


@given(zone_data=zone_dict_strategy())
def test_zone_dict_strategy_completeness(zone_data: dict):
    """Test that zone dict strategy generates all required fields."""
    required_fields = {
        "id",
        "camera_id",
        "name",
        "zone_type",
        "coordinates",
        "shape",
        "color",
        "enabled",
        "priority",
        "created_at",
        "updated_at",
    }
    assert set(zone_data.keys()) == required_fields


@given(zone_data=zone_dict_strategy())
def test_zone_dict_strategy_color_format(zone_data: dict):
    """Test that zone colors are valid hex colors."""
    color = zone_data["color"]
    # Valid hex color format: #RRGGBB
    assert re.match(r"^#[0-9A-Fa-f]{6}$", color)


# =============================================================================
# Edge Case Strategy Tests
# =============================================================================


@given(risk_score=edge_case_risk_scores())
def test_edge_case_risk_scores_are_boundaries(risk_score: int):
    """Test that edge case risk scores are severity boundaries."""
    assert risk_score in [0, 25, 50, 75, 100]


@given(confidence=edge_case_confidence())
def test_edge_case_confidence_are_boundaries(confidence: float):
    """Test that edge case confidence values are boundaries."""
    assert confidence in [0.0, 0.5, 1.0]


@given(bbox=edge_case_bbox())
def test_edge_case_bbox_are_extreme(bbox: dict[str, int]):
    """Test that edge case bboxes cover extreme positions."""
    # Either at edges or minimum size
    at_edge = bbox["x"] == 0 or bbox["y"] == 0 or bbox["x"] + bbox["width"] == 1920
    min_size = bbox["width"] == 1 or bbox["height"] == 1
    full_frame = (
        bbox["x"] == 0 and bbox["y"] == 0 and bbox["width"] == 1920 and bbox["height"] == 1080
    )

    assert at_edge or min_size or full_frame


@given(timestamp=edge_case_timestamp())
def test_edge_case_timestamp_are_significant(timestamp: datetime):
    """Test that edge case timestamps are at significant boundaries."""
    # Year should be one of the edge case years
    assert timestamp.year in [2000, 2024, 2038]


# =============================================================================
# Example-Based Strategy Tests
# =============================================================================


@given(detection=example_person_detection())
def test_example_person_detection_format(detection: dict):
    """Test that example person detections have expected characteristics."""
    assert detection["object_type"] == "person"
    # High confidence
    assert detection["confidence"] >= 0.7
    # Has realistic proportions (taller than wide)
    assert detection["bbox_height"] > detection["bbox_width"]


@given(detection=example_vehicle_detection())
def test_example_vehicle_detection_format(detection: dict):
    """Test that example vehicle detections have expected characteristics."""
    assert detection["object_type"] in ["car", "truck", "vehicle"]
    # High confidence
    assert detection["confidence"] >= 0.8
    # Has realistic proportions (wider than tall)
    assert detection["bbox_width"] > detection["bbox_height"]


@given(event=example_high_risk_event())
def test_example_high_risk_event_format(event: dict):
    """Test that example high-risk events have critical severity."""
    assert event["risk_score"] >= 76
    assert event["risk_level"] == "critical"
    assert event["summary"] is not None
    assert event["reasoning"] is not None
