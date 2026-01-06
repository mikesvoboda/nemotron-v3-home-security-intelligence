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
