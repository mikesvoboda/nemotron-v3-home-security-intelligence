"""Unit tests for camera schema Pydantic validation (NEM-2569).

Tests comprehensive input validation for camera create/update request models:
- Name length constraints
- Name character restrictions (prevent control characters, excessive whitespace)
- Folder path format validation
- Path traversal prevention
- Forbidden character rejection
- Edge cases and boundary conditions

These tests follow TDD methodology - they define expected behavior
before implementation.
"""

import pytest
from pydantic import ValidationError

from backend.api.schemas.camera import CameraCreate, CameraUpdate


class TestCameraCreateNameValidation:
    """Tests for CameraCreate name field validation."""

    def test_valid_name_simple(self) -> None:
        """Test that a simple valid name is accepted."""
        camera = CameraCreate(name="Front Door", folder_path="/export/foscam/front_door")
        assert camera.name == "Front Door"

    def test_valid_name_with_numbers(self) -> None:
        """Test that a name with numbers is accepted."""
        camera = CameraCreate(name="Camera 1", folder_path="/export/foscam/camera_1")
        assert camera.name == "Camera 1"

    def test_valid_name_with_special_chars(self) -> None:
        """Test that a name with safe special characters is accepted."""
        camera = CameraCreate(name="Front-Door (Main)", folder_path="/export/foscam/front_door")
        assert camera.name == "Front-Door (Main)"

    def test_valid_name_unicode(self) -> None:
        """Test that a name with unicode characters is accepted."""
        camera = CameraCreate(name="Cam\u00e9ra Principal", folder_path="/export/foscam/principal")
        assert camera.name == "Cam\u00e9ra Principal"

    def test_name_empty_string_rejected(self) -> None:
        """Test that an empty name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="", folder_path="/export/foscam/test")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("name",)
        assert "at least 1 character" in errors[0]["msg"].lower()

    def test_name_too_long_rejected(self) -> None:
        """Test that a name exceeding max length is rejected."""
        long_name = "x" * 256  # Max is 255
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name=long_name, folder_path="/export/foscam/test")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("name",)
        assert "255" in errors[0]["msg"] or "at most" in errors[0]["msg"].lower()

    def test_name_max_length_accepted(self) -> None:
        """Test that a name at exactly max length is accepted."""
        max_name = "x" * 255
        camera = CameraCreate(name=max_name, folder_path="/export/foscam/test")
        assert len(camera.name) == 255

    def test_name_whitespace_only_rejected(self) -> None:
        """Test that a name with only whitespace is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="   ", folder_path="/export/foscam/test")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("name",)
        # Should fail because whitespace-only is effectively empty

    def test_name_with_null_byte_rejected(self) -> None:
        """Test that a name with null byte is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Camera\x00Test", folder_path="/export/foscam/test")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("name",)

    def test_name_with_control_chars_rejected(self) -> None:
        """Test that a name with control characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Camera\x1bTest", folder_path="/export/foscam/test")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("name",)

    def test_name_with_newline_rejected(self) -> None:
        """Test that a name with newline is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Camera\nTest", folder_path="/export/foscam/test")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("name",)

    def test_name_with_tab_rejected(self) -> None:
        """Test that a name with tab character is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Camera\tTest", folder_path="/export/foscam/test")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("name",)

    def test_name_leading_trailing_whitespace_stripped(self) -> None:
        """Test that leading/trailing whitespace in name is stripped."""
        camera = CameraCreate(name="  Front Door  ", folder_path="/export/foscam/front")
        assert camera.name == "Front Door"


class TestCameraCreateFolderPathValidation:
    """Tests for CameraCreate folder_path field validation."""

    def test_valid_folder_path_absolute(self) -> None:
        """Test that an absolute path is accepted."""
        camera = CameraCreate(name="Test", folder_path="/export/foscam/test_camera")
        assert camera.folder_path == "/export/foscam/test_camera"

    def test_valid_folder_path_with_underscores(self) -> None:
        """Test that a path with underscores is accepted."""
        camera = CameraCreate(name="Test", folder_path="/export/foscam/front_door_camera")
        assert camera.folder_path == "/export/foscam/front_door_camera"

    def test_valid_folder_path_with_hyphens(self) -> None:
        """Test that a path with hyphens is accepted."""
        camera = CameraCreate(name="Test", folder_path="/export/foscam/front-door")
        assert camera.folder_path == "/export/foscam/front-door"

    def test_folder_path_empty_rejected(self) -> None:
        """Test that an empty folder_path is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Test", folder_path="")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("folder_path",) for e in errors)

    def test_folder_path_too_long_rejected(self) -> None:
        """Test that a folder_path exceeding max length is rejected."""
        long_path = "/export/foscam/" + "x" * 486  # Total > 500
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Test", folder_path=long_path)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("folder_path",) for e in errors)

    def test_folder_path_traversal_dot_dot_rejected(self) -> None:
        """Test that path traversal with .. is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Test", folder_path="/export/foscam/../../../etc/passwd")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("folder_path",)
        assert "traversal" in errors[0]["msg"].lower()

    def test_folder_path_traversal_encoded_rejected(self) -> None:
        """Test that encoded path traversal is rejected (.. in middle)."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Test", folder_path="/export/foscam/test/../secret")

        errors = exc_info.value.errors()
        assert errors[0]["loc"] == ("folder_path",)
        assert "traversal" in errors[0]["msg"].lower()

    def test_folder_path_with_angle_brackets_rejected(self) -> None:
        """Test that path with angle brackets is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Test", folder_path="/export/foscam/<camera>")

        errors = exc_info.value.errors()
        assert errors[0]["loc"] == ("folder_path",)
        assert "forbidden" in errors[0]["msg"].lower()

    def test_folder_path_with_pipe_rejected(self) -> None:
        """Test that path with pipe character is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Test", folder_path="/export/foscam/test|inject")

        errors = exc_info.value.errors()
        assert errors[0]["loc"] == ("folder_path",)
        assert "forbidden" in errors[0]["msg"].lower()

    def test_folder_path_with_question_mark_rejected(self) -> None:
        """Test that path with question mark is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Test", folder_path="/export/foscam/test?query")

        errors = exc_info.value.errors()
        assert errors[0]["loc"] == ("folder_path",)
        assert "forbidden" in errors[0]["msg"].lower()

    def test_folder_path_with_asterisk_rejected(self) -> None:
        """Test that path with asterisk is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Test", folder_path="/export/foscam/test*")

        errors = exc_info.value.errors()
        assert errors[0]["loc"] == ("folder_path",)
        assert "forbidden" in errors[0]["msg"].lower()

    def test_folder_path_with_colon_rejected(self) -> None:
        """Test that path with colon (not at start for Windows) is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Test", folder_path="/export/foscam/test:stream")

        errors = exc_info.value.errors()
        assert errors[0]["loc"] == ("folder_path",)
        assert "forbidden" in errors[0]["msg"].lower()

    def test_folder_path_with_double_quote_rejected(self) -> None:
        """Test that path with double quote is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Test", folder_path='/export/foscam/test"camera')

        errors = exc_info.value.errors()
        assert errors[0]["loc"] == ("folder_path",)
        assert "forbidden" in errors[0]["msg"].lower()

    def test_folder_path_with_null_byte_rejected(self) -> None:
        """Test that path with null byte is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Test", folder_path="/export/foscam/test\x00camera")

        errors = exc_info.value.errors()
        assert errors[0]["loc"] == ("folder_path",)
        assert "forbidden" in errors[0]["msg"].lower()

    def test_folder_path_with_control_char_rejected(self) -> None:
        """Test that path with control character is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Test", folder_path="/export/foscam/test\x1fcamera")

        errors = exc_info.value.errors()
        assert errors[0]["loc"] == ("folder_path",)
        assert "forbidden" in errors[0]["msg"].lower()

    def test_folder_path_relative_warning(self) -> None:
        """Test that relative paths are accepted but noted.

        Note: This may be allowed since path resolution happens at runtime.
        The schema allows relative paths as they may be valid in some contexts.
        """
        camera = CameraCreate(name="Test", folder_path="relative/path")
        assert camera.folder_path == "relative/path"

    def test_folder_path_single_dot_allowed(self) -> None:
        """Test that single dot in path is allowed (not traversal)."""
        camera = CameraCreate(name="Test", folder_path="/export/foscam/.hidden")
        assert camera.folder_path == "/export/foscam/.hidden"

    def test_folder_path_dot_in_name_allowed(self) -> None:
        """Test that dots within component names are allowed."""
        camera = CameraCreate(name="Test", folder_path="/export/foscam/camera.backup")
        assert camera.folder_path == "/export/foscam/camera.backup"


class TestCameraUpdateNameValidation:
    """Tests for CameraUpdate name field validation."""

    def test_name_none_allowed(self) -> None:
        """Test that None name is allowed for partial updates."""
        update = CameraUpdate(status="offline")
        assert update.name is None

    def test_valid_name_update(self) -> None:
        """Test valid name update."""
        update = CameraUpdate(name="Updated Camera Name")
        assert update.name == "Updated Camera Name"

    def test_name_empty_string_rejected(self) -> None:
        """Test that an empty name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraUpdate(name="")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_name_too_long_rejected(self) -> None:
        """Test that a name exceeding max length is rejected."""
        long_name = "x" * 256
        with pytest.raises(ValidationError) as exc_info:
            CameraUpdate(name=long_name)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_name_whitespace_only_rejected(self) -> None:
        """Test that a name with only whitespace is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraUpdate(name="   ")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_name_with_control_chars_rejected(self) -> None:
        """Test that a name with control characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraUpdate(name="Camera\x00Test")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_name_leading_trailing_whitespace_stripped(self) -> None:
        """Test that leading/trailing whitespace in name is stripped."""
        update = CameraUpdate(name="  Updated Name  ")
        assert update.name == "Updated Name"


class TestCameraUpdateFolderPathValidation:
    """Tests for CameraUpdate folder_path field validation."""

    def test_folder_path_none_allowed(self) -> None:
        """Test that None folder_path is allowed for partial updates."""
        update = CameraUpdate(status="offline")
        assert update.folder_path is None

    def test_valid_folder_path_update(self) -> None:
        """Test valid folder_path update."""
        update = CameraUpdate(folder_path="/export/foscam/new_location")
        assert update.folder_path == "/export/foscam/new_location"

    def test_folder_path_empty_rejected(self) -> None:
        """Test that an empty folder_path is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraUpdate(folder_path="")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("folder_path",) for e in errors)

    def test_folder_path_traversal_rejected(self) -> None:
        """Test that path traversal is rejected on update."""
        with pytest.raises(ValidationError) as exc_info:
            CameraUpdate(folder_path="/export/foscam/../../../etc/passwd")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("folder_path",) for e in errors)

    def test_folder_path_with_forbidden_chars_rejected(self) -> None:
        """Test that forbidden characters are rejected on update."""
        with pytest.raises(ValidationError) as exc_info:
            CameraUpdate(folder_path="/export/foscam/test<>|")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("folder_path",) for e in errors)


class TestCameraCreateStatusValidation:
    """Tests for CameraCreate status field validation."""

    def test_valid_status_online(self) -> None:
        """Test that online status is accepted."""
        camera = CameraCreate(name="Test", folder_path="/export/foscam/test", status="online")
        assert camera.status.value == "online"

    def test_valid_status_offline(self) -> None:
        """Test that offline status is accepted."""
        camera = CameraCreate(name="Test", folder_path="/export/foscam/test", status="offline")
        assert camera.status.value == "offline"

    def test_valid_status_error(self) -> None:
        """Test that error status is accepted."""
        camera = CameraCreate(name="Test", folder_path="/export/foscam/test", status="error")
        assert camera.status.value == "error"

    def test_valid_status_unknown(self) -> None:
        """Test that unknown status is accepted."""
        camera = CameraCreate(name="Test", folder_path="/export/foscam/test", status="unknown")
        assert camera.status.value == "unknown"

    def test_invalid_status_rejected(self) -> None:
        """Test that invalid status is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Test", folder_path="/export/foscam/test", status="invalid_status")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("status",) for e in errors)

    def test_default_status_is_online(self) -> None:
        """Test that default status is online."""
        camera = CameraCreate(name="Test", folder_path="/export/foscam/test")
        assert camera.status.value == "online"


class TestCameraSchemaValidationErrorMessages:
    """Tests for validation error message quality."""

    def test_path_traversal_error_message_is_descriptive(self) -> None:
        """Test that path traversal error message is helpful."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Test", folder_path="/export/../secret")

        error_msg = str(exc_info.value)
        assert "traversal" in error_msg.lower() or ".." in error_msg

    def test_forbidden_chars_error_message_lists_chars(self) -> None:
        """Test that forbidden character error is descriptive."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="Test", folder_path="/export/foscam/test<>")

        error_msg = str(exc_info.value)
        assert "forbidden" in error_msg.lower()


class TestCameraCreateMultipleValidationErrors:
    """Tests for multiple validation errors in single request."""

    def test_multiple_field_errors_reported(self) -> None:
        """Test that errors in multiple fields are all reported."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(name="", folder_path="")

        errors = exc_info.value.errors()
        # Should have errors for both name and folder_path
        locs = {e["loc"][0] for e in errors}
        assert "name" in locs
        assert "folder_path" in locs


class TestCameraUpdatePartialValidation:
    """Tests for partial update validation (only provided fields validated)."""

    def test_empty_update_allowed(self) -> None:
        """Test that an update with no fields is technically valid."""
        update = CameraUpdate()
        assert update.name is None
        assert update.folder_path is None
        assert update.status is None

    def test_single_field_update_valid(self) -> None:
        """Test that updating a single field is valid."""
        update = CameraUpdate(status="offline")
        assert update.status.value == "offline"
        assert update.name is None
        assert update.folder_path is None

    def test_multiple_field_update_valid(self) -> None:
        """Test that updating multiple fields is valid."""
        update = CameraUpdate(name="New Name", status="offline")
        assert update.name == "New Name"
        assert update.status.value == "offline"
        assert update.folder_path is None
