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


# =============================================================================
# RTSP/ONVIF Schema Tests (NEM-4191)
# =============================================================================


class TestCameraCreateRTSPFields:
    """Tests for CameraCreate RTSP/ONVIF field validation.

    NEM-4191: Tests for new schema fields supporting RTSP and ONVIF streaming:
    - ingestion_mode: 'ftp' | 'rtsp' | 'onvif'
    - rtsp_url: nullable string with URL format validation
    - rtsp_username: nullable string
    - rtsp_password: nullable string
    - stream_profile: 'main' | 'sub' | 'both' (nullable)
    - motion_sensitivity: float 0.0-1.0 (default 0.5)
    """

    def test_create_camera_with_rtsp_mode(self) -> None:
        """Test creating camera with RTSP ingestion mode."""
        camera = CameraCreate(
            name="RTSP Camera",
            folder_path="/export/cameras/rtsp",
            ingestion_mode="rtsp",
            rtsp_url="rtsp://192.168.1.100:554/stream1",
        )
        assert camera.ingestion_mode == "rtsp"
        assert camera.rtsp_url == "rtsp://192.168.1.100:554/stream1"

    def test_create_camera_with_onvif_mode(self) -> None:
        """Test creating camera with ONVIF ingestion mode."""
        camera = CameraCreate(
            name="ONVIF Camera",
            folder_path="/export/cameras/onvif",
            ingestion_mode="onvif",
            rtsp_url="rtsp://192.168.1.101:554/onvif1",
        )
        assert camera.ingestion_mode == "onvif"

    def test_create_camera_defaults_to_ftp_mode(self) -> None:
        """Test that ingestion_mode defaults to 'ftp' when not specified."""
        camera = CameraCreate(name="Default Camera", folder_path="/export/cameras/default")
        assert camera.ingestion_mode == "ftp"

    def test_create_camera_with_complete_rtsp_config(self) -> None:
        """Test creating camera with all RTSP fields populated."""
        camera = CameraCreate(
            name="Complete RTSP Camera",
            folder_path="/export/cameras/complete",
            ingestion_mode="rtsp",
            rtsp_url="rtsp://192.168.1.100:554/stream1",
            rtsp_username="admin",
            rtsp_password="secret123",  # pragma: allowlist secret
            stream_profile="main",
            motion_sensitivity=0.75,
        )
        assert camera.ingestion_mode == "rtsp"
        assert camera.rtsp_url == "rtsp://192.168.1.100:554/stream1"
        assert camera.rtsp_username == "admin"
        assert camera.rtsp_password == "secret123"  # pragma: allowlist secret
        assert camera.stream_profile == "main"
        assert camera.motion_sensitivity == 0.75

    def test_create_camera_rtsp_fields_optional(self) -> None:
        """Test that RTSP fields are optional for FTP cameras."""
        camera = CameraCreate(
            name="FTP Camera", folder_path="/export/cameras/ftp", ingestion_mode="ftp"
        )
        assert camera.rtsp_url is None
        assert camera.rtsp_username is None
        assert camera.rtsp_password is None
        assert camera.stream_profile is None

    def test_motion_sensitivity_defaults_to_0_5(self) -> None:
        """Test that motion_sensitivity defaults to 0.5."""
        camera = CameraCreate(name="Default Motion", folder_path="/export/cameras/motion")
        assert camera.motion_sensitivity == 0.5


class TestCameraCreateRTSPURLValidation:
    """Tests for RTSP URL format validation."""

    def test_valid_rtsp_url_basic(self) -> None:
        """Test that a basic RTSP URL is accepted."""
        camera = CameraCreate(
            name="Test",
            folder_path="/export/test",
            rtsp_url="rtsp://192.168.1.100:554/stream",
        )
        assert camera.rtsp_url == "rtsp://192.168.1.100:554/stream"

    def test_valid_rtsp_url_with_auth(self) -> None:
        """Test that RTSP URL with embedded auth is accepted."""
        camera = CameraCreate(
            name="Test",
            folder_path="/export/test",
            rtsp_url="rtsp://user:pass@192.168.1.100:554/stream",  # pragma: allowlist secret
        )
        assert (
            camera.rtsp_url
            == "rtsp://user:pass@192.168.1.100:554/stream"  # pragma: allowlist secret
        )

    def test_valid_rtsps_url(self) -> None:
        """Test that RTSPS (secure) URL is accepted."""
        camera = CameraCreate(
            name="Test",
            folder_path="/export/test",
            rtsp_url="rtsps://192.168.1.100:554/stream",
        )
        assert camera.rtsp_url == "rtsps://192.168.1.100:554/stream"

    def test_valid_rtsp_url_with_hostname(self) -> None:
        """Test that RTSP URL with hostname is accepted."""
        camera = CameraCreate(
            name="Test",
            folder_path="/export/test",
            rtsp_url="rtsp://camera.local:554/stream1",
        )
        assert camera.rtsp_url == "rtsp://camera.local:554/stream1"

    def test_invalid_rtsp_url_wrong_scheme(self) -> None:
        """Test that non-RTSP URL scheme is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(
                name="Test",
                folder_path="/export/test",
                rtsp_url="http://192.168.1.100/stream",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("rtsp_url",) for e in errors)

    def test_invalid_rtsp_url_malformed(self) -> None:
        """Test that malformed URL is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(
                name="Test",
                folder_path="/export/test",
                rtsp_url="not a valid url",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("rtsp_url",) for e in errors)

    def test_rtsp_url_none_allowed(self) -> None:
        """Test that rtsp_url can be None."""
        camera = CameraCreate(
            name="Test",
            folder_path="/export/test",
            ingestion_mode="ftp",
            rtsp_url=None,
        )
        assert camera.rtsp_url is None


class TestCameraCreateStreamProfileValidation:
    """Tests for stream_profile field validation."""

    def test_stream_profile_main_accepted(self) -> None:
        """Test that 'main' stream profile is accepted."""
        camera = CameraCreate(name="Test", folder_path="/export/test", stream_profile="main")
        assert camera.stream_profile == "main"

    def test_stream_profile_sub_accepted(self) -> None:
        """Test that 'sub' stream profile is accepted."""
        camera = CameraCreate(name="Test", folder_path="/export/test", stream_profile="sub")
        assert camera.stream_profile == "sub"

    def test_stream_profile_both_accepted(self) -> None:
        """Test that 'both' stream profile is accepted."""
        camera = CameraCreate(name="Test", folder_path="/export/test", stream_profile="both")
        assert camera.stream_profile == "both"

    def test_stream_profile_invalid_rejected(self) -> None:
        """Test that invalid stream profile is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(
                name="Test",
                folder_path="/export/test",
                stream_profile="invalid",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("stream_profile",) for e in errors)

    def test_stream_profile_none_allowed(self) -> None:
        """Test that stream_profile can be None."""
        camera = CameraCreate(name="Test", folder_path="/export/test", stream_profile=None)
        assert camera.stream_profile is None


class TestCameraCreateMotionSensitivityValidation:
    """Tests for motion_sensitivity range validation."""

    def test_motion_sensitivity_valid_mid_range(self) -> None:
        """Test that mid-range motion_sensitivity is accepted."""
        camera = CameraCreate(name="Test", folder_path="/export/test", motion_sensitivity=0.5)
        assert camera.motion_sensitivity == 0.5

    def test_motion_sensitivity_minimum_value(self) -> None:
        """Test that 0.0 is accepted as minimum."""
        camera = CameraCreate(name="Test", folder_path="/export/test", motion_sensitivity=0.0)
        assert camera.motion_sensitivity == 0.0

    def test_motion_sensitivity_maximum_value(self) -> None:
        """Test that 1.0 is accepted as maximum."""
        camera = CameraCreate(name="Test", folder_path="/export/test", motion_sensitivity=1.0)
        assert camera.motion_sensitivity == 1.0

    def test_motion_sensitivity_below_minimum_rejected(self) -> None:
        """Test that values below 0.0 are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(
                name="Test",
                folder_path="/export/test",
                motion_sensitivity=-0.1,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("motion_sensitivity",) for e in errors)

    def test_motion_sensitivity_above_maximum_rejected(self) -> None:
        """Test that values above 1.0 are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(
                name="Test",
                folder_path="/export/test",
                motion_sensitivity=1.1,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("motion_sensitivity",) for e in errors)


class TestCameraCreateIngestionModeValidation:
    """Tests for ingestion_mode enum validation."""

    def test_ingestion_mode_ftp_accepted(self) -> None:
        """Test that 'ftp' ingestion mode is accepted."""
        camera = CameraCreate(name="Test", folder_path="/export/test", ingestion_mode="ftp")
        assert camera.ingestion_mode == "ftp"

    def test_ingestion_mode_rtsp_accepted(self) -> None:
        """Test that 'rtsp' ingestion mode is accepted."""
        camera = CameraCreate(name="Test", folder_path="/export/test", ingestion_mode="rtsp")
        assert camera.ingestion_mode == "rtsp"

    def test_ingestion_mode_onvif_accepted(self) -> None:
        """Test that 'onvif' ingestion mode is accepted."""
        camera = CameraCreate(name="Test", folder_path="/export/test", ingestion_mode="onvif")
        assert camera.ingestion_mode == "onvif"

    def test_ingestion_mode_invalid_rejected(self) -> None:
        """Test that invalid ingestion mode is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(
                name="Test",
                folder_path="/export/test",
                ingestion_mode="invalid",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("ingestion_mode",) for e in errors)


class TestCameraCreateConditionalValidation:
    """Tests for conditional field validation based on ingestion_mode.

    NEM-4191: When ingestion_mode is 'rtsp' or 'onvif', rtsp_url should be required.
    """

    def test_rtsp_mode_requires_rtsp_url(self) -> None:
        """Test that RTSP mode requires rtsp_url to be provided."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(
                name="Test",
                folder_path="/export/test",
                ingestion_mode="rtsp",
                rtsp_url=None,
            )

        errors = exc_info.value.errors()
        # Should have validation error indicating rtsp_url is required for RTSP mode
        assert any("rtsp_url" in str(e) for e in errors)

    def test_onvif_mode_requires_rtsp_url(self) -> None:
        """Test that ONVIF mode requires rtsp_url to be provided."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreate(
                name="Test",
                folder_path="/export/test",
                ingestion_mode="onvif",
                rtsp_url=None,
            )

        errors = exc_info.value.errors()
        # Should have validation error indicating rtsp_url is required for ONVIF mode
        assert any("rtsp_url" in str(e) for e in errors)

    def test_ftp_mode_allows_missing_rtsp_url(self) -> None:
        """Test that FTP mode allows rtsp_url to be None."""
        camera = CameraCreate(
            name="Test",
            folder_path="/export/test",
            ingestion_mode="ftp",
            rtsp_url=None,
        )
        assert camera.ingestion_mode == "ftp"
        assert camera.rtsp_url is None


class TestCameraUpdateRTSPFields:
    """Tests for CameraUpdate RTSP/ONVIF field validation."""

    def test_update_ingestion_mode_to_rtsp(self) -> None:
        """Test updating ingestion_mode to RTSP."""
        update = CameraUpdate(ingestion_mode="rtsp")
        assert update.ingestion_mode == "rtsp"

    def test_update_rtsp_url(self) -> None:
        """Test updating rtsp_url."""
        update = CameraUpdate(rtsp_url="rtsp://192.168.1.100:554/stream1")
        assert update.rtsp_url == "rtsp://192.168.1.100:554/stream1"

    def test_update_rtsp_credentials(self) -> None:
        """Test updating RTSP username and password."""
        update = CameraUpdate(rtsp_username="admin", rtsp_password="newpass")
        assert update.rtsp_username == "admin"
        assert update.rtsp_password == "newpass"  # pragma: allowlist secret

    def test_update_stream_profile(self) -> None:
        """Test updating stream_profile."""
        update = CameraUpdate(stream_profile="both")
        assert update.stream_profile == "both"

    def test_update_motion_sensitivity(self) -> None:
        """Test updating motion_sensitivity."""
        update = CameraUpdate(motion_sensitivity=0.8)
        assert update.motion_sensitivity == 0.8

    def test_update_all_rtsp_fields(self) -> None:
        """Test updating all RTSP fields at once."""
        update = CameraUpdate(
            ingestion_mode="rtsp",
            rtsp_url="rtsp://192.168.1.100:554/stream1",
            rtsp_username="admin",
            rtsp_password="secret",  # pragma: allowlist secret
            stream_profile="main",
            motion_sensitivity=0.7,
        )
        assert update.ingestion_mode == "rtsp"
        assert update.rtsp_url == "rtsp://192.168.1.100:554/stream1"
        assert update.rtsp_username == "admin"
        assert update.rtsp_password == "secret"  # pragma: allowlist secret
        assert update.stream_profile == "main"
        assert update.motion_sensitivity == 0.7

    def test_update_rtsp_fields_to_none(self) -> None:
        """Test clearing RTSP fields by setting to None."""
        update = CameraUpdate(
            rtsp_url=None,
            rtsp_username=None,
            rtsp_password=None,
            stream_profile=None,
        )
        assert update.rtsp_url is None
        assert update.rtsp_username is None
        assert update.rtsp_password is None
        assert update.stream_profile is None

    def test_update_motion_sensitivity_validation(self) -> None:
        """Test that motion_sensitivity validation applies to updates."""
        with pytest.raises(ValidationError) as exc_info:
            CameraUpdate(motion_sensitivity=1.5)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("motion_sensitivity",) for e in errors)

    def test_update_invalid_rtsp_url_rejected(self) -> None:
        """Test that invalid RTSP URL is rejected in updates."""
        with pytest.raises(ValidationError) as exc_info:
            CameraUpdate(rtsp_url="http://invalid-scheme.com/stream")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("rtsp_url",) for e in errors)


class TestCameraResponseRTSPFields:
    """Tests for CameraResponse with RTSP/ONVIF fields.

    Note: CameraResponse schema should include the new RTSP fields
    in its response model for API consistency.
    """

    def test_camera_response_has_rtsp_fields(self) -> None:
        """Test that CameraResponse model includes RTSP fields."""
        from backend.api.schemas.camera import CameraResponse

        # Check that the schema has the RTSP field annotations
        fields = CameraResponse.model_fields
        assert "ingestion_mode" in fields
        assert "rtsp_url" in fields
        assert "rtsp_username" in fields
        assert "rtsp_password" in fields
        assert "stream_profile" in fields
        assert "motion_sensitivity" in fields
