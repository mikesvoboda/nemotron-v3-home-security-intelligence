"""Unit tests for RFC 7807 Problem Details schema.

Tests cover:
- ProblemDetail schema validation
- HTTP status code to phrase mapping
- Required vs optional field handling
- Model serialization with exclude_none
- Edge cases for unknown status codes

NEM-1425: Standardize error response format with RFC 7807 Problem Details
"""

import pytest
from pydantic import ValidationError

from backend.api.schemas.problem_details import (
    HTTP_STATUS_PHRASES,
    ProblemDetail,
    get_status_phrase,
)

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# get_status_phrase Tests
# =============================================================================


class TestGetStatusPhrase:
    """Tests for get_status_phrase function."""

    def test_common_client_errors(self):
        """Test common 4xx status phrases."""
        assert get_status_phrase(400) == "Bad Request"
        assert get_status_phrase(401) == "Unauthorized"
        assert get_status_phrase(403) == "Forbidden"
        assert get_status_phrase(404) == "Not Found"
        assert get_status_phrase(405) == "Method Not Allowed"
        assert get_status_phrase(409) == "Conflict"
        assert get_status_phrase(422) == "Unprocessable Content"
        assert get_status_phrase(429) == "Too Many Requests"

    def test_common_server_errors(self):
        """Test common 5xx status phrases."""
        assert get_status_phrase(500) == "Internal Server Error"
        assert get_status_phrase(501) == "Not Implemented"
        assert get_status_phrase(502) == "Bad Gateway"
        assert get_status_phrase(503) == "Service Unavailable"
        assert get_status_phrase(504) == "Gateway Timeout"

    def test_success_status_codes(self):
        """Test 2xx status phrases."""
        assert get_status_phrase(200) == "OK"
        assert get_status_phrase(201) == "Created"
        assert get_status_phrase(202) == "Accepted"
        assert get_status_phrase(204) == "No Content"
        assert get_status_phrase(206) == "Partial Content"

    def test_redirection_status_codes(self):
        """Test 3xx status phrases."""
        assert get_status_phrase(301) == "Moved Permanently"
        assert get_status_phrase(302) == "Found"
        assert get_status_phrase(304) == "Not Modified"
        assert get_status_phrase(307) == "Temporary Redirect"
        assert get_status_phrase(308) == "Permanent Redirect"

    def test_teapot_status_code(self):
        """Test RFC 2324 I'm a Teapot status."""
        assert get_status_phrase(418) == "I'm a Teapot"

    def test_unknown_status_code(self):
        """Test unknown status code returns Unknown Error."""
        assert get_status_phrase(999) == "Unknown Error"
        assert get_status_phrase(0) == "Unknown Error"
        assert get_status_phrase(-1) == "Unknown Error"

    def test_all_defined_status_codes_have_phrases(self):
        """Verify all standard HTTP status codes are defined."""
        # Common codes that should be present
        expected_codes = [
            100,
            101,
            200,
            201,
            204,
            206,
            301,
            302,
            304,
            307,
            308,
            400,
            401,
            403,
            404,
            405,
            408,
            409,
            410,
            413,
            415,
            422,
            429,
            500,
            501,
            502,
            503,
            504,
        ]
        for code in expected_codes:
            phrase = get_status_phrase(code)
            assert phrase != "Unknown Error", f"Status code {code} should have a phrase"
            assert isinstance(phrase, str)
            assert len(phrase) > 0


# =============================================================================
# ProblemDetail Schema Tests
# =============================================================================


class TestProblemDetailSchema:
    """Tests for ProblemDetail Pydantic model."""

    def test_minimal_valid_problem_detail(self):
        """Test creating ProblemDetail with only required fields."""
        problem = ProblemDetail(
            title="Not Found",
            status=404,
            detail="Resource not found",
        )

        assert problem.type == "about:blank"  # Default value
        assert problem.title == "Not Found"
        assert problem.status == 404
        assert problem.detail == "Resource not found"
        assert problem.instance is None  # Optional, defaults to None

    def test_full_problem_detail(self):
        """Test creating ProblemDetail with all fields."""
        problem = ProblemDetail(
            type="https://api.example.com/problems/camera-not-found",
            title="Not Found",
            status=404,
            detail="Camera 'front_door' does not exist",
            instance="/api/cameras/front_door",
        )

        assert problem.type == "https://api.example.com/problems/camera-not-found"
        assert problem.title == "Not Found"
        assert problem.status == 404
        assert problem.detail == "Camera 'front_door' does not exist"
        assert problem.instance == "/api/cameras/front_door"

    def test_default_type_is_about_blank(self):
        """Test that default type follows RFC 7807 recommendation."""
        problem = ProblemDetail(
            title="Bad Request",
            status=400,
            detail="Invalid request",
        )

        # RFC 7807 specifies "about:blank" as the default
        assert problem.type == "about:blank"

    def test_status_code_validation_minimum(self):
        """Test that status code must be >= 100."""
        with pytest.raises(ValidationError) as exc_info:
            ProblemDetail(
                title="Invalid",
                status=99,
                detail="Invalid status code",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("status",)
        assert "greater than or equal to 100" in errors[0]["msg"]

    def test_status_code_validation_maximum(self):
        """Test that status code must be <= 599."""
        with pytest.raises(ValidationError) as exc_info:
            ProblemDetail(
                title="Invalid",
                status=600,
                detail="Invalid status code",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("status",)
        assert "less than or equal to 599" in errors[0]["msg"]

    def test_valid_status_code_boundaries(self):
        """Test valid status codes at boundaries."""
        # Minimum valid
        problem_100 = ProblemDetail(
            title="Continue",
            status=100,
            detail="Continue",
        )
        assert problem_100.status == 100

        # Maximum valid
        problem_599 = ProblemDetail(
            title="Unknown",
            status=599,
            detail="Unknown status",
        )
        assert problem_599.status == 599

    def test_required_fields(self):
        """Test that title, status, and detail are required."""
        # Missing title
        with pytest.raises(ValidationError) as exc_info:
            ProblemDetail(
                status=404,
                detail="Missing title",
            )
        assert any(e["loc"] == ("title",) for e in exc_info.value.errors())

        # Missing status
        with pytest.raises(ValidationError) as exc_info:
            ProblemDetail(
                title="Not Found",
                detail="Missing status",
            )
        assert any(e["loc"] == ("status",) for e in exc_info.value.errors())

        # Missing detail
        with pytest.raises(ValidationError) as exc_info:
            ProblemDetail(
                title="Not Found",
                status=404,
            )
        assert any(e["loc"] == ("detail",) for e in exc_info.value.errors())

    def test_model_dump_excludes_none(self):
        """Test model_dump with exclude_none removes optional fields."""
        problem = ProblemDetail(
            title="Not Found",
            status=404,
            detail="Resource not found",
        )

        dumped = problem.model_dump(exclude_none=True)

        assert "type" in dumped  # Has default value
        assert "title" in dumped
        assert "status" in dumped
        assert "detail" in dumped
        assert "instance" not in dumped  # Should be excluded (is None)

    def test_model_dump_includes_instance_when_set(self):
        """Test model_dump includes instance when it has a value."""
        problem = ProblemDetail(
            title="Not Found",
            status=404,
            detail="Resource not found",
            instance="/api/cameras/test",
        )

        dumped = problem.model_dump(exclude_none=True)

        assert "instance" in dumped
        assert dumped["instance"] == "/api/cameras/test"

    def test_json_serialization(self):
        """Test that ProblemDetail serializes to valid JSON."""
        problem = ProblemDetail(
            type="about:blank",
            title="Not Found",
            status=404,
            detail="Camera 'front_door' does not exist",
            instance="/api/cameras/front_door",
        )

        json_str = problem.model_dump_json()

        # Should be valid JSON
        import json

        parsed = json.loads(json_str)

        assert parsed["type"] == "about:blank"
        assert parsed["title"] == "Not Found"
        assert parsed["status"] == 404
        assert parsed["detail"] == "Camera 'front_door' does not exist"
        assert parsed["instance"] == "/api/cameras/front_door"


# =============================================================================
# Integration Tests for Common Error Scenarios
# =============================================================================


class TestProblemDetailCommonScenarios:
    """Tests for common error scenarios using ProblemDetail."""

    def test_404_not_found_scenario(self):
        """Test creating a 404 Not Found problem detail."""
        problem = ProblemDetail(
            type="about:blank",
            title=get_status_phrase(404),
            status=404,
            detail="Camera 'unknown_camera' does not exist",
            instance="/api/cameras/unknown_camera",
        )

        dumped = problem.model_dump(exclude_none=True)

        assert dumped == {
            "type": "about:blank",
            "title": "Not Found",
            "status": 404,
            "detail": "Camera 'unknown_camera' does not exist",
            "instance": "/api/cameras/unknown_camera",
        }

    def test_400_bad_request_scenario(self):
        """Test creating a 400 Bad Request problem detail."""
        problem = ProblemDetail(
            type="about:blank",
            title=get_status_phrase(400),
            status=400,
            detail="The 'limit' parameter must be a positive integer",
            instance="/api/events",
        )

        dumped = problem.model_dump(exclude_none=True)

        assert dumped["title"] == "Bad Request"
        assert dumped["status"] == 400

    def test_422_validation_error_scenario(self):
        """Test creating a 422 Unprocessable Content problem detail."""
        problem = ProblemDetail(
            type="about:blank",
            title=get_status_phrase(422),
            status=422,
            detail="Request body contains invalid JSON",
            instance="/api/cameras",
        )

        dumped = problem.model_dump(exclude_none=True)

        assert dumped["title"] == "Unprocessable Content"
        assert dumped["status"] == 422

    def test_500_internal_server_error_scenario(self):
        """Test creating a 500 Internal Server Error problem detail."""
        problem = ProblemDetail(
            type="about:blank",
            title=get_status_phrase(500),
            status=500,
            detail="An unexpected error occurred",
            instance="/api/system/health",
        )

        dumped = problem.model_dump(exclude_none=True)

        assert dumped["title"] == "Internal Server Error"
        assert dumped["status"] == 500

    def test_503_service_unavailable_scenario(self):
        """Test creating a 503 Service Unavailable problem detail."""
        problem = ProblemDetail(
            type="about:blank",
            title=get_status_phrase(503),
            status=503,
            detail="The AI detection service is currently unavailable",
            instance="/api/detections",
        )

        dumped = problem.model_dump(exclude_none=True)

        assert dumped["title"] == "Service Unavailable"
        assert dumped["status"] == 503

    def test_429_rate_limit_scenario(self):
        """Test creating a 429 Too Many Requests problem detail."""
        problem = ProblemDetail(
            type="about:blank",
            title=get_status_phrase(429),
            status=429,
            detail="Rate limit exceeded. Please wait 60 seconds before retrying.",
            instance="/api/events",
        )

        dumped = problem.model_dump(exclude_none=True)

        assert dumped["title"] == "Too Many Requests"
        assert dumped["status"] == 429


# =============================================================================
# HTTP_STATUS_PHRASES Dictionary Tests
# =============================================================================


class TestHTTPStatusPhrases:
    """Tests for HTTP_STATUS_PHRASES dictionary."""

    def test_dictionary_is_populated(self):
        """Test that the dictionary has entries."""
        assert len(HTTP_STATUS_PHRASES) > 0

    def test_all_values_are_strings(self):
        """Test that all phrases are non-empty strings."""
        for code, phrase in HTTP_STATUS_PHRASES.items():
            assert isinstance(code, int), f"Code {code} should be an int"
            assert isinstance(phrase, str), f"Phrase for {code} should be a string"
            assert len(phrase) > 0, f"Phrase for {code} should not be empty"

    def test_common_codes_exist(self):
        """Test that all common HTTP codes are defined."""
        common_codes = [200, 201, 204, 400, 401, 403, 404, 500, 502, 503]
        for code in common_codes:
            assert code in HTTP_STATUS_PHRASES, f"Code {code} should be in dictionary"
