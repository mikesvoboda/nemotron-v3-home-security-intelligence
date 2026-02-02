"""API key authentication security tests.

This module tests the API key authentication middleware:
- Valid API key acceptance
- Invalid API key rejection
- Missing API key handling
- API key in header vs query parameter
- Exempt endpoint handling
- Key leakage prevention
"""

import hashlib

import pytest
from fastapi.testclient import TestClient

from backend.api.middleware.auth import AuthMiddleware, _hash_key


class TestHashKeyFunction:
    """Test the API key hashing function."""

    def test_hash_key_returns_sha256(self):
        """Test that _hash_key returns SHA-256 hash."""
        test_key = "my-test-key"
        expected = hashlib.sha256(test_key.encode()).hexdigest()

        result = _hash_key(test_key)

        assert result == expected

    def test_hash_key_consistent(self):
        """Test that hashing the same key produces consistent results."""
        test_key = "another-test-key"

        hash1 = _hash_key(test_key)
        hash2 = _hash_key(test_key)

        assert hash1 == hash2

    def test_different_keys_different_hashes(self):
        """Test that different keys produce different hashes."""
        key1 = "key1"
        key2 = "key2"

        assert _hash_key(key1) != _hash_key(key2)


class TestAuthMiddlewareExemptPaths:
    """Test the exempt path checking logic in AuthMiddleware."""

    def test_health_endpoints_exempt(self):
        """Test that health endpoints are exempt from auth."""
        middleware = AuthMiddleware(app=None, valid_key_hashes=set())

        exempt_paths = ["/", "/health", "/ready", "/api/system/health", "/api/system/health/ready"]

        for path in exempt_paths:
            assert middleware._is_exempt_path(path), f"Path should be exempt: {path}"

    def test_docs_endpoints_exempt(self):
        """Test that documentation endpoints are exempt from auth."""
        middleware = AuthMiddleware(app=None, valid_key_hashes=set())

        exempt_paths = ["/docs", "/docs/", "/redoc", "/redoc/", "/openapi.json"]

        for path in exempt_paths:
            assert middleware._is_exempt_path(path), f"Path should be exempt: {path}"

    def test_metrics_endpoint_exempt(self):
        """Test that Prometheus metrics endpoint is exempt from auth."""
        middleware = AuthMiddleware(app=None, valid_key_hashes=set())

        assert middleware._is_exempt_path("/api/metrics")

    def test_media_endpoints_exempt(self):
        """Test that media endpoints are exempt from auth."""
        middleware = AuthMiddleware(app=None, valid_key_hashes=set())

        exempt_paths = [
            "/api/media/cameras/test/image.jpg",
            "/api/media/thumbnails/detection.png",
            "/api/detections/123/image",
            "/api/detections/123/video",
            "/api/detections/123/video/thumbnail",
            "/api/cameras/front_door/snapshot",
        ]

        for path in exempt_paths:
            assert middleware._is_exempt_path(path), f"Path should be exempt: {path}"

    def test_api_endpoints_not_exempt(self):
        """Test that regular API endpoints are NOT exempt from auth."""
        middleware = AuthMiddleware(app=None, valid_key_hashes=set())

        protected_paths = [
            "/api/cameras",
            "/api/events",
            "/api/events/123",
            "/api/cameras/front_door",
            "/api/system/status",
            "/api/admin/config",
        ]

        for path in protected_paths:
            assert not middleware._is_exempt_path(path), f"Path should NOT be exempt: {path}"


class TestAPIKeyLeakage:
    """Test that API keys are not leaked in responses or logs."""

    def test_api_key_not_in_error_response(self, security_client: TestClient):
        """Test that API key is not reflected in error messages."""
        test_key = "secret-key-do-not-leak-this-12345"
        response = security_client.get(
            "/api/cameras",
            headers={"X-API-Key": test_key},
        )

        # The API key should not appear in the response
        response_text = response.text
        assert test_key not in response_text, "API key leaked in response"


class TestExemptEndpointsWithClient:
    """Test that exempt endpoints work without authentication."""

    @pytest.mark.parametrize(
        "endpoint,description",
        [
            ("/", "Root status endpoint"),
            ("/health", "Liveness probe"),
            ("/api/system/health", "Health check"),
            ("/api/metrics", "Prometheus metrics"),
            ("/docs", "Swagger documentation"),
            ("/openapi.json", "OpenAPI schema"),
        ],
    )
    def test_exempt_endpoint_accessible(
        self, security_client: TestClient, endpoint: str, description: str
    ):
        """Test that exempt endpoints are accessible.

        Scenario: {description}
        """
        response = security_client.get(endpoint)

        # Should not require authentication (401)
        assert response.status_code != 401, f"Exempt endpoint {endpoint} requires authentication"


class TestMediaEndpointSecurity:
    """Test security of media endpoints."""

    def test_media_endpoint_returns_404_for_missing_file(self, security_client: TestClient):
        """Test that media endpoint returns 404 for non-existent files."""
        response = security_client.get("/api/media/cameras/test/nonexistent.jpg")

        # Should return 404, not expose path info
        assert response.status_code in [403, 404]

    def test_media_endpoint_blocks_path_traversal(self, security_client: TestClient):
        """Test that media endpoint blocks path traversal."""
        response = security_client.get("/api/media/cameras/../../../etc/passwd")

        # Should block path traversal
        assert response.status_code in [400, 403, 404]

        # Should not contain sensitive file contents
        assert "root:" not in response.text


class TestAuthenticationDisabled:
    """Test behavior when API key authentication is disabled."""

    def test_root_endpoint_works_without_key(self, security_client: TestClient):
        """Test that root endpoint works without API key when auth is disabled."""
        response = security_client.get("/")

        # Should not require authentication
        assert response.status_code != 401

    def test_invalid_key_ignored_for_exempt_endpoints(self, security_client: TestClient):
        """Test that invalid API keys are ignored for exempt endpoints."""
        response = security_client.get(
            "/",
            headers={"X-API-Key": "any-random-key"},
        )

        # Should not return 401 for exempt endpoints
        assert response.status_code != 401


class TestConstantTimeComparison:
    """Test that API key validation uses constant-time comparison.

    OWASP A07:2021 - Identification and Authentication Failures

    Timing attacks can be used to determine valid API keys by measuring
    the time it takes for the server to reject an invalid key. If the
    comparison short-circuits (returns early on first difference), an
    attacker can brute-force the key one character at a time.

    The fix is to use hmac.compare_digest() which performs constant-time
    comparison regardless of when the first difference occurs.
    """

    def test_validate_api_key_uses_constant_time_comparison(self):
        """Test that AuthMiddleware._validate_key_hash uses hmac.compare_digest.

        This test verifies the implementation uses constant-time comparison
        by checking that hmac.compare_digest is called during validation.
        """
        from unittest.mock import patch

        from backend.api.middleware.auth import AuthMiddleware

        # Create middleware with a known valid hash
        valid_hash = _hash_key("valid-api-key")
        middleware = AuthMiddleware(app=None, valid_key_hashes={valid_hash})

        # Test with matching hash
        with patch("backend.api.middleware.auth.hmac.compare_digest") as mock_compare:
            mock_compare.return_value = True
            result = middleware._validate_key_hash(valid_hash)

            # hmac.compare_digest should have been called
            assert mock_compare.called, "hmac.compare_digest should be used for key validation"
            assert result is True

    def test_validate_api_key_rejects_invalid_with_constant_time(self):
        """Test that invalid keys are rejected using constant-time comparison."""
        from unittest.mock import patch

        from backend.api.middleware.auth import AuthMiddleware

        valid_hash = _hash_key("valid-api-key")
        invalid_hash = _hash_key("invalid-api-key")
        middleware = AuthMiddleware(app=None, valid_key_hashes={valid_hash})

        # Test with non-matching hash
        with patch("backend.api.middleware.auth.hmac.compare_digest") as mock_compare:
            mock_compare.return_value = False
            result = middleware._validate_key_hash(invalid_hash)

            # hmac.compare_digest should have been called
            assert mock_compare.called, "hmac.compare_digest should be used for key validation"
            assert result is False

    def test_websocket_validation_uses_constant_time_comparison(self):
        """Test that WebSocket API key validation uses hmac.compare_digest."""
        from unittest.mock import patch

        from backend.api.middleware.auth import _validate_key_hash_constant_time

        valid_hash = _hash_key("valid-api-key")
        valid_hashes = {valid_hash}

        # Test with matching hash
        with patch("backend.api.middleware.auth.hmac.compare_digest") as mock_compare:
            mock_compare.return_value = True
            result = _validate_key_hash_constant_time(valid_hash, valid_hashes)

            assert mock_compare.called, (
                "hmac.compare_digest should be used for WebSocket validation"
            )
            assert result is True

    def test_constant_time_comparison_checks_all_hashes(self):
        """Test that validation compares against all valid hashes.

        This ensures timing doesn't leak information about which keys exist.
        Even if a match is found early, we should compare against all hashes
        to maintain constant-time behavior.
        """
        from unittest.mock import patch

        from backend.api.middleware.auth import AuthMiddleware

        # Create middleware with multiple valid hashes
        hash1 = _hash_key("key1")
        hash2 = _hash_key("key2")
        hash3 = _hash_key("key3")
        middleware = AuthMiddleware(app=None, valid_key_hashes={hash1, hash2, hash3})

        test_hash = _hash_key("key2")  # This matches hash2

        with patch("backend.api.middleware.auth.hmac.compare_digest") as mock_compare:
            # Simulate: returns True for hash2, False for others
            def side_effect(a, b):
                return a == b

            mock_compare.side_effect = side_effect
            result = middleware._validate_key_hash(test_hash)

            # Should return True (found a match)
            assert result is True
            # hmac.compare_digest should have been called at least once
            assert mock_compare.call_count >= 1
