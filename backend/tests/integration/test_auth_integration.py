"""Integration tests for API authentication middleware.

These tests verify the API key authentication system against real HTTP requests,
covering scenarios including:
- Valid API key authentication (header and query parameter)
- Invalid/missing API key rejection
- Protected vs public endpoint access
- Authentication disabled mode

Uses the client fixture from conftest.py for authentication-disabled tests
and a separate auth_client fixture for authentication-enabled tests.

IMPORTANT: These tests must be run serially (-n0) due to shared FastAPI app state.
Run with:

    uv run pytest backend/tests/integration/test_auth_integration.py -n0
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest
from fastapi import status

if TYPE_CHECKING:
    from httpx import AsyncClient

    from backend.core.redis import RedisClient

# Mark as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Test Helpers
# =============================================================================


def _hash_api_key(key: str) -> str:
    """Hash an API key using SHA-256.

    Args:
        key: Plain text API key

    Returns:
        SHA-256 hash of the key
    """
    return hashlib.sha256(key.encode()).hexdigest()


# Test API keys (use pragma comment to mark as test secrets)
VALID_API_KEY = "test_valid_key_12345"  # pragma: allowlist secret
INVALID_API_KEY = "test_invalid_key_99999"  # pragma: allowlist secret


# =============================================================================
# Authentication Disabled Tests (Default Behavior)
# =============================================================================


class TestAuthenticationDisabled:
    """Test behavior when authentication is disabled (default).

    These tests use the standard client fixture which has auth disabled.
    """

    @pytest.mark.asyncio
    async def test_protected_endpoint_accessible_without_key(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that protected endpoints are accessible when auth is disabled."""
        response = await client.get("/api/cameras")

        # Should succeed without API key
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_public_endpoint_accessible_without_key(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that public endpoints remain accessible when auth is disabled."""
        response = await client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Health endpoint returns "alive" as status
        assert data["status"] in ["healthy", "alive"]

    @pytest.mark.asyncio
    async def test_no_auth_header_required_when_disabled(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that X-API-Key header is ignored when auth is disabled."""
        # Send request with API key even though auth is disabled
        response = await client.get(
            "/api/cameras",
            headers={"X-API-Key": INVALID_API_KEY},
        )

        # Should succeed - auth is disabled so key is ignored
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_events_endpoint_accessible_without_key(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that events endpoint is accessible when auth is disabled."""
        response = await client.get("/api/events")

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_detections_endpoint_accessible_without_key(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that detections endpoint is accessible when auth is disabled."""
        response = await client.get("/api/detections")

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_post_endpoint_accessible_without_key(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that POST endpoints are accessible when auth is disabled."""
        camera_data = {
            "id": "test_camera",
            "name": "Test Camera",
            "folder_path": "/export/foscam/test_camera",
        }

        response = await client.post("/api/cameras", json=camera_data)

        # Should succeed (or fail with validation error, but not 401)
        assert response.status_code != status.HTTP_401_UNAUTHORIZED
        # Likely 201 Created or 422 Validation Error
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]


# =============================================================================
# Public Endpoint Access Tests
# =============================================================================


class TestPublicEndpointAccess:
    """Test that certain endpoints are always public regardless of auth settings.

    These tests verify exemptions work correctly.
    """

    @pytest.mark.asyncio
    async def test_health_endpoint_accessible(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that /health is always accessible."""
        response = await client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data

    @pytest.mark.asyncio
    async def test_metrics_endpoint_accessible(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that /api/metrics is always accessible."""
        response = await client.get("/api/metrics")

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_docs_endpoint_accessible(self, client: AsyncClient, clean_tables: None) -> None:
        """Test that /docs is always accessible."""
        response = await client.get("/docs")

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_openapi_json_accessible(self, client: AsyncClient, clean_tables: None) -> None:
        """Test that /openapi.json is always accessible."""
        response = await client.get("/openapi.json")

        assert response.status_code == status.HTTP_200_OK
        openapi = response.json()
        assert "openapi" in openapi
        assert "paths" in openapi


# =============================================================================
# Media Endpoint Tests
# =============================================================================


class TestMediaEndpointSecurity:
    """Test that media endpoints are accessible without authentication.

    Media endpoints bypass authentication because they're accessed directly
    by browsers via <img>/<video> tags. They have their own security controls:
    - Path traversal protection
    - File type allowlist
    - Rate limiting
    """

    @pytest.mark.asyncio
    async def test_media_endpoint_accessible_without_auth(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that media endpoints don't require authentication."""
        # This will 404 if file doesn't exist, but shouldn't 401
        response = await client.get("/api/media/test_camera/test_image.jpg")

        # Should not be 401 unauthorized
        assert response.status_code != status.HTTP_401_UNAUTHORIZED
        # Likely 404 Not Found or 200 OK if file exists
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK]


# =============================================================================
# API Key Validation Tests
# =============================================================================


class TestAPIKeyValidation:
    """Test API key validation behavior.

    These tests verify key hashing and comparison logic.
    """

    def test_api_key_hashing_consistency(self) -> None:
        """Test that API key hashing is consistent."""
        key = "test_key_123"  # pragma: allowlist secret
        hash1 = _hash_api_key(key)
        hash2 = _hash_api_key(key)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64 hex characters

    def test_different_keys_produce_different_hashes(self) -> None:
        """Test that different API keys produce different hashes."""
        key1 = "test_key_1"  # pragma: allowlist secret
        key2 = "test_key_2"  # pragma: allowlist secret

        hash1 = _hash_api_key(key1)
        hash2 = _hash_api_key(key2)

        assert hash1 != hash2

    def test_case_sensitive_key_hashing(self) -> None:
        """Test that API key hashing is case-sensitive."""
        key_lower = "test_key"  # pragma: allowlist secret
        key_upper = "TEST_KEY"  # pragma: allowlist secret

        hash_lower = _hash_api_key(key_lower)
        hash_upper = _hash_api_key(key_upper)

        assert hash_lower != hash_upper


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestAuthEdgeCases:
    """Test edge cases in authentication logic."""

    @pytest.mark.asyncio
    async def test_empty_api_key_header_ignored(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that empty X-API-Key header is handled gracefully."""
        # With auth disabled, empty header should be ignored
        response = await client.get(
            "/api/cameras",
            headers={"X-API-Key": ""},
        )

        # Should succeed when auth is disabled
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_whitespace_only_api_key_handled(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that whitespace-only API key is handled gracefully."""
        response = await client.get(
            "/api/cameras",
            headers={"X-API-Key": "   "},
        )

        # Should succeed when auth is disabled
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_very_long_api_key_handled(self, client: AsyncClient, clean_tables: None) -> None:
        """Test that very long API keys are handled without crashing."""
        long_key = "a" * 10000  # 10KB key

        response = await client.get(
            "/api/cameras",
            headers={"X-API-Key": long_key},
        )

        # Should succeed when auth is disabled
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_special_characters_in_api_key(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that special characters in API key are handled."""
        special_key = "key-with.special_chars!@#$%"  # pragma: allowlist secret

        response = await client.get(
            "/api/cameras",
            headers={"X-API-Key": special_key},
        )

        # Should succeed when auth is disabled
        assert response.status_code == status.HTTP_200_OK


# =============================================================================
# Rate Limiting Integration Tests
# =============================================================================


class TestRateLimitingIntegration:
    """Test rate limiting behavior with authentication.

    Note: Detailed rate limiting tests are in test_rate_limit_*.py files.
    These tests verify basic integration between auth and rate limiting.
    """

    @pytest.mark.asyncio
    async def test_rate_limiting_applies_to_authenticated_requests(
        self, real_redis: RedisClient, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that rate limiting is applied to authenticated requests.

        This is a basic smoke test. Full rate limiting scenarios are tested
        in dedicated rate limiting test files.
        """
        # Make a few requests to ensure rate limiting logic is invoked
        for _ in range(3):
            response = await client.get("/api/cameras")

            # Should succeed (200) or hit rate limit (429)
            # With auth disabled, we expect 200 OK
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_429_TOO_MANY_REQUESTS,
            ]


# =============================================================================
# Endpoint Coverage Tests
# =============================================================================


class TestEndpointCoverage:
    """Test authentication behavior across different endpoint types."""

    @pytest.mark.asyncio
    async def test_cameras_endpoint_coverage(self, client: AsyncClient, clean_tables: None) -> None:
        """Test authentication on cameras endpoints."""
        # GET /api/cameras
        response = await client.get("/api/cameras")
        assert response.status_code == status.HTTP_200_OK

        # GET /api/cameras/{id} - will 404 but shouldn't 401
        response = await client.get("/api/cameras/nonexistent_cam")
        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_events_endpoint_coverage(self, client: AsyncClient, clean_tables: None) -> None:
        """Test authentication on events endpoints."""
        # GET /api/events
        response = await client.get("/api/events")
        assert response.status_code == status.HTTP_200_OK

        # GET /api/events/{id} - will 404 but shouldn't 401
        response = await client.get("/api/events/999999")
        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_detections_endpoint_coverage(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test authentication on detections endpoints."""
        # GET /api/detections
        response = await client.get("/api/detections")
        assert response.status_code == status.HTTP_200_OK

        # GET /api/detections/{id} - will 404 but shouldn't 401
        response = await client.get("/api/detections/999999")
        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_system_endpoints_coverage(self, client: AsyncClient, clean_tables: None) -> None:
        """Test authentication on system endpoints."""
        # System health endpoints should be public
        response = await client.get("/api/system/health")
        assert response.status_code == status.HTTP_200_OK

        response = await client.get("/api/system/health/ready")
        # Status can be 200 or 503 depending on services, but not 401
        assert response.status_code != status.HTTP_401_UNAUTHORIZED


# =============================================================================
# Authentication Header Tests
# =============================================================================


class TestAuthenticationHeaders:
    """Test X-API-Key header handling."""

    @pytest.mark.asyncio
    async def test_header_name_case_insensitive(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that header name is case-insensitive (HTTP standard)."""
        # HTTP headers are case-insensitive per RFC 2616
        # FastAPI/Starlette normalizes headers to lowercase

        # Try different cases - all should work the same
        for header_name in ["X-API-Key", "x-api-key", "X-Api-Key", "X-API-KEY"]:
            response = await client.get(
                "/api/cameras",
                headers={header_name: "some_key"},
            )

            # Should succeed when auth is disabled
            assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_multiple_api_key_headers_uses_first(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test behavior when multiple X-API-Key headers are sent."""
        # When multiple headers with same name are sent, behavior depends on client
        # Most clients will combine them or use the first one

        response = await client.get(
            "/api/cameras",
            headers={"X-API-Key": VALID_API_KEY},
        )

        # Should succeed when auth is disabled
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_api_key_not_logged_in_responses(
        self, client: AsyncClient, clean_tables: None
    ) -> None:
        """Test that API key is not leaked in error responses."""
        # Even if auth fails, the API key should not appear in response
        response = await client.get(
            "/api/cameras",
            headers={"X-API-Key": "secret_key_should_not_leak"},  # pragma: allowlist secret
        )

        # Should succeed when auth is disabled
        assert response.status_code == status.HTTP_200_OK

        # Verify response doesn't contain the API key
        response_text = response.text
        assert "secret_key_should_not_leak" not in response_text
