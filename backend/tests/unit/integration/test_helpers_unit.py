"""Unit tests for integration test helper functions."""

import pytest
from backend.tests.integration.test_helpers import get_error_message, has_error


class TestGetErrorMessage:
    """Test the get_error_message helper function."""

    def test_old_format_detail_string(self):
        """Test extracting message from old format with string detail."""
        data = {"detail": "Camera not found"}
        assert get_error_message(data) == "Camera not found"

    def test_new_format_simple_error(self):
        """Test extracting message from new format with simple error."""
        data = {"error": {"code": "NOT_FOUND", "message": "Camera not found"}}
        assert get_error_message(data) == "Camera not found"

    def test_new_format_validation_error_single(self):
        """Test extracting message from new format with single validation error."""
        data = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "errors": [
                    {
                        "field": "query.limit",
                        "message": "Input should be less than or equal to 100",
                        "value": "500",
                    }
                ],
            }
        }
        expected = "query.limit: Input should be less than or equal to 100"
        assert get_error_message(data) == expected

    def test_new_format_validation_error_multiple(self):
        """Test extracting message from new format with multiple validation errors."""
        data = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "errors": [
                    {
                        "field": "query.entity_type",
                        "message": "Input should be 'person' or 'vehicle'",
                        "value": "invalid",
                    },
                    {
                        "field": "query.limit",
                        "message": "Input should be greater than 0",
                        "value": "-1",
                    },
                ],
            }
        }
        result = get_error_message(data)
        # Check both error messages are present
        assert "query.entity_type" in result
        assert "Input should be 'person' or 'vehicle'" in result
        assert "query.limit" in result
        assert "Input should be greater than 0" in result

    def test_new_format_validation_error_no_field(self):
        """Test validation error without field name."""
        data = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "errors": [
                    {
                        "message": "Missing required field",
                    }
                ],
            }
        }
        assert get_error_message(data) == "Missing required field"

    def test_new_format_validation_error_empty_errors(self):
        """Test validation error with empty errors array."""
        data = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "errors": [],
            }
        }
        # Should fall back to the message field
        assert get_error_message(data) == "Request validation failed"

    def test_missing_error_raises(self):
        """Test that missing error information raises KeyError."""
        data = {"status": "error"}
        with pytest.raises(KeyError, match="No error message found"):
            get_error_message(data)

    def test_empty_dict_raises(self):
        """Test that empty dict raises KeyError."""
        with pytest.raises(KeyError, match="No error message found"):
            get_error_message({})


class TestHasError:
    """Test the has_error helper function."""

    def test_has_error_old_format(self):
        """Test detecting error in old format."""
        assert has_error({"detail": "Error message"})

    def test_has_error_new_format(self):
        """Test detecting error in new format."""
        assert has_error({"error": {"code": "ERROR", "message": "Error message"}})

    def test_has_error_validation_format(self):
        """Test detecting validation error in new format."""
        data = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "errors": [{"field": "test", "message": "Invalid"}],
            }
        }
        assert has_error(data)

    def test_no_error(self):
        """Test no error detection for success response."""
        assert not has_error({"status": "ok", "data": []})

    def test_error_not_dict(self):
        """Test that error must be a dict."""
        assert not has_error({"error": "string error"})
