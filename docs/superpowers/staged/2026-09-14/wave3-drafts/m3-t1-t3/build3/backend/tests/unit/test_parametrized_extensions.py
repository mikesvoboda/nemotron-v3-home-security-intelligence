"""Additional parametrized tests for comprehensive coverage.

This module extends test coverage using parametrization to reduce
test boilerplate and improve test maintainability. Tests cover:
- Model validation with various inputs
- API status codes and error conditions
- Service behavior with edge cases
- Enum value handling
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from backend.api.schemas.camera import CameraCreate
from backend.api.schemas.zone import ZoneCreate
from backend.models.camera import normalize_camera_id
from backend.models.camera_zone import CameraZoneShape, CameraZoneType
from backend.models.detection import Detection
from backend.models.enums import CameraStatus, Severity
from backend.models.event import Event

# Aliases for backward compatibility
ZoneShape = CameraZoneShape
ZoneType = CameraZoneType

# =============================================================================
# Camera ID Normalization Parametrized Tests
# =============================================================================


class TestCameraIdNormalizationParametrized:
    """Parametrized tests for camera ID normalization."""

    @pytest.mark.parametrize(
        ("input_name", "expected_id"),
        [
            # Simple cases
            ("test", "test"),
            ("Test", "test"),
            ("TEST", "test"),
            # Spaces to underscores
            ("Front Door", "front_door"),
            ("My Camera Name", "my_camera_name"),
            # Special characters removed (not replaced with underscore)
            ("test@camera", "testcamera"),
            ("test#camera", "testcamera"),
            ("test$camera", "testcamera"),
            # Multiple spaces/special chars
            ("test  camera", "test_camera"),
            ("test___camera", "test_camera"),
            # Leading/trailing special chars
            ("_test_", "test"),
            ("__test__", "test"),
            # Mixed cases
            ("Front-Door-Camera", "front_door_camera"),
            ("Garage (Main)", "garage_main"),
        ],
    )
    def test_normalize_camera_id_various_inputs(self, input_name: str, expected_id: str) -> None:
        """Test camera ID normalization with various input patterns."""
        assert normalize_camera_id(input_name) == expected_id

    @pytest.mark.parametrize(
        "name",
        [
            "abc",
            "test123",
            "front_door",
            "BackYard",
            "garage-main",
            "Camera 1",
        ],
    )
    def test_normalize_camera_id_idempotent(self, name: str) -> None:
        """Test that normalizing twice gives same result."""
        once = normalize_camera_id(name)
        twice = normalize_camera_id(once)
        assert once == twice


# =============================================================================
# Camera Status Parametrized Tests
# =============================================================================


class TestCameraStatusParametrized:
    """Parametrized tests for camera status values."""

    @pytest.mark.parametrize(
        "status",
        ["online", "offline", "error", "unknown"],
    )
    def test_camera_create_with_various_statuses(self, status: str) -> None:
        """Test CameraCreate schema accepts various status values."""
        camera = CameraCreate(
            name="Test Camera",
            folder_path="/export/foscam/test",
            status=status,
        )
        assert camera.status == status

    @pytest.mark.parametrize(
        "status",
        list(CameraStatus),
    )
    def test_camera_create_with_enum_statuses(self, status: CameraStatus) -> None:
        """Test CameraCreate schema accepts CameraStatus enum values."""
        camera = CameraCreate(
            name="Test Camera",
            folder_path="/export/foscam/test",
            status=status,
        )
        assert camera.status == status


# =============================================================================
# Path Traversal Validation Parametrized Tests
# =============================================================================


class TestPathTraversalValidationParametrized:
    """Parametrized tests for path traversal detection."""

    @pytest.mark.parametrize(
        "malicious_path",
        [
            "../etc/passwd",
            "../../home/user",
            "/export/foscam/../../../etc",
            "test/../../../sensitive",
            "./../../config",
            "path/../../secret",
        ],
    )
    def test_camera_rejects_path_traversal(self, malicious_path: str) -> None:
        """Test that path traversal attempts are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(
                name="Test Camera",
                folder_path=malicious_path,
            )

        errors = exc_info.value.errors()
        assert any("Path traversal" in str(e.get("msg", "")) for e in errors)

    @pytest.mark.parametrize(
        "valid_path",
        [
            "/export/foscam/front_door",
            "/export/foscam/back_yard",
            "/export/foscam/garage",
            "/data/cameras/test",
            "/var/cameras/cam1",
        ],
    )
    def test_camera_accepts_valid_paths(self, valid_path: str) -> None:
        """Test that valid paths are accepted."""
        camera = CameraCreate(
            name="Test Camera",
            folder_path=valid_path,
        )
        assert camera.folder_path == valid_path


# =============================================================================
# Detection Confidence Parametrized Tests
# =============================================================================


class TestDetectionConfidenceParametrized:
    """Parametrized tests for detection confidence validation."""

    @pytest.mark.parametrize(
        "confidence",
        [0.0, 0.1, 0.5, 0.75, 0.9, 0.95, 0.99, 1.0],
    )
    def test_detection_valid_confidence_values(self, confidence: float) -> None:
        """Test detection accepts valid confidence values."""
        detection = Detection(
            camera_id="test_cam",
            file_path="/test/path.jpg",
            confidence=confidence,
        )
        assert detection.confidence == confidence
        assert 0.0 <= detection.confidence <= 1.0

    @pytest.mark.parametrize(
        ("confidence", "threshold", "expected"),
        [
            (0.95, 0.90, True),
            (0.85, 0.90, False),
            (0.90, 0.90, True),
            (0.50, 0.80, False),
            (1.0, 0.99, True),
            (0.0, 0.01, False),
        ],
    )
    def test_detection_confidence_threshold_comparison(
        self, confidence: float, threshold: float, expected: bool
    ) -> None:
        """Test confidence threshold comparisons."""
        detection = Detection(
            camera_id="test_cam",
            file_path="/test/path.jpg",
            confidence=confidence,
        )
        assert (detection.confidence >= threshold) == expected


# =============================================================================
# Event Risk Score Parametrized Tests
# =============================================================================


class TestEventRiskScoreParametrized:
    """Parametrized tests for event risk score validation."""

    @pytest.mark.parametrize(
        "risk_score",
        [0, 10, 25, 50, 75, 90, 100],
    )
    def test_event_valid_risk_scores(self, risk_score: int) -> None:
        """Test event accepts valid risk scores."""
        event = Event(
            batch_id="test_batch",
            camera_id="test_cam",
            started_at=datetime.now(UTC),
            risk_score=risk_score,
        )
        assert event.risk_score == risk_score
        assert 0 <= event.risk_score <= 100

    @pytest.mark.parametrize(
        ("risk_score", "expected_in_range"),
        [
            (0, "low"),
            (25, "low"),
            (35, "medium"),
            (50, "medium"),
            (65, "high"),
            (75, "high"),
            (85, "critical"),
            (100, "critical"),
        ],
    )
    def test_event_risk_score_to_level_mapping(
        self, risk_score: int, expected_in_range: str
    ) -> None:
        """Test risk score typically maps to expected risk level range.

        Note: risk_level is LLM-determined, but typically follows these ranges.
        """
        event = Event(
            batch_id="test_batch",
            camera_id="test_cam",
            started_at=datetime.now(UTC),
            risk_score=risk_score,
            risk_level=expected_in_range,
        )
        assert event.risk_level == expected_in_range


# =============================================================================
# Severity Enum Parametrized Tests
# =============================================================================


class TestSeverityEnumParametrized:
    """Parametrized tests for Severity enum."""

    @pytest.mark.parametrize(
        ("severity", "priority"),
        [
            (Severity.LOW, 3),  # Priority 3 = lowest priority
            (Severity.MEDIUM, 2),
            (Severity.HIGH, 1),
            (Severity.CRITICAL, 0),  # Priority 0 = highest priority
        ],
    )
    def test_severity_priority_mapping(self, severity: Severity, priority: int) -> None:
        """Test severity enum values map to expected priorities.

        Note: Lower priority number = higher priority (0 is highest).
        """
        from backend.services.severity import get_severity_priority

        assert get_severity_priority(severity) == priority

    @pytest.mark.parametrize(
        ("sev1", "sev2", "expected"),
        [
            (Severity.LOW, Severity.MEDIUM, True),
            (Severity.MEDIUM, Severity.HIGH, True),
            (Severity.HIGH, Severity.CRITICAL, True),
            (Severity.LOW, Severity.LOW, False),
            (Severity.MEDIUM, Severity.LOW, False),
            (Severity.CRITICAL, Severity.HIGH, False),
        ],
    )
    def test_severity_comparison(self, sev1: Severity, sev2: Severity, expected: bool) -> None:
        """Test severity comparison operators."""
        from backend.services.severity import severity_lt

        assert severity_lt(sev1, sev2) == expected


# =============================================================================
# Zone Coordinate Parametrized Tests
# =============================================================================


class TestZoneCoordinateParametrized:
    """Parametrized tests for zone coordinate validation."""

    @pytest.mark.parametrize(
        "coords",
        [
            [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],  # Rectangle
            [[0.2, 0.2], [0.8, 0.2], [0.5, 0.8]],  # Triangle
            [[0.1, 0.1], [0.5, 0.1], [0.7, 0.5], [0.5, 0.9], [0.1, 0.7]],  # Pentagon
        ],
    )
    def test_zone_accepts_valid_coordinates(self, coords: list[list[float]]) -> None:
        """Test zone accepts various valid coordinate sets."""
        zone = ZoneCreate(
            name="Test Zone",
            coordinates=coords,
            shape=ZoneShape.POLYGON,
        )
        assert zone.coordinates == coords
        assert len(zone.coordinates) >= 3

    @pytest.mark.parametrize(
        ("zone_type", "expected_color_pattern"),
        [
            (ZoneType.ENTRY_POINT, "#"),
            (ZoneType.DRIVEWAY, "#"),
            (ZoneType.SIDEWALK, "#"),
            (ZoneType.YARD, "#"),
            (ZoneType.OTHER, "#"),
        ],
    )
    def test_zone_type_has_default_color(
        self, zone_type: ZoneType, expected_color_pattern: str
    ) -> None:
        """Test zone types can have colors."""
        zone = ZoneCreate(
            name="Test Zone",
            coordinates=[[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
            zone_type=zone_type,
        )
        assert zone.color.startswith(expected_color_pattern)


# =============================================================================
# Timestamp Validation Parametrized Tests
# =============================================================================


class TestTimestampValidationParametrized:
    """Parametrized tests for timestamp validation."""

    @pytest.mark.parametrize(
        "delta_minutes",
        [0, 1, 5, 30, 60, 120, 1440],  # 0 min to 24 hours
    )
    def test_event_timestamp_ordering_various_deltas(self, delta_minutes: int) -> None:
        """Test event timestamp ordering with various time deltas."""
        started_at = datetime.now(UTC)
        ended_at = started_at + timedelta(minutes=delta_minutes)

        event = Event(
            batch_id="test_batch",
            camera_id="test_cam",
            started_at=started_at,
            ended_at=ended_at,
        )

        assert event.ended_at >= event.started_at
        delta = event.ended_at - event.started_at
        assert delta.total_seconds() >= 0


# =============================================================================
# Object Type Parametrized Tests
# =============================================================================


class TestObjectTypeParametrized:
    """Parametrized tests for object type handling."""

    @pytest.mark.parametrize(
        "object_type",
        [
            "person",
            "vehicle",
            "car",
            "truck",
            "motorcycle",
            "bicycle",
            "dog",
            "cat",
            "bird",
            "package",
        ],
    )
    def test_detection_accepts_various_object_types(self, object_type: str) -> None:
        """Test detection accepts various object types."""
        detection = Detection(
            camera_id="test_cam",
            file_path="/test/path.jpg",
            object_type=object_type,
        )
        assert detection.object_type == object_type


# =============================================================================
# Media Type Parametrized Tests
# =============================================================================


class TestMediaTypeParametrized:
    """Parametrized tests for media type validation."""

    @pytest.mark.parametrize(
        ("media_type", "file_extension", "file_type"),
        [
            ("image", ".jpg", "image/jpeg"),
            ("image", ".jpeg", "image/jpeg"),
            ("image", ".png", "image/png"),
            ("video", ".mp4", "video/mp4"),
            ("video", ".mkv", "video/x-matroska"),
            ("video", ".avi", "video/x-msvideo"),
        ],
    )
    def test_detection_media_type_consistency(
        self, media_type: str, file_extension: str, file_type: str
    ) -> None:
        """Test media type consistency with file types."""
        detection = Detection(
            camera_id="test_cam",
            file_path=f"/test/path{file_extension}",
            media_type=media_type,
            file_type=file_type,
        )
        assert detection.media_type == media_type
        assert detection.file_type == file_type


# =============================================================================
# Boolean Flag Parametrized Tests
# =============================================================================


class TestBooleanFlagsParametrized:
    """Parametrized tests for boolean flags."""

    @pytest.mark.parametrize(
        "reviewed",
        [True, False],
    )
    def test_event_reviewed_flag(self, reviewed: bool) -> None:
        """Test event reviewed flag with both values."""
        event = Event(
            batch_id="test_batch",
            camera_id="test_cam",
            started_at=datetime.now(UTC),
            reviewed=reviewed,
        )
        assert event.reviewed == reviewed
        assert isinstance(event.reviewed, bool)

    @pytest.mark.parametrize(
        "is_fast_path",
        [True, False],
    )
    def test_event_fast_path_flag(self, is_fast_path: bool) -> None:
        """Test event fast path flag with both values."""
        event = Event(
            batch_id="test_batch",
            camera_id="test_cam",
            started_at=datetime.now(UTC),
            is_fast_path=is_fast_path,
        )
        assert event.is_fast_path == is_fast_path
        assert isinstance(event.is_fast_path, bool)

    @pytest.mark.parametrize(
        "enabled",
        [True, False],
    )
    def test_zone_enabled_flag(self, enabled: bool) -> None:
        """Test zone enabled flag with both values."""
        zone = ZoneCreate(
            name="Test Zone",
            coordinates=[[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
            enabled=enabled,
        )
        assert zone.enabled == enabled
        assert isinstance(zone.enabled, bool)


# =============================================================================
# Edge Case Parametrized Tests
# =============================================================================


class TestEdgeCasesParametrized:
    """Parametrized tests for edge cases."""

    @pytest.mark.parametrize(
        "risk_score",
        [0, 100],  # Boundary values
    )
    def test_event_risk_score_boundaries(self, risk_score: int) -> None:
        """Test event risk score at boundaries."""
        event = Event(
            batch_id="test_batch",
            camera_id="test_cam",
            started_at=datetime.now(UTC),
            risk_score=risk_score,
        )
        assert event.risk_score == risk_score

    @pytest.mark.parametrize(
        "confidence",
        [0.0, 1.0],  # Boundary values
    )
    def test_detection_confidence_boundaries(self, confidence: float) -> None:
        """Test detection confidence at boundaries."""
        detection = Detection(
            camera_id="test_cam",
            file_path="/test/path.jpg",
            confidence=confidence,
        )
        assert detection.confidence == confidence

    @pytest.mark.parametrize(
        "priority",
        [0, 50, 100],  # Min, mid, max
    )
    def test_zone_priority_range(self, priority: int) -> None:
        """Test zone priority at various points in valid range."""
        zone = ZoneCreate(
            name="Test Zone",
            coordinates=[[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
            priority=priority,
        )
        assert zone.priority == priority
        assert 0 <= zone.priority <= 100
