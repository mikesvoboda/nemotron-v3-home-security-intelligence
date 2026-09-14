"""Unit tests for cameras API field selection (sparse fieldsets).

Tests for the fields query parameter on the list cameras endpoint that enables
clients to request only specific fields in the response.

TDD Approach: These tests are written FIRST, before the implementation.
"""

from typing import ClassVar

import pytest


class TestCamerasFieldSelectionSchema:
    """Schema-level tests for cameras field selection behavior."""

    # Define the valid camera fields that can be requested
    VALID_CAMERA_FIELDS: ClassVar[set[str]] = {
        "id",
        "name",
        "folder_path",
        "status",
        "created_at",
        "last_seen_at",
    }

    def test_camera_response_fields_documentation(self):
        """Document the fields available in CameraResponse for field selection."""
        # This test documents the expected fields for reference
        assert "id" in self.VALID_CAMERA_FIELDS
        assert "name" in self.VALID_CAMERA_FIELDS
        assert "folder_path" in self.VALID_CAMERA_FIELDS
        assert "status" in self.VALID_CAMERA_FIELDS
        assert "created_at" in self.VALID_CAMERA_FIELDS
        assert "last_seen_at" in self.VALID_CAMERA_FIELDS


class TestCamerasFieldSelectionLogic:
    """Tests for field selection logic in list_cameras endpoint."""

    def test_filter_camera_dict_single_field(self):
        """Test filtering camera dict to single field."""
        from backend.api.utils.field_filter import filter_fields

        camera_dict = {
            "id": "front_door",
            "name": "Front Door Camera",
            "folder_path": "/export/foscam/front_door",
            "status": "online",
            "created_at": "2025-12-23T10:00:00Z",
            "last_seen_at": "2025-12-23T12:00:00Z",
        }

        result = filter_fields(camera_dict, {"id"})
        assert result == {"id": "front_door"}

    def test_filter_camera_dict_multiple_fields(self):
        """Test filtering camera dict to multiple fields."""
        from backend.api.utils.field_filter import filter_fields

        camera_dict = {
            "id": "front_door",
            "name": "Front Door Camera",
            "folder_path": "/export/foscam/front_door",
            "status": "online",
            "created_at": "2025-12-23T10:00:00Z",
            "last_seen_at": "2025-12-23T12:00:00Z",
        }

        result = filter_fields(camera_dict, {"id", "name", "status"})
        assert result == {
            "id": "front_door",
            "name": "Front Door Camera",
            "status": "online",
        }

    def test_filter_camera_dict_handles_none_last_seen(self):
        """Test that None last_seen_at is preserved when selected."""
        from backend.api.utils.field_filter import filter_fields

        camera_dict = {
            "id": "front_door",
            "name": "Front Door Camera",
            "folder_path": "/export/foscam/front_door",
            "status": "offline",
            "created_at": "2025-12-23T10:00:00Z",
            "last_seen_at": None,
        }

        result = filter_fields(camera_dict, {"id", "status", "last_seen_at"})
        assert result == {
            "id": "front_door",
            "status": "offline",
            "last_seen_at": None,
        }


class TestCamerasFieldValidation:
    """Tests for field validation in cameras endpoint."""

    VALID_CAMERA_FIELDS: ClassVar[set[str]] = {
        "id",
        "name",
        "folder_path",
        "status",
        "created_at",
        "last_seen_at",
    }

    def test_validate_valid_fields(self):
        """Test validation passes for valid fields."""
        from backend.api.utils.field_filter import validate_fields

        requested = {"id", "name", "status"}
        result = validate_fields(requested, self.VALID_CAMERA_FIELDS)
        assert result == {"id", "name", "status"}

    def test_validate_invalid_field_raises_error(self):
        """Test validation raises error for invalid fields."""
        from backend.api.utils.field_filter import FieldFilterError, validate_fields

        requested = {"id", "invalid_field", "name"}

        with pytest.raises(FieldFilterError) as exc_info:
            validate_fields(requested, self.VALID_CAMERA_FIELDS)

        assert "invalid_field" in str(exc_info.value)
        assert exc_info.value.invalid_fields == {"invalid_field"}

    def test_validate_all_fields_at_once(self):
        """Test validation with all valid camera fields."""
        from backend.api.utils.field_filter import validate_fields

        result = validate_fields(self.VALID_CAMERA_FIELDS, self.VALID_CAMERA_FIELDS)
        assert result == self.VALID_CAMERA_FIELDS


class TestCamerasFieldSelectionUsageExample:
    """Example usage tests demonstrating the expected field selection behavior."""

    def test_typical_dropdown_request(self):
        """Test typical dropdown request with minimal fields (just id and name)."""
        from backend.api.utils.field_filter import (
            filter_fields,
            parse_fields_param,
            validate_fields,
        )

        # Dropdown typically needs: id, name
        fields_param = "id,name"
        valid_fields = {
            "id",
            "name",
            "folder_path",
            "status",
            "created_at",
            "last_seen_at",
        }

        # Parse
        requested = parse_fields_param(fields_param)
        assert requested == {"id", "name"}

        # Validate
        validated = validate_fields(requested, valid_fields)
        assert validated == {"id", "name"}

        # Apply to camera data
        camera_dict = {
            "id": "front_door",
            "name": "Front Door Camera",
            "folder_path": "/export/foscam/front_door",
            "status": "online",
            "created_at": "2025-12-23T10:00:00Z",
            "last_seen_at": "2025-12-23T12:00:00Z",
        }

        result = filter_fields(camera_dict, validated)
        assert result == {
            "id": "front_door",
            "name": "Front Door Camera",
        }

    def test_typical_status_check_request(self):
        """Test typical status check request with id, name, status, last_seen_at."""
        from backend.api.utils.field_filter import (
            filter_fields,
            parse_fields_param,
            validate_fields,
        )

        fields_param = "id,name,status,last_seen_at"
        valid_fields = {
            "id",
            "name",
            "folder_path",
            "status",
            "created_at",
            "last_seen_at",
        }

        # Parse and validate
        requested = parse_fields_param(fields_param)
        validated = validate_fields(requested, valid_fields)

        # Apply to camera data
        camera_dict = {
            "id": "back_yard",
            "name": "Back Yard Camera",
            "folder_path": "/export/foscam/back_yard",
            "status": "offline",
            "created_at": "2025-12-20T08:00:00Z",
            "last_seen_at": "2025-12-22T18:30:00Z",
        }

        result = filter_fields(camera_dict, validated)
        assert result == {
            "id": "back_yard",
            "name": "Back Yard Camera",
            "status": "offline",
            "last_seen_at": "2025-12-22T18:30:00Z",
        }

    def test_filter_list_of_cameras(self):
        """Test filtering a list of camera dicts."""
        from backend.api.utils.field_filter import filter_fields

        cameras = [
            {
                "id": "front_door",
                "name": "Front Door",
                "folder_path": "/export/foscam/front_door",
                "status": "online",
                "created_at": "2025-12-23T10:00:00Z",
                "last_seen_at": "2025-12-23T12:00:00Z",
            },
            {
                "id": "back_yard",
                "name": "Back Yard",
                "folder_path": "/export/foscam/back_yard",
                "status": "offline",
                "created_at": "2025-12-20T08:00:00Z",
                "last_seen_at": None,
            },
        ]

        fields_to_include = {"id", "name", "status"}
        result = [filter_fields(c, fields_to_include) for c in cameras]

        assert result == [
            {"id": "front_door", "name": "Front Door", "status": "online"},
            {"id": "back_yard", "name": "Back Yard", "status": "offline"},
        ]
