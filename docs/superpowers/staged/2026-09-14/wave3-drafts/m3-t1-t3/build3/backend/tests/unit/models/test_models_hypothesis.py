"""Property-based tests for core models using Hypothesis.

This module contains comprehensive property-based tests for the core SQLAlchemy models
and their associated Pydantic schemas. Property-based testing generates many random inputs
to verify that certain invariants always hold, rather than testing specific hand-picked
examples.

Models tested:
- Camera: name validation, FTP path format, ID normalization
- Detection: bbox invariants, confidence bounds
- Event: risk_score bounds, timestamp ordering
- Zone: polygon coordinate invariants, geometry validation

Key properties tested:
1. Model field constraints are enforced
2. Serialization roundtrips preserve data
3. Validation rejects invalid states
4. Derived values maintain consistency
"""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from backend.api.schemas.camera import CameraCreate
from backend.api.schemas.zone import (
    ZoneCreate,
    _has_duplicate_consecutive_points,
    _is_self_intersecting,
    _polygon_area,
    _validate_polygon_geometry,
)
from backend.models.camera import Camera, normalize_camera_id
from backend.models.camera_zone import CameraZone, CameraZoneShape, CameraZoneType
from backend.models.detection import Detection
from backend.models.enums import CameraStatus
from backend.models.event import Event

# Aliases for backward compatibility
Zone = CameraZone
ZoneShape = CameraZoneShape
ZoneType = CameraZoneType

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid camera names (1-255 chars, non-empty)
camera_names = st.text(
    min_size=1,
    max_size=255,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs"),
        whitelist_characters="-_",
    ),
).filter(lambda x: len(x.strip()) > 0)

# Strategy for valid folder paths (no path traversal, valid characters)
valid_folder_paths = st.from_regex(
    r"/[a-zA-Z0-9_\-/]{1,100}",
    fullmatch=True,
).filter(lambda x: ".." not in x and len(x) <= 500)

# Strategy for camera statuses
camera_statuses = st.sampled_from(list(CameraStatus))

# Strategy for valid confidence scores (0-1 range)
valid_confidence = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Strategy for invalid confidence scores (outside 0-1)
invalid_confidence = st.one_of(
    st.floats(max_value=-0.001, allow_nan=False, allow_infinity=False),
    st.floats(min_value=1.001, allow_nan=False, allow_infinity=False),
)

# Strategy for valid risk scores (0-100 inclusive)
valid_risk_scores = st.integers(min_value=0, max_value=100)

# Strategy for invalid risk scores (outside 0-100)
invalid_risk_scores = st.one_of(
    st.integers(max_value=-1),
    st.integers(min_value=101),
)

# Strategy for positive integers (for bbox dimensions)
positive_integers = st.integers(min_value=0, max_value=10000)

# Strategy for normalized coordinates (0-1 range)
normalized_coord = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Strategy for zone types
zone_types = st.sampled_from(list(ZoneType))

# Strategy for zone shapes
zone_shapes = st.sampled_from(list(ZoneShape))

# Strategy for valid hex colors
valid_hex_colors = st.from_regex(r"^#[0-9A-Fa-f]{6}$", fullmatch=True)

# Strategy for zone priorities (0-100)
zone_priorities = st.integers(min_value=0, max_value=100)

# Strategy for timestamps (Hypothesis datetimes() does NOT take tzinfo in min/max)
# We add UTC timezone afterwards in the composite strategy
timestamps = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
)


# Composite strategy for valid rectangle coordinates
@st.composite
def valid_rectangle_coords(draw: st.DrawFn) -> list[list[float]]:
    """Generate valid rectangle coordinates (4 points, normalized).

    Creates a rectangle with:
    - x1 < x2 (left < right)
    - y1 < y2 (top < bottom)
    - Minimum area of 0.01 to avoid degenerate shapes
    """
    # Ensure minimum size for non-degenerate rectangle
    x1 = draw(st.floats(min_value=0.0, max_value=0.8, allow_nan=False, allow_infinity=False))
    y1 = draw(st.floats(min_value=0.0, max_value=0.8, allow_nan=False, allow_infinity=False))
    width = draw(
        st.floats(min_value=0.1, max_value=1.0 - x1, allow_nan=False, allow_infinity=False)
    )
    height = draw(
        st.floats(min_value=0.1, max_value=1.0 - y1, allow_nan=False, allow_infinity=False)
    )

    x2 = x1 + width
    y2 = y1 + height

    # Ensure within bounds
    x2 = min(x2, 1.0)
    y2 = min(y2, 1.0)

    # Rectangle: top-left, top-right, bottom-right, bottom-left
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


# Composite strategy for valid triangle coordinates
@st.composite
def valid_triangle_coords(draw: st.DrawFn) -> list[list[float]]:
    """Generate valid triangle coordinates (3 points, normalized, non-degenerate)."""
    # Generate 3 points that form a non-degenerate triangle
    x1 = draw(st.floats(min_value=0.0, max_value=0.4, allow_nan=False, allow_infinity=False))
    y1 = draw(st.floats(min_value=0.0, max_value=0.4, allow_nan=False, allow_infinity=False))

    x2 = draw(st.floats(min_value=0.5, max_value=1.0, allow_nan=False, allow_infinity=False))
    y2 = draw(st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False))

    x3 = draw(st.floats(min_value=0.2, max_value=0.8, allow_nan=False, allow_infinity=False))
    y3 = draw(st.floats(min_value=0.6, max_value=1.0, allow_nan=False, allow_infinity=False))

    coords = [[x1, y1], [x2, y2], [x3, y3]]

    # Ensure non-degenerate (positive area)
    area = abs(_polygon_area(coords))
    assume(area >= 0.01)  # Minimum area to avoid near-degenerate triangles

    return coords


# Composite strategy for valid convex polygon coordinates (4-8 points)
@st.composite
def valid_convex_polygon_coords(draw: st.DrawFn) -> list[list[float]]:
    """Generate valid convex polygon coordinates.

    Uses a simple strategy: generate points on a circle-like pattern
    to ensure convexity.
    """
    import math

    n_points = draw(st.integers(min_value=4, max_value=8))
    cx = draw(st.floats(min_value=0.3, max_value=0.7, allow_nan=False, allow_infinity=False))
    cy = draw(st.floats(min_value=0.3, max_value=0.7, allow_nan=False, allow_infinity=False))
    radius = draw(st.floats(min_value=0.15, max_value=0.25, allow_nan=False, allow_infinity=False))

    coords = []
    for i in range(n_points):
        angle = 2 * math.pi * i / n_points
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        # Clamp to [0, 1]
        x = max(0.0, min(1.0, x))
        y = max(0.0, min(1.0, y))
        coords.append([x, y])

    # Ensure valid polygon
    area = abs(_polygon_area(coords))
    assume(area >= 0.01)
    assume(not _is_self_intersecting(coords))
    assume(not _has_duplicate_consecutive_points(coords))

    return coords


# Composite strategy for valid bbox (x, y, width, height)
@st.composite
def valid_bbox(draw: st.DrawFn) -> tuple[int, int, int, int]:
    """Generate valid bounding box coordinates.

    Returns (x, y, width, height) where:
    - All values are non-negative
    - x + width and y + height represent the bottom-right corner
    """
    x = draw(st.integers(min_value=0, max_value=1920))
    y = draw(st.integers(min_value=0, max_value=1080))
    width = draw(st.integers(min_value=1, max_value=500))
    height = draw(st.integers(min_value=1, max_value=500))
    return (x, y, width, height)


# Composite strategy for ordered timestamp pairs
@st.composite
def ordered_timestamps(draw: st.DrawFn) -> tuple[datetime, datetime]:
    """Generate two timestamps where started_at <= ended_at."""
    started_at_naive = draw(timestamps)
    delta = draw(st.timedeltas(min_value=timedelta(seconds=0), max_value=timedelta(hours=24)))
    ended_at_naive = started_at_naive + delta
    # Add UTC timezone
    started_at = started_at_naive.replace(tzinfo=UTC)
    ended_at = ended_at_naive.replace(tzinfo=UTC)
    return (started_at, ended_at)


# =============================================================================
# Camera Model Property Tests
# =============================================================================


class TestCameraModelProperties:
    """Property-based tests for Camera model and schema."""

    @given(name=camera_names, path=valid_folder_paths, status=camera_statuses)
    @settings(max_examples=100)
    def test_camera_create_valid_inputs(self, name: str, path: str, status: CameraStatus) -> None:
        """Property: Valid inputs always create a valid CameraCreate schema."""
        schema = CameraCreate(name=name, folder_path=path, status=status)

        # NEM-2569: Camera names are now stripped of leading/trailing whitespace
        assert schema.name == name.strip()
        assert schema.folder_path == path
        assert schema.status == status

    @given(name=camera_names, path=valid_folder_paths)
    @settings(max_examples=100)
    def test_camera_schema_serialization_roundtrip(self, name: str, path: str) -> None:
        """Property: CameraCreate serializes and deserializes correctly."""
        schema = CameraCreate(name=name, folder_path=path)
        json_data = schema.model_dump()
        reconstructed = CameraCreate(**json_data)

        assert reconstructed.name == schema.name
        assert reconstructed.folder_path == schema.folder_path
        assert reconstructed.status == schema.status

    @given(path_with_traversal=st.text(min_size=3).map(lambda x: f"../{x}"))
    @settings(max_examples=50)
    def test_camera_rejects_path_traversal(self, path_with_traversal: str) -> None:
        """Property: Path traversal attempts are always rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Test", folder_path=path_with_traversal)

        # Verify it's specifically the path traversal validation
        errors = exc_info.value.errors()
        assert any("Path traversal" in str(e.get("msg", "")) for e in errors)

    @given(name=st.text(min_size=1, max_size=100))
    @settings(max_examples=100)
    def test_normalize_camera_id_always_valid(self, name: str) -> None:
        """Property: normalize_camera_id always produces valid identifiers."""
        result = normalize_camera_id(name)

        # Result should be lowercase
        assert result == result.lower()

        # Result should contain only valid ID characters
        for char in result:
            assert char.isalnum() or char == "_", f"Invalid char: {char!r}"

        # No leading/trailing underscores
        if result:
            assert not result.startswith("_")
            assert not result.endswith("_")

        # No consecutive underscores
        assert "__" not in result

    @given(name=st.text(min_size=1, max_size=100))
    @settings(max_examples=100)
    def test_normalize_camera_id_idempotent(self, name: str) -> None:
        """Property: Normalizing twice gives same result as once."""
        once = normalize_camera_id(name)
        twice = normalize_camera_id(once)
        assert once == twice

    @given(folder_name=camera_names)
    @settings(max_examples=50)
    def test_camera_from_folder_name_consistency(self, folder_name: str) -> None:
        """Property: from_folder_name produces consistent ID and preserves name."""
        camera = Camera.from_folder_name(folder_name, "/test/path")

        # ID matches normalize_camera_id output
        expected_id = normalize_camera_id(folder_name)
        assert camera.id == expected_id

        # Original name is preserved
        assert camera.name == folder_name

        # Default status is online
        assert camera.status == "online"


# =============================================================================
# Detection Model Property Tests
# =============================================================================


class TestDetectionModelProperties:
    """Property-based tests for Detection model."""

    @given(confidence=valid_confidence)
    @settings(max_examples=100)
    def test_detection_confidence_bounds(self, confidence: float) -> None:
        """Property: Valid confidence is always in [0, 1]."""
        detection = Detection(
            camera_id="test_cam",
            file_path="/test/path.jpg",
            confidence=confidence,
        )

        assert 0.0 <= detection.confidence <= 1.0

    @given(bbox=valid_bbox())
    @settings(max_examples=100)
    def test_detection_bbox_invariants(self, bbox: tuple[int, int, int, int]) -> None:
        """Property: Bounding box dimensions are always non-negative."""
        x, y, width, height = bbox

        detection = Detection(
            camera_id="test_cam",
            file_path="/test/path.jpg",
            bbox_x=x,
            bbox_y=y,
            bbox_width=width,
            bbox_height=height,
        )

        assert detection.bbox_x >= 0
        assert detection.bbox_y >= 0
        assert detection.bbox_width >= 0
        assert detection.bbox_height >= 0

        # Derived property: bottom-right corner coordinates
        x2 = detection.bbox_x + detection.bbox_width
        y2 = detection.bbox_y + detection.bbox_height
        assert x2 >= detection.bbox_x  # x2 >= x1
        assert y2 >= detection.bbox_y  # y2 >= y1

    @given(
        x=positive_integers,
        y=positive_integers,
        width=st.integers(min_value=1, max_value=1000),
        height=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=100)
    def test_detection_bbox_corner_ordering(self, x: int, y: int, width: int, height: int) -> None:
        """Property: Bounding box corners maintain x1 < x2, y1 < y2 when width/height > 0."""
        detection = Detection(
            camera_id="test_cam",
            file_path="/test/path.jpg",
            bbox_x=x,
            bbox_y=y,
            bbox_width=width,
            bbox_height=height,
        )

        x1, y1 = detection.bbox_x, detection.bbox_y
        x2 = x1 + detection.bbox_width
        y2 = y1 + detection.bbox_height

        # When width > 0, x2 > x1
        if width > 0:
            assert x2 > x1

        # When height > 0, y2 > y1
        if height > 0:
            assert y2 > y1

    @given(media_type=st.sampled_from(["image", "video"]))
    @settings(max_examples=20)
    def test_detection_media_type_values(self, media_type: str) -> None:
        """Property: media_type is always 'image' or 'video'."""
        detection = Detection(
            camera_id="test_cam",
            file_path="/test/path.jpg",
            media_type=media_type,
        )

        assert detection.media_type in ["image", "video"]

    @given(
        duration=st.floats(min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_detection_video_duration_non_negative(self, duration: float) -> None:
        """Property: Video duration is always non-negative."""
        detection = Detection(
            camera_id="test_cam",
            file_path="/test/path.mp4",
            media_type="video",
            duration=duration,
        )

        assert detection.duration >= 0


# =============================================================================
# Event Model Property Tests
# =============================================================================


class TestEventModelProperties:
    """Property-based tests for Event model."""

    @given(risk_score=valid_risk_scores)
    @settings(max_examples=100)
    def test_event_risk_score_bounds(self, risk_score: int) -> None:
        """Property: Valid risk_score is always in [0, 100]."""
        event = Event(
            batch_id="batch_001",
            camera_id="test_cam",
            started_at=datetime.now(UTC),
            risk_score=risk_score,
        )

        assert 0 <= event.risk_score <= 100

    @given(timestamps=ordered_timestamps())
    @settings(max_examples=100)
    def test_event_timestamp_ordering(self, timestamps: tuple[datetime, datetime]) -> None:
        """Property: ended_at is always >= started_at when both are set."""
        started_at, ended_at = timestamps

        event = Event(
            batch_id="batch_001",
            camera_id="test_cam",
            started_at=started_at,
            ended_at=ended_at,
        )

        assert event.ended_at >= event.started_at

    @given(
        risk_score=valid_risk_scores,
        risk_level=st.sampled_from(["low", "medium", "high", "critical"]),
    )
    @settings(max_examples=100)
    def test_event_risk_level_consistency(self, risk_score: int, risk_level: str) -> None:
        """Property: Event can have any risk_score with any risk_level (LLM-determined)."""
        # Note: risk_level is LLM-determined, not directly derived from risk_score
        # This test verifies both can be set independently
        event = Event(
            batch_id="batch_001",
            camera_id="test_cam",
            started_at=datetime.now(UTC),
            risk_score=risk_score,
            risk_level=risk_level,
        )

        assert event.risk_score == risk_score
        assert event.risk_level == risk_level

    @given(reviewed=st.booleans())
    @settings(max_examples=20)
    def test_event_reviewed_is_boolean(self, reviewed: bool) -> None:
        """Property: reviewed field is always a valid boolean."""
        event = Event(
            batch_id="batch_001",
            camera_id="test_cam",
            started_at=datetime.now(UTC),
            reviewed=reviewed,
        )

        assert isinstance(event.reviewed, bool)
        assert event.reviewed == reviewed

    @given(batch_id=st.text(min_size=1, max_size=50).filter(lambda x: len(x.strip()) > 0))
    @settings(max_examples=50)
    def test_event_batch_id_preserved(self, batch_id: str) -> None:
        """Property: batch_id is always preserved as given."""
        event = Event(
            batch_id=batch_id,
            camera_id="test_cam",
            started_at=datetime.now(UTC),
        )

        assert event.batch_id == batch_id

    @given(is_fast_path=st.booleans())
    @settings(max_examples=20)
    def test_event_fast_path_flag(self, is_fast_path: bool) -> None:
        """Property: is_fast_path flag is always a valid boolean."""
        event = Event(
            batch_id="batch_001",
            camera_id="test_cam",
            started_at=datetime.now(UTC),
            is_fast_path=is_fast_path,
        )

        assert isinstance(event.is_fast_path, bool)
        assert event.is_fast_path == is_fast_path


# =============================================================================
# Zone Model Property Tests
# =============================================================================


class TestZoneModelProperties:
    """Property-based tests for Zone model and schema."""

    @given(coords=valid_rectangle_coords())
    @settings(max_examples=100)
    def test_zone_rectangle_coordinates_valid(self, coords: list[list[float]]) -> None:
        """Property: Valid rectangle coordinates always pass validation."""
        schema = ZoneCreate(
            name="Test Zone",
            coordinates=coords,
            shape=ZoneShape.RECTANGLE,
        )

        assert len(schema.coordinates) == 4
        for point in schema.coordinates:
            assert len(point) == 2
            assert 0 <= point[0] <= 1
            assert 0 <= point[1] <= 1

    @given(coords=valid_triangle_coords())
    @settings(max_examples=100)
    def test_zone_triangle_coordinates_valid(self, coords: list[list[float]]) -> None:
        """Property: Valid triangle coordinates always pass validation."""
        schema = ZoneCreate(
            name="Test Zone",
            coordinates=coords,
            shape=ZoneShape.POLYGON,
        )

        assert len(schema.coordinates) == 3
        for point in schema.coordinates:
            assert len(point) == 2
            assert 0 <= point[0] <= 1
            assert 0 <= point[1] <= 1

    @given(coords=valid_convex_polygon_coords())
    @settings(max_examples=50)
    def test_zone_polygon_coordinates_valid(self, coords: list[list[float]]) -> None:
        """Property: Valid convex polygon coordinates always pass validation."""
        schema = ZoneCreate(
            name="Test Zone",
            coordinates=coords,
            shape=ZoneShape.POLYGON,
        )

        assert len(schema.coordinates) >= 3
        for point in schema.coordinates:
            assert len(point) == 2
            assert 0 <= point[0] <= 1
            assert 0 <= point[1] <= 1

    @given(priority=zone_priorities)
    @settings(max_examples=50)
    def test_zone_priority_bounds(self, priority: int) -> None:
        """Property: Zone priority is always in [0, 100]."""
        coords = [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]
        schema = ZoneCreate(
            name="Test Zone",
            coordinates=coords,
            priority=priority,
        )

        assert 0 <= schema.priority <= 100

    @given(zone_type=zone_types)
    @settings(max_examples=10)
    def test_zone_type_values(self, zone_type: ZoneType) -> None:
        """Property: zone_type is always a valid ZoneType enum value."""
        coords = [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]
        schema = ZoneCreate(
            name="Test Zone",
            coordinates=coords,
            zone_type=zone_type,
        )

        assert schema.zone_type in ZoneType

    @given(color=valid_hex_colors)
    @settings(max_examples=50)
    def test_zone_color_format(self, color: str) -> None:
        """Property: Zone color is always a valid hex color."""
        coords = [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]
        schema = ZoneCreate(
            name="Test Zone",
            coordinates=coords,
            color=color,
        )

        assert schema.color.startswith("#")
        assert len(schema.color) == 7

    @given(enabled=st.booleans())
    @settings(max_examples=10)
    def test_zone_enabled_is_boolean(self, enabled: bool) -> None:
        """Property: Zone enabled flag is always a valid boolean."""
        coords = [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]
        schema = ZoneCreate(
            name="Test Zone",
            coordinates=coords,
            enabled=enabled,
        )

        assert isinstance(schema.enabled, bool)
        assert schema.enabled == enabled


class TestZoneCoordinateValidation:
    """Property-based tests for zone coordinate validation functions."""

    @given(coords=valid_rectangle_coords())
    @settings(max_examples=100)
    def test_valid_polygon_has_positive_area(self, coords: list[list[float]]) -> None:
        """Property: Valid polygons always have positive area."""
        area = abs(_polygon_area(coords))
        assert area > 0

    @given(coords=valid_rectangle_coords())
    @settings(max_examples=100)
    def test_valid_rectangle_not_self_intersecting(self, coords: list[list[float]]) -> None:
        """Property: Valid rectangles never self-intersect."""
        assert not _is_self_intersecting(coords)

    @given(coords=valid_rectangle_coords())
    @settings(max_examples=100)
    def test_valid_rectangle_no_duplicate_points(self, coords: list[list[float]]) -> None:
        """Property: Valid rectangles have no duplicate consecutive points."""
        assert not _has_duplicate_consecutive_points(coords)

    def test_degenerate_polygon_rejected(self) -> None:
        """Test that collinear points (degenerate polygon) are rejected."""
        # Three collinear points
        collinear = [[0.1, 0.1], [0.2, 0.2], [0.3, 0.3]]

        with pytest.raises(ValueError, match="zero or near-zero area"):
            _validate_polygon_geometry(collinear)

    def test_self_intersecting_polygon_rejected(self) -> None:
        """Test that self-intersecting polygon is rejected."""
        # A complex crossed polygon that has positive area by shoelace formula
        # but whose edges cross each other
        crossed = [[0.1, 0.3], [0.9, 0.3], [0.9, 0.7], [0.1, 0.7], [0.5, 0.1], [0.5, 0.9]]

        with pytest.raises(ValueError, match="self-intersecting"):
            _validate_polygon_geometry(crossed)

    def test_duplicate_consecutive_points_rejected(self) -> None:
        """Test that duplicate consecutive points are rejected."""
        duplicate = [[0.1, 0.1], [0.1, 0.1], [0.5, 0.1], [0.5, 0.5]]

        with pytest.raises(ValueError, match="duplicate consecutive"):
            _validate_polygon_geometry(duplicate)

    @given(
        x=st.floats(min_value=-1.0, max_value=-0.01, allow_nan=False, allow_infinity=False)
        | st.floats(min_value=1.01, max_value=2.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_out_of_range_coordinates_rejected(self, x: float) -> None:
        """Property: Coordinates outside [0, 1] are always rejected."""
        coords = [[x, 0.5], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]

        with pytest.raises(ValueError, match="normalized"):
            _validate_polygon_geometry(coords)


# =============================================================================
# Schema Roundtrip Tests
# =============================================================================


class TestSchemaRoundtrips:
    """Property-based tests for schema serialization roundtrips."""

    @given(
        name=camera_names,
        path=valid_folder_paths,
        status=camera_statuses,
    )
    @settings(max_examples=50)
    def test_camera_create_roundtrip(self, name: str, path: str, status: CameraStatus) -> None:
        """Property: CameraCreate roundtrips through JSON correctly."""
        original = CameraCreate(name=name, folder_path=path, status=status)
        json_data = original.model_dump(mode="json")
        restored = CameraCreate.model_validate(json_data)

        assert restored.name == original.name
        assert restored.folder_path == original.folder_path
        assert restored.status == original.status

    @given(
        coords=valid_rectangle_coords(),
        zone_type=zone_types,
        color=valid_hex_colors,
        enabled=st.booleans(),
        priority=zone_priorities,
    )
    @settings(max_examples=50)
    def test_zone_create_roundtrip(
        self,
        coords: list[list[float]],
        zone_type: ZoneType,
        color: str,
        enabled: bool,
        priority: int,
    ) -> None:
        """Property: ZoneCreate roundtrips through JSON correctly."""
        original = ZoneCreate(
            name="Test Zone",
            coordinates=coords,
            zone_type=zone_type,
            color=color,
            enabled=enabled,
            priority=priority,
        )
        json_data = original.model_dump(mode="json")
        restored = ZoneCreate.model_validate(json_data)

        assert restored.name == original.name
        assert restored.coordinates == original.coordinates
        assert restored.zone_type == original.zone_type
        assert restored.color == original.color
        assert restored.enabled == original.enabled
        assert restored.priority == original.priority


# =============================================================================
# Model Relationship Consistency Tests
# =============================================================================


class TestModelRelationshipConsistency:
    """Property-based tests for model relationship consistency."""

    @given(camera_id=st.text(min_size=1, max_size=50).filter(lambda x: len(x.strip()) > 0))
    @settings(max_examples=50)
    def test_detection_camera_id_preserved(self, camera_id: str) -> None:
        """Property: Detection's camera_id is always preserved."""
        detection = Detection(
            camera_id=camera_id,
            file_path="/test/path.jpg",
        )

        assert detection.camera_id == camera_id

    @given(camera_id=st.text(min_size=1, max_size=50).filter(lambda x: len(x.strip()) > 0))
    @settings(max_examples=50)
    def test_event_camera_id_preserved(self, camera_id: str) -> None:
        """Property: Event's camera_id is always preserved."""
        event = Event(
            batch_id="batch_001",
            camera_id=camera_id,
            started_at=datetime.now(UTC),
        )

        assert event.camera_id == camera_id

    @given(camera_id=st.text(min_size=1, max_size=50).filter(lambda x: len(x.strip()) > 0))
    @settings(max_examples=50)
    def test_zone_camera_id_preserved(self, camera_id: str) -> None:
        """Property: Zone's camera_id is always preserved."""
        zone = Zone(
            id="zone_001",
            camera_id=camera_id,
            name="Test Zone",
            coordinates=[[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
        )

        assert zone.camera_id == camera_id
