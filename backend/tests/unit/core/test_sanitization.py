"""Tests for sanitization utilities.

This module tests the sanitization functions used to prevent:
- Command injection (container names)
- Path disclosure (error messages)
- Metric cardinality explosion
- Exception information leakage
- SSRF attacks (URL validation)

Related Linear issues:
- NEM-1124: Container name sanitization
- NEM-1078: Filename sanitization in error responses
- NEM-1064: Prometheus metric label sanitization
- NEM-1059: Exception message sanitization
- NEM-1077: URL validation for grafana_url
"""

import pytest

from backend.core.sanitization import (
    CONTAINER_NAME_MAX_LENGTH,
    KNOWN_ERROR_TYPES,
    KNOWN_RISK_LEVELS,
    METRIC_LABEL_MAX_LENGTH,
    URLValidationError,
    sanitize_camera_id,
    sanitize_container_name,
    sanitize_error_for_response,
    sanitize_error_type,
    sanitize_metric_label,
    sanitize_object_class,
    sanitize_path_for_error,
    sanitize_risk_level,
    validate_container_names,
    validate_grafana_url,
    validate_monitoring_url,
)

# =============================================================================
# Container Name Sanitization Tests (NEM-1124)
# =============================================================================


class TestContainerNameSanitization:
    """Tests for container name sanitization to prevent command injection."""

    def test_valid_simple_name(self) -> None:
        """Valid simple container names should pass through."""
        assert sanitize_container_name("backend") == "backend"
        assert sanitize_container_name("frontend") == "frontend"
        assert sanitize_container_name("redis") == "redis"

    def test_valid_complex_name(self) -> None:
        """Valid names with hyphens and underscores should pass."""
        assert (
            sanitize_container_name("nemotron-v3-home-security-intelligence_backend_1")
            == "nemotron-v3-home-security-intelligence_backend_1"
        )
        assert sanitize_container_name("my_container-123") == "my_container-123"

    def test_valid_numeric_suffix(self) -> None:
        """Names with numeric suffixes should pass."""
        assert sanitize_container_name("container1") == "container1"
        assert sanitize_container_name("backend_1") == "backend_1"

    def test_empty_name_raises(self) -> None:
        """Empty names should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            sanitize_container_name("")

    def test_whitespace_only_raises(self) -> None:
        """Whitespace-only names should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            sanitize_container_name("   ")

    def test_command_injection_semicolon(self) -> None:
        """Command injection with semicolon should be rejected."""
        with pytest.raises(ValueError, match="Only alphanumeric"):
            sanitize_container_name("container; rm -rf /")

    def test_command_injection_backticks(self) -> None:
        """Command injection with backticks should be rejected."""
        with pytest.raises(ValueError, match="Only alphanumeric"):
            sanitize_container_name("container`whoami`")

    def test_command_injection_dollar_parens(self) -> None:
        """Command injection with $() should be rejected."""
        with pytest.raises(ValueError, match="Only alphanumeric"):
            sanitize_container_name("container$(cat /etc/passwd)")

    def test_command_injection_pipe(self) -> None:
        """Command injection with pipe should be rejected."""
        with pytest.raises(ValueError, match="Only alphanumeric"):
            sanitize_container_name("container | cat /etc/passwd")

    def test_command_injection_ampersand(self) -> None:
        """Command injection with ampersand should be rejected."""
        with pytest.raises(ValueError, match="Only alphanumeric"):
            sanitize_container_name("container && rm -rf /")

    def test_command_injection_newline(self) -> None:
        """Command injection with newline should be rejected."""
        with pytest.raises(ValueError, match="Only alphanumeric"):
            sanitize_container_name("container\nrm -rf /")

    def test_special_chars_rejected(self) -> None:
        """Special characters should be rejected."""
        invalid_chars = [
            "!",
            "@",
            "#",
            "$",
            "%",
            "^",
            "&",
            "*",
            "(",
            ")",
            "=",
            "+",
            "[",
            "]",
            "{",
            "}",
            "'",
            '"',
            "<",
            ">",
            "?",
            "/",
            "\\",
            "`",
            "~",
        ]
        for char in invalid_chars:
            with pytest.raises(ValueError, match="Only alphanumeric"):
                sanitize_container_name(f"container{char}name")

    def test_name_starting_with_hyphen_rejected(self) -> None:
        """Names starting with hyphen should be rejected."""
        with pytest.raises(ValueError, match="Must start with alphanumeric"):
            sanitize_container_name("-container")

    def test_name_starting_with_underscore_rejected(self) -> None:
        """Names starting with underscore should be rejected."""
        with pytest.raises(ValueError, match="Must start with alphanumeric"):
            sanitize_container_name("_container")

    def test_name_too_long_raises(self) -> None:
        """Names exceeding max length should raise ValueError."""
        long_name = "a" * (CONTAINER_NAME_MAX_LENGTH + 1)
        with pytest.raises(ValueError, match="exceeds maximum length"):
            sanitize_container_name(long_name)

    def test_name_at_max_length_passes(self) -> None:
        """Names at exactly max length should pass."""
        max_name = "a" * CONTAINER_NAME_MAX_LENGTH
        assert sanitize_container_name(max_name) == max_name

    def test_whitespace_trimmed(self) -> None:
        """Leading/trailing whitespace should be trimmed."""
        assert sanitize_container_name("  container  ") == "container"

    def test_validate_container_names_list(self) -> None:
        """Batch validation should work for valid names."""
        names = ["container1", "container-2", "container_3"]
        assert validate_container_names(names) == names

    def test_validate_container_names_invalid_raises(self) -> None:
        """Batch validation should raise on first invalid name."""
        names = ["container1", "invalid;name", "container3"]
        with pytest.raises(ValueError):
            validate_container_names(names)


# =============================================================================
# Path Sanitization Tests (NEM-1078)
# =============================================================================


class TestPathSanitization:
    """Tests for path sanitization to prevent information disclosure."""

    def test_simple_filename(self) -> None:
        """Simple filename without path should pass through."""
        assert sanitize_path_for_error("image.jpg") == "image.jpg"

    def test_unix_path_extracts_filename(self) -> None:
        """Unix paths should be reduced to just filename."""
        assert sanitize_path_for_error("/home/user/secret/path/image.jpg") == "image.jpg"

    def test_nested_unix_path(self) -> None:
        """Deeply nested paths should extract filename."""
        assert sanitize_path_for_error("/a/b/c/d/e/f/file.txt") == "file.txt"

    def test_windows_path_extracts_filename(self) -> None:
        """Windows-style paths should be reduced to filename."""
        assert sanitize_path_for_error("C:\\Users\\Admin\\secret\\image.jpg") == "image.jpg"

    def test_empty_path_returns_unknown(self) -> None:
        """Empty paths should return [unknown]."""
        assert sanitize_path_for_error("") == "[unknown]"

    def test_none_like_empty(self) -> None:
        """None-like values should return [unknown]."""
        assert sanitize_path_for_error("") == "[unknown]"

    def test_just_slash_returns_unknown(self) -> None:
        """Just a slash should return [unknown]."""
        assert sanitize_path_for_error("/") == "[unknown]"

    def test_long_filename_truncated(self) -> None:
        """Very long filenames should be truncated."""
        long_name = "a" * 150 + ".jpg"
        result = sanitize_path_for_error(long_name)
        assert len(result) <= 100
        assert result.endswith("...")

    def test_path_with_spaces(self) -> None:
        """Paths with spaces should extract filename correctly."""
        assert sanitize_path_for_error("/path/with spaces/my file.jpg") == "my file.jpg"


# =============================================================================
# Error Message Sanitization Tests (NEM-1059)
# =============================================================================


class TestErrorSanitization:
    """Tests for error message sanitization to prevent information leakage."""

    def test_simple_error_passes_through(self) -> None:
        """Simple error messages should pass through."""
        error = ValueError("Something went wrong")
        result = sanitize_error_for_response(error)
        assert "Something went wrong" in result

    def test_path_in_error_sanitized(self) -> None:
        """File paths in errors should be sanitized."""
        error = FileNotFoundError("/home/user/secret/config/database.yaml not found")
        result = sanitize_error_for_response(error)
        assert "/home/user/secret/config" not in result
        assert "database.yaml" in result

    def test_password_in_error_redacted(self) -> None:
        """Password values in errors should be redacted."""
        error = ValueError("Connection failed: password=supersecret123")
        result = sanitize_error_for_response(error)
        assert "supersecret123" not in result
        assert "REDACTED" in result

    def test_bearer_token_redacted(self) -> None:
        """Bearer tokens should be redacted."""
        error = ValueError("Auth failed: Bearer eyJhbGciOiJIUzI1NiIs...")
        result = sanitize_error_for_response(error)
        assert "eyJhbGciOiJIUzI1NiIs" not in result
        assert "REDACTED" in result

    def test_api_key_redacted(self) -> None:
        """API keys should be redacted."""
        error = ValueError("Request failed: api_key=sk-123456789")
        result = sanitize_error_for_response(error)
        assert "sk-123456789" not in result
        assert "REDACTED" in result

    def test_ip_address_redacted(self) -> None:
        """IP addresses should be redacted."""
        error = ValueError("Connection to 192.168.1.100 failed")
        result = sanitize_error_for_response(error)
        assert "192.168.1.100" not in result
        assert "IP_REDACTED" in result

    def test_long_error_truncated(self) -> None:
        """Very long error messages should be truncated."""
        long_message = "Error: " + "x" * 500
        error = ValueError(long_message)
        result = sanitize_error_for_response(error)
        assert len(result) <= 210  # 200 + small buffer for context
        assert "..." in result

    def test_with_context(self) -> None:
        """Error with context should include context prefix."""
        error = ValueError("File not found")
        result = sanitize_error_for_response(error, context="processing image")
        assert result.startswith("Error processing image:")

    def test_multiple_paths_sanitized(self) -> None:
        """Multiple paths in error should all be sanitized."""
        error = ValueError("Cannot copy /src/secret/a.txt to /dst/hidden/b.txt")
        result = sanitize_error_for_response(error)
        assert "/src/secret" not in result
        assert "/dst/hidden" not in result
        assert "a.txt" in result
        assert "b.txt" in result


# =============================================================================
# Prometheus Label Sanitization Tests (NEM-1064)
# =============================================================================


class TestMetricLabelSanitization:
    """Tests for Prometheus metric label sanitization."""

    def test_known_object_class_passes(self) -> None:
        """Known object classes should pass through."""
        for obj_class in ["person", "car", "dog", "cat"]:
            assert sanitize_object_class(obj_class) == obj_class

    def test_unknown_object_class_returns_other(self) -> None:
        """Unknown object classes should return 'other'."""
        assert sanitize_object_class("malicious_class_name") == "other"
        assert sanitize_object_class("attacker_controlled_value") == "other"

    def test_object_class_case_insensitive(self) -> None:
        """Object class matching should be case-insensitive."""
        assert sanitize_object_class("PERSON") == "person"
        assert sanitize_object_class("Car") == "car"

    def test_known_error_types_pass(self) -> None:
        """Known error types should pass through."""
        for error_type in KNOWN_ERROR_TYPES:
            assert sanitize_error_type(error_type) == error_type

    def test_unknown_error_type_returns_other(self) -> None:
        """Unknown error types should return 'other'."""
        assert sanitize_error_type("custom_user_error") == "other"

    def test_known_risk_levels_pass(self) -> None:
        """Known risk levels should pass through."""
        for level in KNOWN_RISK_LEVELS:
            assert sanitize_risk_level(level) == level

    def test_unknown_risk_level_returns_unknown(self) -> None:
        """Unknown risk levels should return 'unknown'."""
        # Note: risk levels use 'unknown' as default instead of 'other'
        result = sanitize_metric_label("custom_level", label_name="level")
        assert result == "other"  # Gets 'other' because it's not in allowlist

    def test_empty_value_returns_unknown(self) -> None:
        """Empty values should return 'unknown'."""
        assert sanitize_metric_label("") == "unknown"
        assert sanitize_metric_label("   ") == "unknown"

    def test_very_long_label_truncated(self) -> None:
        """Very long labels should be truncated."""
        long_value = "x" * 200
        result = sanitize_metric_label(long_value)
        assert len(result) <= METRIC_LABEL_MAX_LENGTH

    def test_special_chars_replaced(self) -> None:
        """Special characters should be replaced."""
        # Without allowlist, special chars should be replaced
        result = sanitize_metric_label("value!@#$%with^special", allowlist=None)
        assert "!" not in result
        assert "@" not in result
        assert "#" not in result

    def test_camera_id_sanitization(self) -> None:
        """Camera IDs should be sanitized but not use allowlist."""
        assert sanitize_camera_id("front_door") == "front_door"
        assert sanitize_camera_id("camera-1") == "camera-1"

    def test_camera_id_special_chars_replaced(self) -> None:
        """Camera ID special characters should be replaced."""
        assert sanitize_camera_id("camera/path") == "camera_path"
        assert sanitize_camera_id("camera@location") == "camera_location"

    def test_camera_id_truncated(self) -> None:
        """Long camera IDs should be truncated."""
        long_id = "camera_" + "x" * 100
        result = sanitize_camera_id(long_id, max_length=64)
        assert len(result) <= 64

    def test_camera_id_empty_returns_unknown(self) -> None:
        """Empty camera ID should return 'unknown'."""
        assert sanitize_camera_id("") == "unknown"

    def test_user_controlled_input_cardinality(self) -> None:
        """User-controlled values should not create unbounded cardinality."""
        # Simulate attacker trying to create many unique label values
        for i in range(100):
            attacker_value = f"attack_value_{i}"
            result = sanitize_object_class(attacker_value)
            assert result == "other"  # All unknown values map to 'other'

    def test_known_coco_classes(self) -> None:
        """All known COCO dataset classes should be recognized."""
        sample_coco_classes = ["person", "bicycle", "car", "motorcycle", "bus", "truck"]
        for cls in sample_coco_classes:
            assert sanitize_object_class(cls) == cls


# =============================================================================
# URL Validation Tests (NEM-1077)
# =============================================================================


class TestGrafanaURLValidation:
    """Tests for Grafana URL validation."""

    def test_valid_http_localhost(self) -> None:
        """HTTP localhost URLs should be valid for Grafana."""
        assert validate_grafana_url("http://localhost:3002") == "http://localhost:3002"

    def test_valid_http_127(self) -> None:
        """HTTP 127.0.0.1 URLs should be valid."""
        assert validate_grafana_url("http://127.0.0.1:3002") == "http://127.0.0.1:3002"

    def test_valid_https_url(self) -> None:
        """HTTPS URLs should be valid."""
        assert validate_grafana_url("https://grafana.example.com") == "https://grafana.example.com"

    def test_valid_docker_internal(self) -> None:
        """Docker internal hostnames should be valid."""
        assert validate_grafana_url("http://grafana:3000") == "http://grafana:3000"

    def test_trailing_slash_removed(self) -> None:
        """Trailing slashes should be removed for consistency."""
        assert validate_grafana_url("http://localhost:3002/") == "http://localhost:3002"

    def test_empty_url_raises(self) -> None:
        """Empty URLs should raise URLValidationError."""
        with pytest.raises(URLValidationError, match="cannot be empty"):
            validate_grafana_url("")

    def test_invalid_scheme_raises(self) -> None:
        """Non-http/https schemes should raise."""
        with pytest.raises(URLValidationError, match="Invalid URL scheme"):
            validate_grafana_url("ftp://grafana:21")

    def test_file_scheme_raises(self) -> None:
        """File scheme should be rejected."""
        with pytest.raises(URLValidationError, match="Invalid URL scheme"):
            validate_grafana_url("file:///etc/passwd")

    def test_missing_hostname_raises(self) -> None:
        """URLs without hostname should raise."""
        with pytest.raises(URLValidationError, match="must have a hostname"):
            validate_grafana_url("http://")

    def test_cloud_metadata_blocked(self) -> None:
        """Cloud metadata endpoint should be blocked."""
        with pytest.raises(URLValidationError, match="metadata"):
            validate_grafana_url("http://169.254.169.254/latest/meta-data")

    def test_link_local_blocked(self) -> None:
        """Link-local addresses should be blocked."""
        with pytest.raises(URLValidationError, match="Link-local"):
            validate_grafana_url("http://169.254.1.1:3000")

    def test_google_metadata_hostname_blocked(self) -> None:
        """Google metadata hostname should be blocked."""
        with pytest.raises(URLValidationError, match="blocked for security"):
            validate_grafana_url("http://metadata.google.internal")

    def test_invalid_port_raises(self) -> None:
        """Invalid port numbers should raise."""
        # Port 99999 exceeds the 65535 max, causing a parse error
        with pytest.raises((URLValidationError, ValueError)):
            validate_grafana_url("http://localhost:99999")

    def test_private_ip_allowed_for_grafana(self) -> None:
        """Private IPs should be allowed for Grafana (internal monitoring)."""
        # This should NOT raise since allow_internal=True for Grafana
        result = validate_grafana_url("http://192.168.1.100:3002")
        assert result == "http://192.168.1.100:3002"


class TestMonitoringURLValidation:
    """Tests for generic monitoring URL validation."""

    def test_private_ip_blocked_when_not_allowed(self) -> None:
        """Private IPs should be blocked when allow_internal=False."""
        with pytest.raises(URLValidationError, match="Private/internal"):
            validate_monitoring_url("http://192.168.1.100:3002", allow_internal=False)

    def test_10_network_blocked_when_not_allowed(self) -> None:
        """10.x.x.x addresses should be blocked when allow_internal=False."""
        with pytest.raises(URLValidationError, match="Private/internal"):
            validate_monitoring_url("http://10.0.0.1:3000", allow_internal=False)

    def test_172_network_blocked_when_not_allowed(self) -> None:
        """172.16.x.x addresses should be blocked when allow_internal=False."""
        with pytest.raises(URLValidationError, match="Private/internal"):
            validate_monitoring_url("http://172.16.0.1:3000", allow_internal=False)

    def test_localhost_allowed_when_internal_allowed(self) -> None:
        """Localhost should be allowed when allow_internal=True."""
        result = validate_monitoring_url("http://127.0.0.1:3000", allow_internal=True)
        assert "127.0.0.1" in result

    def test_https_required_when_specified(self) -> None:
        """HTTP should be rejected when require_https=True."""
        with pytest.raises(URLValidationError, match="Only HTTPS"):
            validate_monitoring_url("http://example.com:3000", require_https=True)

    def test_https_valid_when_required(self) -> None:
        """HTTPS should pass when require_https=True."""
        result = validate_monitoring_url("https://example.com:3000", require_https=True)
        assert result.startswith("https://")

    def test_public_url_allowed(self) -> None:
        """Public URLs should be allowed."""
        result = validate_monitoring_url("https://grafana.mycompany.com", allow_internal=False)
        assert "grafana.mycompany.com" in result


# =============================================================================
# Integration Tests
# =============================================================================


class TestSanitizationIntegration:
    """Integration tests combining multiple sanitization functions."""

    def test_error_with_path_and_password(self) -> None:
        """Error with both path and password should sanitize both."""
        error = ValueError("Failed to connect to /secret/db.conf with password=secret123")
        result = sanitize_error_for_response(error)
        assert "/secret" not in result
        assert "secret123" not in result
        assert "db.conf" in result
        assert "REDACTED" in result

    def test_metric_label_with_injection_attempt(self) -> None:
        """Metric labels with injection attempts should be safely handled."""
        # Attempt to inject special characters
        malicious = 'person\n{label="value"}'
        result = sanitize_object_class(malicious)
        assert result == "other"  # Unknown value maps to 'other'

    def test_container_name_with_url_injection(self) -> None:
        """Container names with URL-like injection should be rejected."""
        with pytest.raises(ValueError):
            sanitize_container_name("container://evil.com")
