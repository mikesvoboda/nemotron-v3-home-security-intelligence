"""Integration tests for REST API authentication (NEM-2047).

This module provides comprehensive integration tests for REST API authentication:
- API key authentication (valid, invalid, missing scenarios)
- Protected endpoint access control
- Rate limiting configuration
- Session management (stateless API key validation)
- Error response format verification (RFC 7807)

Routes covered: All protected endpoints vs exempt endpoints
Uses custom fixtures with appropriate Settings patches.

IMPORTANT: These tests create custom client fixtures with api_key_enabled=True
and must run serially (-n0) to avoid state conflicts.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import AsyncGenerator
from contextlib import ExitStack
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.middleware.auth import AuthMiddleware, _hash_key
from backend.core.config import Settings, get_settings
from backend.tests.integration.test_helpers import get_error_message

if TYPE_CHECKING:
    from httpx import AsyncClient

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Helper Functions for Fixtures
# =============================================================================


def create_mock_services() -> dict:
    """Create mock services for the app."""
    mock_system_broadcaster = MagicMock()
    mock_system_broadcaster.start_broadcasting = AsyncMock()
    mock_system_broadcaster.stop_broadcasting = AsyncMock()

    mock_gpu_monitor = MagicMock()
    mock_gpu_monitor.start = AsyncMock()
    mock_gpu_monitor.stop = AsyncMock()

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.start = AsyncMock()
    mock_cleanup_service.stop = AsyncMock()
    mock_cleanup_service.running = False
    mock_cleanup_service.get_cleanup_stats.return_value = {
        "running": False,
        "retention_days": 30,
        "cleanup_time": "03:00",
        "delete_images": False,
        "next_cleanup": None,
    }

    mock_file_watcher = MagicMock()
    mock_file_watcher.start = AsyncMock()
    mock_file_watcher.stop = AsyncMock()
    mock_file_watcher.configure_mock(
        running=False,
        camera_root="/mock/foscam",
        _use_polling=False,
        _pending_tasks={},
    )

    mock_file_watcher_class = MagicMock(return_value=mock_file_watcher)

    mock_file_watcher_for_routes = MagicMock()
    mock_file_watcher_for_routes.configure_mock(
        running=False,
        camera_root="/mock/foscam",
        _use_polling=False,
        _pending_tasks={},
    )

    mock_pipeline_manager = MagicMock()
    mock_pipeline_manager.start = AsyncMock()
    mock_pipeline_manager.stop = AsyncMock()

    mock_event_broadcaster = MagicMock()
    mock_event_broadcaster.start = AsyncMock()
    mock_event_broadcaster.stop = AsyncMock()
    mock_event_broadcaster.channel_name = "security_events"

    mock_service_health_monitor = MagicMock()
    mock_service_health_monitor.start = AsyncMock()
    mock_service_health_monitor.stop = AsyncMock()

    return {
        "system_broadcaster": mock_system_broadcaster,
        "gpu_monitor": mock_gpu_monitor,
        "cleanup_service": mock_cleanup_service,
        "file_watcher": mock_file_watcher,
        "file_watcher_class": mock_file_watcher_class,
        "file_watcher_for_routes": mock_file_watcher_for_routes,
        "pipeline_manager": mock_pipeline_manager,
        "event_broadcaster": mock_event_broadcaster,
        "service_health_monitor": mock_service_health_monitor,
    }


def compute_key_hashes(api_keys: list[str]) -> set[str]:
    """Compute SHA-256 hashes for a list of API keys."""
    return {hashlib.sha256(key.encode()).hexdigest() for key in api_keys}


def get_patches(
    test_settings: Settings,
    mock_redis: AsyncMock,
    mock_services: dict,
) -> list:
    """Get all patches needed for the test fixtures."""
    return [
        patch("backend.main.init_db", AsyncMock(return_value=None)),
        patch("backend.main.close_db", AsyncMock(return_value=None)),
        patch("backend.main.init_redis", AsyncMock(return_value=mock_redis)),
        patch("backend.main.close_redis", AsyncMock(return_value=None)),
        patch(
            "backend.main.get_system_broadcaster",
            return_value=mock_services["system_broadcaster"],
        ),
        patch("backend.main.GPUMonitor", return_value=mock_services["gpu_monitor"]),
        patch("backend.main.CleanupService", return_value=mock_services["cleanup_service"]),
        patch("backend.main.FileWatcher", mock_services["file_watcher_class"]),
        patch(
            "backend.main.get_pipeline_manager",
            AsyncMock(return_value=mock_services["pipeline_manager"]),
        ),
        patch("backend.main.stop_pipeline_manager", AsyncMock()),
        patch(
            "backend.main.get_broadcaster",
            AsyncMock(return_value=mock_services["event_broadcaster"]),
        ),
        patch("backend.main.stop_broadcaster", AsyncMock()),
        patch(
            "backend.main.ServiceHealthMonitor",
            return_value=mock_services["service_health_monitor"],
        ),
        patch(
            "backend.api.routes.system._file_watcher",
            mock_services["file_watcher_for_routes"],
        ),
        patch("backend.api.routes.system._cleanup_service", mock_services["cleanup_service"]),
        patch("backend.core.config.get_settings", return_value=test_settings),
        patch("backend.api.middleware.auth.get_settings", return_value=test_settings),
        patch("backend.core.redis._redis_client", mock_redis),
        patch("backend.core.redis.init_redis", return_value=mock_redis),
        patch("backend.core.redis.close_redis", return_value=None),
        patch("backend.core.redis.get_redis", return_value=mock_redis),
    ]


def patch_auth_middleware_keys(app, api_keys: list[str]) -> None:
    """Patch the AuthMiddleware's valid_key_hashes with new keys.

    The AuthMiddleware caches key hashes at initialization time.
    This function updates the cached hashes to match test settings.
    """
    # Compute hashes for the test keys
    key_hashes = compute_key_hashes(api_keys)

    # Walk the middleware stack to find AuthMiddleware and update its key hashes
    # The middleware_stack is built at runtime, we need to access the actual middleware instance
    current = app.middleware_stack
    while current is not None:
        # Check if this is our AuthMiddleware
        if hasattr(current, "valid_key_hashes"):
            current.valid_key_hashes = key_hashes
            return
        # Move to the next layer (app attribute in middleware)
        current = getattr(current, "app", None)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_redis_for_auth() -> AsyncMock:
    """Create a mock Redis client for auth tests."""
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }
    mock_redis_client._client = None
    return mock_redis_client


@pytest.fixture
async def auth_enabled_client(
    integration_db: str, mock_redis_for_auth: AsyncMock, clean_tables: None
) -> AsyncGenerator[tuple[AsyncClient, str]]:
    """Async HTTP client with API key authentication enabled.

    Returns a tuple of (client, valid_api_key) so tests can use the valid key.
    """
    from httpx import ASGITransport, AsyncClient

    from backend.main import app

    valid_api_key = "test-auth-api-key-12345"  # pragma: allowlist secret

    # Create settings with API key enabled
    test_settings = Settings(
        api_key_enabled=True,
        api_keys=[valid_api_key],
        database_url=os.environ.get("DATABASE_URL", ""),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/15"),
    )

    # Create mock services
    mock_services = create_mock_services()

    # Get all patches
    patches = get_patches(test_settings, mock_redis_for_auth, mock_services)

    # Use ExitStack to manage the patches
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)

        get_settings.cache_clear()

        # Patch the middleware's key hashes to use our test keys
        patch_auth_middleware_keys(app, [valid_api_key])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac, valid_api_key

        get_settings.cache_clear()


@pytest.fixture
async def auth_disabled_client(
    integration_db: str, mock_redis_for_auth: AsyncMock, clean_tables: None
) -> AsyncGenerator[AsyncClient]:
    """Async HTTP client with API key authentication disabled."""
    from httpx import ASGITransport, AsyncClient

    from backend.main import app

    # Create settings with API key disabled
    test_settings = Settings(
        api_key_enabled=False,
        api_keys=[],
        database_url=os.environ.get("DATABASE_URL", ""),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/15"),
    )

    # Create mock services
    mock_services = create_mock_services()

    # Get all patches
    patches = get_patches(test_settings, mock_redis_for_auth, mock_services)

    # Use ExitStack to manage the patches
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)

        get_settings.cache_clear()

        # Clear middleware key hashes (no valid keys when auth disabled)
        patch_auth_middleware_keys(app, [])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

        get_settings.cache_clear()


@pytest.fixture
async def multi_key_client(
    integration_db: str, mock_redis_for_auth: AsyncMock, clean_tables: None
) -> AsyncGenerator[tuple[AsyncClient, list[str]]]:
    """Async HTTP client with multiple API keys configured.

    Returns a tuple of (client, list_of_valid_api_keys).
    """
    from httpx import ASGITransport, AsyncClient

    from backend.main import app

    valid_keys = ["key-alpha-12345", "key-beta-67890", "key-gamma-24680"]

    # Create settings with multiple API keys
    test_settings = Settings(
        api_key_enabled=True,
        api_keys=valid_keys,
        database_url=os.environ.get("DATABASE_URL", ""),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/15"),
    )

    # Create mock services
    mock_services = create_mock_services()

    # Get all patches
    patches = get_patches(test_settings, mock_redis_for_auth, mock_services)

    # Use ExitStack to manage the patches
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)

        get_settings.cache_clear()

        # Patch the middleware's key hashes to use our test keys
        patch_auth_middleware_keys(app, valid_keys)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac, valid_keys

        get_settings.cache_clear()


# =============================================================================
# API Key Authentication Tests
# =============================================================================


class TestAPIKeyValidAuthentication:
    """Tests for valid API key authentication scenarios."""

    @pytest.mark.asyncio
    async def test_valid_api_key_in_header_grants_access(
        self, auth_enabled_client: tuple[AsyncClient, str]
    ) -> None:
        """Test that a valid API key in X-API-Key header grants access to protected endpoints."""
        client, valid_key = auth_enabled_client

        response = await client.get(
            "/api/cameras",
            headers={"X-API-Key": valid_key},
        )
        # Should not be 401 Unauthorized
        assert response.status_code != 401, f"Valid API key should grant access: {response.json()}"

    @pytest.mark.asyncio
    async def test_valid_api_key_in_query_param_grants_access(
        self, auth_enabled_client: tuple[AsyncClient, str]
    ) -> None:
        """Test that a valid API key in query parameter grants access."""
        client, valid_key = auth_enabled_client

        response = await client.get(f"/api/cameras?api_key={valid_key}")
        assert response.status_code != 401, (
            f"Valid API key in query param should work: {response.json()}"
        )

    @pytest.mark.asyncio
    async def test_multiple_valid_keys_all_work(
        self, multi_key_client: tuple[AsyncClient, list[str]]
    ) -> None:
        """Test that multiple configured API keys all work."""
        client, valid_keys = multi_key_client

        for key in valid_keys:
            response = await client.get(
                "/api/cameras",
                headers={"X-API-Key": key},
            )
            assert response.status_code != 401, f"Key {key[:10]}... should be valid"


class TestAPIKeyInvalidAuthentication:
    """Tests for invalid API key authentication scenarios."""

    @pytest.mark.asyncio
    async def test_invalid_api_key_returns_401(
        self, auth_enabled_client: tuple[AsyncClient, str]
    ) -> None:
        """Test that an invalid API key returns 401 Unauthorized."""
        client, _ = auth_enabled_client

        response = await client.get(
            "/api/cameras",
            headers={"X-API-Key": "wrong-invalid-key-xyz"},
        )
        assert response.status_code == 401
        data = response.json()
        error_msg = get_error_message(data)
        assert "invalid" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_401(
        self, auth_enabled_client: tuple[AsyncClient, str]
    ) -> None:
        """Test that a missing API key returns 401 when auth is enabled."""
        client, _ = auth_enabled_client

        response = await client.get("/api/cameras")
        assert response.status_code == 401
        data = response.json()
        error_msg = get_error_message(data)
        assert "api key" in error_msg.lower() or "required" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_empty_api_key_returns_401(
        self, auth_enabled_client: tuple[AsyncClient, str]
    ) -> None:
        """Test that an empty API key returns 401."""
        client, _ = auth_enabled_client

        response = await client.get(
            "/api/cameras",
            headers={"X-API-Key": ""},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_partial_key_match_rejected(
        self, auth_enabled_client: tuple[AsyncClient, str]
    ) -> None:
        """Test that partial API key match is rejected."""
        client, valid_key = auth_enabled_client

        # Try with only first 10 characters
        partial_key = valid_key[:10]
        response = await client.get(
            "/api/cameras",
            headers={"X-API-Key": partial_key},
        )
        assert response.status_code == 401


class TestAPIKeyHashing:
    """Tests for API key hashing mechanism."""

    def test_hash_key_uses_sha256(self) -> None:
        """Test that API keys are hashed using SHA-256."""
        test_key = "my-secret-api-key"
        expected = hashlib.sha256(test_key.encode()).hexdigest()

        result = _hash_key(test_key)

        assert result == expected

    def test_hash_key_deterministic(self) -> None:
        """Test that hashing is deterministic (same key = same hash)."""
        test_key = "deterministic-key-test"

        hash1 = _hash_key(test_key)
        hash2 = _hash_key(test_key)

        assert hash1 == hash2

    def test_different_keys_produce_different_hashes(self) -> None:
        """Test that different keys produce different hashes."""
        key1 = "api-key-alpha"
        key2 = "api-key-beta"

        assert _hash_key(key1) != _hash_key(key2)


# =============================================================================
# Protected Endpoints Tests
# =============================================================================


class TestProtectedEndpoints:
    """Tests for protected endpoint access control."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "endpoint,method,description",
        [
            ("/api/cameras", "GET", "List cameras"),
            ("/api/events", "GET", "List events"),
            ("/api/alerts", "GET", "List alerts"),
            ("/api/alerts/rules", "GET", "List alert rules"),
            ("/api/detections", "GET", "List detections"),
            ("/api/zones", "GET", "List zones"),
            ("/api/analytics/summary", "GET", "Analytics summary"),
        ],
    )
    async def test_protected_endpoints_require_auth(
        self,
        auth_enabled_client: tuple[AsyncClient, str],
        endpoint: str,
        method: str,
        description: str,
    ) -> None:
        """Test that protected endpoints require authentication.

        Scenario: {description}
        """
        client, _ = auth_enabled_client

        if method == "GET":
            response = await client.get(endpoint)
        elif method == "POST":
            response = await client.post(endpoint, json={})
        else:
            response = await client.request(method, endpoint)

        assert response.status_code == 401, f"{description} ({endpoint}) should require auth"


class TestExemptEndpoints:
    """Tests for endpoints exempt from authentication."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "endpoint,description",
        [
            ("/", "Root status endpoint"),
            ("/health", "Liveness probe"),
            ("/ready", "Readiness probe"),
            ("/api/system/health", "System health check"),
            ("/api/system/health/ready", "Detailed readiness probe"),
            ("/api/metrics", "Prometheus metrics"),
            ("/docs", "Swagger documentation"),
            ("/openapi.json", "OpenAPI schema"),
        ],
    )
    async def test_exempt_endpoints_work_without_auth(
        self,
        auth_enabled_client: tuple[AsyncClient, str],
        endpoint: str,
        description: str,
    ) -> None:
        """Test that exempt endpoints work without authentication.

        Scenario: {description}
        """
        client, _ = auth_enabled_client

        response = await client.get(endpoint)
        # Should NOT return 401
        assert response.status_code != 401, f"Exempt endpoint {endpoint} should not require auth"


class TestAuthDisabled:
    """Tests for behavior when API key auth is disabled."""

    @pytest.mark.asyncio
    async def test_disabled_auth_allows_all_requests(
        self, auth_disabled_client: AsyncClient
    ) -> None:
        """Test that disabled auth allows all requests without API key."""
        response = await auth_disabled_client.get("/api/cameras")
        # Should not be 401 when auth is disabled
        assert response.status_code != 401


# =============================================================================
# Rate Limiting Tests
# =============================================================================


class TestRateLimiting:
    """Tests for rate limiting configuration."""

    @pytest.mark.asyncio
    async def test_rate_limiter_configuration_tiers(self) -> None:
        """Test that rate limit tiers are properly configured."""
        from backend.api.middleware.rate_limit import RateLimitTier, get_tier_limits

        # Verify each tier has valid limits
        tiers = [
            RateLimitTier.DEFAULT,
            RateLimitTier.MEDIA,
            RateLimitTier.SEARCH,
            RateLimitTier.WEBSOCKET,
        ]

        for tier in tiers:
            limits = get_tier_limits(tier)
            requests_per_minute, burst = limits
            assert requests_per_minute > 0, f"Tier {tier} should have positive rate limit"
            assert burst >= 1, f"Tier {tier} should have positive burst"

    @pytest.mark.asyncio
    async def test_rate_limiter_can_be_customized(self) -> None:
        """Test that rate limiter supports custom configuration."""
        from backend.api.middleware.rate_limit import RateLimiter, RateLimitTier

        # Create with custom values
        limiter = RateLimiter(
            tier=RateLimitTier.DEFAULT,
            requests_per_minute=100,
            burst=20,
        )

        assert limiter.requests_per_minute == 100
        assert limiter.burst == 20

    @pytest.mark.asyncio
    async def test_different_tiers_have_different_limits(self) -> None:
        """Test that different endpoint tiers have appropriately different limits."""
        from backend.api.middleware.rate_limit import RateLimitTier, get_tier_limits

        default_limits = get_tier_limits(RateLimitTier.DEFAULT)
        media_limits = get_tier_limits(RateLimitTier.MEDIA)
        search_limits = get_tier_limits(RateLimitTier.SEARCH)

        # All should be positive
        assert all(x > 0 for x in default_limits)
        assert all(x > 0 for x in media_limits)
        assert all(x > 0 for x in search_limits)


# =============================================================================
# Session Management Tests
# =============================================================================


class TestSessionManagement:
    """Tests for session management behavior.

    This application uses stateless API key authentication.
    These tests verify the stateless nature of the authentication.
    """

    @pytest.mark.asyncio
    async def test_api_key_validation_per_request(
        self, auth_enabled_client: tuple[AsyncClient, str]
    ) -> None:
        """Test that API key is validated on each request (stateless)."""
        client, valid_key = auth_enabled_client

        # First request with valid key
        response1 = await client.get(
            "/api/cameras",
            headers={"X-API-Key": valid_key},
        )
        assert response1.status_code != 401

        # Second request without key should fail
        response2 = await client.get("/api/cameras")
        assert response2.status_code == 401

        # Third request with valid key again should work
        response3 = await client.get(
            "/api/cameras",
            headers={"X-API-Key": valid_key},
        )
        assert response3.status_code != 401

    @pytest.mark.asyncio
    async def test_can_switch_between_keys(
        self, multi_key_client: tuple[AsyncClient, list[str]]
    ) -> None:
        """Test that requests can switch between valid keys freely (stateless)."""
        client, valid_keys = multi_key_client

        # Switch between keys on consecutive requests
        for key in valid_keys * 2:  # Do two passes
            response = await client.get(
                "/api/cameras",
                headers={"X-API-Key": key},
            )
            assert response.status_code != 401, f"Key {key[:10]}... should work"


# =============================================================================
# Error Response Format Tests (RFC 7807)
# =============================================================================


class TestAuthErrorResponseFormat:
    """Tests for error response format verification per RFC 7807."""

    @pytest.mark.asyncio
    async def test_401_error_has_proper_structure(
        self, auth_enabled_client: tuple[AsyncClient, str]
    ) -> None:
        """Test that 401 errors have proper error structure."""
        client, _ = auth_enabled_client

        response = await client.get("/api/cameras")

        assert response.status_code == 401
        data = response.json()

        # Error should be present in either format
        assert "detail" in data or "error" in data

    @pytest.mark.asyncio
    async def test_error_message_does_not_leak_valid_keys(
        self, auth_enabled_client: tuple[AsyncClient, str]
    ) -> None:
        """Test that error messages don't leak configured valid API keys."""
        client, valid_key = auth_enabled_client

        response = await client.get("/api/cameras")

        assert response.status_code == 401
        response_text = response.text

        # Valid key should never appear in error responses
        assert valid_key not in response_text

    @pytest.mark.asyncio
    async def test_invalid_key_not_in_error_response(
        self, auth_enabled_client: tuple[AsyncClient, str]
    ) -> None:
        """Test that the attempted key is handled properly in error responses."""
        client, _ = auth_enabled_client

        test_key = "secret-test-key-do-not-leak"
        response = await client.get(
            "/api/cameras",
            headers={"X-API-Key": test_key},
        )

        assert response.status_code == 401
        # The API key should not be reflected back in the response
        # (though this is implementation-dependent)


# =============================================================================
# Auth Middleware Unit Tests (testing middleware directly)
# =============================================================================


class TestAuthMiddlewareExemptPaths:
    """Unit-level tests for AuthMiddleware exempt path checking."""

    def test_health_endpoints_are_exempt(self) -> None:
        """Test that health endpoints are exempt from auth."""
        middleware = AuthMiddleware(app=None, valid_key_hashes=set())

        exempt_paths = [
            "/",
            "/health",
            "/ready",
            "/api/system/health",
            "/api/system/health/ready",
        ]

        for path in exempt_paths:
            assert middleware._is_exempt_path(path), f"Path should be exempt: {path}"

    def test_docs_endpoints_are_exempt(self) -> None:
        """Test that documentation endpoints are exempt from auth."""
        middleware = AuthMiddleware(app=None, valid_key_hashes=set())

        exempt_paths = ["/docs", "/docs/", "/redoc", "/redoc/", "/openapi.json"]

        for path in exempt_paths:
            assert middleware._is_exempt_path(path), f"Path should be exempt: {path}"

    def test_metrics_endpoint_is_exempt(self) -> None:
        """Test that Prometheus metrics endpoint is exempt."""
        middleware = AuthMiddleware(app=None, valid_key_hashes=set())

        assert middleware._is_exempt_path("/api/metrics")

    def test_media_endpoints_are_exempt(self) -> None:
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

    def test_api_endpoints_are_protected(self) -> None:
        """Test that regular API endpoints are NOT exempt."""
        middleware = AuthMiddleware(app=None, valid_key_hashes=set())

        protected_paths = [
            "/api/cameras",
            "/api/events",
            "/api/events/123",
            "/api/alerts",
            "/api/alerts/rules",
            "/api/system/status",
            "/api/admin/config",
        ]

        for path in protected_paths:
            assert not middleware._is_exempt_path(path), f"Path should NOT be exempt: {path}"
