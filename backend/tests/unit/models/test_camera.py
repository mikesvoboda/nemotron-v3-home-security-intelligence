"""Unit tests for Camera model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- Factory method (from_folder_name)
- normalize_camera_id function
- Property-based tests for ID normalization
"""

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.camera import Camera, normalize_camera_id

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid folder names (non-empty strings)
folder_names = st.text(
    min_size=1,
    max_size=100,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs"), whitelist_characters="-_"
    ),
)

# Strategy for alphanumeric names with spaces/hyphens
valid_folder_names = st.from_regex(r"[A-Za-z][A-Za-z0-9 \-_]{0,49}", fullmatch=True)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_camera():
    """Create a sample camera for testing."""
    return Camera(
        id="front_door",
        name="Front Door",
        folder_path="/export/foscam/Front Door",
        status="online",
    )


@pytest.fixture
def sample_camera_with_timestamps():
    """Create a camera with all timestamp fields populated."""
    now = datetime.now(UTC)
    return Camera(
        id="back_yard",
        name="Back Yard",
        folder_path="/export/foscam/Back Yard",
        status="offline",
        created_at=now,
        last_seen_at=now,
    )


# =============================================================================
# normalize_camera_id Tests
# =============================================================================


class TestNormalizeCameraId:
    """Tests for the normalize_camera_id function."""

    def test_normalize_simple_name(self):
        """Test normalizing a simple name with space."""
        assert normalize_camera_id("Front Door") == "front_door"

    def test_normalize_hyphenated_name(self):
        """Test normalizing a hyphenated name."""
        assert normalize_camera_id("back-yard") == "back_yard"

    def test_normalize_mixed_case(self):
        """Test normalizing a mixed case name."""
        assert normalize_camera_id("GaRaGe") == "garage"

    def test_normalize_multiple_spaces(self):
        """Test normalizing multiple consecutive spaces."""
        assert normalize_camera_id("Front   Door") == "front_door"

    def test_normalize_multiple_hyphens(self):
        """Test normalizing multiple consecutive hyphens."""
        assert normalize_camera_id("front---door") == "front_door"

    def test_normalize_mixed_separators(self):
        """Test normalizing mixed spaces and hyphens."""
        assert normalize_camera_id("front - door") == "front_door"

    def test_normalize_leading_trailing_whitespace(self):
        """Test normalizing name with leading/trailing whitespace."""
        assert normalize_camera_id("  Front Door  ") == "front_door"

    def test_normalize_special_characters_removed(self):
        """Test that special characters are removed."""
        assert normalize_camera_id("Front@Door#1") == "frontdoor1"

    def test_normalize_empty_string(self):
        """Test normalizing empty string returns empty string."""
        assert normalize_camera_id("") == ""

    def test_normalize_only_whitespace(self):
        """Test normalizing only whitespace returns empty string."""
        assert normalize_camera_id("   ") == ""

    def test_normalize_only_special_chars(self):
        """Test normalizing only special chars returns empty string."""
        assert normalize_camera_id("@#$%") == ""

    def test_normalize_preserves_underscores(self):
        """Test that existing underscores are preserved."""
        assert normalize_camera_id("front_door") == "front_door"

    def test_normalize_numbers(self):
        """Test normalizing names with numbers."""
        assert normalize_camera_id("Camera 1") == "camera_1"
        assert normalize_camera_id("Camera1") == "camera1"

    def test_normalize_unicode_characters(self):
        """Test handling of unicode characters."""
        # Non-word characters are stripped
        result = normalize_camera_id("camera_")
        assert result == "camera"


# =============================================================================
# Camera Model Tests
# =============================================================================


class TestCameraModelInitialization:
    """Tests for Camera model initialization."""

    def test_camera_creation_minimal(self):
        """Test creating a camera with minimal required fields."""
        camera = Camera(
            id="test_cam",
            name="Test Camera",
            folder_path="/path/to/camera",
        )

        assert camera.id == "test_cam"
        assert camera.name == "Test Camera"
        assert camera.folder_path == "/path/to/camera"

    def test_camera_default_status_column_definition(self):
        """Test that status column has 'online' as default.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(Camera)
        status_col = mapper.columns["status"]
        assert status_col.default is not None
        assert status_col.default.arg == "online"

    def test_camera_custom_status(self):
        """Test camera with custom status."""
        camera = Camera(
            id="test_cam",
            name="Test Camera",
            folder_path="/path",
            status="offline",
        )

        assert camera.status == "offline"

    def test_camera_with_last_seen_at(self):
        """Test camera with last_seen_at timestamp."""
        now = datetime.now(UTC)
        camera = Camera(
            id="test_cam",
            name="Test Camera",
            folder_path="/path",
            last_seen_at=now,
        )

        assert camera.last_seen_at == now

    def test_camera_last_seen_at_default_is_none(self):
        """Test that last_seen_at defaults to None."""
        camera = Camera(
            id="test_cam",
            name="Test Camera",
            folder_path="/path",
        )

        assert camera.last_seen_at is None


class TestCameraModelAttributes:
    """Tests for Camera model attributes."""

    def test_camera_has_id_field(self, sample_camera):
        """Test camera has id field."""
        assert hasattr(sample_camera, "id")
        assert sample_camera.id == "front_door"

    def test_camera_has_name_field(self, sample_camera):
        """Test camera has name field."""
        assert hasattr(sample_camera, "name")
        assert sample_camera.name == "Front Door"

    def test_camera_has_folder_path_field(self, sample_camera):
        """Test camera has folder_path field."""
        assert hasattr(sample_camera, "folder_path")
        assert sample_camera.folder_path == "/export/foscam/Front Door"

    def test_camera_has_status_field(self, sample_camera):
        """Test camera has status field."""
        assert hasattr(sample_camera, "status")
        assert sample_camera.status == "online"

    def test_camera_has_created_at_field(self, sample_camera):
        """Test camera has created_at field."""
        assert hasattr(sample_camera, "created_at")

    def test_camera_has_last_seen_at_field(self, sample_camera):
        """Test camera has last_seen_at field."""
        assert hasattr(sample_camera, "last_seen_at")


class TestCameraRepr:
    """Tests for Camera string representation."""

    def test_camera_repr_contains_class_name(self, sample_camera):
        """Test repr contains class name."""
        repr_str = repr(sample_camera)
        assert "Camera" in repr_str

    def test_camera_repr_contains_id(self, sample_camera):
        """Test repr contains camera id."""
        repr_str = repr(sample_camera)
        assert "front_door" in repr_str

    def test_camera_repr_contains_name(self, sample_camera):
        """Test repr contains camera name."""
        repr_str = repr(sample_camera)
        assert "Front Door" in repr_str

    def test_camera_repr_contains_status(self, sample_camera):
        """Test repr contains camera status."""
        repr_str = repr(sample_camera)
        assert "online" in repr_str

    def test_camera_repr_format(self, sample_camera):
        """Test repr has expected format."""
        repr_str = repr(sample_camera)
        # Should be like: <Camera(id='front_door', name='Front Door', status='online')>
        assert repr_str.startswith("<Camera(")
        assert repr_str.endswith(")>")


class TestCameraFactoryMethod:
    """Tests for Camera.from_folder_name factory method."""

    def test_from_folder_name_basic(self):
        """Test creating camera from folder name."""
        camera = Camera.from_folder_name("Front Door", "/export/foscam/Front Door")

        assert camera.id == "front_door"
        assert camera.name == "Front Door"  # Original name preserved
        assert camera.folder_path == "/export/foscam/Front Door"
        assert camera.status == "online"

    def test_from_folder_name_hyphenated(self):
        """Test factory with hyphenated folder name."""
        camera = Camera.from_folder_name("back-yard", "/export/foscam/back-yard")

        assert camera.id == "back_yard"
        assert camera.name == "back-yard"  # Original preserved

    def test_from_folder_name_uppercase(self):
        """Test factory with uppercase folder name."""
        camera = Camera.from_folder_name("GARAGE", "/export/foscam/GARAGE")

        assert camera.id == "garage"
        assert camera.name == "GARAGE"  # Original preserved

    def test_from_folder_name_preserves_display_name(self):
        """Test that factory preserves original name for display."""
        camera = Camera.from_folder_name("Front   Door", "/path")

        # ID is normalized, name is preserved
        assert camera.id == "front_door"
        assert camera.name == "Front   Door"


class TestCameraRelationships:
    """Tests for Camera relationship definitions."""

    def test_camera_has_detections_relationship(self, sample_camera):
        """Test camera has detections relationship defined."""
        assert hasattr(sample_camera, "detections")

    def test_camera_has_events_relationship(self, sample_camera):
        """Test camera has events relationship defined."""
        assert hasattr(sample_camera, "events")

    def test_camera_has_zones_relationship(self, sample_camera):
        """Test camera has zones relationship defined."""
        assert hasattr(sample_camera, "zones")

    def test_camera_has_activity_baselines_relationship(self, sample_camera):
        """Test camera has activity_baselines relationship defined."""
        assert hasattr(sample_camera, "activity_baselines")

    def test_camera_has_class_baselines_relationship(self, sample_camera):
        """Test camera has class_baselines relationship defined."""
        assert hasattr(sample_camera, "class_baselines")


# =============================================================================
# Property-based Tests
# =============================================================================


class TestNormalizeCameraIdProperties:
    """Property-based tests for normalize_camera_id."""

    @given(name=st.text(min_size=1, max_size=100))
    @settings(max_examples=100)
    def test_normalize_returns_lowercase(self, name: str):
        """Property: Normalized IDs are always lowercase."""
        result = normalize_camera_id(name)
        assert result == result.lower()

    @given(name=st.text(min_size=1, max_size=100))
    @settings(max_examples=100)
    def test_normalize_no_spaces_or_hyphens(self, name: str):
        """Property: Normalized IDs contain no spaces or hyphens."""
        result = normalize_camera_id(name)
        assert " " not in result
        assert "-" not in result

    @given(name=st.text(min_size=1, max_size=100))
    @settings(max_examples=100)
    def test_normalize_only_valid_chars(self, name: str):
        """Property: Normalized IDs contain only alphanumeric and underscore."""
        result = normalize_camera_id(name)
        for char in result:
            assert char.isalnum() or char == "_", f"Invalid char: {char!r}"

    @given(name=st.text(min_size=1, max_size=100))
    @settings(max_examples=100)
    def test_normalize_no_leading_trailing_underscores(self, name: str):
        """Property: Normalized IDs have no leading/trailing underscores."""
        result = normalize_camera_id(name)
        if result:  # Only check non-empty results
            assert not result.startswith("_")
            assert not result.endswith("_")

    @given(name=st.text(min_size=1, max_size=100))
    @settings(max_examples=100)
    def test_normalize_no_consecutive_underscores(self, name: str):
        """Property: Normalized IDs have no consecutive underscores."""
        result = normalize_camera_id(name)
        assert "__" not in result

    @given(name=valid_folder_names)
    @settings(max_examples=50)
    def test_normalize_idempotent(self, name: str):
        """Property: Normalizing twice gives same result as once."""
        once = normalize_camera_id(name)
        twice = normalize_camera_id(once)
        assert once == twice


class TestCameraFromFolderNameProperties:
    """Property-based tests for Camera.from_folder_name."""

    @given(folder_name=valid_folder_names)
    @settings(max_examples=50)
    def test_factory_id_matches_normalize(self, folder_name: str):
        """Property: Factory method ID matches normalize_camera_id output."""
        camera = Camera.from_folder_name(folder_name, "/path")
        expected_id = normalize_camera_id(folder_name)
        assert camera.id == expected_id

    @given(folder_name=valid_folder_names)
    @settings(max_examples=50)
    def test_factory_preserves_original_name(self, folder_name: str):
        """Property: Factory method preserves original folder name."""
        camera = Camera.from_folder_name(folder_name, "/path")
        assert camera.name == folder_name

    @given(folder_name=valid_folder_names, path=st.text(min_size=1, max_size=200))
    @settings(max_examples=50)
    def test_factory_preserves_path(self, folder_name: str, path: str):
        """Property: Factory method preserves folder path."""
        camera = Camera.from_folder_name(folder_name, path)
        assert camera.folder_path == path

    @given(folder_name=valid_folder_names)
    @settings(max_examples=50)
    def test_factory_status_always_online(self, folder_name: str):
        """Property: Factory method always sets status to 'online'."""
        camera = Camera.from_folder_name(folder_name, "/path")
        assert camera.status == "online"
