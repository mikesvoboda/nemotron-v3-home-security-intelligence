"""Unit tests for Detection model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- Bounding box fields
- Video-specific metadata fields
- Property-based tests for field values
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.detection import Detection
from backend.tests.factories import DetectionFactory

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid confidence scores (0.0 to 1.0)
confidence_scores = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# Strategy for valid bbox coordinates (non-negative integers)
bbox_coords = st.integers(min_value=0, max_value=10000)

# Strategy for valid object types
object_types = st.sampled_from(["person", "vehicle", "animal", "package", "unknown"])

# Strategy for valid media types
media_types = st.sampled_from(["image", "video"])


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_detection():
    """Create a sample detection for testing using factory."""
    return DetectionFactory(
        id=1,
        camera_id="front_door",
        file_path="/export/foscam/front_door/image001.jpg",
        file_type="image/jpeg",
        object_type="person",
        confidence=0.95,
        bbox_x=100,
        bbox_y=200,
        bbox_width=150,
        bbox_height=300,
    )


@pytest.fixture
def sample_video_detection():
    """Create a sample video detection for testing using factory."""
    return DetectionFactory(
        id=2,
        camera_id="back_yard",
        file_path="/export/foscam/back_yard/video001.mp4",
        video=True,  # Use factory trait
        object_type="vehicle",
        confidence=0.88,
        duration=30.5,
    )


@pytest.fixture
def minimal_detection():
    """Create a detection with only required fields using factory."""
    return DetectionFactory.build(
        camera_id="test_cam",
        file_path="/path/to/file.jpg",
        file_type=None,
        object_type=None,
        confidence=None,
        bbox_x=None,
        bbox_y=None,
        bbox_width=None,
        bbox_height=None,
    )


# =============================================================================
# Detection Model Initialization Tests
# =============================================================================


class TestDetectionModelInitialization:
    """Tests for Detection model initialization."""

    def test_detection_creation_minimal(self):
        """Test creating a detection with minimal required fields."""
        detection = Detection(
            camera_id="test_cam",
            file_path="/path/to/image.jpg",
        )

        assert detection.camera_id == "test_cam"
        assert detection.file_path == "/path/to/image.jpg"

    def test_detection_with_all_fields(self, sample_detection):
        """Test detection with all fields populated."""
        assert sample_detection.id == 1
        assert sample_detection.camera_id == "front_door"
        assert sample_detection.file_path == "/export/foscam/front_door/image001.jpg"
        assert sample_detection.file_type == "image/jpeg"
        assert sample_detection.object_type == "person"
        assert sample_detection.confidence == 0.95

    def test_detection_optional_fields_default_to_none(self, minimal_detection):
        """Test that optional fields default to None."""
        assert minimal_detection.file_type is None
        assert minimal_detection.object_type is None
        assert minimal_detection.confidence is None
        assert minimal_detection.bbox_x is None
        assert minimal_detection.bbox_y is None
        assert minimal_detection.bbox_width is None
        assert minimal_detection.bbox_height is None
        assert minimal_detection.thumbnail_path is None

    def test_detection_media_type_default_column_definition(self):
        """Test that media_type column has 'image' as default.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(Detection)
        media_type_col = mapper.columns["media_type"]
        assert media_type_col.default is not None
        assert media_type_col.default.arg == "image"

    def test_detection_video_fields_default_to_none(self, minimal_detection):
        """Test that video fields default to None."""
        assert minimal_detection.duration is None
        assert minimal_detection.video_codec is None
        assert minimal_detection.video_width is None
        assert minimal_detection.video_height is None


# =============================================================================
# Detection Field Tests
# =============================================================================


class TestDetectionBoundingBox:
    """Tests for Detection bounding box fields."""

    def test_bbox_all_fields_present(self, sample_detection):
        """Test all bbox fields are present."""
        assert sample_detection.bbox_x == 100
        assert sample_detection.bbox_y == 200
        assert sample_detection.bbox_width == 150
        assert sample_detection.bbox_height == 300

    def test_bbox_can_be_zero(self):
        """Test bbox coordinates can be zero."""
        detection = Detection(
            camera_id="test",
            file_path="/path",
            bbox_x=0,
            bbox_y=0,
            bbox_width=100,
            bbox_height=100,
        )

        assert detection.bbox_x == 0
        assert detection.bbox_y == 0

    def test_bbox_large_values(self):
        """Test bbox with large coordinate values."""
        detection = Detection(
            camera_id="test",
            file_path="/path",
            bbox_x=3840,
            bbox_y=2160,
            bbox_width=1920,
            bbox_height=1080,
        )

        assert detection.bbox_x == 3840
        assert detection.bbox_y == 2160


class TestDetectionConfidence:
    """Tests for Detection confidence field."""

    def test_confidence_normal_value(self, sample_detection):
        """Test confidence with normal value."""
        assert sample_detection.confidence == 0.95

    def test_confidence_zero(self):
        """Test confidence can be zero."""
        detection = Detection(
            camera_id="test",
            file_path="/path",
            confidence=0.0,
        )
        assert detection.confidence == 0.0

    def test_confidence_one(self):
        """Test confidence can be 1.0."""
        detection = Detection(
            camera_id="test",
            file_path="/path",
            confidence=1.0,
        )
        assert detection.confidence == 1.0

    def test_confidence_low_value(self):
        """Test confidence with low value."""
        detection = Detection(
            camera_id="test",
            file_path="/path",
            confidence=0.01,
        )
        assert detection.confidence == 0.01


class TestDetectionVideoMetadata:
    """Tests for Detection video-specific fields."""

    def test_video_detection_media_type(self, sample_video_detection):
        """Test video detection has correct media_type."""
        assert sample_video_detection.media_type == "video"

    def test_video_detection_duration(self, sample_video_detection):
        """Test video detection has duration."""
        assert sample_video_detection.duration == 30.5

    def test_video_detection_codec(self, sample_video_detection):
        """Test video detection has codec."""
        assert sample_video_detection.video_codec == "h264"

    def test_video_detection_dimensions(self, sample_video_detection):
        """Test video detection has dimensions."""
        assert sample_video_detection.video_width == 1920
        assert sample_video_detection.video_height == 1080

    def test_video_detection_hevc_codec(self):
        """Test video detection with HEVC codec."""
        detection = Detection(
            camera_id="test",
            file_path="/path/video.mp4",
            media_type="video",
            video_codec="hevc",
        )
        assert detection.video_codec == "hevc"


class TestDetectionObjectType:
    """Tests for Detection object_type field."""

    def test_object_type_person(self):
        """Test detection with person object type."""
        detection = Detection(
            camera_id="test",
            file_path="/path",
            object_type="person",
        )
        assert detection.object_type == "person"

    def test_object_type_vehicle(self):
        """Test detection with vehicle object type."""
        detection = Detection(
            camera_id="test",
            file_path="/path",
            object_type="vehicle",
        )
        assert detection.object_type == "vehicle"

    def test_object_type_animal(self):
        """Test detection with animal object type."""
        detection = Detection(
            camera_id="test",
            file_path="/path",
            object_type="animal",
        )
        assert detection.object_type == "animal"

    def test_object_type_custom(self):
        """Test detection with custom object type."""
        detection = Detection(
            camera_id="test",
            file_path="/path",
            object_type="package",
        )
        assert detection.object_type == "package"


# =============================================================================
# Detection Repr Tests
# =============================================================================


class TestDetectionRepr:
    """Tests for Detection string representation."""

    def test_detection_repr_contains_class_name(self, sample_detection):
        """Test repr contains class name."""
        repr_str = repr(sample_detection)
        assert "Detection" in repr_str

    def test_detection_repr_contains_id(self, sample_detection):
        """Test repr contains detection id."""
        repr_str = repr(sample_detection)
        assert "id=1" in repr_str

    def test_detection_repr_contains_camera_id(self, sample_detection):
        """Test repr contains camera_id."""
        repr_str = repr(sample_detection)
        assert "front_door" in repr_str

    def test_detection_repr_contains_object_type(self, sample_detection):
        """Test repr contains object_type."""
        repr_str = repr(sample_detection)
        assert "person" in repr_str

    def test_detection_repr_contains_confidence(self, sample_detection):
        """Test repr contains confidence."""
        repr_str = repr(sample_detection)
        assert "0.95" in repr_str

    def test_detection_repr_format(self, sample_detection):
        """Test repr has expected format."""
        repr_str = repr(sample_detection)
        assert repr_str.startswith("<Detection(")
        assert repr_str.endswith(")>")


# =============================================================================
# Detection Relationship Tests
# =============================================================================


class TestDetectionRelationships:
    """Tests for Detection relationship definitions."""

    def test_detection_has_camera_relationship(self, sample_detection):
        """Test detection has camera relationship defined."""
        assert hasattr(sample_detection, "camera")


# =============================================================================
# Detection Table Args Tests
# =============================================================================


class TestDetectionTableArgs:
    """Tests for Detection table arguments (indexes)."""

    def test_detection_has_table_args(self):
        """Test Detection model has __table_args__."""
        assert hasattr(Detection, "__table_args__")

    def test_detection_tablename(self):
        """Test Detection has correct table name."""
        assert Detection.__tablename__ == "detections"

    def test_detection_has_camera_id_index(self):
        """Test Detection has camera_id index defined."""
        indexes = Detection.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_detections_camera_id" in index_names

    def test_detection_has_detected_at_index(self):
        """Test Detection has detected_at index defined."""
        indexes = Detection.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_detections_detected_at" in index_names

    def test_detection_has_camera_time_composite_index(self):
        """Test Detection has camera_id + detected_at composite index defined."""
        indexes = Detection.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_detections_camera_time" in index_names

    def test_detection_has_camera_object_type_composite_index(self):
        """Test Detection has camera_id + object_type composite index defined (NEM-1538)."""
        indexes = Detection.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_detections_camera_object_type" in index_names

    def test_detection_camera_object_type_index_columns(self):
        """Test camera_id + object_type index has correct columns (NEM-1538)."""
        indexes = Detection.__table_args__
        camera_object_idx = None
        for idx in indexes:
            if hasattr(idx, "name") and idx.name == "idx_detections_camera_object_type":
                camera_object_idx = idx
                break
        assert camera_object_idx is not None
        column_names = [col.name for col in camera_object_idx.columns]
        assert column_names == ["camera_id", "object_type"]


# =============================================================================
# Property-based Tests
# =============================================================================


class TestDetectionProperties:
    """Property-based tests for Detection model."""

    @given(confidence=confidence_scores)
    @settings(max_examples=50)
    def test_confidence_roundtrip(self, confidence: float):
        """Property: Confidence values roundtrip correctly."""
        detection = Detection(
            camera_id="test",
            file_path="/path",
            confidence=confidence,
        )
        # Allow for floating point precision
        assert abs(detection.confidence - confidence) < 1e-10

    @given(x=bbox_coords, y=bbox_coords, w=bbox_coords, h=bbox_coords)
    @settings(max_examples=50)
    def test_bbox_roundtrip(self, x: int, y: int, w: int, h: int):
        """Property: Bounding box values roundtrip correctly."""
        detection = Detection(
            camera_id="test",
            file_path="/path",
            bbox_x=x,
            bbox_y=y,
            bbox_width=w,
            bbox_height=h,
        )
        assert detection.bbox_x == x
        assert detection.bbox_y == y
        assert detection.bbox_width == w
        assert detection.bbox_height == h

    @given(object_type=object_types)
    @settings(max_examples=20)
    def test_object_type_roundtrip(self, object_type: str):
        """Property: Object type values roundtrip correctly."""
        detection = Detection(
            camera_id="test",
            file_path="/path",
            object_type=object_type,
        )
        assert detection.object_type == object_type

    @given(media_type=media_types)
    @settings(max_examples=10)
    def test_media_type_roundtrip(self, media_type: str):
        """Property: Media type values roundtrip correctly."""
        detection = Detection(
            camera_id="test",
            file_path="/path",
            media_type=media_type,
        )
        assert detection.media_type == media_type

    @given(
        duration=st.floats(min_value=0.0, max_value=86400.0, allow_nan=False),
        width=st.integers(min_value=1, max_value=8192),
        height=st.integers(min_value=1, max_value=4320),
    )
    @settings(max_examples=50)
    def test_video_metadata_roundtrip(self, duration: float, width: int, height: int):
        """Property: Video metadata values roundtrip correctly."""
        detection = Detection(
            camera_id="test",
            file_path="/path",
            media_type="video",
            duration=duration,
            video_width=width,
            video_height=height,
        )
        assert abs(detection.duration - duration) < 1e-10
        assert detection.video_width == width
        assert detection.video_height == height

    @given(camera_id=st.text(min_size=1, max_size=50), file_path=st.text(min_size=1, max_size=200))
    @settings(max_examples=50)
    def test_required_fields_roundtrip(self, camera_id: str, file_path: str):
        """Property: Required fields roundtrip correctly."""
        detection = Detection(
            camera_id=camera_id,
            file_path=file_path,
        )
        assert detection.camera_id == camera_id
        assert detection.file_path == file_path
